"""
Layout 21 Step 1 — Priority-Based Phrase Assignment
====================================================
Visual structure:
    [      main_text (top center)      ]
                         \
                      [arrow]
                      [image]

Priority order (Priority-Based Approach):
  P1: main_text        — always present, gets first chunk of tokens
  P2: group_1 (arrow + image) — ATOMIC: both appear or neither does
      - arrow fires first (phrase spoken just before image appears)
      - image fires second

Token threshold:
  N < 5  → P1 only  (all tokens go to main_text)
  N >= 5 → P1 + group_1  (text + arrow + image)

The group is always atomic — we never emit an arrow without its image.
All tokens are always fully covered (tiling layout).
"""

import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


CONNECTORS = {
    "and", "but", "so", "or", "then", "when", "while", "because",
    "into", "to", "with", "that", "which", "as", "if", "after", "before",
}

MIN_TOKENS_FULL = 5   # minimum tokens to include the arrow+image group


# ---------------------------------------------------------------------------
# Heading span
# ---------------------------------------------------------------------------

def find_heading_end(tokens: list, has_group: bool) -> int:
    """
    How many tokens go to main_text.
    Rule: heading phrase MUST end at a sentence boundary (independently readable).
    - No group: all tokens.
    - With group: preferred range 2-8 tokens; extend forward if no boundary found.
    """
    n = len(tokens)
    if not has_group:
        return n

    hard_max = max(2, n - 3)   # leave at least 3 tokens for arrow(1) + image(2)

    # 1. Search preferred short range [2, min(8, hard_max)]
    for i in range(2, min(8, hard_max) + 1):
        if ends_sentence(tokens[i - 1]):
            return i

    # 2. Extend forward up to target+5 (cap prevents too many heading lines)
    target = max(2, min(8, n // 2))
    forward_cap = min(target + 5, hard_max)
    for i in range(8, forward_cap + 1):
        if ends_sentence(tokens[i - 1]):
            return i

    # 3. Next sentence too far — use previous sentence end (backward from target)
    for i in range(target - 1, 1, -1):
        if ends_sentence(tokens[i - 1]):
            return max(2, i)

    # 4. No sentence boundary at all — use proportional fallback
    return max(2, min(hard_max, n // 2))


# ---------------------------------------------------------------------------
# Arrow / image split within the group
# ---------------------------------------------------------------------------

def split_group(group_tokens: list) -> tuple:
    """
    Split group tokens into (arrow_phrase, img_phrase).
    Arrow: 1-2 tokens (prefer connector word). Image: rest (min 2 tokens).
    """
    n = len(group_tokens)
    if n == 0:
        return ("", "")
    if n == 1:
        # Can't form a valid group — shouldn't happen given MIN_TOKENS_FULL
        return ("", group_tokens[0])
    if n == 2:
        return (group_tokens[0], group_tokens[1])
    if n == 3:
        return (group_tokens[0], " ".join(group_tokens[1:]))

    # 4+ tokens: prefer 2-token arrow if first word is a connector
    arrow_len = 1
    if clean_word(group_tokens[0]) in CONNECTORS:
        arrow_len = 2

    return (
        " ".join(group_tokens[:arrow_len]),
        " ".join(group_tokens[arrow_len:]),
    )


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

    n         = len(tokens)
    has_group = n >= MIN_TOKENS_FULL
    print(f"  Tokens: {n}  ->  Group active: {has_group}")

    # --- Phrase assignment ---
    main_end    = find_heading_end(tokens, has_group)
    main_phrase = " ".join(tokens[:main_end])

    group = None
    if has_group:
        group_tokens              = tokens[main_end:]
        arrow_phrase, img_phrase  = split_group(group_tokens)
        group = {
            "group_id":     "group_1",
            "arrow_phrase": arrow_phrase,
            "img_phrase":   img_phrase,
        }

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for w in main_phrase.split() if clean_word(w)]
    if group:
        for key in ("arrow_phrase", "img_phrase"):
            built_clean.extend([clean_word(w) for w in group[key].split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    # --- Output ---
    out = {
        "scene_id":         scene_id,
        "layout":           "21",
        "scene_text":       scene_text,
        "has_group":        has_group,
        "main_text_phrase": main_phrase,
        "group":            group,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_21_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"  main_text : '{main_phrase}'")
    if group:
        print(f"  arrow     : '{group['arrow_phrase']}'")
        print(f"  image     : '{group['img_phrase']}'")
    else:
        print("  (no group — text only)")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
