"""
Layout 15 Generator — Hero + Bullets
=====================================
Director space: 1920x1080

Layout:
- Large hero image on the LEFT (centered ~490, 540)
- Section title top-right
- 3 bullet text items stacked vertically on the right
- Optional CTA line at the bottom-right
"""

import json
import os
import random
import re
import sys

W, H = 1920, 1080

IMG_SCALE = 0.44
HERO_X    = 490
HERO_Y    = H // 2

RIGHT_X = 1310

TITLE_Y       = 150
BULLET_Y_START = 360
BULLET_Y_GAP  = 185

CHAR_PX       = 30    # Comic Sans fontSize=40 — ALL CAPS uppercase
LBL_CHAR_PX   = 20    # Comic Sans fontSize=40 — mixed-case / lowercase
FONT_SIZE     = 40
MARGIN        = 60    # minimum px from canvas edge to text edge


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


def safe_scale(text, center_x, preferred_cap=2.5, char_px=None, min_scale=1.0):
    """Formula-based scale: larger for short text, capped by canvas width."""
    chars   = max(1, len(text))
    n_words = max(1, len(text.split()))
    available_half = min(center_x - MARGIN, W - center_x - MARGIN)
    available_half = max(10, available_half)
    cpx = char_px if char_px is not None else CHAR_PX
    canvas_safe = (2 * available_half) / (chars * cpx)
    preferred   = min(preferred_cap, 14.0 / n_words)
    return round(max(min_scale, min(preferred, canvas_safe)), 3)


def make_el(eid, etype, phrase, x, y, scale, angle=0, animation="pop",
            prop="", filename="", description="", text_content=None):
    return {
        "element_id": eid,
        "type": etype,
        "phrase": phrase,
        "text_content": text_content if text_content is not None else (phrase if etype.startswith("text") else ""),
        "filename": filename,
        "description": description,
        "x": int(x), "y": int(y),
        "scale": scale, "angle": angle,
        "animation": animation,
        "property": prop,
        "reason": ""
    }


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s1_path = f"assets/tmp/{sid}_layout_15_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_15_step_2_tmp.json"
    odir    = "assets/directorscript"
    opath   = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s1_path, encoding="utf-8") as f:
            s1 = json.load(f)
        with open(s2_path, encoding="utf-8") as f:
            s2 = json.load(f)
    except FileNotFoundError:
        print(f"Error: missing step tmp files for {sid}. Run Step 1 & Step 2 first.")
        return 1

    # ── Phrases from step_1 (used for display content, counts only) ──────────
    bullets_data  = s1["bullets"]
    cta_data      = s1.get("cta", {})
    _has_cta      = bool((cta_data.get("phrase") or "").strip())
    _n_bullets    = min(3, len(bullets_data))

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    # P1=hero, P2=section_title, P3..P(2+n)=bullets, P(3+n)=cta(opt)
    _n_slots = 2 + _n_bullets + (1 if _has_cta else 0)
    n_tokens = len(_tokens)
    n_active = min(_n_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_n_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _phrases = (_all_phrases + [None] * _n_slots)[:_n_slots]
    hero_phrase    = _phrases[0] or ""
    section_phrase = _phrases[1] or ""
    _bullet_phrases = _phrases[2: 2 + _n_bullets]
    _cta_phrase     = _phrases[2 + _n_bullets] if _has_cta else None

    # ── Image description from step_2 ─────────────────────────────────────────
    hero_img   = s2.get("hero_image", {})
    text_types = s2.get("text_types", {})

    section_type  = text_types.get("section_title", "text_highlighted")
    bullet_types  = [
        text_types.get("bullet_b1", "text_black"),
        text_types.get("bullet_b2", "text_red"),
        text_types.get("bullet_b3", "text_black"),
    ]
    cta_type = text_types.get("cta", "text_red")

    script = {"scene_id": sid, "elements": []}
    els    = script["elements"]

    # ── Hero image ─────────────────────────────────────────────────────────────
    _hero_p = _phrases[0]
    if _hero_p is not None:
        is_real = bool(hero_img.get("is_realistic", False))
        els.append(make_el(
            "hero_image", "image", _hero_p,
            HERO_X, HERO_Y, IMG_SCALE,
            animation="slide_in_left",
            prop="shadow" if is_real else "",
            filename="hero_main.jpg",
            description=hero_img.get("visual_description", ""),
        ))

    # ── Section title ──────────────────────────────────────────────────────────
    _section_p = _phrases[1]
    if _section_p is not None:
        title_upper = s1.get("section", {}).get("phrase", _section_p).upper()
        els.append(make_el(
            "section_title", section_type, _section_p,
            RIGHT_X, TITLE_Y,
            safe_scale(title_upper, RIGHT_X, preferred_cap=2.5),
            animation="slide_in_right",
            text_content=title_upper,
        ))

    # ── Bullets ────────────────────────────────────────────────────────────────
    n_bullets = len(bullets_data)
    for i, b in enumerate(bullets_data[:3]):
        _bphrase = _bullet_phrases[i] if i < len(_bullet_phrases) else None
        if _bphrase is None:
            continue
        btxt = b.get("phrase", _bphrase).strip() or _bphrase
        by  = BULLET_Y_START + i * BULLET_Y_GAP
        eid = f"bullet_{b.get('bullet_id', f'b{i+1}')}"
        els.append(make_el(
            eid, bullet_types[i], _bphrase,
            RIGHT_X, by,
            safe_scale(btxt, RIGHT_X, preferred_cap=2.0, char_px=LBL_CHAR_PX, min_scale=0.5),
            animation="slide_in_right",
            text_content=btxt,
        ))

    # ── CTA ────────────────────────────────────────────────────────────────────
    if _has_cta and _cta_phrase is not None:
        cta_y = BULLET_Y_START + min(3, n_bullets) * BULLET_Y_GAP + 80
        cta_phrase = cta_data.get("phrase", _cta_phrase)
        els.append(make_el(
            "cta", cta_type, _cta_phrase,
            RIGHT_X, cta_y,
            safe_scale(cta_phrase, RIGHT_X, preferred_cap=1.8, char_px=LBL_CHAR_PX, min_scale=0.5),
            animation="pop",
            text_content=cta_phrase,
        ))

    with open(opath, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)

    print(f"\nSaved: {opath}")
    print(f"   {len(els)} elements total (1 hero + {min(3, n_bullets)} bullets"
          + (" + cta" if _has_cta and _cta_phrase is not None else "") + ")")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
