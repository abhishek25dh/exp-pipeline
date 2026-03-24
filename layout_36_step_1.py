"""
Layout 36 Step 1 - Host Right (Static) + Image Left + Arrow + Image Center + Text Bottom-Left
==============================================================================================
Visual structure:
  [ img_left (P2) ]  [ arrow (P3) -> ]  [ img_center (P4) ]  [ host_explaining.png (P1, right) ]
  [ text_bottom_left (P5, fires last)                                                           ]

Priority / firing order:
  P1: host_explaining.png  -- fires FIRST  (right side, static, Rule 6: forward sentence search)
  P2: img_left             -- fires second (AI image)
  P3: arrow.png            -- fires third  (static, transition connector, must have phrase)
  P4: img_center           -- fires fourth (AI image)
  P5: text_bottom_left     -- fires LAST   (Rule 6: backward sentence search = punchline)

Token thresholds:
  N < 3   -> n_active=1 (host only)
  N < 5   -> n_active=2 (host + img_left)
  N < 10  -> n_active=4 (host + img_left + arrow + img_center; no text)
  N >= 10 -> n_active=5 (all five)

Phrase allocation (n_active=5, N>=10):
  P5 text (fires last):   narrow callout -> target = N - max(2, N//6); find_punchline_start backward.
  P1 host (fires first):  heading -> target = max(3, N//5); find_heading_end forward, capped at text_start-3.
  P2/P3/P4:               tokens[host_end:text_start] split evenly into 3.

Text constraints (bottom-left, x=599, y=826):
  TEXT_SAFE_W = 490 (derived from original: 8 chars * 25 * scale 2.437 = 487px).
  MAX_CHARS_LINE = 19, LINE_SPACING = 110.
  Vertical: center y=826. Bottom safe = 1050 -> (n-1)*55 <= 224 -> MAX_LINES_TEXT = 5.

Text type: seeded random per scene (seed = scene_num * 7919).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED  = 7919
TEXT_TYPES      = ["text_highlighted", "text_red", "text_black"]
TEXT_SAFE_W     = 490
AVG_CHAR_W      = 25
MAX_CHARS_LINE  = TEXT_SAFE_W // AVG_CHAR_W   # 19
LINE_SPACING    = 110
MAX_LINES_TEXT  = 5


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
    """Forward sentence search (fires first = heading). Searches forward from target,
    capped at min(target+5, max_end). Falls back to previous sentence end if cap exceeded."""
    forward_limit = min(target + 5, max_end)
    for i in range(max(1, target), forward_limit + 1):
        if ends_sentence(tokens[i - 1]):
            return i
    for i in range(target - 1, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return max(1, i)
    return max_end


def find_punchline_start(tokens: list, target: int) -> int:
    """Backward sentence search (fires last = punchline). Returns index i so tokens[i:] is the phrase."""
    for i in range(target, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return i
    return max(1, target)


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

    n         = len(tokens)
    text_type = pick_text_type(scene_num)

    if n < 3:
        n_active = 1
    elif n < 5:
        n_active = 2
    elif n < 10:
        n_active = 4
    else:
        n_active = 5

    print(f"  Tokens: {n}  ->  Active: {n_active}  |  Text type: {text_type}")

    # --- Phrase allocation ---
    host_phrase    = ""
    img_left_phrase  = ""
    arrow_phrase     = ""
    img_center_phrase = ""
    text_phrase    = ""

    if n_active == 1:
        host_phrase = " ".join(tokens)

    elif n_active == 2:
        host_target = max(1, n // 2)
        host_end    = find_heading_end(tokens, host_target, n - 1)
        host_phrase     = " ".join(tokens[:host_end])
        img_left_phrase = " ".join(tokens[host_end:])

    elif n_active == 4:
        host_target = max(1, n // 4)
        host_end    = find_heading_end(tokens, host_target, n - 3)
        host_phrase = " ".join(tokens[:host_end])
        middle      = split_evenly(tokens[host_end:], 3)
        img_left_phrase   = middle[0]
        arrow_phrase      = middle[1]
        img_center_phrase = middle[2]

    else:  # n_active == 5
        text_target  = n - max(2, n // 6)
        text_start   = find_punchline_start(tokens, text_target)
        text_phrase  = " ".join(tokens[text_start:])

        host_target  = max(3, n // 5)
        host_max_end = max(1, text_start - 3)
        host_end     = find_heading_end(tokens, host_target, host_max_end)
        host_phrase  = " ".join(tokens[:host_end])

        middle = split_evenly(tokens[host_end:text_start], 3)
        img_left_phrase   = middle[0]
        arrow_phrase      = middle[1]
        img_center_phrase = middle[2]

    # --- Rule 6 validation for text elements ---
    print(f"  host   (P1): '{host_phrase[:70]}'")
    if host_phrase.split():
        ends_ok = ends_sentence(host_phrase.split()[-1])
        print(f"    Rule 6: {'OK' if ends_ok else 'FAIL!'}")

    if img_left_phrase:
        print(f"  img_left (P2): '{img_left_phrase[:70]}'")
    if arrow_phrase:
        print(f"  arrow    (P3): '{arrow_phrase[:70]}'")
    if img_center_phrase:
        print(f"  img_ctr  (P4): '{img_center_phrase[:70]}'")

    if text_phrase:
        ends_ok = ends_sentence(text_phrase.split()[-1]) if text_phrase.split() else False
        print(f"  text   (P5): '{text_phrase[:70]}'  {'(Rule 6 OK)' if ends_ok else '(Rule 6 FAIL!)'}")
        n_lines = estimate_lines(text_phrase)
        if n_lines > MAX_LINES_TEXT:
            print(f"  WARNING: text has {n_lines} lines > MAX {MAX_LINES_TEXT} -- degrading to n_active=4.")
            n_active         = 4
            text_phrase      = ""
            # redistribute text tokens back to img_center (last active element absorbs)
            all_middle_toks  = tokens[host_end:]
            middle           = split_evenly(all_middle_toks, 3)
            img_left_phrase  = middle[0]
            arrow_phrase     = middle[1]
            img_center_phrase = middle[2]

    # --- Tiling validation ---
    all_phrases  = [p for p in [host_phrase, img_left_phrase, arrow_phrase,
                                img_center_phrase, text_phrase] if p]
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in all_phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":            scene_id,
        "layout":              "36",
        "scene_text":          scene_text,
        "n_active":            n_active,
        "text_type":           text_type,
        "host_phrase":         host_phrase,
        "img_left_phrase":     img_left_phrase,
        "arrow_phrase":        arrow_phrase,
        "img_center_phrase":   img_center_phrase,
        "text_phrase":         text_phrase,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_36_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
