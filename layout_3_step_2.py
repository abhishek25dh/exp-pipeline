"""
Layout 3 Step 2 — AI Image Descriptions
=========================================
Reads deterministic spans from Step 1.
AI role (single call): write a visual description for each image span.
Outputs grouped_elements format for the generator.
"""

import json
import os
import time
from pathlib import Path
import sys

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

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_3_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: missing {step1_path}")
        return 1

    step1 = json.loads(step1_path.read_text(encoding="utf-8"))
    scene_text = step1["scene_text"]
    images = step1["images"]

    # --- AI: image descriptions ---
    print(f"  Calling AI for {len(images)} image description(s)...")
    desc_raw = _api_call(
        DESC_SYSTEM_PROMPT,
        json.dumps({
            "scene_voiceover": scene_text,
            "images_needed": [
                {"img_id": img["img_id"], "phrase_spoken_when_image_appears": img["phrase"]}
                for img in images
            ],
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

    grouped_elements = []
    for img in images:
        d = desc_map.get(img["img_id"], "").strip()
        if not d:
            d = _fallback_description(img["phrase"])
        grouped_elements.append({
            "element_id":        img["element_id"],
            "group_id":          img["group_id"],
            "phrase":            img["phrase"],
            "visual_description": d,
            "reason":            "Deterministic span-derived phrase.",
        })

    out_path = Path("assets/tmp") / f"{scene_id}_layout_3_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"grouped_elements": grouped_elements}, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
