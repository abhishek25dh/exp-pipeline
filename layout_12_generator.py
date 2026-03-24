"""
Layout 12 Generator — 3-Image Focal Layout
===========================================
Director space: 1920x1080

Layout (from definition layout_12_definition.json):
  img_2  center  x=780  y=520  scale=0.411  (P1 — fires first)
  img_1  left    x=260  y=540  scale=0.239  (P2 — fires second)
  img_3  right   x=1500 y=500  scale=0.683  (P3 — fires third/largest)

Phrase order follows priority: img_2 first, img_1 second, img_3 third.
If script is too short, lower-priority images are dropped (atomic: no).
"""

import json, os, sys

# Fixed geometry from layout_12_definition.json (scene 1920×1080 coords)
IMAGES = [
    {"image_id": "img_2", "priority": 1, "x": 780,  "y": 520, "scale": 0.411, "animation": "pop"},
    {"image_id": "img_1", "priority": 2, "x": 260,  "y": 540, "scale": 0.239, "animation": "pop"},
    {"image_id": "img_3", "priority": 3, "x": 1500, "y": 500, "scale": 0.683, "animation": "pop"},
]


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_el(eid, etype, phrase, x, y, scale, animation="pop", prop="", filename="", description=""):
    return {
        "element_id":   eid,
        "type":         etype,
        "phrase":       phrase,
        "text_content": "",
        "filename":     filename,
        "description":  description,
        "x":            int(x),
        "y":            int(y),
        "scale":        round(scale, 3),
        "angle":        0,
        "animation":    animation,
        "property":     prop,
        "reason":       "",
    }


def fallback_description(phrase):
    return f"A clean illustration representing '{phrase}', on a pure white background."


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid       = f"scene_{scene_num}"

    s1 = load_json(f"assets/tmp/{sid}_layout_12_step_1_tmp.json")
    s2 = load_json(f"assets/tmp/{sid}_layout_12_step_2_tmp.json")

    if s1 is None:
        print(f"Error: step 1 tmp not found for {sid}. Run step 1 first.")
        return 1

    # Build phrase + description maps from step outputs
    phrase_map = {}
    for img in s1.get("images", []):
        phrase_map[img["image_id"]] = img.get("phrase", "")

    desc_map = {}
    if isinstance(s2, dict):
        for img in s2.get("images", []):
            desc_map[img["image_id"]] = img.get("image", {})

    script = {"scene_id": sid, "elements": []}
    els    = script["elements"]

    for img_def in IMAGES:
        iid   = img_def["image_id"]
        phrase = phrase_map.get(iid)

        # Skip if this image was not activated (no phrase = token budget exhausted)
        if not phrase:
            continue

        img_meta = desc_map.get(iid, {})
        desc     = img_meta.get("visual_description") or fallback_description(phrase)
        is_real  = bool(img_meta.get("is_realistic", False))

        els.append(make_el(
            eid=iid,
            etype="image",
            phrase=phrase,
            x=img_def["x"],
            y=img_def["y"],
            scale=img_def["scale"],
            animation=img_def["animation"],
            prop="shadow" if is_real else "",
            filename=f"{iid}.jpg",
            description=desc,
        ))

    os.makedirs("assets/directorscript", exist_ok=True)
    out_path = f"assets/directorscript/{sid}_director.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)

    print(f"\nSaved: {out_path}")
    print(f"   {len(els)} image(s) emitted")
    for el in els:
        print(f"   {el['element_id']:10} phrase={repr(el['phrase'])} x={el['x']} y={el['y']} scale={el['scale']}")


if __name__ == "__main__":
    sys.exit(main() or 0)
