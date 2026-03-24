"""
Layout 24 Generator - Two Images + Bottom Text
===============================================
Canvas: 1920 x 1080

Full layout:
  [ img_left (x=550) ]  [ img_right (x=1370) ]   y=380, scale=0.42
  [            bottom text (x=960)            ]   y=870

1-image layout (P2 only, centered):
  [          img_center (x=960)               ]   y=380, scale=0.50
  [            bottom text (x=960)            ]   y=870

Text-only layout:
  [            bottom text (x=960)            ]   y=540 (vertically centered)

Text Type Dynamism: seeded random per scene.
Text scale: 1.0 minimum; if phrase exceeds canvas width, split into multiple lines.
"""

import json
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas constants
# ---------------------------------------------------------------------------
AVG_CHAR_W_SCENE = 30
TEXT_SAFE_W      = 1800
MAX_CHARS_LINE   = TEXT_SAFE_W // AVG_CHAR_W_SCENE   # 60 chars at scale 1.0
LINE_SPACING     = 130   # px between text lines when split
TEXT_TYPES       = ["text_highlighted", "text_red", "text_black"]

# Image positions
IMG_LEFT_X,  IMG_LEFT_Y,  IMG_LEFT_SCALE  = 550,  380, 0.42
IMG_RIGHT_X, IMG_RIGHT_Y, IMG_RIGHT_SCALE = 1370, 380, 0.42
IMG_CENTER_X, IMG_CENTER_Y, IMG_CENTER_SCALE = 960, 380, 0.50

# Text positions
TEXT_X              = 960
TEXT_Y_WITH_IMAGES  = 870   # bottom when images are present
TEXT_Y_ALONE        = 540   # vertically centered when text-only


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


def pick_text_type(scene_num: str) -> str:
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def compute_text_scale(phrase: str) -> float:
    """Scale for a phrase that is guaranteed to fit on one line (<= MAX_CHARS_LINE)."""
    n_chars   = max(1, len(phrase))
    n_words   = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W_SCENE * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def split_into_lines(phrase: str) -> list:
    """
    Split phrase into lines of at most MAX_CHARS_LINE characters each.
    Splits at word boundaries; tries to keep lines balanced.
    """
    if len(phrase) <= MAX_CHARS_LINE:
        return [phrase]

    words = phrase.split()
    lines = []
    current = []
    current_len = 0

    for word in words:
        add_len = len(word) + (1 if current else 0)
        if current and current_len + add_len > MAX_CHARS_LINE:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += add_len

    if current:
        lines.append(" ".join(current))

    return lines


def text_line_y_positions(n_lines: int, base_y: int) -> list:
    """Return y positions for n_lines centered around base_y."""
    if n_lines == 1:
        return [base_y]
    total = (n_lines - 1) * LINE_SPACING
    start = base_y - total // 2
    return [start + i * LINE_SPACING for i in range(n_lines)]


def img_coords(slot: str, n_images: int) -> tuple:
    """Return (x, y, scale) for an image slot."""
    if n_images == 1:
        return IMG_CENTER_X, IMG_CENTER_Y, IMG_CENTER_SCALE
    return (
        (IMG_LEFT_X,  IMG_LEFT_Y,  IMG_LEFT_SCALE)  if slot == "left"
        else (IMG_RIGHT_X, IMG_RIGHT_Y, IMG_RIGHT_SCALE)
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_24_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data         = json.loads(step2_path.read_text(encoding="utf-8"))
    n_images     = data.get("n_images", 0)
    images       = data.get("images", [])
    text_phrase  = data.get("text_phrase", "")

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
    # P1..Pn = images (in priority order), P(n+1) = text (lowest priority, drops first)
    _total_slots = len(images) + 1
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _phrases = _all_phrases + [None] * (_total_slots - n_active)
    _img_phrases  = _phrases[:len(images)]
    _text_phrase  = _phrases[len(images)]

    text_type = pick_text_type(scene_num)
    base_y    = TEXT_Y_WITH_IMAGES if n_images > 0 else TEXT_Y_ALONE
    elements  = []

    # --- Images first (they fire before the text in timing) ---
    for ii, img in enumerate(images):
        _ip = _img_phrases[ii] if ii < len(_img_phrases) else None
        if _ip is None:
            continue
        slot    = img["slot"]
        x, y, s = img_coords(slot, n_images)
        elements.append({
            "element_id":   f"img_{slot}_{scene_id}",
            "type":         "image",
            "phrase":       _ip,
            "text_content": "",
            "x":            x,
            "y":            y,
            "scale":        s,
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_{slot}_{scene_id}.jpg",
            "description":  img.get("img_description", ""),
            "reason":       f"Layout 24 image ({slot}, priority {img['priority']})",
        })
        print(f"  img_{slot}: x={x} y={y} scale={s} phrase='{img['phrase'][:50]}'")

    # --- Bottom text: split into lines if too long for scale 1.0 ---
    if _text_phrase is not None:
        lines   = split_into_lines(text_phrase)
        y_pos   = text_line_y_positions(len(lines), base_y)

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            scale = compute_text_scale(line)
            eid   = "text_bottom" if len(lines) == 1 else f"text_bottom_l{i + 1}"
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
                "reason":       f"Bottom anchor text for layout 24 (line {i + 1}/{len(lines)})",
            })
            print(f"  text_bottom_l{i + 1}: type={text_type} scale={scale} y={y} phrase='{line[:50]}'")

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
