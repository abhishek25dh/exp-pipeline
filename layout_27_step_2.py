"""
Layout 27 Step 2 - Host Emotion Detection
==========================================
Calls AI to determine the host's emotion based on scene content.
No image descriptions needed (host is a static local asset; texts are rendered directly).

Emotion options: happy, sad, explaining, angry
-> mapped to: host_happy.png, host_sad.png, host_explaining.png, host_angry.png
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
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            API_KEY = _f.read().strip()
MODEL   = "deepseek/deepseek-chat"

SYSTEM_PROMPT = """You are an emotion analyst for explainer video scripts.

Read the scene voiceover and select the single most fitting emotion for the on-screen host character.

EMOTION DEFINITIONS:
- "explaining" -- neutral, informative, educational tone (default if unsure)
- "happy"      -- positive, excited, celebratory, inspiring
- "sad"        -- somber, regretful, cautionary, loss
- "angry"      -- urgent, frustrated, alarmed, strongly critical

OUTPUT: Valid JSON only. No extra text.
{"emotion": "<one of: explaining, happy, sad, angry>"}"""


def call_api(scene_text: str):
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
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps({"scene_voiceover": scene_text})},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }
        for attempt in range(1, 5):
            try:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=60,
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


EMOTION_TO_FILE = {
    "happy":     "host_happy.png",
    "sad":       "host_sad.png",
    "explaining": "host_explaining.png",
    "angry":     "host_angry.png",
}


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_27_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: {step1_path} not found. Run Step 1 first.")
        return 1

    step1      = json.loads(step1_path.read_text(encoding="utf-8"))
    scene_text = step1.get("scene_text", "")

    print(f"  Calling AI for host emotion...")
    raw = call_api(scene_text)

    emotion = "explaining"   # default
    if raw:
        try:
            raw = raw.strip()
            s, e = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[s:e + 1])
            detected = data.get("emotion", "explaining").strip().lower()
            if detected in EMOTION_TO_FILE:
                emotion = detected
            else:
                print(f"  Unknown emotion '{detected}', defaulting to 'explaining'.")
        except Exception as ex:
            print(f"  Warning: emotion parse error ({ex}). Defaulting to 'explaining'.")

    host_filename = EMOTION_TO_FILE[emotion]
    print(f"  Emotion: {emotion} -> {host_filename}")

    out = {**step1, "host_emotion": emotion, "host_filename": host_filename}
    out_path = Path("assets/tmp") / f"{scene_id}_layout_27_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
