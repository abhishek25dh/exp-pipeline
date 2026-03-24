"""
Layout 22 Generator — Text Only
=================================
Canvas: 1920 × 1080

All lines are centered horizontally (x=960).
Lines are distributed evenly around the vertical center (y=540).
Line spacing = 150 scene px.

Text Type Dynamism: seeded-random per scene — all lines in the same scene
share the same type (consistent look), but varies across scenes.
"""

import json
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas constants
# ---------------------------------------------------------------------------
CANVAS_CX    = 960
CANVAS_CY    = 540
LINE_SPACING = 150   # scene px between consecutive line centers
TEXT_TYPES   = ["text_highlighted", "text_red", "text_black"]
AVG_CHAR_W   = 30    # Comic Sans uppercase, fontSize=40, in scene px at scale=1
TEXT_SAFE_W  = 1800  # safe width (1920 minus 60px margin each side)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def allot_phrases(tokens, n_slots):
    n = len(tokens)
    if n == 0:
        return [None] * n_slots
    results = []
    t = 0
    for i in range(n_slots):
        remaining_tokens = n - t
        remaining_slots  = n_slots - i
        if remaining_tokens <= 0:
            results.append(None)
        else:
            give = max(1, remaining_tokens // remaining_slots)
            if i == n_slots - 1:
                give = remaining_tokens
            results.append(" ".join(tokens[t: t + give]))
            t += give
    return results


def compute_text_scale(phrase: str) -> float:
    n_chars   = max(1, len(phrase))
    n_words   = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def pick_text_type(scene_num: str) -> str:
    """Seeded-random text type — reproducible per scene, varies across scenes."""
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def line_y_positions(n: int) -> list:
    """
    Return y-coordinates for n lines, centered around CANVAS_CY.
    Example:
      n=1 → [540]
      n=2 → [465, 615]
      n=3 → [390, 540, 690]
      n=4 → [315, 465, 615, 765]
    """
    total_height = (n - 1) * LINE_SPACING
    first_y      = CANVAS_CY - total_height // 2
    return [first_y + i * LINE_SPACING for i in range(n)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_22_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: {step1_path} not found. Run Step 1 first.")
        return 1

    data      = json.loads(step1_path.read_text(encoding="utf-8"))
    n_lines   = data.get("n_lines", 1)
    lines     = data.get("lines", [])

    if not lines:
        print("Error: no lines in Step 1 output.")
        return 1

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    _prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    _scene_text = ""
    if _prompt_path.exists():
        try:
            _scene_text = _strip_scene_prefix(
                json.loads(_prompt_path.read_text(encoding="utf-8")).get("prompt", "")
            )
        except Exception:
            pass
    _tokens = _scene_text.split()
    _total_slots = len(lines)
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _phrases = _all_phrases + [None] * (_total_slots - n_active)

    text_type  = pick_text_type(scene_num)
    y_positions = line_y_positions(n_lines)
    elements   = []

    # Uniform scale from longest line keeps all lines visually consistent
    all_phrases = [l["phrase"] for l in lines]
    longest = max(all_phrases, key=len) if all_phrases else ""
    uniform_scale = compute_text_scale(longest)

    print(f"  n_lines={n_lines}  scale={uniform_scale}  type={text_type}")

    for i, line in enumerate(lines):
        _phrase = _phrases[i] if i < len(_phrases) else None  # None for inactive slots
        if _phrase is None:
            continue
        phrase = line["phrase"]
        y      = y_positions[i]

        elements.append({
            "element_id":   f"text_line_{i + 1}",
            "type":         text_type,
            "phrase":       _phrase,
            "text_content": phrase,
            "x":            CANVAS_CX,
            "y":            y,
            "scale":        uniform_scale,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     "",
            "description":  "",
            "reason":       f"Text line {i + 1} of {n_lines}",
        })

        print(f"  line {i + 1}: y={y}  '{phrase}'")

    # --- Write director JSON ---
    out_dir  = Path("assets/directorscript")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_director.json"
    out_path.write_text(
        json.dumps({"scene_id": scene_id, "elements": elements}, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved: {out_path}  ({len(elements)} element(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
