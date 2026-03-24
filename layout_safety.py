"""
Layout Safety — Deterministic Canvas Boundary & Overlap Prevention
===================================================================
Import this in any layout generator and call `safe_pass(elements)` as
the final step before saving the director JSON.

Usage:
    from layout_safety import safe_pass
    script["elements"] = safe_pass(script["elements"])

What it does:
  1. clamp_all   — pushes every element back inside the canvas safe zone
  2. check_overlap — detects bounding-box collisions and nudges apart

All math is deterministic (no random). Coordinates stay integers.
"""

# ── Canvas constants (director space) ────────────────────────────────────────
W, H = 1920, 1080
SAFE_MARGIN = 42          # px from each edge — nothing should be closer

# ── Element base sizes (pixels at scale 1.0) ─────────────────────────────────
IMG_BASE   = 1000.0       # generated images are 1024 but we budget 1000
ARROW_W    = 1050.0       # arrow.png intrinsic width
ARROW_H    = 700.0        # arrow.png intrinsic height
TEXT_CHAR_W = 30.0         # Comic Sans MS at fontSize=40 — scene coords per char at scale 1.0
TEXT_LINE_H = 70.0         # approximate line height at scale 1.0


# ══════════════════════════════════════════════════════════════════════════════
#  Bounding-box helpers
# ══════════════════════════════════════════════════════════════════════════════

def _bbox(el):
    """Return (half_w, half_h) for an element — the distance from its center
    to its edges *before rotation* (rotation ignored for simplicity)."""
    t = el.get("type", "")
    sc = el.get("scale", 1.0)

    if t == "image":
        hw = hh = (IMG_BASE * sc) / 2.0
    elif t == "arrow":
        hw = (ARROW_W * sc) / 2.0
        hh = (ARROW_H * sc) / 2.0
    else:
        # text types: text_black, text_red, text_highlighted, etc.
        txt = el.get("text_content", "") or el.get("phrase", "") or ""
        char_count = max(1, len(txt))
        hw = (char_count * TEXT_CHAR_W * sc) / 2.0
        hh = (TEXT_LINE_H * sc) / 2.0

    return hw, hh


def _rect(el):
    """Return (x1, y1, x2, y2) axis-aligned bounding box."""
    hw, hh = _bbox(el)
    cx = el.get("x", 0)
    cy = el.get("y", 0)
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def _overlaps(r1, r2):
    """True if two (x1,y1,x2,y2) rectangles overlap."""
    return not (r1[2] <= r2[0] or r2[2] <= r1[0] or
                r1[3] <= r2[1] or r2[3] <= r1[1])


def _overlap_area(r1, r2):
    """Intersection area of two rects (0 if no overlap)."""
    ox = max(0, min(r1[2], r2[2]) - max(r1[0], r2[0]))
    oy = max(0, min(r1[3], r2[3]) - max(r1[1], r2[1]))
    return ox * oy


# ══════════════════════════════════════════════════════════════════════════════
#  1. clamp_all — push elements inside safe zone
# ══════════════════════════════════════════════════════════════════════════════

def clamp_all(elements, margin=SAFE_MARGIN):
    """Clamp every element so its bounding box stays inside the canvas.

    Modifies elements in-place and returns the list.
    """
    x_min = margin
    x_max = W - margin
    y_min = margin
    y_max = H - margin

    for el in elements:
        hw, hh = _bbox(el)
        cx = el.get("x", 0)
        cy = el.get("y", 0)

        # Clamp center so that box edges stay within safe zone
        new_cx = max(x_min + hw, min(x_max - hw, cx))
        new_cy = max(y_min + hh, min(y_max - hh, cy))

        # For very large elements that exceed canvas, center them
        if hw * 2 > (x_max - x_min):
            new_cx = W / 2
        if hh * 2 > (y_max - y_min):
            new_cy = H / 2

        el["x"] = int(round(new_cx))
        el["y"] = int(round(new_cy))

    return elements


# ══════════════════════════════════════════════════════════════════════════════
#  2. check_overlap — detect and nudge overlapping elements
# ══════════════════════════════════════════════════════════════════════════════

def check_overlap(elements, min_gap=8, max_passes=6):
    """Detect bounding-box overlaps and nudge elements apart.

    Only nudges same-type pairs (image↔image, text↔text).
    Text overlapping its own image is expected (label on image) so we skip
    image↔text pairs.

    After nudging, re-clamps everything to stay on canvas.
    Runs up to `max_passes` iterations to resolve cascading shifts.

    Modifies elements in-place and returns the list.
    """
    for _pass in range(max_passes):
        moved = False
        for i in range(len(elements)):
            for j in range(i + 1, len(elements)):
                ei, ej = elements[i], elements[j]
                ti = ei.get("type", "")
                tj = ej.get("type", "")

                # Skip cross-type pairs (text labels sit on images intentionally)
                is_img_i = (ti == "image" or ti == "arrow")
                is_img_j = (tj == "image" or tj == "arrow")
                is_txt_i = ti.startswith("text")
                is_txt_j = tj.startswith("text")

                if is_img_i != is_img_j:
                    continue  # one is image, other is text — skip

                ri = _rect(ei)
                rj = _rect(ej)

                # Inflate rects by min_gap
                ri_padded = (ri[0] - min_gap, ri[1] - min_gap,
                             ri[2] + min_gap, ri[3] + min_gap)
                rj_padded = (rj[0] - min_gap, rj[1] - min_gap,
                             rj[2] + min_gap, rj[3] + min_gap)

                if not _overlaps(ri_padded, rj_padded):
                    continue

                # Calculate overlap center and push apart
                cx_i, cy_i = ei["x"], ei["y"]
                cx_j, cy_j = ej["x"], ej["y"]

                dx = cx_j - cx_i
                dy = cy_j - cy_i

                # If exactly stacked, push horizontally
                if dx == 0 and dy == 0:
                    dx = 1

                hw_i, hh_i = _bbox(ei)
                hw_j, hh_j = _bbox(ej)

                # Required separation (center-to-center)
                need_x = hw_i + hw_j + min_gap
                need_y = hh_i + hh_j + min_gap

                # Push along the axis with less overlap
                overlap_x = need_x - abs(dx) if abs(dx) < need_x else 0
                overlap_y = need_y - abs(dy) if abs(dy) < need_y else 0

                if overlap_x <= 0 and overlap_y <= 0:
                    continue

                # Choose the cheaper axis to resolve
                if overlap_x > 0 and (overlap_y <= 0 or overlap_x <= overlap_y):
                    nudge = (overlap_x // 2) + 1
                    sign = 1 if dx >= 0 else -1
                    ei["x"] -= int(nudge * sign)
                    ej["x"] += int(nudge * sign)
                else:
                    nudge = (overlap_y // 2) + 1
                    sign = 1 if dy >= 0 else -1
                    ei["y"] -= int(nudge * sign)
                    ej["y"] += int(nudge * sign)

                moved = True

        # Re-clamp after nudges
        clamp_all(elements)

        if not moved:
            break

    return elements


# ══════════════════════════════════════════════════════════════════════════════
#  3. safe_pass — single-call entry point
# ══════════════════════════════════════════════════════════════════════════════

def safe_pass(elements, margin=SAFE_MARGIN, min_gap=8):
    """Run the full safety pipeline on a list of director elements.

    1. Clamp all elements inside the canvas safe zone.
    2. Detect and resolve same-type overlaps.

    Returns the (modified) elements list.
    """
    clamp_all(elements, margin=margin)
    check_overlap(elements, min_gap=min_gap)
    return elements


# ── CLI self-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import glob as _glob

    # Run safety check on all existing director scripts
    pattern = "assets/directorscript/*_director.json"
    files = sorted(_glob.glob(pattern))
    if not files:
        print("No director scripts found to test.")
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        els = data.get("elements", [])
        before = [(e["element_id"], e["x"], e["y"]) for e in els]
        safe_pass(els)
        after = [(e["element_id"], e["x"], e["y"]) for e in els]
        changes = sum(1 for b, a in zip(before, after) if b != a)
        tag = f" ({changes} elements adjusted)" if changes else ""
        print(f"  {os.path.basename(fp)}: {len(els)} elements{tag}")
