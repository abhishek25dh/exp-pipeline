"""
Layout 33 Step 1 - Text Heading (Top-Center) + Image Left + Arrow + Image Right (Bottom)
=========================================================================================
Visual structure:
  [         TEXT HEADING (P1, top-center, ~x=929, y=332)          ]
  [ img_left (P2) ]  [ arrow (P3) ]  [ img_right (P4)             ]

Priority / firing order:
  P1: text_heading -- fires FIRST (sets topic/context, Rule 6: forward sentence search)
  P2: img_left     -- fires second
  P3: arrow        -- fires third (transition connector, must have phrase per Rule 1)
  P4: img_right    -- fires last

Token thresholds:
  N < 3  -> P1 only (heading gets all tokens)
  N < 6  -> P1 + P2 (heading + img_left; bottom row needs >= 3 tokens to split 3 ways)
  N >= 6 -> all 4

Phrase allocation (all 4 active):
  text_heading (P1): first sentence ending at forward sentence boundary, ~N//4 tokens,
                     cap at target+5 (Rule 6 heading pattern).
  img_left, arrow, img_right: remaining tokens split evenly among 3.

Vertical bounds (heading):
  Heading center y=332. Image top edge ~467 (y=711, scale=0.488, ~1000px -> half=244).
  Available below center: 467 - 30 - 332 = 105 scene px.
  At LINE_SPACING=110: floor(105/55) = 1 extra line below -> MAX_LINES_HEADING = 3.
  MAX_CHARS_HEADING = 3 x 72 = 216. (Rarely violated given ~N//4 token target.)

Text type: seeded random per scene (seed = scene_num * 7919).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED   = 7919
TEXT_TYPES       = ["text_highlighted", "text_red", "text_black"]
TEXT_SAFE_W      = 1800
AVG_CHAR_W       = 25
MAX_CHARS_LINE   = TEXT_SAFE_W // AVG_CHAR_W    # 72
MAX_LINES_HEADING = 3
MAX_CHARS_HEADING = MAX_LINES_HEADING * MAX_CHARS_LINE   # 216


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
    """
    Find end of heading phrase (fires first = forward sentence search).
    Searches forward from target, capped at target+5 (Rule 6).
    Falls back to previous sentence end if cap exceeded.
    If no sentence boundary found anywhere, returns max_end.
    """
    forward_limit = min(target + 5, max_end)
    for i in range(max(1, target), forward_limit + 1):
        if ends_sentence(tokens[i - 1]):
            return i
    for i in range(target - 1, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return max(1, i)
    return max_end


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


def split_evenly(tokens: list, n: int) -> list:
    """Split tokens into n roughly equal parts, snapping to sentence boundaries."""
    total = len(tokens)
    if n == 1:
        return [" ".join(tokens)]
    raw_targets = [round(total * i / n) for i in range(1, n)]
    split_pts, prev = [], 0
    for i, t in enumerate(raw_targets):
        best = t
        for delta in range(0, 4):
            for idx in [t + delta, t - delta]:
                if 1 <= idx < total and ends_sentence(tokens[idx - 1]):
                    best = idx
                    break
            else:
                continue
            break
        best = max(prev + 1, min(best, total - (n - 1 - i)))
        split_pts.append(best)
        prev = best
    bounds = [0] + split_pts + [total]
    return [" ".join(tokens[bounds[i]:bounds[i + 1]]) for i in range(n)]


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

    n        = len(tokens)
    n_active = 1 if n < 3 else (2 if n < 6 else 4)
    text_type = pick_text_type(scene_num)
    print(f"  Tokens: {n}  ->  Active: {n_active}  |  Text type: {text_type}")

    if n_active == 1:
        heading_phrase   = " ".join(tokens)
        img_phrases      = []

    elif n_active == 2:
        heading_target   = max(1, n // 4)
        max_heading      = max(1, n - 1)
        heading_end      = find_heading_end(tokens, heading_target, max_heading)
        heading_phrase   = " ".join(tokens[:heading_end])
        img_phrases      = [" ".join(tokens[heading_end:])]

    else:
        # All 4: heading gets first ~N//4 tokens, rest split 3 ways
        heading_target   = max(1, n // 4)
        max_heading      = max(1, n - 3)     # leave at least 1 token per bottom element
        heading_end      = find_heading_end(tokens, heading_target, max_heading)
        heading_phrase   = " ".join(tokens[:heading_end])
        img_phrases      = split_evenly(tokens[heading_end:], 3)  # img_left, arrow, img_right

    # Vertical bounds check on heading
    heading_lines = estimate_lines(heading_phrase)
    if heading_lines > MAX_LINES_HEADING:
        print(f"  WARNING: heading has {heading_lines} lines > MAX {MAX_LINES_HEADING} "
              f"({len(heading_phrase)} chars) — may overlap bottom images.")

    element_ids = ["text_heading", "img_left", "arrow", "img_right"][:n_active]
    all_phrases = [heading_phrase] + img_phrases

    for eid, phrase in zip(element_ids, all_phrases):
        ends_ok = ends_sentence(phrase.split()[-1]) if phrase.split() else False
        r6 = " (Rule 6 OK)" if eid == "text_heading" and ends_ok else \
             (" (Rule 6 FAIL!)" if eid == "text_heading" else "")
        print(f"  {eid:14s}: '{phrase[:65]}'{r6}")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in all_phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":          scene_id,
        "layout":            "33",
        "scene_text":        scene_text,
        "n_active":          n_active,
        "text_type":         text_type,
        "heading_phrase":    heading_phrase,
        "img_left_phrase":   img_phrases[0] if len(img_phrases) > 0 else "",
        "arrow_phrase":      img_phrases[1] if len(img_phrases) > 1 else "",
        "img_right_phrase":  img_phrases[2] if len(img_phrases) > 2 else "",
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_33_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
