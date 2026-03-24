import json
import sys
from pathlib import Path


def span_center(span):
    s, e = span
    return (s + e) / 2.0


def assign_column(span, left_mid, right_mid):
    c = span_center(span)
    if c <= left_mid:
        return "left"
    if c >= right_mid:
        return "right"

    d_left = abs(c - left_mid)
    d_right = abs(c - right_mid)
    if d_left + 1.2 < d_right:
        return "left"
    if d_right + 1.2 < d_left:
        return "right"
    return "middle"


def ensure_column_coverage(grouped):
    cols = {"left": [], "middle": [], "right": []}
    for idx, item in enumerate(grouped):
        col = item.get("column", "middle")
        cols.setdefault(col, []).append((idx, item))

    if not cols["left"] and len(grouped) >= 2:
        idx = min(range(len(grouped)), key=lambda i: grouped[i]["span"][0])
        grouped[idx]["column"] = "left"
        grouped[idx]["reason"] = "Moved to left to maintain left-column visual coverage."

    if not cols["right"] and len(grouped) >= 2:
        idx = max(range(len(grouped)), key=lambda i: grouped[i]["span"][0])
        grouped[idx]["column"] = "right"
        grouped[idx]["reason"] = "Moved to right to maintain right-column visual coverage."

    return grouped


def rebalance_columns(grouped, max_side_items=4):
    # Keep side columns from becoming overcrowded; shift overflow near anchors to middle.
    for side in ("left", "right"):
        while True:
            side_indices = [i for i, it in enumerate(grouped) if it.get("column") == side]
            if len(side_indices) <= max_side_items:
                break
            if side == "left":
                # Move the side item closest to bridge (latest left item).
                idx = max(side_indices, key=lambda i: grouped[i]["span"][0])
            else:
                # Move the side item closest to bridge (earliest right item).
                idx = min(side_indices, key=lambda i: grouped[i]["span"][0])
            grouped[idx]["column"] = "middle"
            grouped[idx]["reason"] = "Moved to middle to prevent side-column overcrowding."
    return grouped


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    step1_path = Path(f"assets/tmp/{scene_id}_layout_1_step_1_tmp.json")
    step2_path = Path(f"assets/tmp/{scene_id}_layout_1_step_2_tmp.json")
    if not step1_path.exists() or not step2_path.exists():
        print(f"Error: Missing step input JSON for {scene_id}.")
        return 1

    step1 = json.loads(step1_path.read_text(encoding="utf-8"))
    step2 = json.loads(step2_path.read_text(encoding="utf-8"))

    anchor_spans = step1.get("anchor_spans", {})
    left_span = anchor_spans.get("text_1", [0, 1])
    right_span = anchor_spans.get("text_2", [1, 2])
    left_mid = span_center(left_span)
    right_mid = span_center(right_span)

    phrases = step2.get("phrases", [])
    grouped = []
    for item in phrases:
        span = item.get("span", [0, 0])
        if not isinstance(span, list) or len(span) != 2:
            continue
        col = assign_column(span, left_mid, right_mid)
        grouped.append(
            {
                "phrase_id": item.get("phrase_id", ""),
                "span": span,
                "phrase": item.get("phrase", ""),
                "visual_description": item.get("visual_description", ""),
                "column": col,
                "reason": "Deterministic column assignment from anchor proximity and chronology.",
            }
        )

    grouped.sort(key=lambda x: (x["span"][0], x["span"][1]))
    grouped = ensure_column_coverage(grouped)
    grouped = rebalance_columns(grouped)

    out = {
        "scene_id": scene_id,
        "grouped_elements": grouped,
    }

    out_path = Path(f"assets/tmp/{scene_id}_layout_1_step_3_tmp.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 3 complete. Saved to {out_path}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
