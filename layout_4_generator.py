"""
Layout 4 Generator — Fully Random Placement
=============================================
Director space: 1920×1080 | Canvas: 960×540
Fabric image base: 1024×1024 at scaleX = director_scale / 2
Rendered size = 1024 * scale

Randomness:
  - Host can be in ANY of 4 corners (ignores host_side from input)
  - Text can be in any REMAINING corner (not same as host)
  - Both positions have jitter so they're never identical between runs
  - Text scale can shrink to 1.5 if space is tight
  - Host scale shrinks (down to 0.48) when many images
"""

import json, math, os, random, re, sys
from typing import List, Tuple, Optional, Dict

# ── Constants ─────────────────────────────────────────────────────────────────
W, H     = 1920, 1080
TOP_DEAD = 80
EX, EY   = 160, 80
RENDER   = 1024

UL, UR = EX, W - EX             # 160, 1760
UT, UB = TOP_DEAD + EY, H - EY  # 330, 1000
UW, UH = UR - UL, UB - UT       # 1600, 670

GAP_FIX      = 35
GAP_IMG      = 24
MIN_SC       = 0.12
MAX_SC       = 0.55
MAX_ACTIVE   = 6    # max floating images; keeps scales healthy and canvas uncluttered

CHAR_W   = 50      # director px per char at scale 2.25
TEXT_H   = 110      # text line height at scale 2.25
MIN_TEXT_SC = 1.5   # text scale can shrink to this
MAX_TEXT_SC = 2.25  # default text scale


# ── Phrase allocation ─────────────────────────────────────────────────────────

def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def allot_phrases(tokens, n_slots):
    """Split tokens proportionally into n_slots phrases.
    Returns list of str|None — None means element gets no phrase and is skipped."""
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
                give = remaining_tokens   # last slot absorbs leftover
            results.append(" ".join(tokens[t: t + give]))
            t += give
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def wrap_text(text, mx=13):
    words = text.split()
    if not words: return [""]
    lines, cur, cl = [], [], 0
    for w in words:
        if not cur: cur.append(w); cl = len(w)
        elif cl+1+len(w) <= mx: cur.append(w); cl += 1+len(w)
        else: lines.append(" ".join(cur)); cur=[w]; cl=len(w)
    if cur: lines.append(" ".join(cur))
    return lines

def get_gid(el):
    eid = el.get("element_id", el.get("phrase_id", ""))
    p = eid.split("_")
    return p[2] if len(p) >= 3 and p[0] == "image" and p[1] == "group" else None

def box_hit(ax, ay, ahw, ahh, bx, by, bhw, bhh, gap=0):
    return abs(ax-bx) < ahw+bhw+gap and abs(ay-by) < ahh+bhh+gap


# ── Placed-element tracker ────────────────────────────────────────────────────

class Box:
    __slots__ = ('x','y','hw','hh','fixed')
    def __init__(self, x, y, hw, hh, fixed=False):
        self.x, self.y, self.hw, self.hh, self.fixed = x, y, hw, hh, fixed


def collides(x, y, hw, hh, placed: List[Box]) -> bool:
    for p in placed:
        gap = GAP_FIX if p.fixed else GAP_IMG
        if box_hit(x, y, hw, hh, p.x, p.y, p.hw, p.hh, gap):
            return True
    return False


def find_spot_random(hw, hh, placed, tries=3000):
    for _ in range(tries):
        x = random.uniform(UL+hw, UR-hw)
        y = random.uniform(UT+hh, UB-hh)
        if not collides(x, y, hw, hh, placed):
            return (x, y)
    return None


def find_spot_scan(hw, hh, placed, step=20):
    valid = []
    x = UL + hw
    while x + hw <= UR:
        y = UT + hh
        while y + hh <= UB:
            if not collides(x, y, hw, hh, placed):
                valid.append((x, y))
            y += step
        x += step
    return random.choice(valid) if valid else None


def find_spot_near(hw, hh, placed, cx, cy, radius=300, tries=2000):
    for phase in range(5):
        r = radius * (1 + phase * 0.6)
        for _ in range(tries // 5):
            x = cx + random.uniform(-r, r)
            y = cy + random.uniform(-r, r)
            x = max(UL+hw, min(UR-hw, x))
            y = max(UT+hh, min(UB-hh, y))
            if not collides(x, y, hw, hh, placed):
                return (x, y)
    return find_spot_scan(hw, hh, placed, step=20)


def find_spot_anywhere(hw, hh, placed):
    pos = find_spot_random(hw, hh, placed, tries=2000)
    return pos if pos else find_spot_scan(hw, hh, placed, step=20)


def find_spot_shrinking(hw_base, placed, scale, min_scale=MIN_SC):
    s = scale
    while s >= min_scale:
        hw = RENDER * s / 2
        pos = find_spot_anywhere(hw, hw, placed)
        if pos:
            return pos, s
        s = round(s - 0.01, 3)
    return None, min_scale


# ── Scale calculator ──────────────────────────────────────────────────────────

def compute_group_scales(groups, total, free_area):
    n = len(groups)
    if n == 0: return {}

    if n == 1:
        gid = list(groups.keys())[0]
        c = len(groups[gid])
        max_cell = math.sqrt(free_area * 0.85 / max(1, c))
        s = (max_cell - GAP_IMG) / RENDER
        return {gid: min(MAX_SC, max(MIN_SC, round(s, 3)))}

    budget = free_area * 0.80
    max_cell = math.sqrt(budget / max(1, total))
    uniform_s = (max_cell - GAP_IMG) / RENDER
    uniform_s = min(0.45, max(MIN_SC, uniform_s))

    sorted_gids = sorted(groups.keys(), key=lambda g: len(groups[g]))
    result = {}
    for rank, gid in enumerate(sorted_gids):
        t = rank / max(1, n - 1)
        multiplier = 1.05 - t * 0.10
        s = uniform_s * multiplier
        result[gid] = max(MIN_SC, min(0.55, round(s, 3)))

    used = sum(len(groups[g]) * (RENDER * result[g] + GAP_IMG)**2 for g in groups)
    if used > budget:
        ratio = math.sqrt(budget / used) * 0.95
        for g in result:
            result[g] = max(MIN_SC, round(result[g] * ratio, 3))

    return result


# ── Corner position helpers ───────────────────────────────────────────────────

CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"]

def corner_pos(corner, hw, hh, jitter=40):
    """Return (x, y) for an element placed in the given corner with random jitter."""
    margin = 30
    j = random.randint(0, jitter)

    if "left" in corner:
        x = UL + hw + margin + j
    else:
        x = UR - hw - margin - j

    if "top" in corner:
        y = UT + hh + margin + j
    else:
        y = UB - hh - margin - j

    return x, y


def opposite_corners(corner):
    """Return list of corners that are NOT the same as the given one, sorted by distance (diagonal first)."""
    diagonal = {
        "top-left": "bottom-right", "top-right": "bottom-left",
        "bottom-left": "top-right", "bottom-right": "top-left"
    }
    adjacent = [c for c in CORNERS if c != corner and c != diagonal[corner]]
    return [diagonal[corner]] + adjacent  # diagonal first, then adjacent


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"
    # Seed random deterministically so layout is stable across reruns
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))
    s1 = f"assets/tmp/{sid}_layout_4_step_1_tmp.json"
    s3 = f"assets/tmp/{sid}_layout_4_step_3_tmp.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s1) as f: setup = json.load(f).get("setup", {})
    except FileNotFoundError:
        setup = {"main_text": "DYNAMIC TITLE", "host_emotion": "explaining",
                 "host_side": "left", "host_size": "half_bottom"}

    try:
        with open(s3) as f: step3 = json.load(f)
    except FileNotFoundError:
        step3 = {"grouped_elements": []}

    script = {"scene_id": sid, "elements": []}
    placed: List[Box] = []

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json") as f:
            prompt_data = json.load(f)
        scene_text = strip_scene_prefix(prompt_data.get("prompt", ""))
    except FileNotFoundError:
        scene_text = ""
    tokens = scene_text.split()

    # ═══ 1. HOST — P1 (always appears) ════════════════════════════════════════
    hsize        = setup.get("host_size", "half_bottom")
    emot         = setup.get("host_emotion", "explaining")
    mtxt         = setup.get("main_text", "TITLE")
    anchor_type  = setup.get("anchor_type", "text_highlighted")

    images = step3.get("grouped_elements", [])
    n_images = len(images)

    # ── Priority-based phrase allocation ─────────────────────────────────────
    # P1=host, P2=text use step_1 anchor phrases (spans are the source of truth).
    # Remaining uncovered tokens are allotted to images (P3+) by token budget.
    img_priority = list(range(n_images))
    random.shuffle(img_priority)   # seeded — random priority P3..Pn

    host_phrase_s1 = setup.get("host_phrase", "")
    text_phrase_s1 = setup.get("phrase", "")

    # Find which tokens are consumed by host and text anchor phrases
    covered = set()
    for anchor in [host_phrase_s1, text_phrase_s1]:
        if not anchor:
            continue
        aw = anchor.split()
        for si in range(len(tokens) - len(aw) + 1):
            if tokens[si:si + len(aw)] == aw:
                covered.update(range(si, si + len(aw)))
                break

    remaining_tokens = [t for i, t in enumerate(tokens) if i not in covered]

    # Token-budget dropping: 2 tokens minimum per image slot
    n_active_cap = min(n_images, MAX_ACTIVE, max(0, len(remaining_tokens) // 2))
    img_allot = allot_phrases(remaining_tokens, n_active_cap) if n_active_cap > 0 else []

    img_phrases = [None] * n_images
    for rank, orig_idx in enumerate(img_priority):
        if rank >= n_active_cap:
            break
        img_phrases[orig_idx] = img_allot[rank] if rank < len(img_allot) else None

    active_images  = [img for i, img in enumerate(images) if img_phrases[i] is not None]
    active_phrases = [img_phrases[i] for i, img in enumerate(images) if img_phrases[i] is not None]

    # Final phrase values: step_1 anchors for host/text, fallback to allot if missing
    host_phrase_v = host_phrase_s1 or (tokens[0] if tokens else "")
    text_phrase_v = text_phrase_s1 or None

    print(f"   Phrase allocation: host=P1, text={'P2' if text_phrase_v else 'skipped'}, "
          f"images={len(active_images)}/{n_images} active ({len(remaining_tokens)} remaining tokens)")

    # Host scale: shrink when lots of active images
    base_host_sc = 0.70 if hsize == "full" else 0.62
    if len(active_images) > 12:
        hsc = max(0.48, base_host_sc - 0.10)
    elif len(active_images) > 8:
        hsc = max(0.48, base_host_sc - 0.05)
    else:
        hsc = base_host_sc

    # Use actual rendered half-size for host collision box
    h_hw = RENDER * hsc / 2
    h_hh = RENDER * hsc / 2

    # half_bottom host prefers bottom corners so top half stays open for images
    if hsize == "half_bottom":
        host_corner = random.choices(
            ["bottom-left", "bottom-right", "top-left", "top-right"],
            weights=[45, 45, 5, 5], k=1
        )[0]
    else:
        host_corner = random.choice(CORNERS)
    hx, hy = corner_pos(host_corner, h_hw, h_hh, jitter=30)

    host_side = "left" if "left" in host_corner else "right"

    placed.append(Box(hx, hy, h_hw, h_hh, fixed=True))
    script["elements"].append({
        "element_id": "host_character", "type": "image", "phrase": host_phrase_v,
        "filename": f"host_{emot}.png", "description": "Host Character",
        "x": hx, "y": hy, "scale": hsc, "angle": 0,
        "animation": f"slide_in_{host_side}",
        "property": "", "reason": "Host P1", "text_content": "",
    })

    print(f"   Host: {host_corner} ({int(hx)},{int(hy)}) hw={int(h_hw)} hh={int(h_hh)} scale={hsc}")

    # ═══ 2. TITLE TEXT — P2 (skipped if no phrase remaining) ═════════════════
    # Text safe width for corner zone (host occupies one side ~700px)
    TEXT_SAFE_W = 900   # scene px available for corner text
    AVG_CHAR_W  = 20    # scene px per char at scale=1 (mixed-case Comic Sans)

    anchor_phrase = mtxt   # AI-generated label shown visually
    n_chars = max(1, len(anchor_phrase))
    n_words = max(1, len(anchor_phrase.split()))
    pref_sc = min(3.5, 18.0 / n_words)
    safe_sc = TEXT_SAFE_W / (AVG_CHAR_W * n_chars)
    text_sc = round(max(1.0, min(pref_sc, safe_sc)), 3)

    # Wrap text to fit within TEXT_SAFE_W at the chosen scale
    max_chars_line = max(8, int(TEXT_SAFE_W / (AVG_CHAR_W * max(1.0, text_sc))))
    wrapped_lines = wrap_text(anchor_phrase, mx=max_chars_line)
    wrapped_text = '\n'.join(wrapped_lines)
    n_lines = len(wrapped_lines)

    # Estimate block bounding box for collision check
    MAX_CHARS_LINE = max_chars_line
    est_lines = n_lines
    t_hw = TEXT_SAFE_W / 2
    t_hh = (max(1, est_lines) * TEXT_H) / 2

    # Pick a corner for text (prefer diagonal from host)
    text_corner_options = opposite_corners(host_corner)
    weights = [60, 20, 20]
    text_corner_preferred = random.choices(text_corner_options, weights=weights, k=1)[0]
    # Try preferred corner first, then fall back to other corners
    all_text_corners = [text_corner_preferred] + [c for c in text_corner_options if c != text_corner_preferred]

    t_hw_orig, t_hh_orig = t_hw, t_hh
    text_corner = text_corner_preferred
    tx = ty = None
    found_clear = False
    for try_corner in all_text_corners:
        for attempt_sc in [text_sc, max(1.0, text_sc * 0.8), 1.0]:
            scale_ratio = attempt_sc / text_sc
            tw_try = t_hw_orig * scale_ratio
            th_try = t_hh_orig * scale_ratio
            tx_try, ty_try = corner_pos(try_corner, tw_try, th_try, jitter=60)
            if not box_hit(tx_try, ty_try, tw_try, th_try, hx, hy, h_hw, h_hh, GAP_FIX):
                text_corner, text_sc = try_corner, attempt_sc
                t_hw, t_hh = tw_try, th_try
                tx, ty = tx_try, ty_try
                found_clear = True
                break
        if found_clear:
            break

    if not found_clear:
        # Last resort: use preferred corner at original scale, accept minor overlap
        tx, ty = corner_pos(text_corner_preferred, t_hw_orig, t_hh_orig, jitter=0)
        t_hw, t_hh = t_hw_orig, t_hh_orig

    if text_phrase_v:
        placed.append(Box(tx, ty, t_hw, t_hh, fixed=True))
        script["elements"].append({
            "element_id": "main_title_text_0", "type": anchor_type,
            "phrase": text_phrase_v, "text_content": wrapped_text.upper(),
            "x": int(tx), "y": int(ty), "scale": text_sc,
            "angle": 0,
            "animation": "pop", "property": "", "reason": "Main Anchor P2",
            "typing_speed": 0.5, "filename": "", "description": "",
        })
        print(f"   Text: {text_corner} ({int(tx)},{int(ty)}) scale={text_sc} phrase='{text_phrase_v[:40]}'")
    else:
        print("   Text: skipped (no phrase remaining)")

    # ═══ 3. FLOATING IMAGES — active images only (P3..Pn) ════════════════════
    if not active_images:
        _save(script, placed, opath); return

    groups: Dict[str, list] = {}
    for img, phrase in zip(active_images, active_phrases):
        groups.setdefault(img.get("group_id", "group_1"), []).append((img, phrase))

    total = len(active_images)
    host_area = (h_hw * 2 + 2 * GAP_FIX) * (h_hh * 2 + 2 * GAP_FIX)
    text_area  = (t_hw * 2 + 2 * GAP_FIX) * (t_hh * 2 + 2 * GAP_FIX) if text_phrase_v else 0
    free_area  = UW * UH - host_area - text_area * 0.7
    free_area  = max(free_area, UW * UH * 0.3)
    gscales = compute_group_scales(groups, total, free_area)

    sorted_g = sorted(groups.items(), key=lambda kv: len(kv[1]))

    print(f"   Groups: {len(groups)}  Active images: {total}")
    for gid, items in sorted_g:
        print(f"     {gid}: {len(items)} imgs @ scale {gscales[gid]:.3f} "
              f"({int(RENDER * gscales[gid] / 2)}px canvas)")

    idx = 0
    for gid, gitems in sorted_g:
        scale = gscales[gid]
        hw = RENDER * scale / 2

        # Place first image of group (anchor)
        pos, actual_s = find_spot_shrinking(hw, placed, scale)
        if pos is None:
            for es in [0.13, 0.12, 0.10, 0.08]:
                ehw = RENDER * es / 2
                ep = find_spot_scan(ehw, ehw, placed, step=15)
                if ep:
                    pos, actual_s = ep, es
                    break
        if pos is None:
            pos = (random.uniform(UL + 50, UR - 50),
                   random.uniform(UT + 50, UB - 50))
            actual_s = MIN_SC
            print(f"   ⚠ FORCED anchor for {gid}")

        scale = actual_s
        hw = RENDER * scale / 2
        placed.append(Box(pos[0], pos[1], hw, hw))
        img0, phrase0 = gitems[0]
        script["elements"].append(_mk(img0, phrase0, gid, idx, pos[0], pos[1], scale))
        anchor_x, anchor_y = pos
        idx += 1

        # Place remaining group images near anchor
        for img, phrase in gitems[1:]:
            s = scale
            ihw = RENDER * s / 2

            p = find_spot_near(ihw, ihw, placed, anchor_x, anchor_y,
                               radius=RENDER * scale + GAP_IMG + 80, tries=2500)
            if p is None:
                p, s = find_spot_shrinking(ihw, placed, s)
                ihw = RENDER * s / 2

            if p is None:
                for es in [0.13, 0.12, 0.10, 0.08]:
                    ehw = RENDER * es / 2
                    ep = find_spot_scan(ehw, ehw, placed, step=15)
                    if ep:
                        p, s = ep, es
                        ihw = ehw
                        break
            if p is None:
                p = (random.uniform(UL + ihw, UR - ihw),
                     random.uniform(UT + ihw, UB - ihw))
                s = MIN_SC
                ihw = RENDER * s / 2
                print(f"   ⚠ FORCED {img.get('element_id', '?')}")

            placed.append(Box(p[0], p[1], ihw, ihw))
            script["elements"].append(_mk(img, phrase, gid, idx, p[0], p[1], s))
            idx += 1

    # ═══ 4. VERIFY & SAVE ════════════════════════════════════════════════════
    _save(script, placed, opath)


def _mk(img, phrase, gid, idx, x, y, scale):
    eid = img.get("element_id", "")
    if not eid:
        pid = img.get("phrase_id", f"phrase_{idx}")
        eid = f"image_{gid}_{pid}"

    return {
        "element_id": eid,
        "type": "image",
        "phrase": phrase,   # verbatim from scene text (priority-assigned)
        "filename": f"{gid}_image_{idx}.jpg",
        "description": img.get("visual_description", ""),
        "x": x, "y": y, "scale": scale,
        "angle": random.randint(-14, 14),
        "animation": "pop", "property": "shadow",
        "reason": img.get("reason", ""), "text_content": "",
    }


def _save(script, placed, path):
    floats = [p for p in placed if not p.fixed]
    fixeds = [p for p in placed if p.fixed]
    bad_ii, bad_if = 0, 0
    for i in range(len(floats)):
        for j in range(i + 1, len(floats)):
            a, b = floats[i], floats[j]
            if box_hit(a.x, a.y, a.hw, a.hh, b.x, b.y, b.hw, b.hh, 0):
                bad_ii += 1
        for f in fixeds:
            a = floats[i]
            if box_hit(a.x, a.y, a.hw, a.hh, f.x, f.y, f.hw, f.hh, 0):
                bad_if += 1

    print(f"   Overlaps: {bad_ii} img-img, {bad_if} img-fixed")

    for el in script["elements"]:
        el["x"] = int(round(el["x"]))
        el["y"] = int(round(el["y"]))
        el["scale"] = round(el["scale"], 3)
    with open(path, "w") as f:
        json.dump(script, f, indent=2)

    fl = [e for e in script["elements"]
          if e.get("type") == "image" and e.get("element_id") != "host_character"]
    if fl:
        sc = sorted(set(e["scale"] for e in fl), reverse=True)
        cpx = [round(RENDER * e["scale"] / 2) for e in fl]
        print(f"\nSaved: {path}")
        print(f"   {len(fl)} images | scales: {', '.join(f'{s:.2f}' for s in sc)}")
        print(f"   Canvas range: {min(cpx)}px – {max(cpx)}px")
    else:
        print(f"\nSaved (no images): {path}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)