import json
import os
import re
import sys
import hashlib

W, H = 1920, 1080
BASE_IMG_SIZE = 1000.0
MAX_SCALE = 0.24          # default; overridden per total image count in main()
DEFAULT_GAP = 28.0
MIN_GAP = 0.0

# Dynamic max scale by total image count (avoids overlap / canvas overflow):
#   1 image  -> up to 0.60  (600px fits in 680px available height, 636px safe column width)
#   2 images -> up to 0.45  (if in separate columns each gets ~0.60; if stacked ~0.33 fits)
#   3-4      -> up to 0.32
#   5+       -> 0.24 (original)
_SCALE_BY_COUNT = {1: 0.60, 2: 0.45, 3: 0.32, 4: 0.32}
_DEFAULT_MAX_SCALE = 0.24

COLUMN_CENTERS = {
    "left": 360,
    "middle": 960,
    "right": 1560,
}

TEXT_Y = 190
TEXT_SCALE = 1.63      # max allowed scale -- calibrated for mixed-case Comic Sans
IMAGE_TOP = 340
IMAGE_BOTTOM = 1020
TEXT_CHAR_PX = 20.0    # mixed-case Comic Sans avg char width (was 30.0 for ALL-CAPS)
TEXT_MIN_SCALE = 0.9
WRAP_MIN_SCALE = 0.75

X_JITTER_PX = 92.0
Y_JITTER_PX = 26.0
ANGLE_JITTER_DEG = 7.0
SAFE_MARGIN_PX = 42.0


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


def _unit_from_hash(seed: str) -> float:
    # Deterministic pseudo-random in [-1, 1]. Avoid Python's salted hash().
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    n = int.from_bytes(digest[:4], "big")
    u01 = n / 2**32  # [0, 1)
    return (u01 * 2.0) - 1.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _fit_column_stack(count: int, max_scale: float = MAX_SCALE):
    if count <= 0:
        return 0.0, 0.0, []

    available_h = float(IMAGE_BOTTOM - IMAGE_TOP)
    gap_candidates = [DEFAULT_GAP, 20.0, 12.0, 6.0, 2.0, MIN_GAP]
    chosen_gap = MIN_GAP
    chosen_scale = 0.05

    for gap in gap_candidates:
        fit_scale = (available_h - (count - 1) * gap) / (count * BASE_IMG_SIZE)
        fit_scale = min(max_scale, fit_scale)
        if fit_scale > 0:
            chosen_gap = gap
            chosen_scale = fit_scale
            break

    if chosen_scale <= 0:
        chosen_gap = 0.0
        chosen_scale = available_h / max(1.0, count * BASE_IMG_SIZE)

    item_h = BASE_IMG_SIZE * chosen_scale
    used_h = count * item_h + (count - 1) * chosen_gap
    start_cy = IMAGE_TOP + (available_h - used_h) / 2.0 + item_h / 2.0
    ys = [start_cy + i * (item_h + chosen_gap) for i in range(count)]
    return chosen_scale, chosen_gap, ys


def _column_sort_key(item):
    span = item.get("span", [10**9, 10**9])
    sg = item.get("subgroup", 1)
    return (int(sg), span[0], span[1], item.get("element_id", ""))


def _fit_text_scale(text: str, x: float, base_scale: float = TEXT_SCALE):
    phrase = (text or "").strip()
    if not phrase:
        return base_scale
    half_width = max(1.0, min(x, W - x) - 40.0)
    max_text_width = 2.0 * half_width
    fit = max_text_width / max(1.0, len(phrase) * TEXT_CHAR_PX)
    return round(min(base_scale, max(TEXT_MIN_SCALE, fit)), 3)


def _wrap_text_lines(text: str, x: float, base_scale: float = TEXT_SCALE):
    phrase = (text or "").strip()
    if not phrase:
        return [phrase], base_scale

    half_width = max(1.0, min(x, W - x) - 40.0)
    max_text_width = 2.0 * half_width

    # If it fits at or above TEXT_MIN_SCALE, keep single-line.
    fit_single = max_text_width / max(1.0, len(phrase) * TEXT_CHAR_PX)
    if fit_single >= TEXT_MIN_SCALE:
        return [phrase], round(min(base_scale, fit_single), 3)

    # Otherwise, wrap into multiple lines aiming to fit at WRAP_MIN_SCALE.
    max_chars = int(max_text_width / max(1.0, TEXT_CHAR_PX * WRAP_MIN_SCALE))
    max_chars = max(8, max_chars)

    words = phrase.split()
    lines = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
            continue
        if len(cur) + 1 + len(w) <= max_chars:
            cur = f"{cur} {w}"
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    # Keep a small bound on line count to avoid stacking into images.
    if len(lines) > 3:
        lines = lines[:2] + [" ".join(lines[2:])]

    # Avoid a lonely single-word last line when we can balance it.
    if len(lines) >= 2 and len(lines[-1].split()) == 1:
        prev_words = lines[-2].split()
        if len(prev_words) >= 3:
            moved = prev_words.pop()
            lines[-2] = " ".join(prev_words)
            lines[-1] = f"{moved} {lines[-1]}"

    # Choose a uniform scale that makes every line fit (allow smaller than TEXT_MIN_SCALE when wrapped).
    fits = [max_text_width / max(1.0, len(ln) * TEXT_CHAR_PX) for ln in lines if ln.strip()]
    fit_all = min(fits) if fits else WRAP_MIN_SCALE
    scale = min(base_scale, max(0.6, min(1.0, fit_all)))
    return lines, round(scale, 3)


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    step_1_path = f"assets/tmp/{scene_id}_layout_1_step_1_tmp.json"
    step_4_path = f"assets/tmp/{scene_id}_layout_1_step_4_tmp.json"
    output_dir = "assets/directorscript"
    output_path = os.path.join(output_dir, f"{scene_id}_director.json")
    os.makedirs(output_dir, exist_ok=True)

    with open(step_1_path, "r", encoding="utf-8") as f:
        step_1_data = json.load(f)
    with open(step_4_path, "r", encoding="utf-8") as f:
        step_4_data = json.load(f)

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{scene_id}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()

    # Count elements: texts (from step 1) + images (from step 4)
    _main_texts = step_1_data.get("main_texts", [])
    _all_images = step_4_data.get("final_elements", [])
    _n_texts = len(_main_texts)
    _n_images = len(_all_images)

    # Text elements: use anchor_spans from step_1 as phrase triggers.
    # Each text fires exactly when its own anchor words are spoken.
    _anchor_spans = step_1_data.get("anchor_spans", {})
    _text_anchor_phrases = {}
    _covered_indices = set()
    for _txt in _main_texts:
        _eid = _txt.get("element_id", "")
        _span = _anchor_spans.get(_eid)
        if _span and len(_span) == 2:
            _s, _e = int(_span[0]), int(_span[1])
            _toks = _tokens[_s:min(_e, len(_tokens))]
            if _toks:
                _text_anchor_phrases[_eid] = " ".join(_toks)
                _covered_indices.update(range(_s, min(_e, len(_tokens))))

    # Remaining tokens (not covered by any anchor) are allotted to images
    _remaining_tokens = [t for i, t in enumerate(_tokens) if i not in _covered_indices]
    _image_phrases = allot_phrases(_remaining_tokens, _n_images)

    director_script = {"scene_id": scene_id, "elements": []}

    for _ti, txt in enumerate(step_1_data.get("main_texts", [])):
        _eid_txt = txt.get("element_id", f"text_{_ti}")
        _txt_phrase = _text_anchor_phrases.get(_eid_txt)
        if _txt_phrase is None:
            continue
        col = txt.get("column", "middle")
        phrase = txt.get("text_content", "")
        x = COLUMN_CENTERS.get(col, 960)
        lines, text_scale = _wrap_text_lines(phrase, x)
        line_spacing = int(round(70.0 * text_scale))
        base_id = txt.get("element_id", "text_unk")
        base_anim = "slide_in_left" if col == "left" else ("pop" if col == "right" else "fade_up")

        for li, line in enumerate(lines):
            element_id = base_id if li == 0 else f"{base_id}_l{li + 1}"
            director_script["elements"].append(
                {
                    "element_id": element_id,
                    "type": txt.get("type", "text_highlighted"),
                    "phrase": _txt_phrase if li == 0 else (line or "").strip(),
                    "text_content": (line or "").strip(),
                    "x": x,
                    "y": TEXT_Y + (li * line_spacing),
                    "scale": text_scale,
                    "angle": 0,
                    "animation": base_anim if li == 0 else "fade_up",
                    "property": "",
                    "reason": txt.get("reason", ""),
                    "typing_speed": 0.5,
                    "filename": "",
                    "description": "",
                }
            )

    # Build an index map from image element_id to its allotted phrase
    _img_phrase_map = {}
    for _ii, _img in enumerate(_all_images):
        _img_eid = _img.get("element_id", f"image_unk_{_ii}")
        _img_phrase_map[_img_eid] = _image_phrases[_ii] if _ii < len(_image_phrases) else None

    columns = {"left": [], "middle": [], "right": []}
    for img in step_4_data.get("final_elements", []):
        col = img.get("column", "middle")
        if col in columns:
            columns[col].append(img)

    # Dynamic max scale based on total image count
    total_images = sum(len(v) for v in columns.values())
    dyn_max_scale = _SCALE_BY_COUNT.get(total_images, _DEFAULT_MAX_SCALE)

    column_file_counter = {"left": 0, "middle": 0, "right": 0}
    for col in ("left", "middle", "right"):
        col_items = sorted(columns[col], key=_column_sort_key)
        if not col_items:
            continue

        # Also cap by horizontal safe width for this column
        col_x = float(COLUMN_CENTERS[col])
        half_safe_w = max(1.0, min(col_x, W - col_x) - SAFE_MARGIN_PX)
        max_scale_h = half_safe_w * 2.0 / BASE_IMG_SIZE
        col_max_scale = min(dyn_max_scale, max_scale_h)

        scale, gap, ys = _fit_column_stack(len(col_items), col_max_scale)
        base_x = float(COLUMN_CENTERS[col])
        item_size = BASE_IMG_SIZE * scale
        half = item_size / 2.0
        y_jitter_cap = min(Y_JITTER_PX, max(0.0, gap * 0.35))

        for i, img in enumerate(col_items):
            idx = column_file_counter[col]
            column_file_counter[col] += 1

            eid = img.get("element_id", f"image_{col}_{idx}")
            _img_allot_phrase = _img_phrase_map.get(eid)
            if _img_allot_phrase is None:
                continue
            # Small deterministic collage feel while staying roughly column-aligned.
            kx = _unit_from_hash(f"{scene_id}|{eid}|x")
            ky = _unit_from_hash(f"{scene_id}|{eid}|y")
            ka = _unit_from_hash(f"{scene_id}|{eid}|a")

            alt = -1.0 if (i % 2 == 0) else 1.0
            dx = (alt * X_JITTER_PX * 0.55) + (kx * X_JITTER_PX * 0.45)
            dy = (alt * y_jitter_cap * 0.45) + (ky * y_jitter_cap * 0.55)
            ang = ka * ANGLE_JITTER_DEG

            x = _clamp(base_x + dx, SAFE_MARGIN_PX + half, W - SAFE_MARGIN_PX - half)
            y = _clamp(float(ys[i]) + dy, SAFE_MARGIN_PX + half, H - SAFE_MARGIN_PX - half)

            director_script["elements"].append(
                {
                    "element_id": eid,
                    "type": "image",
                    "phrase": _img_allot_phrase,
                    "filename": f"{col}_image_{idx}.jpg",
                    "description": img.get("visual_description", ""),
                    "x": int(round(x)),
                    "y": int(round(y)),
                    "scale": round(scale, 3),
                    "angle": int(round(ang)),
                    "animation": "pop",
                    "property": "shadow",
                    "reason": img.get("reason", ""),
                    "text_content": "",
                }
            )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(director_script, f, ensure_ascii=False, indent=2)

    print(f"Director Script successfully generated: {output_path}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
