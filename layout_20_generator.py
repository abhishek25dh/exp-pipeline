"""
Layout 20 Generator — Top Text + Arrows + Images
=================================================
Canvas: 1920 × 1080

Structure:
    [         main_text (top center, y≈315)         ]
         /              |               \
   [arrow_left]   [arrow_center]   [arrow_right]
   [img_left  ]   [img_center  ]   [img_right  ]
         (y≈830)

Active groups adapt to token count (Priority-Based Approach):
  1 group  → center only
  2 groups → center (left side) + left (right side), balanced
  3 groups → left / center / right, full spread

Text Type Dynamism: main_text type is seeded-random per scene.
"""

import json
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas constants
# ---------------------------------------------------------------------------
W, H       = 1920, 1080
ARROW_SCALE = 0.2
IMG_SCALE   = {1: 0.38, 2: 0.33, 3: 0.30}   # scale shrinks as groups increase

# Geometry tables keyed by n_groups.
# Each entry: list of (img_x, img_y) and (arrow_x, arrow_y, arrow_angle)
# in priority order: group_1 (center), group_2 (left), group_3 (right)
GEOMETRY = {
    1: {
        "img":   [(960, 830)],
        "arrow": [(960, 566, 90)],
    },
    2: {
        # 2 active groups displayed balanced left+right
        "img":   [(480, 830), (1440, 830)],
        "arrow": [(620, 540, 107), (1300, 540, 73)],
    },
    3: {
        # full spread: group_1=center, group_2=left, group_3=right
        # visual order left→right: group_2, group_1, group_3
        "img":   [(351, 830), (959, 830), (1584, 820)],
        "arrow": [(476, 526, 129), (952, 566, 90), (1444, 548, 57)],
    },
}

TEXT_X, TEXT_Y = 960, 315
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]

# ---------------------------------------------------------------------------
# Canvas text-fit math
# ---------------------------------------------------------------------------
# Layout tester renders at 960×540 (scene ÷2). All scene coords are 1920×1080.
# Text: fontSize=40 in canvas px → effective 80px in scene coords.
# canvas_scaleX = scene_scale / 2.
# Comic Sans uppercase at fontSize=40: avg character width ≈ 30 scene px at scale=1.
# Text width in scene px = num_chars × 30 × scene_scale.
# Safe width = 1800 scene px (1920 minus 60px margin each side).
# → max safe scale = 1800 / (30 × num_chars) = 60 / num_chars.

AVG_CHAR_W_SCENE = 30     # Comic Sans uppercase, fontSize=40, in scene px at scale=1
TEXT_SAFE_W      = 1800   # scene px


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def compute_text_scale(phrase: str) -> float:
    """
    Compute heading scale using both aesthetic preference and canvas overflow safety.
    - Preferred: larger for short text (word-count based).
    - Safety cap: ensures text never exceeds safe canvas width (char-count based).
    """
    n_chars  = max(1, len(phrase))
    n_words  = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W_SCENE * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def pick_text_type(scene_num: str) -> str:
    """Seeded-random text type — reproducible per scene, varied across scenes."""
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_20_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    step1      = json.loads(step2_path.read_text(encoding="utf-8"))
    n_groups   = step1.get("n_groups", 0)
    main_phrase = step1.get("main_text_phrase", "")
    groups     = step1.get("groups", [])
    scene_text = step1.get("scene_text", "")

    # ── Resilient group count handling ─────────────────────────────────────────
    _max_geo = max(GEOMETRY.keys())  # 3
    if len(groups) > _max_geo:
        print(f"   Warning: Layout 20 expects at most {_max_geo} groups, got {len(groups)}. Dropping extras.")
        groups = groups[:_max_geo]
    n_groups = min(n_groups, _max_geo, len(groups)) if groups else 0
    if n_groups < len(groups):
        n_groups = len(groups)

    if not main_phrase:
        print("Error: no main_text_phrase in Step 1 output.")
        return 1

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    _prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    _scene_text = ""
    if _prompt_path.exists():
        try:
            _scene_text = _strip_scene_prefix(
                json.loads(_prompt_path.read_text(encoding="utf-8")).get("prompt", "")
            )
        except Exception:
            pass
    _tokens = _scene_text.split()
    # Slots: 1 (main_text) + n_groups * 2 (arrow + img per group)
    _total_slots = 1 + n_groups * 2
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    # Pad to full slot count so index arithmetic below stays unchanged
    _slot_phrases = _all_phrases + [None] * (_total_slots - n_active)
    # slot 0 = main_text; slots 1,2 = group1 arrow,img; slots 3,4 = group2; etc.
    _main_phrase_allot  = _slot_phrases[0]
    _group_slot_phrases = _slot_phrases[1:]  # pairs [arrow, img] per group

    elements   = []
    text_type  = pick_text_type(scene_num)
    text_scale = compute_text_scale(main_phrase)

    # ── Main text ────────────────────────────────────────────────────────────
    if _main_phrase_allot is not None:
        elements.append({
            "element_id":   "text_main",
            "type":         text_type,
            "phrase":       _main_phrase_allot,
            "text_content": main_phrase.upper(),
            "x":            TEXT_X,
            "y":            TEXT_Y,
            "scale":        text_scale,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     "",
            "description":  "",
            "reason":       "Main heading text for layout 20",
        })

    print(f"  main_text: type={text_type} scale={text_scale} phrase='{main_phrase}'")

    if n_groups == 0:
        print("  No groups (token count too low) — main_text only.")
    else:
        geo      = GEOMETRY[n_groups]
        img_scale = IMG_SCALE[n_groups]

        for i, group in enumerate(groups):
            _arrow_phrase = _group_slot_phrases[i * 2] if (i * 2) < len(_group_slot_phrases) else None
            _img_phrase   = _group_slot_phrases[i * 2 + 1] if (i * 2 + 1) < len(_group_slot_phrases) else None
            if _img_phrase is None:
                continue

            pos         = group["position"]       # center / left / right
            arrow_phrase = group["arrow_phrase"]
            img_phrase   = group["img_phrase"]

            img_x,   img_y          = geo["img"][i]
            arr_x,   arr_y, arr_ang = geo["arrow"][i]

            # Arrow — fires just before the image (timing: arrow_phrase spoken first)
            if _arrow_phrase is not None:
                elements.append({
                    "element_id":   f"arrow_{i + 1}",
                    "type":         "arrow",
                    "phrase":       _arrow_phrase,
                    "text_content": "",
                    "x":            arr_x,
                    "y":            arr_y,
                    "scale":        ARROW_SCALE,
                    "angle":        arr_ang,
                    "animation":    "pop",
                    "property":     "",
                    "filename":     "arrow.png",
                    "description":  "",
                    "reason":       f"Arrow pointing to {pos} image",
                })

            # Image
            if _img_phrase is not None:
                elements.append({
                    "element_id":   f"img_{i + 1}",
                    "type":         "image",
                    "phrase":       _img_phrase,
                    "text_content": "",
                    "x":            img_x,
                    "y":            img_y,
                    "scale":        img_scale,
                    "angle":        0,
                    "animation":    "pop",
                    "property":     "shadow",
                    "filename":     f"img_{i + 1}_{scene_id}.jpg",
                    "description":  group.get("img_description", ""),
                    "reason":       f"{pos.capitalize()} image for layout 20",
                })

            print(f"  group_{i+1} ({pos:6s}): arrow='{_arrow_phrase}' img='{_img_phrase}'")

    # ── Write director JSON ──────────────────────────────────────────────────
    out_dir  = Path("assets/directorscript")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_director.json"

    director = {"scene_id": scene_id, "elements": elements}
    out_path.write_text(json.dumps(director, indent=2), encoding="utf-8")

    imgs   = sum(1 for e in elements if e["type"] == "image")
    arrows = sum(1 for e in elements if e["type"] == "arrow")
    texts  = sum(1 for e in elements if "text" in e["type"])
    print(f"\nSaved: {out_path}")
    print(f"  {texts} text | {arrows} arrows | {imgs} images | {len(elements)} total elements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
