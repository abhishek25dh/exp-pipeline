"""
Layout 24 Step 1 - Priority-Based Phrase Assignment
=====================================================
Visual structure:
  [ img_left  ]  [ img_right ]    <- y~380, two images
  [       bottom text        ]    <- y~870, centered text

Priority order:
  P1: bottom_text  - always present (last phrase in script, the punchline/anchor)
  P2 & P3: img_left and img_right - RANDOMLY SWAPPED per scene (seeded)
            one of them is P2, the other P3 — different every scene

Token thresholds:
  N < 4  -> P1 only (text = all tokens)
  N < 6  -> P1 + P2 image only (1 image, randomly left or right)
  N >= 6 -> P1 + both images

Phrase order in script (timing): images fire first, text fires last.
  img_P2_phrase (tokens 0..a) -> img_P3_phrase (tokens a..b) -> text_phrase (tokens b..N)

Randomness: seeded per scene_num so same scene always produces same layout,
but different scenes get different image priority ordering.
"""

import json
import random
import re
import sys
from pathlib import Path

RAND_SEED_MULT = 2053   # different from text_type seed (7919)


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def choose_n_images(n_tokens: int) -> int:
    if n_tokens < 4:
        return 0
    if n_tokens < 6:
        return 1
    return 2


def find_text_start(tokens: list, n_images: int) -> int:
    """
    Find index where the bottom text phrase begins (text gets the tail of the script).
    Prefers the last sentence boundary, leaving at least 2 tokens per image.
    """
    n         = len(tokens)
    min_start = max(n_images * 2, 1)   # leave at least 2 tokens per active image

    # Search backward for the last sentence boundary
    for i in range(n - 1, min_start - 1, -1):
        if ends_sentence(tokens[i - 1]):
            return i

    # No sentence boundary — use last proportional chunk
    return max(min_start, n - max(2, n // (n_images + 1)))


def img_order_for_scene(scene_num: str) -> tuple:
    """
    Return (first_slot, second_slot) as ('left','right') or ('right','left').
    Seeded per scene so same scene is always reproducible, but varies across scenes.
    """
    rng = random.Random(int(scene_num) * RAND_SEED_MULT if scene_num.isdigit() else hash(scene_num))
    slots = ["left", "right"]
    rng.shuffle(slots)
    return tuple(slots)   # (P2_slot, P3_slot)


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
    n_images = choose_n_images(n)
    print(f"  Tokens: {n}  ->  Active images: {n_images}")

    # --- Determine image slot order (random per scene) ---
    p2_slot, p3_slot = img_order_for_scene(scene_num)
    print(f"  Image order: P2={p2_slot}  P3={p3_slot}")

    # --- Find text start (text = tail of script) ---
    text_start   = find_text_start(tokens, n_images)
    text_phrase  = " ".join(tokens[text_start:])
    image_tokens = tokens[:text_start]

    # --- Split image tokens between active images ---
    images_out = []
    if n_images == 0:
        text_phrase = " ".join(tokens)   # all tokens go to text

    elif n_images == 1:
        # Only P2 image active — use its slot
        images_out.append({
            "img_id":   f"img_{p2_slot}",
            "slot":     p2_slot,
            "priority": 2,
            "phrase":   " ".join(image_tokens),
        })

    else:  # n_images == 2
        # Split image tokens: P2 gets first half, P3 gets rest
        m    = len(image_tokens)
        half = max(2, m // 2)
        # Cap to leave at least 2 for P3
        half = min(half, m - 2)

        p2_phrase = " ".join(image_tokens[:half])
        p3_phrase = " ".join(image_tokens[half:])

        images_out.append({
            "img_id":   f"img_{p2_slot}",
            "slot":     p2_slot,
            "priority": 2,
            "phrase":   p2_phrase,
        })
        images_out.append({
            "img_id":   f"img_{p3_slot}",
            "slot":     p3_slot,
            "priority": 3,
            "phrase":   p3_phrase,
        })

    # Print summary
    for img in images_out:
        print(f"  img_{img['slot']:5s} (P{img['priority']}): '{img['phrase'][:60]}'")
    print(f"  text (P1)      : '{text_phrase[:60]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = []
    for img in images_out:
        built_clean.extend([clean_word(w) for w in img["phrase"].split() if clean_word(w)])
    built_clean.extend([clean_word(w) for w in text_phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":    scene_id,
        "layout":      "24",
        "scene_text":  scene_text,
        "n_images":    n_images,
        "p2_slot":     p2_slot,
        "p3_slot":     p3_slot,
        "images":      images_out,
        "text_phrase": text_phrase,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_24_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
