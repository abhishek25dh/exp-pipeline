"""
Layout 27 Generator - Host Mid + Text Left + Text Right
========================================================
Canvas: 1920 x 1080

Layout (from scene_8_director.json reference):
  [ text_left  (x=404,  y=425) ]  [ HOST (x=964, y=576, s=0.75) ]  [ text_right (x=1542, y=426) ]

Host: static local asset -- emotion-matched filename (host_happy/sad/explaining/angry.png).
Text: seeded random type per scene (text_highlighted / text_red / text_black).
Text scale: computed per line (capped to TEXT_SAFE_W_SIDE, min scale 1.0).
Text wraps to multiple lines if phrase exceeds MAX_CHARS_LINE chars.
"""

import json
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------
HOST_X, HOST_Y, HOST_SCALE = 964, 576, 0.75

TEXT_LEFT_X,  TEXT_LEFT_BASE_Y  = 404,  425
TEXT_RIGHT_X, TEXT_RIGHT_BASE_Y = 1542, 426

# Safe width for side text (bounded by host's horizontal extent)
TEXT_SAFE_W_SIDE = 500
AVG_CHAR_W       = 30
MAX_CHARS_LINE   = TEXT_SAFE_W_SIDE // AVG_CHAR_W   # 20 chars at scale 1.0
LINE_SPACING     = 130

SLOT_X = {"left": TEXT_LEFT_X,  "right": TEXT_RIGHT_X}
SLOT_Y = {"left": TEXT_LEFT_BASE_Y, "right": TEXT_RIGHT_BASE_Y}
TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]


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
    safe      = TEXT_SAFE_W_SIDE / (AVG_CHAR_W * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def split_into_lines(phrase: str) -> list:
    """Split phrase into lines of at most MAX_CHARS_LINE chars each.
    Every line is strictly bounded — no absorb-overflow into the last line.
    At scale 1.0, each line <= MAX_CHARS_LINE chars = exactly TEXT_SAFE_W_SIDE wide.
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


def text_line_y_positions(n_lines: int, base_y: int) -> list:
    if n_lines == 1:
        return [base_y]
    total = (n_lines - 1) * LINE_SPACING
    start = base_y - total // 2
    return [start + i * LINE_SPACING for i in range(n_lines)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_27_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data          = json.loads(step2_path.read_text(encoding="utf-8"))
    host_phrase   = data.get("host_phrase", "")
    host_filename = data.get("host_filename", "host_explaining.png")
    host_emotion  = data.get("host_emotion", "explaining")
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type     = rng.choice(TEXT_TYPES)
    texts         = data.get("texts", [])

    if not host_phrase:
        print("Error: no host_phrase in Step 2 output.")
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
    # P1=host (highest priority), P2=text_left, P3=text_right (lowest priority)
    _total_slots = 1 + len(texts)
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _phrases = _all_phrases + [None] * (_total_slots - n_active)
    _host_phrase = _phrases[0]
    _txt_phrases = _phrases[1:]

    elements = []

    # --- Host (P1, fires first) ---
    if _host_phrase is not None:
        elements.append({
            "element_id":   f"img_host_mid_{scene_id}",
            "type":         "image",
            "phrase":       _host_phrase,
            "text_content": "",
            "x":            HOST_X,
            "y":            HOST_Y,
            "scale":        HOST_SCALE,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     host_filename,
            "description":  "",
            "reason":       f"Layout 27 host (center, emotion={host_emotion})",
        })
    print(f"  host_mid: {host_filename}  x={HOST_X} y={HOST_Y} scale={HOST_SCALE} phrase='{(_host_phrase or '')[:50]}'")

    # --- Text elements (P2, P3) ---
    for ti, txt in enumerate(texts):
        _tp = _txt_phrases[ti] if ti < len(_txt_phrases) else None
        if _tp is None:
            continue
        slot   = txt["slot"]
        phrase = txt["phrase"]
        base_x = SLOT_X[slot]
        base_y = SLOT_Y[slot]

        lines = split_into_lines(phrase)
        y_pos = text_line_y_positions(len(lines), base_y)

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            scale = compute_text_scale(line)
            eid   = f"text_{slot}_{scene_id}" if len(lines) == 1 else f"text_{slot}_l{i+1}_{scene_id}"
            elements.append({
                "element_id":   eid,
                "type":         text_type,
                "phrase":       _tp if i == 0 else "",
                "text_content": line.upper(),
                "x":            base_x,
                "y":            y,
                "scale":        scale,
                "angle":        0,
                "animation":    "pop",
                "property":     "",
                "filename":     "",
                "description":  "",
                "reason":       f"Layout 27 {slot} text (P{txt['priority']}, line {i+1}/{len(lines)})",
            })
            print(f"  text_{slot}_l{i+1}: type={text_type} scale={scale} y={y} phrase='{line[:45]}'")

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
