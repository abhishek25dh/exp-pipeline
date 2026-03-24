import sys
import json
import os
import requests
import re
from pathlib import Path

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            API_KEY = _f.read().strip()
def clean_json_response(content):
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"
    
    prompt_file = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_file.exists():
        print(f"Error: {prompt_file} not found.")
        return 1
        
    with open(prompt_file, "r") as f:
        scene_data = json.load(f)
        
    with open("layout_11_step_1.txt", "r") as f:
        system_prompt = f.read()

    user_content = json.dumps(scene_data, indent=2)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.4
    }

    print("Calling OpenRouter API for Layout 11 Step 1 (Mind-Map Extraction)...")
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        content = response.json()['choices'][0]['message']['content']
        clean_content = clean_json_response(content)
        
        try:
            parsed = json.loads(clean_content)
            out_dir = Path("assets/tmp")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{scene_id}_layout_11_step_1_tmp.json"
            
            with open(out_file, "w") as f:
                json.dump(parsed, f, indent=2)
            print(f"Step 1 complete. Saved to {out_file}")
            
        except json.JSONDecodeError:
            print("Failed to parse JSON response. Raw output:")
            print(content)
    else:
        print(f"API Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
