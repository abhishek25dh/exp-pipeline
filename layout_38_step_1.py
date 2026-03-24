"""
Layout 38 Step 1 - Text Bottom Center (Fires First) + Two AI Images
====================================================================
Visual structure:
  [ img_left (P2, x=415, y=511)  ]  [ img_right (P3, x=1443, y=503) ]
  [        text_bottom_center (P1, x=942, y=934)                     ]

Priority / firing order (creation timestamp in director JSON):
  P1: text_bottom_center -- fires FIRST (bottom-center label/premise; Rule 6: forward sentence search)
  P2: img_left           -- fires second (AI image)
  P3: img_right          -- fires last   (AI image)

Token thresholds:
  N < 2  -> n_active=1 (text only)
  N < 4  -> n_active=2 (text + img_left)
  N >= 4 -> n_active=3 (all three)

Phrase allocation (n_active=3):
  P1 text (fires first, narrow callout): target = max(2, N//6); find_heading_end forward, capped at N-2.
  P2+P3 images: remaining tokens split evenly at nearest sentence boundary.

Text constraints (bottom center, x=942, y=934):
  TEXT_SAFE_W=350 (derived from original: 8 chars * 25 * scale 1.74 = 348px).
  MAX_CHARS_LINE=14, LINE_SPACING=110.
  Vertical: center y=934. Bottom safe=1050 -> (n-1)*55 <= 116 -> MAX_LINES_TEXT=3.
  Callout rule (TEXT_SAFE_W <= 600): allocate max(2, N//6) tokens.

Text type: seeded random per scene (seed = scene_num * 7919).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED  = 7919
TEXT_TYPES      = ["text_highlighted", "text_red", "text_black"]
TEXT_SAFE_W     = 350
AVG_CHAR_W      = 25
MAX_CHARS_LINE  = TEXT_SAFE_W // AVG_CHAR_W   # 14
LINE_SPACING    = 110
MAX_LINES_TEXT  = 3


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def pick_text_type(scene_num: str) -> str:
    rng = random.Random(int(scene_num) * TEXT_TYPE_SEED if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def find_heading_end(tokens: list, target: int, max_end: int) -> int:
    """Forward sentence search (fires first = heading/premise).
    Searches forward from target, capped at min(target+5, max_end).
    Falls back to previous sentence end if cap exceeded.
    If no sentence boundary found, returns max_end."""
    forward_limit = min(target + 5, max_end)
    for i in range(max(1, target), forward_limit + 1):
        if ends_sentence(tokens[i - 1]):
            return i
    for i in range(target - 1, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return max(1, i)
    return max_end


def find_split(tokens: list, target: int, window: int = 3) -> int:
    """Snap split point to nearest sentence boundary within window."""
    n = len(tokens)
    for delta in range(0, window + 1):
        for idx in [target + delta, target - delta]:
            if 1 <= idx < n and ends_sentence(tokens[idx - 1]):
                return idx
    return max(1, min(n - 1, target))


def estimate_lines(phrase: str) -> int:
    if len(phrase) <= MAX_CHARS_LINE:
        return 1
    words = phrase.split()
    lines, current_len = 1, 0
    for word in words:
        add_len = len(word) + (1 if current_len > 0 else 0)
        if current_len + add_len > MAX_CHARS_LINE:
            lines += 1
            current_len = len(word)
        else:
            current_len += add_len
    return lines


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text  = strip_scene_prefix(prompt_data.get("prompt", ""))
    tokens      = scene_text.split()

    if not tokens:
        print("Error: empty scene text.")
        return 1

    n         = len(tokens)
    text_type = pick_text_type(scene_num)

    if n < 2:
        n_active = 1
    elif n < 4:
        n_active = 2
    else:
        n_active = 3

    print(f"  Tokens: {n}  ->  Active: {n_active}  |  Text type: {text_type}")

    text_phrase      = ""
    img_left_phrase  = ""
    img_right_phrase = ""

    if n_active == 1:
        text_phrase = " ".join(tokens)

    elif n_active == 2:
        text_target = max(1, n // 2)
        text_end    = find_heading_end(tokens, text_target, n - 1)
        text_phrase     = " ".join(tokens[:text_end])
        img_left_phrase = " ".join(tokens[text_end:])

    else:  # n_active == 3
        # P1 text: narrow callout -> max(2, N//6) tokens
        text_target = max(2, n // 6)
        text_end    = find_heading_end(tokens, text_target, n - 2)
        text_phrase = " ".join(tokens[:text_end])

        # P2+P3 images: remaining tokens split evenly
        remaining   = tokens[text_end:]
        mid         = find_split(remaining, len(remaining) // 2)
        img_left_phrase  = " ".join(remaining[:mid])
        img_right_phrase = " ".join(remaining[mid:])

    # --- Rule 6 validation for text (fires first) ---
    ends_ok = ends_sentence(text_phrase.split()[-1]) if text_phrase.split() else False
    print(f"  text   (P1): '{text_phrase[:70]}'  {'(Rule 6 OK)' if ends_ok else '(Rule 6 FAIL!)'}")

    # --- Vertical bounds check ---
    n_lines = estimate_lines(text_phrase)
    if n_lines > MAX_LINES_TEXT:
        print(f"  WARNING: text has {n_lines} lines > MAX {MAX_LINES_TEXT} -- may overflow bottom canvas.")

    if img_left_phrase:
        print(f"  img_left (P2): '{img_left_phrase[:70]}'")
    if img_right_phrase:
        print(f"  img_right(P3): '{img_right_phrase[:70]}'")

    # --- Tiling validation ---
    all_phrases  = [p for p in [text_phrase, img_left_phrase, img_right_phrase] if p]
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in all_phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":        scene_id,
        "layout":          "38",
        "scene_text":      scene_text,
        "n_active":        n_active,
        "text_type":       text_type,
        "text_phrase":     text_phrase,
        "img_left_phrase": img_left_phrase,
        "img_right_phrase": img_right_phrase,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_38_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
