"""
Layout 32 Generator - Two Images Side-by-Side (No Text)
========================================================
Canvas: 1920 x 1080

Layout (from scene_13_director.json reference):
  [ img_left (x=502, y=556, scale=0.806) ]  [ img_right (x=1391, y=559, scale=0.784) ]

Both AI-generated. Slots randomly assigned per scene (from step 1).
"""

import json
import re
import sys
from pathlib import Path

IMG_GEOMETRY = {
    "left":  {"x": 502,  "y": 556, "scale": 0.806},
    "right": {"x": 1391, "y": 559, "scale": 0.784},
}


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


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_32_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data     = json.loads(step2_path.read_text(encoding="utf-8"))
    images   = data.get("images", [])

    if not images:
        print("Error: no images in Step 2 output.")
        return 1

    # ── Resilient: drop images with unknown geometry slots ─────────────────────
    _valid_images = [img for img in images if img.get("slot") in IMG_GEOMETRY]
    if len(_valid_images) < len(images):
        print(f"   Warning: Layout 32 dropping {len(images) - len(_valid_images)} images with unknown slots.")
        images = _valid_images
    if not images:
        print("Error: no images with valid geometry slots in Step 2 output.")
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
    _sorted_images = sorted(images, key=lambda x: x["priority"])
    _total_slots = len(_sorted_images)
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)

    elements = []
    for ii, img in enumerate(_sorted_images):
        _ip = _all_phrases[ii] if ii < n_active else None
        if _ip is None:
            continue
        slot = img["slot"]
        geo  = IMG_GEOMETRY[slot]
        elements.append({
            "element_id":   f"img_{slot}_{scene_id}",
            "type":         "image",
            "phrase":       _ip,
            "text_content": "",
            "x":            geo["x"],
            "y":            geo["y"],
            "scale":        geo["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_{slot}_{scene_id}.jpg",
            "description":  img.get("img_description", ""),
            "reason":       f"Layout 32 image (slot={slot}, priority={img['priority']})",
        })
        print(f"  img_{slot}: x={geo['x']} y={geo['y']} scale={geo['scale']} phrase='{_ip[:55]}'")

    out_dir  = Path("assets/directorscript")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_director.json"
    out_path.write_text(
        json.dumps({"scene_id": scene_id, "elements": elements}, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved: {out_path}  ({len(elements)} element(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
