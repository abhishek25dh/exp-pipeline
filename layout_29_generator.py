"""
Layout 29 Generator - Statement Stack (4 Text Lines, Alternating Black/Red)
============================================================================
Canvas: 1920 x 1080

Layout (from scene_10_director.json reference):
  [ TEXT 1 (text_black, x=964, y=282 ) ]
  [ TEXT 2 (text_red,   x=962, y=497 ) ]
  [ TEXT 3 (text_black, x=968, y=694 ) ]
  [ TEXT 4 (text_red,   x=948, y=925 ) ]

All elements centered on the canvas (x ≈ 960).
Types are position-fixed alternating (black/red/black/red).
Scale computed dynamically per phrase — never below 1.0.

If a phrase exceeds MAX_CHARS_LINE (72) it wraps into multiple sub-lines
centered around the slot's base y-position.  LINE_SPACING=100 keeps wrapped
lines well clear of adjacent slots (minimum gap ~97 scene px at 2 lines).

Safe gap check (worst case: 2 lines per slot, LINE_SPACING=100):
  slot1 (y=282) 2-line extent: [232, 332]  → gap to slot2 start [447]: 115 ✓
  slot2 (y=497) 2-line extent: [447, 547]  → gap to slot3 start [644]: 97  ✓
  slot3 (y=694) 2-line extent: [644, 744]  → gap to slot4 start [875]: 131 ✓
  slot4 (y=925) 2-line extent: [875, 975]  → bottom of canvas [1080]: 105 ✓
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas geometry (from scene_10_director.json reference)
# ---------------------------------------------------------------------------
SLOT_GEOMETRY = [
    {"x": 964, "y": 282},   # slot_1  text_black
    {"x": 962, "y": 497},   # slot_2  text_red
    {"x": 968, "y": 694},   # slot_3  text_black
    {"x": 948, "y": 925},   # slot_4  text_red
]

SLOT_TYPES = ["text_black", "text_red", "text_black", "text_red"]

TEXT_SAFE_W    = 1800
AVG_CHAR_W     = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 72 chars at scale 1.0
LINE_SPACING   = 100


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
    """Dynamic scale for a single line — aesthetic preference capped at safe width."""
    n_chars   = max(1, len(phrase))
    n_words   = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def split_into_lines(phrase: str) -> list:
    """Split phrase into lines of at most MAX_CHARS_LINE chars.
    Every line strictly bounded — no absorb-overflow anti-pattern.
    """
    if len(phrase) <= MAX_CHARS_LINE:
        return [phrase]

    words = phrase.split()
    lines, current, current_len = [], [], 0
    for word in words:
        add_len = len(word) + (1 if current else 0)
        if current and current_len + add_len > MAX_CHARS_LINE:
            lines.append(" ".join(current))
            current, current_len = [word], len(word)
        else:
            current.append(word)
            current_len += add_len
    if current:
        lines.append(" ".join(current))
    return lines


def line_y_positions(n_lines: int, base_y: int) -> list:
    """Y positions for n_lines centered around base_y."""
    if n_lines == 1:
        return [base_y]
    total_span = (n_lines - 1) * LINE_SPACING
    start = base_y - total_span // 2
    return [start + i * LINE_SPACING for i in range(n_lines)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_29_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data     = json.loads(step2_path.read_text(encoding="utf-8"))
    slots    = data.get("slots", [])

    if not slots:
        print("Error: no slots in Step 2 output.")
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
    _total_slots = len(SLOT_GEOMETRY)   # 4
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)

    # Build a priority-sorted slot list (priority 1..4 -> index 0..3)
    _sorted_slots = sorted(slots, key=lambda s: s["priority"])

    elements = []

    for si, slot in enumerate(_sorted_slots):
        _phrase = _all_phrases[si] if si < n_active else None
        if _phrase is None:
            continue

        idx     = slot["priority"] - 1          # 0-based index into geometry
        geo     = SLOT_GEOMETRY[idx]
        stype   = slot["type"]                  # text_black or text_red
        slot_id = slot["slot_id"]

        lines  = split_into_lines(_phrase)
        y_pos  = line_y_positions(len(lines), geo["y"])

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            scale = compute_text_scale(line)
            eid   = slot_id if len(lines) == 1 else f"{slot_id}_l{i + 1}"
            elements.append({
                "element_id":   eid,
                "type":         stype,
                "phrase":       line,
                "text_content": line.upper(),
                "x":            geo["x"],
                "y":            y,
                "scale":        scale,
                "angle":        0,
                "animation":    "pop",
                "property":     "",
                "filename":     "",
                "description":  "",
                "reason":       f"Layout 29 slot {idx + 1} (priority={slot['priority']}, line {i + 1}/{len(lines)})",
            })
            print(f"  {eid}: type={stype} scale={scale} x={geo['x']} y={y} phrase='{line[:60]}'")

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
