"""
Layout 19 Generator — Pyramid Stack
=====================================
Director space: 1920x1080

Layout features:
1. Title text centered at the top.
2. Hero image centered in upper area (larger scale).
3. Two supporting images in the middle row (left + right).
4. Three keyword text labels spread across the bottom row.
5. Forms a visual pyramid: 1 top, 2 middle, 3 bottom.

Uses layout_safety.safe_pass() for canvas boundary enforcement.
"""

import json
import os
import random
import re
import sys
import hashlib

from layout_safety import safe_pass

W, H = 1920, 1080

CHAR_PX   = 30    # Comic Sans MS at fontSize=40 scene coords
MARGIN    = 60    # min px from canvas edge to text center
FONT_SIZE = 40    # canvas fontSize (used for vertical height calc)
TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]

# ── Pyramid positions ────────────────────────────────────────────────────────
# Row 1 (top): 1 hero image — centered
HERO_X = W // 2           # 960
HERO_Y = 340
HERO_SCALE = 0.30

# Row 2 (middle): 2 supporting images — left and right
SUPPORT_Y = 620
SUPPORT_LEFT_X = 420
SUPPORT_RIGHT_X = 1500
SUPPORT_SCALE = 0.24

# Row 3 (bottom): 3 text labels — spread evenly
TEXT_Y = 880
TEXT_POSITIONS = [300, 960, 1620]
# Max half-width per label: half the inter-position spacing minus a gap buffer,
# so adjacent labels don't overlap when both scale up
_TEXT_SPACING     = min(TEXT_POSITIONS[i+1] - TEXT_POSITIONS[i] for i in range(len(TEXT_POSITIONS)-1))  # 660
TEXT_MAX_AVAIL_HALF = _TEXT_SPACING // 2 - 50  # 280 px — keeps labels separated

# Title
TITLE_Y = 120

# Jitter for organic feel
ANGLE_JITTER_DEG = 5.0

# Vertical bounds for title: sits between canvas top and hero image top
_HERO_IMG_RADIUS   = int(1024 * HERO_SCALE / 2)            # 153 px
_HERO_TOP_CANVAS   = (HERO_Y - _HERO_IMG_RADIUS) / 2       # 93.5 canvas px
_TITLE_Y_CANVAS    = TITLE_Y / 2                            # 60 canvas px
_VERT_MARGIN       = 15                                     # canvas px buffer
TITLE_HEIGHT_CAP = max(1.0, min(
    (_TITLE_Y_CANVAS - _VERT_MARGIN) / 10,                          # from top
    (_HERO_TOP_CANVAS - _VERT_MARGIN - _TITLE_Y_CANVAS) / 10,       # to hero
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


def safe_scale(text, center_x, preferred_cap=2.5, max_avail_half=None):
    """Formula-based scale: larger for short text, capped by column width.
    Pass max_avail_half to further limit scale based on inter-element spacing.
    """
    chars   = max(1, len(text))
    n_words = max(1, len(text.split()))
    avail_half = min(center_x - MARGIN, W - center_x - MARGIN)
    if max_avail_half is not None:
        avail_half = min(avail_half, max_avail_half)
    avail_half = max(10, avail_half)
    canvas_safe = (2 * avail_half) / (chars * CHAR_PX)
    preferred   = min(preferred_cap, 14.0 / n_words)
    return round(max(1.0, min(preferred, canvas_safe)), 3)


def _unit_from_hash(seed: str) -> float:
    """Deterministic pseudo-random in [-1, 1]."""
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    n = int.from_bytes(digest[:4], "big")
    return (n / 2**32) * 2.0 - 1.0


def make_el(eid, etype, phrase, x, y, scale, angle=0, animation="pop",
            prop="", filename="", description="", text_content=None):
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
        "angle": int(angle),
        "animation": animation,
        "property": prop,
        "reason": "",
    }


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fallback_description(img_phrase, txt_phrase):
    phrase = f"{img_phrase} {txt_phrase}".strip()
    return f"A clean illustration showing {phrase}, on a pure white background."


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s1_path = f"assets/tmp/{sid}_layout_19_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_19_step_2_tmp.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    s1 = load_json(s1_path)
    if s1 is None:
        print(f"Error: {s1_path} not found. Run Step 1 first.")
        return 1
    s2 = load_json(s2_path)

    main_title = (s1.get("main_title") or "").strip()
    panels = s1.get("panels", [])
    if len(panels) == 0:
        print(f"Error: Layout 19 got 0 panels. Cannot proceed.")
        return 1
    if len(panels) < 3:
        print(f"   Warning: Layout 19 expects 3 panels, got {len(panels)}. Padding with duplicates.")
        while len(panels) < 3:
            panels.append(dict(panels[-1], panel_id=f"panel_{len(panels)+1}"))
    elif len(panels) > 3:
        print(f"   Warning: Layout 19 expects 3 panels, got {len(panels)}. Dropping extras.")
        panels = panels[:3]

    # Build image description map from step 2
    image_map = {}
    if isinstance(s2, dict):
        for panel in s2.get("detailed_panels", []):
            pid = panel.get("panel_id")
            if pid:
                image_map[pid] = panel.get("image", {})

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    _n_panels = min(3, len(panels))
    # P1=title, then per panel: img + txt
    _total_slots = 1 + _n_panels * 2
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    # Pad to full slot count so index arithmetic below stays unchanged
    _phrases = _all_phrases + [None] * (_total_slots - n_active)
    _title_phrase = _phrases[0]
    _panel_phrases = _phrases[1:]  # pairs [img, txt] per panel

    script = {"scene_id": sid, "elements": []}
    els = script["elements"]

    # ── Title ─────────────────────────────────────────────────────────────────
    title_upper = main_title.upper()
    title_scale = min(safe_scale(title_upper, W // 2, preferred_cap=3.5), TITLE_HEIGHT_CAP)
    title_scale = max(1.0, round(title_scale, 3))
    if _title_phrase is not None:
        els.append(make_el(
            "title_pyramid", "text_black", _title_phrase,
            W // 2, TITLE_Y, title_scale,
            animation="fade_up",
            text_content=_title_phrase.upper(),
        ))

    # ── Pyramid placement ────────────────────────────────────────────────────
    # Panel positions: [hero_top, support_left, support_right]
    img_positions = [
        {"x": HERO_X,          "y": HERO_Y,    "scale": HERO_SCALE},
        {"x": SUPPORT_LEFT_X,  "y": SUPPORT_Y, "scale": SUPPORT_SCALE},
        {"x": SUPPORT_RIGHT_X, "y": SUPPORT_Y, "scale": SUPPORT_SCALE},
    ]

    animations = ["pop", "slide_in_left", "slide_in_right"]

    for i, panel in enumerate(panels[:3]):
        pid = panel.get("panel_id", f"panel_{i+1}")
        _img_phrase = _panel_phrases[i * 2] if (i * 2) < len(_panel_phrases) else None
        _txt_phrase = _panel_phrases[i * 2 + 1] if (i * 2 + 1) < len(_panel_phrases) else None
        if _img_phrase is None and _txt_phrase is None:
            continue
        img_phrase = _img_phrase or ""
        txt_phrase = _txt_phrase or ""

        pos = img_positions[i]
        img_data = image_map.get(pid) or {
            "visual_description": fallback_description(img_phrase, txt_phrase),
            "is_realistic": False,
        }
        is_real = img_data.get("is_realistic", False)

        # Deterministic small angle jitter
        ang = _unit_from_hash(f"{sid}|{pid}|a") * ANGLE_JITTER_DEG

        # Image
        if _img_phrase is not None:
            els.append(make_el(
                f"img_{pid}", "image", _img_phrase,
                pos["x"], pos["y"], pos["scale"],
                angle=int(ang),
                animation=animations[i],
                prop="shadow" if is_real else "",
                filename=f"{pid}_img.jpg",
                description=img_data.get("visual_description", ""),
            ))

        # Text label in bottom row — formula-based scale, seeded random type
        if _txt_phrase is not None:
            txt_ang   = _unit_from_hash(f"{sid}|{pid}|ta") * 3.0
            txt_scale = safe_scale(txt_phrase, TEXT_POSITIONS[i], preferred_cap=2.0,
                                   max_avail_half=TEXT_MAX_AVAIL_HALF)
            txt_type  = random.choice(TEXT_TYPES)
            els.append(make_el(
                f"txt_{pid}", txt_type, _txt_phrase,
                TEXT_POSITIONS[i], TEXT_Y, txt_scale,
                angle=int(txt_ang),
                animation="pop",
                text_content=txt_phrase,
            ))

    # ═══ Safety pass ══════════════════════════════════════════════════════════
    script["elements"] = safe_pass(script["elements"])

    # ═══ Final save ═══════════════════════════════════════════════════════════
    with open(opath, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)

    num_imgs = len([e for e in els if e["type"] == "image"])
    print(f"\nSaved: {opath}")
    print(f"   {num_imgs} images | {len(els)} total elements")
    print(f"   Pyramid: 1 hero + 2 support + 3 labels + title")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
