import json
import re
import sys
from pathlib import Path

import requests

import os
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            API_KEY = _f.read().strip()
MODEL = "deepseek/deepseek-chat"
TARGETS = {"you", "you're", "youre", "your"}
EMOTIONS = {"happy", "sad", "angry", "explaining"}


def clean_json_response(content: str) -> str:
    content = (content or "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        return content[start : end + 1].strip()
    return content


def normalize_token(token: str) -> str:
    return re.sub(r"^[^\w']+|[^\w']+$", "", token.lower())


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def detect_emotion_heuristic(script_text: str) -> str:
    t = (script_text or "").lower()
    if any(w in t for w in ["happy", "content", "joy", "glad"]):
        return "happy"
    if any(w in t for w in ["sad", "lonely", "alone", "sorrow"]):
        return "sad"
    if any(w in t for w in ["angry", "mad", "furious", "frustrat"]):
        return "angry"
    return "explaining"


def _window_around(idx: int, size: int, total: int):
    start = max(0, idx - size // 2)
    end = start + size
    if end > total:
        end = total
        start = max(0, end - size)
    return start, end


def _segment_sizes(length: int, slots: int):
    if slots <= 0:
        return []
    sizes = [length // slots] * slots
    for i in range(length % slots):
        sizes[i] += 1
    return sizes


def _best_partition_spread(total_tokens: int, span_start: int, span_end: int):
    left_len = span_start
    right_len = total_tokens - span_end
    spreads = []
    for left_slots in range(5):
        right_slots = 4 - left_slots
        if left_len > 0 and left_slots == 0:
            continue
        if right_len > 0 and right_slots == 0:
            continue
        if left_slots > left_len or right_slots > right_len:
            continue
        sizes = _segment_sizes(left_len, left_slots) + _segment_sizes(right_len, right_slots)
        if len(sizes) != 4:
            continue
        spreads.append(max(sizes) - min(sizes))
    return min(spreads) if spreads else 999


def build_host_candidates(tokens):
    n = len(tokens)
    if n == 0:
        return []

    # We need at least 4 non-host tokens for 4 images.
    max_host_len = max(1, n - 4)

    spans = []
    seen = set()
    anchor_indices = [i for i, t in enumerate(tokens) if normalize_token(t) in TARGETS]
    if not anchor_indices:
        anchor_indices = [0]

    for idx in anchor_indices:
        for size in range(7, 2, -1):
            if size > max_host_len:
                continue
            s, e = _window_around(idx, size, n)
            if e - s > max_host_len:
                continue
            if (s, e) not in seen:
                seen.add((s, e))
                spans.append((s, e))

    if not spans:
        # Extreme short scripts fallback.
        size = min(max_host_len, max(1, n // 2))
        spans = [(0, max(1, size))]

    candidates = []
    for i, (s, e) in enumerate(spans, start=1):
        phrase = " ".join(tokens[s:e]).strip()
        if not phrase:
            continue
        candidates.append(
            {
                "id": f"H{i}",
                "span": [s, e],
                "phrase": phrase,
            }
        )

    # Keep host choices that allow the most balanced 4-image split.
    if candidates:
        best = min(_best_partition_spread(n, c["span"][0], c["span"][1]) for c in candidates)
        candidates = [
            c for c in candidates
            if _best_partition_spread(n, c["span"][0], c["span"][1]) == best
        ]
        for i, c in enumerate(candidates, start=1):
            c["id"] = f"H{i}"
    return candidates


def call_api(system_prompt: str, user_payload: dict):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"]
    return json.loads(clean_json_response(raw))


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"
    prompt_file = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_file.exists():
        print(f"Error: {prompt_file} not found.")
        return 1

    scene_data = json.loads(prompt_file.read_text(encoding="utf-8"))
    script_text = strip_scene_prefix(scene_data.get("prompt", ""))
    tokens = script_text.split()
    if len(tokens) < 1:
        print(f"Error: {scene_id} has only {len(tokens)} tokens; need >=1 for host+4 images.")
        return 1

    candidates = build_host_candidates(tokens)
    if not candidates:
        print(f"Error: Could not build host candidates for {scene_id}.")
        return 1

    system_prompt = Path("layout_7_step_1.txt").read_text(encoding="utf-8")
    user_payload = {
        "scene_id": scene_id,
        "script_tokens": tokens,
        "host_candidates": candidates,
    }

    parsed = {}
    try:
        print("Calling OpenRouter API for Layout 7 Step 1 (Host Selection)...")
        parsed = call_api(system_prompt, user_payload)
    except Exception as exc:
        print(f"Step 1 API warning: {exc}")
        print("Falling back to deterministic defaults.")

    selected_id = str(parsed.get("host_candidate_id", "")).strip()
    selected = next((c for c in candidates if c["id"] == selected_id), candidates[0])

    host_emotion = str(parsed.get("host_emotion", "")).strip().lower()
    if host_emotion not in EMOTIONS:
        host_emotion = detect_emotion_heuristic(script_text)

    g1 = str(parsed.get("group_1_focus", "")).strip() or "left narrative strand"
    g2 = str(parsed.get("group_2_focus", "")).strip() or "right narrative strand"

    out = {
        "script_tokens": tokens,
        "host_emotion": host_emotion,
        "host_span": selected["span"],
        "host_phrase": selected["phrase"],
        "groups": [
            {"id": "group_1", "narrative_focus": g1},
            {"id": "group_2", "narrative_focus": g2},
        ],
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{scene_id}_layout_7_step_1_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
