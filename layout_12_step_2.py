"""
Layout 12 Step 2 — AI Visual Descriptions
==========================================
Calls OpenRouter to generate visual descriptions for each image phrase.
Falls back to deterministic descriptions if API unavailable.

Input:  assets/tmp/{scene_id}_layout_12_step_1_tmp.json
Output: assets/tmp/{scene_id}_layout_12_step_2_tmp.json
"""

import json, os, sys
from pathlib import Path
import requests

DEFAULT_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not DEFAULT_API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openrouter_key.txt")
    if os.path.exists(_kp):
        with open(_kp, encoding="utf-8") as _f:
            DEFAULT_API_KEY = _f.read().strip()


def clean_json_response(content):
    content = content.strip()
    start = content.find("{")
    end   = content.rfind("}")
    if start != -1 and end != -1:
        content = content[start:end + 1]
    return content.strip()


def fallback_description(phrase):
    return f"A clean illustration of {phrase}, on a pure white background."


def call_api(system_prompt, user_payload, api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": json.dumps(user_payload, indent=2)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
    }
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=payload, timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"API Error {r.status_code}: {r.text}")
    return json.loads(clean_json_response(r.json()["choices"][0]["message"]["content"]))


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step1_file = Path("assets/tmp") / f"{scene_id}_layout_12_step_1_tmp.json"
    if not step1_file.exists():
        print(f"Error: {step1_file} not found. Run Step 1 first.")
        return 1

    step1 = json.loads(step1_file.read_text(encoding="utf-8"))
    images = step1.get("images", [])

    system_prompt_file = Path("layout_12_step_2.txt")
    if not system_prompt_file.exists():
        print("Error: layout_12_step_2.txt not found.")
        return 1
    system_prompt = system_prompt_file.read_text(encoding="utf-8")

    user_payload = {
        "scene_id":     scene_id,
        "scene_script": step1.get("script", ""),
        "images":       [{"image_id": img["image_id"], "phrase": img["phrase"]} for img in images],
    }

    api_key  = os.getenv("OPENROUTER_API_KEY", DEFAULT_API_KEY).strip()
    ai_data  = None
    if api_key:
        print("Calling OpenRouter for visual descriptions...")
        try:
            ai_data = call_api(system_prompt, user_payload, api_key)
        except (RuntimeError, json.JSONDecodeError, KeyError) as exc:
            print(f"  API error: {exc}. Using fallback descriptions.")
    else:
        print("No API key found — using deterministic fallbacks.")

    # Build image_id → description map from AI response
    ai_map = {}
    if isinstance(ai_data, dict):
        for item in (ai_data.get("images") or []):
            iid = str(item.get("image_id", "")).strip()
            if iid:
                ai_map[iid] = item

    # Assemble output
    images_out = []
    for img in images:
        iid  = img["image_id"]
        ai   = ai_map.get(iid, {})
        images_out.append({
            "image_id": iid,
            "phrase":   img["phrase"],
            "priority": img["priority"],
            "image": {
                "visual_description": ai.get("visual_description") or fallback_description(img["phrase"]),
                "is_realistic":       bool(ai.get("is_realistic", False)),
            },
        })

    out      = {"scene_id": scene_id, "images": images_out}
    out_file = Path("assets/tmp") / f"{scene_id}_layout_12_step_2_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_file}")


if __name__ == "__main__":
    sys.exit(main() or 0)
