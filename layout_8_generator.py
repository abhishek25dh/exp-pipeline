"""
Layout 8 Generator - Timeline Path
==================================
Director space: 1920×1080

Layout features:
1. main_title at the top center.
2. 3 or 4 sequential events (steps).
3. Steps are plotted equidistantly across the X-axis.
4. Steps follow a zigzag across the Y-axis (high / low alternating).
5. Arrows connect adjacent steps (decorative, no timing).

Text scale is computed per step using the STEP-LOCAL safe width
(limited by distance to canvas edge AND distance to neighboring step),
so edge steps never overflow the canvas.
Text x is clamped with a safe margin so nothing is cut off.
"""

import json
import math
import os
import random
import re
import sys
from math import ceil

W, H = 1920, 1080
SAFE_MARGIN = 70       # px from canvas edge — text never closer than this
MARGIN_X    = 200      # leftmost / rightmost step center x
IMG_SCALE   = 0.25
IMG_SIZE    = 1024 * IMG_SCALE   # 256 px
ARROW_SCALE = 0.20

# Vertical layout — chosen so arrows at midpoint (y_high+y_low)/2 = 530
# stay well clear of text which is TEXT_Y_OFFSET below each image center
Y_HIGH         = 380   # image center y for even-indexed steps
Y_LOW          = 680   # image center y for odd-indexed steps
TEXT_Y_OFFSET  = 270   # px below image center → text at 650 (high) / 950 (low)
                       # arrow midpoint = (380+680)/2 = 530 → 120 px above high text ✓

# Title scale: use canvas-width formula since title is centered
_TITLE_MAX_SCALE = 2.4
_TITLE_MIN_SCALE = 1.2
AVG_CHAR_W = 30        # Comic Sans MS scene px per char at scale=1.0


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


def _title_scale(phrase: str) -> float:
    n = max(1, len(phrase))
    safe = (W - 2 * SAFE_MARGIN) / (AVG_CHAR_W * n)
    preferred = min(_TITLE_MAX_SCALE, 18.0 / max(1, len(phrase.split())))
    return round(max(_TITLE_MIN_SCALE, min(_TITLE_MAX_SCALE, preferred, safe)), 3)


def _step_text_scale(phrase: str, step_x: float, x_spacing: float) -> float:
    """
    Scale from the step-column width (x_spacing).
    Canvas-edge overflow is handled separately by _clamp_text_x — so edge steps
    aren't double-penalised here.
    Short phrases (few words) scale up freely; long phrases scale down to fit.
    """
    n_chars = max(1, len(phrase))
    n_words = max(1, len(phrase.split()))

    # Column safe width = step spacing minus a small buffer each side
    safe_w = max(100.0, x_spacing - 40)
    safe      = safe_w / (AVG_CHAR_W * n_chars)
    preferred = min(2.5, 14.0 / n_words)   # short phrases can grow up to 2.5
    return round(max(0.75, min(safe, preferred)), 3)


def _clamp_text_x(nominal_x: float, phrase: str, scale: float) -> int:
    """Shift text centre so the rendered text stays within the safe canvas area."""
    half_w = len(phrase) * AVG_CHAR_W * scale / 2.0
    lo = SAFE_MARGIN + half_w
    hi = W - SAFE_MARGIN - half_w
    clamped = max(lo, min(nominal_x, hi))
    # ceil when pushed left (so left edge stays >= SAFE_MARGIN), floor otherwise
    return ceil(clamped) if clamped >= lo - 0.01 and nominal_x < lo else int(clamped)


def make_el(eid, etype, phrase, x, y, scale, angle=0, animation="pop",
            prop="", filename="", description="", text_content=None):
    return {
        "element_id":  eid,
        "type":        etype,
        "phrase":      phrase,
        "text_content": text_content if text_content is not None
                        else (phrase if etype.startswith("text") else ""),
        "filename":    filename,
        "description": description,
        "x":   int(x),
        "y":   int(y),
        "scale": scale,
        "angle": angle,
        "animation": animation,
        "property":  prop,
        "reason":    "",
    }


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fallback_description(img_phrase, txt_phrase):
    phrase = f"{img_phrase} {txt_phrase}".strip()[:80]
    return (f"A 2D colorful cartoon graphic of objects related to '{phrase}' "
            f"on a pure white background. "
            f"No text, no letters, no numbers, no watermarks.")


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s1_path = f"assets/tmp/{sid}_layout_8_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_8_step_2_tmp.json"
    odir    = "assets/directorscript"
    opath   = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    s1 = load_json(s1_path)
    if s1 is None:
        print(f"Error: {s1_path} not found. Run Step 1 first.")
        return 1
    s2 = load_json(s2_path)

    main_title = (s1.get("main_title") or "The Process").strip()
    steps = s1.get("steps", [])
    if len(steps) < 1:
        print(f"Error: Layout 8 requires at least 1 step, found {len(steps)}.")
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
    # P1=title, then P2/P3 per step (img+txt), arrows keep phrase=""
    _num_steps = len(steps)
    _n_slots = 1 + _num_steps * 2
    n_tokens = len(_tokens)
    n_active = min(_n_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_n_slots} active slots")
    _phrases = allot_phrases(_tokens, n_active)
    # Pad with None so indices beyond n_active are skipped
    _phrases += [None] * (_n_slots - n_active)
    _title_phrase = _phrases[0] or ""
    _step_phrases = _phrases[1:]  # [step0_img, step0_txt, step1_img, step1_txt, ...]

    script = {"scene_id": sid, "elements": []}
    els    = script["elements"]

    # ── Title ──────────────────────────────────────────────────────────────
    ts = _title_scale(_title_phrase or main_title)
    els.append(make_el(
        "title_timeline", "text_black", _title_phrase,
        W / 2, 130, ts,
        animation="pop", text_content=(_title_phrase or main_title).upper(),
    ))

    num_steps = len(steps)
    x_spacing = (W - 2 * MARGIN_X) / max(1, num_steps - 1)

    coords = []
    for i, step in enumerate(steps):
        x = MARGIN_X + i * x_spacing
        y = Y_HIGH if (i % 2 == 0) else Y_LOW
        coords.append({"x": x, "y": y})

        step_id    = step.get("step_id", f"step_{i + 1}")
        img_phrase = _step_phrases[i * 2] if (i * 2) < len(_step_phrases) else None
        txt_phrase = _step_phrases[i * 2 + 1] if (i * 2 + 1) < len(_step_phrases) else None
        if img_phrase is None and txt_phrase is None:
            continue

        text_type = "text_black"
        if i == 1:
            text_type = "text_red"
        if i == num_steps - 1:
            text_type = "text_highlighted"

        img_data = image_map.get(step_id) or {
            "visual_description": fallback_description(img_phrase or "", txt_phrase or ""),
            "is_realistic": False,
        }
        is_real = img_data.get("is_realistic", False)

        # ── Image ──────────────────────────────────────────────────────────
        if img_phrase is not None:
            els.append(make_el(
                f"img_{step_id}", "image", img_phrase,
                x, y, IMG_SCALE,
                animation="pop",
                prop="shadow" if is_real else "",
                filename=f"{step_id}_img.jpg",
                description=img_data.get("visual_description", ""),
            ))

        # ── Text label (below image, canvas-safe) ─────────────────────────
        if txt_phrase is not None:
            txt_scale = _step_text_scale(txt_phrase, x, x_spacing)
            text_x    = _clamp_text_x(x, txt_phrase, txt_scale)
            text_y    = y + TEXT_Y_OFFSET

            # Clamp text_y: bottom of text must not exceed safe bottom margin
            text_y = min(text_y, H - SAFE_MARGIN - 30)

            els.append(make_el(
                f"txt_{step_id}", text_type, txt_phrase,
                text_x, text_y, txt_scale,
                animation="pop",
            ))

    # ── Decorative arrows ──────────────────────────────────────────────────
    # Arrows are purely decorative (no timing phrase needed).
    # Position at geometric midpoint between adjacent step image centres.
    for i in range(num_steps - 1):
        p1, p2 = coords[i], coords[i + 1]
        mid_x = (p1["x"] + p2["x"]) / 2
        mid_y = (p1["y"] + p2["y"]) / 2   # = (380+680)/2 = 530 — clears text zone
        dx = p2["x"] - p1["x"]
        dy = p2["y"] - p1["y"]
        angle_deg = math.degrees(math.atan2(dy, dx))

        els.append(make_el(
            f"arrow_{i}_{i + 1}", "arrow", "",
            mid_x, mid_y, ARROW_SCALE,
            angle=int(angle_deg),
            animation="pop",
            filename="arrow.png",
            description="Connecting steps",
        ))

    with open(opath, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)

    num_imgs  = sum(1 for e in els if e["type"] == "image")
    num_arrws = sum(1 for e in els if e["type"] == "arrow")
    print(f"\nSaved: {opath}")
    print(f"   {num_imgs} images | {num_arrws} arrows | {len(els)} total elements")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
