"""
Layout 38 Generator - Text Bottom Center (Fires First) + Two AI Images
=======================================================================
Canvas: 1920 x 1080

Layout (from scene_19_director.json reference):
  [ img_left  (x=415,  y=511, s=0.667) ]  [ img_right (x=1443, y=503, s=0.656) ]
  [          text_bottom_center (x=942, y=934)                                   ]

Priority: P1=text_bottom_center (fires first), P2=img_left, P3=img_right.

Text config (bottom center, narrow callout):
  TEXT_SAFE_W=350. AVG_CHAR_W=20 (mixed-case). MAX_CHARS_LINE=17. MAX_TEXT_SCALE=1.3.
  LINE_SPACING=70 (canvas 35px). MAX_LINES=3 (hard cap).
  Vertical: 3 lines centered at y=970 → positions 900,970,1040 (canvas 450,485,520).
  Images bottom at canvas≈426. Text top at canvas≈435. Bottom at canvas≈535 < 540.
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_X        = 942
TEXT_BASE_Y   = 970   # center of 3-line block; lines at 900,970,1040 (canvas 450,485,520)
TEXT_SAFE_W   = 350
AVG_CHAR_W    = 20    # mixed-case Comic Sans avg char width
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 17
MAX_TEXT_SCALE = 1.3  # caps text half-height to ~15px canvas, preventing bottom overflow
LINE_SPACING  = 70    # scene px between lines (canvas 35px); images bottom at canvas≈426
MAX_LINES     = 3     # 3 lines: canvas y=450,485,520 — all clear of images (426) and edge (540)
TEXT_TYPES    = ["text_highlighted", "text_red", "text_black"]

IMG_LEFT  = {"x": 415,  "y": 511, "scale": 0.667}
IMG_RIGHT = {"x": 1443, "y": 503, "scale": 0.656}


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
    return round(max(1.0, min(preferred, safe, MAX_TEXT_SCALE)), 3)


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
    # Hard cap: merge overflow into last line to stay within MAX_LINES
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [" ".join(lines[MAX_LINES - 1:])]
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

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_38_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data             = json.loads(step2_path.read_text(encoding="utf-8"))
    n_active         = data.get("n_active", 1)
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type        = rng.choice(TEXT_TYPES)
    text_phrase      = data.get("text_phrase", "")
    img_left_phrase  = data.get("img_left_phrase", "")
    img_right_phrase = data.get("img_right_phrase", "")

    if not text_phrase:
        print("Error: no text_phrase in Step 2 output.")
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
    # P1=text, P2=img_left, P3=img_right
    _phrases = allot_phrases(_tokens, n_active)
    _text_phrase  = _phrases[0] if len(_phrases) > 0 else None
    _img_l_phrase = _phrases[1] if len(_phrases) > 1 else None
    _img_r_phrase = _phrases[2] if len(_phrases) > 2 else None

    elements = []

    # P1 — text bottom center (fires first, narrow callout, consistent block scale)
    if _text_phrase is not None:
        lines = split_into_lines(text_phrase)
        y_pos = line_y_positions(len(lines), TEXT_BASE_Y)
        # Consistent scale: compute from longest line
        scale = compute_text_scale(max(lines, key=len))

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            eid = f"text_bc_{scene_id}" if len(lines) == 1 else f"text_bc_l{i + 1}_{scene_id}"
            elements.append({
                "element_id":   eid,
                "type":         text_type,
                "phrase":       line,
                "text_content": line.upper(),
                "x":            TEXT_X,
                "y":            y,
                "scale":        scale,
                "angle":        0,
                "animation":    "pop",
                "property":     "",
                "filename":     "",
                "description":  "",
                "reason":       f"Layout 38 text bottom center (P1, fires first, line {i + 1}/{len(lines)})",
            })
            print(f"  text_l{i+1}:   type={text_type} scale={scale} y={y} phrase='{line[:50]}'")

    # P2 — img_left
    if img_left_phrase and n_active >= 2 and _img_l_phrase is not None:
        elements.append({
            "element_id":   f"img_left_{scene_id}",
            "type":         "image",
            "phrase":       _img_l_phrase,
            "text_content": "",
            "x":            IMG_LEFT["x"],
            "y":            IMG_LEFT["y"],
            "scale":        IMG_LEFT["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_left_{scene_id}.jpg",
            "description":  data.get("img_left_description", ""),
            "reason":       "Layout 38 left image (P2, AI generated)",
        })
        print(f"  img_left:  x={IMG_LEFT['x']} y={IMG_LEFT['y']} phrase='{_img_l_phrase[:55]}'")

    # P3 — img_right
    if img_right_phrase and n_active == 3 and _img_r_phrase is not None:
        elements.append({
            "element_id":   f"img_right_{scene_id}",
            "type":         "image",
            "phrase":       _img_r_phrase,
            "text_content": "",
            "x":            IMG_RIGHT["x"],
            "y":            IMG_RIGHT["y"],
            "scale":        IMG_RIGHT["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_right_{scene_id}.jpg",
            "description":  data.get("img_right_description", ""),
            "reason":       "Layout 38 right image (P3, AI generated)",
        })
        print(f"  img_right: x={IMG_RIGHT['x']} y={IMG_RIGHT['y']} phrase='{_img_r_phrase[:55]}'")

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
