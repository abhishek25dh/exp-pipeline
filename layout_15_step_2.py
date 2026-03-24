"""
Layout 15 Step 2 — AI Hero Image Description
=============================================
Reads deterministic phrase plan from Step 1.
Single AI call: write visual description for the hero image only.
AI also picks text_types for section, bullets, and cta.

Phrases come ONLY from step_1 verbatim spans — AI never invents text.
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

MODEL = "deepseek/deepseek-chat"

DESC_SYSTEM = """You are a visual art director for explainer videos.

Write a precise image generation prompt for the hero image.

RULES:
1. Describe the ACTUAL VISUAL — objects, colors, setting, composition literally seen.
2. Never use "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the hero phrase AND the full scene voiceover for context.
4. Pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum.
7. Style: "2D colorful cartoon graphic" or "realistic photo" — pick whichever fits best.
8. Also pick text_types for each slot: choose from "text_highlighted", "text_red", "text_black".
9. Output valid JSON only. No markdown.

OUTPUT FORMAT:
{"is_realistic": false, "description": "...", "text_types": {"section_title": "text_highlighted", "bullet_b1": "text_black", "bullet_b2": "text_red", "bullet_b3": "text_black", "cta": "text_red"}}"""


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


TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]
DEFAULT_TEXT_TYPES = {
    "section_title": "text_highlighted",
    "bullet_b1": "text_black",
    "bullet_b2": "text_red",
    "bullet_b3": "text_black",
    "cta": "text_red",
}


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"
    random.seed(int(scene_num) * 7919 if str(scene_num).isdigit() else hash(scene_num))

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_15_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: missing {step1_path}")
        return 1

    step1      = json.loads(step1_path.read_text(encoding="utf-8"))
    scene_text = step1["scene_text"]
    hero_phrase = step1["hero"]["phrase"]

    print(f"  Calling AI for hero image description...")
    raw = _api_call(DESC_SYSTEM,
                    json.dumps({
                        "scene_voiceover": scene_text,
                        "hero_phrase": hero_phrase,
                    }, indent=2))

    is_realistic = False
    description  = ""
    text_types   = dict(DEFAULT_TEXT_TYPES)

    if raw:
        try:
            data = json.loads(raw)
            is_realistic = bool(data.get("is_realistic", False))
            description  = data.get("description", "").strip()
            if data.get("text_types"):
                for k, v in data["text_types"].items():
                    if v in TEXT_TYPES:
                        text_types[k] = v
        except Exception:
            pass

    if not description:
        description = _fallback_desc(hero_phrase)

    out = {
        "scene_id": scene_id,
        "hero_image": {
            "visual_description": description,
            "is_realistic": is_realistic,
        },
        "text_types": text_types,
    }

    out_path = Path("assets/tmp") / f"{scene_id}_layout_15_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 2 complete. Saved to {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
