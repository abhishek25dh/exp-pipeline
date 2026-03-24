

import json
import requests
import time # Added this so the script can wait and retry

import os
# --- YOUR CONFIGURATION ---
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL_ID = "openai/gpt-oss-120b:free" 
# --------------------------

def main():
    # 1. Read the Director Rules (System Prompt)
    try:
        with open("system.txt", "r", encoding="utf-8") as file:
            system_prompt = file.read()
    except FileNotFoundError:
        print("Error: system.txt not found. Create it and paste your rules inside.")
        return

    # 2. Read the actual scene you want to generate (User Prompt)
    try:
        with open("prompt.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            user_prompt = data.get("prompt", "")
    except FileNotFoundError:
        print("Error: prompt.json not found in this folder.")
        return

    # 3. Setup the API call to OpenRouter
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    # 4. Make the request with an AUTO-RETRY LOOP
    max_retries = 5
    for attempt in range(max_retries):
        print(f"Sending scene to {MODEL_ID}... (Attempt {attempt + 1}/{max_retries})")
        response = requests.post(url, headers=headers, json=payload)

        # If it succeeds, break out of the loop
        if response.status_code == 200:
            result_data = response.json()
            assistant_reply = result_data["choices"][0]["message"]["content"]
            
            # Clean up any markdown code blocks
            assistant_reply = assistant_reply.replace("```json", "").replace("```", "").strip()
            
            # Write the raw JSON string directly to the file
            with open("output.json", "w", encoding="utf-8") as file:
                file.write(assistant_reply)
                
            print("Success! Check output.json for the complete layout.")
            break # Stop trying, we got it!
            
        # If the server is busy (429 Rate Limit), wait and retry
        elif response.status_code == 429:
            print("Server is busy (Rate Limited). Waiting 5 seconds before trying again...")
            time.sleep(5)
            
        # If it's any other error, print it and stop
        else:
            print(f"API Error {response.status_code}: {response.text}")
            break

if __name__ == "__main__":
    main()