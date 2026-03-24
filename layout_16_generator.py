"""
Layout 16 Generator — Filmstrip
================================
Director space: 1920x1080

Layout:
- Strip title at top center
- Strip subtitle below title
- 5 images in a horizontal row at mid-screen
- Caption label directly beneath each image
"""

import json, os, random, re, sys

W, H = 1920, 1080

IMG_SCALE  = 0.18
IMG_RADIUS = int(1024 * IMG_SCALE / 2)    # 92 px

MARGIN_X  = 192
IMG_Y     = 500
CAPTION_Y = IMG_Y + IMG_RADIUS + 60       # 652

TITLE_Y = 220
SUB_Y   = 340

NUM_FRAMES = 5

CHAR_PX     = 30    # Comic Sans fontSize=40, scene coords — empirically confirmed wider than average
MARGIN_SAFE = 80    # px buffer from canvas edge


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
    """Formula-based scale: larger for short text, capped by canvas width."""
    chars   = max(1, len(text))
    n_words = max(1, len(text.split()))
    available_half = min(center_x, W - center_x) - MARGIN_SAFE
    available_half = max(10, available_half)
    canvas_safe = (2 * available_half) / (chars * CHAR_PX)
    preferred   = min(preferred_cap, 14.0 / n_words)
    return round(max(1.0, min(preferred, canvas_safe)), 3)


def split_caption(text):
    """Split at the nearest word boundary to the midpoint."""
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


def needs_split(text, frame_half_px):
    """True if text at CAP_SCALE overflows the frame's half-width."""
    return (len(text) * CHAR_PX * CAP_SCALE / 2) > frame_half_px - 10


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

    s2_path = f"assets/tmp/{sid}_layout_16_step_2_tmp.json"
    odir    = "assets/directorscript"
    opath   = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s2_path) as f:
            d = json.load(f)
    except FileNotFoundError:
        print(f"Error: {s2_path} not found. Run Step 1 & Step 2 first.")
        return 1

    strip_title    = d.get("strip_title", "THE JOURNEY")
    strip_subtitle = d.get("strip_subtitle", "")
    frames         = d.get("detailed_frames", [])

    if len(frames) != NUM_FRAMES:
        print(f"Warning: Expected {NUM_FRAMES} frames, got {len(frames)}. Proceeding anyway.")

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    n_tokens = len(_tokens)

    # Priority-based frame dropping: each frame pair needs ~3 tokens to be non-trivial.
    # Drop lower-priority (later) frames when the script is too short.
    # P1=title, P2..P6=frames 1-5, P7=subtitle (lowest, optional)
    _n_active_frames = min(len(frames), max(1, (n_tokens - 2) // 3))

    # strip_subtitle is lowest priority — include only if tokens are plentiful enough
    # that every slot (title + subtitle + frames) gets at least 2 tokens each.
    # Below that threshold the subtitle slot gets squeezed to a single stop word.
    _slots_with_sub = 1 + 1 + _n_active_frames * 2
    _include_subtitle = bool(strip_subtitle) and (n_tokens >= _slots_with_sub * 2)

    _n_slots = 1 + (1 if _include_subtitle else 0) + _n_active_frames * 2
    _phrases = allot_phrases(_tokens, _n_slots)
    _pi = 0
    _title_phrase = _phrases[_pi]; _pi += 1
    _sub_phrase   = _phrases[_pi] if _include_subtitle else None; _pi += (1 if _include_subtitle else 0)
    _frame_phrases = _phrases[_pi:]  # pairs: [img0, cap0, img1, cap1, ...]

    print(f"   Token budget: {n_tokens} tokens -> {_n_active_frames} active frames, subtitle={'yes' if _include_subtitle else 'dropped'}")

    script = {"scene_id": sid, "elements": []}
    els    = script["elements"]

    # ── Titles ─────────────────────────────────────────────────────────────────
    title_upper = strip_title.upper()
    title_scale = safe_scale(title_upper, W // 2, preferred_cap=3.5)
    if _title_phrase is not None:
        els.append(make_el("strip_title", "text_highlighted",
                           _title_phrase,
                           W // 2, TITLE_Y, title_scale,
                           animation="slide_in_up",
                           text_content=title_upper))

    if strip_subtitle and _sub_phrase is not None:
        sub_scale = safe_scale(strip_subtitle, W // 2, preferred_cap=2.5)
        els.append(make_el("strip_subtitle", "text_black",
                           _sub_phrase,
                           W // 2, SUB_Y, sub_scale,
                           animation="slide_in_up"))

    # ── X positions: evenly spaced across canvas ───────────────────────────────
    n = len(frames)
    if n == 1:
        x_positions = [W // 2]
    else:
        span = W - 2 * MARGIN_X
        x_positions = [MARGIN_X + i * (span // (n - 1)) for i in range(n)]

    # ── Frames ────────────────────────────────────────────────────────────────
    # Each frame: image phrase = narrative (full sentence), caption phrase = short ALL-CAPS
    # This ensures every element has its own unique phrase.
    frame_half_px = (x_positions[1] - x_positions[0]) / 2 if len(x_positions) > 1 else MARGIN_X

    for i, frame in enumerate(frames[:_n_active_frames]):
        fx       = x_positions[i]
        fid      = frame.get("frame_id", f"frame_{i+1}")
        cap_type = frame.get("caption_type", "text_black")
        img_data = frame.get("image", {})
        is_real  = img_data.get("is_realistic", False)

        _img_p = _frame_phrases[i * 2] if (i * 2) < len(_frame_phrases) else None
        _cap_p = _frame_phrases[i * 2 + 1] if (i * 2 + 1) < len(_frame_phrases) else None
        if _img_p is None and _cap_p is None:
            continue

        if _img_p is not None:
            els.append(make_el(f"img_{fid}", "image", _img_p,
                               fx, IMG_Y, IMG_SCALE,
                               animation="pop",
                               prop="shadow" if is_real else "",
                               filename=f"{fid}_img.jpg",
                               description=img_data.get("visual_description", "")))

        if _cap_p is not None:
            # Caption scale: formula-based, capped by frame width
            cap_safe_w   = max(10, 2 * (frame_half_px - 20))
            cap_scale    = safe_scale(_cap_p, fx, preferred_cap=1.8)
            cap_scale    = round(min(cap_scale, cap_safe_w / max(1, len(_cap_p) * CHAR_PX)), 3)
            cap_scale    = max(1.0, cap_scale)
            els.append(make_el(f"cap_{fid}", cap_type, _cap_p,
                               fx, CAPTION_Y, cap_scale,
                               animation="pop"))

    with open(opath, "w") as f:
        json.dump(script, f, indent=2)

    print(f"\nSaved: {opath}")
    print(f"   {len(els)} elements total ({len(frames)} frames)")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
