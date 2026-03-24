"""
Layout 16 Step 2 — AI Visual Descriptions
==========================================
Reads phrase plan from Step 1.
Single AI call: write visual descriptions for all 5 frame images.
AI also confirms/picks caption_type for each frame.

Phrases come ONLY from step_1 verbatim spans — AI never invents text.
"""

import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openrouter_key.txt")
    if os.path.exists(_kp):
        with open(_kp, encoding="utf-8") as _f:
            API_KEY = _f.read().strip()

MODEL = "deepseek/deepseek-chat"

DESC_SYSTEM = """You are a visual art director for explainer videos.

For each filmstrip frame image write a precise image generation prompt.

RULES:
1. Describe the ACTUAL VISUAL — objects, colors, setting, composition literally seen.
2. Never use "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the phrase spoken when the image appears AND the full scene voiceover for context.
4. Pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum.
7. Style: "2D colorful cartoon graphic" or "realistic photo" — pick whichever fits best.
8. Also pick caption_type for each frame: one of "text_red", "text_highlighted", "text_black".
9. Output valid JSON only. No markdown.

OUTPUT FORMAT:
{"frames": [
  {"frame_id": "frame_1", "caption_type": "text_black", "is_realistic": false, "description": "..."},
  {"frame_id": "frame_2", "caption_type": "text_highlighted", "is_realistic": false, "description": "..."},
  ...
]}"""


def _api_call(system, user):
    if not API_KEY:
        return None
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user",   "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }
    for attempt in range(1, 4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers=headers, json=payload, timeout=90)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"].strip()
                s, e = raw.find("{"), raw.rfind("}")
                return raw[s:e + 1] if s != -1 else raw
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 8))
        except Exception:
            time.sleep(min(2 ** attempt, 8))
    return None


NEGATIVE_WORDS = {
    "loser", "regret", "upset", "stressed", "stress", "worst", "hate", "sad",
    "alone", "lonely", "panic", "anxious", "anxiety", "angry", "anger",
}
HIGHLIGHT_WORDS = {
    "secure", "strength", "grounded", "enjoy", "company", "content", "calm",
    "meaningful", "carefully", "realize",
}
TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]


def _fallback_caption_type(phrase):
    w = set(re.findall(r"[a-z']+", (phrase or "").lower()))
    if w & NEGATIVE_WORDS:
        return "text_red"
    if w & HIGHLIGHT_WORDS:
        return "text_highlighted"
    return "text_black"


def _fallback_desc(phrase):
    p = (phrase or "").strip(".,!? ")[:60]
    return (f"On a pure white background, a 2D colorful cartoon graphic illustrating the concept of '{p}'. "
            f"Bold colors, simple shapes, no background details. "
            f"No text, no letters, no numbers, no watermarks.")


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"
    random.seed(int(scene_num) * 7919 if str(scene_num).isdigit() else hash(scene_num))

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_16_step_1_tmp.json"
    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"

    if not step1_path.exists():
        print(f"Error: missing {step1_path}")
        return 1
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    step1      = json.loads(step1_path.read_text(encoding="utf-8"))
    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text = re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt_data.get("prompt", ""), flags=re.I).strip()

    frames = step1.get("frames", [])
    images_needed = [
        {"frame_id": f["frame_id"], "phrase_spoken_when_image_appears": f.get("img_phrase", "")}
        for f in frames
    ]

    print(f"  Calling AI for {len(images_needed)} frame image description(s)...")
    raw = _api_call(DESC_SYSTEM,
                    json.dumps({
                        "scene_voiceover": scene_text,
                        "images_needed": images_needed,
                    }, indent=2))

    desc_map  = {}
    ltype_map = {}
    real_map  = {}

    if raw:
        try:
            data = json.loads(raw)
            for item in data.get("frames", []):
                fid = item.get("frame_id")
                if fid:
                    desc_map[fid]  = item.get("description", "").strip()
                    ltype_map[fid] = item.get("caption_type", "")
                    real_map[fid]  = bool(item.get("is_realistic", False))
        except Exception:
            pass

    strip_title    = step1.get("strip_title", "")
    strip_subtitle = step1.get("strip_subtitle", "")

    detailed_frames = []
    for fr in frames:
        fid        = fr.get("frame_id", "")
        img_phrase = (fr.get("img_phrase") or "").strip()
        cap_phrase = (fr.get("cap_phrase") or "").strip()
        ltype      = ltype_map.get(fid, "")
        if ltype not in TEXT_TYPES:
            ltype = _fallback_caption_type(cap_phrase)
        detailed_frames.append({
            "frame_id":     fid,
            "img_phrase":   img_phrase,
            "cap_phrase":   cap_phrase,
            "caption_type": ltype,
            "image": {
                "visual_description": desc_map.get(fid, "") or _fallback_desc(img_phrase),
                "is_realistic": real_map.get(fid, False),
            },
        })

    out = {
        "strip_title":    strip_title,
        "strip_subtitle": strip_subtitle,
        "detailed_frames": detailed_frames,
    }

    out_path = Path("assets/tmp") / f"{scene_id}_layout_16_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 2 complete. Saved to {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
