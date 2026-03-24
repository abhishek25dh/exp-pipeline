"""
Layout 6 Step 1 — Deterministic Tokenization + Group Assignment
================================================================
Layout 6: 2 rows, each row has 1 image + 1-3 text labels.

FULLY DETERMINISTIC — no AI calls.
Splits script into 2 groups using DP (balanced, sentence-boundary biased).
Within each group: img_phrase = first N tokens (absorbs overflow to keep texts ≤5 words),
texts = remaining tokens in ≤5-word chunks (max 3 texts).
Outputs {groups} for Step 2 to add AI image descriptions.
"""

import json
import math
import re
import sys
from pathlib import Path

MAX_TEXT_WORDS = 5   # per text element (approach.md: keep ≤5 words at scale 1.6)
MAX_TEXTS = 3        # max text elements per group


def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def ends_sentence(tok):
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def partition_into_2(tokens):
    """DP split: 2 balanced contiguous spans, biased to sentence boundaries."""
    n = len(tokens)
    if n < 4:
        return [(0, n)]
    target = n / 2.0
    best_cost = math.inf
    best_split = n // 2
    for i in range(2, n - 1):
        seg1 = i
        seg2 = n - i
        cost = (seg1 - target) ** 2 + (seg2 - target) ** 2
        if i < n and not ends_sentence(tokens[i - 1]):
            cost += 8
        if cost < best_cost:
            best_cost = cost
            best_split = i
    return [(0, best_split), (best_split, n)]


def assign_group_elements(tokens, s, e):
    """
    Assign tokens in group [s, e) to img_phrase + text chunks.
    img_phrase absorbs enough tokens so remaining ≤ MAX_TEXT_WORDS * MAX_TEXTS.
    Each text chunk ≤ MAX_TEXT_WORDS. Last text absorbs any short leftover.
    Returns (img_phrase, img_span, texts_list)
      texts_list = [{"phrase": str, "span": [s, e]}]
    """
    toks = tokens[s:e]
    n = len(toks)

    # Minimum img tokens so remaining fits in MAX_TEXTS × MAX_TEXT_WORDS
    max_remaining = MAX_TEXTS * MAX_TEXT_WORDS
    img_min = max(2, n - max_remaining)
    # Preferred img length: ~1/4 of group, at least img_min
    img_len = max(img_min, min(4, max(2, n // 4)))
    # Snap forward to a sentence end within +3 tokens if possible
    for offset in range(0, min(4, n - img_len - 1)):
        if ends_sentence(toks[img_len - 1 + offset]):
            img_len = img_len + offset
            break
    img_len = max(img_min, min(img_len, n - 1))

    img_phrase = " ".join(toks[:img_len])
    img_span = [s, s + img_len]

    # Split remaining into ≤5-word chunks, max 3 texts
    rest = toks[img_len:]
    texts = []
    pos = 0
    while pos < len(rest):
        if len(texts) == MAX_TEXTS - 1:  # last text absorbs all leftover
            chunk = rest[pos:]
            texts.append({
                "phrase": " ".join(chunk),
                "span": [s + img_len + pos, e],
            })
            break
        chunk = rest[pos:pos + MAX_TEXT_WORDS]
        texts.append({
            "phrase": " ".join(chunk),
            "span": [s + img_len + pos, s + img_len + pos + len(chunk)],
        })
        pos += MAX_TEXT_WORDS

    return img_phrase, img_span, texts


def validate_tiling(tokens, groups):
    """Ensure all group phrases tile the full token list exactly once."""
    covered = []
    for g in groups:
        s, e = g["img_span"]
        covered.extend(tokens[s:e])
        for t in g["texts"]:
            ts, te = t["span"]
            covered.extend(tokens[ts:te])
    return covered == tokens


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text = strip_scene_prefix(prompt_data.get("prompt", ""))
    tokens = scene_text.split()

    if not tokens:
        print(f"Error: empty scene text for {scene_id}.")
        return 1

    spans = partition_into_2(tokens)

    groups = []
    for idx, (s, e) in enumerate(spans, start=1):
        img_phrase, img_span, texts = assign_group_elements(tokens, s, e)
        groups.append({
            "group_id": f"group_{idx}",
            "img_phrase": img_phrase,
            "img_span": img_span,
            "texts": texts,
        })

    # Validate tiling
    if not validate_tiling(tokens, groups):
        print("Error: tiling validation failed — tokens not fully covered.")
        return 1

    print(f"  Tokens: {len(tokens)}  |  Groups: {len(groups)}")
    for g in groups:
        print(f"    {g['group_id']}: img='{g['img_phrase']}' | "
              f"{len(g['texts'])} texts: {[t['phrase'] for t in g['texts']]}")

    out = {
        "scene_id": scene_id,
        "scene_text": scene_text,
        "tokens": tokens,
        "groups": groups,
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_6_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
