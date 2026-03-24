"""
Layout 34 Step 1 - Image Left + Image Right + Text Center (x2) + Image Bottom
==============================================================================
Visual structure:
  [ img_left (P1, mid-left) ]  [ text_1 (P3, top-center) ]  [ img_right (P2, mid-right) ]
                               [ text_2 (P4, mid-center) ]
                                [ img_bottom (P5, bottom) ]

Priority / firing order (matches element_id creation timestamps):
  P1: img_left   -- fires first
  P2: img_right  -- fires second
  P3: text_1     -- fires third  (top-center label)
  P4: text_2     -- fires fourth (mid-center label)
  P5: img_bottom -- fires last   (conclusion image)

Token thresholds:
  N < 3  -> P1 only
  N < 5  -> P1 + P2
  N < 8  -> P1 + P2 + P3
  N < 12 -> P1 + P2 + P3 + P4
  N >= 12 -> all 5

Text constraints (center gap between side images):
  TEXT_SAFE_W=450 (derived from original placeholder: 8 chars * 25 * scale 2.24 = 448px).
  MAX_CHARS_LINE=18, LINE_SPACING=100.
  Horizontal: at TEXT_SAFE_W=450, text extends from 973-225=748 to 973+225=1198 scene.
    img_left inner edge ~741, img_right inner edge ~1207 -> ~7-9px scene margin each side.
  Vertical: text_1(y=338) and text_2(y=486) are 148px apart.
  With LINE_SPACING=100, 2-line block spans 100px centered:
    text_1 bottom = 388, text_2 top = 436 -> 48px gap -> MAX_LINES_TEXT=2.

Text type: seeded random per scene (seed = scene_num * 7919).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED   = 7919
TEXT_TYPES       = ["text_highlighted", "text_red", "text_black"]
TEXT_SAFE_W      = 450
AVG_CHAR_W       = 25
MAX_CHARS_LINE   = TEXT_SAFE_W // AVG_CHAR_W    # 18
MAX_LINES_TEXT   = 2
MAX_CHARS_TEXT   = MAX_LINES_TEXT * MAX_CHARS_LINE  # 36


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def pick_text_type(scene_num: str) -> str:
    rng = random.Random(int(scene_num) * TEXT_TYPE_SEED if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


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

    n = len(tokens)
    n_active = 1 if n < 3 else (2 if n < 5 else (3 if n < 8 else (4 if n < 12 else 5)))
    text_type = pick_text_type(scene_num)
    print(f"  Tokens: {n}  ->  Active: {n_active}  |  Text type: {text_type}")

    element_ids = ["img_left", "img_right", "text_1", "text_2", "img_bottom"][:n_active]
    phrases     = split_evenly(tokens, n_active)

    for eid, phrase in zip(element_ids, phrases):
        ends_ok = ends_sentence(phrase.split()[-1]) if phrase.split() else False
        r6 = "  (Rule 6 OK)" if eid in ("text_1", "text_2") and ends_ok else \
             ("  (Rule 6 FAIL!)" if eid in ("text_1", "text_2") else "")
        print(f"  {eid:12s}: '{phrase[:65]}'{r6}")

    # Vertical bounds check for text elements
    for eid, phrase in zip(element_ids, phrases):
        if eid in ("text_1", "text_2"):
            n_lines = estimate_lines(phrase)
            if n_lines > MAX_LINES_TEXT:
                print(f"  WARNING: {eid} has {n_lines} lines > MAX {MAX_LINES_TEXT} "
                      f"({len(phrase)} chars) -- may overlap adjacent elements.")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":          scene_id,
        "layout":            "34",
        "scene_text":        scene_text,
        "n_active":          n_active,
        "text_type":         text_type,
        "img_left_phrase":   phrases[0] if n_active >= 1 else "",
        "img_right_phrase":  phrases[1] if n_active >= 2 else "",
        "text_1_phrase":     phrases[2] if n_active >= 3 else "",
        "text_2_phrase":     phrases[3] if n_active >= 4 else "",
        "img_bottom_phrase": phrases[4] if n_active >= 5 else "",
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_34_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
