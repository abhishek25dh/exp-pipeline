"""
Layout 2 Step 3 — Formatter
============================
Reads step_2 output and writes two files:
  1. Overwrites step_1_tmp.json with {main_texts} format the generator expects.
  2. Writes step_3_tmp.json with {grouped_elements} format the generator expects.

No AI calls. Purely deterministic formatting step.
"""

import json
import sys
from pathlib import Path


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_2_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: missing {step2_path}")
        return 1

    data = json.loads(step2_path.read_text(encoding="utf-8"))

    anchor_phrase = data.get("anchor_phrase", "")
    anchor_type   = data.get("anchor_type", "text_red")
    images        = data.get("images", [])

    # --- Write step_1_tmp.json (main_texts for generator) ---
    main_texts = [{
        "element_id": "text_1",
        "type": anchor_type,
        "text_content": anchor_phrase,
        "phrase": anchor_phrase,
        "position": "center",
        "reason": "Deterministic verbatim anchor selected by AI from candidate list.",
    }]
    step1_out = Path("assets/tmp") / f"{scene_id}_layout_2_step_1_tmp.json"
    step1_out.write_text(
        json.dumps({"main_texts": main_texts}, indent=2), encoding="utf-8"
    )

    # --- Write step_3_tmp.json (grouped_elements for generator) ---
    grouped_elements = []
    for img in images:
        grouped_elements.append({
            "element_id":        img.get("element_id", f"image_{img.get('img_id', '0')}"),
            "group_id":          img.get("group_id", "group_1"),
            "phrase":            img.get("phrase", ""),
            "visual_description": img.get("description", ""),
            "reason":            "Deterministic span-derived phrase.",
        })

    step3_out = Path("assets/tmp") / f"{scene_id}_layout_2_step_3_tmp.json"
    step3_out.write_text(
        json.dumps({"grouped_elements": grouped_elements}, indent=2), encoding="utf-8"
    )

    print(f"Step 3 complete: anchor='{anchor_phrase}', images={len(grouped_elements)}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
