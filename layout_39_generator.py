"""
Layout 39 Generator - 2x2 Image Grid Left + 4 Text Rows Right
==============================================================
Canvas: 1920 x 1080

Layout (from scene_20_director.json reference):
  Left 2x2 grid:                        Right 4-row text list:
  img_tl (x=274,  y=384,  s=0.392)       text_row1 (x=1426, y=329,  s=3.09)
  img_tr (x=772,  y=386,  s=0.384)       text_row2 (x=1436, y=540,  s=3.03)
  img_bl (x=270,  y=832,  s=0.384)       text_row3 (x=1443, y=750,  s=2.955)
  img_br (x=785,  y=823,  s=0.386)       text_row4 (x=1452, y=935,  s=3.015)

Priority: P1=img_tl, P2=img_tr, P3=img_bl, P4=img_br, P5=text_row1 ... P8=text_row4 (last/punchline).

Text config (right column bullets):
  TEXT_SAFE_W=600 (from 8 chars * 25 * ~3.0 scale = 600px).
  MAX_CHARS_LINE=24, rows are single-line bullet labels.
  Scale computed from phrase length (consistent across all rows for visual uniformity).
"""

import json
import random
import re
import sys
from pathlib import Path

TEXT_SAFE_W    = 600
AVG_CHAR_W     = 30
MAX_CHARS_LINE = TEXT_SAFE_W // AVG_CHAR_W  # 20
TEXT_TYPES     = ["text_highlighted", "text_red", "text_black"]

# Element geometry from director script
IMGS = {
    "img_tl": {"x": 274,  "y": 384, "scale": 0.392},
    "img_tr": {"x": 772,  "y": 386, "scale": 0.384},
    "img_bl": {"x": 270,  "y": 832, "scale": 0.384},
    "img_br": {"x": 785,  "y": 823, "scale": 0.386},
}

TEXT_ROWS = [
    {"key": "text_row1", "x": 1426, "y": 329,  "ref_scale": 3.09},
    {"key": "text_row2", "x": 1436, "y": 540,  "ref_scale": 3.03},
    {"key": "text_row3", "x": 1443, "y": 750,  "ref_scale": 2.955},
    {"key": "text_row4", "x": 1452, "y": 935,  "ref_scale": 3.015},
]

# Priority order for n_active selection
PRIORITY = ["img_tl", "img_tr", "img_bl", "img_br",
            "text_row1", "text_row2", "text_row3", "text_row4"]


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


def compute_text_scale(phrase: str) -> float:
    n = max(1, len(phrase))
    safe = TEXT_SAFE_W / (AVG_CHAR_W * n)
    # Allow scaling down as far as needed to fit; cap at 4.0 for readability
    return round(max(1.0, min(4.0, safe)), 3)


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_39_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: {step2_path} not found. Run Step 2 first.")
        return 1

    data      = json.loads(step2_path.read_text(encoding="utf-8"))
    rng = random.Random(int(scene_num) * 7919 if scene_num.isdigit() else hash(scene_num))
    text_type = rng.choice(TEXT_TYPES)

    # ── Load scene text for token-budget priority dropping ────────────────────
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

    # Priority-based dropping: 2 tokens minimum per slot
    n_active    = min(len(PRIORITY), max(1, n_tokens // 2))
    active_keys = PRIORITY[:n_active]
    print(f"   Token budget: {n_tokens} tokens -> {n_active} active elements")

    _phrases = allot_phrases(_tokens, len(active_keys))

    elements = []

    # --- P1-P4: Images ---
    for p_idx, key in enumerate(active_keys):
        if not key.startswith("img_"):
            break
        _ip = _phrases[p_idx] if p_idx < len(_phrases) else None
        if _ip is None:
            continue
        geo = IMGS[key]
        elements.append({
            "element_id":  f"{key}_{scene_id}",
            "type":        "image",
            "phrase":      _ip,
            "text_content": "",
            "x":           geo["x"],
            "y":           geo["y"],
            "scale":       geo["scale"],
            "angle":       0,
            "animation":   "pop",
            "property":    "shadow",
            "filename":    f"{key}_{scene_id}.jpg",
            "description": data.get(f"{key}_description", ""),
            "reason":      f"Layout 39 image grid {key} (P{p_idx+1})",
        })
        print(f"  {key:8s}: x={geo['x']} y={geo['y']} phrase='{_ip[:55]}'")

    # --- P5-P8: Text rows ---
    # Each row scales independently: short phrases stay large, long ones shrink to fit.
    for row in TEXT_ROWS:
        key = row["key"]
        if key not in active_keys:
            continue
        p_idx = active_keys.index(key)
        _tp = _phrases[p_idx] if p_idx < len(_phrases) else None
        if _tp is None:
            continue
        scale = compute_text_scale(_tp)
        _tc = _tp.strip(".,!?").upper()
        elements.append({
            "element_id":  f"{key}_{scene_id}",
            "type":        text_type,
            "phrase":      _tp,
            "text_content": _tc,
            "x":           row["x"],
            "y":           row["y"],
            "scale":       scale,
            "angle":       0,
            "animation":   "pop",
            "property":    "",
            "filename":    "",
            "description": "",
            "reason":      f"Layout 39 text {key} (P{p_idx+1}{'  punchline' if key == 'text_row4' else ''})",
        })
        print(f"  {key:10s}: x={row['x']} y={row['y']} scale={scale} phrase='{_tp[:55]}'")

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
