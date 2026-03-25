import sys
import os
import json
import requests
import time

# --- YOUR CONFIGURATION ---
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL_ID = "deepseek/deepseek-v3.2" 
# --------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_prompts.py <scene_number>")
        sys.exit(1)
    if not API_KEY:
        print("Error: OPENROUTER_API_KEY is not set.")
        sys.exit(1)
        
    scene_num = sys.argv[1]
    
    system_prompt_path = "image_system_prompt.txt"
    input_file = os.path.join("assets", "directorscript", f"scene_{scene_num}_director.json")
    output_dir = os.path.join("assets", "image_prompts")
    output_file = os.path.join(output_dir, f"scene_{scene_num}_image_prompts.json")

    os.makedirs(output_dir, exist_ok=True)

    # 1. Read System Rules
    try:
        with open(system_prompt_path, "r", encoding="utf-8") as file:
            system_prompt = file.read()
    except FileNotFoundError:
        print(f"Error: '{system_prompt_path}' not found.")
        sys.exit(1)

    # 2. Read Director Script
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            director_json_raw = file.read()
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    # 3. Setup API Call
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Convert this Director Script to the Image Prompt format:\n\n{director_json_raw}"}
        ],
        "response_format": { "type": "json_object" } # Tells DeepSeek to output JSON
    }

    # 4. Execution with Retry
    max_retries = 5
    success = False
    for attempt in range(max_retries):
        print(f"Converting Scene {scene_num} using {MODEL_ID}... (Attempt {attempt + 1})")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)

            if response.status_code == 200:
                result_data = response.json()
                assistant_reply = result_data["choices"][0]["message"]["content"]
                
                # Clean markdown if present
                assistant_reply = assistant_reply.replace("```json", "").replace("```", "").strip()
                
                # Validate and Save
                try:
                    json_data = json.loads(assistant_reply)
                    with open(output_file, "w", encoding="utf-8") as file:
                        json.dump(json_data, file, indent=2) # Pretty-print the output
                    print(f"DONE! Saved to: {output_file}")
                    success = True
                    break
                    
                except json.JSONDecodeError:
                    print("Error: Model returned invalid JSON.")
                    break
                    
            elif response.status_code == 429:
                print("Rate limited. Waiting 10s...")
                time.sleep(10)
            else:
                print(f"API Error {response.status_code}: {response.text}")
                break
                
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
