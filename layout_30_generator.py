"""
Layout 30 Generator - Host Left + 1 Image Right
================================================
Canvas: 1920 x 1080

Layout (from scene_11_director.json reference):
  [ host_looking_right (x=473,  y=577, scale=1.5) ]  [ img_right (x=1383, y=553, scale=0.5) ]

Host is a static local asset (host_looking_right.png).
Right image is AI-generated.
"""

import json
import re
import sys
from pathlib import Path

HOST_X     = 473
HOST_Y     = 577
HOST_SCALE = 1.5
HOST_FILE  = "host_looking_right.png"

IMG_X      = 1383
IMG_Y      = 553
IMG_SCALE  = 0.5


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

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_30_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data        = json.loads(step2_path.read_text(encoding="utf-8"))
    host_phrase = data.get("host_phrase", "")
    img_phrase  = data.get("img_phrase", "")
    img_desc    = data.get("img_description", "")
    img_style   = data.get("img_style", "2D colorful cartoon graphic")

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
    # P1=host, P2=img_right
    _total_slots = 2
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _all_phrases = allot_phrases(_tokens, n_active)
    _host_phrase = _all_phrases[0] if 0 < n_active else None
    _img_phrase  = _all_phrases[1] if 1 < n_active else None

    elements = []

    # P1 — host (fires first)
    if _host_phrase is not None:
        elements.append({
            "element_id":   f"host_left_{scene_id}",
            "type":         "image",
            "phrase":       _host_phrase,
            "text_content": "",
            "x":            HOST_X,
            "y":            HOST_Y,
            "scale":        HOST_SCALE,
            "angle":        0,
            "animation":    "pop",
            "property":     "",
            "filename":     HOST_FILE,
            "description":  "",
            "reason":       "Layout 30 host (P1, static local asset)",
        })
    print(f"  host_left: x={HOST_X} y={HOST_Y} scale={HOST_SCALE} phrase='{(_host_phrase or '')[:60]}'")

    # P2 — right image (fires after host)
    if _img_phrase is not None:
        elements.append({
            "element_id":   f"img_right_{scene_id}",
            "type":         "image",
            "phrase":       _img_phrase,
            "text_content": "",
            "x":            IMG_X,
            "y":            IMG_Y,
            "scale":        IMG_SCALE,
            "angle":        0,
            "animation":    "pop",
            "property":     "shadow",
            "filename":     f"img_right_{scene_id}.jpg",
            "description":  img_desc,
            "reason":       "Layout 30 right image (P2, AI-generated)",
        })
        print(f"  img_right: x={IMG_X} y={IMG_Y} scale={IMG_SCALE} phrase='{_img_phrase[:60]}'")

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
