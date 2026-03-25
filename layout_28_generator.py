"""
Layout 28 Generator - Two Images Side-by-Side + Punchline Text Bottom
======================================================================
Canvas: 1920 x 1080

Layout (from scene_9_director.json reference):
  [ img_left  (x=493,  y=475, scale=0.616) ]  [ img_right (x=1371, y=465, scale=0.609) ]
  [             TEXT PUNCHLINE (x=943, y=922, bottom-center)                            ]

Text is a punchline (fires last):
  - Full-canvas safe width: TEXT_SAFE_W = 1800 scene px
  - MAX_CHARS_LINE = 72 (at scale 1.0, line exactly fills safe width)
  - Lines stacked vertically centered around TEXT_BASE_Y = 922
  - Scale computed per line — never below 1.0 (wraps instead)
  - LINE_SPACING = 100 keeps all lines within canvas even at 4 lines
"""

import json
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------
IMG_GEOMETRY = {
    "left":  {"x": 493,  "y": 475, "scale": 0.616},
    "right": {"x": 1371, "y": 465, "scale": 0.609},
}

TEXT_X         = 943
TEXT_BASE_Y    = 922
TEXT_SAFE_W    = 1800   # full canvas safe width (centered, 60px margin each side)
AVG_CHAR_W     = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 72 chars at scale 1.0
LINE_SPACING   = 100
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]


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
    """Scale for a single line that fits within TEXT_SAFE_W."""
    n_chars   = max(1, len(phrase))
    n_words   = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def split_into_lines(phrase: str) -> list:
    """Split phrase into lines of at most MAX_CHARS_LINE chars each.
    Every line strictly bounded — no absorb-overflow into the last line.
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
    """Return y positions for n_lines centered around base_y."""
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

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_28_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data        = json.loads(step2_path.read_text(encoding="utf-8"))
    images      = data.get("images", [])
    text_phrase = data.get("text_phrase", "")
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type   = rng.choice(TEXT_TYPES)

    # ── Resilient: drop images with unknown geometry slots ─────────────────────
    _valid_images = [img for img in images if img.get("slot") in IMG_GEOMETRY]
    if len(_valid_images) < len(images):
        print(f"   Warning: Layout 28 dropping {len(images) - len(_valid_images)} images with unknown slots.")
        images = _valid_images

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
    # P1=img_left, P2=img_right, P3=text
    _sorted_images = sorted(images, key=lambda x: x["priority"])
    _total_slots = len(_sorted_images) + 1
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _img_phrases  = [_all_phrases[i] if i < n_active else None for i in range(len(_sorted_images))]
    _text_phrase  = _all_phrases[len(_sorted_images)] if len(_sorted_images) < n_active else None

    elements = []

    # --- Images (P1, P2 — fire first, in priority order) ---
    for ii, img in enumerate(_sorted_images):
        _ip = _img_phrases[ii] if ii < len(_img_phrases) else None
        if _ip is None:
            continue
        slot = img["slot"]
        geo  = IMG_GEOMETRY[slot]
        elements.append({
            "element_id":   f"img_{slot}_{scene_id}",
            "type":         "image",
            "phrase":       _ip,
            "text_content": "",
            "x":            geo["x"],
            "y":            geo["y"],
            "scale":        geo["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_{slot}_{scene_id}.jpg",
            "description":  img.get("img_description", ""),
            "reason":       f"Layout 28 image (slot={slot}, priority={img['priority']})",
        })
        print(f"  img_{slot}: x={geo['x']} y={geo['y']} scale={geo['scale']} phrase='{_ip[:50]}'")

    # --- Punchline text (P3 — fires last) ---
    if _text_phrase is not None:
        lines = split_into_lines(_text_phrase)
        y_pos = text_line_y_positions(len(lines), TEXT_BASE_Y)

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            scale = compute_text_scale(line)
            eid   = "text_punchline" if len(lines) == 1 else f"text_punchline_l{i + 1}"
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
                "reason":       f"Layout 28 punchline text (line {i + 1}/{len(lines)})",
            })
            print(f"  text_punchline_l{i+1}: type={text_type} scale={scale} y={y} phrase='{line[:60]}'")

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
