"""
Layout 26 Step 1 - Text Top-Left + 2 Images Below + 4 Images Right (2x2)
=========================================================================
Visual structure:
  [ TEXT (P1, top-left)          ]   [ img_R_TL ] [ img_R_TR ]
  [ img_BL (P2/P3) ] [ img_BR ]     [ img_R_BL ] [ img_R_BR ]

Priority order:
  P1: text           -- always present (random type: highlighted/red/black)
  P2, P3: 2 images below text -- randomly swapped slot (left/right)
  P4-P7: 4 images on right    -- randomly shuffled slot order

Token thresholds (each active element needs at least 2 tokens):
  N < 2  -> P1 only (text)
  N < 4  -> P1 + P2
  N < 6  -> P1 + P2 + P3
  N < 8  -> P1-P4
  N < 10 -> P1-P5
  N < 12 -> P1-P6
  N >= 12 -> all 7

Phrase split: text phrase extends forward to the next sentence end (must be readable standalone).
Remaining tokens split evenly among active images.
Text type: seeded random per scene (seed = scene_num * 7919).
Slot randomness: seeded per scene (seed = scene_num * 6143).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED = 7919
SLOT_SEED      = 6143
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]

BELOW_SLOTS = ["left", "right"]
RIGHT_SLOTS = ["top_left", "top_right", "bot_left", "bot_right"]


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def choose_n_active(n_tokens: int) -> int:
    if n_tokens < 2:
        return 1
    if n_tokens < 4:
        return 2
    if n_tokens < 6:
        return 3
    if n_tokens < 8:
        return 4
    if n_tokens < 10:
        return 5
    if n_tokens < 12:
        return 6
    return 7


def pick_text_type(scene_num: str) -> str:
    rng = random.Random(int(scene_num) * TEXT_TYPE_SEED if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def shuffled_slots(scene_num: str) -> tuple:
    """Return (below_slots, right_slots) both randomly shuffled, seeded per scene."""
    rng = random.Random(int(scene_num) * SLOT_SEED if scene_num.isdigit() else hash(scene_num))
    below = BELOW_SLOTS[:]
    rng.shuffle(below)
    right = RIGHT_SLOTS[:]
    rng.shuffle(right)
    return below, right


def find_text_end_sentence(tokens: list, target: int, max_end: int) -> int:
    """
    Find where a TEXT element's phrase should end.
    Rule: phrase must end at a sentence boundary (independently readable).

    Forward search is capped at target+5 to prevent text from consuming too many
    tokens and producing too many visual lines. If the next sentence end is further
    than 5 tokens away, fall back to the PREVIOUS sentence end (backward search).
    This keeps text short enough to fit in its canvas area without overlapping images.
    """
    forward_limit = min(target + 5, max_end)
    for i in range(max(1, target), forward_limit + 1):
        if ends_sentence(tokens[i - 1]):
            return i
    # Next sentence end too far forward — use previous sentence end
    for i in range(target - 1, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return max(1, i)
    return max(1, min(target, max_end))


def split_images_evenly(tokens: list, n: int) -> list:
    """Split tokens into n roughly equal phrases at nearest sentence boundaries."""
    total = len(tokens)
    if n == 1:
        return [" ".join(tokens)]
    raw_targets = [round(total * i / n) for i in range(1, n)]
    split_pts, prev = [], 0
    for i, t in enumerate(raw_targets):
        # Bidirectional ±window search is fine for image phrases
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
    n_active = choose_n_active(n)
    n_below  = max(0, min(2, n_active - 1))        # P2/P3 below images
    n_right  = max(0, n_active - 1 - n_below)      # P4-P7 right images
    print(f"  Tokens: {n}  ->  Active: {n_active} (1 text + {n_below} below + {n_right} right)")

    text_type            = pick_text_type(scene_num)
    below_slots, right_slots = shuffled_slots(scene_num)
    active_below = below_slots[:n_below]
    active_right = right_slots[:n_right]
    print(f"  Text type: {text_type}")
    print(f"  Below slots: {below_slots}  ->  Active: {active_below}")
    print(f"  Right slots: {right_slots}  ->  Active: {active_right}")

    # --- Extract text phrase: extend forward to next sentence end ---
    n_images    = n_below + n_right
    text_target = max(1, n // n_active)
    max_text_end = max(1, n - n_images)   # leave at least 1 token per image
    text_end    = find_text_end_sentence(tokens, text_target, max_text_end)
    text_phrase = " ".join(tokens[:text_end])

    # --- Split remaining tokens evenly among active images ---
    img_phrases  = split_images_evenly(tokens[text_end:], n_images) if n_images > 0 else []
    below_phrases = img_phrases[:n_below]
    right_phrases = img_phrases[n_below:]

    print(f"  text (P1)          : '{text_phrase[:60]}'")
    for i, (slot, phrase) in enumerate(zip(active_below, below_phrases)):
        print(f"  img_below_{slot:5s} (P{i+2}): '{phrase[:60]}'")
    for i, (slot, phrase) in enumerate(zip(active_right, right_phrases)):
        print(f"  img_right_{slot:9s} (P{i+2+n_below}): '{phrase[:60]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for w in text_phrase.split() if clean_word(w)]
    for phrase in below_phrases + right_phrases:
        built_clean.extend([clean_word(w) for w in phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    # --- Build image lists ---
    below_images = [
        {"img_id": f"img_below_{slot}", "slot": slot, "group": "below", "priority": i + 2, "phrase": phrase}
        for i, (slot, phrase) in enumerate(zip(active_below, below_phrases))
    ]
    right_images = [
        {"img_id": f"img_right_{slot}", "slot": slot, "group": "right", "priority": i + 2 + n_below, "phrase": phrase}
        for i, (slot, phrase) in enumerate(zip(active_right, right_phrases))
    ]

    out = {
        "scene_id":     scene_id,
        "layout":       "26",
        "scene_text":   scene_text,
        "n_active":     n_active,
        "text_phrase":  text_phrase,
        "text_type":    text_type,
        "below_slots":  below_slots,
        "right_slots":  right_slots,
        "images":       below_images + right_images,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_26_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
