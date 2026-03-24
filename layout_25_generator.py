"""
Layout 25 Generator - Host Right + 4 Images Left (2x2 Grid)
=============================================================
Canvas: 1920 x 1080

Layout:
  [ img_top_left  (x=308,  y=350, s=0.295) ]  [ img_top_right  (x=752, y=352, s=0.313) ]
  [ img_bot_left  (x=323,  y=763, s=0.284) ]  [ img_bot_right  (x=764, y=762, s=0.283) ]
                                       [ host_looking_left (x=1485, y=621, s=0.754) ]

Host is a static local asset (host_looking_left.png) -- P1, always present, no AI generation.
Left images are AI-generated -- P2-P5, active count depends on token count.
No text elements in this layout.
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------
HOST_X, HOST_Y, HOST_SCALE = 1485, 621, 0.754

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


SLOT_GEOMETRY = {
    "top_left":     {"x": 308,  "y": 350, "scale": 0.295},
    "top_right":    {"x": 752,  "y": 352, "scale": 0.313},
    "bottom_left":  {"x": 323,  "y": 763, "scale": 0.284},
    "bottom_right": {"x": 764,  "y": 762, "scale": 0.283},
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_25_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data       = json.loads(step2_path.read_text(encoding="utf-8"))
    host_phrase = data.get("host_phrase", "")
    images      = data.get("images", [])

    if not host_phrase:
        print("Error: no host_phrase in Step 2 output.")
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
    n_tokens = len(_tokens)
    # Priority-based image dropping: each image needs ~2 tokens to be non-trivial.
    _n_active_imgs = min(len(images), max(1, (n_tokens - 1) // 2))
    _phrases = allot_phrases(_tokens, 1 + _n_active_imgs)
    _host_phrase = _phrases[0] or host_phrase
    _img_phrases = _phrases[1:]
    print(f"   Token budget: {n_tokens} tokens -> {_n_active_imgs} active images")

    elements = []

    # --- Host image (P1, fires first) ---
    if _phrases[0] is not None:
        elements.append({
            "element_id":   f"img_host_right_{scene_id}",
            "type":         "image",
            "phrase":       _host_phrase,
            "text_content": "",
            "x":            HOST_X,
            "y":            HOST_Y,
            "scale":        HOST_SCALE,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     "host_looking_left.png",
            "description":  "",
            "reason":       "Layout 25 host image (P1, static local asset)",
        })
    print(f"  host_right: x={HOST_X} y={HOST_Y} scale={HOST_SCALE} phrase='{_host_phrase[:50]}'")

    # --- Left AI images (P2-P5, fire in priority order) ---
    for ii, img in enumerate(images[:_n_active_imgs]):
        _ip = _img_phrases[ii] if ii < len(_img_phrases) else None
        if _ip is None:
            continue
        slot = img["slot"]
        geo  = SLOT_GEOMETRY[slot]
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
            "reason":       f"Layout 25 left image (slot={slot}, priority={img['priority']})",
        })
        print(f"  img_{slot}: x={geo['x']} y={geo['y']} scale={geo['scale']} phrase='{img['phrase'][:50]}'")

    # --- Write director JSON ---
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
