"""
Layout 17 Generator — Triforce / Three-Point Triangle
======================================================
Director space: 1920x1080

Layout:
- 3 vertices of an equilateral triangle (top, bottom-right, bottom-left)
- Each vertex: image + label (placed BELOW the image)
  - If label text is too wide, it is wrapped into multiple stacked lines
    (each line is a separate director element with its own consecutive phrase fragment)
- Center: unifying concept word (text_highlighted)

Math: circumradius R=350 from center (960, 540).
Vertices at angles 90, -30, -150 degrees (standard math angle, y-up in math but y-down on screen).

Text Fit:
  CHAR_PX ≈ 22 per character at scale 1.0.
  safe_width per vertex is canvas-constrained from vertex x position.
  If label text exceeds safe_width at scale 1.4, shrink down to min_scale 0.85.
  If still too wide, wrap into multiple lines (max 3 lines).
  Each wrapped line becomes its own element with a consecutive phrase portion.
"""

import json, os, random, re, sys, math

W, H = 1920, 1080
CX, CY = W // 2, H // 2    # 960, 540

R          = 350             # circumradius
IMG_SCALE  = 0.22
IMG_RADIUS = int(1024 * IMG_SCALE / 2)    # 112 px

# Center safe width: gap between vertex image edges across the triangle center
CENTER_SAFE_W = max(50, (R - IMG_RADIUS) * 2 - 40)   # ~436 px

# Vertex angles
VERTEX_ANGLES = {"top": 90, "bottom_right": -30, "bottom_left": -150}

# Text fitting constants
CHAR_PX = 30          # pixels per char at scale 1.0 (Comic Sans MS)
LABEL_MIN_SCALE = 0.85
MAX_LABEL_LINES = 3
MARGIN = 60
LINE_GAP = 52         # vertical gap between stacked label lines


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


def vertex_pos(angle_deg):
    rad = math.radians(angle_deg)
    return (CX + R * math.cos(rad), CY - R * math.sin(rad))


def _text_width(text, scale):
    return len(text) * CHAR_PX * scale


def _wrap_words_by_width(words, scale, max_width):
    """Wrap words into lines that fit within max_width at given scale."""
    lines = []
    current = []
    for w in words:
        candidate = " ".join(current + [w])
        if current and _text_width(candidate, scale) > max_width:
            lines.append(" ".join(current))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))
    return lines


def _safe_width_for_vertex(vid, vx):
    """Compute safe text width for a vertex, accounting for neighbor vertices.
    Bottom vertices share the same y, so their labels must not overlap horizontally.
    """
    left_space = vx - MARGIN
    right_space = (W - MARGIN) - vx

    # For bottom vertices, also constrain by the midpoint between them
    # so their labels don't overlap horizontally
    bl_x, _ = vertex_pos(VERTEX_ANGLES["bottom_left"])
    br_x, _ = vertex_pos(VERTEX_ANGLES["bottom_right"])
    midpoint = (bl_x + br_x) / 2
    LABEL_GAP = 80  # min horizontal gap between two bottom labels

    if vid == "bottom_left":
        # Right edge must not pass midpoint (minus gap)
        right_space = min(right_space, midpoint - vx - LABEL_GAP / 2)
    elif vid == "bottom_right":
        # Left edge must not pass midpoint (minus gap)
        left_space = min(left_space, vx - midpoint - LABEL_GAP / 2)

    return int(2 * max(0, min(left_space, right_space)))


def _preferred_label_scale(text):
    """Formula-based preferred scale: larger for short text, capped at 2.0."""
    n_words = max(1, len(text.split()))
    return min(2.0, 14.0 / n_words)


def _fit_label(text, vid, vx):
    """Determine how to fit label text at vertex position.
    Returns (lines, scale) where lines is a list of display strings.
    """
    words = text.split()
    if not words:
        return [""], LABEL_MIN_SCALE

    max_width = _safe_width_for_vertex(vid, vx)

    # Start from formula-based preferred scale (short text scales up)
    preferred = _preferred_label_scale(text)
    scale = preferred
    while scale >= LABEL_MIN_SCALE:
        if _text_width(text, scale) <= max_width:
            return [text], round(scale, 3)
        scale = round(scale - 0.05, 3)

    # Still too wide at min scale — wrap into multiple lines
    scale = LABEL_MIN_SCALE
    lines = _wrap_words_by_width(words, scale, max_width)
    if len(lines) <= MAX_LABEL_LINES:
        return lines, scale

    # Force fit into MAX_LABEL_LINES
    n = len(words)
    k = min(MAX_LABEL_LINES, n)
    base = n // k
    rem = n % k
    forced = []
    idx = 0
    for row in range(k):
        take = base + (1 if row < rem else 0)
        forced.append(" ".join(words[idx:idx + take]))
        idx += take

    # Final scale check
    longest = max((len(line) for line in forced), default=1)
    fit_scale = max_width / max(1, longest * CHAR_PX)
    final_scale = min(LABEL_MIN_SCALE, fit_scale)
    final_scale = max(0.65, round(final_scale, 3))
    return forced, final_scale


def _split_phrase_into_lines(phrase, num_lines):
    """Split a phrase string into num_lines consecutive portions at word boundaries.
    Each portion is a unique, non-empty phrase for timing.
    """
    words = phrase.split()
    if num_lines <= 1 or len(words) <= 1:
        return [phrase]

    n = len(words)
    k = min(num_lines, n)
    base = n // k
    rem = n % k
    lines = []
    idx = 0
    for row in range(k):
        take = base + (1 if row < rem else 0)
        lines.append(" ".join(words[idx:idx + take]))
        idx += take
    return lines


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

    s1_path = f"assets/tmp/{sid}_layout_17_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_17_step_2_tmp.json"
    odir    = "assets/directorscript"
    opath   = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    # Try step 2 first (has visual details), fall back to step 1
    s2_data = None
    s1_data = None

    if os.path.exists(s2_path):
        with open(s2_path, encoding="utf-8") as f:
            s2_data = json.load(f)
    if os.path.exists(s1_path):
        with open(s1_path, encoding="utf-8") as f:
            s1_data = json.load(f)

    if s2_data is None and s1_data is None:
        print(f"Error: No step output found. Run Step 1 first.")
        return 1

    # Get center_word
    center_word = ""
    if s2_data:
        center_word = (s2_data.get("center_word") or "").strip()
    if not center_word and s1_data:
        center_word = (s1_data.get("center_word") or "").strip()
    if not center_word:
        center_word = "CORE"

    # Build vertex data — phrases always from step 1, visuals from step 2
    s1_vertex_map = {}
    if s1_data:
        for v in s1_data.get("vertices", []):
            vid = v.get("vertex_id")
            if vid:
                s1_vertex_map[vid] = v

    s2_vertex_map = {}
    if s2_data:
        for v in s2_data.get("detailed_vertices", []):
            vid = v.get("vertex_id")
            if vid:
                s2_vertex_map[vid] = v

    vid_order = ["top", "bottom_right", "bottom_left"]

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    n_tokens = len(_tokens)

    # ── Find where center_word is actually spoken and carve it out ────────────
    # This prevents timing collision between center_word and a vertex phrase,
    # and ensures center_word fires when those words are actually spoken.
    def _find_span(tkns, phrase):
        words = phrase.lower().rstrip(".,!?").split()
        for i in range(len(tkns) - len(words) + 1):
            window = [t.lower().strip(".,!?'\"") for t in tkns[i:i + len(words)]]
            if window == [w.strip(".,!?'\"") for w in words]:
                return i, i + len(words)
        return None, None

    cw_start, cw_end = _find_span(_tokens, center_word)
    if cw_start is not None:
        _center_phrase = " ".join(_tokens[cw_start:cw_end])
        _vertex_tokens = _tokens[:cw_start] + _tokens[cw_end:]
        print(f"   Center word matched in script: '{_center_phrase}'")
    else:
        _center_phrase = _tokens[0] if _tokens else None
        _vertex_tokens = _tokens[1:] if _tokens else []
        print(f"   Center word '{center_word}' not found verbatim — using first token '{_center_phrase}'")

    # Priority-based vertex dropping: each vertex pair needs ~2 tokens from the
    # remaining pool. Drop lower-priority (later) vertices when script is too short.
    _n_active_vertices = min(len(vid_order), max(1, len(_vertex_tokens) // 2))
    _vertex_phrases = allot_phrases(_vertex_tokens, _n_active_vertices * 2)

    print(f"   Token budget: {n_tokens} tokens -> {_n_active_vertices} active vertices")

    script = {"scene_id": sid, "elements": []}
    els = script["elements"]

    # ── Center word ───────────────────────────────────────────────────────────
    cw_display = center_word.upper()
    n_chars_cw = max(1, len(cw_display))
    n_words_cw = max(1, len(cw_display.split()))
    cw_preferred = min(2.0, 10.0 / n_words_cw)
    cw_canvas_safe = CENTER_SAFE_W / (CHAR_PX * n_chars_cw)
    cw_scale = round(max(1.0, min(cw_preferred, cw_canvas_safe)), 3)

    # _center_phrase is already set in the allocation section above (span-based)
    if _center_phrase is not None:
        els.append(make_el("center_word", "text_highlighted",
                           _center_phrase,
                           CX, CY,
                           cw_scale, animation="pop",
                           text_content=cw_display))

    # ── Vertices ──────────────────────────────────────────────────────────────
    anim_map = {"top": "slide_in_up", "bottom_right": "pop", "bottom_left": "pop"}

    for vi, vid in enumerate(vid_order[:_n_active_vertices]):
        _vimg_phrase = _vertex_phrases[vi * 2] if (vi * 2) < len(_vertex_phrases) else None
        _vlbl_phrase = _vertex_phrases[vi * 2 + 1] if (vi * 2 + 1) < len(_vertex_phrases) else None
        if _vimg_phrase is None and _vlbl_phrase is None:
            continue

        s1_v = s1_vertex_map.get(vid, {})
        s2_v = s2_vertex_map.get(vid, {})

        vx, vy = vertex_pos(VERTEX_ANGLES[vid])

        # Visual details from step 2
        ltype = s2_v.get("label_type", "text_black")
        img_data = s2_v.get("image", {})
        if not img_data.get("visual_description"):
            combined = f"{_vimg_phrase or ''} {_vlbl_phrase or ''}".strip()
            img_data = {
                "visual_description": f"A realistic photo illustrating {combined}, single subject on a pure white background.",
                "is_realistic": True,
            }
        is_real = img_data.get("is_realistic", True)

        # Label display text: first word of allot-derived _vlbl_phrase (verbatim,
        # matches timing trigger). AI lbl_phrase is NOT used as display text —
        # it can be a stop word (e.g. "a") which is meaningless on screen.
        label_display = (_vlbl_phrase.split()[0].strip(".,!?") if _vlbl_phrase else "").upper()

        # Image at vertex — fires on _vimg_phrase
        if _vimg_phrase is not None:
            els.append(make_el(f"img_{vid}", "image", _vimg_phrase,
                               vx, vy, IMG_SCALE,
                               animation=anim_map.get(vid, "pop"),
                               prop="shadow" if is_real else "",
                               filename=f"{vid}_img.jpg",
                               description=img_data.get("visual_description", "")))

        # ── Text Fit for label ────────────────────────────────────────────────
        if _vlbl_phrase is not None:
            label_y = vy + IMG_RADIUS + 53
            display_lines, label_scale = _fit_label(label_display, vid, int(vx))

            if len(display_lines) == 1:
                # Single line — one element
                els.append(make_el(f"label_{vid}", ltype, _vlbl_phrase,
                                   vx, label_y, label_scale,
                                   animation=anim_map.get(vid, "pop"),
                                   text_content=display_lines[0]))
                print(f"  {vid}: label fits in 1 line at scale {label_scale}")
            else:
                # Multi-line — split _vlbl_phrase across lines so each gets its own
                # consecutive sub-phrase (never phrase="" which fires at time 0.0)
                print(f"  {vid}: label wrapped into {len(display_lines)} lines at scale {label_scale}")
                sub_phrases = _split_phrase_into_lines(_vlbl_phrase, len(display_lines))
                for j, disp_line in enumerate(display_lines):
                    line_y = label_y + j * LINE_GAP
                    els.append(make_el(
                        f"label_{vid}_{j}", ltype, sub_phrases[j],
                        vx, line_y, label_scale,
                        animation=anim_map.get(vid, "pop"),
                        text_content=disp_line))

    with open(opath, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)

    print(f"\nSaved: {opath}")
    print(f"   {len(els)} elements total")

    # Print summary
    print("\nElements:")
    for el in els:
        p = el['phrase']
        tc = el.get('text_content', '')
        t = el['type']
        print(f"  {el['element_id']:28s} {t:18s} phrase=\"{p}\"")
        if tc:
            print(f"  {'':28s} {'':18s} text =\"{tc}\"")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
