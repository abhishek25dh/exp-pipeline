"""
Layout 36 Generator - Host Right + Image Left + Arrow + Image Center + Text Bottom-Left
========================================================================================
Canvas: 1920 x 1080

Layout (from scene_17_director.json reference):
  [ img_left (x=277,  y=483, s=0.437)                                ] [ host (x=1497, y=559, s=1.608) ]
  [ arrow    (x=632,  y=482, s=0.2, angle=27) ]
  [ img_center (x=899, y=503, s=0.362)                               ]
  [ text_bottom_left (x=599, y=826)                                  ]

Priority: P1=host (fires first), P2=img_left, P3=arrow, P4=img_center, P5=text_bottom_left (fires last).

Text config (narrow bottom-left callout):
  TEXT_SAFE_W=490 (from original placeholder: 8 chars * 25 * scale 2.437 = 487px).
  MAX_CHARS_LINE=19, LINE_SPACING=110.
  Multi-line: consistent scale from longest line.
  Vertical: center y=826. MAX_LINES=5 (bottom at 826 + 4*55 = 1046 < 1050).
"""

import json
import random
import re
import sys
from pathlib import Path

HOST       = {"x": 1497, "y": 559,  "scale": 0.75, "filename": "host_explaining.png"}
IMG_LEFT   = {"x": 277,  "y": 483,  "scale": 0.437}
ARROW      = {"x": 632,  "y": 482,  "scale": 0.2,   "angle": 27, "filename": "arrow.png"}
IMG_CENTER = {"x": 899,  "y": 503,  "scale": 0.362}

TEXT_X        = 599
TEXT_BASE_Y   = 826
TEXT_SAFE_W   = 490
AVG_CHAR_W    = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 19
LINE_SPACING  = 110
TEXT_TYPES    = ["text_highlighted", "text_red", "text_black"]


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

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_36_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data              = json.loads(step2_path.read_text(encoding="utf-8"))
    n_active          = data.get("n_active", 1)
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type         = rng.choice(TEXT_TYPES)
    host_phrase       = data.get("host_phrase", "")
    img_left_phrase   = data.get("img_left_phrase", "")
    arrow_phrase      = data.get("arrow_phrase", "")
    img_center_phrase = data.get("img_center_phrase", "")
    text_phrase       = data.get("text_phrase", "")

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
    # P1=host, P2=img_left, P3=arrow, P4=img_center, P5=text (only when n_active==5)
    _phrases = allot_phrases(_tokens, n_active)
    _pi = 0

    elements = []

    # P1 — host (fires first, right side, static asset)
    _p1 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if _p1 is not None:
        elements.append({
            "element_id":   f"host_{scene_id}",
            "type":         "image",
            "phrase":       _p1,
            "text_content": "",
            "x":            HOST["x"],
            "y":            HOST["y"],
            "scale":        HOST["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     HOST["filename"],
            "description":  "",
            "reason":       "Layout 36 host (P1, right side, static asset)",
        })
    print(f"  host:       x={HOST['x']} y={HOST['y']} scale={HOST['scale']} phrase='{(_p1 or '')[:55]}'")

    # P2 — img_left (AI image)
    _p2 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if img_left_phrase and n_active >= 2 and _p2 is not None:
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
            "reason":       "Layout 36 left image (P2, AI generated)",
        })
        print(f"  img_left:   x={IMG_LEFT['x']} y={IMG_LEFT['y']} phrase='{_p2[:55]}'")

    # P3 — arrow (static asset, fires with transition phrase)
    _p3 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if arrow_phrase and n_active >= 4 and _p3 is not None:
        elements.append({
            "element_id":   f"arrow_{scene_id}",
            "type":         "arrow",
            "phrase":       _p3,
            "text_content": "",
            "x":            ARROW["x"],
            "y":            ARROW["y"],
            "scale":        ARROW["scale"],
            "angle":        ARROW["angle"],
            "animation":    "pop",
            "property":     "",
            "filename":     ARROW["filename"],
            "description":  "",
            "reason":       "Layout 36 arrow (P3, static asset, angle=27)",
        })
        print(f"  arrow:      x={ARROW['x']} y={ARROW['y']} angle={ARROW['angle']} phrase='{_p3[:55]}'")

    # P4 — img_center (AI image)
    _p4 = _phrases[_pi] if _pi < len(_phrases) else None
    _pi += 1
    if img_center_phrase and n_active >= 4 and _p4 is not None:
        elements.append({
            "element_id":   f"img_center_{scene_id}",
            "type":         "image",
            "phrase":       _p4,
            "text_content": "",
            "x":            IMG_CENTER["x"],
            "y":            IMG_CENTER["y"],
            "scale":        IMG_CENTER["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_center_{scene_id}.jpg",
            "description":  data.get("img_center_description", ""),
            "reason":       "Layout 36 center image (P4, AI generated)",
        })
        print(f"  img_center: x={IMG_CENTER['x']} y={IMG_CENTER['y']} phrase='{_p4[:55]}'")

    # P5 — text bottom-left (fires last, narrow callout, consistent block scale)
    _p5 = _phrases[_pi] if _pi < len(_phrases) else None
    if text_phrase and n_active == 5 and _p5 is not None:
        lines = split_into_lines(text_phrase)
        y_pos = line_y_positions(len(lines), TEXT_BASE_Y)
        # Consistent scale: compute from longest line (prevents short lines rendering oversized)
        scale = compute_text_scale(max(lines, key=len))

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            eid = f"text_bl_{scene_id}" if len(lines) == 1 else f"text_bl_l{i + 1}_{scene_id}"
            elements.append({
                "element_id":   eid,
                "type":         text_type,
                "phrase":       _p5 if i == 0 else "",
                "text_content": line.upper(),
                "x":            TEXT_X,
                "y":            y,
                "scale":        scale,
                "angle":        0,
                "animation":    "pop",
                "property":     "",
                "filename":     "",
                "description":  "",
                "reason":       f"Layout 36 text bottom-left (P5, line {i + 1}/{len(lines)})",
            })
            print(f"  text_l{i+1}:    type={text_type} scale={scale} y={y} phrase='{line[:45]}'")

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
