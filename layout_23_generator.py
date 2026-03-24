"""
Layout 23 Generator - Hero + Supporting Images
===============================================
Canvas: 1920 x 1080

Full layout (4 images):
                  [ P3 top-mid ] [ P4 top-right ]   y~350
  [ P1 hero                   ]                     y~558
  [ (large, left)             ] [ P2 bottom-right ] y~761

Fewer active images shift to balanced positions:
  1 image: hero centered
  2 images: hero left + P2 bottom-right (reference positions)
  3 images: hero + P2 + P3 repositioned above P2
  4 images: full reference layout
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Geometry per active image count
# Key: n_images -> list of (x, y, scale) in priority order
#      [hero, bottom_right, top_mid, top_right]
# ---------------------------------------------------------------------------
GEOMETRY = {
    1: [
        (960,  540,  0.728),   # hero centered
    ],
    2: [
        (466,  558,  0.728),   # hero left
        (1336, 761,  0.465),   # bottom-right
    ],
    3: [
        (466,  558,  0.728),   # hero left
        (1336, 761,  0.465),   # bottom-right
        (1300, 320,  0.320),   # top (above P2, centered right-side)
    ],
    4: [
        (466,  558,  0.728),   # hero left      (from reference)
        (1336, 761,  0.465),   # bottom-right   (from reference)
        (1041, 351,  0.285),   # top-mid        (from reference)
        (1592, 350,  0.301),   # top-right      (from reference)
    ],
}

# Filenames for each position slot
FILENAMES = ["img_hero", "img_bottom_right", "img_top_mid", "img_top_right"]


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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_23_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data     = json.loads(step2_path.read_text(encoding="utf-8"))
    n_images = data.get("n_images", 1)
    images   = data.get("images", [])

    if not images:
        print("Error: no images in Step 2 output.")
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
    _total_slots = len(images)
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _phrases = _all_phrases + [None] * (_total_slots - n_active)

    geo      = GEOMETRY[n_images]
    elements = []

    for i, img in enumerate(images):
        _phrase = _phrases[i] if i < len(_phrases) else None  # None for inactive slots
        if _phrase is None:
            continue
        x, y, scale = geo[i]
        phrase      = img.get("phrase", "")
        img_desc    = img.get("img_description", "")
        fname       = FILENAMES[i]

        elements.append({
            "element_id":   f"{fname}_{scene_id}",
            "type":         "image",
            "phrase":       _phrase,
            "text_content": "",
            "x":            x,
            "y":            y,
            "scale":        scale,
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"{fname}_{scene_id}.jpg",
            "description":  img_desc,
            "reason":       f"{img['position']} image (priority {i + 1})",
        })

        print(f"  {img['position']:14s}: x={x} y={y} scale={scale} phrase='{phrase[:40]}...'")

    # --- Write director JSON ---
    out_dir  = Path("assets/directorscript")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_director.json"
    out_path.write_text(
        json.dumps({"scene_id": scene_id, "elements": elements}, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved: {out_path}  ({len(elements)} image(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
