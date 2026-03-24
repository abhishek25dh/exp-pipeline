import json
import os
import re
import sys
import time
from pathlib import Path

import requests

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openrouter_key.txt")
    if os.path.exists(_kp):
        with open(_kp, encoding="utf-8") as _f:
            API_KEY = _f.read().strip()

AI_MODEL = "deepseek/deepseek-chat"

AI_SYSTEM_PROMPT = """You are a visual art director for explainer videos.

Write a precise image generation prompt for each scene image.

RULES:
1. Describe the ACTUAL VISUAL -- objects, people, colors, setting, composition you would literally see.
2. Never use "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the phrase spoken when the image appears AND the full scene voiceover for context.
4. Pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum.
7. Choose style per image: "2D colorful cartoon graphic" or "realistic photo".
8. Output valid JSON only. No extra text, no markdown fences.

OUTPUT FORMAT:
{"images": [{"img_id": "phrase_1", "style": "2D colorful cartoon graphic", "description": "..."}]}"""


def _call_ai_descriptions(scene_text: str, phrases: list) -> dict:
    """Call OpenRouter and return {phrase_id: description} map. Returns {} on failure."""
    if not API_KEY:
        return {}
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({
                "scene_voiceover": scene_text,
                "images_needed": [
                    {"img_id": p["phrase_id"], "phrase_spoken_when_image_appears": p["phrase"]}
                    for p in phrases
                ],
            }, indent=2)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.6,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    for attempt in range(1, 4):
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=90,
            )
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"].strip()
                s, e = raw.find("{"), raw.rfind("}")
                data = json.loads(raw[s:e + 1]) if s != -1 else {}
                return {item["img_id"]: item.get("description", "").strip()
                        for item in data.get("images", []) if item.get("img_id")}
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 8))
                continue
        except Exception:
            time.sleep(min(2 ** attempt, 8))
    return {}

BAD_END_TOKENS = {"you're", "we're", "they're", "i'm"}
MIN_PHRASE_TOKENS = 3


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def phrase_from_span(tokens, span):
    s, e = span
    return " ".join(tokens[s:e]).strip()


def normalize_token(token: str) -> str:
    return re.sub(r"^[^\w']+|[^\w']+$", "", (token or "").lower())


def segment_sizes(length: int, slots: int):
    if slots <= 0:
        return []
    base = length // slots
    rem = length % slots
    out = []
    for i in range(slots):
        out.append(base + (1 if i < rem else 0))
    return out


def choose_phrase_count(remaining_tokens: int) -> int:
    if remaining_tokens <= 0:
        return 0

    # Cap phrase count so each phrase can stay >= MIN_PHRASE_TOKENS when possible.
    max_phrases = max(1, remaining_tokens // MIN_PHRASE_TOKENS)

    # Aim for ~4 tokens per phrase, then clamp.
    target = round(remaining_tokens / 4.0)
    target = max(1, min(target, max_phrases, 10))
    return int(target)


def allocate_slots(segment_lengths, total_slots: int):
    slots = [0] * len(segment_lengths)
    non_empty = [i for i, ln in enumerate(segment_lengths) if ln > 0]
    if total_slots <= 0 or not non_empty:
        return slots

    max_slots = []
    for ln in segment_lengths:
        if ln <= 0:
            max_slots.append(0)
        else:
            max_slots.append(max(1, ln // MIN_PHRASE_TOKENS))

    if total_slots <= len(non_empty):
        ranked = sorted(non_empty, key=lambda i: segment_lengths[i], reverse=True)
        for i in ranked[:total_slots]:
            slots[i] = 1
        return slots

    for i in non_empty:
        slots[i] = 1
    assigned = len(non_empty)

    while assigned < total_slots:
        candidates = [i for i in non_empty if slots[i] < max_slots[i]]
        if not candidates:
            break
        best = max(candidates, key=lambda i: segment_lengths[i] / (slots[i] + 1))
        slots[best] += 1
        assigned += 1

    return slots


def split_segments_into_spans(segments, slots_per_segment):
    spans = []
    for idx, (start, end) in enumerate(segments):
        slots = slots_per_segment[idx]
        if slots <= 0:
            continue
        sizes = segment_sizes(end - start, slots)
        cur = start
        for size in sizes:
            nxt = cur + size
            spans.append([cur, nxt])
            cur = nxt
    return spans


def dedupe_adjacent_spans(tokens, spans):
    if not spans:
        return spans
    for _ in range(4):
        seen = set()
        changed = False
        for i in range(len(spans)):
            s, e = spans[i]
            key = normalize(phrase_from_span(tokens, [s, e]))
            if not key or key not in seen:
                seen.add(key)
                continue

            # Try taking one token from next span if they are adjacent.
            if i + 1 < len(spans):
                ns, ne = spans[i + 1]
                if e == ns and (ne - ns) > 1:
                    spans[i][1] += 1
                    spans[i + 1][0] += 1
                    changed = True
                    key2 = normalize(phrase_from_span(tokens, spans[i]))
                    seen.add(key2)
                    continue

            # Otherwise try taking one token from previous adjacent span.
            if i - 1 >= 0:
                ps, pe = spans[i - 1]
                if ps < pe and pe == s and (pe - ps) > 1:
                    spans[i][0] -= 1
                    spans[i - 1][1] -= 1
                    changed = True
                    key2 = normalize(phrase_from_span(tokens, spans[i]))
                    seen.add(key2)
                    continue

            seen.add(key)
        if not changed:
            break
    return spans


def smooth_dangling_end_tokens(tokens, spans):
    """
    Avoid phrases like "very important. You're" by shifting a trailing contraction
    token into the next span when spans are adjacent.
    """
    if not spans:
        return spans

    for _ in range(4):
        changed = False
        for i in range(len(spans) - 1):
            s, e = spans[i]
            ns, ne = spans[i + 1]
            if e != ns:
                continue
            if (e - s) < 2:
                continue
            end_norm = normalize_token(tokens[e - 1]) if (e - 1) < len(tokens) else ""
            if end_norm and end_norm in BAD_END_TOKENS and (ne - ns) >= 1:
                spans[i][1] -= 1
                spans[i + 1][0] -= 1
                changed = True
        if not changed:
            break
    return spans


def _fallback_description(phrase: str) -> str:
    p = (phrase or "").strip()
    if not p:
        return "Clean conceptual visual on a pure white background. No text, no letters, no numbers, no watermarks."
    return (f"On a pure white background, a 2D colorful cartoon graphic related to '{p[:60]}'. "
            f"Bold shapes, vibrant colors, clean composition. No text, no letters, no numbers, no watermarks.")


def build_remaining_segments(total_tokens: int, anchor_spans):
    sorted_spans = sorted(anchor_spans, key=lambda x: x[0])
    merged = []
    for s, e in sorted_spans:
        s = max(0, int(s))
        e = min(total_tokens, int(e))
        if s >= e:
            continue
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)

    segments = []
    cur = 0
    for s, e in merged:
        if cur < s:
            segments.append([cur, s])
        cur = max(cur, e)
    if cur < total_tokens:
        segments.append([cur, total_tokens])
    return segments


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_path = Path(f"assets/scene_prompts/{scene_id}_prompt.json")
    step1_path = Path(f"assets/tmp/{scene_id}_layout_1_step_1_tmp.json")
    if not prompt_path.exists() or not step1_path.exists():
        print(f"Error: Missing input files for {scene_id}.")
        return 1

    scene_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    step1 = json.loads(step1_path.read_text(encoding="utf-8"))

    script_text = strip_scene_prefix(scene_data.get("prompt", ""))
    tokens = step1.get("script_tokens") or script_text.split()
    if not isinstance(tokens, list) or not tokens:
        print(f"Error: Invalid script tokens for {scene_id}.")
        return 1

    anchor_spans_dict = step1.get("anchor_spans", {})
    text1_span = anchor_spans_dict.get("text_1", [0, 0])
    text2_span = anchor_spans_dict.get("text_2", [0, 0])
    anchor_spans = [text1_span, text2_span]

    remaining_segments = build_remaining_segments(len(tokens), anchor_spans)
    remaining_count = sum(max(0, e - s) for s, e in remaining_segments)
    if remaining_count <= 0:
        # All tokens consumed by text anchors — write empty image list and continue
        print(f"  No remaining tokens for images in {scene_id} — text-only output.")
        out = {
            "scene_id": scene_id,
            "script_tokens": tokens,
            "anchor_spans": {"text_1": text1_span, "text_2": text2_span},
            "phrases": [],
        }
        out_path = Path(f"assets/tmp/{scene_id}_layout_1_step_2_tmp.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Step 2 complete. Saved to {out_path}")
        return 0

    phrase_count = choose_phrase_count(remaining_count)
    segment_lengths = [e - s for s, e in remaining_segments]
    slots_per_segment = allocate_slots(segment_lengths, phrase_count)
    spans = split_segments_into_spans(remaining_segments, slots_per_segment)
    spans = [sp for sp in spans if sp[1] > sp[0]]
    spans = dedupe_adjacent_spans(tokens, spans)
    spans = smooth_dangling_end_tokens(tokens, spans)

    used = set()
    phrases = []
    for i, span in enumerate(spans, start=1):
        phrase = phrase_from_span(tokens, span)
        key = normalize(phrase)
        if not phrase or not key:
            continue
        if key in used:
            continue
        used.add(key)
        phrases.append(
            {
                "phrase_id": f"phrase_{i}",
                "span": span,
                "phrase": phrase,
                "visual_description": "",   # filled by AI below
                "type": "image",
                "reason": "Deterministic micro-phrase from non-anchor script span.",
            }
        )

    if not phrases:
        print(f"Error: Failed to create phrases for {scene_id}.")
        return 1

    # --- AI image descriptions (OpenRouter) ---
    print(f"  Calling AI for {len(phrases)} image description(s)...")
    ai_descs = _call_ai_descriptions(script_text, phrases)
    for p in phrases:
        pid = p["phrase_id"]
        desc = ai_descs.get(pid, "").strip()
        if not desc:
            print(f"  Fallback description for {pid}")
            desc = _fallback_description(p["phrase"])
        p["visual_description"] = desc

    out = {
        "scene_id": scene_id,
        "script_tokens": tokens,
        "anchor_spans": {
            "text_1": text1_span,
            "text_2": text2_span,
        },
        "phrases": phrases,
    }

    out_path = Path(f"assets/tmp/{scene_id}_layout_1_step_2_tmp.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 2 complete. Saved to {out_path}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
