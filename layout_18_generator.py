"""
Layout 18 Generator - Polaroid Wall
===================================
Director space: 1920x1080

Layout:
- Wall title at top center
- 4 polaroid images in a loose 2x2 arrangement with slight rotations
- Each polaroid has a handwritten-style caption below it, matching the rotation angle

Positions and rotations are HARDCODED (Safe Slots pattern - same philosophy as Layout 11).
Doing this ensures zero overlap and a natural polaroid-wall feel for any scene.
"""

import json
import os
import random
import re
import sys

W, H = 1920, 1080

IMG_SCALE = 0.24
IMG_RADIUS = int(1024 * IMG_SCALE / 2)  # 122 px

CAPTION_OFFSET = IMG_RADIUS + 62  # 184 px below image center

CHAR_PX    = 30    # Comic Sans fontSize=40, scene coords — wider than average
MARGIN     = 60    # min px from canvas edge to text (scene coords)
FONT_SIZE  = 40    # canvas fontSize (used for vertical height calc)
TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]

TITLE_X = W // 2
TITLE_Y = 80   # scene coords — moved down from 65 to give top-margin headroom

# Fixed polaroid positions and angles - do not change these, they are collision-safe
POLAROIDS = {
    "tl": {"x": 420, "y": 290, "angle": -9},
    "tr": {"x": 1500, "y": 270, "angle": 7},
    "bl": {"x": 390, "y": 760, "angle": 6},
    "br": {"x": 1530, "y": 780, "angle": -8},
}

# Vertical bounds for title: must fit between top canvas edge and first image row.
# canvas coords: multiply scene by 0.5.  Text half-height (canvas) = FONT_SIZE * (scale/2) / 2 = 10 * scale
_IMG_TOP_MIN_CANVAS = min(p["y"] for p in POLAROIDS.values()) / 2 - IMG_RADIUS / 2  # ≈74
_TITLE_Y_CANVAS     = TITLE_Y / 2   # 40
_VERT_MARGIN        = 15            # canvas px buffer between text and canvas edge / image
TITLE_HEIGHT_CAP = max(1.0, min(
    (_TITLE_Y_CANVAS - _VERT_MARGIN) / 10,               # from canvas top
    (_IMG_TOP_MIN_CANVAS - _VERT_MARGIN - _TITLE_Y_CANVAS) / 10  # to first image
))


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


def safe_scale(text, center_x, preferred_cap=2.5):
    """Formula-based scale: larger for short text, capped by column width.
    Uses CHAR_PX=30 (Comic Sans is wider than average).
    """
    chars   = max(1, len(text))
    n_words = max(1, len(text.split()))
    avail_half = min(center_x - MARGIN, W - center_x - MARGIN)
    avail_half = max(10, avail_half)
    canvas_safe = (2 * avail_half) / (chars * CHAR_PX)
    preferred   = min(preferred_cap, 14.0 / n_words)
    return round(max(1.0, min(preferred, canvas_safe)), 3)


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


def load_step1(step1_path):
    if not os.path.exists(step1_path):
        return None
    with open(step1_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_step2(step2_path):
    if not os.path.exists(step2_path):
        return None
    with open(step2_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fallback_description(img_phrase, cap_phrase):
    phrase = f"{img_phrase} {cap_phrase}".strip()
    return f"A realistic photo illustrating {phrase}, on a pure white background."


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s1_path = f"assets/tmp/{sid}_layout_18_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_18_step_2_tmp.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    s1 = load_step1(s1_path)
    s2 = load_step2(s2_path)
    if s1 is None and s2 is None:
        print(f"Error: {s2_path} not found. Run Step 1 (and Step 2 if desired).")
        return 1

    wall_title = ""
    if isinstance(s2, dict):
        wall_title = (s2.get("wall_title") or "").strip()
    if not wall_title and isinstance(s1, dict):
        wall_title = (s1.get("wall_title") or "").strip()
    if not wall_title:
        wall_title = "MEMORIES"

    phrase_map = {}
    if isinstance(s1, dict):
        for p in s1.get("polaroids", []):
            pid = p.get("polaroid_id")
            if pid:
                phrase_map[pid] = {
                    "img_phrase": p.get("img_phrase", ""),
                    "cap_phrase": p.get("cap_phrase", ""),
                }

    image_map = {}
    if isinstance(s2, dict):
        for p in s2.get("detailed_polaroids", []):
            pid = p.get("polaroid_id")
            if pid:
                image_map[pid] = p.get("image", {})

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    # P1=wall_title, then per polaroid: img + cap (4 polaroids = 8 slots)
    _pid_order = ["tl", "tr", "bl", "br"]
    _total_slots = 1 + len(_pid_order) * 2  # 9 slots
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    # Pad to full slot count so index arithmetic below stays unchanged
    _phrases = _all_phrases + [None] * (_total_slots - n_active)
    _title_phrase = _phrases[0]
    _polaroid_phrases = _phrases[1:]  # pairs [img, cap] per polaroid

    script = {"scene_id": sid, "elements": []}
    els = script["elements"]

    # -- Wall title ------------------------------------------------------------
    # Scale capped by BOTH horizontal overflow AND vertical bounds (title sits
    # between top canvas edge and first image row — very constrained zone).
    title_upper = wall_title.upper()
    title_scale = min(safe_scale(title_upper, TITLE_X, preferred_cap=3.5), TITLE_HEIGHT_CAP)
    title_scale = max(1.0, round(title_scale, 3))
    if _title_phrase is not None:
        els.append(
            make_el(
                "wall_title",
                "text_highlighted",
                _title_phrase,
                TITLE_X,
                TITLE_Y,
                title_scale,
                animation="slide_in_up",
                text_content=title_upper,
            )
        )

    # -- Polaroids -------------------------------------------------------------
    pid_order = ["tl", "tr", "bl", "br"]
    for pi, pid in enumerate(pid_order):
        pos = POLAROIDS[pid]
        px = pos["x"]
        py = pos["y"]
        angle = pos["angle"]

        _img_p = _polaroid_phrases[pi * 2] if (pi * 2) < len(_polaroid_phrases) else None
        _cap_p = _polaroid_phrases[pi * 2 + 1] if (pi * 2 + 1) < len(_polaroid_phrases) else None
        if _img_p is None and _cap_p is None:
            continue
        phrase_data = phrase_map.get(pid, {})
        img_phrase = phrase_data.get("img_phrase", "A Memory")
        cap_phrase = phrase_data.get("cap_phrase", "A Memory")
        img_data = image_map.get(pid, {})
        if not img_data:
            img_data = {
                "visual_description": fallback_description(img_phrase, cap_phrase),
                "is_realistic": True,
            }
        is_real = img_data.get("is_realistic", True)

        # Image - fires on _img_p
        if _img_p is not None:
            els.append(
                make_el(
                    f"img_{pid}",
                    "image",
                    _img_p,
                    px,
                    py,
                    IMG_SCALE,
                    angle=angle,
                    animation="pop",
                    prop="shadow" if is_real else "",
                    filename=f"polaroid_{pid}.jpg",
                    description=img_data.get("visual_description", ""),
                )
            )

        # Caption - fires on _cap_p
        if _cap_p is not None:
            cap_y     = py + CAPTION_OFFSET
            cap_scale = safe_scale(cap_phrase, px, preferred_cap=2.0)
            cap_type  = random.choice(TEXT_TYPES)
            els.append(
                make_el(
                    f"cap_{pid}",
                    cap_type,
                    _cap_p,
                    px,
                    cap_y,
                    cap_scale,
                    angle=angle,
                    animation="pop",
                )
            )

    with open(opath, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)

    print(f"\nSaved: {opath}")
    print(f"   {len(els)} elements total (4 polaroids + title)")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
