"""
Layout 28 Step 1 - Two Images Side-by-Side + Punchline Text Bottom
===================================================================
Visual structure:
  [ img_left (P1/P2) ]   [ img_right (P1/P2) ]
  [      TEXT PUNCHLINE (P3, bottom-center)   ]

Priority order (intelligence-driven):
  P1, P2: two images — randomly assigned left/right slot per scene (seeded)
  P3:     punchline text at bottom-center — always fires LAST

The bottom text is a conclusion / punchline: it ends at the last token of the
script and starts at the nearest sentence boundary ~75% through.  This ensures
it is a complete, independently readable closing statement (Rule 6).

Token thresholds (each active element needs at least 2 tokens):
  N < 3  -> P1 only (one image, all tokens)
  N < 5  -> P1 + P2 (both images only, tokens split evenly)
  N >= 5 -> all 3 (both images + punchline text)

Phrase split:
  Text punchline: tokens from last sentence boundary (~last 25%) to end.
  Images: tokens before the punchline split evenly.

Text type: seeded random per scene (seed = scene_num * 7919).
Slot randomness: seeded per scene (seed = scene_num * 3571).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED = 7919
SLOT_SEED      = 3571
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]
IMG_SLOTS      = ["left", "right"]


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def choose_n_active(n_tokens: int) -> int:
    if n_tokens < 3:
        return 1
    if n_tokens < 5:
        return 2
    return 3


def pick_text_type(scene_num: str) -> str:
    rng = random.Random(int(scene_num) * TEXT_TYPE_SEED if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def shuffled_img_slots(scene_num: str) -> list:
    """Return ["left","right"] or ["right","left"] seeded per scene."""
    rng = random.Random(int(scene_num) * SLOT_SEED if scene_num.isdigit() else hash(scene_num))
    slots = IMG_SLOTS[:]
    rng.shuffle(slots)
    return slots   # [P1_slot, P2_slot]


def find_punchline_start(tokens: list, target: int) -> int:
    """
    Find where the punchline text starts.
    Searches BACKWARD from target for the most recent sentence boundary.
    The punchline phrase = tokens[result:] — always ends at script end (Rule 6).

    target ≈ n - n//4: we want the last ~25% to be the punchline.
    We walk backward to ensure the punchline starts at a complete sentence.
    """
    for i in range(target, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return i   # punchline starts at token index i (0-based)
    return max(1, target)   # fallback: no sentence boundary found


def split_images_evenly(tokens: list, n: int) -> list:
    """Split tokens into n roughly equal phrases at nearest sentence boundaries."""
    total = len(tokens)
    if n <= 0:
        return []
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
    n_active = choose_n_active(n)
    n_imgs   = min(2, n_active)         # 1 or 2 images
    has_text = n_active == 3
    print(f"  Tokens: {n}  ->  Active: {n_active} ({n_imgs} image(s) + {'1 punchline text' if has_text else 'no text'})")

    text_type = pick_text_type(scene_num)
    img_slots = shuffled_img_slots(scene_num)
    active_img_slots = img_slots[:n_imgs]
    print(f"  Text type: {text_type}  |  Image slots: {img_slots}  ->  Active: {active_img_slots}")

    # --- Phrase assignment ---
    # Punchline text (P3) fires LAST — starts at the nearest sentence boundary
    # before the last ~25% of the script.  Images split everything before it.

    if n_active == 1:
        img_phrases  = [" ".join(tokens)]
        text_phrase  = ""

    elif n_active == 2:
        # Both images, no punchline text
        img_phrases = split_images_evenly(tokens, 2)
        text_phrase = ""

    else:
        # All 3 active: find punchline start, images take the rest
        n_imgs_active   = 2
        # Reserve at least 1 token per image before the punchline
        punchline_target = max(n_imgs_active, n - max(2, n // 4))
        text_start       = find_punchline_start(tokens, punchline_target)

        text_phrase  = " ".join(tokens[text_start:])
        img_phrases  = split_images_evenly(tokens[:text_start], n_imgs_active)

    print(f"  img_phrases: {[p[:50] for p in img_phrases]}")
    if text_phrase:
        print(f"  punchline  : '{text_phrase[:70]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = []
    for phrase in img_phrases:
        built_clean.extend([clean_word(w) for w in phrase.split() if clean_word(w)])
    if text_phrase:
        built_clean.extend([clean_word(w) for w in text_phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    # --- Build image and text lists ---
    images_out = [
        {"img_id": f"img_{slot}", "slot": slot, "priority": i + 1, "phrase": phrase}
        for i, (slot, phrase) in enumerate(zip(active_img_slots, img_phrases))
    ]

    out = {
        "scene_id":   scene_id,
        "layout":     "28",
        "scene_text": scene_text,
        "n_active":   n_active,
        "text_type":  text_type,
        "img_slots":  img_slots,
        "images":     images_out,
        "text_phrase": text_phrase,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_28_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
