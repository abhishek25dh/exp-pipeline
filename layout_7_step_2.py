import json
import sys
import time
from pathlib import Path

import requests

import os
API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            API_KEY = _f.read().strip()
MODEL = "deepseek/deepseek-chat"


def clean_json_response(content: str) -> str:
    content = (content or "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        return content[start : end + 1].strip()
    return content


def phrase_from_span(tokens, span):
    s, e = span
    return " ".join(tokens[s:e]).strip()


def split_segment(start: int, end: int, slots: int):
    if slots == 0:
        return []
    length = end - start
    sizes = [length // slots] * slots
    for i in range(length % slots):
        sizes[i] += 1
    spans = []
    cur = start
    for sz in sizes:
        nxt = cur + sz
        spans.append([cur, nxt])
        cur = nxt
    return spans


def generate_allocations(left_len: int, right_len: int):
    allocations = []
    for left_slots in range(5):
        right_slots = 4 - left_slots
        if left_len > 0 and left_slots == 0:
            continue
        if right_len > 0 and right_slots == 0:
            continue
        if left_slots > 0 and left_len == 0:
            continue
        if right_slots > 0 and right_len == 0:
            continue
        allocations.append((left_slots, right_slots))

    # Prefer weighted allocation close to token ratio, then keep others.
    if left_len + right_len > 0:
        ratio_target = 4 * (left_len / (left_len + right_len))
        allocations.sort(key=lambda lr: abs(lr[0] - ratio_target))
    return allocations


def build_partition_candidates(tokens, host_span):
    hs, he = host_span
    n = len(tokens)
    left_len = hs
    right_len = n - he
    allocations = generate_allocations(left_len, right_len)
    if not allocations:
        raise ValueError("Cannot allocate 4 image spans without overlap.")

    candidates = []
    seen = set()
    pid = 1
    for left_slots, right_slots in allocations:
        spans = []
        spans.extend(split_segment(0, hs, left_slots))
        spans.extend(split_segment(he, n, right_slots))
        if len(spans) != 4:
            continue
        key = tuple((a, b) for a, b in spans)
        if key in seen:
            continue
        seen.add(key)
        phrases = [phrase_from_span(tokens, sp) for sp in spans]
        candidates.append(
            {
                "partition_id": f"P{pid}",
                "spans": spans,
                "phrases": phrases,
            }
        )
        pid += 1

    if not candidates:
        raise ValueError("No valid 4-span candidate generated.")

    # Keep only the most equal splits so AI can choose semantics
    # without violating the "equally divide remaining phrases" goal.
    def spread(c):
        lens = [b - a for a, b in c["spans"]]
        return max(lens) - min(lens)

    min_spread = min(spread(c) for c in candidates)
    equalized = [c for c in candidates if spread(c) == min_spread]
    return equalized


def default_description(phrase: str) -> str:
    if not phrase:
        return "A clean 2D colorful cartoon graphic on a pure white background. No text, no letters, no numbers, no watermarks."
    p = phrase.strip(".,!? ")[:60]
    return (
        f"A 2D colorful cartoon graphic of objects related to '{p}' on a pure white background. "
        "No text, no letters, no numbers, no watermarks."
    )


def call_api(system_prompt: str, user_payload: dict, retries: int = 3):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
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
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            return json.loads(clean_json_response(raw))
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise last_exc


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"
    step1_file = Path("assets/tmp") / f"{scene_id}_layout_7_step_1_tmp.json"
    if not step1_file.exists():
        print(f"Error: {step1_file} not found. Run Step 1 first.")
        return 1

    step1 = json.loads(step1_file.read_text(encoding="utf-8"))
    tokens = step1.get("script_tokens", [])
    host_span = step1.get("host_span", [0, 0])
    host_phrase = step1.get("host_phrase", "")

    if not (isinstance(host_span, list) and len(host_span) == 2):
        print("Error: invalid host_span in Step 1 output.")
        return 1
    hs, he = host_span
    if not (0 <= hs < he <= len(tokens)):
        print("Error: host_span out of bounds.")
        return 1
    if len(tokens) - (he - hs) < 4:
        # Not enough non-host tokens — fall back to splitting all tokens into 4 image phrases
        print("Warning: not enough non-host tokens; using all tokens for image phrases.")
        host_span = [len(tokens), len(tokens)]
        hs, he = host_span

    candidates = build_partition_candidates(tokens, host_span)
    system_prompt = Path("layout_7_step_2.txt").read_text(encoding="utf-8")
    user_payload = {
        "scene_id": scene_id,
        "script_tokens": tokens,
        "host_span": host_span,
        "host_phrase": host_phrase,
        "partition_candidates": candidates,
    }

    parsed = {}
    try:
        print("Calling OpenRouter API for Layout 7 Step 2 (Partition + Visuals)...")
        parsed = call_api(system_prompt, user_payload)
    except Exception as exc:
        print(f"Step 2 API warning: {exc}")
        print("Falling back to deterministic defaults.")

    chosen_id = str(parsed.get("partition_id", "")).strip()
    chosen = next((c for c in candidates if c["partition_id"] == chosen_id), candidates[0])

    image_meta = parsed.get("images", [])
    if not isinstance(image_meta, list):
        image_meta = []
    image_meta = image_meta[:4]
    while len(image_meta) < 4:
        image_meta.append({})

    merged_images = []
    for i in range(4):
        phrase = chosen["phrases"][i]
        meta = image_meta[i] if isinstance(image_meta[i], dict) else {}
        desc = str(meta.get("visual_description", "")).strip() or default_description(phrase)
        is_realistic = bool(meta.get("is_realistic", True))
        merged_images.append(
            {
                "span": chosen["spans"][i],
                "phrase": phrase,
                "visual_description": desc,
                "is_realistic": is_realistic,
            }
        )

    out = {
        "script_tokens": tokens,
        "host_span": host_span,
        "partition_id": chosen["partition_id"],
        "detailed_groups": [
            {"group_id": "group_1", "images": merged_images[:2]},
            {"group_id": "group_2", "images": merged_images[2:]},
        ],
    }

    out_file = Path("assets/tmp") / f"{scene_id}_layout_7_step_2_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 2 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
