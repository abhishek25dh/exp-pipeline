"""
Layout 10 Generator — Macro to Micro (Zoom Map)
==============================================
Director space: 1920×1080

Layout features:
1. One massive "Macro" image centered in the left half of the screen.
2. 2 or 3 smaller "Micro" images stacked vertically in the right half of the screen.
3. Arrows connect the right-edge of the Macro image to the center-left edge of each Micro image.
"""

import json, os, random, re, sys, math

# ── Constants ─────────────────────────────────────────────────────────────────
W, H = 1920, 1080
RENDER = 1024

MACRO_SCALE = 0.50
MICRO_SCALE = 0.22
ARROW_SCALE = 0.20

MACRO_CX = 550
MACRO_CY = 590 # Slightly below center to leave room for the big title
MICRO_CX = 1450
MARGIN = 60
CHAR_PX = 30        # uppercase / ALL-CAPS text
LBL_CHAR_PX = 20    # mixed-case label text (micro labels)
MICRO_TXT_SCALE = 1.2
MICRO_TXT_MIN_SCALE = 0.75
MAX_MICRO_TXT_LINES = 4
BLOCK_GAP = 24


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


def _text_width(text, scale, char_px=None):
    return len(text) * (char_px or LBL_CHAR_PX) * scale


def _wrap_words_by_width(words, scale, max_width, char_px=None):
    lines = []
    current = []
    for w in words:
        candidate = " ".join(current + [w])
        if current and _text_width(candidate, scale, char_px) > max_width:
            lines.append(" ".join(current))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))
    return lines


def _split_phrase_for_stack(phrase, max_width):
    words = phrase.split()
    if not words:
        return [""], MICRO_TXT_MIN_SCALE

    # Find the highest readable scale that fits phrase into <= MAX_MICRO_TXT_LINES lines.
    scale = MICRO_TXT_SCALE
    while scale >= MICRO_TXT_MIN_SCALE:
        lines = _wrap_words_by_width(words, scale, max_width)
        if len(lines) <= MAX_MICRO_TXT_LINES:
            return lines, round(scale, 3)
        scale = round(scale - 0.05, 3)

    # Fallback: force line count to MAX_MICRO_TXT_LINES using word-count chunks.
    n = len(words)
    k = min(MAX_MICRO_TXT_LINES, n)
    base = n // k
    rem = n % k
    forced = []
    i = 0
    for row in range(k):
        take = base + (1 if row < rem else 0)
        forced.append(" ".join(words[i:i + take]))
        i += take
    # Ensure forced lines still fit width by lowering scale if needed.
    longest = max((len(line) for line in forced), default=1)
    fit_scale = max_width / max(1, longest * LBL_CHAR_PX)
    final_scale = min(MICRO_TXT_MIN_SCALE, fit_scale)
    final_scale = max(0.6, round(final_scale, 3))
    return forced, final_scale


def micro_text_layout(img_x, img_y, phrase):
    """Return text layout dict for a micro label.
    - If short enough, place as one line on the right.
    - If long, split into stacked lines below the image."""
    img_half = int(RENDER * MICRO_SCALE / 2)
    gap = 20  # gap between image right edge and text left edge
    img_right = img_x + img_half

    # How much space to the RIGHT of the image (text extends fully to the right)?
    available_right = W - MARGIN - img_right - gap - 12  # small safety margin
    max_scale_right = available_right / max(1, len(phrase) * LBL_CHAR_PX)

    if max_scale_right >= MICRO_TXT_MIN_SCALE:
        # Fits to the right at a readable scale
        actual_scale = min(MICRO_TXT_SCALE, max_scale_right)
        text_w = _text_width(phrase, actual_scale)
        cx = img_right + gap + text_w / 2
        cx = min(cx, W - MARGIN - text_w / 2)
        text_h = max(24, int(36 * actual_scale))
        y = int(img_y)
        y = max(MARGIN + text_h // 2, min(H - MARGIN - text_h // 2, y))
        return {
            "x": int(cx),
            "y": y,
            "scale": round(actual_scale, 3),
            "lines": [phrase],
            "line_gap": 0,
        }

    # Too long: place centered below the image as stacked lines.
    cx = int(img_x)
    top_y = int(img_y + img_half + 30)
    available_half = min(cx - MARGIN, W - MARGIN - cx)
    max_line_width = max(200, int(2 * available_half))
    lines, scale = _split_phrase_for_stack(phrase, max_line_width)
    line_gap = max(38, int(52 * scale))
    return {
        "x": cx,
        "y": int(top_y),
        "scale": scale,
        "lines": lines,
        "line_gap": line_gap,
    }


def text_block_bounds(txt_layout):
    scale = txt_layout["scale"]
    lines = txt_layout["lines"]
    text_h = max(24, int(36 * scale))
    if len(lines) == 1:
        top = int(txt_layout["y"] - text_h / 2)
        bottom = int(txt_layout["y"] + text_h / 2)
    else:
        block_h = ((len(lines) - 1) * txt_layout["line_gap"]) + text_h
        top = int(txt_layout["y"])
        bottom = int(txt_layout["y"] + block_h)
    return top, bottom


def layout_micro_block(x, y, txt_phrase):
    img_half = int(RENDER * MICRO_SCALE / 2)
    txt_layout = micro_text_layout(x, y, txt_phrase)
    min_txt_top = y + img_half + 30

    # Keep stacked text below its own image.
    if len(txt_layout["lines"]) > 1 and txt_layout["y"] < min_txt_top:
        shift_up = min_txt_top - txt_layout["y"]
        y = max(MARGIN + img_half, y - shift_up)
        txt_layout = micro_text_layout(x, y, txt_phrase)

    img_top = int(y - img_half)
    img_bottom = int(y + img_half)
    txt_top, txt_bottom = text_block_bounds(txt_layout)
    top = min(img_top, txt_top)
    bottom = max(img_bottom, txt_bottom)
    return {
        "x": int(x),
        "y": int(y),
        "txt_layout": txt_layout,
        "top": int(top),
        "bottom": int(bottom),
    }


def resolve_micro_collisions(layouts, txt_phrases):
    """Resolve vertical collisions for micro blocks holistically.
    A block is image + all wrapped text lines."""
    if not layouts:
        return layouts

    # Measure current block heights.
    heights = [max(1, l["bottom"] - l["top"]) for l in layouts]
    n = len(layouts)
    desired_tops = [l["top"] for l in layouts]

    # Fit gap to available height. If space is tight, reduce gap but never below 0.
    free_space = (H - 2 * MARGIN) - sum(heights)
    gap = BLOCK_GAP
    if n > 1:
        gap = max(0, min(BLOCK_GAP, free_space // (n - 1)))

    tops = [0] * n
    tops[0] = max(MARGIN, desired_tops[0])
    for i in range(1, n):
        tops[i] = max(desired_tops[i], tops[i - 1] + heights[i - 1] + gap)

    # If stack still overflows, anchor bottom and back-pack upwards with same gap.
    stack_bottom = tops[-1] + heights[-1]
    if stack_bottom > H - MARGIN:
        tops[-1] = H - MARGIN - heights[-1]
        for i in range(n - 2, -1, -1):
            tops[i] = tops[i + 1] - gap - heights[i]
        if tops[0] < MARGIN:
            # Final fallback: pin top and recompute downward without overlap.
            tops[0] = MARGIN
            for i in range(1, n):
                tops[i] = tops[i - 1] + heights[i - 1] + gap

    # Rebuild each layout using its image center target derived from desired top.
    rebuilt = []
    img_half = int(RENDER * MICRO_SCALE / 2)
    for i, l in enumerate(layouts):
        target_y = int(tops[i] + img_half)
        rebuilt.append(layout_micro_block(l["x"], target_y, txt_phrases[i]))
    return rebuilt

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s2_path = f"assets/tmp/{sid}_layout_10_step_2_tmp.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s2_path) as f:
            step2 = json.load(f)
    except FileNotFoundError:
        print(f"Error: Step 2 tmp JSON not found for {sid}. Run them first.")
        return 1

    macro = step2.get("macro_image", {})
    micros = step2.get("micro_images", [])

    num_micros = len(micros)
    if num_micros == 0:
        print(f"   Warning: Layout 10 got 0 micro images. Rendering macro-only.")
    elif num_micros < 2:
        print(f"   Warning: Layout 10 expects 2-3 micro images, got {num_micros}. Padding with duplicates.")
        while len(micros) < 2:
            micros.append(dict(micros[-1], micro_id=f"micro_{len(micros)+1}"))
        num_micros = len(micros)
    elif num_micros > 3:
        print(f"   Warning: Layout 10 expects 2-3 micro images, got {num_micros}. Dropping extras.")
        micros = micros[:3]
        num_micros = len(micros)

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    n_tokens = len(_tokens)
    # Priority-based micro dropping: each micro needs 3 slots (arrow+img+txt).
    # Drop lower-priority micros when the script is too short.
    _used_micros_count = min(min(3, num_micros), max(0 if num_micros == 0 else 1, (n_tokens - 2) // 3))
    # P1=macro_img, P2=macro_txt, then per active micro: arrow, img, txt
    _n_slots = 2 + _used_micros_count * 3
    _phrases = allot_phrases(_tokens, _n_slots)
    print(f"   Token budget: {n_tokens} tokens -> {_used_micros_count} active micros")
    _macro_img_phrase = _phrases[0]
    _macro_txt_phrase = _phrases[1]
    _micro_phrases = _phrases[2:]  # groups of 3: [arrow, img, txt] per micro

    script = {"scene_id": sid, "elements": []}

    print(f"   Generating Macro/Micro Layout...")

    # 1. Place Macro Image & Text
    m_real = macro.get("is_realistic", False)
    m_type = macro.get("text_type", "text_highlighted")

    if _macro_img_phrase is not None:
        script["elements"].append({
            "element_id": "img_macro",
            "type": "image",
            "phrase": _macro_img_phrase,
            "filename": "macro_img.jpg",
            "description": macro.get("visual_description", ""),
            "x": MACRO_CX,
            "y": MACRO_CY,
            "scale": MACRO_SCALE,
            "angle": random.randint(-2, 2),
            "animation": "pop",
            "property": "shadow" if m_real else "",
            "reason": "Main macro overview",
            "text_content": ""
        })

    # Large title sits high above the macro image
    max_macro_w = (MACRO_CX - MARGIN) * 2
    _m_txt = _macro_txt_phrase or ""
    macro_words = _m_txt.split()
    lines = [_m_txt]
    macro_scale = 1.7

    if _macro_txt_phrase is not None:
        fit_scale = max_macro_w / max(1, len(_m_txt) * CHAR_PX)
        n_macro_words = max(1, len(macro_words))
        preferred_scale = min(2.5, 18.0 / n_macro_words)

        if fit_scale >= 1.0:
            # Phrase fits on one line — use preferred scale capped by fit
            macro_scale = round(min(preferred_scale, fit_scale), 3)
            lines = [_m_txt]
        else:
            # Phrase too long for one line at scale=1.0 — wrap at min_scale=1.0
            # (approach rule: "if min_scale overflows, prefer wrapping")
            macro_scale = 1.0
            lines = _wrap_words_by_width(macro_words, macro_scale, max_macro_w, CHAR_PX)
            # Consistent scale: recompute from longest line to ensure every line fits
            longest = max(lines, key=len)
            line_fit = max_macro_w / max(1, len(longest) * CHAR_PX)
            if line_fit < macro_scale:
                macro_scale = round(max(0.7, line_fit), 3)
                lines = _wrap_words_by_width(macro_words, macro_scale, max_macro_w, CHAR_PX)

        line_gap = int(55 * macro_scale)
        start_y = 200 - (len(lines) - 1) * line_gap // 2

        if len(lines) == 1:
            script["elements"].append({
                "element_id": "txt_macro",
                "type": m_type,
                "phrase": _macro_txt_phrase,
                "text_content": lines[0],
                "x": MACRO_CX,
                "y": start_y,
                "scale": macro_scale,
                "angle": 0,
                "animation": "pop",
                "property": "",
                "reason": "Macro Title",
                "filename": "",
                "description": ""
            })
        else:
            # Split _macro_txt_phrase into consecutive sub-phrases — one per line.
            # Never use phrase="" which would fire all lines at time 0.0.
            _macro_sub_phrases = _split_phrase_for_stack(_macro_txt_phrase, max_macro_w)[0] if _macro_txt_phrase else lines
            # _split_phrase_for_stack returns (lines, scale) — we only need the word-split.
            # Use word-count chunks matching len(lines) instead.
            _mw = _macro_txt_phrase.split() if _macro_txt_phrase else []
            _mk = len(lines)
            _mb = len(_mw) // _mk if _mk else 1
            _mr = len(_mw) % _mk if _mk else 0
            _macro_sub = []
            _mi2 = 0
            for _mrow in range(_mk):
                _mtake = _mb + (1 if _mrow < _mr else 0)
                _macro_sub.append(" ".join(_mw[_mi2:_mi2 + _mtake]))
                _mi2 += _mtake
            for j, line in enumerate(lines):
                script["elements"].append({
                    "element_id": f"txt_macro_{j}",
                    "type": m_type,
                    "phrase": _macro_sub[j] if j < len(_macro_sub) else (_macro_txt_phrase or ""),
                    "text_content": line,
                    "x": MACRO_CX,
                    "y": int(start_y + j * line_gap),
                    "scale": macro_scale,
                    "angle": 0,
                    "animation": "pop",
                    "property": "",
                    "reason": "Macro Title line",
                    "filename": "",
                    "description": ""
                })

    # The point where arrows originate from (right edge of the macro image box)
    macro_box_width = RENDER * MACRO_SCALE
    arrow_origin_x = MACRO_CX + (macro_box_width / 2) + 20
    arrow_origin_y = MACRO_CY

    # 2. Add Micro Images, Text, and Connecting Arrows
    usable_h = 800
    start_y = 540 - (usable_h / 2) + (usable_h / max(1, num_micros) / 2)
    y_step = usable_h / max(1, num_micros)

    used_micros = micros[:3]
    micro_infos = []
    for i, micro in enumerate(used_micros):
        _arrow_p = _micro_phrases[i * 3] if (i * 3) < len(_micro_phrases) else None
        _img_p   = _micro_phrases[i * 3 + 1] if (i * 3 + 1) < len(_micro_phrases) else None
        _txt_p   = _micro_phrases[i * 3 + 2] if (i * 3 + 2) < len(_micro_phrases) else None
        micro_infos.append({
            "idx": i,
            "is_real": micro.get("is_realistic", False),
            "arrow_phrase": _arrow_p,
            "img_phrase": _img_p,
            "txt_phrase": _txt_p or f"Detail {i+1}",
            "txt_phrase_raw": _txt_p,
            "txt_type": micro.get("text_type", "text_black"),
            "visual_description": micro.get("visual_description", ""),
        })

    # Build initial micro layouts and then resolve collisions holistically.
    layouts = []
    for i, info in enumerate(micro_infos):
        y0 = int(start_y + (i * y_step))
        x0 = MICRO_CX + random.randint(-30, 30)
        layouts.append(layout_micro_block(x0, y0, info["txt_phrase"]))
    layouts = resolve_micro_collisions(layouts, [m["txt_phrase"] for m in micro_infos])

    for i, info in enumerate(micro_infos):
        if info["arrow_phrase"] is None and info["img_phrase"] is None and info["txt_phrase_raw"] is None:
            continue
        x = layouts[i]["x"]
        y = layouts[i]["y"]
        txt_layout = layouts[i]["txt_layout"]

        # Calculate Arrow connecting macro to this micro
        # Arrow points from arrow_origin to the left edge of the micro image
        micro_box_width = RENDER * MICRO_SCALE
        target_x = x - (micro_box_width / 2) - 40
        target_y = y

        mid_x = (arrow_origin_x + target_x) / 2
        mid_y = (arrow_origin_y + target_y) / 2

        dx = target_x - arrow_origin_x
        dy = target_y - arrow_origin_y
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)

        # Arrow fires as transition cue — skip entirely if no phrase available
        # (phrase="" would fire at time 0.0 before anything is spoken)
        if not info["arrow_phrase"]:
            continue
        script["elements"].append({
            "element_id": f"arrow_{i}",
            "type": "arrow",
            "phrase": info["arrow_phrase"],
            "filename": "arrow.png",
            "description": "Connecting macro to micro",
            "x": int(mid_x),
            "y": int(mid_y),
            "scale": ARROW_SCALE,
            "angle": int(angle_deg),
            "animation": "pop",
            "property": "",
            "reason": "Transition",
            "text_content": ""
        })

        # Micro Image
        if info["img_phrase"] is not None:
            script["elements"].append({
                "element_id": f"img_micro_{i}",
                "type": "image",
                "phrase": info["img_phrase"],
                "filename": f"micro_{i}_img.jpg",
                "description": info["visual_description"],
                "x": x,
                "y": y,
                "scale": MICRO_SCALE,
                "angle": random.randint(-4, 4),
                "animation": "pop",
                "property": "shadow" if info["is_real"] else "",
                "reason": f"Micro detail {i+1}",
                "text_content": ""
            })

        # Micro Text — if too long, split into stacked lines in original word order.
        if info["txt_phrase_raw"] is not None:
            txt_lines = txt_layout["lines"]
            if len(txt_lines) == 1:
                script["elements"].append({
                    "element_id": f"txt_micro_{i}",
                    "type": info["txt_type"],
                    "phrase": info["txt_phrase_raw"],
                    "text_content": txt_lines[0],
                    "x": txt_layout["x"],
                    "y": txt_layout["y"],
                    "scale": txt_layout["scale"],
                    "angle": 0,
                    "animation": "pop",
                    "property": "",
                    "reason": "Micro label",
                    "filename": "",
                    "description": ""
                })
            else:
                print(f"   micro_{i}: split long text into {len(txt_lines)} lines")
                # Split txt_phrase_raw into consecutive sub-phrases — one per line.
                _tw = (info["txt_phrase_raw"] or "").split()
                _tk = len(txt_lines)
                _tb = len(_tw) // _tk if _tk else 1
                _tr = len(_tw) % _tk if _tk else 0
                _tsub = []
                _ti = 0
                for _trow in range(_tk):
                    _ttake = _tb + (1 if _trow < _tr else 0)
                    _tsub.append(" ".join(_tw[_ti:_ti + _ttake]))
                    _ti += _ttake
                for j, line in enumerate(txt_lines):
                    script["elements"].append({
                        "element_id": f"txt_micro_{i}_{j}",
                        "type": info["txt_type"],
                        "phrase": _tsub[j] if j < len(_tsub) else (info["txt_phrase_raw"] or ""),
                        "text_content": line,
                        "x": txt_layout["x"],
                        "y": int(txt_layout["y"] + j * txt_layout["line_gap"]),
                        "scale": txt_layout["scale"],
                        "angle": 0,
                        "animation": "pop",
                        "property": "",
                        "reason": "Micro label line",
                        "filename": "",
                        "description": ""
                    })

    # ═══ Final save ═══════════════════════════════════════════════════════════
    with open(opath, "w") as f:
        json.dump(script, f, indent=2)

    total_el = len(script["elements"])
    
    print(f"\nSaved: {opath}")
    print(f"   1 Macro | {min(3, num_micros)} Micros | {total_el} total elements")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
