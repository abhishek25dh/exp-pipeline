"""
Layout 3 Step 1 — Deterministic Tokenization + Image Spans
===========================================================
Layout 3: scattered images only — no central text element.

FULLY DETERMINISTIC — no AI calls.
Splits all script tokens into N image spans, pairs consecutive spans into groups.
Outputs {tokens, scene_text, images} for Step 2 to add AI descriptions.
"""

import json
import re
import sys
from pathlib import Path


def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def ends_sentence(tok):
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def build_image_spans(tokens):
    """Split all tokens into N spans — no gaps, no overlaps.
    N = max(2, min(8, tokens // 3)).
    Pairs consecutive spans into visual groups (2 images per group).
    """
    n = len(tokens)
    n_img = max(2, min(8, max(1, n // 3)))

    size = n // n_img
    spans = []
    pos = 0
    for i in range(n_img):
        end = (pos + size) if i < n_img - 1 else n
        end = min(end, n)
        if pos < end:
            spans.append([pos, end])
        pos = end

    return spans


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text = strip_scene_prefix(prompt_data.get("prompt", ""))
    tokens = scene_text.split()

    if not tokens:
        print(f"Error: empty scene text for {scene_id}.")
        return 1

    spans = build_image_spans(tokens)
    if not spans:
        print(f"Error: no image spans for {scene_id}.")
        return 1

    images = []
    for idx, span in enumerate(spans):
        phrase = " ".join(tokens[span[0]:span[1]])
        group_num = (idx // 2) + 1
        images.append({
            "img_id": f"img_{idx}",
            "element_id": f"image_group_{group_num}_{idx}",
            "group_id": f"group_{group_num}",
            "span": span,
            "phrase": phrase,
            "description": "",
        })

    print(f"  Tokens: {len(tokens)}  |  Images: {len(images)}")
    for img in images:
        print(f"    {img['img_id']}  {img['group_id']}  span={img['span']}  '{img['phrase']}'")

    out = {
        "scene_id": scene_id,
        "scene_text": scene_text,
        "tokens": tokens,
        "images": images,
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_3_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
