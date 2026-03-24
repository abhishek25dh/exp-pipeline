"""
Layout 21 Generator — Text + Arrow + Image
===========================================
Canvas: 1920 × 1080

Structure (text-only):
    [      main_text (top center, y≈310)      ]

Structure (full):
    [      main_text (top center, y≈310)      ]
                              \
                           [arrow]   (off-center, angled toward image)
                           [image]   (center-ish, y≈713)

Arrow orientation alternates left/right per scene (seeded random) for
visual variety while remaining reproducible.

Text Type Dynamism: seeded random choice of text_highlighted / text_red / text_black.
"""

import json
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas constants
# ---------------------------------------------------------------------------
W, H         = 1920, 1080
TEXT_X       = 960
TEXT_Y       = 310
ARROW_SCALE  = 0.2
IMG_SCALE    = 0.53
TEXT_TYPES   = ["text_highlighted", "text_red", "text_black"]

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

AVG_CHAR_W_SCENE = 30
TEXT_SAFE_W      = 1800

# Two arrow/image placement variants (mirrored left/right)
# Variant A — arrow from right, pointing down-left  (matches scene_2 reference)
# Variant B — arrow from left,  pointing down-right (mirrored)
VARIANTS = {
    "A": {
        "arrow_x": 1274, "arrow_y": 497, "arrow_angle": 142,
        "img_x":    914, "img_y":   713,
    },
    "B": {
        "arrow_x":  646, "arrow_y": 497, "arrow_angle":  38,
        "img_x":   1006, "img_y":   713,
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def allot_phrases(tokens, n_slots):
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


def pick_variant(scene_num: str) -> dict:
    """Seeded-random variant — reproducible per scene."""
    rng = random.Random(int(scene_num) * 3571 if scene_num.isdigit() else hash(scene_num))
    return VARIANTS[rng.choice(["A", "B"])]


def pick_text_type(scene_num: str) -> str:
    """Seeded-random text type — reproducible per scene."""
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    return rng.choice(TEXT_TYPES)


def compute_text_scale(phrase: str) -> float:
    """
    Compute heading scale using both aesthetic preference and canvas overflow safety.
    - Preferred: larger for short text (word-count based).
    - Safety cap: ensures text never exceeds safe canvas width (char-count based).
    """
    n_chars   = max(1, len(phrase))
    n_words   = max(1, len(phrase.split()))
    preferred = min(3.5, 18.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W_SCENE * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_21_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data        = json.loads(step2_path.read_text(encoding="utf-8"))
    has_group   = data.get("has_group", False)
    main_phrase = data.get("main_text_phrase", "")
    group       = data.get("group")

    if not main_phrase:
        print("Error: no main_text_phrase in Step 2 output.")
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
    # P1=text_main, P2=arrow(opt), P3=img(opt)
    _total_slots = 1 + (2 if has_group and group else 0)
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    # Pad to full slot count so index arithmetic below stays unchanged
    _phrases = _all_phrases + [None] * (_total_slots - n_active)
    _main_phrase = _phrases[0] or main_phrase
    _arrow_phrase = _phrases[1] if _total_slots >= 2 else None
    _img_phrase   = _phrases[2] if _total_slots >= 3 else None

    text_type  = pick_text_type(scene_num)
    text_scale = compute_text_scale(main_phrase)
    variant    = pick_variant(scene_num)
    elements   = []

    # ── Main text ──────────────────────────────────────────────────────────
    if _main_phrase is not None:
        elements.append({
            "element_id":   "text_main",
            "type":         text_type,
            "phrase":       _main_phrase,
            "text_content": main_phrase.upper(),
            "x":            TEXT_X,
            "y":            TEXT_Y,
            "scale":        text_scale,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     "",
            "description":  "",
            "reason":       "Main heading text for layout 21",
        })

    print(f"  text_main : type={text_type} scale={text_scale} phrase='{main_phrase}'")

    if not has_group or not group:
        print("  (text-only — no arrow/image group)")
    else:
        img_desc = group.get("img_description", "")

        # ── Arrow + Image atomic group (arrow must not exist without its image) ──
        if _img_phrase is not None:
            if _arrow_phrase is not None:
                elements.append({
                    "element_id":   "arrow_1",
                    "type":         "arrow",
                    "phrase":       _arrow_phrase,
                    "text_content": "",
                    "x":            variant["arrow_x"],
                    "y":            variant["arrow_y"],
                    "scale":        ARROW_SCALE,
                    "angle":        variant["arrow_angle"],
                    "animation":    "pop",
                    "property":     "",
                    "filename":     "arrow.png",
                    "description":  "",
                    "reason":       "Arrow pointing to image",
                })

        # ── Image (fires after arrow) ─────────────────────────────────────
        if _img_phrase is not None:
            elements.append({
                "element_id":   "img_1",
                "type":         "image",
                "phrase":       _img_phrase,
                "text_content": "",
                "x":            variant["img_x"],
                "y":            variant["img_y"],
                "scale":        IMG_SCALE,
                "angle":        0,
                "animation":    "pop",
                "property":     "shadow",
                "filename":     f"img_1_{scene_id}.jpg",
                "description":  img_desc,
                "reason":       "Main image for layout 21",
            })

        print(f"  arrow_1   : phrase='{_arrow_phrase}' angle={variant['arrow_angle']}")
        print(f"  img_1     : phrase='{_img_phrase}'")
        print(f"  img_desc  : {img_desc[:90]}...")

    # ── Write director JSON ────────────────────────────────────────────────
    out_dir  = Path("assets/directorscript")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_director.json"

    out_path.write_text(
        json.dumps({"scene_id": scene_id, "elements": elements}, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved: {out_path}  ({len(elements)} elements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
