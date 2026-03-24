"""
Layout 30 Step 1 - Host Left + 1 Image Right
=============================================
Visual structure:
  [ host_looking_right (P1, left, static) ]  [ img_right (P2, AI-generated) ]

Priority:
  P1: host_looking_right.png -- always present, static local asset
  P2: single image on right  -- AI-generated, fires after host

Token thresholds:
  N < 3  -> P1 only (host gets all tokens)
  N >= 3 -> P1 + P2 (host + image, tokens split evenly at sentence boundary)
"""

import json
import re
import sys
from pathlib import Path


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def find_split(tokens: list, target: int, window: int = 3) -> int:
    """Snap split point to nearest sentence boundary within window."""
    n = len(tokens)
    for delta in range(0, window + 1):
        for idx in [target + delta, target - delta]:
            if 1 <= idx < n and ends_sentence(tokens[idx - 1]):
                return idx
    return max(1, min(n - 1, target))


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

    n        = len(tokens)
    n_active = 2 if n >= 3 else 1
    print(f"  Tokens: {n}  ->  Active: {n_active}")

    if n_active == 1:
        host_phrase  = " ".join(tokens)
        img_phrase   = ""
    else:
        split = find_split(tokens, n // 2)
        host_phrase = " ".join(tokens[:split])
        img_phrase  = " ".join(tokens[split:])

    print(f"  host (P1): '{host_phrase[:70]}'")
    if img_phrase:
        print(f"  img  (P2): '{img_phrase[:70]}'")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = [clean_word(w) for w in host_phrase.split() if clean_word(w)]
    if img_phrase:
        built_clean.extend([clean_word(w) for w in img_phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":   scene_id,
        "layout":     "30",
        "scene_text": scene_text,
        "n_active":   n_active,
        "host_phrase": host_phrase,
        "img_phrase":  img_phrase,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_30_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
