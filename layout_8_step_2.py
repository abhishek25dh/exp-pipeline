import json
import os
import sys
import time
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
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


import re as _re

def _strip_scene_prefix(text):
    return _re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=_re.I).strip()

def _allot_phrases(tokens, n_slots):
    n = len(tokens)
    if n == 0:
        return [None] * n_slots
    results = []
    t = 0
    for i in range(n_slots):
        remaining_tokens = n - t
        remaining_slots  = n_slots - i
        if remaining_tokens <= 0:
            results.append(None)
        else:
            give = max(1, remaining_tokens // remaining_slots)
            if i == n_slots - 1:
                give = remaining_tokens
            results.append(" ".join(tokens[t: t + give]))
            t += give
    return results

def _inject_allotted_phrases(steps, scene_prompt):
    """Fill any empty img_phrase/txt_phrase in steps using allotted phrases
    computed directly from the scene text, so step_2 AI always has real context."""
    tokens = _strip_scene_prefix(scene_prompt).split()
    n_slots = 1 + len(steps) * 2   # slot 0 = title, then img+txt per step
    n_active = min(n_slots, max(1, len(tokens) // 2))
    all_phrases = _allot_phrases(tokens, n_active)
    all_phrases += [None] * (n_slots - n_active)
    step_phrases = all_phrases[1:]  # drop title slot
    for i, step in enumerate(steps):
        if not step.get("img_phrase"):
            step["img_phrase"] = step_phrases[i * 2] or ""
        if not step.get("txt_phrase"):
            step["txt_phrase"] = step_phrases[i * 2 + 1] or ""


def call_api(system_prompt, user_payload, api_key, retries=3):
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
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=90,
            )
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 8))
                continue
            if response.status_code != 200:
                raise RuntimeError(f"API Error {response.status_code}: {response.text}")
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(clean_json_response(content))
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise last_exc


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_file = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    step1_file = Path("assets/tmp") / f"{scene_id}_layout_8_step_1_tmp.json"

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

    scene_prompt = scene_data.get("prompt", "")

    # Ensure every step has real phrases — fill gaps from allotment so the AI
    # always receives meaningful context regardless of what step_1 produced.
    _inject_allotted_phrases(steps, scene_prompt)

    with open("layout_8_step_2.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    user_payload = {
        "scene_id": scene_id,
        "scene_prompt": scene_prompt,
        "main_title": step1_data.get("main_title", ""),
        "steps": steps,
    }

    api_key = os.getenv("OPENROUTER_API_KEY", DEFAULT_API_KEY).strip()
    if not api_key:
        print("Error: OPENROUTER_API_KEY is not set.")
        return 1

    print("Calling OpenRouter API for Layout 8 Step 2 (visual descriptions)...")
    ai_data = call_api(system_prompt, user_payload, api_key)

    ai_map = {}
    if isinstance(ai_data, dict):
        items = ai_data.get("detailed_steps") or ai_data.get("steps") or []
        for item in items:
            sid = str(item.get("step_id", "")).strip()
            image = item.get("image", {})
            if sid and image.get("visual_description"):
                ai_map[sid] = image

    detailed_steps = []
    for step in steps:
        sid = step.get("step_id")
        if sid not in ai_map:
            raise RuntimeError(f"Step 2 AI did not return a description for step '{sid}'")
        image = ai_map[sid]
        detailed_steps.append(
            {
                "step_id": sid,
                "image": {
                    "visual_description": image.get("visual_description", ""),
                    "is_realistic": bool(image.get("is_realistic", False)),
                },
            }
        )

    out = {
        "main_title": step1_data.get("main_title", ""),
        "detailed_steps": detailed_steps,
    }

    out_file = Path("assets/tmp") / f"{scene_id}_layout_8_step_2_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 2 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
