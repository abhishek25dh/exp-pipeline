"""
Layout 19 Step 2 — AI Visual Descriptions for Pyramid Stack
============================================================
Calls OpenRouter to generate visual_description for each panel's image.
Falls back to deterministic descriptions if no API key or on error.
"""

import json
import os
import sys
from pathlib import Path

import requests


DEFAULT_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()


def clean_json_response(content):
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    # Extra safety: extract first JSON object
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        content = content[start:end + 1]
    return content.strip()


def fallback_image_description(img_phrase, txt_phrase):
    phrase = f"{img_phrase} {txt_phrase}".strip()
    return f"A clean illustration showing {phrase}, on a pure white background."


def call_api(system_prompt, user_payload, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, indent=2)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"API Error {response.status_code}: {response.text}")
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(clean_json_response(content))


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_file = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    step1_file = Path("assets/tmp") / f"{scene_id}_layout_19_step_1_tmp.json"

    if not prompt_file.exists():
        print(f"Error: {prompt_file} not found.")
        return 1
    if not step1_file.exists():
        print(f"Error: {step1_file} not found. Run Step 1 first.")
        return 1

    scene_data = json.loads(prompt_file.read_text(encoding="utf-8"))
    step1_data = json.loads(step1_file.read_text(encoding="utf-8"))

    panels = step1_data.get("panels", [])
    if len(panels) < 3:
        print("Error: Step 1 output needs at least 3 panels.")
        return 1

    with open("layout_19_step_2.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    user_payload = {
        "scene_id": scene_id,
        "scene_prompt": scene_data.get("prompt", ""),
        "main_title": step1_data.get("main_title", ""),
        "panels": panels,
    }

    # Try reading API key from env, then from file
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        key_file = Path("openrouter_key.txt")
        if key_file.exists():
            api_key = key_file.read_text(encoding="utf-8").strip()

    ai_data = None
    if api_key:
        print("Calling OpenRouter API for Layout 19 Step 2 (visual descriptions)...")
        try:
            ai_data = call_api(system_prompt, user_payload, api_key)
        except (RuntimeError, json.JSONDecodeError, KeyError) as exc:
            print(f"  API/parse error: {exc}")
            ai_data = None
    else:
        print("No API key found; using deterministic fallbacks.")

    ai_map = {}
    if isinstance(ai_data, dict):
        items = ai_data.get("detailed_panels") or ai_data.get("panels") or []
        for item in items:
            pid = str(item.get("panel_id", "")).strip()
            image = item.get("image", {})
            if pid:
                ai_map[pid] = image

    detailed_panels = []
    for panel in panels:
        pid = panel.get("panel_id")
        img_phrase = panel.get("img_phrase", "")
        txt_phrase = panel.get("txt_phrase", "")
        image = ai_map.get(pid) or {
            "visual_description": fallback_image_description(img_phrase, txt_phrase),
            "is_realistic": False,
        }
        detailed_panels.append({
            "panel_id": pid,
            "image": {
                "visual_description": image.get("visual_description", ""),
                "is_realistic": bool(image.get("is_realistic", False)),
            },
        })

    out = {
        "main_title": step1_data.get("main_title", ""),
        "detailed_panels": detailed_panels,
    }

    out_file = Path("assets/tmp") / f"{scene_id}_layout_19_step_2_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 2 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
