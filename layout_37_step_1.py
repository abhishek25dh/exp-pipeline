"""
Layout 37 Step 1 - Large Center Image + 2 Left + 3 Right (All AI, No Text)
===========================================================================
Visual structure:
  [ img_tl (P2) ]  [ img_center (P1, large) ]  [ img_tr1 (P4) ]  [ img_tr2 (P5) ]
  [ img_bl (P3) ]  [                        ]  [ img_br  (P6)                    ]

Priority / firing order (creation timestamp in director JSON):
  P1: img_center  (x=730,  y=530,  s=0.590) -- fires FIRST (large, main focal image)
  P2: img_tl      (x=232,  y=376,  s=0.271) -- top-left
  P3: img_bl      (x=224,  y=702,  s=0.259) -- bottom-left
  P4: img_tr1     (x=1293, y=405,  s=0.303) -- top-right #1
  P5: img_tr2     (x=1701, y=399,  s=0.304) -- top-right #2 (far right)
  P6: img_br      (x=1469, y=777,  s=0.304) -- bottom-right

All six are AI-generated images. No text, no host -- no Rule 6 constraints.

Token thresholds:
  N < 2  -> n_active=1 (center only)
  N < 4  -> n_active=3 (center + left pair P2+P3; left pair comes as a visual unit)
  N < 5  -> n_active=4 (add P4)
  N < 6  -> n_active=5 (add P5)
  N >= 6 -> n_active=6 (all six)

Phrase allocation: split_evenly across all active elements.
"""

import json
import re
import sys
from pathlib import Path

ELEMENT_NAMES = ["img_center", "img_tl", "img_bl", "img_tr1", "img_tr2", "img_br"]


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def split_evenly(tokens: list, n: int) -> list:
    """Split tokens into n roughly equal parts, snapping to sentence boundaries."""
    total = len(tokens)
    if n == 1:
        return [" ".join(tokens)]
    raw_targets = [round(total * i / n) for i in range(1, n)]
    split_pts, prev = [], 0
    for i, t in enumerate(raw_targets):
        best = t
        for delta in range(0, 4):
            for idx in [t + delta, t - delta]:
                if 1 <= idx < total and ends_sentence(tokens[idx - 1]):
                    best = idx
                    break
            else:
                continue
            break
        best = max(prev + 1, min(best, total - (n - 1 - i)))
        split_pts.append(best)
        prev = best
    bounds = [0] + split_pts + [total]
    return [" ".join(tokens[bounds[i]:bounds[i + 1]]) for i in range(n)]


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text  = strip_scene_prefix(prompt_data.get("prompt", ""))
    tokens      = scene_text.split()

    if not tokens:
        print("Error: empty scene text.")
        return 1

    n = len(tokens)
    if n < 2:
        n_active = 1
    elif n < 4:
        n_active = 3
    elif n < 5:
        n_active = 4
    elif n < 6:
        n_active = 5
    else:
        n_active = 6

    print(f"  Tokens: {n}  ->  Active: {n_active}")

    phrases      = split_evenly(tokens, n_active)
    active_names = ELEMENT_NAMES[:n_active]

    for name, phrase in zip(active_names, phrases):
        print(f"  {name:12s}: '{phrase[:70]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for p in phrases for w in p.split() if clean_word(w)]
    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    images_out = [
        {"img_id": name, "priority": i + 1, "phrase": phrase}
        for i, (name, phrase) in enumerate(zip(active_names, phrases))
    ]

    out = {
        "scene_id":   scene_id,
        "layout":     "37",
        "scene_text": scene_text,
        "n_active":   n_active,
        "images":     images_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_37_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
