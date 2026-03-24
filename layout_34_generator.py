"""
Layout 34 Generator - Image Left + Image Right + Text Center (x2) + Image Bottom
==================================================================================
Canvas: 1920 x 1080

Layout (from scene_15_director.json reference):
  [ img_left (x=361, y=559, s=0.604) ]  [ text_1 (x=973, y=338) ]  [ img_right (x=1582, y=564, s=0.598) ]
                                         [ text_2 (x=976, y=486) ]
                                          [ img_bottom (x=978, y=794, s=0.399) ]

Priority order: P1=img_left, P2=img_right, P3=text_1, P4=text_2, P5=img_bottom.
Text config: TEXT_SAFE_W=450 (center gap, derived from original placeholder scale 2.24 × 8 chars × 25 = 448px),
             MAX_CHARS_LINE=18, LINE_SPACING=100.
"""

import json
import random
import re
import sys
from pathlib import Path

IMG_LEFT   = {"x": 361,  "y": 559, "scale": 0.604}
IMG_RIGHT  = {"x": 1582, "y": 564, "scale": 0.598}
TEXT_1_X   = 973
TEXT_1_BASE_Y = 338
TEXT_2_X   = 976
TEXT_2_BASE_Y = 486
IMG_BOTTOM = {"x": 978,  "y": 794, "scale": 0.399}

TEXT_SAFE_W    = 450
AVG_CHAR_W     = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 18
LINE_SPACING   = 100
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]


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


def add_text_elements(elements, phrase, text_type, x, base_y, label, scene_id, priority):
    """Returns the last y position used, or None if phrase is empty."""
    if not phrase:
        return None
    lines = split_into_lines(phrase)
    y_pos = line_y_positions(len(lines), base_y)
    # Consistent scale across all lines: use the longest line to prevent shorter lines rendering huge
    scale = compute_text_scale(max(lines, key=len))
    for i, (line, y) in enumerate(zip(lines, y_pos)):
        eid   = label if len(lines) == 1 else f"{label}_l{i + 1}"
        elements.append({
            "element_id":   eid,
            "type":         text_type,
            "phrase":       line,
            "text_content": line.upper(),
            "x":            x,
            "y":            y,
            "scale":        scale,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     "",
            "description":  "",
            "reason":       f"Layout 34 {label} (P{priority}, line {i + 1}/{len(lines)})",
        })
        print(f"  {label}_l{i+1}: type={text_type} scale={scale} y={y} phrase='{line[:55]}'")
    return y_pos[-1]


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_34_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data             = json.loads(step2_path.read_text(encoding="utf-8"))
    n_active         = data.get("n_active", 1)
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type        = rng.choice(TEXT_TYPES)
    img_left_phrase  = data.get("img_left_phrase",   "")
    img_right_phrase = data.get("img_right_phrase",  "")
    text_1_phrase    = data.get("text_1_phrase",     "")
    text_2_phrase    = data.get("text_2_phrase",     "")
    img_bottom_phrase = data.get("img_bottom_phrase", "")

    if not img_left_phrase:
        print("Error: no img_left_phrase in Step 2 output.")
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
    # P1=img_left, P2=img_right, P3=text_1, P4=text_2, P5=img_bottom
    _phrases = allot_phrases(_tokens, n_active)
    _pi = 0

    elements = []

    # P1 — img_left
    _p1 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if _p1 is not None:
        elements.append({
            "element_id":   f"img_left_{scene_id}",
            "type":         "image",
            "phrase":       _p1,
            "text_content": "",
            "x":            IMG_LEFT["x"],
            "y":            IMG_LEFT["y"],
            "scale":        IMG_LEFT["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_left_{scene_id}.jpg",
            "description":  data.get("img_left_description", ""),
            "reason":       "Layout 34 left image (P1)",
        })
    print(f"  img_left:   x={IMG_LEFT['x']} y={IMG_LEFT['y']} phrase='{(_p1 or '')[:55]}'")

    # P2 — img_right
    _p2 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if img_right_phrase and n_active >= 2 and _p2 is not None:
        elements.append({
            "element_id":   f"img_right_{scene_id}",
            "type":         "image",
            "phrase":       _p2,
            "text_content": "",
            "x":            IMG_RIGHT["x"],
            "y":            IMG_RIGHT["y"],
            "scale":        IMG_RIGHT["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_right_{scene_id}.jpg",
            "description":  data.get("img_right_description", ""),
            "reason":       "Layout 34 right image (P2)",
        })
        print(f"  img_right:  x={IMG_RIGHT['x']} y={IMG_RIGHT['y']} phrase='{_p2[:55]}'")

    # P3 + P4 — text blocks: place adaptively within safe zone above img_bottom
    _p3 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    _p4 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    text_1_active = bool(text_1_phrase and n_active >= 3 and _p3 is not None)
    text_2_active = bool(text_2_phrase and n_active >= 4 and _p4 is not None)

    if text_1_active or text_2_active:
        img_half_h  = int(1024 * IMG_BOTTOM["scale"] / 2)
        safe_top    = 80
        safe_bot    = IMG_BOTTOM["y"] - img_half_h - 30   # 590 - 30 = 560
        available_h = safe_bot - safe_top

        t1_lines = split_into_lines(text_1_phrase) if text_1_active else []
        t2_lines = split_into_lines(text_2_phrase) if text_2_active else []

        # Slots: each line is a slot; one extra gap slot between the two blocks
        n_slots = len(t1_lines) + len(t2_lines) + (1 if t1_lines and t2_lines else 0)
        spacing = min(LINE_SPACING, available_h // max(1, n_slots - 1))
        spacing = max(45, spacing)

        # Center the whole block vertically in the safe zone
        total_span = (n_slots - 1) * spacing
        start_y    = safe_top + max(0, (available_h - total_span) // 2)

        # Assign y positions
        t1_y = [start_y + i * spacing for i in range(len(t1_lines))]
        gap_offset = len(t1_lines) + 1   # +1 for the gap slot
        t2_y = [start_y + (gap_offset + i) * spacing for i in range(len(t2_lines))]

        if text_1_active:
            t1_scale = compute_text_scale(max(t1_lines, key=len))
            for i, (line, y) in enumerate(zip(t1_lines, t1_y)):
                eid = f"text_1_l{i+1}" if len(t1_lines) > 1 else "text_1"
                elements.append({
                    "element_id": eid, "type": text_type, "phrase": _p3 if i == 0 else "",
                    "text_content": line.upper(), "x": TEXT_1_X, "y": y,
                    "scale": t1_scale, "angle": 0, "animation": "pop",
                    "property": "", "filename": "", "description": "",
                    "reason": f"Layout 34 text_1 (P3, line {i+1}/{len(t1_lines)})",
                })
                print(f"  text_1_l{i+1}: scale={t1_scale} y={y} phrase='{line[:55]}'")

        if text_2_active:
            t2_scale = compute_text_scale(max(t2_lines, key=len))
            for i, (line, y) in enumerate(zip(t2_lines, t2_y)):
                eid = f"text_2_l{i+1}" if len(t2_lines) > 1 else "text_2"
                elements.append({
                    "element_id": eid, "type": text_type, "phrase": _p4 if i == 0 else "",
                    "text_content": line.upper(), "x": TEXT_2_X, "y": y,
                    "scale": t2_scale, "angle": 0, "animation": "pop",
                    "property": "", "filename": "", "description": "",
                    "reason": f"Layout 34 text_2 (P4, line {i+1}/{len(t2_lines)})",
                })
                print(f"  text_2_l{i+1}: scale={t2_scale} y={y} phrase='{line[:55]}'")

    # P5 — img_bottom (conclusion, fires last)
    _p5 = _phrases[_pi] if _pi < len(_phrases) else None
    if img_bottom_phrase and n_active >= 5 and _p5 is not None:
        elements.append({
            "element_id":   f"img_bottom_{scene_id}",
            "type":         "image",
            "phrase":       _p5,
            "text_content": "",
            "x":            IMG_BOTTOM["x"],
            "y":            IMG_BOTTOM["y"],
            "scale":        IMG_BOTTOM["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_bottom_{scene_id}.jpg",
            "description":  data.get("img_bottom_description", ""),
            "reason":       "Layout 34 bottom image (P5, conclusion)",
        })
        print(f"  img_bottom: x={IMG_BOTTOM['x']} y={IMG_BOTTOM['y']} phrase='{_p5[:55]}'")

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
