"""
Layout 26 Generator - Text Top-Left + 2 Images Below + 4 Images Right (2x2)
=============================================================================
Canvas: 1920 x 1080

Layout (from scene_7_director.json reference):
  [ TEXT      (x=553, y=400)           ]   [ img_R_TL (x=1314, y=440,  s=0.244) ]
  [ img_BL (x=287, y=813, s=0.421) ]       [ img_R_TR (x=1629, y=445,  s=0.246) ]
  [ img_BR (x=886, y=810, s=0.419) ]       [ img_R_BL (x=1326, y=812,  s=0.244) ]
                                            [ img_R_BR (x=1620, y=820,  s=0.240) ]

Text type: seeded random per scene (text_highlighted / text_red / text_black).
Text scale: computed per phrase. Splits into multiple lines if > MAX_CHARS_LINE.
Text lines are stacked vertically, centered around TEXT_BASE_Y.
"""

import json
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------
TEXT_X        = 553
TEXT_BASE_Y   = 400
TEXT_SAFE_W   = 1000   # safe width for text in left portion (centered at x=553)
AVG_CHAR_W    = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W   # 40 chars at scale 1.0
LINE_SPACING  = 130
TEXT_TYPES    = ["text_highlighted", "text_red", "text_black"]

BELOW_GEOMETRY = {
    "left":  {"x": 287, "y": 813, "scale": 0.421},
    "right": {"x": 886, "y": 810, "scale": 0.419},
}

RIGHT_GEOMETRY = {
    "top_left":  {"x": 1314, "y": 440, "scale": 0.244},
    "top_right": {"x": 1629, "y": 445, "scale": 0.246},
    "bot_left":  {"x": 1326, "y": 812, "scale": 0.244},
    "bot_right": {"x": 1620, "y": 820, "scale": 0.240},
}


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
    """Scale for a single line guaranteed to fit within TEXT_SAFE_W."""
    n_chars   = max(1, len(phrase))
    n_words   = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def split_into_lines(phrase: str) -> list:
    """Split phrase into lines of at most MAX_CHARS_LINE chars each.
    Every line is strictly bounded — no absorb-overflow into the last line.
    At scale 1.0, each line <= MAX_CHARS_LINE chars = exactly TEXT_SAFE_W wide.
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


def get_slot_geometry(slot: str, group: str) -> dict:
    if group == "below":
        return BELOW_GEOMETRY[slot]
    return RIGHT_GEOMETRY[slot]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_26_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data       = json.loads(step2_path.read_text(encoding="utf-8"))
    text_phrase = data.get("text_phrase", "")
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type   = rng.choice(TEXT_TYPES)
    images      = data.get("images", [])

    if not text_phrase:
        print("Error: no text_phrase in Step 2 output.")
        return 1

    # ── Resilient: drop images with unknown geometry slots ─────────────────────
    _all_valid_slots = set(BELOW_GEOMETRY.keys()) | set(RIGHT_GEOMETRY.keys())
    _valid_images = [img for img in images if img.get("slot") in _all_valid_slots]
    if len(_valid_images) < len(images):
        print(f"   Warning: Layout 26 dropping {len(images) - len(_valid_images)} images with unknown slots.")
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
    n_tokens = len(_tokens)
    # Priority-based image dropping: each image needs ~2 tokens to be non-trivial.
    _n_active_imgs = min(len(images), max(1, (n_tokens - 1) // 2))
    # P1=text, P2..=active images
    _phrases = allot_phrases(_tokens, 1 + _n_active_imgs)
    _text_phrase  = _phrases[0]
    _img_phrases  = _phrases[1:]
    print(f"   Token budget: {n_tokens} tokens -> {_n_active_imgs} active images")

    elements = []

    # --- Text element (P1, fires first) ---
    if _text_phrase is not None:
        lines  = split_into_lines(text_phrase)
        y_pos  = text_line_y_positions(len(lines), TEXT_BASE_Y)

        for i, (line, y) in enumerate(zip(lines, y_pos)):
            scale = compute_text_scale(line)
            eid   = "text_top" if len(lines) == 1 else f"text_top_l{i + 1}"
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
                "reason":       f"Layout 26 top text (line {i + 1}/{len(lines)})",
            })
            print(f"  text_top_l{i+1}: type={text_type} scale={scale} y={y} phrase='{line[:50]}'")

    # --- Images (P2-P7, fire in priority order) ---
    for ii, img in enumerate(images[:_n_active_imgs]):
        _ip = _img_phrases[ii] if ii < len(_img_phrases) else None
        if _ip is None:
            continue
        slot  = img["slot"]
        group = img["group"]
        geo   = get_slot_geometry(slot, group)
        elements.append({
            "element_id":   f"img_{group}_{slot}_{scene_id}",
            "type":         "image",
            "phrase":       _ip,
            "text_content": "",
            "x":            geo["x"],
            "y":            geo["y"],
            "scale":        geo["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_{group}_{slot}_{scene_id}.jpg",
            "description":  img.get("img_description", ""),
            "reason":       f"Layout 26 {group} image (slot={slot}, priority={img['priority']})",
        })
        print(f"  img_{group}_{slot}: x={geo['x']} y={geo['y']} scale={geo['scale']} phrase='{img['phrase'][:50]}'")

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
