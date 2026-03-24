"""
Layout 23 Step 1 - Priority-Based Phrase Assignment
=====================================================
Visual structure:
                  [ P3 top-mid ] [ P4 top-right ]
  [ P1 hero                   ]
  [ (large, left)             ] [ P2 bottom-right ]

Priority order (Priority-Based Approach):
  P1: img_hero         - large left image,   always present
  P2: img_bottom_right - medium bottom-right, second priority
  P3: img_top_mid      - small top-middle,    third priority
  P4: img_top_right    - small top-right,     fourth priority

Token thresholds (min 2 tokens per image phrase):
  N < 4  -> P1 only
  N < 6  -> P1 + P2
  N < 8  -> P1 + P2 + P3
  N >= 8 -> all four images

Token allocation is proportional to image scale (larger image = more tokens = richer description).
All tokens always covered (tiling layout).
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Image definitions — scale drives proportional token allocation
# ---------------------------------------------------------------------------
IMAGES = [
    {"id": "img_hero",         "position": "hero",         "scale": 0.728},
    {"id": "img_bottom_right", "position": "bottom_right", "scale": 0.465},
    {"id": "img_top_mid",      "position": "top_mid",      "scale": 0.285},
    {"id": "img_top_right",    "position": "top_right",    "scale": 0.301},
]

THRESHOLDS = [(4, 1), (6, 2), (8, 3)]  # (min_tokens, n_images_if_below)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def choose_n_images(n_tokens: int) -> int:
    for min_tok, n_below in THRESHOLDS:
        if n_tokens < min_tok:
            return n_below
    return 4


def allocate_proportional(tokens: list, active_images: list) -> list:
    """
    Split tokens into proportional chunks based on image scale.
    Larger scale -> more tokens -> richer description.
    Last image absorbs any remainder to ensure full tiling.
    Each image guaranteed at least 2 tokens.
    """
    n            = len(tokens)
    total_scale  = sum(img["scale"] for img in active_images)
    n_imgs       = len(active_images)
    phrases      = []
    pos          = 0

    for i, img in enumerate(active_images):
        if i == n_imgs - 1:
            phrases.append(" ".join(tokens[pos:]))
            break

        proportion = img["scale"] / total_scale
        count      = max(2, round(n * proportion))

        # Must leave at least 2 tokens for each remaining image
        remaining_needed = (n_imgs - i - 1) * 2
        count = min(count, n - pos - remaining_needed)
        count = max(2, count)

        phrases.append(" ".join(tokens[pos: pos + count]))
        pos += count

    return phrases


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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
    active   = IMAGES[:n_images]

    print(f"  Tokens: {n}  ->  Active images: {n_images}")

    phrases = allocate_proportional(tokens, active)

    images_out = []
    for img, phrase in zip(active, phrases):
        images_out.append({
            "img_id":    img["id"],
            "position":  img["position"],
            "scale":     img["scale"],
            "phrase":    phrase,
        })
        print(f"  {img['position']:14s} -> '{phrase}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = []
    for img in images_out:
        built_clean.extend([clean_word(w) for w in img["phrase"].split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":   scene_id,
        "layout":     "23",
        "scene_text": scene_text,
        "n_images":   n_images,
        "images":     images_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_23_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
