"""
Layout 35 Step 1 - Host Left (Static) + Text Right
====================================================
Visual structure:
  [ host_explaining.png (P1, left, static) ]  [ text_right (P2, right) ]

Priority / firing order:
  P1: host_explaining.png -- fires first (static local asset, no AI)
  P2: text_right          -- fires last  (Rule 6: backward sentence search)

Token thresholds:
  N < 3  -> P1 only (host gets all tokens)
  N >= 3 -> P1 + P2

Phrase allocation (N >= 3):
  P2 text (fires last) -> find_punchline_start backward from N - max(2, N//3).
  P1 host              -> all remaining tokens before text_start.

Text constraints (right column, x=1372):
  TEXT_SAFE_W=850 (derived from original: 8 chars * 25 * scale 4.267 = 853px).
  MAX_CHARS_LINE=34, LINE_SPACING=110.
  Vertical: text center y=446, canvas safe 30-1050.
    Max lines (from top): floor((446-30)/55) = 7 -> MAX_LINES_TEXT=7 (generous).
    Practically, warn if > 5 lines.

Text type: seeded random per scene (seed = scene_num * 7919).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED  = 7919
TEXT_TYPES      = ["text_highlighted", "text_red", "text_black"]
TEXT_SAFE_W     = 850
AVG_CHAR_W      = 25
MAX_CHARS_LINE  = TEXT_SAFE_W // AVG_CHAR_W   # 34
LINE_SPACING    = 110
WARN_LINES      = 5


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def pick_text_type(scene_num: str) -> str:
    rng = random.Random(int(scene_num) * TEXT_TYPE_SEED if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def find_punchline_start(tokens: list, target: int) -> int:
    """Search backward from target for the last sentence boundary.
    Returns index i such that tokens[i:] is the punchline phrase.
    """
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
    n_active = 2 if n >= 3 else 1
    text_type = pick_text_type(scene_num)
    print(f"  Tokens: {n}  ->  Active: {n_active}  |  Text type: {text_type}")

    if n_active == 1:
        host_phrase = " ".join(tokens)
        text_phrase = ""
    else:
        target      = max(1, n - max(2, n // 3))
        text_start  = find_punchline_start(tokens, target)
        host_phrase = " ".join(tokens[:text_start])
        text_phrase = " ".join(tokens[text_start:])

    print(f"  host (P1): '{host_phrase[:70]}'")
    if text_phrase:
        ends_ok = ends_sentence(text_phrase.split()[-1]) if text_phrase.split() else False
        print(f"  text (P2): '{text_phrase[:70]}'{'  (Rule 6 OK)' if ends_ok else '  (Rule 6 FAIL!)'}")

        n_lines = estimate_lines(text_phrase)
        if n_lines > WARN_LINES:
            print(f"  WARNING: text has {n_lines} lines > WARN {WARN_LINES} -- may look crowded.")

    # --- Tiling validation ---
    all_phrases  = [p for p in [host_phrase, text_phrase] if p]
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in all_phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":    scene_id,
        "layout":      "35",
        "scene_text":  scene_text,
        "n_active":    n_active,
        "text_type":   text_type,
        "host_phrase": host_phrase,
        "text_phrase": text_phrase,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_35_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
