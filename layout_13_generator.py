"""
Layout 13 Generator - Staircase / Step Up
=========================================
Director space: 1920x1080

Layout:
- 4 steps ascending diagonally from bottom-left to top-right
- Each step: image + label below image
- No title and no numeric badges to preserve phrase correctness
"""

import json
import os
import random
import re
import sys

W, H = 1920, 1080

# X and Y positions for each step (bottom-left -> top-right)
X_STEPS = [260, 660, 1060, 1460]
Y_STEPS = [840, 660, 480, 300]

# Compute max image radius from geometry: no canvas overflow, no neighbour overlap
def _max_img_radius():
    min_r = float('inf')
    for i, (x, y) in enumerate(zip(X_STEPS, Y_STEPS)):
        min_r = min(min_r,
                    x - 40, W - x - 40,        # left/right canvas margin
                    y - 40, H - y - 40)          # top/bottom canvas margin
        if i < len(X_STEPS) - 1:
            dx = X_STEPS[i+1] - x
            dy = Y_STEPS[i+1] - y
            dist = (dx*dx + dy*dy) ** 0.5
            min_r = min(min_r, (dist - 20) / 2)  # 20px gap between adjacent images
    return int(min(min_r, 184))  # 184 → scale≈0.36 (user-verified max)

IMG_RADIUS = _max_img_radius()          # 184 px
IMG_SCALE  = round(IMG_RADIUS * 2 / 1024, 3)  # ≈0.359

LABEL_OFFSET_Y = IMG_RADIUS + 50  # label sits below image
CANVAS_MARGIN = 40
LABEL_SCALE = 1.4
LINE_HEIGHT = 66
CHAR_WIDTH = 30


def _strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def allot_phrases(tokens, n_slots):
    """Split tokens proportionally into n_slots phrases.
    Returns list[str|None] — None means element gets no phrase and must be skipped."""
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


def wrap_words(words, max_chars, min_words_per_line=2):
    if not words:
        return []
    lines = []
    i = 0
    while i < len(words):
        remaining = len(words) - i
        # If remaining words fit on one line, finish.
        if len(" ".join(words[i:])) <= max_chars:
            lines.append(words[i:])
            break

        # Greedy add until limit, but keep enough words for remaining lines.
        line = []
        while i < len(words):
            tentative = line + [words[i]]
            if len(" ".join(tentative)) > max_chars:
                break
            line = tentative
            i += 1
            remaining = len(words) - i
            if remaining <= min_words_per_line:
                continue
        if not line:
            line = [words[i]]
            i += 1
        lines.append(line)

    # Rebalance to avoid a single-word last line when possible.
    if len(lines) >= 2 and len(lines[-1]) == 1 and len(lines[-2]) >= (min_words_per_line + 1):
        lines[-1].insert(0, lines[-2].pop())
    return lines


def split_label_phrase(label_phrase, max_chars):
    words = label_phrase.split()
    if not words:
        return []
    if len(label_phrase) <= max_chars:
        return [label_phrase]

    lines = wrap_words(words, max_chars, min_words_per_line=2)
    return [" ".join(line) for line in lines]


def _adjusted_img_y(label_phrase, img_x, img_y, left_bound, right_bound):
    """Return a (possibly shifted-up) img_y so all label lines fit within the canvas.

    When the label block overflows the canvas bottom even at minimum scale, the image
    must move up — the text cannot be squeezed below it any further.  We solve for the
    largest img_y where:
        img_y + LABEL_OFFSET_Y + (n_lines - 1) * min_line_h  <=  H - CANVAS_MARGIN
    using n_lines computed from the safe column width (independent of img_y).
    The result is clamped so the image never leaves the canvas top.
    """
    if not label_phrase:
        return img_y
    safe_half = min(img_x - left_bound, right_bound - img_x)
    if safe_half <= 0:
        safe_half = min(img_x - CANVAS_MARGIN, (W - img_x) - CANVAS_MARGIN)
    safe_width = max(160, safe_half * 2)
    max_chars  = max(8, int(safe_width / CHAR_WIDTH))
    n_lines    = len(split_label_phrase(label_phrase, max_chars))
    min_line_h = LINE_HEIGHT * (1.05 / LABEL_SCALE)   # smallest possible line height
    # bottom of last line = img_y + LABEL_OFFSET_Y + (n_lines-1)*min_line_h
    max_img_y = H - CANVAS_MARGIN - LABEL_OFFSET_Y - int((n_lines - 1) * min_line_h)
    adjusted  = min(img_y, max_img_y)
    adjusted  = max(adjusted, CANVAS_MARGIN + IMG_RADIUS)   # never clip top of canvas
    if adjusted != img_y:
        print(f"     ^ img_y shifted {img_y}->{adjusted} to keep {n_lines}-line label in canvas")
    return adjusted


def compute_label_lines(label_phrase, x, base_y, img_y, scale, left_bound, right_bound):
    # Constrain label width between neighbor image blocks to avoid horizontal overlap.
    safe_half = min(x - left_bound, right_bound - x)
    if safe_half <= 0:
        safe_half = min(x - CANVAS_MARGIN, (W - x) - CANVAS_MARGIN)
    safe_width = max(160, safe_half * 2)
    char_px = CHAR_WIDTH * (scale / LABEL_SCALE)
    max_chars = max(8, int(safe_width / char_px))

    lines = split_label_phrase(label_phrase, max_chars)
    line_height = LINE_HEIGHT * (scale / LABEL_SCALE)
    block_height = line_height * len(lines)

    top_y = base_y
    bottom_y = base_y + block_height - line_height
    max_bottom = H - CANVAS_MARGIN
    min_top = img_y + IMG_RADIUS + 18

    if bottom_y > max_bottom:
        shift = bottom_y - max_bottom
        top_y -= shift
        bottom_y -= shift

    if top_y < min_top and len(lines) > 1 and scale > 1.05:
        # Try a smaller scale once to fit.
        return compute_label_lines(label_phrase, x, base_y, img_y, max(1.05, scale - 0.12), left_bound, right_bound)

    if top_y < min_top:
        top_y = min_top

    ys = [int(top_y + i * line_height) for i in range(len(lines))]
    return lines, ys, scale


def make_el(
    eid,
    etype,
    phrase,
    x,
    y,
    scale,
    angle=0,
    animation="pop",
    prop="",
    filename="",
    description="",
    text_content=None,
):
    return {
        "element_id": eid,
        "type": etype,
        "phrase": phrase,
        "text_content": text_content if text_content is not None else (phrase if etype.startswith("text") else ""),
        "filename": filename,
        "description": description,
        "x": int(x),
        "y": int(y),
        "scale": scale,
        "angle": angle,
        "animation": animation,
        "property": prop,
        "reason": "",
    }


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fallback_description(img_phrase, label_phrase):
    phrase = f"{img_phrase} {label_phrase}".strip()
    return f"A clean photo illustrating {phrase}, on a pure white background."


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s1_path = f"assets/tmp/{sid}_layout_13_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_13_step_2_tmp.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    s1 = load_json(s1_path)
    if s1 is None:
        print(f"Error: {s1_path} not found. Run Step 1 first.")
        return 1
    s2 = load_json(s2_path)

    steps = s1.get("steps", [])
    if len(steps) < 1:
        print(f"Error: Step 1 output is missing steps.")
        return 1

    image_map = {}
    if isinstance(s2, dict):
        for step in s2.get("detailed_steps", []):
            step_id = step.get("step_id")
            if step_id:
                image_map[step_id] = step.get("image", {})

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    # 2 slots per step: img + label
    _total_slots = len(steps) * 2
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _phrases = (_all_phrases + [None] * _total_slots)[:_total_slots]

    script = {"scene_id": sid, "elements": []}
    els = script["elements"]

    for i, step in enumerate(steps):
        img_x = X_STEPS[i]
        img_y = Y_STEPS[i]
        sid_step = step.get("step_id", f"step_{i+1}")
        _img_phrase   = _phrases[i * 2] if (i * 2) < len(_phrases) else None
        _label_phrase = _phrases[i * 2 + 1] if (i * 2 + 1) < len(_phrases) else None
        if _img_phrase is None and _label_phrase is None:
            continue
        img_phrase   = _img_phrase or ""
        label_phrase = _label_phrase or ""

        label_type = "text_black"
        if i == 2:
            label_type = "text_red"
        elif i == 3:
            label_type = "text_highlighted"

        img_data = image_map.get(sid_step, {})
        if not img_data:
            img_data = {
                "visual_description": fallback_description(img_phrase, label_phrase),
                "is_realistic": False,
            }
        is_real = img_data.get("is_realistic", False)

        # Bounds first — needed for img_y adjustment and label wrapping
        left_bound = CANVAS_MARGIN
        right_bound = W - CANVAS_MARGIN
        if i > 0:
            left_bound = max(left_bound, X_STEPS[i - 1] + IMG_RADIUS + CANVAS_MARGIN)
        if i < (len(X_STEPS) - 1):
            right_bound = min(right_bound, X_STEPS[i + 1] - IMG_RADIUS - CANVAS_MARGIN)

        # Shift image up if its label block would overflow the canvas bottom
        if _label_phrase is not None:
            img_y = _adjusted_img_y(label_phrase, img_x, img_y, left_bound, right_bound)

        # Image (fires on _img_phrase)
        if _img_phrase is not None:
            els.append(
                make_el(
                    f"img_{sid_step}",
                    "image",
                    _img_phrase,
                    img_x,
                    img_y,
                    IMG_SCALE,
                    animation="pop",
                    prop="shadow" if is_real else "",
                    filename=f"{sid_step}_img.jpg",
                    description=img_data.get("visual_description", ""),
                )
            )

        # Label below image (fires on _label_phrase, split into lines if needed)
        base_y = img_y + LABEL_OFFSET_Y

        if _label_phrase is not None:
            lines, ys, label_scale = compute_label_lines(
                label_phrase, img_x, base_y, img_y, LABEL_SCALE, left_bound, right_bound
            )
            for li, (line_text, ly) in enumerate(zip(lines, ys), start=1):
                eid = f"label_{sid_step}" if len(lines) == 1 else f"label_{sid_step}_{li}"
                els.append(
                    make_el(
                        eid,
                        label_type,
                        _label_phrase if li == 1 else "",
                        img_x,
                        ly,
                        label_scale,
                        animation="pop",
                        text_content=line_text,
                    )
                )

    with open(opath, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)

    print(f"\nSaved: {opath}")
    print(f"   {len(els)} elements total ({len(steps)} steps)")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
