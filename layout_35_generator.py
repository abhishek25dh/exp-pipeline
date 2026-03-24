"""
Layout 35 Generator - Host Left (Static) + Text Right
======================================================
Canvas: 1920 x 1080

Layout (from scene_16_director.json reference):
  [ host_explaining.png (x=456, y=566, scale=0.759) ]  [ text_right (x=1372, y=446) ]

Priority: P1=host (fires first), P2=text_right (fires last).

Text config:
  TEXT_SAFE_W=850 (from original placeholder: 8 chars * 25 * scale 4.267 = 853px).
  MAX_CHARS_LINE=34, LINE_SPACING=110.
  Multi-line: consistent scale from longest line (prevents short lines rendering huge).
  Vertical: text center y=446, canvas safe 30-1050. Up to 7 lines before top overflow.
"""

import json
import random
import re
import sys
from pathlib import Path

HOST = {"x": 456, "y": 566, "scale": 0.759, "filename": "host_explaining.png"}

TEXT_X        = 1372
TEXT_BASE_Y   = 446
TEXT_SAFE_W   = 850
AVG_CHAR_W    = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 34
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

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_35_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data        = json.loads(step2_path.read_text(encoding="utf-8"))
    n_active    = data.get("n_active", 1)
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type   = rng.choice(TEXT_TYPES)
    host_phrase = data.get("host_phrase", "")
    text_phrase = data.get("text_phrase", "")

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
    # P1=host, P2=text_right
    _n_slots = 1 + (1 if text_phrase and n_active >= 2 else 0)
    _phrases = allot_phrases(_tokens, _n_slots)
    _host_phrase = _phrases[0]
    _text_phrase = _phrases[1] if _n_slots >= 2 else None

    elements = []

    # P1 — host (fires first, static asset)
    if _host_phrase is not None:
        elements.append({
            "element_id":   f"host_{scene_id}",
            "type":         "image",
            "phrase":       _host_phrase,
            "text_content": "",
            "x":            HOST["x"],
            "y":            HOST["y"],
            "scale":        HOST["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     HOST["filename"],
            "description":  "",
            "reason":       "Layout 35 host (P1, static local asset)",
        })
    print(f"  host:  x={HOST['x']} y={HOST['y']} scale={HOST['scale']} phrase='{(_host_phrase or '')[:60]}'")

    # P2 — text_right (fires last, right column)
    if _text_phrase is not None:
        lines = split_into_lines(text_phrase)
        y_pos = line_y_positions(len(lines), TEXT_BASE_Y)
        # Consistent scale: compute from longest line to prevent short lines rendering huge
        scale = compute_text_scale(max(lines, key=len))

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            eid = f"text_right_{scene_id}" if len(lines) == 1 else f"text_right_l{i + 1}"
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
                "reason":       f"Layout 35 text right (P2, line {i + 1}/{len(lines)})",
            })
            print(f"  text_l{i+1}: type={text_type} scale={scale} y={y} phrase='{line[:55]}'")

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
