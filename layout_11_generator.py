"""
Layout 11 Generator — Core Mind-Map (Orbit)
==============================================
Director space: 1920×1080

Layout features:
1. A single massive text word/phrase dead in the center of the screen representing the core concept.
2. 4 or 5 image nodes plotted in a perfect circle orbit around the center text.
3. Node positions calculated via trigonometry (sin/cos).
"""

import json, os, sys, math, random, re

# ── Constants ─────────────────────────────────────────────────────────────────
W, H = 1920, 1080
CENTER_X = 960
CENTER_Y = 540

# Radii for the invisible elliptical orbit
# (Allows wide text in the center without clipping top/bottom screen edges)
RADIUS_X = 640
RADIUS_Y = 320

IMG_SCALE = 0.22

CHAR_PX = 30    # Comic Sans MS scene px per char at scale=1.0
MARGIN  = 60    # min px from canvas edge to text center

# Center safe width: available between orbit images (roughly 2*(RADIUS_X-IMG_half)-gap)
_IMG_HALF = int(1024 * IMG_SCALE / 2)  # 112 px
CENTER_SAFE_W = max(50, (min(RADIUS_X, RADIUS_Y) - _IMG_HALF) * 2 - 40)


def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def allot_verbatim_phrases(tokens, n_nodes):
    """Priority-based verbatim phrase allocation for Layout 11 (Mind-Map Orbit).

    Priority order:
      P1 : core concept   ← always highest; gets phrase first
      P2 : node group A   ← randomly assigned at generation time
      P3 : node group B
      P4 : node group C
      P5 : node group D
      Within each group: image > text label

    The group-to-priority mapping is determined by the caller shuffling
    node indices before passing them; this function just works top-down.

    Algorithm:
    - Build a flat slot list: [core, g_P2_img, g_P2_txt, g_P3_img, …]
    - Walk slots top-down; give each slot 1 token (core gets 2 if spare).
    - The last filled slot absorbs any leftover tokens.
    - Slots beyond available tokens → None (element is dropped).

    Returns:
      core_phrase  : str  (verbatim first phrase)
      node_phrases : list[(img_phrase|None, txt_phrase|None)] indexed by
                     the ORDER nodes were passed in (after caller shuffle).
    """
    n_tokens = len(tokens)

    # Priority-based node count: core needs 2 tokens minimum, each node needs 3
    # (budget for 1 img + 1 txt + 1 spare so phrases aren't single stop-words).
    # Drop lower-priority nodes when token budget is too tight.
    n_active = min(n_nodes, max(0, (n_tokens - 2) // 3))

    n_slots = 1 + 2 * n_active         # core + img/txt per active node

    slot_results = [None] * n_slots
    t = 0
    for i in range(n_slots):
        if t >= n_tokens:
            break
        left = n_tokens - t
        remaining_slots = n_slots - i
        give = 2 if (i == 0 and left > remaining_slots) else 1
        give = min(give, left)
        slot_results[i] = " ".join(tokens[t: t + give])
        t += give

    # Append leftover tokens to the last filled slot
    if t < n_tokens:
        for i in range(n_slots - 1, -1, -1):
            if slot_results[i] is not None:
                slot_results[i] += " " + " ".join(tokens[t:])
                break

    core_phrase = slot_results[0]
    # Pad to n_nodes so caller always gets a list of length n_nodes
    node_phrases = []
    for i in range(n_nodes):
        if i < n_active:
            node_phrases.append((slot_results[1 + 2 * i], slot_results[1 + 2 * i + 1]))
        else:
            node_phrases.append((None, None))   # dropped — token budget exhausted
    return core_phrase, node_phrases


def safe_scale(text, center_x, preferred_cap=2.5):
    """Formula-based scale: larger for short text, capped by available width."""
    chars   = max(1, len(text))
    n_words = max(1, len(text.split()))
    avail_half = min(center_x - MARGIN, W - center_x - MARGIN)
    avail_half = max(10, avail_half)
    canvas_safe = (2 * avail_half) / (chars * CHAR_PX)
    preferred   = min(preferred_cap, 14.0 / n_words)
    return round(max(1.0, min(preferred, canvas_safe)), 3)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"

    s1_path = f"assets/tmp/{sid}_layout_11_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_11_step_2_tmp.json"
    prompt_path = f"assets/scene_prompts/{sid}_prompt.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s1_path) as f:
            step1 = json.load(f)
        with open(s2_path) as f:
            step2 = json.load(f)
    except FileNotFoundError:
        print(f"Error: Step 1 or 2 tmp JSON not found for {sid}. Run them first.")
        return 1

    # Load scene text for verbatim phrase allocation
    try:
        with open(prompt_path) as f:
            prompt_data = json.load(f)
        scene_text = strip_scene_prefix(prompt_data.get("prompt", ""))
    except FileNotFoundError:
        scene_text = ""
    tokens = scene_text.split()

    core = step1.get("core_concept", {})
    images = step2.get("orbiting_images", [])
    
    num_nodes = len(images)
    if num_nodes < 1:
        print("Error: No orbiting images found for Layout 11.")
        return 1

    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    script = {"scene_id": sid, "elements": []}

    print(f"   Generating Mind-Map Orbit Layout...")

    active_images = images[:5]

    # ── Priority-based phrase allocation ──────────────────────────────────────
    # 1. Randomly assign priorities P2..P(n+1) to the node groups.
    #    The shuffled list is the ORDER in which groups receive phrases.
    priority_order = list(range(len(active_images)))  # [0,1,2,...,n-1]
    random.shuffle(priority_order)   # e.g. [2,0,3,1] → group 2 = P2, group 0 = P3 …

    # 2. Reorder active_images so allot_verbatim_phrases processes them P2→P5.
    ordered_images = [active_images[i] for i in priority_order]

    core_title = core.get("title", "")

    # Try to find core_title verbatim in the script so core fires when those words are spoken.
    def _find_in_tokens(tkns, phrase):
        words = phrase.lower().split()
        for i in range(len(tkns) - len(words) + 1):
            window = [t.lower().strip(".,!?'\"") for t in tkns[i:i + len(words)]]
            if window == [w.strip(".,!?'\"") for w in words]:
                return i, i + len(words)   # start, end indices
        return None, None

    _core_match_start, _core_match_end = _find_in_tokens(tokens, core_title)

    if _core_match_start is not None:
        # Conceptual match found — reserve those tokens for core, allot the
        # remaining tokens to nodes so there are no timing collisions.
        core_phrase = " ".join(tokens[_core_match_start:_core_match_end])
        _node_tokens = tokens[:_core_match_start] + tokens[_core_match_end:]
        print(f"  Core phrase matched in script: '{core_phrase}'")
    else:
        # No match — use first two tokens for core, rest for nodes.
        core_phrase_allot, _ = allot_verbatim_phrases(tokens, 0)  # just get core
        core_phrase = " ".join(tokens[:2]) if len(tokens) >= 2 else (tokens[0] if tokens else "")
        _node_tokens = tokens[2:]
        print(f"  Core title not found verbatim — firing on first tokens: '{core_phrase}'")

    # 3. Allot node phrases from the remaining (non-core) token pool.
    def _allot_nodes(tkns, n_nodes):
        """Allot img+txt phrase pairs to n_nodes, priority-ordered."""
        n = len(tkns)
        n_active = min(n_nodes, max(0, n // 2))
        n_slots = 2 * n_active
        results = [None] * n_slots
        t = 0
        for i in range(n_slots):
            if t >= n:
                break
            give = max(1, (n - t) // (n_slots - i))
            if i == n_slots - 1:
                give = n - t
            results[i] = " ".join(tkns[t:t + give])
            t += give
        pairs = []
        for i in range(n_nodes):
            if i < n_active:
                pairs.append((results[2 * i], results[2 * i + 1]))
            else:
                pairs.append((None, None))
        return pairs

    node_phrases_ordered = _allot_nodes(_node_tokens, len(ordered_images))
    # node_phrases_ordered[k] = (img_phrase, txt_phrase) for priority_order[k]

    # 4. Map back to original node index so geographic placement stays consistent.
    node_phrases = [None] * len(active_images)
    for k, orig_idx in enumerate(priority_order):
        node_phrases[orig_idx] = node_phrases_ordered[k]

    # 1. Place Core Concept Text (P1 — always first)
    if not core_phrase:
        print(f"  Warning: no tokens for core concept — skipping layout 11.")
        return 1

    _core_upper = core_title.upper()
    _core_chars = max(1, len(_core_upper))
    _core_width_cap = CENTER_SAFE_W / (_core_chars * CHAR_PX)
    core_scale = round(max(1.0, min(safe_scale(_core_upper, CENTER_X, preferred_cap=3.0), _core_width_cap)), 3)
    script["elements"].append({
        "element_id": "txt_core",
        "type": "text_red",
        "phrase": core_phrase,          # verbatim from script — fires when core words spoken
        "text_content": _core_upper,    # AI label shown visually
        "x": CENTER_X,
        "y": CENTER_Y,
        "scale": core_scale,
        "angle": 0,
        "animation": "pop",
        "property": "",
        "reason": "Central Mind Map Root",
        "filename": "",
        "description": ""
    })

    # To avoid clipping giant rectangular central text, we use fixed "safe" slots
    # instead of a continuous mathematical ellipse which dips into the focal corners.
    SAFE_SLOTS = [
        {"x": 400,  "y": 250}, # Top Left
        {"x": 1520, "y": 250}, # Top Right
        {"x": 400,  "y": 800}, # Bottom Left
        {"x": 1520, "y": 800}, # Bottom Right
        {"x": 960,  "y": 200}, # Top Center
    ]

    # Shuffle them so it's not always in the exact same index order
    random.shuffle(SAFE_SLOTS)

    TEXT_TYPES = ["text_highlighted", "text_red", "text_black"]

    for i, img in enumerate(active_images):
        img_phrase, txt_phrase = node_phrases[i] if node_phrases[i] is not None else (None, None)

        # Skip this node if priority allocation ran out of tokens for it
        if img_phrase is None and txt_phrase is None:
            print(f"  Skipping node {i+1}: no tokens (lower priority).")
            continue

        slot = SAFE_SLOTS[i]
        x = slot["x"]
        y = slot["y"]

        node_id = img.get("node_id", f"node_{i+1}")
        is_real = img.get("is_realistic", False)

        # text_content = first word of the allot-derived txt_phrase (timing trigger).
        # Must be the word actually spoken at the moment this element appears —
        # never a word from a different position in the script (which would show
        # on screen before the speaker says it).
        # Skip if it duplicates a word already in the core concept.
        lbl_label = txt_phrase.split()[0].strip(".,!?") if txt_phrase else ""
        _core_words = set(core_title.lower().replace(".", "").replace(",", "").split())
        if lbl_label.lower() in _core_words:
            lbl_label = ""   # don't show a label that repeats the core text

        # Seeded text type dynamism per node
        random.seed(int(scene_num) * 7919 + i if str(scene_num).isdigit() else hash(scene_num) + i)
        txt_type = random.choice(TEXT_TYPES)

        if img_phrase is not None:
            # Node Image — fires on verbatim token span from allot_verbatim_phrases
            script["elements"].append({
                "element_id": f"img_{node_id}",
                "type": "image",
                "phrase": img_phrase,           # verbatim timing trigger (span-derived)
                "filename": f"orb_{i}_img.jpg",
                "description": img.get("visual_description", ""),
                "x": int(x),
                "y": int(y),
                "scale": IMG_SCALE,
                "angle": random.randint(-4, 4),
                "animation": "pop",
                "property": "shadow" if is_real else "",
                "reason": f"Orbit node {i+1}",
                "text_content": ""
            })

        if txt_phrase is not None and lbl_label:
            # Node Label — fires on verbatim token span; shows narrative label visually
            # Skip if lbl_label is empty (word filtered as repeating core concept) —
            # otherwise renderer falls back to showing the full phrase as visible text.
            txt_y = y + _IMG_HALF + 50
            lbl_scale = safe_scale(lbl_label, x, preferred_cap=2.0)
            script["elements"].append({
                "element_id": f"txt_{node_id}",
                "type": txt_type,
                "phrase": txt_phrase,           # verbatim timing trigger (span-derived)
                "text_content": lbl_label,      # step_1 AI label shown visually
                "x": int(x),
                "y": int(txt_y),
                "scale": lbl_scale,
                "angle": 0,
                "animation": "pop",
                "property": "",
                "reason": "Node label",
                "filename": "",
                "description": ""
            })

    # ═══ Final save ═══════════════════════════════════════════════════════════
    with open(opath, "w") as f:
        json.dump(script, f, indent=2)

    total_el = len(script["elements"])
    
    print(f"\nSaved: {opath}")
    print(f"   1 Core Label | {num_nodes} Orbiting Nodes | {total_el} total elements")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
