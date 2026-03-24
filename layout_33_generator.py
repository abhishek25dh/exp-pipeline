"""
Layout 33 Generator - Text Heading Top + Image Left + Arrow + Image Right Bottom
=================================================================================
Canvas: 1920 x 1080

Layout (from scene_14_director.json reference):
  [          TEXT HEADING (x=929, y=332, text_highlighted)         ]
  [ img_left (x=363,  y=711, s=0.488) ] [ arrow (x=1019, y=681, s=0.374) ]
  [                                   ] [ img_right (x=1520, y=700, s=0.486) ]

Heading: full-canvas width (TEXT_SAFE_W=1800, MAX_CHARS_LINE=72).
Heading lines stacked vertically centered at y=332.
Vertical safe: MAX_LINES=3 (bottom of 3-line block = 442 < image top ~467).
"""

import json
import random
import re
import sys
from pathlib import Path

HEADING_X      = 929
HEADING_BASE_Y = 332
TEXT_SAFE_W    = 1800
AVG_CHAR_W     = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 72
LINE_SPACING   = 110
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]

IMG_LEFT  = {"x": 363,  "y": 711, "scale": 0.488}
ARROW     = {"x": 1019, "y": 681, "scale": 0.374, "filename": "arrow.png"}
IMG_RIGHT = {"x": 1520, "y": 700, "scale": 0.486}


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


def split_into_lines(phrase: str) -> list:
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
    if n_lines == 1:
        return [base_y]
    total_span = (n_lines - 1) * LINE_SPACING
    start = base_y - total_span // 2
    return [start + i * LINE_SPACING for i in range(n_lines)]


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_33_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data = json.loads(step2_path.read_text(encoding="utf-8"))
    n_active         = data.get("n_active", 1)
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type        = rng.choice(TEXT_TYPES)
    heading_phrase   = data.get("heading_phrase", "")
    img_left_phrase  = data.get("img_left_phrase", "")
    arrow_phrase     = data.get("arrow_phrase", "")
    img_right_phrase = data.get("img_right_phrase", "")

    if not heading_phrase:
        print("Error: no heading_phrase in Step 2 output.")
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
    # P1=heading, P2=img_left, P3=arrow, P4=img_right (only when n_active==4)
    _phrases = allot_phrases(_tokens, n_active)
    _pi = 0

    elements = []

    # P1 — heading text (fires first)
    _ph = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    lines = split_into_lines(heading_phrase)
    y_pos = line_y_positions(len(lines), HEADING_BASE_Y)
    for i, (line, y) in enumerate(zip(lines, y_pos)):
        scale = compute_text_scale(line)
        eid   = "text_heading" if len(lines) == 1 else f"text_heading_l{i + 1}"
        elements.append({
            "element_id":   eid,
            "type":         text_type,
            "phrase":       _ph if i == 0 else "",
            "text_content": line.upper(),
            "x":            HEADING_X,
            "y":            y,
            "scale":        scale,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     "",
            "description":  "",
            "reason":       f"Layout 33 heading (P1, line {i + 1}/{len(lines)})",
        })
        print(f"  heading_l{i+1}: type={text_type} scale={scale} y={y} phrase='{line[:55]}'")

    # P2 — img_left
    _p2 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if img_left_phrase and _p2 is not None:
        elements.append({
            "element_id":   f"img_left_{scene_id}",
            "type":         "image",
            "phrase":       _p2,
            "text_content": "",
            "x":            IMG_LEFT["x"],
            "y":            IMG_LEFT["y"],
            "scale":        IMG_LEFT["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_left_{scene_id}.jpg",
            "description":  data.get("img_left_description", ""),
            "reason":       "Layout 33 left image (P2)",
        })
        print(f"  img_left:  x={IMG_LEFT['x']} y={IMG_LEFT['y']} phrase='{_p2[:55]}'")

    # P3 — arrow
    _p3 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if arrow_phrase and n_active == 4 and _p3 is not None:
        elements.append({
            "element_id":   f"arrow_{scene_id}",
            "type":         "arrow",
            "phrase":       _p3,
            "text_content": "",
            "x":            ARROW["x"],
            "y":            ARROW["y"],
            "scale":        ARROW["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     ARROW["filename"],
            "description":  "",
            "reason":       "Layout 33 arrow (P3, static local asset)",
        })
        print(f"  arrow:     x={ARROW['x']} y={ARROW['y']} phrase='{_p3[:55]}'")

    # P4 — img_right
    _p4 = _phrases[_pi] if _pi < len(_phrases) else None
    if img_right_phrase and n_active == 4 and _p4 is not None:
        elements.append({
            "element_id":   f"img_right_{scene_id}",
            "type":         "image",
            "phrase":       _p4,
            "text_content": "",
            "x":            IMG_RIGHT["x"],
            "y":            IMG_RIGHT["y"],
            "scale":        IMG_RIGHT["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_right_{scene_id}.jpg",
            "description":  data.get("img_right_description", ""),
            "reason":       "Layout 33 right image (P4)",
        })
        print(f"  img_right: x={IMG_RIGHT['x']} y={IMG_RIGHT['y']} phrase='{_p4[:55]}'")

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
