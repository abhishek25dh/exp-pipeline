"""
Layout 39 Step 1 - 2x2 Image Grid Left + 4 Text Rows Right
===========================================================
Visual structure (from scene_20_director.json):
  [ img_tl (P1, x=274,  y=384)  ] [ img_tr (P2, x=772,  y=386)  ] | [text_row1 (P5, x=1426, y=329)]
  [ img_bl (P3, x=270,  y=832)  ] [ img_br (P4, x=785,  y=823)  ] | [text_row2 (P6, x=1436, y=540)]
                                                                    | [text_row3 (P7, x=1443, y=750)]
                                                                    | [text_row4 (P8, x=1452, y=935)]

Priority / firing order (creation timestamp):
  P1: img_tl    -- fires first
  P2: img_tr
  P3: img_bl
  P4: img_br
  P5: text_row1
  P6: text_row2
  P7: text_row3
  P8: text_row4 -- fires LAST -> Rule 6: punchline backward search

Token thresholds:
  N < 2  -> n_active=1  (img_tl only)
  N < 4  -> n_active=2  (top image pair)
  N < 6  -> n_active=4  (full 2x2 grid, no text)
  N < 8  -> n_active=5  (grid + text_row1)
  N < 10 -> n_active=6  (grid + text_row1..2)
  N < 12 -> n_active=7  (grid + text_row1..3)
  N >= 12 -> n_active=8  (all)

Token allocation (n_active=8):
  - Split all tokens into n_active roughly-equal parts snapped to sentence boundaries.
  - P8 (last text row): punchline backward search from its natural start.
  - P1-P7: forward sequential splits at natural sentence boundaries.
  - Images get their share of context; text rows are short bullet-style phrases.

Text constraints (right column, x~1440):
  TEXT_SAFE_W=600 (right column, ~600px wide).
  MAX_CHARS_LINE=20, LINE_SPACING=110.
  Row spacing ~210px -> MAX_LINES_PER_ROW=1 (bullet label style; avoids overlap with next row).
  Horizontal safe: x=1440, span=1440-300=1140 to 1440+300=1740 -- within canvas (1920).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED  = 7919
TEXT_TYPES      = ["text_highlighted", "text_red", "text_black"]
TEXT_SAFE_W     = 600
AVG_CHAR_W      = 30
MAX_CHARS_LINE  = TEXT_SAFE_W // AVG_CHAR_W   # 20
LINE_SPACING    = 110
MAX_LINES_ROW   = 1   # bullet label rows -- tight spacing, keep to 1 line


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def pick_text_type(scene_num: str) -> str:
    rng = random.Random(int(scene_num) * TEXT_TYPE_SEED if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def find_sentence_end(tokens: list, target: int, max_end: int) -> int:
    """Forward sentence search from target, capped at min(target+5, max_end)."""
    forward_limit = min(target + 5, max_end)
    for i in range(max(1, target), forward_limit + 1):
        if ends_sentence(tokens[i - 1]):
            return i
    for i in range(target - 1, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return max(1, i)
    return max_end


def find_punchline_start(tokens: list, target: int, min_start: int = 1) -> int:
    """Backward sentence search -- punchline rule (fires last)."""
    backward_limit = max(min_start, target - 5)
    for i in range(target, backward_limit - 1, -1):
        if i > 0 and ends_sentence(tokens[i - 1]):
            return i
    for i in range(target + 1, len(tokens)):
        if ends_sentence(tokens[i - 1]):
            return min(i, len(tokens) - 1)
    return max(min_start, target)


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


def split_sequential(tokens: list, n_parts: int) -> list:
    """Split tokens into n_parts sequential chunks snapped to sentence boundaries.
    Last part uses punchline backward search; all others use forward search."""
    n = len(tokens)
    size = n // n_parts
    boundaries = [0]

    # Assign first n_parts-1 parts using forward sentence search
    pos = 0
    for i in range(n_parts - 1):
        target = pos + size
        max_end = n - (n_parts - 1 - i)   # leave at least 1 token per remaining part
        end = find_sentence_end(tokens, min(target, max_end), max_end)
        end = max(end, pos + 1)  # always advance — prevents backward movement on fallback
        boundaries.append(end)
        pos = end

    # Last part: punchline backward search
    last_start_natural = pos
    last_target = n - size
    last_start = find_punchline_start(tokens, last_target, min_start=last_start_natural)
    # Ensure last_start >= previous boundary
    last_start = max(last_start, boundaries[-1])
    # Replace last boundary if punchline search moved it
    boundaries[-1] = last_start
    boundaries.append(n)

    chunks = []
    for i in range(n_parts):
        s, e = boundaries[i], boundaries[i + 1]
        chunk = " ".join(tokens[s:e]) if s < e else ""
        chunks.append(chunk)
    return chunks


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

    if   n < 2:  n_active = 1
    elif n < 4:  n_active = 2
    elif n < 6:  n_active = 4
    elif n < 8:  n_active = 5
    elif n < 10: n_active = 6
    elif n < 12: n_active = 7
    else:        n_active = 8

    print(f"  Tokens: {n}  ->  Active: {n_active}  |  Text type: {text_type}")

    chunks = split_sequential(tokens, n_active)

    keys_for_active = [
        "img_tl_phrase",    # P1
        "img_tr_phrase",    # P2
        "img_bl_phrase",    # P3
        "img_br_phrase",    # P4
        "text_row1_phrase", # P5
        "text_row2_phrase", # P6
        "text_row3_phrase", # P7
        "text_row4_phrase", # P8 (punchline)
    ]
    all_keys = keys_for_active[:n_active]

    out = {
        "scene_id":  scene_id,
        "layout":    "39",
        "scene_text": scene_text,
        "n_active":  n_active,
        "text_type": text_type,
    }
    # Zero-fill all keys
    for k in keys_for_active:
        out[k] = ""

    for i, (k, chunk) in enumerate(zip(all_keys, chunks)):
        out[k] = chunk
        is_img  = k.startswith("img_")
        is_last = i == n_active - 1
        rule_tag = ""
        if not is_img:
            last_tok = chunk.split()[-1] if chunk.split() else ""
            if is_last:
                rule_tag = "(Rule 6 punchline FAIL!)" if not ends_sentence(last_tok) else "(Rule 6 punchline OK)"
            else:
                rule_tag = "(Rule 6 FAIL!)" if not ends_sentence(last_tok) else "(Rule 6 OK)"
        print(f"  P{i+1:d} {k:20s}: '{chunk[:60]}'  {rule_tag}")

    # Validate text row line count (warn if over 1 line)
    text_keys = [k for k in all_keys if k.startswith("text_")]
    for k in text_keys:
        phrase = out[k]
        n_lines = estimate_lines(phrase)
        if n_lines > MAX_LINES_ROW:
            print(f"  WARNING: {k} has {n_lines} lines > MAX {MAX_LINES_ROW} -- may overlap next row.")

    # Tiling validation
    all_phrases  = [out[k] for k in all_keys if out[k]]
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in all_phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch!")
        print(f"  Script: {script_clean}")
        print(f"  Built : {built_clean}")

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_39_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
