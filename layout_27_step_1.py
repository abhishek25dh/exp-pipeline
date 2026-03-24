"""
Layout 27 Step 1 - Host Mid + Text Left + Text Right
=====================================================
Visual structure:
  [ text_left (P2/P3) ]  [ HOST (P1, center) ]  [ text_right (P2/P3) ]

Priority order:
  P1: host character (mid) -- emotion determined by AI in step_2
  P2, P3: two text elements -- randomly assigned left/right slots per scene (seeded)

Token thresholds:
  N < 3  -> P1 only (host gets all tokens)
  N < 5  -> P1 + P2 (host + one text)
  N >= 5 -> all 3

Phrase rules:
  Host phrase: fires first, ends at sentence boundary (timing cue for host appearance).
  Text phrases: both must end at sentence boundary (Rule 6 — independently readable).
  Forward search capped at target+5 to prevent text from consuming too many tokens.

Text type: seeded random per scene (seed = scene_num * 7919).
Slot randomness: seeded per scene (seed = scene_num * 8537).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_TYPE_SEED = 7919
SLOT_SEED      = 8537
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]
TEXT_SLOTS     = ["left", "right"]


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


def shuffled_text_slots(scene_num: str) -> list:
    """Return ["left","right"] or ["right","left"] seeded per scene."""
    rng = random.Random(int(scene_num) * SLOT_SEED if scene_num.isdigit() else hash(scene_num))
    slots = TEXT_SLOTS[:]
    rng.shuffle(slots)
    return slots   # [P2_slot, P3_slot]


def find_phrase_end_sentence(tokens: list, target: int, max_end: int, forward_cap: int = 5) -> int:
    """
    Find phrase end at a sentence boundary.
    forward_cap: how far past target to search forward.
      - Use forward_cap=5 when splitting from the FULL script (Rule 6: budget control).
      - Use forward_cap=max_end when splitting WITHIN a fixed remaining bucket
        (we're dividing a fixed pool, not budgeting the whole script).
    Falls back to previous sentence end if forward cap exceeded.
    If no sentence boundary found anywhere, gives all tokens to this phrase.
    """
    forward_limit = min(target + forward_cap, max_end)
    for i in range(max(1, target), forward_limit + 1):
        if ends_sentence(tokens[i - 1]):
            return i
    # Forward cap exceeded — use previous sentence end
    for i in range(target - 1, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return max(1, i)
    # No sentence boundary anywhere — give all tokens to this phrase (whole block is one sentence)
    return max_end


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
    n_texts  = n_active - 1   # 0, 1, or 2
    print(f"  Tokens: {n}  ->  Active: {n_active} (1 host + {n_texts} text(s))")

    text_type = pick_text_type(scene_num)
    slots     = shuffled_text_slots(scene_num)
    active_slots = slots[:n_texts]
    print(f"  Text type: {text_type}  |  Slot order: {slots}  ->  Active: {active_slots}")

    # --- Phrase assignment ---
    # Layout 27 texts are SHORT callout elements (not full narration).
    # Target: each text gets ~N//6 tokens; host gets the bulk (~2/3).
    # This keeps text phrases short enough to fit in the side columns
    # (TEXT_SAFE_W_SIDE=500 scene px, MAX_CHARS_LINE=20).
    #
    # Each phrase (including host) ends at a sentence boundary (Rule 6).

    text_target_each = max(2, n // 6)   # short callout allocation per text

    if n_active == 1:
        host_phrase  = " ".join(tokens)
        text_phrases = []

    elif n_active == 2:
        # Host gets first ~5/6, one text gets last ~1/6
        host_target = max(1, n - text_target_each)
        max_host    = max(1, n - 1)
        host_end    = find_phrase_end_sentence(tokens, host_target, max_host)
        host_phrase  = " ".join(tokens[:host_end])
        text_phrases = [" ".join(tokens[host_end:])]

    else:
        # Host gets first ~4/6, texts each get ~1/6 of remaining
        host_target = max(1, n - 2 * text_target_each)
        max_host    = max(1, n - 2)
        host_end    = find_phrase_end_sentence(tokens, host_target, max_host)

        remaining = tokens[host_end:]
        m         = len(remaining)
        target_p2 = max(1, m // 2)
        # When splitting WITHIN the remaining bucket, allow searching the
        # entire remaining block for a sentence boundary so we don't cut
        # a single long sentence in half. Pass forward_cap=m to force
        # forward search up to the end.
        p2_end    = find_phrase_end_sentence(remaining, target_p2, m, forward_cap=m)

        host_phrase       = " ".join(tokens[:host_end])
        text_phrases_raw  = [
            " ".join(remaining[:p2_end]),
            " ".join(remaining[p2_end:]),
        ]
        # Drop empty phrases (e.g. when remaining is a single sentence, p2 takes it all)
        text_phrases = [p for p in text_phrases_raw if p.strip()]

    print(f"  host (P1)        : '{host_phrase[:60]}'")
    for i, (slot, phrase) in enumerate(zip(active_slots, text_phrases)):
        print(f"  text_{slot:5s} (P{i+2}): '{phrase[:60]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for w in host_phrase.split() if clean_word(w)]
    for phrase in text_phrases:
        built_clean.extend([clean_word(w) for w in phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    # --- Build text list ---
    texts_out = [
        {"text_id": f"text_{slot}", "slot": slot, "priority": i + 2, "phrase": phrase}
        for i, (slot, phrase) in enumerate(zip(active_slots, text_phrases))
    ]

    out = {
        "scene_id":   scene_id,
        "layout":     "27",
        "scene_text": scene_text,
        "n_active":   n_active,
        "host_phrase": host_phrase,
        "text_type":  text_type,
        "slot_order": slots,
        "texts":      texts_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_27_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
