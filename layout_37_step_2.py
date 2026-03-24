"""
Layout 37 Step 2 - AI Descriptions for All Active Images
=========================================================
All elements in layout 37 are AI-generated images.
Calls AI for every active image (up to 6).
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _key_path = Path(__file__).parent / "openrouter_key.txt"
    if _key_path.exists():
        API_KEY = _key_path.read_text(encoding="utf-8").strip()

MODEL = "deepseek/deepseek-chat"

SYSTEM_PROMPT = """You are a visual art director for explainer videos.

Write a precise image generation prompt for each scene image.

RULES:
1. Describe the ACTUAL VISUAL -- objects, people, colors, setting, composition you would literally see.
2. Never use "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the phrase spoken when the image appears AND the full scene voiceover for context.
4. Pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum.
7. Choose style per image: "2D colorful cartoon graphic" or "realistic photo".
8. Output valid JSON only. No extra text, no markdown.

OUTPUT FORMAT:
{
  "images": [
    {
      "img_id": "img_center",
      "style": "2D colorful cartoon graphic",
      "description": "..."
    }
  ]
}"""


def call_api(system_prompt, user_content):
    if not API_KEY:
        print("Error: OPENROUTER_API_KEY not set.")
        return None
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    fallback_models = [
        m.strip() for m in os.getenv(
            "OPENROUTER_MODEL_FALLBACKS",
            f"{MODEL},deepseek/deepseek-v3.2,openai/gpt-4o-mini"
        ).split(",") if m.strip()
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
                    headers=headers, json=payload, timeout=90,
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


def clean_json(content):
    content = content.strip()
    s, e = content.find("{"), content.rfind("}")
    return content[s:e + 1] if s != -1 and e != -1 else content


def fallback_description(phrase):
    clean = phrase.strip(".,!? ")
    return {
        "style": "2D colorful cartoon graphic",
        "description": (
            f"On a pure white background, a 2D colorful cartoon graphic with bold shapes "
            f"and strong colors related to '{clean[:60]}'. Clean, clear composition. "
            f"No text, no letters, no numbers, no watermarks."
        ),
    }


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_37_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: {step1_path} not found. Run Step 1 first.")
        return 1

    step1      = json.loads(step1_path.read_text(encoding="utf-8"))
    scene_text = step1.get("scene_text", "")
    images     = step1.get("images", [])

    if not images:
        out_path = Path("assets/tmp") / f"{scene_id}_layout_37_step_2_tmp.json"
        out_path.write_text(json.dumps(step1, indent=2), encoding="utf-8")
        print(f"No images. Step 2 complete -> {out_path}")
        return 0

    user_content = json.dumps({
        "scene_voiceover": scene_text,
        "images_needed": [
            {"img_id": img["img_id"], "phrase_spoken_when_image_appears": img["phrase"]}
            for img in images
        ],
    }, indent=2)

    print(f"  Calling AI for {len(images)} image description(s)...")
    raw = call_api(SYSTEM_PROMPT, user_content)

    ai_map = {}
    if raw:
        try:
            data = json.loads(clean_json(raw))
            for item in data.get("images", []):
                iid = item.get("img_id", "")
                if iid:
                    ai_map[iid] = {
                        "style":       item.get("style", "2D colorful cartoon graphic"),
                        "description": item.get("description", "").strip(),
                    }
        except Exception as e:
            print(f"  Warning: AI parse error ({e}). Using fallbacks.")

    out = {**step1}
    for img in images:
        iid      = img["img_id"]
        desc     = ai_map.get(iid, {})
        img_desc = desc.get("description", "").strip()
        if not img_desc:
            print(f"  Fallback for {iid}")
            desc     = fallback_description(img["phrase"])
            img_desc = desc["description"]
        out[f"{iid}_description"] = img_desc
        out[f"{iid}_style"]       = desc.get("style", "2D colorful cartoon graphic")
        print(f"  {iid}: {img_desc[:80]}...")

    out_path = Path("assets/tmp") / f"{scene_id}_layout_37_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
