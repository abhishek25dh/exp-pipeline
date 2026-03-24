"""
Layout 21 Step 2 — AI Image Description
=========================================
Calls AI to generate a concrete, specific image description for the single
image in layout 21. The AI knows the full scene voiceover and the exact
phrase being spoken when the image appears.
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            API_KEY = _f.read().strip()
MODEL   = "deepseek/deepseek-chat"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a visual art director for explainer videos.

Your job: write a precise image generation prompt for a single scene image.

RULES:
1. Describe the ACTUAL VISUAL — the objects, people, colors, setting, composition you would literally see.
2. Never use words like "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the phrase and full scene voiceover to decide what concrete object, character, or scenario to visualize.
4. Pure white background required.
5. End with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum.
7. Choose style ("2D colorful cartoon graphic" or "realistic photo") based on whether the subject is a real-world scene/person or an abstract concept.
8. Output valid JSON only. No extra text, no markdown.

OUTPUT FORMAT:
{
  "style": "2D colorful cartoon graphic",
  "description": "..."
}"""

# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_api(system_prompt: str, user_content: str):
    if not API_KEY:
        print("Error: OPENROUTER_API_KEY not set.")
        return None

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
    }
    fallback_models = [
        m.strip()
        for m in os.getenv(
            "OPENROUTER_MODEL_FALLBACKS",
            f"{MODEL},deepseek/deepseek-v3.2,openai/gpt-4o-mini",
        ).split(",")
        if m.strip()
    ]
    models = [MODEL] + [m for m in fallback_models if m != MODEL]

    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.6,
        }
        for attempt in range(1, 5):
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90,
                )
            except Exception as e:
                wait = min(2 ** attempt, 10)
                print(f"  Network error ({model}, attempt {attempt}/4): {e}. Retrying in {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]

            if resp.status_code in (429, 500, 502, 503, 504):
                wait = min(2 ** attempt, 10)
                print(f"  API {resp.status_code} ({model}, attempt {attempt}/4). Retrying in {wait}s...")
                time.sleep(wait)
                continue

            print(f"  API {resp.status_code} ({model}): {resp.text[:200]}")
            break

        print(f"  All attempts failed for model: {model}")

    return None


def clean_json(content: str) -> str:
    content = content.strip()
    start = content.find("{")
    end   = content.rfind("}")
    if start != -1 and end != -1:
        return content[start:end + 1]
    return content


def fallback_description(img_phrase: str) -> dict:
    clean = img_phrase.strip(".,!? ")
    return {
        "style": "2D colorful cartoon graphic",
        "description": (
            f"On a pure white background, a 2D colorful cartoon graphic of a bold, clear visual "
            f"related to '{clean}'. Simple shapes, strong colors, clean composition. "
            f"No text, no letters, no numbers, no watermarks."
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_21_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: {step1_path} not found. Run Step 1 first.")
        return 1

    step1      = json.loads(step1_path.read_text(encoding="utf-8"))
    has_group  = step1.get("has_group", False)
    group      = step1.get("group")
    scene_text = step1.get("scene_text", "")

    img_desc = {}

    if not has_group or not group:
        print("  No group — skipping AI call (text-only layout).")
    else:
        img_phrase = group.get("img_phrase", "")
        user_content = json.dumps({
            "scene_voiceover":                    scene_text,
            "phrase_spoken_when_image_appears":   img_phrase,
        }, indent=2)

        print(f"  Calling AI for image description (phrase: '{img_phrase}')...")
        raw = call_api(SYSTEM_PROMPT, user_content)

        if raw:
            try:
                data     = json.loads(clean_json(raw))
                style    = data.get("style", "2D colorful cartoon graphic")
                desc_txt = data.get("description", "").strip()
                if desc_txt:
                    img_desc = {"style": style, "description": desc_txt}
                    print(f"  AI: {desc_txt[:100]}...")
                else:
                    raise ValueError("Empty description")
            except Exception as e:
                print(f"  Warning: parse error ({e}). Using fallback.")
                img_desc = fallback_description(img_phrase)
        else:
            print("  API failed. Using fallback.")
            img_desc = fallback_description(img_phrase)

    # Merge back into step1 data
    enriched_group = None
    if group:
        enriched_group = {
            **group,
            "img_description": img_desc.get("description", ""),
            "img_style":       img_desc.get("style", "2D colorful cartoon graphic"),
        }

    out = {
        "scene_id":         scene_id,
        "scene_text":       scene_text,
        "has_group":        has_group,
        "main_text_phrase": step1.get("main_text_phrase", ""),
        "group":            enriched_group,
    }

    out_path = Path("assets/tmp") / f"{scene_id}_layout_21_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
