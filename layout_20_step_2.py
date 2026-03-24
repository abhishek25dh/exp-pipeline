"""
Layout 20 Step 2 — AI Image Description Generator
===================================================
Reads the phrase plan from Step 1 and calls AI to write a concrete,
specific image/graphic description for each image element.

The AI knows:
  - The full scene voiceover text (context)
  - The exact phrase spoken when that image appears
  - The position of that image in the layout (left / center / right)

The AI writes a description of the ACTUAL VISUAL — what you would see in
the image — not a meta-description like "depicting X" or "representing Y".
"""

import json
import os
import re
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

Your job: write a precise image generation prompt for each scene image.

RULES:
1. Each description must describe the ACTUAL VISUAL — the objects, people, colors, composition, setting you would literally see in the image.
2. Never say "depicting", "representing", "showing", "illustrating", or "symbolizing". Just describe what is there.
3. Use the phrase and scene context to decide what concrete scene, object, or character makes sense.
4. Every image must have a pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. Keep each description to 2-3 sentences maximum.
7. Vary the visual style between images in the same scene — mix realistic and cartoon when appropriate.
8. Output valid JSON only. No extra text, no markdown.

OUTPUT FORMAT:
{
  "images": [
    {
      "group_id": "group_1",
      "style": "2D colorful cartoon graphic" or "realistic photo",
      "description": "..."
    }
  ]
}"""

# ---------------------------------------------------------------------------
# API call (same pattern as layout_selector.py)
# ---------------------------------------------------------------------------

def call_api(system_prompt: str, user_content: str):
    if not API_KEY:
        print("Error: OPENROUTER_API_KEY is not set.")
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


# ---------------------------------------------------------------------------
# Fallback description (used if API fails)
# ---------------------------------------------------------------------------

def fallback_description(img_phrase: str, position: str) -> str:
    """Simple deterministic fallback — still concrete, not meta."""
    words = img_phrase.strip(".,!? ").lower()
    return (
        f"On a pure white background, a 2D colorful cartoon graphic of an object or character "
        f"that relates to '{words}'. Clean, bold lines, minimal detail. "
        f"No text, no letters, no numbers, no watermarks."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_20_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: {step1_path} not found. Run Step 1 first.")
        return 1

    step1      = json.loads(step1_path.read_text(encoding="utf-8"))
    n_groups   = step1.get("n_groups", 0)
    groups     = step1.get("groups", [])
    scene_text = step1.get("scene_text", "")

    if n_groups == 0:
        # No images needed — write straight-through output (pass through step_1 data)
        out = {
            "images": [],
            "n_groups": 0,
            "groups": [],
            "main_text_phrase": step1.get("main_text_phrase", ""),
            "scene_text": scene_text,
        }
        out_path = Path("assets/tmp") / f"{scene_id}_layout_20_step_2_tmp.json"
        out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"No images (0 groups). Step 2 complete -> {out_path}")
        return 0

    # Build user payload for AI
    image_list = []
    for g in groups:
        image_list.append({
            "group_id": g["group_id"],
            "position": g["position"],
            "phrase_spoken_when_image_appears": g["img_phrase"],
        })

    user_content = json.dumps({
        "scene_voiceover": scene_text,
        "images_needed": image_list,
    }, indent=2)

    print(f"  Calling AI for {len(groups)} image description(s)...")
    raw = call_api(SYSTEM_PROMPT, user_content)

    # Parse AI response
    descriptions = {}   # group_id → {style, description}

    if raw:
        try:
            data = json.loads(clean_json(raw))
            for item in data.get("images", []):
                gid = item.get("group_id", "")
                if gid:
                    descriptions[gid] = {
                        "style":       item.get("style", "2D colorful cartoon graphic"),
                        "description": item.get("description", ""),
                    }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Warning: AI parse error ({e}). Using fallbacks.")

    # Merge descriptions back into groups, apply fallback where needed
    enriched_groups = []
    for g in groups:
        gid  = g["group_id"]
        desc = descriptions.get(gid, {})
        image_desc = desc.get("description", "").strip()
        if not image_desc:
            print(f"  Fallback description for {gid} ({g['position']})")
            image_desc = fallback_description(g["img_phrase"], g["position"])

        enriched_groups.append({
            **g,
            "img_description": image_desc,
            "img_style":       desc.get("style", "2D colorful cartoon graphic"),
        })
        print(f"  {gid} ({g['position']:6s}): {image_desc[:80]}...")

    out = {
        "scene_id":   scene_id,
        "scene_text": scene_text,
        "n_groups":   n_groups,
        "groups":     enriched_groups,
        "main_text_phrase": step1.get("main_text_phrase", ""),
    }

    out_path = Path("assets/tmp") / f"{scene_id}_layout_20_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
