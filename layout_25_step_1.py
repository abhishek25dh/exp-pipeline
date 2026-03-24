"""
Layout 25 Step 1 - Host Right + 4 Images Left (2x2 Grid)
=========================================================
Visual structure:
  [ img_top_left  ]  [ img_top_right  ]   y~350
  [ img_bot_left  ]  [ img_bot_right  ]   y~763
                           [ host_looking_left ]  y~621 (right side)

Priority order:
  P1: host_looking_left -- always present (static local asset, no AI generation)
  P2-P5: 4 left images -- randomly shuffled slot order per scene (seeded)

Token thresholds (each active element gets at least 2 tokens):
  N < 3  -> P1 only
  N < 5  -> P1 + P2
  N < 7  -> P1 + P2 + P3
  N < 9  -> P1 + P2 + P3 + P4
  N >= 9 -> all 5 (P1-P5)

Phrase split: tokens divided evenly among active elements, sentence boundaries preferred.
Host element uses img_host_right_ prefix (not host_ prefix) so phrase audit covers it.
"""

import json
import random
import re
import sys
from pathlib import Path

RAND_SEED_MULT = 4813   # distinct from other layout seeds (7919, 2053, 3571)

LEFT_SLOTS = ["top_left", "top_right", "bottom_left", "bottom_right"]


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
    if n_tokens < 7:
        return 3
    if n_tokens < 9:
        return 4
    return 5


def slot_order_for_scene(scene_num: str) -> list:
    """Return shuffled copy of LEFT_SLOTS seeded per scene."""
    rng = random.Random(int(scene_num) * RAND_SEED_MULT if scene_num.isdigit() else hash(scene_num))
    slots = LEFT_SLOTS[:]
    rng.shuffle(slots)
    return slots   # [P2_slot, P3_slot, P4_slot, P5_slot]


def find_nearest_sentence_end(tokens: list, target: int, window: int = 3) -> int:
    """Return index nearest to target that follows a sentence-ending token."""
    n = len(tokens)
    for delta in range(0, window + 1):
        for idx in [target + delta, target - delta]:
            if 1 <= idx < n and ends_sentence(tokens[idx - 1]):
                return idx
    return max(1, min(n - 1, target))


def split_tokens_n(tokens: list, n: int) -> list:
    """Split tokens into n roughly equal phrase strings, preferring sentence boundaries."""
    total = len(tokens)
    if n == 1:
        return [" ".join(tokens)]

    # Compute n-1 split points from even division, then snap to sentence boundaries
    raw_targets = [round(total * i / n) for i in range(1, n)]
    split_pts = []
    for t in raw_targets:
        split_pts.append(find_nearest_sentence_end(tokens, t))

    # Ensure strictly increasing, each chunk has at least 1 token
    adjusted = []
    prev = 0
    for i, sp in enumerate(split_pts):
        sp = max(prev + 1, sp)
        sp = min(sp, total - (n - 1 - i))   # leave at least 1 token per remaining chunk
        adjusted.append(sp)
        prev = sp

    bounds = [0] + adjusted + [total]
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

    n          = len(tokens)
    n_active   = choose_n_active(n)
    n_images   = n_active - 1   # active left images (excludes host)
    print(f"  Tokens: {n}  ->  Active elements: {n_active} (host + {n_images} image(s))")

    # --- Slot order for this scene ---
    slot_order = slot_order_for_scene(scene_num)   # [P2, P3, P4, P5] slot names
    active_slots = slot_order[:n_images]
    print(f"  Slot order: {slot_order}  ->  Active slots: {active_slots}")

    # --- Split tokens among all active elements ---
    phrases = split_tokens_n(tokens, n_active)
    host_phrase  = phrases[0]
    image_phrases = phrases[1:]

    print(f"  host_right (P1)  : '{host_phrase[:60]}'")
    for i, (slot, phrase) in enumerate(zip(active_slots, image_phrases)):
        print(f"  img_{slot:12s} (P{i+2}): '{phrase[:60]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for w in host_phrase.split() if clean_word(w)]
    for phrase in image_phrases:
        built_clean.extend([clean_word(w) for w in phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    # --- Build images list ---
    images_out = []
    for i, (slot, phrase) in enumerate(zip(active_slots, image_phrases)):
        images_out.append({
            "img_id":   f"img_{slot}",
            "slot":     slot,
            "priority": i + 2,
            "phrase":   phrase,
        })

    out = {
        "scene_id":   scene_id,
        "layout":     "25",
        "scene_text": scene_text,
        "n_active":   n_active,
        "n_images":   n_images,
        "host_phrase": host_phrase,
        "slot_order": slot_order,
        "images":     images_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_25_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
