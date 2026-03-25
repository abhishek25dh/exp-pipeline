"""
Layout 14 Generator — Circular Flow / Cycle
============================================
Director space: 1920x1080

Layout:
- Center: cycle title text (scale kept small to avoid overlapping nodes)
- 4 nodes at 12, 3, 6, 9 o'clock on a circle of radius RADIUS
- Each node: image + label outside the circle
- 4 arrows at 45/135/225/315 degrees connecting adjacent nodes
"""

import json, os, random, re, sys, math

W, H = 1920, 1080
CX, CY = W // 2, H // 2           # 960, 540

IMG_SCALE  = 0.22
IMG_RADIUS = int(1024 * IMG_SCALE / 2)    # 112 px
RADIUS     = 320                           # distance from center to node center

CHAR_PX       = 30    # Comic Sans uppercase fontSize=40 — used for center title
LBL_CHAR_PX   = 20    # Comic Sans lowercase/mixed-case label text — narrower than uppercase
FONT_SIZE    = 40    # tester renders text at fontSize=40
LINE_GAP     = 55    # vertical offset between two center title lines
CANVAS_MARGIN = 30    # minimum px from canvas edge to any element
LBL_MARGIN   = 60    # extra breathing room for left/right labels (avoids visual clip at edge)
IMG_GAP       = 20    # minimum gap between text edge and image edge
CTR_IMG_GAP  = 20    # min gap between center text edge and each orbit image edge

# Center safe width: gap between left and right orbit image edges minus CTR_IMG_GAP each side
CENTER_SAFE_W = max(50, (RADIUS - IMG_RADIUS - CTR_IMG_GAP) * 2)


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


def compute_center_scale(text):
    n_chars = max(1, len(text))
    n_words = max(1, len(text.split()))
    canvas_safe = CENTER_SAFE_W / (LBL_CHAR_PX * n_chars)
    preferred   = min(2.0, 12.0 / n_words)
    # min_scale 0.6 (not 1.0) — long center titles must be allowed to shrink
    # to fit inside CENTER_SAFE_W without overlapping the orbit nodes.
    return round(max(0.6, min(preferred, canvas_safe)), 3)


def compute_label_scale(text, safe_w, available_h=None, min_scale=1.0):
    """Scale based on width and optional height constraint.

    safe_w        : available horizontal width in director px
    available_h   : available vertical height for top/bottom labels (director px)
                    — constrains scale so text doesn't overflow into the image or off canvas
    Tester renders: fontSize=40, originX/Y=center. Text height = FONT_SIZE * scale.

    Uses LBL_CHAR_PX (20) not CHAR_PX (30) because label phrases are lowercase/mixed-case,
    where characters are ~20px wide vs ~30px for uppercase center titles.
    """
    n_chars = max(1, len(text))
    n_words = max(1, len(text.split()))
    width_safe = safe_w / (LBL_CHAR_PX * n_chars)
    preferred  = min(2.5, 14.0 / n_words)
    scale = min(preferred, width_safe)
    if available_h is not None:
        height_safe = available_h / FONT_SIZE
        scale = min(scale, height_safe)
    return round(max(min_scale, scale), 3)

# Clock positions: angle in degrees clockwise from top (screen coords: y-down)
CLOCK = [
    ("phase_1", "12", 270),   # top
    ("phase_2", "3",    0),   # right
    ("phase_3", "6",   90),   # bottom
    ("phase_4", "9",  180),   # left
]

# Arrow positions: midpoints of arcs between adjacent nodes
ARROW_ANGLES_DEG = [315, 45, 135, 225]   # NW, NE, SE, SW (clockwise from 12)


def split_title(text):
    """Split text at the word boundary closest to the middle."""
    words = text.split()
    if len(words) == 1:
        return [text]
    mid = len(text) / 2
    best, best_dist = 1, float("inf")
    for i in range(1, len(words)):
        dist = abs(len(" ".join(words[:i])) - mid)
        if dist < best_dist:
            best_dist = dist
            best = i
    return [" ".join(words[:best]), " ".join(words[best:])]


def node_pos(angle_from_right_deg):
    """Convert standard math angle (right=0, CCW positive) to screen x,y."""
    rad = math.radians(angle_from_right_deg)
    return (CX + RADIUS * math.cos(rad), CY - RADIUS * math.sin(rad))


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

    s2_path = f"assets/tmp/{sid}_layout_14_step_2_tmp.json"
    odir    = "assets/directorscript"
    opath   = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s2_path) as f:
            d = json.load(f)
    except FileNotFoundError:
        print(f"Error: {s2_path} not found. Run Step 1 & Step 2 first.")
        return 1

    center_title = d.get("center_title", "")
    phases       = d.get("phases", [])

    if len(phases) == 0:
        print(f"Error: Layout 14 got 0 phases. Cannot proceed.")
        return 1
    if len(phases) > 4:
        print(f"   Warning: Layout 14 expects at most 4 phases, got {len(phases)}. Dropping extras.")
        phases = phases[:4]

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()

    # Slots: 1 (center_title) + len(phases) * 2 (img + label each)
    _total_slots = 1 + len(phases) * 2
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _all_phrases = (_all_phrases + [None] * _total_slots)[:_total_slots]

    # First slot = center_title; remaining slots = phases (img + label pairs)
    _ct_phrase = _all_phrases[0]
    _phrases   = _all_phrases[1:]

    script = {"scene_id": sid, "elements": []}
    els    = script["elements"]

    # ── Center title — fires on first script token (_ct_phrase) ─────────────────
    if center_title and _ct_phrase is not None:
        ct_words = center_title.split()
        # Split any title with 3+ words so each line is shorter and fits CENTER_SAFE_W.
        if len(ct_words) > 2:
            lines = split_title(center_title)
        else:
            lines = [center_title]
        # Consistent scale across all lines: compute from the longest line.
        longest_line = max(lines, key=len)
        ct_scale = compute_center_scale(longest_line)
        # Dynamic line gap: must be >= text height (FONT_SIZE * scale) + small buffer
        # so lines never overlap. Use max of fixed LINE_GAP and actual text height.
        dyn_gap = max(LINE_GAP, int(FONT_SIZE * ct_scale) + 10)
        offsets = ([-dyn_gap // 2, dyn_gap // 2] if len(lines) == 2 else [0])
        for j, line in enumerate(lines):
            eid = f"center_title_{j+1}" if len(lines) > 1 else "center_title"
            # First line fires on _ct_phrase; subsequent lines get phrase=""
            # so they inherit timing from line 1 via timings.py.
            line_phrase = _ct_phrase if j == 0 else ""
            els.append(make_el(eid, "text_highlighted", line_phrase,
                               CX, CY + offsets[j], ct_scale,
                               animation="pop", text_content=line))

    # Node positions: 12=top, 3=right, 6=bottom, 9=left
    # Using screen-angle (CW from right): top=90, right=0, bottom=270, left=180
    SCREEN_ANGLES = [90, 0, 270, 180]   # for phases 1,2,3,4

    node_coords = []
    anim_map = ["slide_in_up", "slide_in_right", "slide_in_up", "slide_in_left"]
    active_phase_indices = set()   # tracks which phases received at least one phrase

    for i, phase in enumerate(phases):
        screen_angle = SCREEN_ANGLES[i]
        nx = CX + RADIUS * math.cos(math.radians(screen_angle))
        ny = CY - RADIUS * math.sin(math.radians(screen_angle))
        node_coords.append((nx, ny))

        _img_phrase = _phrases[i * 2] if (i * 2) < len(_phrases) else None
        _lbl_phrase = _phrases[i * 2 + 1] if (i * 2 + 1) < len(_phrases) else None
        if _img_phrase is None and _lbl_phrase is None:
            continue
        active_phase_indices.add(i)
        lbl_phrase = phase.get("label_phrase", phase.get("label", f"phase {i+1}"))
        ltype      = phase.get("label_type", "text_black")
        img_data   = phase.get("image", {})
        is_real    = img_data.get("is_realistic", False)
        pid        = phase.get("phase_id", f"phase_{i+1}")

        # Image node — phrase fires when image appears
        if _img_phrase is not None:
            els.append(make_el(f"img_{pid}", "image", _img_phrase,
                               nx, ny, IMG_SCALE,
                               animation=anim_map[i],
                               prop="shadow" if is_real else "",
                               filename=f"{pid}_img.jpg",
                               description=img_data.get("visual_description", "")))

        # Label — placed outside the circle, scaled to the allotted phrase length.
        # Scale MUST use _lbl_phrase (the actual text rendered), not AI label_phrase
        # (which may be shorter and produce an inflated scale that overflows the canvas).
        # Tester: originX/Y='center', fontSize=40. Text height = FONT_SIZE * scale.
        # Must not overlap image (IMG_GAP buffer) or go off canvas (CANVAS_MARGIN buffer).
        _scale_phrase = _lbl_phrase or lbl_phrase   # allotted phrase drives scale
        if i == 0:   # 12 o'clock — label above image
            img_top   = ny - IMG_RADIUS
            avail_h   = img_top - CANVAS_MARGIN - IMG_GAP   # space above image minus gaps
            safe_w    = min(nx, W - nx) * 2 - 80
            lbl_scale = compute_label_scale(_scale_phrase, safe_w, available_h=avail_h, min_scale=1.0)
            text_half = FONT_SIZE * lbl_scale / 2
            # Center label in available space: [CANVAS_MARGIN, img_top - IMG_GAP]
            ly = CANVAS_MARGIN + (avail_h / 2)
            lx = nx

        elif i == 1: # 3 o'clock — label to the right of image
            safe_w    = W - (nx + IMG_RADIUS + IMG_GAP) - LBL_MARGIN
            lbl_scale = compute_label_scale(_scale_phrase, safe_w, min_scale=0.65)
            text_w    = LBL_CHAR_PX * len(_scale_phrase) * lbl_scale
            lx = min(W - LBL_MARGIN - text_w / 2,
                     nx + IMG_RADIUS + IMG_GAP + text_w / 2)
            ly = ny

        elif i == 2: # 6 o'clock — label below image
            img_bot   = ny + IMG_RADIUS
            avail_h   = (H - CANVAS_MARGIN) - (img_bot + IMG_GAP)
            safe_w    = min(nx, W - nx) * 2 - 80
            lbl_scale = compute_label_scale(_scale_phrase, safe_w, available_h=avail_h, min_scale=1.0)
            text_half = FONT_SIZE * lbl_scale / 2
            # Center label in available space: [img_bot + IMG_GAP, H - CANVAS_MARGIN]
            ly = (img_bot + IMG_GAP) + (avail_h / 2)
            lx = nx

        else:        # 9 o'clock — label to the left of image
            safe_w    = (nx - IMG_RADIUS - IMG_GAP) - LBL_MARGIN
            lbl_scale = compute_label_scale(_scale_phrase, safe_w, min_scale=0.65)
            text_w    = LBL_CHAR_PX * len(_scale_phrase) * lbl_scale
            lx = max(LBL_MARGIN + text_w / 2,
                     nx - IMG_RADIUS - IMG_GAP - text_w / 2)
            ly = ny

        if _lbl_phrase is not None:
            els.append(make_el(f"label_{pid}", ltype, _lbl_phrase,
                               lx, ly, lbl_scale,
                               animation=anim_map[i]))

    # ── Arrows between adjacent nodes — only emit if BOTH phases are active ────
    # An arrow with phrase="" fires at time 0.0; skip it entirely when the source
    # or target phase has no tokens (i.e. the phase was dropped by allot_phrases).
    arrow_labels = ["ne", "se", "sw", "nw"]
    for i in range(len(node_coords)):
        j = (i + 1) % 4
        if i not in active_phase_indices or j not in active_phase_indices:
            continue   # one or both phases inactive — no arrow
        p1 = node_coords[i]
        p2 = node_coords[j]
        mid_x = (p1[0] + p2[0]) / 2
        mid_y = (p1[1] + p2[1]) / 2
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angle_deg = math.degrees(math.atan2(dy, dx))
        els.append(make_el(f"arrow_{arrow_labels[i]}", "arrow", "",
                           mid_x, mid_y, 0.07,
                           angle=int(angle_deg),
                           animation="pop",
                           filename="arrow.png"))

    with open(opath, "w") as f:
        json.dump(script, f, indent=2)

    print(f"\nSaved: {opath}")
    print(f"   {len(els)} elements total (4 nodes + 4 arrows + center)")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
