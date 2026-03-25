"""
Layout 37 Generator - Large Center Image + 2 Left + 3 Right (All AI)
=====================================================================
Canvas: 1920 x 1080

Layout (from scene_18_director.json reference):
  [ img_tl  (x=232,  y=376, s=0.271) ]  [ img_center (x=730, y=530, s=0.590) ]  [ img_tr1 (x=1293, y=405, s=0.303) ]  [ img_tr2 (x=1701, y=399, s=0.304) ]
  [ img_bl  (x=224,  y=702, s=0.259) ]  [                                    ]  [ img_br  (x=1469, y=777, s=0.304) ]

Priority:
  P1=img_center (fires first, largest image, main focus)
  P2=img_tl, P3=img_bl (left pair)
  P4=img_tr1, P5=img_tr2, P6=img_br (right trio)

All images are AI-generated. No text, no static assets.
"""

import json
import re
import sys
from pathlib import Path

GEOMETRY = {
    "img_center": {"x": 730,  "y": 530, "scale": 0.590},
    "img_tl":     {"x": 232,  "y": 376, "scale": 0.271},
    "img_bl":     {"x": 224,  "y": 702, "scale": 0.259},
    "img_tr1":    {"x": 1293, "y": 405, "scale": 0.303},
    "img_tr2":    {"x": 1701, "y": 399, "scale": 0.304},
    "img_br":     {"x": 1469, "y": 777, "scale": 0.304},
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

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_37_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data   = json.loads(step2_path.read_text(encoding="utf-8"))
    images = data.get("images", [])

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

    # ── Resilient image count handling ─────────────────────────────────────────
    # Drop images whose img_id has no matching GEOMETRY slot
    _valid_images = [img for img in images if img.get("img_id") in GEOMETRY]
    if len(_valid_images) < len(images):
        print(f"   Warning: Layout 37 dropping {len(images) - len(_valid_images)} images with unknown geometry slots.")
        images = _valid_images

    elements = []
    for ii, img in enumerate(images):
        _ip = _all_phrases[ii] if ii < n_active else None
        if _ip is None:
            continue
        iid    = img["img_id"]
        geo    = GEOMETRY[iid]
        elements.append({
            "element_id":   f"{iid}_{scene_id}",
            "type":         "image",
            "phrase":       _ip,
            "text_content": "",
            "x":            geo["x"],
            "y":            geo["y"],
            "scale":        geo["scale"],
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"{iid}_{scene_id}.jpg",
            "description":  data.get(f"{iid}_description", ""),
            "reason":       f"Layout 37 {iid} (P{img['priority']}, AI generated)",
        })
        print(f"  {iid:12s}: x={geo['x']:4d} y={geo['y']:4d} scale={geo['scale']:.3f}  phrase='{_ip[:55]}'")

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
