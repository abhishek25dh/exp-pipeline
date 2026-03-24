"""
Layout 5 Generator — Cause → Effect
=====================================
Director space: 1920×1080

Each group is a horizontal strip:  [CAUSE_IMG]  [ARROW]  [EFFECT_IMG]
                                     (optional text near one image)

Arrow direction alternates across groups for visual dynamism.
Groups are placed randomly across the canvas with collision avoidance.
Physics relaxation applied to prevent hard overlaps if placement gets tight.
Top ~250px reserved for post-production heading.
"""

import json, os, random, math, re, sys

# ── Constants ─────────────────────────────────────────────────────────────────
W, H = 1920, 1080
TOP_DEAD = 250
MARGIN = 80
RENDER = 1024         # base image size at scale 1.0

# Usable area
UL, UR = MARGIN, W - MARGIN          # 80, 1840
UT, UB = TOP_DEAD, H - MARGIN        # 250, 1000

STRIP_GAP = 30        # gap between cause/arrow/effect within a strip

MIN_SC = 0.12
MAX_SC = 0.55         # let fewer groups fill the canvas

TEXT_H = 60           # approximate height for text element
TEXT_GAP = 20         # gap between image bottom and text

CHAR_PX = 30          # Comic Sans MS scene px per char at scale=1.0
MARGIN  = 80          # matches usable area margin


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


def safe_scale_text(text, center_x, preferred_cap=2.0):
    """Formula-based scale: larger for short text, capped by available width."""
    chars   = max(1, len(text))
    n_words = max(1, len(text.split()))
    avail_half = min(center_x - MARGIN, W - center_x - MARGIN)
    avail_half = max(10, avail_half)
    canvas_safe = (2 * avail_half) / (chars * CHAR_PX)
    preferred   = min(preferred_cap, 14.0 / n_words)
    return round(max(1.0, min(preferred, canvas_safe)), 3)


# ── Scale Calculator ──────────────────────────────────────────────────────────

def compute_image_scale(num_groups):
    """Calculate optimal image scale based on available area and group count.
    Fewer groups → bigger images, up to MAX_SC (0.55).

    Layout 5 strips are 3 elements wide (cause + arrow + effect).
    Physics arranges strips in a 2-column grid for n >= 2 groups.
    The binding constraint is HORIZONTAL: 2 strips must fit side-by-side.

    Derivation:
      strip_half_width = (3 * RENDER * s + 2 * STRIP_GAP) / 2
      4 * strip_half_width + 30 ≤ UR - UL
      → s ≤ (UR - UL - 4 * STRIP_GAP - 30) / (6 * RENDER)  ≈ 0.262
    """
    avail_area = (UR - UL) * (UB - UT)
    budget = avail_area * 0.65
    s = math.sqrt(budget / (max(1, num_groups) * 2.8 * RENDER * RENDER))
    if num_groups == 2:
        # Two strips stacked vertically — each takes full canvas width.
        # Vertical constraint: 2 * strip_height + gap ≤ UB - UT
        vert_cap = (UB - UT - 30) / (2 * RENDER)   # ≈ 0.352
        s = min(s, vert_cap)
    elif num_groups >= 3:
        # 2-column grid — horizontal constraint is binding.
        # Two strips side-by-side: 4 * strip_half_width + 30 ≤ UR - UL
        horiz_cap = (UR - UL - 4 * STRIP_GAP - 30) / (6 * RENDER)  # ≈ 0.262
        s = min(s, horiz_cap)
    return max(MIN_SC, min(MAX_SC, round(s, 3)))


# ── Strip Dimensions ─────────────────────────────────────────────────────────

def strip_dims(img_sc, arrow_sc, has_text):
    """Return (width, height) of a cause→arrow→effect strip."""
    img_size = RENDER * img_sc
    arrow_size = RENDER * arrow_sc
    width = 2 * img_size + arrow_size + 2 * STRIP_GAP
    top_half = max(img_size / 2, arrow_size / 2)
    bottom_half = max(img_size / 2, arrow_size / 2) + (TEXT_GAP + TEXT_H if has_text else 0)
    height = top_half + bottom_half
    return width, height


# ── Physics Relaxation ───────────────────────────────────────────────────────

def run_physics(placed, iterations=50, padding=20):
    """
    Relax overlapping bounding boxes.
    placed format: list of [cx, cy, hw, hh] (we use lists to mutate them)
    """
    for _ in range(iterations):
        moved = False
        for i in range(len(placed)):
            for j in range(i + 1, len(placed)):
                bx1, by1, hw1, hh1 = placed[i]
                bx2, by2, hw2, hh2 = placed[j]
                
                dx = bx1 - bx2
                dy = by1 - by2
                dist_x = abs(dx)
                dist_y = abs(dy)
                
                min_dist_x = hw1 + hw2 + padding
                min_dist_y = hh1 + hh2 + padding
                
                if dist_x < min_dist_x and dist_y < min_dist_y:
                    moved = True
                    overlap_x = min_dist_x - dist_x
                    overlap_y = min_dist_y - dist_y
                    
                    if overlap_x < overlap_y:
                        # Resolve along X
                        push = (overlap_x / 2) + 1
                        sign = 1 if dx > 0 else -1
                        placed[i][0] += push * sign
                        placed[j][0] -= push * sign
                    else:
                        # Resolve along Y
                        push = (overlap_y / 2) + 1
                        sign = 1 if dy > 0 else -1
                        placed[i][1] += push * sign
                        placed[j][1] -= push * sign
        
        # Enforce bounds
        for i in range(len(placed)):
            bx, by, hw, hh = placed[i]
            if bx - hw < UL: placed[i][0] = UL + hw; moved = True
            if bx + hw > UR: placed[i][0] = UR - hw; moved = True
            if by - hh < UT: placed[i][1] = UT + hh; moved = True
            if by + hh > UB: placed[i][1] = UB - hh; moved = True
            
        if not moved:
            break

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"

    # Deterministic scatter/jitter per scene (stable renders).
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s2_path = f"assets/tmp/{sid}_layout_5_step_2_tmp.json"
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

    # Do NOT dedupe groups here.
    # Step 1 is responsible for phrase correctness and full-script tiling.

    n = len(groups)
    if n == 0:
        print("No groups found in Step 2 output.")
        return

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()

    # Count total element slots: each group has cause + arrow + effect + optional text
    _group_slot_counts = []
    for _g in groups:
        _ti = _g.get("text_label", None)
        _has_t = bool(_ti and isinstance(_ti, dict) and _ti.get("text_content", ""))
        _group_slot_counts.append(3 + (1 if _has_t else 0))
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
    _group_phrases = []
    for _ri, _cnt in enumerate(_group_slot_counts):
        _group_phrases.append([_active_map[(_ri, _wi)] for _wi in range(_cnt)])

    script = {"scene_id": sid, "elements": []}

    img_sc = compute_image_scale(n)
    arrow_sc = min(MAX_SC, max(0.20, img_sc))   # arrow scales with images, same max cap
    print(f"   Groups: {n}  |  Image scale: {img_sc}  |  Arrow scale: {arrow_sc}")

    directions = []
    for i in range(n):
        directions.append("right" if i % 2 == 0 else "left")
    random.shuffle(directions)

    # We will compute scale and bounds for everyone first, then just place them roughly and relax
    # Instead of sequential placing, scatter them and run physics!
    
    placed = []
    groups_data = [] # To store precomputed data

    # 1. Initialize random scatter positions
    for g_idx, group in enumerate(groups):
        text_info = group.get("text_label", None)
        has_text = (text_info is not None and isinstance(text_info, dict) and text_info.get("text_content", ""))
        
        sw, sh = strip_dims(img_sc, arrow_sc, has_text)
        hw, hh = sw / 2, sh / 2

        # Start with a random position
        cx = random.uniform(UL + hw, UR - hw)
        cy = random.uniform(UT + hh, UB - hh)

        placed.append([cx, cy, hw, hh])
        groups_data.append({
            "group": group,
            "has_text": has_text,
            "hw": hw, "hh": hh, "sw": sw, "sh": sh,
            "sc": img_sc,
            "arrow_sc": arrow_sc,
            "dir": directions[g_idx]
        })

    # 2. Physics relaxation
    run_physics(placed, iterations=150, padding=30)

    # 3. Apply final placed coordinates
    img_counter = 0
    for g_idx, gdata in enumerate(groups_data):
        _gp = _group_phrases[g_idx]  # [cause_phrase, arrow_phrase, effect_phrase, (text_phrase)]
        cx, cy, hw, hh = placed[g_idx]
        group = gdata["group"]
        has_text = gdata["has_text"]
        current_sc = gdata["sc"]
        direction = gdata["dir"]
        sw, sh = gdata["sw"], gdata["sh"]
        
        gid = group.get("group_id", f"group_{img_counter}")
        cause = group.get("cause", {})
        effect = group.get("effect", {})
        text_info = group.get("text_label", {})
        current_arrow_sc = gdata["arrow_sc"]

        img_size = RENDER * current_sc
        arrow_size = RENDER * current_arrow_sc

        left_img_x = cx - sw / 2 + img_size / 2
        arrow_x = cx
        right_img_x = cx + sw / 2 - img_size / 2

        if has_text:
            img_y = cy - (TEXT_GAP + TEXT_H) / 2
            text_y = img_y + img_size / 2 + TEXT_GAP + TEXT_H / 2
        else:
            img_y = cy
            text_y = None

        if direction == "right":
            cause_x, effect_x = left_img_x, right_img_x
            arrow_angle = random.randint(-4, 4)
        else:
            cause_x, effect_x = right_img_x, left_img_x
            arrow_angle = 180 + random.randint(-4, 4)

        _cause_phrase = _gp[0] if len(_gp) > 0 else None
        if _cause_phrase is None:
            img_counter += 1
            continue
        script["elements"].append({
            "element_id": f"image_{gid}_cause",
            "type": "image",
            "phrase": _cause_phrase,
            "filename": f"{gid}_cause_{img_counter}.jpg",
            "description": cause.get("visual_description", ""),
            "x": int(cause_x),
            "y": int(img_y),
            "scale": round(current_sc, 3),
            "angle": 0,
            "animation": "pop",
            "property": "shadow",
            "reason": f"Cause image for {gid}",
            "text_content": ""
        })

        _arrow_phrase = _gp[1] if len(_gp) > 1 else ""
        script["elements"].append({
            "element_id": f"arrow_{gid}",
            "type": "arrow",
            "phrase": _arrow_phrase or "",
            "filename": "arrow.png",
            "description": "",
            "x": int(arrow_x),
            "y": int(img_y),
            "scale": current_arrow_sc,
            "angle": arrow_angle,
            "animation": "pop",
            "property": "",
            "reason": f"Cause-to-effect arrow for {gid}",
            "text_content": ""
        })

        _effect_phrase = _gp[2] if len(_gp) > 2 else None
        if _effect_phrase is None:
            img_counter += 1
            continue
        script["elements"].append({
            "element_id": f"image_{gid}_effect",
            "type": "image",
            "phrase": _effect_phrase,
            "filename": f"{gid}_effect_{img_counter}.jpg",
            "description": effect.get("visual_description", ""),
            "x": int(effect_x),
            "y": int(img_y),
            "scale": round(current_sc, 3),
            "angle": 0,
            "animation": "pop",
            "property": "shadow",
            "reason": f"Effect image for {gid}",
            "text_content": ""
        })

        if has_text and text_y is not None:
            _text_phrase = _gp[3] if len(_gp) > 3 else None
            if _text_phrase is not None:
                assoc = text_info.get("associated_with", "effect")
                if assoc == "cause":
                    txt_x = int(cause_x)
                else:
                    txt_x = int(effect_x)

                _tc = text_info.get("text_content", "")
                script["elements"].append({
                    "element_id": f"text_{gid}",
                    "type": "text_highlighted",
                    "phrase": _text_phrase,
                    "text_content": _tc,
                    "x": txt_x,
                    "y": int(text_y),
                    "scale": safe_scale_text(_tc, txt_x),
                    "angle": 0,
                    "animation": "pop",
                    "property": "",
                    "reason": text_info.get("reason", "Extra context text"),
                    "typing_speed": 0.5,
                    "filename": "",
                    "description": ""
                })

        print(f"   {gid}: center=({int(cx)},{int(cy)}) dir={direction} "
              f"scale={current_sc}"
              f"{' +text' if has_text else ''}")
        img_counter += 1

    with open(opath, "w") as f:
        json.dump(script, f, indent=2)

    total_el = len(script["elements"])
    imgs = [e for e in script["elements"] if e["type"] == "image"]
    arrows = [e for e in script["elements"] if e["type"] == "arrow"]
    texts = [e for e in script["elements"] if "text" in e["type"]]
    print(f"\nSaved: {opath}")
    print(f"   {n} groups | {len(imgs)} images | {len(arrows)} arrows | "
          f"{len(texts)} texts | {total_el} total elements")

if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
