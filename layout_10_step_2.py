"""
Layout 10 Step 2 — AI Visual Descriptions
==========================================
Layout 10: 1 macro image + 2-3 micro images + connecting arrows.

Reads deterministic phrase plan from Step 1.
Single AI call: write visual descriptions for macro + all micro images.
Outputs the complete step-2 data for the generator.
"""

import json
import os
import random
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

MODEL      = "deepseek/deepseek-chat"
TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]

DESC_SYSTEM = """You are a visual art director for explainer videos.

Write a precise image generation prompt for each image element.

RULES:
1. Describe the ACTUAL VISUAL — objects, colors, setting, composition literally seen.
2. Never use "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the phrase spoken when the image appears AND the full scene voiceover for context.
4. Pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum per image.
7. Style: "2D colorful cartoon graphic" or "realistic photo" — pick whichever fits best.
8. Output valid JSON only. No markdown.

OUTPUT FORMAT:
{"images": [{"img_id": "macro", "style": "2D colorful cartoon graphic", "description": "..."},
            {"img_id": "micro_0", "style": "...", "description": "..."}]}"""


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


def _fallback_desc(phrase):
    p = phrase.strip(".,!? ")[:60]
    return (f"On a pure white background, a 2D colorful cartoon graphic related to '{p}'. "
            f"No text, no letters, no numbers, no watermarks.")


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"
    random.seed(int(scene_num) * 7919 if str(scene_num).isdigit() else hash(scene_num))

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_10_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: missing {step1_path}")
        return 1

    step1      = json.loads(step1_path.read_text(encoding="utf-8"))
    macro      = step1["macro"]
    micros     = step1["micros"]
    scene_text = step1.get("scene_text", "")

    # Build image request list: macro + all micros
    images_needed = [{"img_id": "macro", "phrase_spoken_when_image_appears": macro["img_phrase"]}]
    for m in micros:
        images_needed.append({"img_id": m["micro_id"],
                               "phrase_spoken_when_image_appears": m["img_phrase"]})

    print(f"  Calling AI for {len(images_needed)} image description(s)...")
    raw = _api_call(DESC_SYSTEM,
                    json.dumps({"scene_voiceover": scene_text,
                                "images_needed": images_needed}, indent=2))

    desc_map = {}
    if raw:
        try:
            data = json.loads(raw)
            desc_map = {item["img_id"]: item.get("description", "").strip()
                        for item in data.get("images", []) if item.get("img_id")}
        except Exception:
            pass

    # Assemble output
    out = {
        "macro_image": {
            "visual_description": desc_map.get("macro", "") or _fallback_desc(macro["img_phrase"]),
            "is_realistic": False,
            "img_phrase": macro["img_phrase"],
            "txt_phrase": macro["txt_phrase"],
            "text_type":  random.choice(TEXT_TYPES),
        },
        "micro_images": [],
    }

    for m in micros:
        mid = m["micro_id"]
        out["micro_images"].append({
            "visual_description": desc_map.get(mid, "") or _fallback_desc(m["img_phrase"]),
            "is_realistic": False,
            "arrow_phrase": m["arrow_phrase"],
            "img_phrase":   m["img_phrase"],
            "txt_phrase":   m["txt_phrase"],
            "text_type":    random.choice(TEXT_TYPES),
        })

    out_path = Path("assets/tmp") / f"{scene_id}_layout_10_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
