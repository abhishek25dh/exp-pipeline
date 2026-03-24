"""
Layout 4 Step 3 — Formatter
============================
Reads step_2 output and writes two files:
  1. Overwrites step_1_tmp.json with {setup} format the generator expects.
  2. Writes step_3_tmp.json with {grouped_elements} format the generator expects.

No AI calls. Purely deterministic formatting step.
"""

import json
import sys
from pathlib import Path


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    step2_path = Path("assets/tmp") / f"{scene_id}_layout_4_step_2_tmp.json"
    if not step2_path.exists():
        print(f"Error: missing {step2_path}")
        return 1

    data = json.loads(step2_path.read_text(encoding="utf-8"))

    anchor_phrase = data.get("anchor_phrase", "")
    anchor_type   = data.get("anchor_type", "text_highlighted")
    host_phrase   = data.get("host_phrase", "")
    host_emotion  = data.get("host_emotion", "explaining")
    host_size     = data.get("host_size", "half_bottom")
    images        = data.get("images", [])

    # --- Write step_1_tmp.json (setup format for generator) ---
    setup = {
        "main_text":    anchor_phrase,
        "phrase":       anchor_phrase,
        "anchor_type":  anchor_type,
        "host_phrase":  host_phrase,
        "host_emotion": host_emotion,
        "host_size":    host_size,
    }
    step1_out = Path("assets/tmp") / f"{scene_id}_layout_4_step_1_tmp.json"
    step1_out.write_text(json.dumps({"setup": setup}, indent=2), encoding="utf-8")

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

    step3_out = Path("assets/tmp") / f"{scene_id}_layout_4_step_3_tmp.json"
    step3_out.write_text(
        json.dumps({"grouped_elements": grouped_elements}, indent=2), encoding="utf-8"
    )

    print(f"Step 3 complete: anchor='{anchor_phrase}', images={len(grouped_elements)}, "
          f"host={host_emotion}/{host_size}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
