"""
Layout 32 Step 1 - Two Images Side-by-Side (No Text)
=====================================================
Visual structure:
  [ img_left (P1) ]   [ img_right (P2) ]

Both images are AI-generated. Slots randomly assigned per scene (seeded).
No text elements — no Rule 6 constraints.

Token thresholds:
  N < 3  -> P1 only (one image, all tokens)
  N >= 3 -> P1 + P2 (tokens split evenly at nearest sentence boundary)

Slot randomness: seeded per scene (seed = scene_num * 2267).
"""

import json
import random
import re
import sys
from pathlib import Path

SLOT_SEED = 2267
IMG_SLOTS = ["left", "right"]


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def shuffled_slots(scene_num: str) -> list:
    rng = random.Random(int(scene_num) * SLOT_SEED if scene_num.isdigit() else hash(scene_num))
    slots = IMG_SLOTS[:]
    rng.shuffle(slots)
    return slots


def find_split(tokens: list, target: int, window: int = 3) -> int:
    """Snap split point to nearest sentence boundary within window."""
    n = len(tokens)
    for delta in range(0, window + 1):
        for idx in [target + delta, target - delta]:
            if 1 <= idx < n and ends_sentence(tokens[idx - 1]):
                return idx
    return max(1, min(n - 1, target))


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
    slots    = shuffled_slots(scene_num)
    active_slots = slots[:n_active]
    print(f"  Tokens: {n}  ->  Active: {n_active}  |  Slots: {active_slots}")

    if n_active == 1:
        phrases = [" ".join(tokens)]
    else:
        split   = find_split(tokens, n // 2)
        phrases = [" ".join(tokens[:split]), " ".join(tokens[split:])]

    for slot, phrase in zip(active_slots, phrases):
        print(f"  img_{slot}: '{phrase[:70]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        return 1

    images_out = [
        {"img_id": f"img_{slot}", "slot": slot, "priority": i + 1, "phrase": phrase}
        for i, (slot, phrase) in enumerate(zip(active_slots, phrases))
    ]

    out = {
        "scene_id":   scene_id,
        "layout":     "32",
        "scene_text": scene_text,
        "n_active":   n_active,
        "img_slots":  slots,
        "images":     images_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_32_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
