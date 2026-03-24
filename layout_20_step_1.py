"""
Layout 20 Step 1 — Priority-Based Phrase Assignment
====================================================
Visual structure:
    [      main_text (top center)       ]
         /          |           \
   [arrow_2]   [arrow_1]   [arrow_3]
   [img_2  ]   [img_1  ]   [img_3  ]
    (left)      (center)     (right)

Priority order (highest → lowest):
  P1: main_text       — always present
  P2: group_1 center  — center arrow + center image
  P3: group_2 left    — left arrow   + left image
  P4: group_3 right   — right arrow  + right image

Token thresholds:
  N < 5  → P1 only
  N < 8  → P1 + P2
  N < 11 → P1 + P2 + P3
  N ≥ 11 → full layout (all 3 groups)

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
    t = (tok or "").rstrip()
    return bool(t) and t[-1] in ".!?"


# ---------------------------------------------------------------------------
# Priority-based group count
# ---------------------------------------------------------------------------

THRESHOLDS = [(5, 0), (8, 1), (11, 2)]   # (min_tokens_needed, groups_below_threshold)

def choose_n_groups(n_tokens: int) -> int:
    """Return number of active image groups based on available tokens."""
    for min_needed, groups_if_below in THRESHOLDS:
        if n_tokens < min_needed:
            return groups_if_below
    return 3


# ---------------------------------------------------------------------------
# Heading span selection
# ---------------------------------------------------------------------------

CONNECTORS = {
    "and", "but", "so", "or", "then", "when", "while", "because",
    "into", "to", "with", "that", "which", "as", "if", "after", "before",
}

def find_heading_end(tokens: list, n_groups: int) -> int:
    """
    Choose how many tokens the main_text heading gets.
    Rule: heading phrase MUST end at a sentence boundary (independently readable).
    - Preferred range: 2-8 tokens (short, punchy headline).
    - If no sentence end in preferred range, extend forward to next sentence end.
    - Hard ceiling: must leave at least 3 tokens per active group.
    """
    n = len(tokens)
    if n_groups == 0:
        return n

    hard_max = max(2, n - n_groups * 3)
    proportional = max(2, n // (n_groups + 1))

    # 1. Search preferred short range first [2, min(8, hard_max)]
    for i in range(2, min(8, hard_max) + 1):
        if ends_sentence(tokens[i - 1]):
            return i

    # 2. Extend forward up to proportional+5 (cap prevents too many heading lines)
    forward_cap = min(proportional + 5, hard_max)
    for i in range(8, forward_cap + 1):
        if ends_sentence(tokens[i - 1]):
            return i

    # 3. Next sentence too far — use previous sentence end (backward from proportional)
    for i in range(min(proportional, hard_max) - 1, 1, -1):
        if ends_sentence(tokens[i - 1]):
            return max(2, i)

    # 4. No sentence boundary at all — use proportional fallback
    return max(2, min(hard_max, proportional))


# ---------------------------------------------------------------------------
# Per-group arrow/image split
# ---------------------------------------------------------------------------

def split_group_tokens(group_tokens: list) -> tuple:
    """
    Split a group's tokens into (arrow_phrase, img_phrase).
    Arrow gets 1-2 tokens; image gets the rest.
    Prefers connector words at the start for the arrow span.
    """
    n = len(group_tokens)
    if n == 0:
        return ("", "")
    if n == 1:
        return ("", group_tokens[0])
    if n == 2:
        return (group_tokens[0], group_tokens[1])

    # Prefer 2-token arrow if the first token is a connector
    arrow_len = 1
    if n >= 4 and clean_word(group_tokens[0]) in CONNECTORS:
        arrow_len = 2

    arrow_phrase = " ".join(group_tokens[:arrow_len])
    img_phrase   = " ".join(group_tokens[arrow_len:])
    return (arrow_phrase, img_phrase)


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
    n_groups = choose_n_groups(n)
    print(f"  Tokens: {n}  ->  Active groups: {n_groups}")

    # --- Main text span ---
    main_end    = find_heading_end(tokens, n_groups)
    main_phrase = " ".join(tokens[:main_end])

    # --- Split remaining tokens into groups ---
    remaining = tokens[main_end:]
    m         = len(remaining)
    groups    = []

    if n_groups > 0:
        base  = m // n_groups
        extra = m % n_groups
        pos   = 0
        # Priority → visual position mapping
        positions = ["center", "left", "right"]

        for i in range(n_groups):
            size         = base + (1 if i < extra else 0)
            group_tokens = remaining[pos: pos + size]
            pos         += size

            arrow_phrase, img_phrase = split_group_tokens(group_tokens)
            groups.append({
                "group_id":     f"group_{i + 1}",
                "position":     positions[i],      # group_1=center, group_2=left, group_3=right
                "arrow_phrase": arrow_phrase,
                "img_phrase":   img_phrase,
            })

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for w in main_phrase.split() if clean_word(w)]
    for g in groups:
        for key in ("arrow_phrase", "img_phrase"):
            built_clean.extend([clean_word(w) for w in g[key].split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch — check phrase assignment logic.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    # --- Output ---
    out = {
        "scene_id":         scene_id,
        "layout":           "20",
        "scene_text":       scene_text,
        "n_groups":         n_groups,
        "main_text_phrase": main_phrase,
        "groups":           groups,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_20_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"  main_text : '{main_phrase}'")
    for g in groups:
        print(f"  {g['position']:6s} -> arrow='{g['arrow_phrase']}' | img='{g['img_phrase']}'")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
