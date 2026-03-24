"""
Scene Render UI
===============
Run: python render_video.py
Open: http://localhost:5566

Purpose:
- Load a scene from assets/directorscript + assets/timings + assets/scenes_audio
- Preview layout on canvas
- Render scene_<n>.mp4 with CPU/GPU + HD/4K options
"""

import json
import os
import re
import subprocess
import threading
import time
import traceback
import random
import socket
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from flask import Flask, Response, jsonify, make_response, render_template_string, request, send_from_directory
from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, VideoFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx
from pydub import AudioSegment
from proglog import ProgressBarLogger

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DIRECTOR_DIR = os.path.join(ASSETS_DIR, "directorscript")
TIMINGS_DIR = os.path.join(ASSETS_DIR, "timings")
SCENES_AUDIO_DIR = os.path.join(ASSETS_DIR, "scenes_audio")
OUTPUTS_DIR = os.path.join(ASSETS_DIR, "outputs")
SFX_DIR = os.path.join(BASE_DIR, "sound_effects")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
SETTINGS_PATH = os.path.join(BASE_DIR, "render_video_settings.json")
os.makedirs(TMP_DIR, exist_ok=True)

SFX_FILE_MAP = {
    "click": os.path.join(SFX_DIR, "click.mp3"),
    "pop": os.path.join(SFX_DIR, "pop.mp3"),
    "whoosh": os.path.join(SFX_DIR, "whoosh.mp3"),
    "typing": os.path.join(SFX_DIR, "typing.mp3"),
}

FONT_DEFAULT_KEY = "comic_sans"
FONT_OPTIONS = [
    {
        "key": "comic_sans",
        "label": "Comic Sans (Default)",
        "css": "Comic Sans MS, Comic Sans, cursive",
        "files": ["comic.ttf", "Comic Sans MS.ttf", "Comic Sans.ttf"],
        "bold_files": ["comicbd.ttf", "Comic Sans MS Bold.ttf"],
    },
    {
        "key": "arial",
        "label": "Arial",
        "css": "Arial, Helvetica, sans-serif",
        "files": ["arial.ttf", "Arial.ttf"],
        "bold_files": ["arialbd.ttf", "Arial Bold.ttf"],
    },
    {
        "key": "verdana",
        "label": "Verdana",
        "css": "Verdana, Geneva, sans-serif",
        "files": ["verdana.ttf", "Verdana.ttf"],
        "bold_files": ["verdanab.ttf", "Verdana Bold.ttf"],
    },
    {
        "key": "trebuchet",
        "label": "Trebuchet MS",
        "css": "Trebuchet MS, Arial, sans-serif",
        "files": ["trebuc.ttf", "Trebuchet MS.ttf"],
        "bold_files": ["trebucbd.ttf", "Trebuchet MS Bold.ttf"],
    },
    {
        "key": "times_new_roman",
        "label": "Times New Roman",
        "css": "Times New Roman, Times, serif",
        "files": ["times.ttf", "Times New Roman.ttf"],
        "bold_files": ["timesbd.ttf", "Times New Roman Bold.ttf"],
    },
    {
        "key": "georgia",
        "label": "Georgia",
        "css": "Georgia, serif",
        "files": ["georgia.ttf", "Georgia.ttf"],
        "bold_files": ["georgiab.ttf", "Georgia Bold.ttf"],
    },
    {
        "key": "courier_new",
        "label": "Courier New",
        "css": "Courier New, Courier, monospace",
        "files": ["cour.ttf", "Courier New.ttf"],
        "bold_files": ["courbd.ttf", "Courier New Bold.ttf"],
    },
    {
        "key": "impact",
        "label": "Impact",
        "css": "Impact, Haettenschweiler, Arial Narrow Bold, sans-serif",
        "files": ["impact.ttf", "Impact.ttf"],
        "bold_files": ["impact.ttf", "Impact.ttf"],
    },
]
FONT_BY_KEY = {f["key"]: f for f in FONT_OPTIONS}
SCALABLE_FALLBACK_FONT_FILES = [
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "Arial.ttf",
    "arial.ttf",
    "FreeSans.ttf",
    "NotoSans-Regular.ttf",
]
PROGRESS_LOCK = threading.Lock()
PROGRESS_STATE: Dict[str, Dict[str, object]] = {}


def init_progress(job_id: str, kind: str, label: str) -> None:
    if not job_id:
        return
    with PROGRESS_LOCK:
        PROGRESS_STATE[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "label": label,
            "status": "running",
            "phase": "starting",
            "message": f"{label} starting...",
            "percent": 0.0,
            "updated_at": time.time(),
        }


def update_progress(job_id: str, *, phase: Optional[str] = None, message: Optional[str] = None, percent: Optional[float] = None) -> None:
    if not job_id:
        return
    with PROGRESS_LOCK:
        state = PROGRESS_STATE.setdefault(job_id, {
            "job_id": job_id,
            "kind": "job",
            "label": job_id,
            "status": "running",
            "phase": "starting",
            "message": "",
            "percent": 0.0,
            "updated_at": time.time(),
        })
        if phase is not None:
            state["phase"] = phase
        if message is not None:
            state["message"] = message
        if percent is not None:
            state["percent"] = max(0.0, min(100.0, float(percent)))
        state["updated_at"] = time.time()


def finish_progress(job_id: str, *, status: str, message: str) -> None:
    if not job_id:
        return
    with PROGRESS_LOCK:
        state = PROGRESS_STATE.setdefault(job_id, {
            "job_id": job_id,
            "kind": "job",
            "label": job_id,
        })
        state["status"] = status
        state["message"] = message
        state["phase"] = "done" if status == "completed" else "error"
        state["percent"] = 100.0 if status == "completed" else state.get("percent", 0.0)
        state["updated_at"] = time.time()


def get_progress(job_id: str) -> Dict[str, object]:
    with PROGRESS_LOCK:
        state = PROGRESS_STATE.get(job_id)
        if not state:
            return {"job_id": job_id, "status": "missing", "message": "No progress found."}
        return dict(state)


@app.route("/progress")
def progress_route():
    job_id = (request.args.get("job_id", "") or "").strip()
    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400
    return jsonify(get_progress(job_id))


class MoviePyJobLogger(ProgressBarLogger):
    def __init__(self, job_id: str, phase_label: str):
        super().__init__()
        self.job_id = job_id
        self.phase_label = phase_label

    def bars_callback(self, bar, attr, value, old_value=None):
        super().bars_callback(bar, attr, value, old_value)
        self._publish()

    def callback(self, **changes):
        super().callback(**changes)
        self._publish()

    def _publish(self):
        best_percent = None
        best_message = self.phase_label
        for bar_name, bar_data in self.bars.items():
            total = bar_data.get("total") or 0
            index = bar_data.get("index") or 0
            if total:
                percent = (float(index) / float(total)) * 100.0
                if best_percent is None or percent > best_percent:
                    best_percent = percent
                    best_message = f"{self.phase_label}: {bar_name} {int(index)}/{int(total)}"
        if best_percent is not None:
            update_progress(self.job_id, phase=self.phase_label, message=best_message, percent=best_percent)


def _read_positive_int_env(name: str) -> Optional[int]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
        return value if value > 0 else None
    except Exception:
        return None


def compute_parallel_render_limit() -> int:
    override = _read_positive_int_env("RENDER_MAX_PARALLEL")
    if override is not None:
        return override
    cores = os.cpu_count() or 1
    # Default to a device-aware cap instead of a fixed 4.
    return max(1, min(12, cores))


def should_return_json_error(path: str) -> bool:
    if path == "/":
        return False
    if path.startswith("/image/"):
        return False
    if path.startswith("/preview_sfx_audio"):
        return False
    return True


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    traceback.print_exc()
    if should_return_json_error(request.path):
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500
    return Response("Internal Server Error", status=500, mimetype="text/plain")


def detect_system_info() -> Dict[str, str]:
    cpu = os.environ.get("PROCESSOR_IDENTIFIER", "") or "Unknown CPU"
    gpu = "Unknown GPU"
    cores = os.cpu_count() or 1

    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3,
        )
        first = out.strip().splitlines()[0].strip()
        if first:
            gpu = first
            return {"cpu": cpu, "gpu": gpu, "cores": cores}
    except Exception:
        pass

    # Fallback for Windows if available.
    try:
        out = subprocess.check_output(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3,
        )
        lines = [l.strip() for l in out.splitlines() if l.strip() and "name" not in l.lower()]
        if lines:
            gpu = lines[0]
    except Exception:
        pass

    return {"cpu": cpu, "gpu": gpu, "cores": cores}


def normalize_text_case(text: str) -> str:
    """Convert ALL-CAPS text to title case at render/display time."""
    if not text:
        return text
    if not text.isupper():
        return text
    # Capitalize first letter of each word, lowercase the rest
    def _cap(w):
        return w[0].upper() + w[1:].lower() if w else w
    return '\n'.join(' '.join(_cap(w) for w in line.split()) for line in text.split('\n'))


def load_settings() -> Dict[str, object]:
    default = {"sfx_db": -14.0, "font_key": FONT_DEFAULT_KEY, "font_bold": False}
    if not os.path.exists(SETTINGS_PATH):
        return default
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        font_key = str(data.get("font_key", FONT_DEFAULT_KEY))
        if font_key not in FONT_BY_KEY:
            font_key = FONT_DEFAULT_KEY
        return {
            "sfx_db": float(data.get("sfx_db", default["sfx_db"])),
            "font_key": font_key,
            "font_bold": bool(data.get("font_bold", False)),
        }
    except Exception:
        return default


def save_settings(settings: Dict[str, object]) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_font_choice(font_key: str) -> Dict[str, object]:
    return FONT_BY_KEY.get((font_key or "").strip(), FONT_BY_KEY[FONT_DEFAULT_KEY])


@lru_cache(maxsize=None)
def _font_search_roots() -> Tuple[str, ...]:
    roots = [
        "C:\\Windows\\Fonts",
        "/Library/Fonts",
        "/System/Library/Fonts",
        "/usr/share/fonts",
        "/usr/local/share/fonts",
    ]
    return tuple(root for root in roots if os.path.isdir(root))


@lru_cache(maxsize=None)
def _find_font_file(filename: str) -> str:
    filename = (filename or "").strip()
    if not filename:
        return ""
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    if os.path.exists(filename):
        return filename

    for root in _font_search_roots():
        direct = os.path.join(root, filename)
        if os.path.exists(direct):
            return direct

    target = filename.lower()
    for root in _font_search_roots():
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                if name.lower() == target:
                    return os.path.join(dirpath, name)
    return ""


def resolve_font_path(font_key: str, bold: bool = False) -> str:
    choice = get_font_choice(font_key)
    if bold:
        filenames = [str(x) for x in choice.get("bold_files", [])] + [str(x) for x in choice.get("files", [])]
    else:
        filenames = [str(x) for x in choice.get("files", [])]
    for fn in filenames:
        found = _find_font_file(fn)
        if found:
            return found
    for fn in SCALABLE_FALLBACK_FONT_FILES:
        found = _find_font_file(fn)
        if found:
            return found
    return ""


def create_image_clip_safe(filepath: str, add_shadow: bool = False, angle: float = 0):
    img = Image.open(filepath).convert("RGBA")
    if add_shadow:
        blur_radius, offset = 20, (10, 10)
        padding = blur_radius * 2 + max(abs(offset[0]), abs(offset[1]))
        new_w, new_h = img.width + 2 * padding, img.height + 2 * padding
        canvas = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        alpha = img.split()[3]
        shadow_color = Image.new("RGBA", img.size, (0, 0, 0, 130))
        canvas.paste(shadow_color, (padding + offset[0], padding + offset[1]), mask=alpha)
        canvas = canvas.filter(ImageFilter.GaussianBlur(blur_radius))
        canvas.paste(img, (padding, padding), mask=img)
        img = canvas
    if angle != 0:
        resample_mode = getattr(Image, "Resampling", Image).BICUBIC
        img = img.rotate(-angle, expand=True, resample=resample_mode)
    img_np = np.array(img).astype(np.float32)
    alpha_np = img_np[:, :, 3] / 255.0
    alpha_3 = np.repeat(alpha_np[:, :, None], 3, axis=2)
    # Prevent dark fringe during scale animations by compositing edge RGB over white.
    rgb_np = (img_np[:, :, :3] * alpha_3 + 255.0 * (1.0 - alpha_3)).astype(np.uint8)
    clip = ImageClip(rgb_np)
    mask = ImageClip(alpha_np, ismask=True)
    return clip.set_mask(mask)


def create_text_clip_with_pillow(
    text: str,
    fontsize: int = 70,
    color=(255, 255, 255),
    stroke_color=(0, 0, 0),
    stroke_width: int = 3,
    bg_color=None,
    angle: float = 0,
    font_key: str = FONT_DEFAULT_KEY,
    font_bold: bool = False,
):
    font_path = resolve_font_path(font_key, bold=font_bold)
    try:
        font = ImageFont.truetype(font_path, fontsize) if font_path else ImageFont.truetype("DejaVuSans.ttf", fontsize)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", fontsize)
        except Exception:
            font = ImageFont.load_default()

    dummy_img = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    h_padding, v_padding = int(fontsize * 0.1), int(fontsize * 0.1)
    img_width = int(text_w + (h_padding * 2) + (stroke_width * 2))
    img_height = int(text_h + (v_padding * 2) + (stroke_width * 2))
    img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if bg_color:
        draw.rectangle([0, 0, img_width, img_height], fill=bg_color)
    draw.text(
        (h_padding + stroke_width - bbox[0], v_padding + stroke_width - bbox[1]),
        text,
        font=font,
        fill=color,
        stroke_width=stroke_width if not bg_color else 0,
        stroke_fill=stroke_color,
    )
    if angle != 0:
        resample_mode = getattr(Image, "Resampling", Image).BICUBIC
        img = img.rotate(-angle, expand=True, resample=resample_mode)
    img_np = np.array(img)
    rgb_np = img_np[:, :, :3]
    alpha_np = img_np[:, :, 3] / 255.0
    clip = ImageClip(rgb_np)
    mask = ImageClip(alpha_np, ismask=True)
    return clip.set_mask(mask)


def build_image_dict(scene_id: str) -> Dict[str, str]:
    img_dict = {}
    if os.path.exists(OUTPUTS_DIR):
        for f in os.listdir(OUTPUTS_DIR):
            fp = os.path.join(OUTPUTS_DIR, f)
            if os.path.isfile(fp) and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                img_dict[os.path.splitext(f)[0].lower()] = fp

    scene_dir = os.path.join(OUTPUTS_DIR, scene_id)
    if os.path.exists(scene_dir):
        for f in os.listdir(scene_dir):
            fp = os.path.join(scene_dir, f)
            if os.path.isfile(fp) and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                img_dict[os.path.splitext(f)[0].lower()] = fp
    return img_dict


def is_default_asset_filename(filename: str) -> bool:
    base = os.path.splitext((filename or "").strip().lower())[0]
    return base == "arrow" or base.startswith("host")


def resolve_image_path(scene_id: str, filename: str, img_dict: Dict[str, str]) -> str:
    filename = (filename or "").strip()
    if not filename:
        return ""
    base_name = os.path.splitext(filename)[0].lower()

    # Force defaults from global outputs directory.
    if is_default_asset_filename(filename):
        global_path = os.path.join(OUTPUTS_DIR, filename)
        if os.path.isfile(global_path):
            return global_path

    return img_dict.get(base_name, "")


def load_scene_files(scene_num: str):
    scene_id = f"scene_{scene_num}"
    director_path = os.path.join(DIRECTOR_DIR, f"{scene_id}_director.json")
    timings_path = os.path.join(TIMINGS_DIR, f"{scene_id}_timings.json")
    audio_path = os.path.join(SCENES_AUDIO_DIR, f"{scene_id}.mp3")

    if not os.path.exists(director_path):
        raise FileNotFoundError(f"Missing director file: assets/directorscript/{scene_id}_director.json")
    if not os.path.exists(timings_path):
        raise FileNotFoundError(f"Missing timings file: assets/timings/{scene_id}_timings.json")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Missing audio file: assets/scenes_audio/{scene_id}.mp3")

    with open(director_path, "r", encoding="utf-8") as f:
        director = json.load(f)
    with open(timings_path, "r", encoding="utf-8") as f:
        timings = json.load(f)
    return scene_id, director, timings, audio_path


def list_available_scene_numbers() -> List[int]:
    scenes = []
    if os.path.exists(DIRECTOR_DIR):
        for f in os.listdir(DIRECTOR_DIR):
            match = re.match(r"scene_(\d+)_director\.json", f)
            if match:
                scenes.append(int(match.group(1)))
    scenes.sort()
    return scenes


def list_rendered_scene_video_pairs() -> List[Tuple[int, str]]:
    pairs = []
    for f in os.listdir(BASE_DIR):
        match = re.match(r"scene_(\d+)\.mp4$", f)
        if match:
            pairs.append((int(match.group(1)), os.path.join(BASE_DIR, f)))
    pairs.sort(key=lambda item: item[0])
    return pairs


def can_open_video(video_path: str) -> Tuple[bool, str]:
    clip = None
    try:
        clip = VideoFileClip(video_path)
        clip.get_frame(0)
        return True, ""
    except Exception as exc:
        return False, str(exc)
    finally:
        if clip is not None:
            try:
                clip.close()
            except Exception:
                pass


def inspect_rendered_scene_videos(scene_numbers: Optional[List[int]] = None) -> Dict[str, object]:
    rendered_pairs = list_rendered_scene_video_pairs()
    rendered_map = {n: p for n, p in rendered_pairs}

    if scene_numbers:
        requested_scene_numbers = sorted(set(int(n) for n in scene_numbers))
    else:
        requested_scene_numbers = [n for n, _ in rendered_pairs]

    valid_scene_nums: List[int] = []
    valid_scene_paths: List[str] = []
    invalid_files: List[Dict[str, object]] = []
    missing_scene_numbers: List[int] = []

    for scene_num in requested_scene_numbers:
        video_path = rendered_map.get(scene_num) or os.path.join(BASE_DIR, f"scene_{scene_num}.mp4")
        if not os.path.isfile(video_path):
            missing_scene_numbers.append(scene_num)
            continue
        ok, err = can_open_video(video_path)
        if ok:
            valid_scene_nums.append(scene_num)
            valid_scene_paths.append(video_path)
        else:
            invalid_files.append({"scene": scene_num, "path": video_path, "error": err})

    return {
        "requested_scene_numbers": requested_scene_numbers,
        "valid_scene_numbers": valid_scene_nums,
        "valid_scene_paths": valid_scene_paths,
        "invalid_files": invalid_files,
        "missing_scene_numbers": missing_scene_numbers,
    }


def stitch_scene_videos(hardware: str = "cpu", scene_numbers: Optional[List[int]] = None, job_id: str = "", output_filename: str = "full_video.mp4") -> Dict[str, object]:
    update_progress(job_id, phase="scan", message="Scanning rendered scenes...", percent=2)
    inspection = inspect_rendered_scene_videos(scene_numbers=scene_numbers)
    requested_scene_numbers = inspection["requested_scene_numbers"]
    if not requested_scene_numbers:
        raise FileNotFoundError("No rendered scene videos found (expected scene_<n>.mp4 files).")

    scene_nums = requested_scene_numbers
    scene_paths = [os.path.join(BASE_DIR, f"scene_{n}.mp4") for n in scene_nums if os.path.isfile(os.path.join(BASE_DIR, f"scene_{n}.mp4"))]
    valid_scene_nums = []
    valid_scene_paths = []
    invalid_files = list(inspection["invalid_files"])
    missing_scene_numbers = list(inspection["missing_scene_numbers"])
    total_candidates = max(1, len(requested_scene_numbers))
    for idx, n in enumerate(requested_scene_numbers, start=1):
        update_progress(
            job_id,
            phase="validate",
            message=f"Validating scene_{n}.mp4 ({idx}/{total_candidates})",
            percent=2 + (idx / total_candidates) * 18,
        )
        matching_path = next((p for sn, p in zip(inspection["valid_scene_numbers"], inspection["valid_scene_paths"]) if sn == n), "")
        if matching_path:
            valid_scene_nums.append(n)
            valid_scene_paths.append(matching_path)

    if not valid_scene_paths:
        raise FileNotFoundError("No valid rendered scene videos found to stitch.")

    scene_nums = valid_scene_nums
    scene_paths = valid_scene_paths

    scene_set = set(scene_nums)
    gaps = []
    if scene_nums:
        for n in range(scene_nums[0], scene_nums[-1] + 1):
            if n not in scene_set:
                gaps.append(n)

    clips = []
    normalized_clips = []
    final_clip = None
    try:
        total_scenes = max(1, len(scene_paths))
        opened_scene_nums = []
        for idx, (scene_num, p) in enumerate(zip(scene_nums, scene_paths), start=1):
            scene_name = os.path.basename(p)
            update_progress(
                job_id,
                phase="load",
                message=f"Loading {scene_name} ({idx}/{total_scenes})",
                percent=20 + (idx / total_scenes) * 15,
            )
            try:
                clip = VideoFileClip(p)
                clip.get_frame(0)
                clips.append(clip)
                opened_scene_nums.append(scene_num)
            except Exception as exc:
                invalid_files.append({"scene": scene_num, "path": p, "error": str(exc)})
        if not clips:
            raise FileNotFoundError("No valid scene videos could be opened for stitching.")
        scene_nums = opened_scene_nums
        target_w, target_h = clips[0].size
        total_opened = max(1, len(clips))
        for idx, c in enumerate(clips, start=1):
            update_progress(
                job_id,
                phase="normalize",
                message=f"Normalizing scene {idx}/{total_opened}",
                percent=35 + (idx / total_opened) * 15,
            )
            if c.w == target_w and c.h == target_h:
                normalized_clips.append(c)
                continue
            # Keep aspect ratio and pad to a single output canvas size so scene scale stays consistent.
            scale = min(target_w / c.w, target_h / c.h)
            fitted = c.resize(scale).on_color(
                size=(target_w, target_h),
                color=(0, 0, 0),
                pos=("center", "center"),
            )
            normalized_clips.append(fitted)

        final_clip = concatenate_videoclips(normalized_clips, method="chain")
        update_progress(job_id, phase="encode", message="Encoding stitched full video...", percent=55)

        output_path = os.path.join(BASE_DIR, output_filename)
        codec_map = {
            "cpu": ("libx264", "ultrafast"),
            "nvidia": ("h264_nvenc", "fast"),
            "amd": ("h264_amf", None),
            "apple": ("h264_videotoolbox", None),
        }
        codec, preset = codec_map.get(hardware, ("libx264", "ultrafast"))
        render_args = {
            "fps": 30,
            "audio_codec": "aac",
            "threads": os.cpu_count() or 4,
            "ffmpeg_params": ["-pix_fmt", "yuv420p"],
        }
        if preset:
            render_args["preset"] = preset
        render_args["logger"] = MoviePyJobLogger(job_id, "encode") if job_id else None

        try:
            final_clip.write_videofile(output_path, codec=codec, **render_args)
        except Exception:
            final_clip.write_videofile(output_path, codec="libx264", **render_args)

        return {
            "output_path": output_path,
            "scene_count": len(scene_nums),
            "scene_numbers": scene_nums,
            "duration": float(final_clip.duration or 0.0),
            "gaps": gaps,
            "invalid_files": invalid_files,
            "missing_scene_numbers": missing_scene_numbers,
            "resolution": [int(target_w), int(target_h)],
        }
    finally:
        if final_clip is not None:
            try:
                final_clip.close()
            except Exception:
                pass
        for c in normalized_clips:
            if c in clips:
                continue
            try:
                c.close()
            except Exception:
                pass
        for c in clips:
            try:
                c.close()
            except Exception:
                pass


def auto_modify_director_for_render(scene_num: str):
    scene_id = f"scene_{scene_num}"
    director_path = os.path.join(DIRECTOR_DIR, f"{scene_id}_director.json")
    if not os.path.exists(director_path):
        raise FileNotFoundError(f"Missing director file: assets/directorscript/{scene_id}_director.json")

    with open(director_path, "r", encoding="utf-8") as f:
        director = json.load(f)

    text_animations = ["typing", "fade_up", "pop"]
    image_animations = ["pop", "slide_in_left", "slide_in_right", "slide_in_up", "fade_up"]

    for el in director.get("elements", []):
        el_type = (el.get("type") or "").strip()
        desc = (el.get("description") or "").lower()

        if el_type.startswith("text_"):
            chosen = random.choice(text_animations)
            el["animation"] = chosen
            # Typing effect speed (seconds) for text-only typing animation.
            if chosen == "typing":
                el["typing_speed"] = round(random.uniform(0.35, 0.9), 2)
            else:
                el.pop("typing_speed", None)
            # Text never gets shadow from this auto rule.
            el["property"] = ""
        elif el_type == "image":
            el["animation"] = random.choice(image_animations)
            # Shadow only for realistic image descriptions.
            el["property"] = "shadow" if "realistic" in desc else ""
        else:
            # Arrow and unknown non-text elements: random non-typing animation, no shadow.
            el["animation"] = random.choice(image_animations)
            el["property"] = ""

    with open(director_path, "w", encoding="utf-8") as f:
        json.dump(director, f, indent=2)

    return scene_id, director


def _animation_to_sfx_key(anim_type: str):
    a = (anim_type or "").lower()
    if "jump_cut" in a:
        return "click"
    if "pop" in a:
        return "pop"
    if "draw" in a:
        return "whoosh"
    if "slide" in a or "fade" in a:
        return "whoosh"
    if "typing" in a:
        return "typing"
    return None


def mix_scene_audio_with_sfx(scene_id: str, director: dict, timings: list, base_audio_path: str, sfx_db: float) -> str:
    final_audio = AudioSegment.from_file(base_audio_path)
    animations_lookup = {el.get("element_id"): (el.get("animation") or "") for el in director.get("elements", [])}

    for item in timings:
        el_id = item.get("element_id")
        start_sec = float(item.get("start", 0))
        anim_type = animations_lookup.get(el_id, "")
        sfx_key = _animation_to_sfx_key(anim_type)
        if not sfx_key:
            continue
        sfx_path = SFX_FILE_MAP.get(sfx_key)
        if not sfx_path or not os.path.exists(sfx_path):
            continue
        try:
            sfx_audio = AudioSegment.from_file(sfx_path) + float(sfx_db)
            start_ms = int(start_sec * 1000)
            final_audio = final_audio.overlay(sfx_audio, position=start_ms)
        except Exception:
            continue

    mixed_path = os.path.join(TMP_DIR, f"{scene_id}_mixed_audio.mp3")
    final_audio.export(mixed_path, format="mp3")
    return mixed_path


def uses_centered_coordinates(elements: List[dict]) -> bool:
    if not elements:
        return False
    xs = [float(e.get("x")) for e in elements if isinstance(e.get("x"), (int, float))]
    ys = [float(e.get("y")) for e in elements if isinstance(e.get("y"), (int, float))]
    if not xs or not ys:
        return False
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    has_negative = min_x < 0 or min_y < 0
    centered_range = max_x <= 960 and min_x >= -960 and max_y <= 540 and min_y >= -540
    return has_negative and centered_range


MAX_PARALLEL_RENDERS = compute_parallel_render_limit()
RENDER_SEMAPHORE = threading.BoundedSemaphore(MAX_PARALLEL_RENDERS)

def render_scene(scene_num: str, quality: str, hardware: str, sfx_db: float, font_key: str, font_bold: bool = False, job_id: str = "") -> str:
    scene_id, director, timings, audio_path = load_scene_files(scene_num)
    update_progress(job_id, phase="prepare", message=f"Preparing {scene_id}...", percent=5)

    max_timing_end = max([float(t.get("end", 0)) for t in timings], default=0.0)
    base_audio = AudioSegment.from_file(audio_path)
    base_duration = len(base_audio) / 1000.0
    scene_content_duration = max(base_duration, max_timing_end)
    tail_pad = 0.5
    final_duration = scene_content_duration + tail_pad

    mixed_audio_path = mix_scene_audio_with_sfx(scene_id, director, timings, audio_path, sfx_db)
    mixed_audio = AudioSegment.from_file(mixed_audio_path)
    target_ms = int(np.ceil(final_duration * 1000))
    if len(mixed_audio) < target_ms:
        mixed_audio += AudioSegment.silent(duration=target_ms - len(mixed_audio))
    render_audio_path = os.path.join(TMP_DIR, f"{scene_id}_render_audio.wav")
    mixed_audio.export(render_audio_path, format="wav")
    audio = AudioFileClip(render_audio_path)
    update_progress(job_id, phase="compose", message=f"Building layers for {scene_id}...", percent=15)

    res_w, res_h, res_mult = (3840, 2160, 2.0) if quality == "4K" else (1920, 1080, 1.0)
    bg = ColorClip(size=(res_w, res_h), color=(255, 255, 255)).set_duration(final_duration)
    clips = [bg]

    timings_by_id = {t.get("element_id"): t for t in timings}
    img_dict = build_image_dict(scene_id)
    elements = director.get("elements", [])
    use_centered_coords = uses_centered_coordinates(elements)

    # Sort elements by their timeline start time so the ramp index reflects
    # the order elements actually appear on screen, not their JSON order.
    # Elements with no timing entry (start=0.0) sort to the front.
    elements_sorted = sorted(
        elements,
        key=lambda el: float((timings_by_id.get(el.get("element_id", ""), {})).get("start", 0))
    )
    total_elements = max(1, len(elements_sorted))

    # ── Sequential animation stagger ─────────────────────────────────────────
    # Each element's visual start = max(audio_start, previous_animation_finish).
    # This ensures no two animations overlap: the next element only begins after
    # the previous one has fully appeared. Speed ramp is preserved — the animation
    # plays at its ramped speed, it just can't start until the previous finishes.
    _seq_BASE  = {"pop": 0.3, "slide_in_left": 0.45, "slide_in_right": 0.45,
                  "slide_in_up": 0.45, "fade_up": 0.4, "typing": 0.5}
    _seq_SPEED = [1.0, 0.75, 0.55, 0.40]
    _seq_LAST  = 0.2
    _seq_prev_end = 0.0
    effective_starts = {}
    for _si, _sel in enumerate(elements_sorted, start=1):
        _seid  = _sel.get("element_id", "")
        _sti   = timings_by_id.get(_seid, {})
        _saudio = float(_sti.get("start", 0))
        _send   = float(_sti.get("end", scene_content_duration))
        _sanim  = _sel.get("animation", "none")
        _sbase  = float(_sel.get("typing_speed", 0.5)) if _sanim == "typing" else _seq_BASE.get(_sanim, 0.3)
        _sramp = _seq_SPEED[min(_si - 1, len(_seq_SPEED) - 1)]
        if _si == total_elements:
            _smult = min(_sramp, _seq_LAST / _sbase if _sbase > 0 else 1.0)
        else:
            _smult = _sramp
        _sanim_dur = _sbase * _smult
        _seff = max(_saudio, _seq_prev_end)
        _seff = min(_seff, max(_saudio, _send - 0.05))  # never push past clip end
        effective_starts[_seid] = max(0.0, _seff)
        _seq_prev_end = _seff + _sanim_dur

    for idx, item in enumerate(elements_sorted, start=1):
        update_progress(
            job_id,
            phase="compose",
            message=f"Compositing {scene_id}: element {idx}/{total_elements}",
            percent=15 + (idx / total_elements) * 30,
        )
        el_id = item.get("element_id", "")
        el_type = item.get("type", "image")
        t_info = timings_by_id.get(el_id, {})
        start_time = float(t_info.get("start", 0))
        end_time = float(t_info.get("end", scene_content_duration))
        if end_time <= start_time:
            end_time = min(scene_content_duration, start_time + 0.2)

        animation = item.get("animation", "none")
        rotation = float(item.get("angle", 0))
        scene_x = float(item.get("x", 960))
        scene_y = float(item.get("y", 540))
        if use_centered_coords:
            scene_x += 960
            scene_y += 540
        cx = scene_x * res_mult
        cy = scene_y * res_mult
        js = float(item.get("scale", 1.0))

        if el_type.startswith("text_"):
            content = normalize_text_case(str(item.get("text_content", "")).strip())
            if not content:
                continue
            t_fs = max(10, int(40 * js * res_mult))
            if el_type == "text_red":
                clip = create_text_clip_with_pillow(
                    content, fontsize=t_fs, color=(220, 20, 60),
                    stroke_color=(255, 255, 255), stroke_width=max(1, int(4 * res_mult)),
                    angle=rotation, font_key=font_key, font_bold=font_bold
                )
            elif el_type == "text_black":
                clip = create_text_clip_with_pillow(
                    content, fontsize=t_fs, color=(0, 0, 0),
                    stroke_color=(255, 255, 255), stroke_width=max(1, int(4 * res_mult)),
                    angle=rotation, font_key=font_key, font_bold=font_bold
                )
            elif el_type == "text_highlighted":
                clip = create_text_clip_with_pillow(
                    content, fontsize=t_fs, color=(255, 255, 255),
                    bg_color=(255, 165, 0), angle=rotation, font_key=font_key, font_bold=font_bold
                )
            else:
                clip = create_text_clip_with_pillow(
                    content, fontsize=t_fs, color=(0, 0, 0), angle=rotation, font_key=font_key, font_bold=font_bold
                )
            clip = clip.set_start(effective_starts.get(el_id, start_time)).set_end(end_time)
            sc = 1.0
        else:
            filename = "arrow.png" if el_type == "arrow" else item.get("filename", "")
            image_path = resolve_image_path(scene_id, filename, img_dict)
            if not image_path:
                continue
            clip = create_image_clip_safe(
                image_path,
                add_shadow=item.get("property") == "shadow",
                angle=rotation,
            ).set_start(effective_starts.get(el_id, start_time)).set_end(end_time)
            sc = js * res_mult

        bw, bh = clip.size

        # Progressive animation speed: 1st element normal, each subsequent one faster.
        # Durations: elem1=100%, elem2=75%, elem3=55%, elem4+=40% of base duration.
        # Hard rule: last element always completes in LAST_ANIM_S seconds so it
        # finishes before the audio cut regardless of how many elements there are.
        _ANIM_SPEED = [1.0, 0.75, 0.55, 0.40]
        _LAST_ANIM_S = 0.2
        _ANIM_BASE = {"pop": 0.3, "slide_in_left": 0.45, "slide_in_right": 0.45,
                      "slide_in_up": 0.45, "fade_up": 0.4,
                      "typing": float(item.get("typing_speed", 0.5))}
        _ramp_mult = _ANIM_SPEED[min(idx - 1, len(_ANIM_SPEED) - 1)]
        if idx == total_elements:
            _last_mult = _LAST_ANIM_S / _ANIM_BASE.get(animation, 0.3)
            anim_dur_mult = min(_ramp_mult, _last_mult)  # take whichever is faster
        else:
            anim_dur_mult = _ramp_mult

        if animation == "pop":
            _d1 = 0.2 * anim_dur_mult
            _d2 = 0.3 * anim_dur_mult

            def pop_scale(t, s=sc, w=bw, h=bh, d1=_d1, d2=_d2):
                m = max(0.001, 2.0 / min(w, h))
                if t < d1:
                    v = s * 1.2 * (t / d1) if d1 > 0 else s * 1.2
                elif t < d2:
                    v = s * (1.2 - 0.2 * ((t - d1) / max(0.001, d2 - d1)))
                else:
                    v = s
                return max(m, v)

            def pop_pos(t, x=cx, y=cy, w=bw, h=bh, s=sc, d1=_d1, d2=_d2):
                curr = pop_scale(t, s, w, h, d1, d2)
                return (x - (w * curr) / 2, y - (h * curr) / 2)

            clip = clip.resize(pop_scale).set_position(pop_pos)
        elif animation == "slide_in_left":
            _sd = 0.45 * anim_dur_mult
            clip = clip.resize(sc)

            def slide_left_pos(t, x=cx, y=cy, w=bw, h=bh, s=sc, mult=res_mult, d=_sd):
                start_x = x - (340 * mult)
                curr_x = start_x + ((x - start_x) * min(1.0, t / d))
                return (curr_x - (w * s) / 2, y - (h * s) / 2)

            clip = clip.set_position(slide_left_pos)
        elif animation == "slide_in_right":
            _sd = 0.45 * anim_dur_mult
            clip = clip.resize(sc)

            def slide_right_pos(t, x=cx, y=cy, w=bw, h=bh, s=sc, mult=res_mult, d=_sd):
                start_x = x + (340 * mult)
                curr_x = start_x - ((start_x - x) * min(1.0, t / d))
                return (curr_x - (w * s) / 2, y - (h * s) / 2)

            clip = clip.set_position(slide_right_pos)
        elif animation == "slide_in_up":
            _sd = 0.45 * anim_dur_mult
            clip = clip.resize(sc)

            def slide_up_pos(t, x=cx, y=cy, w=bw, h=bh, s=sc, mult=res_mult, d=_sd):
                start_y = y + (220 * mult)
                curr_y = start_y - ((start_y - y) * min(1.0, t / d))
                return (x - (w * s) / 2, curr_y - (h * s) / 2)

            clip = clip.set_position(slide_up_pos)
        elif animation == "fade_up":
            _fd = 0.4 * anim_dur_mult
            clip = clip.resize(sc)

            def fade_up_pos(t, x=cx, y=cy, w=bw, h=bh, s=sc, mult=res_mult, d=_fd):
                start_y = y + (150 * mult)
                curr_y = start_y - ((start_y - y) * min(1.0, t / d))
                return (x - (w * s) / 2, curr_y - (h * s) / 2)

            clip = clip.set_position(fade_up_pos).crossfadein(_fd)
        elif animation == "typing" and el_type.startswith("text_"):
            clip = clip.resize(sc)
            cw, ch = clip.size
            typing_dur = float(item.get("typing_speed", 0.5)) * anim_dur_mult

            def typing_mask(gf, t, dur=typing_dur, width=cw):
                f = gf(t)
                prog = min(1.0, t / dur) if dur > 0 else 1.0
                limit = int(width * prog)
                new_f = np.zeros_like(f)
                if limit > 0:
                    new_f[:, :limit] = f[:, :limit]
                return new_f

            if clip.mask:
                clip.mask = clip.mask.fl(typing_mask)
            clip = clip.set_position((cx - cw / 2, cy - ch / 2))
        else:
            clip = clip.resize(sc).set_position((cx - (bw * sc) / 2, cy - (bh * sc) / 2))

        clips.append(clip)

    final_video = None
    try:
        final_video = CompositeVideoClip(clips, size=(res_w, res_h)).set_audio(audio).set_duration(final_duration)
        # Hold the last frame briefly while avoiding exact clip-end timestamps that can crash
        # MoviePy's internal concatenate clip reader (t == duration boundary bug).
        freeze_t = max(0, scene_content_duration - 0.05)
        safe_eps = 1.0 / 1000.0
        freeze_safe_t = max(0.0, freeze_t - safe_eps)
        final_video = final_video.fl_time(lambda t: min(t, freeze_safe_t)).set_duration(final_duration)
        output_filename = f"{scene_id}.mp4"
        output_path = os.path.join(BASE_DIR, output_filename)
        temp_output_path = os.path.join(BASE_DIR, f"{scene_id}.rendering.mp4")
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception:
                pass

        codec_map = {
            "cpu": ("libx264", "ultrafast"),
            "nvidia": ("h264_nvenc", "fast"),
            "amd": ("h264_amf", None),
            "apple": ("h264_videotoolbox", None),
        }
        codec, preset = codec_map.get(hardware, ("libx264", "ultrafast"))
        render_args = {
            "fps": 30,
            "audio_codec": "aac",
            "threads": os.cpu_count() or 4,
            "ffmpeg_params": ["-pix_fmt", "yuv420p"],
        }
        if preset:
            render_args["preset"] = preset
        render_args["logger"] = MoviePyJobLogger(job_id, "encode") if job_id else None

        update_progress(job_id, phase="encode", message=f"Encoding {scene_id} video...", percent=50)
        try:
            final_video.write_videofile(temp_output_path, codec=codec, **render_args)
        except Exception:
            # Safe fallback to CPU if requested codec unavailable.
            final_video.write_videofile(temp_output_path, codec="libx264", **render_args)

        os.replace(temp_output_path, output_path)

        return output_path
    finally:
        if final_video is not None:
            try:
                final_video.close()
            except Exception:
                pass
        try:
            audio.close()
        except Exception:
            pass
        temp_output_path = os.path.join(BASE_DIR, f"{scene_id}.rendering.mp4")
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception:
                pass


HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Scene Render UI</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js"></script>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; background:#111; color:#eee; margin:0; }
    .top { display:flex; gap:8px; align-items:center; padding:10px; background:#1b1b1b; border-bottom:1px solid #333; flex-wrap:wrap; }
    .top input, .top select, .top button { padding:6px 8px; border-radius:4px; border:1px solid #444; background:#222; color:#eee; }
    .top button { cursor:pointer; }
    .top .primary { background:#ff7a00; color:#fff; border-color:#ff7a00; }
    .wrap { display:flex; gap:12px; padding:12px; }
    .left { flex:1; }
    .right { width:420px; }
    .canvas-wrap { width:960px; max-width:100%; border:2px solid #333; background:#fff; }
    #log { background:#0b0b0b; border:1px solid #333; padding:8px; height:480px; overflow:auto; font-family:Consolas, monospace; font-size:12px; }
    .progress-shell { width:220px; height:10px; background:#2a2a2a; border:1px solid #444; border-radius:999px; overflow:hidden; }
    .progress-fill { height:100%; width:0%; background:linear-gradient(90deg,#ff7a00,#ffd166); transition:width .2s ease; }
    #progress-text { min-width:260px; max-width:420px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:inline-block; }
    .ok { color:#66bb6a; } .err { color:#ef5350; } .info { color:#9e9e9e; }
  </style>
</head>
<body>
  <div class="top">
    <strong>Scene Render UI</strong>
    <span id="sysinfo" class="info"></span>
    <span id="access-urls" class="info"></span>
    <label>Scene</label>
    <input type="number" id="scene" min="1" value="1" />
    <button onclick="loadScene()">Load Scene</button>
    <label>Quality</label>
    <select id="quality">
      <option value="HD">HD (1920x1080)</option>
      <option value="4K">4K (3840x2160)</option>
    </select>
    <label>Hardware</label>
    <select id="hardware">
      <option value="cpu">CPU</option>
      <option value="nvidia">NVIDIA GPU</option>
      <option value="amd">AMD GPU</option>
      <option value="apple">Apple VideoToolbox</option>
    </select>
    <label>Workers</label>
    <input type="number" id="render-workers" min="1" value="1" style="width:80px;" />
    <label>SFX dB</label>
    <input type="number" id="sfx-db" step="0.1" value="-14.0" style="width:90px;" />
    <label>Font</label>
    <select id="font-key" onchange="onFontChanged()" style="min-width:180px;">
      <option value="comic_sans">Comic Sans (Default)</option>
    </select>
    <label style="display:flex;align-items:center;gap:4px;cursor:pointer;">
      <input type="checkbox" id="font-bold" onchange="onFontChanged()" style="cursor:pointer;">Bold
    </label>
    <button onclick="saveDefaultSfxDb()">Save Default</button>
    <button onclick="playSfxPreview()">Play SFX</button>
    <audio id="sfx-player" controls style="height:32px;"></audio>
    <div class="progress-shell"><div id="progress-fill" class="progress-fill"></div></div>
    <span id="progress-text" class="info">Idle</span>
    <button class="primary" onclick="renderCurrentScene()">Render</button>
    <button class="primary" onclick="parallelRenderAllFromHere()">Render All (Max Power)</button>
    <button class="primary" onclick="stitchAllScenes()">Stitch All Scenes</button>
    <button class="primary" onclick="repairCorruptAndStitch()">Auto Repair + Stitch</button>
    <button class="primary" onclick="renderAllAndStitch()">Render All + Stitch</button>
    <label>Range</label>
    <input type="number" id="range-from" min="1" value="1" style="width:70px;" title="First scene in range" />
    <span>–</span>
    <input type="number" id="range-to" min="1" value="1" style="width:70px;" title="Last scene in range" />
    <button class="primary" onclick="renderAndStitchRange()">Render + Stitch Range</button>
    <button class="primary" onclick="stitchRangeOnly()">Stitch Range</button>
    <label>Para</label>
    <select id="para-select" style="min-width:100px;"><option value="">-- select --</option></select>
    <span id="para-scene-info" class="info" style="font-size:11px;"></span>
    <button class="primary" onclick="renderAndStitchPara()">Render + Stitch Para</button>
    <button class="primary" onclick="stitchParaOnly()">Stitch Para</button>
    <button class="primary" onclick="renderAllParasSequential()">Render + Stitch All Paras</button>
  </div>

  <div class="wrap">
    <div class="left">
      <div class="canvas-wrap"><canvas id="c" width="960" height="540"></canvas></div>
    </div>
    <div class="right">
      <div id="log"></div>
    </div>
  </div>

<script>
const canvas = new fabric.Canvas('c', { backgroundColor: '#fff' });
let currentScene = null;
let currentSceneData = null;
let allScenes = [];
let cpuCores = 1;
let maxParallelRenders = 1;
let recommendedParallelRenders = 1;
let fontCssByKey = { 'comic_sans': 'Comic Sans MS, Comic Sans, cursive' };
let fontLabelByKey = { 'comic_sans': 'Comic Sans (Default)' };
let activeProgressJobId = null;
let activeProgressTimer = null;
let lastProgressMessage = '';

function log(msg, cls='info') {
  const el = document.getElementById('log');
  const d = document.createElement('div');
  d.className = cls;
  d.textContent = msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
}

function makeJobId(prefix) {
  return prefix + '-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
}

function setProgress(percent, message) {
  const fill = document.getElementById('progress-fill');
  const text = document.getElementById('progress-text');
  if (fill) {
    fill.style.width = Math.max(0, Math.min(100, percent || 0)) + '%';
  }
  if (text) {
    text.textContent = message || 'Idle';
  }
}

function resetProgress(message='Idle') {
  lastProgressMessage = '';
  setProgress(0, message);
}

async function pollProgressOnce(jobId) {
  const data = await fetchJson('/progress?job_id=' + encodeURIComponent(jobId));
  if (activeProgressJobId !== jobId) return data;
  const percent = typeof data.percent === 'number' ? data.percent : 0;
  const message = data.message || data.phase || 'Working...';
  setProgress(percent, message);
  if (message && message !== lastProgressMessage && (percent > 0 || data.status === 'running')) {
    log(message + (typeof data.percent === 'number' ? ' [' + Math.round(percent) + '%]' : ''), 'info');
    lastProgressMessage = message;
  }
  if (data.status === 'completed') {
    setProgress(100, data.message || 'Done');
    stopProgressPolling(jobId);
  } else if (data.status === 'failed' || data.status === 'error') {
    stopProgressPolling(jobId);
  }
  return data;
}

function startProgressPolling(jobId, label) {
  stopProgressPolling();
  activeProgressJobId = jobId;
  lastProgressMessage = '';
  setProgress(0, label || 'Starting...');
  pollProgressOnce(jobId).catch(() => {});
  activeProgressTimer = setInterval(() => {
    pollProgressOnce(jobId).catch(() => {});
  }, 800);
}

function stopProgressPolling(jobId) {
  if (jobId && activeProgressJobId && activeProgressJobId !== jobId) return;
  if (activeProgressTimer) {
    clearInterval(activeProgressTimer);
    activeProgressTimer = null;
  }
  activeProgressJobId = null;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const raw = await response.text();
  try {
    return raw ? JSON.parse(raw) : {};
  } catch (err) {
    const snippet = (raw || '').trim().replace(/\s+/g, ' ').slice(0, 200);
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${snippet || 'Expected JSON response'}`);
  }
}

function getSelectedFontKey() {
  const el = document.getElementById('font-key');
  if (!el || !el.value) return 'comic_sans';
  return el.value;
}

function isFontBold() {
  const el = document.getElementById('font-bold');
  return el ? el.checked : false;
}

function normalizeTextCase(text) {
  if (!text) return text;
  if (text === text.toUpperCase() && /[A-Z]/.test(text)) {
    return text.toLowerCase().replace(/(^\w|\s+\w)/g, c => c.toUpperCase());
  }
  return text;
}

function getSelectedFontCss() {
  return fontCssByKey[getSelectedFontKey()] || fontCssByKey['comic_sans'] || 'Comic Sans MS, Comic Sans, cursive';
}

function getSelectedFontLabel() {
  return fontLabelByKey[getSelectedFontKey()] || 'Comic Sans (Default)';
}

function getRequestedWorkerCount() {
  const el = document.getElementById('render-workers');
  const raw = parseInt((el && el.value) || '1', 10);
  return Number.isFinite(raw) && raw > 0 ? raw : 1;
}

function onFontChanged() {
  log('Font preview: ' + getSelectedFontLabel(), 'info');
  if (currentSceneData) {
    drawScene(currentSceneData);
  }
}

function loadFontOptions() {
  return fetchJson('/font_options').then(d => {
    const select = document.getElementById('font-key');
    if (!select) return;
    const prev = select.value || d.default_key || 'comic_sans';
    fontCssByKey = {};
    fontLabelByKey = {};
    select.innerHTML = '';
    (d.fonts || []).forEach(f => {
      fontCssByKey[f.key] = f.css || '';
      fontLabelByKey[f.key] = f.label || f.key;
      const opt = document.createElement('option');
      opt.value = f.key;
      opt.textContent = f.label || f.key;
      select.appendChild(opt);
    });
    select.value = fontCssByKey[prev] ? prev : (d.default_key || 'comic_sans');
  });
}

function drawScene(data) {
  canvas.clear();
  canvas.backgroundColor = '#fff';
  const sceneId = data.scene_id || 'scene_1';
  const elements = data.director.elements || [];
  const useCenteredCoords = isCenteredCoordinateScene(elements);
  const timingsById = {};
  (data.timings || []).forEach(t => timingsById[t.element_id] = t);

  elements.forEach(el => {
    let sceneX = (typeof el.x === 'number') ? el.x : 960;
    let sceneY = (typeof el.y === 'number') ? el.y : 540;
    if (useCenteredCoords) {
      sceneX += 960;
      sceneY += 540;
    }
    const x = sceneX / 2;
    const y = sceneY / 2;
    const sc = (el.scale || 1) / 2;
    const angle = el.angle || 0;
    const typ = el.type || 'image';

    if (typ.startsWith('text')) {
      const text = normalizeTextCase(el.text_content || el.phrase || '');
      const opts = { left:x, top:y, originX:'center', originY:'center', angle:angle, scaleX:sc, scaleY:sc, fontSize:40, fontFamily:getSelectedFontCss(), fontWeight: isFontBold() ? 'bold' : 'normal' };
      if (typ === 'text_red') { opts.fill = '#dc143c'; }
      else if (typ === 'text_highlighted') { opts.fill = '#fff'; opts.backgroundColor = '#ffa500'; }
      else { opts.fill = '#000'; }
      const obj = new fabric.Text(text, opts);
      canvas.add(obj);
    } else {
      const fname = typ === 'arrow' ? 'arrow.png' : (el.filename || '');
      const sceneUrl = '/image/' + sceneId + '/' + encodeURIComponent(fname);
      const globalUrl = '/image/' + encodeURIComponent(fname);
      const baseName = (fname || '').toLowerCase().replace(/\.[^.]+$/, '');
      const isDefault = (baseName === 'arrow' || baseName.startsWith('host'));
      const firstUrl = isDefault ? globalUrl : sceneUrl;
      const secondUrl = isDefault ? sceneUrl : globalUrl;
      fabric.Image.fromURL(firstUrl, function(img) {
        if (img && img.width > 1) {
          img.set({ left:x, top:y, originX:'center', originY:'center', angle:angle, scaleX:sc, scaleY:sc });
          canvas.add(img); canvas.renderAll();
        } else {
          fabric.Image.fromURL(secondUrl, function(img2) {
            if (img2 && img2.width > 1) {
              img2.set({ left:x, top:y, originX:'center', originY:'center', angle:angle, scaleX:sc, scaleY:sc });
              canvas.add(img2); canvas.renderAll();
            } else {
              const ph = new fabric.Rect({ left:x, top:y, width:120, height:120, fill:'#ddd', stroke:'#f00', strokeWidth:2, originX:'center', originY:'center' });
              canvas.add(ph); canvas.renderAll();
            }
          }, { crossOrigin: 'anonymous' });
        }
      }, { crossOrigin: 'anonymous' });
    }
  });
  canvas.renderAll();
}

function isCenteredCoordinateScene(elements) {
  if (!elements.length) return false;
  const xs = [];
  const ys = [];
  elements.forEach(el => {
    if (typeof el.x === 'number') xs.push(el.x);
    if (typeof el.y === 'number') ys.push(el.y);
  });
  if (!xs.length || !ys.length) return false;
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const hasNegative = (minX < 0) || (minY < 0);
  const centeredRange = (maxX <= 960 && minX >= -960 && maxY <= 540 && minY >= -540);
  return hasNegative && centeredRange;
}

function loadScene() {
  const scene = document.getElementById('scene').value;
  fetchJson('/load_scene?scene=' + scene).then(d => {
    if (d.error) { log(d.error, 'err'); return; }
    currentScene = d.scene_id;
    currentSceneData = d;
    drawScene(d);
    log('Loaded ' + d.scene_id + ' | elements=' + (d.director.elements || []).length, 'ok');
  });
}

function renderScene(scene, options = {}) {
    return new Promise((resolve, reject) => {
        const quality = document.getElementById('quality').value;
        const hardware = document.getElementById('hardware').value;
        const sfxDb = parseFloat(document.getElementById('sfx-db').value || '-14');
        const fontKey = getSelectedFontKey();
        const fontBold = isFontBold();
        const trackProgress = options.trackProgress !== false;
        const jobId = options.jobId || makeJobId('render-scene-' + scene);
        log('Rendering scene_' + scene + ' (' + quality + ', ' + hardware + ', font: ' + getSelectedFontLabel() + (fontBold ? ' Bold' : '') + ', SFX ' + sfxDb + ' dB) ...', 'info');
        if (trackProgress) {
            startProgressPolling(jobId, 'Preparing scene_' + scene + '...');
        }
        fetchJson('/render_scene', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ scene: scene, quality: quality, hardware: hardware, sfx_db: sfxDb, font_key: fontKey, font_bold: fontBold, job_id: jobId })
        }).then(d => {
            if (trackProgress) {
                stopProgressPolling(jobId);
            }
            if (d.error) {
                if (trackProgress) {
                    setProgress(0, 'Render failed');
                }
                log(d.error, 'err');
                reject(d.error);
            } else {
                if (trackProgress) {
                    setProgress(100, 'Rendered scene_' + scene);
                }
                log(d.msg, 'ok');
                resolve(d.msg);
            }
        }).catch(err => {
            if (trackProgress) {
                stopProgressPolling(jobId);
                setProgress(0, 'Render failed');
            }
            log('Render failed: ' + err, 'err');
            reject(err);
        });
    });
}

function renderCurrentScene() {
    const scene = document.getElementById('scene').value;
    renderScene(scene, { trackProgress: true });
}

async function parallelRenderAllFromHere() {
    const scenesToRender = [...allScenes];
    if (!scenesToRender.length) {
        log('No scenes found to render.', 'err');
        return;
    }
    const requestedWorkers = getRequestedWorkerCount();
    const numWorkers = Math.max(1, Math.min(requestedWorkers, maxParallelRenders || cpuCores, scenesToRender.length));
    if (requestedWorkers !== numWorkers) {
        log(`Clamped workers from ${requestedWorkers} to ${numWorkers} for this machine/server.`, 'info');
    }
    log(`Starting parallel render for ALL ${scenesToRender.length} scenes with ${numWorkers} workers...`, 'ok');

    const sceneQueue = [...scenesToRender];
    let completedCount = 0;
    const totalScenes = scenesToRender.length;

    async function runWorker(workerId) {
        while (sceneQueue.length > 0) {
            const scene = sceneQueue.shift();
            if (scene === undefined) {
                continue;
            }
            log(`Worker ${workerId} starting scene_${scene} (${completedCount + 1}/${totalScenes})`, 'info');
            try {
                await renderScene(scene, { trackProgress: false });
                completedCount++;
                log(`Worker ${workerId} finished scene_${scene} (${completedCount}/${totalScenes})`, 'ok');
                document.getElementById('scene').value = scene;
            } catch (err) {
                log(`Worker ${workerId} FAILED on scene_${scene}: ${err}`, 'err');
            }
        }
    }

    const workerPromises = [];
    for (let i = 1; i <= numWorkers; i++) {
        workerPromises.push(runWorker(i));
    }
    await Promise.all(workerPromises);
    log('--- Parallel render completed for all scenes. ---', 'ok');
}

function stitchAllScenes() {
    return new Promise((resolve, reject) => {
        const hardware = document.getElementById('hardware').value;
        const jobId = makeJobId('stitch');
        log('Stitching rendered scene videos in numeric order...', 'info');
        startProgressPolling(jobId, 'Preparing stitch...');
        fetchJson('/stitch_all_scenes', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ hardware: hardware, job_id: jobId })
        }).then(d => {
            stopProgressPolling(jobId);
            if (d.error) {
                setProgress(0, 'Stitch failed');
                log(d.error, 'err');
                reject(d.error);
            } else {
                setProgress(100, 'Stitch complete');
                log(d.msg, 'ok');
                resolve(d);
            }
        }).catch(err => {
            stopProgressPolling(jobId);
            setProgress(0, 'Stitch failed');
            log('Stitch failed: ' + err, 'err');
            reject(err);
        });
    });
}

function repairCorruptAndStitch() {
    return new Promise((resolve, reject) => {
        const hardware = document.getElementById('hardware').value;
        const quality = document.getElementById('quality').value;
        const sfxDb = parseFloat(document.getElementById('sfx-db').value || '-14');
        const fontKey = getSelectedFontKey();
        const fontBold = isFontBold();
        const jobId = makeJobId('repair-stitch');
        log('Scanning for corrupt scene videos, re-rendering them, then stitching...', 'info');
        startProgressPolling(jobId, 'Scanning corrupt scenes...');
        fetchJson('/repair_corrupt_and_stitch', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ hardware: hardware, quality: quality, sfx_db: sfxDb, font_key: fontKey, font_bold: fontBold, job_id: jobId })
        }).then(d => {
            stopProgressPolling(jobId);
            if (d.error) {
                setProgress(0, 'Auto repair failed');
                log(d.error, 'err');
                reject(d.error);
            } else {
                setProgress(100, 'Auto repair + stitch complete');
                if (Array.isArray(d.repaired_scenes) && d.repaired_scenes.length) {
                    log('Re-rendered corrupt scenes: ' + d.repaired_scenes.join(', '), 'ok');
                } else {
                    log('No corrupt scenes needed repair.', 'info');
                }
                if (Array.isArray(d.repair_failures) && d.repair_failures.length) {
                    log('Repair failures: ' + d.repair_failures.map(x => 'scene_' + x.scene).join(', '), 'err');
                }
                log(d.msg, 'ok');
                resolve(d);
            }
        }).catch(err => {
            stopProgressPolling(jobId);
            setProgress(0, 'Auto repair failed');
            log('Auto repair + stitch failed: ' + err, 'err');
            reject(err);
        });
    });
}

async function renderAllAndStitch() {
    await parallelRenderAllFromHere();
    await stitchAllScenes();
}

function getRangeScenes() {
    const from = parseInt(document.getElementById('range-from').value, 10);
    const to   = parseInt(document.getElementById('range-to').value,   10);
    if (isNaN(from) || isNaN(to) || from < 1 || to < from) {
        log('Invalid range: set From ≤ To, both ≥ 1.', 'err');
        return null;
    }
    const scenes = [];
    for (let n = from; n <= to; n++) scenes.push(n);
    return scenes;
}

async function renderAndStitchRange() {
    const scenes = getRangeScenes();
    if (!scenes) return;
    const requestedWorkers = getRequestedWorkerCount();
    const numWorkers = Math.max(1, Math.min(requestedWorkers, maxParallelRenders || cpuCores, scenes.length));
    log(`Rendering scenes ${scenes[0]}–${scenes[scenes.length-1]} (${scenes.length} scenes, ${numWorkers} workers)...`, 'ok');

    const sceneQueue = [...scenes];
    let completedCount = 0;
    const totalScenes = scenes.length;

    async function runWorker(workerId) {
        while (sceneQueue.length > 0) {
            const scene = sceneQueue.shift();
            if (scene === undefined) continue;
            log(`Worker ${workerId} starting scene_${scene} (${completedCount + 1}/${totalScenes})`, 'info');
            try {
                await renderScene(scene, { trackProgress: false });
                completedCount++;
                log(`Worker ${workerId} finished scene_${scene} (${completedCount}/${totalScenes})`, 'ok');
            } catch (err) {
                log(`Worker ${workerId} FAILED on scene_${scene}: ${err}`, 'err');
            }
        }
    }

    const workerPromises = [];
    for (let i = 1; i <= numWorkers; i++) workerPromises.push(runWorker(i));
    await Promise.all(workerPromises);
    log('--- Range render complete. Starting stitch... ---', 'ok');
    await stitchRange(scenes);
}

function stitchRangeOnly() {
    const scenes = getRangeScenes();
    if (!scenes) return;
    stitchRange(scenes);
}

function stitchRange(scenes, outputFilename) {
    return new Promise((resolve, reject) => {
        const hardware = document.getElementById('hardware').value;
        const jobId = makeJobId('stitch-range');
        const label = outputFilename || 'full_video.mp4';
        log(`Stitching scenes ${scenes[0]}–${scenes[scenes.length-1]} → ${label}...`, 'info');
        startProgressPolling(jobId, 'Preparing stitch...');
        const body = { hardware: hardware, scene_numbers: scenes, job_id: jobId };
        if (outputFilename) body.output_filename = outputFilename;
        fetchJson('/stitch_all_scenes', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }).then(d => {
            stopProgressPolling(jobId);
            if (d.error) {
                setProgress(0, 'Stitch failed');
                log(d.error, 'err');
                reject(d.error);
            } else {
                setProgress(100, 'Stitch complete');
                log(d.msg, 'ok');
                resolve(d);
            }
        }).catch(err => {
            stopProgressPolling(jobId);
            setProgress(0, 'Stitch failed');
            log('Stitch failed: ' + err, 'err');
            reject(err);
        });
    });
}

async function renderAllParasSequential() {
    if (!paraData.length) {
        log('No para data loaded yet.', 'err');
        return;
    }
    const requestedWorkers = getRequestedWorkerCount();
    log(`=== Starting sequential render+stitch for ${paraData.length} paras ===`, 'ok');

    for (let pi = 0; pi < paraData.length; pi++) {
        const p = paraData[pi];
        const scenes = p.scenes;
        const outFile = p.name + '.mp4';
        const numWorkers = Math.max(1, Math.min(requestedWorkers, maxParallelRenders || cpuCores, scenes.length));
        log(`[${pi+1}/${paraData.length}] ${p.name}: rendering ${scenes.length} scenes with ${numWorkers} workers...`, 'ok');

        const sceneQueue = [...scenes];
        let completedCount = 0;
        const totalScenes = scenes.length;

        async function runWorker(workerId) {
            while (sceneQueue.length > 0) {
                const scene = sceneQueue.shift();
                if (scene === undefined) continue;
                try {
                    await renderScene(scene, { trackProgress: false });
                    completedCount++;
                    log(`  [${p.name}] Worker ${workerId} done scene_${scene} (${completedCount}/${totalScenes})`, 'info');
                } catch (err) {
                    log(`  [${p.name}] Worker ${workerId} FAILED scene_${scene}: ${err}`, 'err');
                }
            }
        }

        const workerPromises = [];
        for (let i = 1; i <= numWorkers; i++) workerPromises.push(runWorker(i));
        await Promise.all(workerPromises);
        log(`[${pi+1}/${paraData.length}] ${p.name}: render done. Stitching → ${outFile}...`, 'ok');

        try {
            await stitchRange(scenes, outFile);
            log(`[${pi+1}/${paraData.length}] ${p.name}: saved as ${outFile}`, 'ok');
        } catch (err) {
            log(`[${pi+1}/${paraData.length}] ${p.name}: stitch FAILED — ${err}`, 'err');
        }
    }

    log(`=== All paras done ===`, 'ok');
}

function saveDefaultSfxDb() {
  const sfxDb = parseFloat(document.getElementById('sfx-db').value || '-14');
  const fontKey = getSelectedFontKey();
  const fontBold = isFontBold();
  fetchJson('/save_settings', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ sfx_db: sfxDb, font_key: fontKey, font_bold: fontBold })
  }).then(d => {
    if (d.error) { log(d.error, 'err'); return; }
    log('Saved defaults: SFX ' + sfxDb + ' dB, Font ' + getSelectedFontLabel() + (fontBold ? ' Bold' : ''), 'ok');
  });
}

function playSfxPreview() {
  const scene = document.getElementById('scene').value;
  const sfxDb = parseFloat(document.getElementById('sfx-db').value || '-14');
  const player = document.getElementById('sfx-player');
  player.src = '/preview_sfx_audio?scene=' + scene + '&sfx_db=' + encodeURIComponent(String(sfxDb)) + '&t=' + Date.now();
  player.play().catch(() => {});
  log('Playing SFX preview for scene_' + scene + ' at ' + sfxDb + ' dB', 'info');
}

fetchJson('/system_info').then(d => {
  cpuCores = d.cores || 1;
  maxParallelRenders = d.max_parallel_renders || 1;
  recommendedParallelRenders = d.recommended_parallel_renders || maxParallelRenders;
  const workerInput = document.getElementById('render-workers');
  if (workerInput) {
    workerInput.max = String(maxParallelRenders);
    workerInput.value = String(recommendedParallelRenders);
    workerInput.title = 'Recommended: ' + recommendedParallelRenders + ' | Max allowed here: ' + maxParallelRenders;
  }
  document.getElementById('sysinfo').textContent = 'CPU: ' + d.cpu + ' ('+cpuCores+' cores) | GPU: ' + d.gpu + ' | Workers: ' + recommendedParallelRenders + '/' + maxParallelRenders;
  const gpu = (d.gpu || '').toLowerCase();
  if (gpu.includes('nvidia')) document.getElementById('hardware').value = 'nvidia';
  loadScene();
});

loadFontOptions().then(() => {
  return fetchJson('/settings').then(d => {
    if (typeof d.sfx_db === 'number') {
      document.getElementById('sfx-db').value = d.sfx_db.toFixed(1);
    }
    if (typeof d.font_key === 'string' && fontCssByKey[d.font_key]) {
      document.getElementById('font-key').value = d.font_key;
    }
    const boldEl = document.getElementById('font-bold');
    if (boldEl && typeof d.font_bold === 'boolean') {
      boldEl.checked = d.font_bold;
    }
    if (currentSceneData) drawScene(currentSceneData);
  });
}).catch(() => {
  log('Unable to load font settings; using defaults.', 'err');
});

fetchJson('/access_urls').then(d => {
  const el = document.getElementById('access-urls');
  if (!el) return;
  const parts = [];
  if (d.lan_url) parts.push('Phone (LAN): ' + d.lan_url);
  if (d.public_url) parts.push('Public: ' + d.public_url);
  if (!d.public_url) parts.push('Public URL: set RENDER_VIDEO_PUBLIC_URL env var');
  el.textContent = parts.join('  |  ');
});

fetchJson('/scenes').then(d => {
    allScenes = d;
    log(`Found ${d.length} scenes.`, 'info');
    if (d.length > 0) {
        document.getElementById('range-from').value = d[0];
        document.getElementById('range-to').value   = d[d.length - 1];
    }
});

let paraData = [];  // [{name, scenes}, ...]

fetchJson('/para_list').then(d => {
    paraData = d;
    const sel = document.getElementById('para-select');
    d.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.name;
        const first = p.scenes[0], last = p.scenes[p.scenes.length - 1];
        opt.textContent = `${p.name}  (scenes ${first}–${last}, ${p.scenes.length})`;
        sel.appendChild(opt);
    });
});

document.getElementById('para-select').addEventListener('change', function() {
    const p = paraData.find(x => x.name === this.value);
    const info = document.getElementById('para-scene-info');
    if (!p) { info.textContent = ''; return; }
    info.textContent = `scenes: ${p.scenes[0]}–${p.scenes[p.scenes.length-1]} (${p.scenes.length} total)`;
});

function getSelectedParaScenes() {
    const val = document.getElementById('para-select').value;
    if (!val) { log('No para selected.', 'err'); return null; }
    const p = paraData.find(x => x.name === val);
    if (!p || !p.scenes.length) { log('Para has no scenes.', 'err'); return null; }
    return p.scenes;
}

async function renderAndStitchPara() {
    const scenes = getSelectedParaScenes();
    if (!scenes) return;
    const para = document.getElementById('para-select').value;
    const requestedWorkers = getRequestedWorkerCount();
    const numWorkers = Math.max(1, Math.min(requestedWorkers, maxParallelRenders || cpuCores, scenes.length));
    log(`Rendering ${para} — scenes ${scenes[0]}–${scenes[scenes.length-1]} (${scenes.length} scenes, ${numWorkers} workers)...`, 'ok');

    const sceneQueue = [...scenes];
    let completedCount = 0;
    const totalScenes = scenes.length;

    async function runWorker(workerId) {
        while (sceneQueue.length > 0) {
            const scene = sceneQueue.shift();
            if (scene === undefined) continue;
            log(`Worker ${workerId} starting scene_${scene} (${completedCount + 1}/${totalScenes})`, 'info');
            try {
                await renderScene(scene, { trackProgress: false });
                completedCount++;
                log(`Worker ${workerId} finished scene_${scene} (${completedCount}/${totalScenes})`, 'ok');
            } catch (err) {
                log(`Worker ${workerId} FAILED on scene_${scene}: ${err}`, 'err');
            }
        }
    }

    const workerPromises = [];
    for (let i = 1; i <= numWorkers; i++) workerPromises.push(runWorker(i));
    await Promise.all(workerPromises);
    log(`--- ${para} render complete. Starting stitch... ---`, 'ok');
    await stitchRange(scenes, para + '.mp4');
}

function stitchParaOnly() {
    const scenes = getSelectedParaScenes();
    if (!scenes) return;
    const para = document.getElementById('para-select').value;
    stitchRange(scenes, para + '.mp4');
}

resetProgress('Idle');
</script>
</body>
</html>
"""


@app.route("/")
def index():
    response = make_response(render_template_string(HTML))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/system_info")
def system_info():
    info = detect_system_info()
    info["max_parallel_renders"] = MAX_PARALLEL_RENDERS
    info["recommended_parallel_renders"] = min(MAX_PARALLEL_RENDERS, max(1, min(8, info.get("cores", 1) or 1)))
    return jsonify(info)


@app.route("/access_urls")
def access_urls():
    lan_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = None

    lan_url = f"http://{lan_ip}:5566" if lan_ip else None
    public_url = os.environ.get("RENDER_VIDEO_PUBLIC_URL", "").strip() or None
    return jsonify({
        "lan_url": lan_url,
        "public_url": public_url
    })


@app.route("/scenes")
def scenes_route():
    return jsonify(list_available_scene_numbers())


@app.route("/para_list")
def para_list_route():
    scenes_dir = os.path.join(ASSETS_DIR, "scenes")
    result = []
    if not os.path.isdir(scenes_dir):
        return jsonify(result)
    import glob as _glob
    para_files = sorted(
        _glob.glob(os.path.join(scenes_dir, "para*.json")),
        key=lambda p: int(re.search(r"para(\d+)", os.path.basename(p)).group(1))
    )
    for path in para_files:
        name = os.path.splitext(os.path.basename(path))[0]  # "para1"
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            scenes = []
            for s in data.get("scenes", []):
                m = re.search(r"(\d+)$", s.get("scene_id", ""))
                if m:
                    scenes.append(int(m.group(1)))
            result.append({"name": name, "scenes": sorted(scenes)})
        except Exception:
            pass
    return jsonify(result)


@app.route("/settings")
def settings_route():
    return jsonify(load_settings())


@app.route("/font_options")
def font_options_route():
    return jsonify({
        "default_key": FONT_DEFAULT_KEY,
        "fonts": [{"key": f["key"], "label": f["label"], "css": f["css"]} for f in FONT_OPTIONS],
    })


@app.route("/save_settings", methods=["POST"])
def save_settings_route():
    payload = request.get_json(silent=True) or {}
    current = load_settings()
    try:
        sfx_db = float(payload.get("sfx_db", current.get("sfx_db", -14.0)))
    except Exception:
        return jsonify({"error": "Invalid sfx_db"})
    font_key = str(payload.get("font_key", current.get("font_key", FONT_DEFAULT_KEY)))
    if font_key not in FONT_BY_KEY:
        return jsonify({"error": "Invalid font_key"})
    font_bold = bool(payload.get("font_bold", current.get("font_bold", False)))
    save_settings({"sfx_db": sfx_db, "font_key": font_key, "font_bold": font_bold})
    return jsonify({"ok": True, "sfx_db": sfx_db, "font_key": font_key, "font_bold": font_bold})


@app.route("/load_scene")
def load_scene():
    scene_num = request.args.get("scene", "1")
    try:
        scene_id, director, timings, audio_path = load_scene_files(scene_num)
        scene_dir = os.path.join(OUTPUTS_DIR, scene_id)
        image_count = 0
        if os.path.isdir(scene_dir):
            image_count = len([f for f in os.listdir(scene_dir) if re.search(r"\.(png|jpe?g|webp)$", f, re.I)])
        return jsonify({
            "scene_id": scene_id,
            "director": director,
            "timings": timings,
            "audio_file": audio_path,
            "images_in_scene_folder": image_count,
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/render_scene", methods=["POST"])
def render_scene_route():
    payload = request.get_json(silent=True) or {}
    settings = load_settings()
    scene_num = str(payload.get("scene", "1"))
    quality = payload.get("quality", "HD")
    hardware = payload.get("hardware", "cpu")
    job_id = str(payload.get("job_id", "")).strip()
    try:
        sfx_db = float(payload.get("sfx_db", settings.get("sfx_db", -14.0)))
    except Exception:
        sfx_db = float(settings.get("sfx_db", -14.0))
    font_key = str(payload.get("font_key", settings.get("font_key", FONT_DEFAULT_KEY)))
    if font_key not in FONT_BY_KEY:
        font_key = FONT_DEFAULT_KEY
    font_bold = bool(payload.get("font_bold", settings.get("font_bold", False)))
    try:
        init_progress(job_id, "render", f"scene_{scene_num}")
        # Auto-modify animation + shadow rules each time render is clicked.
        with RENDER_SEMAPHORE:
            auto_modify_director_for_render(scene_num)
            out_path = render_scene(scene_num, quality, hardware, sfx_db, font_key, font_bold=font_bold, job_id=job_id)
        finish_progress(job_id, status="completed", message=f"Rendered scene_{scene_num} successfully.")
        return jsonify({"msg": f"Rendered successfully: {os.path.basename(out_path)}", "file": out_path})
    except Exception as e:
        finish_progress(job_id, status="failed", message=f"Render failed for scene_{scene_num}: {e}")
        return jsonify({"error": f"Render failed: {e}\n{traceback.format_exc()}"})


@app.route("/stitch_all_scenes", methods=["POST"])
def stitch_all_scenes_route():
    payload = request.get_json(silent=True) or {}
    hardware = payload.get("hardware", "cpu")
    job_id = str(payload.get("job_id", "")).strip()
    raw_scene_numbers = payload.get("scene_numbers")
    scene_numbers = None
    if isinstance(raw_scene_numbers, list):
        try:
            scene_numbers = [int(x) for x in raw_scene_numbers]
        except Exception:
            return jsonify({"error": "Invalid scene_numbers list"})

    output_filename = str(payload.get("output_filename", "full_video.mp4")).strip() or "full_video.mp4"
    # Safety: only allow a plain filename, no path traversal
    output_filename = os.path.basename(output_filename)
    if not output_filename.endswith(".mp4"):
        output_filename += ".mp4"

    try:
        init_progress(job_id, "stitch", "stitch_all_scenes")
        result = stitch_scene_videos(hardware=hardware, scene_numbers=scene_numbers, job_id=job_id, output_filename=output_filename)
        gap_note = ""
        if result["gaps"]:
            gap_note = f" (missing scene numbers skipped: {result['gaps']})"
        invalid_note = ""
        if result.get("invalid_files"):
            bad_scenes = [item["scene"] for item in result["invalid_files"]]
            invalid_note = f" (corrupt scene videos skipped: {bad_scenes})"
        res_note = ""
        if result.get("resolution"):
            res = result["resolution"]
            res_note = f" [{res[0]}x{res[1]}]"
        finish_progress(job_id, status="completed", message=f"Stitched {result['scene_count']} scenes into {os.path.basename(result['output_path'])}.")
        return jsonify({
            "msg": (
                f"Stitched {result['scene_count']} scenes into "
                f"{os.path.basename(result['output_path'])} ({result['duration']:.2f}s){res_note}{gap_note}{invalid_note}"
            ),
            "file": result["output_path"],
            "scene_numbers": result["scene_numbers"],
            "gaps": result["gaps"],
            "invalid_files": result.get("invalid_files", []),
            "duration": result["duration"],
            "resolution": result.get("resolution"),
        })
    except Exception as e:
        finish_progress(job_id, status="failed", message=f"Stitch failed: {e}")
        return jsonify({"error": f"Stitch failed: {e}\n{traceback.format_exc()}"})


@app.route("/repair_corrupt_and_stitch", methods=["POST"])
def repair_corrupt_and_stitch_route():
    payload = request.get_json(silent=True) or {}
    settings = load_settings()
    hardware = payload.get("hardware", "cpu")
    quality = payload.get("quality", "HD")
    job_id = str(payload.get("job_id", "")).strip()
    try:
        sfx_db = float(payload.get("sfx_db", settings.get("sfx_db", -14.0)))
    except Exception:
        sfx_db = float(settings.get("sfx_db", -14.0))
    font_key = str(payload.get("font_key", settings.get("font_key", FONT_DEFAULT_KEY)))
    if font_key not in FONT_BY_KEY:
        font_key = FONT_DEFAULT_KEY
    font_bold = bool(payload.get("font_bold", settings.get("font_bold", False)))
    raw_scene_numbers = payload.get("scene_numbers")
    scene_numbers = None
    if isinstance(raw_scene_numbers, list):
        try:
            scene_numbers = [int(x) for x in raw_scene_numbers]
        except Exception:
            return jsonify({"error": "Invalid scene_numbers list"})

    try:
        init_progress(job_id, "repair_stitch", "repair_corrupt_and_stitch")
        update_progress(job_id, phase="scan", message="Scanning rendered scene videos...", percent=2)
        inspection = inspect_rendered_scene_videos(scene_numbers=scene_numbers)
        target_scene_numbers = inspection["requested_scene_numbers"]
        if not target_scene_numbers:
            return jsonify({"error": "No rendered scene videos found to inspect."})

        corrupt_scene_numbers = [int(item["scene"]) for item in inspection["invalid_files"]]
        repaired_scenes = []
        repair_failures = []

        total_repairs = max(1, len(corrupt_scene_numbers))
        for idx, scene_num in enumerate(corrupt_scene_numbers, start=1):
            try:
                update_progress(
                    job_id,
                    phase="repair",
                    message=f"Re-rendering corrupt scene_{scene_num} ({idx}/{total_repairs})",
                    percent=5 + (idx / total_repairs) * 35,
                )
                with RENDER_SEMAPHORE:
                    auto_modify_director_for_render(str(scene_num))
                    output_path = render_scene(str(scene_num), quality, hardware, sfx_db, font_key, font_bold=font_bold)
                ok, err = can_open_video(output_path)
                if not ok:
                    raise RuntimeError(f"scene_{scene_num}.mp4 is still unreadable after re-render: {err}")
                repaired_scenes.append(scene_num)
            except Exception as exc:
                repair_failures.append({"scene": scene_num, "error": str(exc)})

        update_progress(job_id, phase="stitch", message="Repair scan done. Starting stitch...", percent=45)
        result = stitch_scene_videos(hardware=hardware, scene_numbers=target_scene_numbers, job_id=job_id)
        gap_note = ""
        if result["gaps"]:
            gap_note = f" (missing scene numbers skipped: {result['gaps']})"
        invalid_note = ""
        if result.get("invalid_files"):
            bad_scenes = [item["scene"] for item in result["invalid_files"]]
            invalid_note = f" (corrupt scene videos skipped: {bad_scenes})"
        repair_note = ""
        if repaired_scenes:
            repair_note = f" Re-rendered corrupt scenes: {repaired_scenes}."
        failure_note = ""
        if repair_failures:
            failed_scenes = [item["scene"] for item in repair_failures]
            failure_note = f" Re-render failed for scenes: {failed_scenes}."
        res_note = ""
        if result.get("resolution"):
            res = result["resolution"]
            res_note = f" [{res[0]}x{res[1]}]"
        finish_progress(job_id, status="completed", message=f"Auto repair + stitch finished for {result['scene_count']} scenes.")

        return jsonify({
            "msg": (
                f"Stitched {result['scene_count']} scenes into "
                f"{os.path.basename(result['output_path'])} ({result['duration']:.2f}s){res_note}{gap_note}{invalid_note}"
                f"{repair_note}{failure_note}"
            ),
            "file": result["output_path"],
            "scene_numbers": result["scene_numbers"],
            "gaps": result["gaps"],
            "invalid_files": result.get("invalid_files", []),
            "missing_scene_numbers": result.get("missing_scene_numbers", []),
            "repaired_scenes": repaired_scenes,
            "repair_failures": repair_failures,
            "duration": result["duration"],
            "resolution": result.get("resolution"),
        })
    except Exception as e:
        finish_progress(job_id, status="failed", message=f"Auto repair + stitch failed: {e}")
        return jsonify({"error": f"Auto repair + stitch failed: {e}\n{traceback.format_exc()}"})


@app.route("/preview_sfx_audio")
def preview_sfx_audio():
    scene_num = request.args.get("scene", "1")
    scene_id, director, timings, audio_path = load_scene_files(scene_num)
    try:
        sfx_db = float(request.args.get("sfx_db", load_settings().get("sfx_db", -14.0)))
    except Exception:
        sfx_db = load_settings().get("sfx_db", -14.0)
    mixed_path = mix_scene_audio_with_sfx(scene_id, director, timings, audio_path, sfx_db)
    return send_from_directory(os.path.dirname(mixed_path), os.path.basename(mixed_path))


@app.route("/image/<path:filepath>")
def serve_image(filepath):
    full_path = os.path.normpath(os.path.join(OUTPUTS_DIR, filepath))
    if not full_path.startswith(os.path.normpath(OUTPUTS_DIR)):
        return "Forbidden", 403
    if not os.path.isfile(full_path):
        return "Not found", 404
    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))


if __name__ == "__main__":
    print("\nScene Render UI: http://localhost:5566")
    info = detect_system_info()
    print(f"CPU: {info['cpu']}")
    print(f"GPU: {info['gpu']}\n")
    app.run(host="0.0.0.0", port=5566, debug=False, threaded=True)
