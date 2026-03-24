"""
Layout 22 Step 1 — Text-Only Line Splitter
===========================================
The entire scene voiceover is displayed as text.
If the full phrase would overflow the canvas at min readable scale (1.0),
it is split into 2, 3, or 4 equal-ish lines until it fits.

Priority: every token must appear (tiling). No elements are ever dropped.
Splitting is deterministic — prefer sentence boundaries, then equal split.
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants (must match generator)
# ---------------------------------------------------------------------------
AVG_CHAR_W_SCENE = 25    # Comic Sans uppercase fontSize=40 in scene px at scale=1
TEXT_SAFE_W      = 1800  # scene px safe width
MIN_SCALE        = 1.0
MAX_LINES        = 4


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def safe_scale_for(phrase: str) -> float:
    n_chars = max(1, len(phrase))
    return TEXT_SAFE_W / (AVG_CHAR_W_SCENE * n_chars)


def preferred_scale_for(phrase: str) -> float:
    n_words = max(1, len(phrase.split()))
    return min(3.5, 18.0 / n_words)


def resolved_scale_for(phrase: str) -> float:
    return min(preferred_scale_for(phrase), safe_scale_for(phrase))


# ---------------------------------------------------------------------------
# Token partitioning
# ---------------------------------------------------------------------------

def split_tokens(tokens: list, n: int) -> list:
    """
    Split tokens into n equal-ish parts.
    Prefer cutting at sentence boundaries within ±2 tokens of the ideal split point.
    Returns list of phrase strings.
    """
    total = len(tokens)
    if n == 1:
        return [" ".join(tokens)]

    target = total / n
    phrases = []
    pos = 0

    for part in range(n):
        if part == n - 1:
            # Last part gets all remaining tokens
            phrases.append(" ".join(tokens[pos:]))
            break

        ideal = round(pos + target * (part + 1 - part))
        ideal = pos + max(1, round((total - pos) / (n - part)))

        # Search ±2 tokens around ideal for a sentence boundary
        best_end = ideal
        for offset in range(-2, 3):
            candidate = ideal + offset
            if pos < candidate <= total - (n - part - 1):
                if ends_sentence(tokens[candidate - 1]):
                    best_end = candidate
                    break

        # Clamp: must leave at least 1 token for each remaining part
        best_end = max(pos + 1, min(best_end, total - (n - part - 1)))
        phrases.append(" ".join(tokens[pos:best_end]))
        pos = best_end

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

    n = len(tokens)
    print(f"  Tokens: {n}")

    # Try increasing line counts until scale fits
    chosen_lines  = None
    chosen_scale  = None

    for n_lines in range(1, MAX_LINES + 1):
        lines = split_tokens(tokens, n_lines)
        # Scale is limited by the longest line
        longest     = max(lines, key=len)
        scale       = resolved_scale_for(longest)
        clamped     = max(MIN_SCALE, scale)
        print(f"  n_lines={n_lines}: longest={len(longest)} chars, scale={round(scale,3)}")
        if scale >= MIN_SCALE:
            chosen_lines = lines
            chosen_scale = round(clamped, 3)
            break

    if chosen_lines is None:
        # Even 4 lines still overflows — use 4 lines at min scale
        chosen_lines = split_tokens(tokens, MAX_LINES)
        longest      = max(chosen_lines, key=len)
        chosen_scale = round(max(MIN_SCALE, resolved_scale_for(longest)), 3)

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = []
    for p in chosen_lines:
        built_clean.extend([clean_word(w) for w in p.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    lines_out = [{"line_num": i + 1, "phrase": p} for i, p in enumerate(chosen_lines)]

    out = {
        "scene_id":   scene_id,
        "layout":     "22",
        "scene_text": scene_text,
        "n_lines":    len(chosen_lines),
        "scale":      chosen_scale,
        "lines":      lines_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_22_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    for line in lines_out:
        print(f"  line {line['line_num']}: scale={chosen_scale}  '{line['phrase']}'")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
