import json
import sys
from pathlib import Path


def assign_subgroups(grouped_elements):
    by_col = {"left": [], "middle": [], "right": []}
    for idx, item in enumerate(grouped_elements):
        col = item.get("column", "middle")
        by_col.setdefault(col, []).append((idx, item))

    result = [None] * len(grouped_elements)
    image_id = 1

    for col in ("left", "middle", "right"):
        col_items = by_col.get(col, [])
        col_items.sort(key=lambda x: (x[1]["span"][0], x[1]["span"][1]))

        subgroup = 1
        prev_end = None
        for _, item in col_items:
            start = item["span"][0]
            end = item["span"][1]

            if prev_end is not None and (start - prev_end) >= 4:
                subgroup += 1
                reason = "New subgroup due to larger narrative gap in this column."
            elif prev_end is None:
                reason = "First subgroup in this column."
            else:
                reason = "Same subgroup due to close narrative continuity in this column."

            result_item = {
                "element_id": f"image_{image_id}",
                "phrase_id": item.get("phrase_id", ""),
                "span": item.get("span", [0, 0]),
                "phrase": item.get("phrase", ""),
                "visual_description": item.get("visual_description", ""),
                "column": col,
                "subgroup": subgroup,
                "reason": reason,
            }
            result[image_id - 1] = result_item
            image_id += 1
            prev_end = end

    # Remove any empty slots caused by missing columns.
    return [r for r in result if r is not None]


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    step3_path = Path(f"assets/tmp/{scene_id}_layout_1_step_3_tmp.json")
    if not step3_path.exists():
        print(f"Error: Missing step 3 JSON for {scene_id}.")
        return 1

    step3 = json.loads(step3_path.read_text(encoding="utf-8"))
    grouped_elements = step3.get("grouped_elements", [])

    # Ensure deterministic chronological ordering before subgrouping.
    grouped_elements = sorted(grouped_elements, key=lambda x: (x["span"][0], x["span"][1]))
    final_elements = assign_subgroups(grouped_elements)

    out = {
        "scene_id": scene_id,
        "final_elements": final_elements,
    }

    out_path = Path(f"assets/tmp/{scene_id}_layout_1_step_4_tmp.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 4 complete. Saved to {out_path}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
