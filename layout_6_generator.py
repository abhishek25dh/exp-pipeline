"""
Layout 6 Generator — Two Rows (Image + Texts)
==============================================
Director space: 1920×1080

Layout divides the screen into Top Row and Bottom Row.
Exactly two narrative groups are processed.
Row 1: [Image] [Stacked Texts] (or vice versa)
Row 2: [Stacked Texts] [Image] (alignment alternates)

Text scale computed per-group from longest phrase using approach.md formula.
Consistent scale applied to all texts in a group (block-level).
"""

import json, math, os, random, re, sys

# ── Constants ─────────────────────────────────────────────────────────────────
W, H = 1920, 1080
RENDER = 1024         # base image size at scale 1.0

MARGIN_X = 120
MARGIN_Y = 100
UL, UR = MARGIN_X, W - MARGIN_X
UT, UB = MARGIN_Y, H - MARGIN_Y

ROW_HEIGHT = (UB - UT) / 2
ROW_1_CY = UT + ROW_HEIGHT / 2
ROW_2_CY = UT + ROW_HEIGHT + ROW_HEIGHT / 2

LEFT_CX  = UL + (UR - UL) * 0.28   # 28% from left
RIGHT_CX = UL + (UR - UL) * 0.72   # 72% from left

IMG_SCALE = 0.38
IMG_SIZE  = RENDER * IMG_SCALE

TEXT_GAP = 110        # vertical gap between stacked text elements (scene px)

# Text safe width: approx column width available beside the image (scene px)
TEXT_SAFE_W  = 800
AVG_CHAR_W   = 30     # Comic Sans fontSize=40, scene coords at scale=1 — wider than average


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


def compute_text_scale(phrase: str) -> float:
    n_chars = max(1, len(phrase))
    n_words = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe = TEXT_SAFE_W / (AVG_CHAR_W * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    # Deterministic seed — stable layout across reruns
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s2_path = f"assets/tmp/{sid}_layout_6_step_2_tmp.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s2_path) as f:
            step2 = json.load(f)
    except FileNotFoundError:
        print(f"Error: {s2_path} not found. Run Step 2 first.")
        return 1

    groups = step2.get("detailed_groups", [])
    if len(groups) == 0:
        print(f"Error: Layout 6 got 0 groups from step 2. Cannot proceed.")
        return 1
    if len(groups) < 2:
        # Pad: duplicate the last group so we have 2 rows
        print(f"   Warning: Layout 6 expects 2 groups, got {len(groups)}. Padding with duplicate.")
        while len(groups) < 2:
            groups.append(dict(groups[-1], group_id=f"group_{len(groups)+1}"))
    elif len(groups) > 2:
        # Drop lowest-priority (last) groups
        print(f"   Warning: Layout 6 expects 2 groups, got {len(groups)}. Dropping extras.")
        groups = groups[:2]

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()

    # Count slots: each group has 1 image + N texts
    # Priority order: group1_image, group1_texts..., group2_image, group2_texts...
    _group_slot_counts = []
    for _g in groups:
        _group_slot_counts.append(1 + len(_g.get("texts", [])))
    _total_slots = sum(_group_slot_counts)
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")

    _all_phrases = allot_phrases(_tokens, n_active)
    # Map active slots back to (group_idx, slot_within_group) → phrase
    _active_map = {}
    _sc = 0
    for _ri, _cnt in enumerate(_group_slot_counts):
        for _wi in range(_cnt):
            _active_map[(_ri, _wi)] = _all_phrases[_sc] if _sc < n_active else None
            _sc += 1
    # Build per-group phrase lists from active map
    _group_phrases = []
    for _ri, _cnt in enumerate(_group_slot_counts):
        _group_phrases.append([_active_map[(_ri, _wi)] for _wi in range(_cnt)])

    script = {"scene_id": sid, "elements": []}

    # Alternate image alignment between rows
    top_image_is_left = random.choice([True, False])

    print("   Generating 2-Row Layout...")

    img_counter = 0
    for row_idx, group in enumerate(groups):
        _gp = _group_phrases[row_idx]  # [img_phrase, txt1_phrase, txt2_phrase, ...]
        gid        = group.get("group_id", f"group_{row_idx + 1}")
        image_data = group.get("image", {})
        texts_data = group.get("texts", [])

        cy = ROW_1_CY if row_idx == 0 else ROW_2_CY
        image_on_left = top_image_is_left if row_idx == 0 else not top_image_is_left

        if image_on_left:
            img_x     = LEFT_CX
            texts_cx  = RIGHT_CX
            align_str = "Img-Left"
        else:
            img_x     = RIGHT_CX
            texts_cx  = LEFT_CX
            align_str = "Img-Right"

        # ── Image element ──────────────────────────────────────────────────
        _img_phrase = _gp[0] if len(_gp) > 0 else None
        if _img_phrase is None:
            img_counter += 1
            continue
        script["elements"].append({
            "element_id": f"image_{gid}_0",
            "type":        "image",
            "phrase":      _img_phrase,
            "filename":    f"{gid}_img_{img_counter}.jpg",
            "description": image_data.get("visual_description", ""),
            "x":           int(img_x),
            "y":           int(cy),
            "scale":       IMG_SCALE,
            "angle":       0,
            "animation":   "pop",
            "property":    "shadow",
            "reason":      image_data.get("reason", ""),
            "text_content": ""
        })
        img_counter += 1

        # ── Text elements (block-level consistent scale) ───────────────────
        if texts_data:
            # Compute scale once from the longest phrase in this group
            longest = max(texts_data, key=lambda t: len(t.get("text_content", "")))
            block_scale = compute_text_scale(longest.get("text_content", "x"))

            num_texts = len(texts_data)
            total_height = (num_texts - 1) * TEXT_GAP
            start_y = cy - total_height / 2
            start_y = max(UT, min(start_y, UB - total_height))

            for t_idx, txt in enumerate(texts_data):
                _txt_phrase = _gp[1 + t_idx] if (1 + t_idx) < len(_gp) else None
                if _txt_phrase is None:
                    continue
                txt_y    = start_y + t_idx * TEXT_GAP
                txt_type = txt.get("text_type", "text_highlighted")
                tc       = txt.get("text_content", "")

                script["elements"].append({
                    "element_id":  f"text_{gid}_{t_idx + 1}",
                    "type":        txt_type,
                    "phrase":      _txt_phrase,
                    "text_content": tc,
                    "x":           int(texts_cx),
                    "y":           int(txt_y),
                    "scale":       block_scale,
                    "angle":       0,
                    "animation":   "pop",
                    "property":    "",
                    "reason":      "Emphasis text",
                    "typing_speed": 0.5,
                    "filename":    "",
                    "description": ""
                })

        print(f"   Row {row_idx + 1}: {gid} | Align: {align_str} | "
              f"Texts: {len(texts_data)}")

    with open(opath, "w") as f:
        json.dump(script, f, indent=2)

    total_el  = len(script["elements"])
    num_imgs  = sum(1 for e in script["elements"] if e["type"] == "image")
    num_txts  = sum(1 for e in script["elements"] if "text" in e["type"])
    print(f"\nSaved: {opath}")
    print(f"   {num_imgs} images | {num_txts} texts | {total_el} total elements")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
