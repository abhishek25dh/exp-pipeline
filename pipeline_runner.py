#!/usr/bin/env python3
"""
Pipeline Runner
===============
Full pipeline orchestrator with real-time web UI.
Run: python pipeline_runner.py
Open: http://localhost:5577
"""

import os, sys, json, glob, subprocess, threading, time, datetime, queue, re, copy
from pathlib import Path
from flask import Flask, Response, jsonify, render_template_string, request, stream_with_context

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
PY = sys.executable

PORT = 5577
STATE_FILE  = BASE_DIR / "pipeline_state.json"
TIMING_FILE = BASE_DIR / "pipeline_timing.json"

# ─── Global State ──────────────────────────────────────────────────────────────
_state = {
    "status": "idle",   # idle | running | paused | completed | failed
    "run_id": None,
    "para_numbers": [],
    "scene_numbers": [],
    "scene_filter": [],  # when non-empty: process only these scene numbers
    "runpod_url": "",
    "layout_exclude": "",
    "start_time": None,
    "end_time": None,
    "steps": {},        # task_id → {status, start, end, duration}
    "error": None,
}
_state_lock = threading.Lock()

_log_buffer  = []          # last 1000 messages
_log_lock    = threading.Lock()
_sse_clients = []          # list of queue.Queue per connected browser tab
_sse_lock    = threading.Lock()

_active_procs     = []
_active_procs_lock = threading.Lock()

_pipeline_thread = None
_stop_event      = threading.Event()
_manual_mode     = False
_manual_continue = threading.Event()   # set when user clicks "Run Next Step"

_timing = {}               # persisted timing data across runs
_openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()


# ─── Persistence ───────────────────────────────────────────────────────────────

def _load_timing():
    global _timing
    if TIMING_FILE.exists():
        try:
            _timing = json.loads(TIMING_FILE.read_text(encoding="utf-8"))
        except Exception:
            _timing = {}

def _save_timing():
    TIMING_FILE.write_text(json.dumps(_timing, indent=2), encoding="utf-8")

def _save_state():
    with _state_lock:
        data = copy.deepcopy(_state)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _load_state():
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            with _state_lock:
                _state.update(saved)
        except Exception:
            pass


def _safe_delete(path: Path):
    try:
        if path.is_dir():
            for child in path.iterdir():
                _safe_delete(child)
            path.rmdir()
        elif path.exists():
            path.unlink()
    except Exception:
        pass


def _current_openrouter_key():
    return (_openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")).strip()


def _reset_pipeline_data():
    patterns = [
        "assets/para/para_*.json",
        "assets/scene_prompts/scene_*_prompt.json",
        "assets/scenes/para*.json",
        "assets/directorscript/scene_*_director.json",
        "assets/scenes_audio/scene_*.mp3",
        "assets/scenes_audio/scene_*_transcript_full.json",
        "assets/image_prompts/scene_*_image_prompts.json",
        "assets/timings/scene_*_timings.json",
        "assets/outputs/scene_*",
        "assets/tmp/*.json",
        "tmp/*.json",
    ]
    for pattern in patterns:
        for p in glob.glob(str(BASE_DIR / pattern)):
            _safe_delete(Path(p))
    # Clear state/timing files
    global _timing
    _timing = {}
    _save_timing()
    with _state_lock:
        _state.update({
            "status": "idle",
            "run_id": None,
            "para_numbers": [],
            "scene_numbers": [],
            "scene_filter": [],
            "steps": {},
            "error": None,
            "start_time": None,
            "end_time": None,
        })
    _save_state()


# ─── Broadcast / Logging ───────────────────────────────────────────────────────

def _broadcast(msg_type, **kw):
    msg = {"type": msg_type, "ts": round(time.time(), 3), **kw}
    with _log_lock:
        _log_buffer.append(msg)
        if len(_log_buffer) > 1000:
            _log_buffer.pop(0)
    with _sse_lock:
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass

def _log(text, level="info", task=None):
    _broadcast("log", text=text, level=level, task=task)

def _update_task(task_id, **kw):
    with _state_lock:
        if task_id not in _state["steps"]:
            _state["steps"][task_id] = {}
        _state["steps"][task_id].update(kw)
    _broadcast("task", task_id=task_id, **kw)
    _save_state()

def _push_stats():
    _broadcast("stats", **_live_stats())


# ─── File System Helpers ───────────────────────────────────────────────────────

def _count(pattern):
    return len(glob.glob(str(BASE_DIR / pattern)))

def _live_stats():
    mp3s   = _count("assets/scenes_audio/scene_*.mp3")
    jsons  = _count("assets/scenes_audio/scene_*_transcript_full.json")
    imgs   = _count("assets/outputs/scene_*/*.png") + _count("assets/outputs/scene_*/*.jpg")
    dirs   = _count("assets/directorscript/scene_*_director.json")
    prompts= _count("assets/scene_prompts/scene_*_prompt.json")
    iprpts = _count("assets/image_prompts/scene_*_image_prompts.json")
    tims   = _count("assets/timings/scene_*_timings.json")
    paras  = _count("assets/para/para_*.json")
    scenes = _count("assets/scenes/para*.json")
    return {
        "paras": paras,
        "scene_prompts": prompts,
        "para_scenes": scenes,
        "director_scripts": dirs,
        "scene_audio": mp3s,
        "scene_transcripts": jsons,
        "image_prompts": iprpts,
        "timings": tims,
        "images": imgs,
        "total_scenes": prompts,
    }

def _detect_para_numbers():
    nums = []
    for f in glob.glob(str(BASE_DIR / "assets/para/para_*.json")):
        m = re.search(r'para_(\d+)\.json', f)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)

def _detect_scene_numbers():
    nums = []
    for f in glob.glob(str(BASE_DIR / "assets/scene_prompts/scene_*_prompt.json")):
        m = re.search(r'scene_(\d+)_prompt\.json', f)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


# ─── Completion Checks (for resume / skip) ────────────────────────────────────

def _done_script_py():
    return (BASE_DIR / "tmp/background_audio_transcript_full.json").exists()

def _done_docx_to_paras():
    return _count("assets/para/para_*.json") > 0

def _done_layout_selector(para):
    for f in glob.glob(str(BASE_DIR / "assets/scene_prompts/scene_*_prompt.json")):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            if str(d.get("para_id")) == str(para):
                return True
        except Exception:
            pass
    return False

def _done_para_to_scenes(para):
    return (BASE_DIR / f"assets/scenes/para{para}.json").exists()

def _done_layout_creator(scene):
    return (BASE_DIR / f"assets/directorscript/scene_{scene}_director.json").exists()

def _done_audiocutter():
    director_scenes = {
        int(m.group(1))
        for p in (BASE_DIR / "assets/directorscript").glob("scene_*_director.json")
        for m in [__import__('re').search(r'scene_(\d+)_director', p.name)] if m
    }
    if not director_scenes:
        return False
    return all((BASE_DIR / f"assets/scenes_audio/scene_{s}.mp3").exists() for s in director_scenes)

def _done_audiocutter_para(para, scenes):
    """All scenes belonging to this para have audio cuts."""
    return all((BASE_DIR / f"assets/scenes_audio/scene_{s}.mp3").exists() for s in scenes)

def _done_scenes_scripts(scene):
    return (BASE_DIR / f"assets/scenes_audio/scene_{scene}_transcript_full.json").exists()

def _done_generate_prompts(scene):
    path = BASE_DIR / f"assets/image_prompts/scene_{scene}_image_prompts.json"
    if not path.exists():
        return False
    try:
        # Determine which image filenames this scene needs prompts for
        director = BASE_DIR / f"assets/directorscript/scene_{scene}_director.json"
        required_filenames = set()
        if director.exists():
            ddata = json.loads(director.read_text(encoding="utf-8"))
            for del_ in ddata.get("elements", []):
                fn = del_.get("filename", "")
                if not fn:
                    continue
                # Skip shared static assets — not generated per-scene
                if fn.startswith("host_") or fn == "arrow.png":
                    continue
                required_filenames.add(fn)

        # Text-only scene: no image prompts needed — done as long as file exists
        if not required_filenames:
            return True

        data = json.loads(path.read_text(encoding="utf-8"))
        elements = data.get("elements", [])
        if not elements:
            return False
        for el in elements:
            if not isinstance(el, dict) or "image_prompt" not in el or "filename" not in el:
                return False
            # image_prompt must be a non-empty string
            if not isinstance(el["image_prompt"], str) or not el["image_prompt"].strip():
                return False
        # Cross-check: every required filename must have a matching prompt
        prompt_filenames = {el["filename"] for el in elements}
        for fn in required_filenames:
            if fn not in prompt_filenames:
                return False
        return True
    except Exception:
        return False

def _done_timings(scene):
    return (BASE_DIR / f"assets/timings/scene_{scene}_timings.json").exists()

def _done_image_gen():
    return _count("assets/outputs/scene_*/*.png") > 0

def _get_scenes_for_para(para):
    """Return sorted list of scene numbers whose para_id matches this para."""
    scenes = []
    for f in glob.glob(str(BASE_DIR / "assets/scene_prompts/scene_*_prompt.json")):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            if str(d.get("para_id")) == str(para):
                m = re.search(r"scene_(\d+)_prompt", Path(f).name)
                if m:
                    scenes.append(int(m.group(1)))
        except Exception:
            pass
    return sorted(scenes)


def _para_for_scene(scene):
    """Return the para_id (as int) that owns this scene, or None."""
    p = BASE_DIR / f"assets/scene_prompts/scene_{scene}_prompt.json"
    if p.exists():
        try:
            return int(json.loads(p.read_text(encoding="utf-8"))["para_id"])
        except Exception:
            pass
    return None


# ─── Subprocess + Parallel Runner ─────────────────────────────────────────────

def _run(cmd, task_id, env_extra=None, periodic_stats_on=None):
    """Run a subprocess, stream its output line by line. Returns True on success."""
    if _stop_event.is_set():
        return False

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    openrouter_key = _current_openrouter_key()
    if openrouter_key:
        env["OPENROUTER_API_KEY"] = openrouter_key
    if env_extra:
        env.update(env_extra)

    cmd_str = " ".join(str(c) for c in cmd)
    _log(f"$ {cmd_str}", level="cmd", task=task_id)
    _update_task(task_id, status="running", start=round(time.time(), 3))

    start_ts = time.time()
    proc = None
    try:
        proc = subprocess.Popen(
            [str(c) for c in cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(BASE_DIR),
            env=env,
        )
        with _active_procs_lock:
            _active_procs.append(proc)

        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _log(line, level="out", task=task_id)
                if periodic_stats_on and periodic_stats_on in line:
                    _push_stats()
            if _stop_event.is_set():
                proc.kill()
                _log("Stopped by user.", level="warn", task=task_id)
                return False

        proc.wait()
        elapsed = round(time.time() - start_ts, 2)
        success = proc.returncode == 0
        status  = "completed" if success else "failed"
        level   = "ok" if success else "err"
        symbol  = "✓" if success else "✗"

        _update_task(task_id, status=status, end=round(time.time(), 3), duration=elapsed)

        # Record to timing data
        run_id = _state.get("run_id", "unknown")
        if run_id not in _timing:
            _timing[run_id] = {}
        _timing[run_id][task_id] = {
            "cmd": cmd_str,
            "start_ts": start_ts,
            "duration_s": elapsed,
            "status": status,
        }
        _save_timing()
        _push_stats()

        _log(f"{symbol} {task_id} — {elapsed:.1f}s", level=level, task=task_id)
        return success

    except Exception as e:
        _log(f"Exception running {task_id}: {e}", level="err", task=task_id)
        _update_task(task_id, status="failed")
        return False
    finally:
        with _active_procs_lock:
            if proc and proc in _active_procs:
                _active_procs.remove(proc)


def _run_parallel(tasks):
    """Run list of (cmd, task_id, env_extra) in parallel. Returns True if all succeeded."""
    results = {}
    threads = []

    def _worker(cmd, task_id, env_extra):
        results[task_id] = _run(cmd, task_id, env_extra)

    for cmd, task_id, env_extra in tasks:
        t = threading.Thread(target=_worker, args=(cmd, task_id, env_extra), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return all(results.values())


def _skip(task_id, reason="already exists"):
    _log(f"⟳  Skipping {task_id} — {reason}", level="skip", task=task_id)
    _update_task(task_id, status="skipped")


def _await_manual(step_name):
    """In manual mode: broadcast waiting state and block until user clicks Run Step."""
    with _state_lock:
        _state["waiting_for"] = step_name
    _broadcast("waiting", step_name=step_name)
    _save_state()
    if not _manual_mode:
        return
    _manual_continue.clear()
    _log(f"\n  ⏸  Manual mode — click [Run Next Step] to start: {step_name}", level="warn")
    while not _stop_event.is_set():
        if _manual_continue.wait(timeout=0.5):
            break
    with _state_lock:
        _state["waiting_for"] = None


# ─── Pipeline Main ─────────────────────────────────────────────────────────────

def _pipeline_main():
    try:
        run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with _state_lock:
            _state["run_id"] = run_id
            _state["status"] = "running"
            _state["start_time"] = round(time.time(), 3)
        _save_state()

        para_numbers  = _state.get("para_numbers") or _detect_para_numbers()
        runpod_url    = _state.get("runpod_url", "")
        scene_filter  = [int(s) for s in (_state.get("scene_filter") or []) if str(s).isdigit()]

        # When all target scenes already have scene prompt files, skip Steps 1–2 layout selection
        _all_prompts_exist = (
            bool(scene_filter) and
            all((BASE_DIR / f"assets/scene_prompts/scene_{s}_prompt.json").exists() for s in scene_filter)
        )

        with _state_lock:
            _state["para_numbers"] = para_numbers

        _log("═" * 56, level="info")
        _log(f"  Pipeline started  |  Run: {run_id}", level="ok")
        _log(f"  Paras: {para_numbers}", level="info")
        if scene_filter:
            _log(f"  Target scenes: {scene_filter}  (scene-prompts → image-prompts mode)", level="info")
            if _all_prompts_exist:
                _log(f"  Scene prompts found — skipping Steps 1–2 layout selection, stopping after Step 4", level="info")
        _log(f"  OpenRouter key: {'set' if _current_openrouter_key() else 'not set'}", level="info")
        _log("═" * 56, level="info")

        # ── STEP 1 ── Parallel: script.py + docx_to_paras.py ─────────────────
        _await_manual("Step 1 — Transcribe Audio + Extract Paras")
        if _stop_event.is_set(): raise StopIteration()
        _log("\n▶ STEP 1 — Transcribe Audio + Extract Paras", level="step")
        if _all_prompts_exist:
            _skip("script_py", "scene prompts exist — skipping audio transcription")
            _skip("docx_to_paras", "scene prompts exist — skipping para extraction")
        else:
            tasks = []
            if _done_script_py():
                _skip("script_py", "transcript already exists")
            else:
                tasks.append(([PY, "script.py"], "script_py", None))

            if _done_docx_to_paras():
                _skip("docx_to_paras", "para files already exist")
            else:
                tasks.append(([PY, "docx_to_paras.py"], "docx_to_paras", None))

            if tasks and not _run_parallel(tasks):
                raise RuntimeError("Step 1 failed")
            if _stop_event.is_set():
                raise StopIteration()

        # Re-detect para numbers now that docx_to_paras.py has run (or from existing files)
        para_numbers = _detect_para_numbers()
        with _state_lock:
            _state["para_numbers"] = para_numbers
        _log(f"  Detected {len(para_numbers)} para(s): {para_numbers}", level="info")
        _save_state()

        # ── STEP 2 ── Streaming: layout_selector (sequential) → downstream per para ──
        # As each para's layout_selector finishes, immediately fire para_to_scenes +
        # layout_creator for its scenes in a background thread — overlapping with the
        # next para's layout_selector call.
        _await_manual("Step 2 — Layout Selection + Director Scripts")
        if _stop_event.is_set(): raise StopIteration()
        _log("\n▶ STEP 2 — Layout Selection + Director Scripts (streaming)", level="step")

        stream_errors = []
        stream_errors_lock = threading.Lock()
        para_threads = []

        # In target-scene mode, only process paras that contain the target scenes
        if scene_filter:
            known_paras = {_para_for_scene(s) for s in scene_filter}
            known_paras.discard(None)
            effective_paras = sorted(known_paras) if known_paras else para_numbers
            scene_filter_set = set(scene_filter)
        else:
            effective_paras = para_numbers
            scene_filter_set = set()

        def _downstream_para(para, scenes):
            try:
                if _stop_event.is_set(): return
                # In target-scene mode restrict layout_creator to only the target scenes
                if scene_filter_set:
                    scenes = [s for s in scenes if s in scene_filter_set]
                # para_to_scenes + layout_creator for each scene — all parallel
                tasks = []
                if _done_para_to_scenes(para):
                    _skip(f"para_to_scenes_{para}")
                else:
                    tasks.append(([PY, "para_to_scenes.py", str(para)], f"para_to_scenes_{para}", None))
                for s in scenes:
                    if _done_layout_creator(s):
                        _skip(f"layout_creator_{s}")
                    else:
                        tasks.append(([PY, "layout_creator.py", str(s)], f"layout_creator_{s}", None))
                if tasks and not _run_parallel(tasks):
                    raise RuntimeError(f"para_to_scenes/layout_creator failed for para {para}")
            except Exception as exc:
                with stream_errors_lock:
                    stream_errors.append(str(exc))

        for para in effective_paras:
            if _stop_event.is_set(): raise StopIteration()
            tid = f"layout_selector_{para}"
            if _done_layout_selector(para):
                _skip(tid, f"scene prompts for para {para} already exist")
            else:
                env_extra = None
                with _state_lock:
                    exclude = (_state.get("layout_exclude") or "").strip()
                if exclude:
                    env_extra = {"LAYOUT_EXCLUDE": exclude}
                if not _run([PY, "layout_selector.py", str(para)], tid, env_extra):
                    raise RuntimeError(f"layout_selector.py {para} failed")
            scenes = _get_scenes_for_para(para)
            with _state_lock:
                _state["scene_numbers"] = _detect_scene_numbers()
            _save_state()
            if scenes:
                t = threading.Thread(target=_downstream_para, args=(para, scenes), daemon=True)
                t.start()
                para_threads.append(t)

        for t in para_threads:
            t.join()

        if stream_errors:
            raise RuntimeError("Step 2 streaming errors: " + "; ".join(stream_errors))
        if _stop_event.is_set(): raise StopIteration()

        scene_numbers = _detect_scene_numbers()
        # In target-scene mode, restrict all downstream steps to only the target scenes
        if scene_filter:
            scene_numbers = sorted(s for s in scene_numbers if s in scene_filter_set)
            _log(f"  Filtered to target scenes: {scene_numbers}", level="info")
        else:
            _log(f"  Detected {len(scene_numbers)} total scenes: {scene_numbers}", level="info")
        with _state_lock:
            _state["scene_numbers"] = scene_numbers
        _save_state()
        _push_stats()

        # ── STEP 3 ── audiocutter (single batch — loads audio once) ──────────
        _await_manual("Step 3 — Cut Scene Audio")
        if _stop_event.is_set(): raise StopIteration()
        _log("\n▶ STEP 3 — Cut Scene Audio", level="step")

        # In target-scene mode, check only whether the target scenes have audio
        _audio_done = (
            all((BASE_DIR / f"assets/scenes_audio/scene_{s}.mp3").exists() for s in scene_numbers)
            if scene_filter else _done_audiocutter()
        )
        if _audio_done:
            _skip("audiocutter", "scene audio already exists")
        else:
            args = [str(p) for p in effective_paras]
            if not _run([PY, "audiocutter.py"] + args, "audiocutter"):
                raise RuntimeError("audiocutter.py failed")
            # Delete stale transcripts for target scenes so scenes_scripts re-transcribes
            for s in scene_numbers:
                _stale = BASE_DIR / f"assets/scenes_audio/scene_{s}_transcript_full.json"
                if _stale.exists():
                    _stale.unlink()
            if scene_filter:
                missing = [s for s in scene_numbers if not (BASE_DIR / f"assets/scenes_audio/scene_{s}.mp3").exists()]
            else:
                missing = [
                    s for s in {
                        int(m.group(1))
                        for p in (BASE_DIR / "assets/directorscript").glob("scene_*_director.json")
                        for m in [__import__('re').search(r'scene_(\d+)_director', p.name)] if m
                    }
                    if not (BASE_DIR / f"assets/scenes_audio/scene_{s}.mp3").exists()
                ]
            if missing:
                raise RuntimeError(f"audiocutter.py completed but missing audio for scenes: {sorted(missing)}")
        if _stop_event.is_set(): raise StopIteration()
        _push_stats()

        # ── STEP 4 ── Streaming: scenes_scripts → generate_prompts + timings ─
        # Each scene flows independently: as soon as its transcript is done,
        # generate_prompts and timings fire immediately — no waiting for other scenes.
        _await_manual("Step 4 — Transcribe Scenes + Image Prompts + Timings")
        if _stop_event.is_set(): raise StopIteration()
        _log("\n▶ STEP 4 — Transcribe + Prompts + Timings (streaming per scene)", level="step")

        stream_errors = []
        stream_errors_lock = threading.Lock()
        scene_threads = []

        def _downstream_scene(scene):
            try:
                if _stop_event.is_set(): return
                # scenes_scripts
                if not _done_scenes_scripts(scene):
                    if not _run([PY, "scenes_scripts.py", str(scene)], f"scenes_scripts_{scene}"):
                        raise RuntimeError(f"scenes_scripts.py {scene} failed")
                else:
                    _skip(f"scenes_scripts_{scene}")
                if _stop_event.is_set(): return
                # generate_prompts (with validation + retry) + timings in parallel
                tasks = []
                if not _done_generate_prompts(scene):
                    # Run generate_prompts first, validate, retry up to 3 times
                    prompts_ok = False
                    for attempt in range(1, 4):
                        tid = f"gen_prompts_{scene}" if attempt == 1 else f"gen_prompts_{scene}_retry{attempt}"
                        _run([PY, "generate_prompts.py", str(scene)], tid)
                        if _done_generate_prompts(scene):
                            prompts_ok = True
                            break
                        # Delete corrupted output before retry
                        bad = BASE_DIR / f"assets/image_prompts/scene_{scene}_image_prompts.json"
                        if bad.exists():
                            _log(f"  Corrupted image prompts for scene {scene} (attempt {attempt}/3), retrying...", level="warn", task=f"gen_prompts_{scene}")
                            bad.unlink()
                    if not prompts_ok:
                        raise RuntimeError(f"generate_prompts failed for scene {scene} after 3 attempts (corrupted output)")
                else:
                    _skip(f"gen_prompts_{scene}")
                if not _done_timings(scene):
                    tasks.append(([PY, "timings.py", str(scene)], f"timings_{scene}", None))
                else:
                    _skip(f"timings_{scene}")
                if tasks and not _run_parallel(tasks):
                    raise RuntimeError(f"timings failed for scene {scene}")
            except Exception as exc:
                with stream_errors_lock:
                    stream_errors.append(str(exc))

        for scene in scene_numbers:
            if _stop_event.is_set(): raise StopIteration()
            t = threading.Thread(target=_downstream_scene, args=(scene,), daemon=True)
            t.start()
            scene_threads.append(t)

        for t in scene_threads:
            t.join()

        if stream_errors:
            raise RuntimeError("Step 4 streaming errors: " + "; ".join(stream_errors))
        if _stop_event.is_set(): raise StopIteration()
        _push_stats()

        if scene_filter:
            # Target-scene mode: stop here — image prompts are done, skip image generation
            _log("\n⟳  Target-scene mode — stopping after image prompts (Step 5 skipped)", level="skip")
        else:
            # ── PRE-FLIGHT: validate image prompts before generation ─────────────
            # Auto-detect and regenerate corrupted/incomplete image prompt files
            bad_scenes = [s for s in scene_numbers if not _done_generate_prompts(s)]
            if bad_scenes:
                _log(f"\n⚠ Pre-flight: {len(bad_scenes)} scene(s) have bad/missing image prompts: {sorted(bad_scenes)}", level="warn")
                for scene in bad_scenes:
                    if _stop_event.is_set(): raise StopIteration()
                    bad_path = BASE_DIR / f"assets/image_prompts/scene_{scene}_image_prompts.json"
                    if bad_path.exists():
                        _log(f"  Deleting corrupt/incomplete prompts for scene {scene}", level="warn")
                        bad_path.unlink()
                    prompts_ok = False
                    for attempt in range(1, 4):
                        tid = f"preflight_gen_prompts_{scene}" if attempt == 1 else f"preflight_gen_prompts_{scene}_retry{attempt}"
                        _run([PY, "generate_prompts.py", str(scene)], tid)
                        if _done_generate_prompts(scene):
                            prompts_ok = True
                            _log(f"  ✓ Regenerated image prompts for scene {scene}", level="ok")
                            break
                        bad_path2 = BASE_DIR / f"assets/image_prompts/scene_{scene}_image_prompts.json"
                        if bad_path2.exists():
                            _log(f"  Retry {attempt}/3 — still corrupt for scene {scene}", level="warn")
                            bad_path2.unlink()
                    if not prompts_ok:
                        _log(f"  ✗ Failed to regenerate prompts for scene {scene} after 3 attempts", level="err")

            # ── STEP 5 ── image.py → ComfyUI ─────────────────────────────────────
            _await_manual("Step 5 — Generate Images (ComfyUI)")
            if _stop_event.is_set(): raise StopIteration()
            _log("\n▶ STEP 5 — Generate Images (ComfyUI)", level="step")
            # Always run image.py — it skips already-generated images internally
            env_extra = {"RUNPOD_URL": runpod_url} if runpod_url else {}
            if not _run([PY, "image.py"], "image_gen", env_extra, periodic_stats_on="Saved to:"):
                raise RuntimeError("image.py failed")
            _push_stats()

        # ── DONE ─────────────────────────────────────────────────────────────
        with _state_lock:
            _state["status"] = "completed"
            _state["end_time"] = round(time.time(), 3)
        _save_state()
        elapsed = _state["end_time"] - _state["start_time"]
        _log("\n" + "═" * 56, level="info")
        _log(f"  ✓ Pipeline complete — {elapsed/60:.1f} min total", level="ok")
        _log("═" * 56, level="info")
        _broadcast("done")

    except StopIteration:
        with _state_lock:
            _state["status"] = "paused"
        _save_state()
        _log("\n  Paused. Click Resume to continue from where you left off.", level="warn")
        _broadcast("paused")

    except Exception as e:
        with _state_lock:
            _state["status"] = "failed"
            _state["error"] = str(e)
        _save_state()
        _log(f"\n  ✗ Pipeline failed: {e}", level="err")
        _broadcast("failed", error=str(e))


# ─── Flask Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/stream")
def stream():
    client_q = queue.Queue(maxsize=500)
    with _sse_lock:
        _sse_clients.append(client_q)
    with _log_lock:
        backlog = list(_log_buffer[-300:])
    for msg in backlog:
        try:
            client_q.put_nowait(msg)
        except queue.Full:
            break

    def generate():
        try:
            while True:
                try:
                    msg = client_q.get(timeout=20)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield 'data: {"type":"ping"}\n\n'
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if client_q in _sse_clients:
                    _sse_clients.remove(client_q)

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/status")
def status():
    with _state_lock:
        s = copy.deepcopy(_state)
    s["openrouter_key_set"] = bool(_current_openrouter_key())
    s["stats"] = _live_stats()
    if s["start_time"] and not s["end_time"]:
        s["elapsed"] = round(time.time() - s["start_time"], 1)
    elif s["start_time"] and s["end_time"]:
        s["elapsed"] = round(s["end_time"] - s["start_time"], 1)
    else:
        s["elapsed"] = 0
    return jsonify(s)


@app.route("/start", methods=["POST"])
def start():
    global _pipeline_thread
    global _openrouter_api_key
    data = request.get_json(silent=True) or {}
    if _state["status"] == "running":
        return jsonify({"error": "Already running"}), 400
    # Ensure the old pipeline thread is fully dead before starting a new one
    if _pipeline_thread is not None and _pipeline_thread.is_alive():
        _stop_event.set()
        _pipeline_thread.join(timeout=10)
        if _pipeline_thread.is_alive():
            return jsonify({"error": "Previous pipeline thread still alive, try again shortly"}), 409

    para_numbers   = data.get("para_numbers") or _detect_para_numbers()
    runpod_url     = (data.get("runpod_url") or "").strip()
    layout_exclude = (data.get("layout_exclude") or "").strip()
    openrouter_key = (data.get("openrouter_api_key") or "").strip()
    raw_filter     = data.get("scene_filter") or []
    scene_filter   = [int(s) for s in raw_filter if str(s).isdigit()] if raw_filter else []
    if openrouter_key:
        _openrouter_api_key = openrouter_key

    with _state_lock:
        _state.update({
            "status": "idle",
            "para_numbers": para_numbers,
            "scene_filter": scene_filter,
            "runpod_url": runpod_url,
            "layout_exclude": layout_exclude,
            "steps": {},
            "error": None,
            "start_time": None,
            "end_time": None,
        })
    _stop_event.clear()
    _pipeline_thread = threading.Thread(target=_pipeline_main, daemon=True)
    _pipeline_thread.start()
    return jsonify({"ok": True, "para_numbers": para_numbers, "scene_filter": scene_filter})


@app.route("/resume", methods=["POST"])
def resume():
    global _pipeline_thread
    global _openrouter_api_key
    data = request.get_json(silent=True) or {}
    if _state["status"] == "running":
        return jsonify({"error": "Already running"}), 400
    # Ensure the old pipeline thread is fully dead before starting a new one
    if _pipeline_thread is not None and _pipeline_thread.is_alive():
        _stop_event.set()
        _pipeline_thread.join(timeout=10)
        if _pipeline_thread.is_alive():
            return jsonify({"error": "Previous pipeline thread still alive, try again shortly"}), 409
    runpod_url = (data.get("runpod_url") or _state.get("runpod_url") or "").strip()
    layout_exclude = (data.get("layout_exclude") or _state.get("layout_exclude") or "").strip()
    openrouter_key = (data.get("openrouter_api_key") or "").strip()
    if openrouter_key:
        _openrouter_api_key = openrouter_key
    with _state_lock:
        _state["runpod_url"] = runpod_url
        _state["layout_exclude"] = layout_exclude
        _state["start_time"] = _state.get("start_time") or round(time.time(), 3)
    _stop_event.clear()
    _pipeline_thread = threading.Thread(target=_pipeline_main, daemon=True)
    _pipeline_thread.start()
    return jsonify({"ok": True})


@app.route("/stop", methods=["POST"])
def stop():
    _stop_event.set()
    with _active_procs_lock:
        for proc in _active_procs:
            try:
                proc.kill()
            except Exception:
                pass
    return jsonify({"ok": True})


@app.route("/timing_data")
def timing_data():
    return jsonify(_timing)


@app.route("/detect_paras")
def detect_paras():
    return jsonify({"para_numbers": _detect_para_numbers()})


@app.route("/set_mode", methods=["POST"])
def set_mode():
    global _manual_mode
    data = request.get_json(silent=True) or {}
    _manual_mode = bool(data.get("manual", False))
    with _state_lock:
        _state["manual_mode"] = _manual_mode
    _save_state()
    return jsonify({"ok": True, "manual": _manual_mode})


@app.route("/continue_step", methods=["POST"])
def continue_step():
    _manual_continue.set()
    return jsonify({"ok": True})

@app.route("/reset", methods=["POST"])
def reset():
    if _state.get("status") == "running":
        return jsonify({"error": "Pipeline is running"}), 400
    data = request.get_json(silent=True) or {}
    if not data.get("confirm"):
        return jsonify({"error": "Confirmation required"}), 400
    _reset_pipeline_data()
    _broadcast("reset")
    _push_stats()
    return jsonify({"ok": True})


@app.route("/clear_step/<task_id>", methods=["POST"])
def clear_step(task_id):
    """Mark a completed/failed step as pending so it runs again on next start."""
    with _state_lock:
        if task_id in _state["steps"]:
            _state["steps"][task_id]["status"] = "pending"
    _save_state()
    return jsonify({"ok": True})


@app.route("/gen_image_prompts", methods=["POST"])
def gen_image_prompts():
    """Run generate_prompts.py for all detected scenes in parallel."""
    if _state.get("status") == "running":
        return jsonify({"error": "Pipeline is running"}), 400

    data = request.get_json(silent=True) or {}
    global _openrouter_api_key
    openrouter_key = (data.get("openrouter_api_key") or "").strip()
    if openrouter_key:
        _openrouter_api_key = openrouter_key

    def _run_it():
        scenes = _detect_scene_numbers()
        if not scenes:
            _log("No scenes found in assets/scene_prompts/.", level="warn", task="gen_img_prompts")
            return
        _log(f"\n▶ Generating image prompts for {len(scenes)} scene(s): {scenes}", level="step", task="gen_img_prompts")
        tasks = [([PY, "generate_prompts.py", str(s)], f"gen_prompts_{s}", None) for s in scenes]
        ok = _run_parallel(tasks)
        _log("Image prompts complete." if ok else "Some image prompts failed.", level="ok" if ok else "err", task="gen_img_prompts")
        _push_stats()
        _broadcast("gen_prompts_done", ok=ok)

    threading.Thread(target=_run_it, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/gen_images", methods=["POST"])
def gen_images():
    """Run image.py to send all image prompts to ComfyUI."""
    if _state.get("status") == "running":
        return jsonify({"error": "Pipeline is running"}), 400

    data = request.get_json(silent=True) or {}
    runpod_url = (data.get("runpod_url") or "").strip()
    global _openrouter_api_key
    openrouter_key = (data.get("openrouter_api_key") or "").strip()
    if openrouter_key:
        _openrouter_api_key = openrouter_key

    def _run_it():
        _log("\n▶ Generating images via ComfyUI...", level="step", task="image_gen")
        env_extra = {"RUNPOD_URL": runpod_url} if runpod_url else {}
        ok = _run([PY, "image.py"], "image_gen", env_extra, periodic_stats_on="Saved to:")
        _log("Image generation complete." if ok else "Image generation failed.", level="ok" if ok else "err", task="image_gen")
        _push_stats()
        _broadcast("gen_images_done", ok=ok)

    threading.Thread(target=_run_it, daemon=True).start()
    return jsonify({"ok": True})


# ─── HTML Template ─────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pipeline Runner</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#c9d1d9;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* Top bar */
.topbar{background:#161b22;border-bottom:1px solid #30363d;padding:10px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;flex-shrink:0}
.topbar .title{font-weight:700;font-size:15px;color:#fff;letter-spacing:.5px;margin-right:4px}
.badge{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.badge-idle    {background:#21262d;color:#8b949e}
.badge-running {background:#1f4e2a;color:#3fb950;animation:pulse 1.5s ease-in-out infinite}
.badge-paused  {background:#3d2a00;color:#d29922}
.badge-completed{background:#1f4e2a;color:#3fb950}
.badge-failed  {background:#4e1f1f;color:#f85149}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
.topbar input[type=text]{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:5px 10px;border-radius:6px;font-size:12px;width:280px}
.topbar input[type=text]:focus{outline:none;border-color:#58a6ff}
.topbar input[type=number]{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:5px 8px;border-radius:6px;font-size:12px;width:80px}
.topbar label{font-size:11px;color:#8b949e;white-space:nowrap}
.btn{padding:6px 14px;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;letter-spacing:.3px}
.btn-start {background:#238636;color:#fff}
.btn-start:hover{background:#2ea043}
.btn-stop  {background:#b62324;color:#fff}
.btn-stop:hover{background:#da3633}
.btn-resume{background:#d29922;color:#000}
.btn-resume:hover{background:#e3b341}
.btn-dl    {background:#21262d;color:#c9d1d9;border:1px solid #30363d}
.btn-dl:hover{background:#30363d}
.btn-reset {background:#3a1c1c;color:#f85149;border:1px solid #8b1f1f}
.btn-reset:hover{background:#4e1f1f}
.btn-mode  {background:#21262d;color:#8b949e;border:1px solid #30363d}
.btn-mode.manual{background:#3d2a00;color:#d29922;border-color:#d29922}
.btn-prompts{background:#1a3050;color:#79c0ff;border:1px solid #2c4a7c}
.btn-prompts:hover{background:#213a63}
.btn-prompts.busy{background:#1f4e2a;color:#3fb950;border-color:#2ea043;animation:pulse 1.5s ease-in-out infinite}
.btn-imggen {background:#2d1f4e;color:#c084fc;border:1px solid #5b3e9e}
.btn-imggen:hover{background:#3a2860}
.btn-imggen.busy{background:#1f4e2a;color:#3fb950;border-color:#2ea043;animation:pulse 1.5s ease-in-out infinite}
.btn:disabled{opacity:.4;cursor:not-allowed}

/* Waiting banner */
.wait-banner{display:none;background:#1c1400;border:1px solid #d29922;border-radius:8px;margin:10px 14px;padding:12px 16px;align-items:center;gap:12px}
.wait-banner.show{display:flex}
.wait-banner .wicon{font-size:20px}
.wait-banner .wtext{flex:1;font-size:13px;color:#e3b341}
.wait-banner .wstep{font-size:11px;color:#8b949e;margin-top:2px}
.btn-run-step{background:#d29922;color:#000;font-weight:700;padding:8px 18px;border:none;border-radius:6px;cursor:pointer;font-size:13px}
.btn-run-step:hover{background:#e3b341}
.elapsed{font-size:12px;color:#8b949e;font-variant-numeric:tabular-nums;min-width:60px}

/* Main layout */
.main{display:flex;flex:1;overflow:hidden}

/* Left: Steps panel */
.steps-panel{width:320px;flex-shrink:0;border-right:1px solid #30363d;display:flex;flex-direction:column;overflow:hidden}
.steps-header{padding:10px 14px;font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #30363d;flex-shrink:0}
.steps-scroll{flex:1;overflow-y:auto;padding:8px}

.step-group{margin-bottom:6px;border:1px solid #21262d;border-radius:8px;overflow:hidden}
.step-group-header{padding:8px 12px;background:#161b22;display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
.step-group-header:hover{background:#1c2128}
.step-icon{font-size:14px;width:18px;text-align:center;flex-shrink:0}
.step-name{flex:1;font-size:12px;font-weight:600;color:#c9d1d9}
.step-dur{font-size:10px;color:#8b949e;font-variant-numeric:tabular-nums;white-space:nowrap}
.step-badge{font-size:9px;font-weight:700;padding:1px 6px;border-radius:10px;text-transform:uppercase}
.sb-pending  {background:#21262d;color:#8b949e}
.sb-running  {background:#1f4e2a;color:#3fb950}
.sb-completed{background:#1a3a1a;color:#3fb950}
.sb-failed   {background:#4e1f1f;color:#f85149}
.sb-skipped  {background:#21262d;color:#6e7681}

.task-list{padding:4px 8px 8px 8px;background:#0d1117}
.task-row{display:flex;align-items:center;gap:6px;padding:4px 6px;border-radius:4px;cursor:pointer}
.task-row:hover{background:#161b22}
.task-row.active{background:#1c2128;border-left:2px solid #58a6ff}
.task-icon{font-size:11px;width:14px;text-align:center;flex-shrink:0}
.task-name{font-size:11px;color:#c9d1d9;flex:1}
.task-dur{font-size:10px;color:#8b949e;font-variant-numeric:tabular-nums}

/* Progress bar */
.overall-bar{padding:8px 14px;border-top:1px solid #21262d;flex-shrink:0}
.overall-bar .label{font-size:10px;color:#8b949e;display:flex;justify-content:space-between;margin-bottom:4px}
.bar-track{height:5px;background:#21262d;border-radius:3px;overflow:hidden}
.bar-fill{height:100%;background:linear-gradient(90deg,#238636,#3fb950);border-radius:3px;transition:width .5s}

/* Right panel */
.right-panel{flex:1;display:flex;flex-direction:column;overflow:hidden}

/* Stats row */
.stats-row{display:flex;gap:8px;padding:10px 14px;border-bottom:1px solid #30363d;flex-wrap:wrap;flex-shrink:0;background:#161b22}
.stat-card{background:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px 12px;min-width:80px;text-align:center}
.stat-card .sv{font-size:18px;font-weight:700;color:#58a6ff;font-variant-numeric:tabular-nums;line-height:1.2}
.stat-card .sl{font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}

/* Log filter */
.log-controls{display:flex;align-items:center;gap:8px;padding:8px 14px;border-bottom:1px solid #30363d;flex-shrink:0}
.log-controls label{font-size:11px;color:#8b949e}
.log-controls select{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:3px 8px;border-radius:4px;font-size:11px}
.log-controls .search{background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:3px 8px;border-radius:4px;font-size:11px;flex:1}
.log-controls .search:focus{outline:none;border-color:#58a6ff}
.cb-autoscroll{display:flex;align-items:center;gap:4px;font-size:11px;color:#8b949e;cursor:pointer}

/* Log */
.log-panel{flex:1;overflow-y:auto;padding:8px 14px;font-family:'Cascadia Code','Consolas','Courier New',monospace;font-size:11.5px;line-height:1.7}
.log-line{white-space:pre-wrap;word-break:break-all;padding:1px 0}
.l-info{color:#8b949e}
.l-ok  {color:#3fb950}
.l-err {color:#f85149}
.l-warn{color:#d29922}
.l-cmd {color:#79c0ff;font-style:italic}
.l-out {color:#c9d1d9}
.l-step{color:#d2a8ff;font-weight:700;margin-top:4px}
.l-skip{color:#6e7681;font-style:italic}
.l-ts  {color:#484f58;margin-right:6px;user-select:none}
.hidden{display:none!important}
</style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
  <span class="title">⬡ Pipeline Runner</span>
  <span id="status-badge" class="badge badge-idle">IDLE</span>
  <span class="elapsed" id="elapsed-display">00:00</span>

  <label>RunPod URL</label>
  <input type="text" id="runpod-url" placeholder="xxxx-8188.proxy.runpod.net">

  <label>OpenRouter Key</label>
  <input type="password" id="openrouter-key" placeholder="optional; leave blank to keep current" style="width:260px">

  <label style="color:#58a6ff; font-weight:bold;">Target Scenes</label>
  <input type="text" id="scene-filter" placeholder="e.g. 12, 15" title="Comma-separated scene numbers to generate" style="width:100px; border-color:#58a6ff;">

  <label>Para #s</label>
  <input type="text" id="para-nums" placeholder="1,2,3 or blank=auto" style="width:150px">

  <label>Exclude Layouts</label>
  <input type="text" id="layout-exclude" placeholder="e.g. 2,4,8" style="width:120px">

  <button class="btn btn-start"  id="btn-start"  onclick="startPipeline()">▶ Start</button>
  <button class="btn btn-stop"   id="btn-stop"   onclick="stopPipeline()"  disabled>■ Stop</button>
  <button class="btn btn-resume" id="btn-resume" onclick="resumePipeline()" disabled>↺ Resume</button>
  <button class="btn btn-mode"   id="btn-mode"   onclick="toggleMode()">⚡ Auto Mode</button>
  <button class="btn btn-dl"     onclick="downloadTiming()">⬇ Timing JSON</button>
  <button class="btn btn-reset"  id="btn-reset" onclick="resetPipeline()">Reset</button>
  <div style="width:1px;height:24px;background:#30363d;margin:0 4px"></div>
  <button class="btn btn-prompts" id="btn-gen-prompts" onclick="genImagePrompts()">⬡ Gen Image Prompts</button>
  <button class="btn btn-imggen"  id="btn-gen-images"  onclick="genImages()">⬡ Gen Images</button>
</div>

<!-- MAIN -->
<div class="main">

  <!-- LEFT: Steps panel -->
  <div class="steps-panel">
    <div class="steps-header">Pipeline Steps</div>
    <div class="steps-scroll" id="steps-container"></div>
    <div class="overall-bar">
      <div class="label">
        <span>Overall Progress</span>
        <span id="pct-label">0%</span>
      </div>
      <div class="bar-track"><div class="bar-fill" id="overall-bar" style="width:0%"></div></div>
    </div>
  </div>

  <!-- RIGHT -->
  <div class="right-panel">

    <!-- Stats -->
    <div class="stats-row" id="stats-row">
      <div class="stat-card"><div class="sv" id="s-paras">0</div><div class="sl">Paras</div></div>
      <div class="stat-card"><div class="sv" id="s-scene_prompts">0</div><div class="sl">Scene Prompts</div></div>
      <div class="stat-card"><div class="sv" id="s-director_scripts">0</div><div class="sl">Director Scripts</div></div>
      <div class="stat-card"><div class="sv" id="s-scene_audio">0</div><div class="sl">Scene Audio</div></div>
      <div class="stat-card"><div class="sv" id="s-scene_transcripts">0</div><div class="sl">Transcripts</div></div>
      <div class="stat-card"><div class="sv" id="s-image_prompts">0</div><div class="sl">Img Prompts</div></div>
      <div class="stat-card"><div class="sv" id="s-timings">0</div><div class="sl">Timings</div></div>
      <div class="stat-card"><div class="sv" id="s-images">0</div><div class="sl">Images</div></div>
    </div>

    <!-- Waiting banner (manual mode) -->
    <div class="wait-banner" id="wait-banner">
      <span class="wicon">⏸</span>
      <div>
        <div class="wtext">Manual Mode — pipeline is waiting for you</div>
        <div class="wstep" id="wait-step-name"></div>
      </div>
      <button class="btn-run-step" onclick="runNextStep()">▶ Run Next Step</button>
    </div>

    <!-- Log controls -->
    <div class="log-controls">
      <label>Filter task:</label>
      <select id="filter-task" onchange="applyFilter()">
        <option value="">All tasks</option>
      </select>
      <input class="search" id="filter-search" placeholder="Search log..." oninput="applyFilter()">
      <label class="cb-autoscroll">
        <input type="checkbox" id="autoscroll" checked> Auto-scroll
      </label>
      <button class="btn btn-dl" onclick="clearLog()" style="padding:3px 10px;font-size:11px">Clear</button>
    </div>

    <!-- Log panel -->
    <div class="log-panel" id="log-panel"></div>

  </div>
</div>

<script>
// ─── State ────────────────────────────────────────────────────────────────────
const taskState = {};      // task_id → {status, start, end, duration}
const logLines  = [];      // all log messages
let   filterTask   = "";
let   filterSearch = "";
let   activeFilter = "";   // task clicked in left panel
let   elapsedStart = null;
let   elapsedTimer = null;

// ─── Pipeline step definitions (left panel structure) ─────────────────────────
const STEP_DEFS = [
  { id: "s1", name: "Step 1 — Transcribe + Extract Paras", parallel: true,
    tasks: [
      { id: "script_py",     name: "script.py",         desc: "Transcribe full audio (AssemblyAI)" },
      { id: "docx_to_paras", name: "docx_to_paras.py",  desc: "Extract paras from script.docx" },
    ]},
  { id: "s2", name: "Step 2 — Layout Selection + Director Scripts (streaming)", parallel: true, dynamic: "s2",
    tasks: [] },
  { id: "s3", name: "Step 3 — Cut Scene Audio", parallel: false,
    tasks: [{ id: "audiocutter", name: "audiocutter.py", desc: "Cut audio per scene" }]},
  { id: "s4", name: "Step 4 — Transcribe + Prompts + Timings (streaming)", parallel: true, dynamic: "s4",
    tasks: [] },
  { id: "s5", name: "Step 5 — Generate Images (ComfyUI)", parallel: false,
    tasks: [{ id: "image_gen", name: "image.py", desc: "Send all prompts to ComfyUI" }]},
];

// ─── Build step panel ─────────────────────────────────────────────────────────
function buildStepPanel(paraNumbers, sceneNumbers) {
  // Inject dynamic tasks
  // Step 2: layout_selector per para + para_to_scenes per para + layout_creator per scene
  const s2 = STEP_DEFS.find(s => s.id === "s2");
  const lsTasks = (paraNumbers || []).map(n => ({
    id: `layout_selector_${n}`, name: `layout_selector.py ${n}`, desc: `Para ${n} — layout select`
  }));
  const ptTasks = (paraNumbers || []).map(n => ({
    id: `para_to_scenes_${n}`, name: `para_to_scenes.py ${n}`, desc: `Para ${n} — scene breakdown`
  }));
  const lcTasks = (sceneNumbers || []).map(n => ({
    id: `layout_creator_${n}`, name: `layout_creator.py ${n}`, desc: `Scene ${n} director`
  }));
  s2.tasks = [...lsTasks, ...ptTasks, ...lcTasks];

  // Step 4: scenes_scripts + generate_prompts + timings per scene
  const s4 = STEP_DEFS.find(s => s.id === "s4");
  const ssTasks  = (sceneNumbers || []).map(n => ({
    id: `scenes_scripts_${n}`, name: `scenes_scripts.py ${n}`, desc: `Scene ${n} transcript`
  }));
  const gpTasks  = (sceneNumbers || []).map(n => ({
    id: `gen_prompts_${n}`, name: `generate_prompts.py ${n}`, desc: `Scene ${n} prompts`
  }));
  const timTasks = (sceneNumbers || []).map(n => ({
    id: `timings_${n}`, name: `timings.py ${n}`, desc: `Scene ${n} timings`
  }));
  s4.tasks = [...ssTasks, ...gpTasks, ...timTasks];

  // Rebuild filter dropdown
  const sel = document.getElementById("filter-task");
  sel.innerHTML = '<option value="">All tasks</option>';

  const container = document.getElementById("steps-container");
  container.innerHTML = "";

  STEP_DEFS.forEach(step => {
    const allTasks = step.tasks;
    const grp = document.createElement("div");
    grp.className = "step-group";
    grp.id = "grp-" + step.id;

    const hdr = document.createElement("div");
    hdr.className = "step-group-header";
    const parallelTag = step.parallel ? ' <span style="font-size:9px;color:#8b949e;margin-left:4px">⇉ parallel</span>' : '';
    hdr.innerHTML = `
      <span class="step-icon" id="sicon-${step.id}">○</span>
      <span class="step-name">${step.name}${parallelTag}</span>
      <span class="step-badge sb-pending" id="sbadge-${step.id}">pending</span>
      <span class="step-dur" id="sdur-${step.id}"></span>`;
    hdr.onclick = () => { const tl = grp.querySelector(".task-list"); tl.style.display = tl.style.display === "none" ? "" : "none"; };

    const taskList = document.createElement("div");
    taskList.className = "task-list";

    allTasks.forEach(task => {
      const row = document.createElement("div");
      row.className = "task-row";
      row.id = "trow-" + task.id;
      row.innerHTML = `
        <span class="task-icon" id="ticon-${task.id}">○</span>
        <span class="task-name">${task.name}</span>
        <span class="task-dur" id="tdur-${task.id}"></span>`;
      row.onclick = (e) => { e.stopPropagation(); setActiveFilter(task.id); };
      taskList.appendChild(row);

      const opt = document.createElement("option");
      opt.value = task.id;
      opt.textContent = task.name;
      sel.appendChild(opt);
    });

    grp.appendChild(hdr);
    grp.appendChild(taskList);
    container.appendChild(grp);
  });
}

// ─── Task state rendering ─────────────────────────────────────────────────────
const STATUS_ICON  = { pending:"○", running:"⟳", completed:"✓", failed:"✗", skipped:"–" };
const STATUS_COLOR = { pending:"#8b949e", running:"#3fb950", completed:"#3fb950", failed:"#f85149", skipped:"#6e7681" };
const BADGE_CLASS  = { pending:"sb-pending", running:"sb-running", completed:"sb-completed", failed:"sb-failed", skipped:"sb-skipped" };

function updateTaskUI(taskId, data) {
  taskState[taskId] = Object.assign(taskState[taskId] || {}, data);
  const st = taskState[taskId].status || "pending";
  const dur = taskState[taskId].duration;

  const icon = document.getElementById("ticon-" + taskId);
  const durEl = document.getElementById("tdur-" + taskId);
  const row   = document.getElementById("trow-" + taskId);
  if (icon) { icon.textContent = STATUS_ICON[st] || "○"; icon.style.color = STATUS_COLOR[st]; }
  if (durEl && dur) { durEl.textContent = fmtSec(dur); }
  if (row) { row.style.opacity = st === "skipped" ? "0.5" : "1"; }

  // Update parent step badge
  STEP_DEFS.forEach(step => {
    if (!step.tasks.find(t => t.id === taskId)) return;
    const statuses = step.tasks.map(t => (taskState[t.id] || {}).status || "pending");
    let stepSt = "pending";
    if (statuses.every(s => s === "completed" || s === "skipped")) stepSt = "completed";
    else if (statuses.some(s => s === "failed")) stepSt = "failed";
    else if (statuses.some(s => s === "running")) stepSt = "running";

    const sIcon  = document.getElementById("sicon-" + step.id);
    const sBadge = document.getElementById("sbadge-" + step.id);
    if (sIcon)  { sIcon.textContent = STATUS_ICON[stepSt]; sIcon.style.color = STATUS_COLOR[stepSt]; }
    if (sBadge) { sBadge.className = "step-badge " + (BADGE_CLASS[stepSt] || "sb-pending"); sBadge.textContent = stepSt; }

    // Step duration = max duration among tasks
    const durs = step.tasks.map(t => (taskState[t.id] || {}).duration || 0);
    const maxDur = Math.max(...durs);
    const sDur = document.getElementById("sdur-" + step.id);
    if (sDur && maxDur > 0) sDur.textContent = fmtSec(maxDur);
  });

  updateProgress();
}

function updateProgress() {
  const allTasks = STEP_DEFS.flatMap(s => s.tasks);
  const total = allTasks.length;
  if (total === 0) return;
  const done = allTasks.filter(t => {
    const st = (taskState[t.id] || {}).status;
    return st === "completed" || st === "skipped";
  }).length;
  const pct = Math.round(done / total * 100);
  document.getElementById("overall-bar").style.width = pct + "%";
  document.getElementById("pct-label").textContent = pct + "%";
}

// ─── Log rendering ────────────────────────────────────────────────────────────
const LOG_PANEL = () => document.getElementById("log-panel");
const LEVEL_CLASS = { info:"l-info", ok:"l-ok", err:"l-err", warn:"l-warn", cmd:"l-cmd", out:"l-out", step:"l-step", skip:"l-skip" };

function appendLog(msg) {
  logLines.push(msg);
  if (msg.type !== "log") return;
  const el = renderLogLine(msg);
  if (el) {
    LOG_PANEL().appendChild(el);
    if (document.getElementById("autoscroll").checked) {
      el.scrollIntoView({ block: "nearest" });
    }
    applyVisibility(el, msg);
  }
}

function renderLogLine(msg) {
  const div = document.createElement("div");
  div.className = "log-line";
  const ts = new Date(msg.ts * 1000).toTimeString().slice(0, 8);
  const lvl = msg.level || "out";
  div.innerHTML = `<span class="l-ts">${ts}</span><span class="${LEVEL_CLASS[lvl] || 'l-out'}">${escHtml(msg.text)}</span>`;
  div.dataset.task = msg.task || "";
  div.dataset.text = (msg.text || "").toLowerCase();
  return div;
}

function applyVisibility(el, msg) {
  const taskOk   = !filterTask   || (msg.task || "") === filterTask;
  const searchOk = !filterSearch || (msg.text || "").toLowerCase().includes(filterSearch);
  if (!taskOk || !searchOk) el.classList.add("hidden");
  else el.classList.remove("hidden");
}

function applyFilter() {
  filterTask   = document.getElementById("filter-task").value;
  filterSearch = document.getElementById("filter-search").value.toLowerCase();
  LOG_PANEL().querySelectorAll(".log-line").forEach(el => {
    const taskOk   = !filterTask   || el.dataset.task === filterTask;
    const searchOk = !filterSearch || el.dataset.text.includes(filterSearch);
    el.classList.toggle("hidden", !taskOk || !searchOk);
  });
}

function setActiveFilter(taskId) {
  activeFilter = activeFilter === taskId ? "" : taskId;
  document.getElementById("filter-task").value = activeFilter;
  applyFilter();
  document.querySelectorAll(".task-row").forEach(r => r.classList.remove("active"));
  if (activeFilter) {
    const row = document.getElementById("trow-" + activeFilter);
    if (row) row.classList.add("active");
  }
}

function clearLog() {
  logLines.length = 0;
  LOG_PANEL().innerHTML = "";
}

function escHtml(s) {
  return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ─── Stats update ─────────────────────────────────────────────────────────────
function updateStats(stats) {
  const keys = ["paras","scene_prompts","director_scripts","scene_audio","scene_transcripts","image_prompts","timings","images"];
  keys.forEach(k => {
    const el = document.getElementById("s-" + k);
    if (el && stats[k] !== undefined) el.textContent = stats[k];
  });
}

// ─── Elapsed timer ────────────────────────────────────────────────────────────
function startElapsedTimer(startTs) {
  elapsedStart = startTs || Date.now() / 1000;
  if (elapsedTimer) clearInterval(elapsedTimer);
  elapsedTimer = setInterval(() => {
    const sec = Math.round(Date.now() / 1000 - elapsedStart);
    document.getElementById("elapsed-display").textContent = fmtSec(sec);
  }, 1000);
}
function stopElapsedTimer(totalSec) {
  if (elapsedTimer) clearInterval(elapsedTimer);
  if (totalSec !== undefined) document.getElementById("elapsed-display").textContent = fmtSec(totalSec);
}
function fmtSec(s) {
  s = Math.round(s);
  const m = Math.floor(s / 60), r = s % 60;
  return String(m).padStart(2,"0") + ":" + String(r).padStart(2,"0");
}

// ─── Status badge ─────────────────────────────────────────────────────────────
function setStatusBadge(status) {
  const badge = document.getElementById("status-badge");
  badge.className = "badge badge-" + status;
  badge.textContent = status.toUpperCase();
}

function setButtons(status) {
  const running = status === "running";
  document.getElementById("btn-start").disabled      = running;
  document.getElementById("btn-stop").disabled       = !running;
  document.getElementById("btn-resume").disabled     = status !== "paused" && status !== "failed";
  document.getElementById("btn-reset").disabled      = running;
  document.getElementById("btn-gen-prompts").disabled = running;
  document.getElementById("btn-gen-images").disabled  = running;
}

// ─── SSE connection ───────────────────────────────────────────────────────────
function connect() {
  const es = new EventSource("/stream");
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "ping") return;

    if (msg.type === "log") {
      appendLog(msg);
    } else if (msg.type === "task") {
      if (msg.status === "running") hideWaitBanner();
      updateTaskUI(msg.task_id, msg);
    } else if (msg.type === "stats") {
      updateStats(msg);
    } else if (msg.type === "waiting") {
      if (isManualMode) showWaitBanner(msg.step_name);
    } else if (msg.type === "gen_prompts_done") {
      const btn = document.getElementById("btn-gen-prompts");
      btn.disabled = false;
      btn.classList.remove("busy");
      btn.textContent = "⬡ Gen Image Prompts";
    } else if (msg.type === "gen_images_done") {
      const btn = document.getElementById("btn-gen-images");
      btn.disabled = false;
      btn.classList.remove("busy");
      btn.textContent = "⬡ Gen Images";
    } else if (msg.type === "done") {
      setStatusBadge("completed");
      setButtons("completed");
      stopElapsedTimer();
    } else if (msg.type === "paused") {
      setStatusBadge("paused");
      setButtons("paused");
      stopElapsedTimer();
    } else if (msg.type === "failed") {
      setStatusBadge("failed");
      setButtons("failed");
      stopElapsedTimer();
    }
  };
  es.onerror = () => { setTimeout(connect, 3000); };
}

// ─── Controls ────────────────────────────────────────────────────────────────
function parseParagraphs() {
  const raw = document.getElementById("para-nums").value.trim();
  if (!raw) return null;
  return raw.split(/[,\s]+/).map(Number).filter(n => !isNaN(n) && n > 0);
}

function parseSceneFilter() {
  const raw = document.getElementById("scene-filter").value.trim();
  if (!raw) return null;
  return raw.split(/[,\s]+/).map(Number).filter(n => !isNaN(n) && n > 0);
}

function startPipeline() {
  const runpodUrl  = document.getElementById("runpod-url").value.trim();
  const openrouterKey = document.getElementById("openrouter-key").value.trim();
  const paraNumbers = parseParagraphs();
  const layoutExclude = document.getElementById("layout-exclude").value.trim();
  const sceneFilter = parseSceneFilter();
  const body = { runpod_url: runpodUrl, para_numbers: paraNumbers, layout_exclude: layoutExclude };
  if (sceneFilter) body.scene_filter = sceneFilter;
  if (openrouterKey) body.openrouter_api_key = openrouterKey;
  setStatusBadge("running");
  setButtons("running");
  clearLog();
  Object.keys(taskState).forEach(k => delete taskState[k]);
  fetch("/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  }).then(r => r.json()).then(d => {
    if (d.error) { alert(d.error); setStatusBadge("idle"); setButtons("idle"); return; }
    if (openrouterKey) document.getElementById("openrouter-key").value = "";
    buildStepPanel(d.para_numbers, []);
    startElapsedTimer();
  });
}

function stopPipeline() {
  fetch("/stop", { method: "POST" }).then(() => {
    setStatusBadge("paused");
    setButtons("paused");
    stopElapsedTimer();
  });
}

function resumePipeline() {
  const runpodUrl = document.getElementById("runpod-url").value.trim();
  const openrouterKey = document.getElementById("openrouter-key").value.trim();
  const layoutExclude = document.getElementById("layout-exclude").value.trim();
  const body = { runpod_url: runpodUrl, layout_exclude: layoutExclude };
  if (openrouterKey) body.openrouter_api_key = openrouterKey;
  setStatusBadge("running");
  setButtons("running");
  fetch("/resume", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  }).then(r => r.json()).then(d => {
    if (d.error) { alert(d.error); return; }
    if (openrouterKey) document.getElementById("openrouter-key").value = "";
    startElapsedTimer();
  });
}

function downloadTiming() {
  window.location = "/timing_data";
}

function resetPipeline() {
  const status = document.getElementById("status-badge").textContent.toLowerCase();
  if (status === "running") return;
  const ok = confirm("Reset pipeline? This deletes generated paras, scene prompts, images, timings, and outputs.");
  if (!ok) return;
  fetch("/reset", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ confirm: true })
  }).then(r => r.json()).then(d => {
    if (d.error) { alert(d.error); return; }
    setStatusBadge("idle");
    setButtons("idle");
    clearLog();
    buildStepPanel([], []);
    fetch("/status").then(r => r.json()).then(s => updateStats(s));
  });
}

// ─── Manual mode ──────────────────────────────────────────────────────────────
let isManualMode = false;

function toggleMode() {
  isManualMode = !isManualMode;
  const btn = document.getElementById("btn-mode");
  if (isManualMode) {
    btn.textContent = "🖐 Manual Mode";
    btn.classList.add("manual");
  } else {
    btn.textContent = "⚡ Auto Mode";
    btn.classList.remove("manual");
  }
  fetch("/set_mode", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ manual: isManualMode })
  });
}

function runNextStep() {
  document.getElementById("wait-banner").classList.remove("show");
  fetch("/continue_step", { method: "POST" });
}

function showWaitBanner(stepName) {
  const banner = document.getElementById("wait-banner");
  document.getElementById("wait-step-name").textContent = "Next: " + stepName;
  banner.classList.add("show");
}

function hideWaitBanner() {
  document.getElementById("wait-banner").classList.remove("show");
}

// ─── Standalone image actions ────────────────────────────────────────────────
function genImagePrompts() {
  const openrouterKey = document.getElementById("openrouter-key").value.trim();
  const btn = document.getElementById("btn-gen-prompts");
  btn.disabled = true;
  btn.classList.add("busy");
  btn.textContent = "Generating...";
  const body = {};
  if (openrouterKey) body.openrouter_api_key = openrouterKey;
  fetch("/gen_image_prompts", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  })
    .then(r => r.json())
    .then(d => {
      if (d.error) { alert(d.error); btn.disabled = false; btn.classList.remove("busy"); btn.textContent = "Gen Image Prompts"; }
      if (!d.error && openrouterKey) document.getElementById("openrouter-key").value = "";
    });
}

function genImages() {
  const runpodUrl = document.getElementById("runpod-url").value.trim();
  const openrouterKey = document.getElementById("openrouter-key").value.trim();
  const btn = document.getElementById("btn-gen-images");
  btn.disabled = true;
  btn.classList.add("busy");
  btn.textContent = "Generating...";
  const body = { runpod_url: runpodUrl };
  if (openrouterKey) body.openrouter_api_key = openrouterKey;
  fetch("/gen_images", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  }).then(r => r.json()).then(d => {
    if (d.error) { alert(d.error); btn.disabled = false; btn.classList.remove("busy"); btn.textContent = "Gen Images"; }
    if (!d.error && openrouterKey) document.getElementById("openrouter-key").value = "";
  });
}

// --- Init ─────────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  buildStepPanel([], []);

  // Load existing status
  fetch("/status").then(r => r.json()).then(s => {
    setStatusBadge(s.status || "idle");
    setButtons(s.status || "idle");
    updateStats(s.stats || {});

    if (s.runpod_url) document.getElementById("runpod-url").value = s.runpod_url;
    if (s.openrouter_key_set)
      document.getElementById("openrouter-key").placeholder = "key loaded (enter a new one to override)";
    if (s.para_numbers && s.para_numbers.length)
      document.getElementById("para-nums").value = s.para_numbers.join(",");

    if (s.para_numbers || s.scene_numbers)
      buildStepPanel(s.para_numbers || [], s.scene_numbers || []);

    if (s.steps) {
      Object.entries(s.steps).forEach(([tid, data]) => updateTaskUI(tid, data));
    }

    if (s.status === "running" && s.start_time) startElapsedTimer(s.start_time);
    if (s.elapsed && (s.status === "completed" || s.status === "paused"))
      document.getElementById("elapsed-display").textContent = fmtSec(s.elapsed);
  });

  connect();
});
</script>
</body>
</html>"""


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _load_state()
    _load_timing()
    # If server restarted while "running", treat it as paused
    if _state.get("status") == "running":
        _state["status"] = "paused"
    print(f"\n  Pipeline Runner → http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
