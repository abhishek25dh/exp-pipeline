"""
Layout 2 Step 2 — AI Anchor Selection + Deterministic Image Spans + AI Descriptions
=====================================================================================
AI role (limited):
  1. Pick ONE anchor candidate ID from the pre-validated list.
  2. Pick text_type (text_highlighted / text_red / text_black).

Deterministic role:
  - Split remaining tokens (after anchor) into N image spans (no gaps, no overlaps).
  - Pair consecutive image spans into visual groups (2 images per group max).

AI role (image descriptions):
  - Call OpenRouter once for all image descriptions.
"""

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

MODEL = "deepseek/deepseek-chat"

TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]


def ends_sentence(tok):
    return bool(tok) and tok.rstrip()[-1] in ".!?"

ANCHOR_SYSTEM_PROMPT = """You are choosing the best short text anchor for a visual explainer scene.

The anchor is the single most impactful 1-4 word phrase from the script.

Given pre-validated candidates, return ONLY valid JSON:
{"candidate_id": "C3", "text_type": "text_red"}

Rules:
- candidate_id must be exactly one of the provided IDs.
- text_type: text_red=urgent/negative, text_highlighted=positive/insight, text_black=neutral.
- No other keys. No markdown."""

DESC_SYSTEM_PROMPT = """You are a visual art director for explainer videos.

Write a precise image generation prompt for each scene image.

RULES:
1. Describe the ACTUAL VISUAL -- objects, people, colors, setting, composition literally seen.
2. Never use "depicting", "representing", "showing", "illustrating", "symbolizing".
3. Use the phrase spoken when the image appears AND the full scene voiceover for context.
4. Pure white background.
5. End every description with: No text, no letters, no numbers, no watermarks.
6. 2-3 sentences maximum.
7. Choose style: "2D colorful cartoon graphic" or "realistic photo".
8. Output valid JSON only. No markdown.

OUTPUT FORMAT:
{"images": [{"img_id": "img_0", "style": "2D colorful cartoon graphic", "description": "..."}]}"""


def _api_call(system, user):
    if not API_KEY:
        return None
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }
    for attempt in range(1, 4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers=headers, json=payload, timeout=90)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"].strip()
                s, e = raw.find("{"), raw.rfind("}")
                return raw[s:e + 1] if s != -1 else raw
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 8))
        except Exception:
            time.sleep(min(2 ** attempt, 8))
    return None


def snap_to_sentence_end(tokens, span):
    """Rule 6: ensure anchor phrase ends at a sentence boundary.
    Searches forward up to +5 tokens, then backward if needed.
    Priority: P1 (anchor) is assigned first and must end cleanly."""
    s, e = span
    n = len(tokens)
    # Already clean
    if ends_sentence(tokens[e - 1]):
        return [s, e]
    # Forward search (up to +5)
    for i in range(e, min(e + 5, n)):
        if ends_sentence(tokens[i]):
            return [s, i + 1]
    # Backward search (from e-1 down to s+1)
    for i in range(e - 2, s, -1):
        if ends_sentence(tokens[i]):
            return [s, i + 1]
    # No sentence boundary found — keep original span
    return [s, e]


def build_image_spans(tokens, anchor_span):
    """Split tokens NOT in anchor_span into N image spans — no gaps, no overlaps."""
    a_s, a_e = anchor_span
    n = len(tokens)
    segments = []
    if a_s > 0:
        segments.append([0, a_s])
    if a_e < n:
        segments.append([a_e, n])

    remaining = sum(e - s for s, e in segments)
    if remaining == 0:
        return []

    n_img = max(2, min(8, max(1, remaining // 3)))

    spans = []
    total_alloc = 0
    for seg_idx, (ss, se) in enumerate(segments):
        seg_len = se - ss
        is_last_seg = seg_idx == len(segments) - 1
        if is_last_seg:
            seg_count = max(1, n_img - total_alloc)
        else:
            seg_count = max(1, round(n_img * seg_len / remaining))
        seg_count = min(seg_count, seg_len)

        size = seg_len // seg_count
        pos = ss
        for i in range(seg_count):
            end = (pos + size) if i < seg_count - 1 else se
            end = min(end, se)
            if pos < end:
                spans.append([pos, end])
            pos = end
        total_alloc += seg_count

    return spans


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_2_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: missing {step1_path}")
        return 1

    step1 = json.loads(step1_path.read_text(encoding="utf-8"))
    tokens = step1["tokens"]
    candidates = step1["candidates"]
    scene_text = step1["scene_text"]
    default_id = step1["default_candidate_id"]

    # --- AI: select anchor ---
    print("  Calling AI for anchor selection...")
    anchor_raw = _api_call(
        ANCHOR_SYSTEM_PROMPT,
        json.dumps({
            "script": scene_text,
            "candidates": [{"id": c["id"], "phrase": c["phrase"]} for c in candidates],
        }, indent=2),
    )

    selected_id = default_id
    text_type = "text_red"
    if anchor_raw:
        try:
            sel = json.loads(anchor_raw)
            cid = sel.get("candidate_id", "")
            if any(c["id"] == cid for c in candidates):
                selected_id = cid
            tt = sel.get("text_type", "")
            if tt in TEXT_TYPES:
                text_type = tt
        except Exception:
            pass

    anchor = next(c for c in candidates if c["id"] == selected_id)

    # --- P1 PRIORITY: snap anchor to sentence boundary (Rule 6) ---
    # P1 (center text) is assigned its phrase FIRST.
    # Rule 6: anchor phrase must end at a sentence boundary.
    snapped_span = snap_to_sentence_end(tokens, anchor["span"])
    if snapped_span != anchor["span"]:
        old_phrase = anchor["phrase"]
        anchor = {**anchor, "span": snapped_span,
                  "phrase": " ".join(tokens[snapped_span[0]:snapped_span[1]])}
        print(f"  Rule 6 snap: '{old_phrase}' -> '{anchor['phrase']}'")
    rule6_ok = ends_sentence(anchor["phrase"].split()[-1]) if anchor["phrase"].split() else False
    print(f"  P1 anchor: '{anchor['phrase']}'  type={text_type}  {'(Rule 6 OK)' if rule6_ok else '(Rule 6 WARN)'}")

    # --- P2-PN PRIORITY: images get remaining tokens after P1 is assigned ---
    img_spans = build_image_spans(tokens, anchor["span"])
    if not img_spans:
        # Fallback: anchor took all tokens, use full script for one image
        img_spans = [[0, len(tokens)]]

    images = []
    for idx, span in enumerate(img_spans):
        phrase = " ".join(tokens[span[0]:span[1]])
        group_num = (idx // 2) + 1
        images.append({
            "img_id": f"img_{idx}",
            "element_id": f"image_group_{group_num}_{idx}",
            "group_id": f"group_{group_num}",
            "span": span,
            "phrase": phrase,
            "description": "",
        })
        print(f"    img_{idx}  group_{group_num}  span={span}  '{phrase}'")

    # --- AI: image descriptions ---
    print(f"  Calling AI for {len(images)} image description(s)...")
    desc_raw = _api_call(
        DESC_SYSTEM_PROMPT,
        json.dumps({
            "scene_voiceover": scene_text,
            "images_needed": [
                {"img_id": img["img_id"], "phrase_spoken_when_image_appears": img["phrase"]}
                for img in images
            ],
        }, indent=2),
    )

    desc_map = {}
    if desc_raw:
        try:
            data = json.loads(desc_raw)
            desc_map = {item["img_id"]: item.get("description", "").strip()
                        for item in data.get("images", []) if item.get("img_id")}
        except Exception:
            pass

    for img in images:
        d = desc_map.get(img["img_id"], "").strip()
        if not d:
            p = img["phrase"].strip(".,!? ")
            d = (f"On a pure white background, a 2D colorful cartoon graphic related to '{p[:60]}'. "
                 f"No text, no letters, no numbers, no watermarks.")
        img["description"] = d

    out = {
        "scene_id": scene_id,
        "scene_text": scene_text,
        "tokens": tokens,
        "anchor_phrase": anchor["phrase"],
        "anchor_span": anchor["span"],
        "anchor_type": text_type,
        "images": images,
    }

    out_path = Path("assets/tmp") / f"{scene_id}_layout_2_step_2_tmp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 2 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
