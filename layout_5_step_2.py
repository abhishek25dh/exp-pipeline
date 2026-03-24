"""
Layout 5 Step 2 — AI Image Descriptions
=========================================
Layout 5: Cause -> Effect groups with arrow between them.

Reads deterministic groups from Step 1 (phrases already tiled correctly).
AI role (single call): write visual descriptions for all cause + effect images.
Outputs detailed_groups format for the generator.
"""

import json
import os
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

DESC_SYSTEM_PROMPT = """You are a visual art director for explainer videos.

Write a precise image generation prompt for each scene image.

RULES:
1. Describe the ACTUAL VISUAL -- objects, people, colors, setting, composition literally seen.
2. Never use "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the phrase spoken when the image appears AND the full scene voiceover for context.
4. Pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum.
7. Choose style: "2D colorful cartoon graphic" or "realistic photo".
8. Output valid JSON only. No markdown.

OUTPUT FORMAT:
{"images": [{"img_id": "img_0", "style": "2D colorful cartoon graphic", "description": "..."}]}"""


def _api_call(system, user):
    if not API_KEY:
        return None
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
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


def _fallback_description(phrase):
    p = phrase.strip(".,!? ")
    return (f"On a pure white background, a 2D colorful cartoon graphic related to '{p[:60]}'. "
            f"No text, no letters, no numbers, no watermarks.")


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_5_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: {step1_path} not found. Run Step 1 first.")
        return 1

    step1 = json.loads(step1_path.read_text(encoding="utf-8"))
    groups = step1.get("groups", [])
    scene_text = step1.get("scene_text", "")

    if not groups:
        print("Error: no groups found in Layout 5 Step 1 output.")
        return 1

    # Build flat list of all images needed (cause + effect per group)
    images_needed = []
    for g in groups:
        gid = g.get("group_id", "")
        cause_p = (g.get("cause_phrase") or "").strip()
        effect_p = (g.get("effect_phrase") or "").strip()
        images_needed.append({"img_id": f"{gid}_cause", "phrase_spoken_when_image_appears": cause_p})
        images_needed.append({"img_id": f"{gid}_effect", "phrase_spoken_when_image_appears": effect_p})

    # AI: one call for all image descriptions
    print(f"  Calling AI for {len(images_needed)} image description(s)...")
    desc_raw = _api_call(
        DESC_SYSTEM_PROMPT,
        json.dumps({
            "scene_voiceover": scene_text,
            "images_needed": images_needed,
        }, indent=2),
    )

    desc_map = {}
    if desc_raw:
        try:
            data = json.loads(desc_raw)
            desc_map = {item["img_id"]: item.get("description", "").strip()
                        for item in data.get("images", []) if item.get("img_id")}
        except Exception:
            pass

    # Assemble detailed_groups
    detailed = []
    for g in groups:
        gid = g.get("group_id", "")
        cause_p = (g.get("cause_phrase") or "").strip()
        arrow_p = (g.get("arrow_phrase") or "").strip()
        effect_p = (g.get("effect_phrase") or "").strip()

        cause_desc = desc_map.get(f"{gid}_cause", "").strip() or _fallback_description(cause_p)
        effect_desc = desc_map.get(f"{gid}_effect", "").strip() or _fallback_description(effect_p)

        detailed.append({
            "group_id": gid,
            "arrow_phrase": arrow_p,
            "cause": {
                "phrase": cause_p,
                "visual_description": cause_desc,
            },
            "effect": {
                "phrase": effect_p,
                "visual_description": effect_desc,
            },
            "text_label": g.get("text_label", None),
        })

    out_path = Path("assets/tmp") / f"{scene_id}_layout_5_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"detailed_groups": detailed}, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
