"""
Layout 35 Step 2 - Passthrough (No AI Needed)
=============================================
host_explaining.png is a static local asset -- no description required.
Text element needs no AI generation.
Step 2 simply copies Step 1 output to the Step 2 path to maintain pipeline consistency.
"""

import json
import sys
from pathlib import Path


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    step1_path = Path("assets/tmp") / f"{scene_id}_layout_35_step_1_tmp.json"
    if not step1_path.exists():
        print(f"Error: {step1_path} not found. Run Step 1 first.")
        return 1

    data     = json.loads(step1_path.read_text(encoding="utf-8"))
    out_path = Path("assets/tmp") / f"{scene_id}_layout_35_step_2_tmp.json"
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Step 2 complete (passthrough) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
