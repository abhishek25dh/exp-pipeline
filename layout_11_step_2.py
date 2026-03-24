import sys
import json
import requests
from pathlib import Path

import os
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            API_KEY = _f.read().strip()
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "from", "by", "it", "its", "is", "was", "are", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "not", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "up", "out", "as", "so", "if", "then", "than",
    "also", "just", "about", "into", "over", "after", "before",
    "no", "now", "when", "what", "where", "who", "how", "never",
    "always", "ever", "still", "even", "yet", "own", "maybe", "like",
    # contracted forms (apostrophe stripped by _norm)
    "youre", "dont", "cant", "wont", "isnt", "wasnt", "didnt", "hasnt",
    "havent", "shouldnt", "wouldnt", "couldnt", "theyre", "thats",
    "youve", "ive", "weve", "arent", "doesnt", "hadnt", "werent",
    "im", "hed", "shed", "wed", "theyd", "youll", "hell", "shell",
    "well", "theyll",
}


def content_words(phrase):
    def _norm(w):
        return w.strip("'\".,!?").replace("\u2019", "").replace("'", "")
    return set(_norm(w) for w in phrase.lower().split()
               if _norm(w) not in STOP_WORDS and len(_norm(w)) > 1)


def clean_json_response(content):
    content = content.strip()
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1:
        content = content[start:end+1]
    return content.strip()


def validate_phrases(parsed, core_title):
    errors = []
    nodes = parsed.get("orbiting_images", [])

    if len(nodes) < 4 or len(nodes) > 5:
        errors.append(f"Expected 4 or 5 nodes, got {len(nodes)}")
        return errors

    phrases = []
    labels = []

    if core_title:
        phrases.append(core_title)
        labels.append("core_concept")

    for nd in nodes:
        nid = nd.get("node_id", "?")
        for key in ("img_phrase", "txt_phrase"):
            val = nd.get(key, "").strip()
            if not val:
                errors.append(f"{nid}.{key} is empty")
            else:
                phrases.append(val)
                labels.append(f"{nid}.{key}")

    for i in range(len(phrases)):
        pi_lower = phrases[i].lower()
        cw_i = content_words(phrases[i])
        for j in range(i + 1, len(phrases)):
            pj_lower = phrases[j].lower()
            if pi_lower == pj_lower:
                errors.append(f"EXACT DUPLICATE: [{labels[i]}]='{phrases[i]}' == [{labels[j]}]='{phrases[j]}'")
                continue
            if pi_lower in pj_lower or pj_lower in pi_lower:
                errors.append(f"SUBSTRING: [{labels[i]}]='{phrases[i]}' inside [{labels[j]}]='{phrases[j]}'")
                continue
            cw_j = content_words(phrases[j])
            overlap = cw_i & cw_j
            if overlap:
                errors.append(
                    f"CONTENT OVERLAP [{labels[i]}]='{phrases[i]}' & [{labels[j]}]='{phrases[j]}' "
                    f"(shared: {overlap})"
                )

    return errors


def call_api(headers, payload):
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=payload, timeout=60
    )
    if response.status_code != 200:
        raise RuntimeError(f"API Error {response.status_code}: {response.text}")
    content = response.json()['choices'][0]['message']['content']
    return json.loads(clean_json_response(content))


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_file = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    step1_file = Path("assets/tmp") / f"{scene_id}_layout_11_step_1_tmp.json"

    if not prompt_file.exists():
        print(f"Error: {prompt_file} not found.")
        return 1
    if not step1_file.exists():
        print(f"Error: {step1_file} not found. Run Step 1 first.")
        return 1

    with open(prompt_file, "r") as f:
        scene_data = json.load(f)
    with open(step1_file, "r") as f:
        step1_data = json.load(f)

    core_title = step1_data.get("core_concept", {}).get("title", "").strip()

    with open("layout_11_step_2.txt", "r") as f:
        system_prompt = f.read()

    combined_data = {"scene_prompt": scene_data, "mind_map_data": step1_data}

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    base_payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(combined_data, indent=2)}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.4
    }

    MAX_RETRIES = 4
    parsed = None
    for attempt in range(1, MAX_RETRIES + 1):
        payload = dict(base_payload)
        payload["temperature"] = 0.4 + (attempt - 1) * 0.15

        print(f"Calling OpenRouter API for Layout 11 Step 2 (attempt {attempt}/{MAX_RETRIES})...")
        try:
            parsed = call_api(headers, payload)
        except (RuntimeError, json.JSONDecodeError, KeyError) as e:
            print(f"  API/parse error: {e}")
            if attempt == MAX_RETRIES:
                print("All retries exhausted.")
                return
            continue

        errors = validate_phrases(parsed, core_title)
        if not errors:
            print(f"  Validation passed on attempt {attempt}.")
            break
        else:
            print(f"  Validation FAILED (attempt {attempt}):")
            for err in errors:
                print(f"    - {err}")
            if attempt == MAX_RETRIES:
                print("All retries exhausted. Saving best result anyway.")
                break
            print("  Retrying with higher temperature...")

    out_file = Path("assets/tmp") / f"{scene_id}_layout_11_step_2_tmp.json"
    with open(out_file, "w") as f:
        json.dump(parsed, f, indent=2)
    print(f"Step 2 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
