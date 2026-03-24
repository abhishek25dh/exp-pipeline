import json
import os
import sys
from pathlib import Path

import requests


DEFAULT_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not DEFAULT_API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            DEFAULT_API_KEY = _f.read().strip()
def clean_json_response(content):
    content = content.strip()
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        content = content[start : end + 1]
    return content.strip()


def fallback_image_description(img_phrase, label_phrase):
    phrase = f"{img_phrase} {label_phrase}".strip()
    return f"A clean photo illustrating {phrase}, on a pure white background."


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
    step1_file = Path("assets/tmp") / f"{scene_id}_layout_13_step_1_tmp.json"

    if not prompt_file.exists():
        print(f"Error: {prompt_file} not found.")
        return 1
    if not step1_file.exists():
        print(f"Error: {step1_file} not found. Run Step 1 first.")
        return 1

    scene_data = json.loads(prompt_file.read_text(encoding="utf-8"))
    step1_data = json.loads(step1_file.read_text(encoding="utf-8"))

    steps = step1_data.get("steps", [])
    if len(steps) < 1:
        print("Error: Step 1 output is missing steps.")
        return 1

    with open("layout_13_step_2.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    user_payload = {
        "scene_id": scene_id,
        "scene_prompt": scene_data.get("prompt", ""),
        "steps": steps,
    }

    api_key = os.getenv("OPENROUTER_API_KEY", DEFAULT_API_KEY).strip()
    ai_data = None
    if api_key:
        print("Calling OpenRouter API for Layout 13 Step 2 (visual descriptions)...")
        try:
            ai_data = call_api(system_prompt, user_payload, api_key)
        except (RuntimeError, json.JSONDecodeError, KeyError) as exc:
            print(f"  API/parse error: {exc}")
            ai_data = None
    else:
        print("No OPENROUTER_API_KEY set; using deterministic fallbacks.")

    ai_map = {}
    if isinstance(ai_data, dict):
        items = ai_data.get("detailed_steps") or ai_data.get("steps") or []
        for item in items:
            sid = str(item.get("step_id", "")).strip()
            image = item.get("image", {})
            if sid:
                ai_map[sid] = image

    detailed_steps = []
    for step in steps:
        sid = step.get("step_id")
        img_phrase = step.get("img_phrase", "")
        label_phrase = step.get("label_phrase", "")
        image = ai_map.get(sid) or {
            "visual_description": fallback_image_description(img_phrase, label_phrase),
            "is_realistic": False,
        }
        detailed_steps.append(
            {
                "step_id": sid,
                "image": {
                    "visual_description": image.get("visual_description", ""),
                    "is_realistic": bool(image.get("is_realistic", False)),
                },
            }
        )

    out = {"detailed_steps": detailed_steps}

    out_file = Path("assets/tmp") / f"{scene_id}_layout_13_step_2_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 2 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
