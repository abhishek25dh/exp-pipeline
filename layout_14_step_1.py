"""
Layout 14 Step 1 — Deterministic 4-Phase Circular Flow
=======================================================
Layout 14: 4 circular nodes connected by arrows, center title.

Fully deterministic — no AI calls.

Algorithm:
  1. Split script into sentence spans.
  2. Partition sentences into 4 balanced groups.
  3. Each group: img_phrase (majority tokens) + label_phrase (last 2-3 tokens).
  4. Center title: first short sentence (or first 2-4 tokens).
"""

import json
import re
import sys
from pathlib import Path

PUNCT_END = (".", "!", "?")


def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def ends_sentence(tok):
    return bool(tok) and tok.rstrip()[-1] in PUNCT_END


def find_sentence_ends(tokens):
    ends = []
    for i, tok in enumerate(tokens):
        if ends_sentence(tok):
            ends.append(i + 1)
    if not ends or ends[-1] != len(tokens):
        ends.append(len(tokens))
    return ends


def group_sentences_into_n(sent_ends, total, n):
    """Greedy partition of sentences into n balanced groups.

    Guarantees each group gets at least one sentence by enforcing:
      remaining_sents <= remaining_groups → must break now.
    """
    n_sents = len(sent_ends)
    target  = total / n
    groups  = []
    g_start = 0
    sent_idx = 0
    for g in range(n):
        if g == n - 1:
            groups.append((g_start, total))
            break
        g_end = g_start
        while sent_idx < n_sents:
            new_end  = sent_ends[sent_idx]
            sent_idx += 1
            g_end    = new_end
            remaining_groups = n - g - 1
            remaining_sents  = n_sents - sent_idx
            # Must stop: each remaining group needs ≥1 sentence
            if remaining_sents <= remaining_groups:
                break
            # Optionally stop when this group has enough tokens
            if (g_end - g_start) >= target * 0.6:
                break
        groups.append((g_start, g_end))
        g_start = g_end
    return groups


def assign_group_phrases(tokens, s, e, max_label_words=3):
    """img_phrase = majority of group, label_phrase = last 2-3 tokens."""
    n = e - s
    label_len = min(max_label_words, max(2, n // 3))
    label_start = e - label_len
    # Snap label_start to sentence boundary if possible
    for offset in range(0, min(3, label_start - s)):
        pos = label_start - offset
        if pos > s and ends_sentence(tokens[pos - 1]):
            label_start = pos
            break
    label_start = max(s + 1, label_start)
    label_start = min(label_start, e - 1)  # ensure label has at least 1 token
    return (
        " ".join(tokens[s:label_start]),  [s, label_start],
        " ".join(tokens[label_start:e]),  [label_start, e],
    )


def pick_center_title(tokens, sent_ends):
    """Pick a short verbatim phrase from the start of the script for center."""
    first_end = sent_ends[0] if sent_ends else len(tokens)
    if 2 <= first_end <= 4:
        return " ".join(tokens[:first_end]), [0, first_end]
    end = min(4, first_end)
    return " ".join(tokens[:end]), [0, end]


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

    if len(tokens) < 1:
        print(f"Error: script too short for Layout 14, got {len(tokens)}.")
        return 1

    # Priority allocation: use as many phases as tokens allow (min 2 tokens per phase).
    # P1=4 phases, fall back to fewer for short scripts.
    if len(tokens) >= 8:
        n_phases = 4
    elif len(tokens) >= 6:
        n_phases = 3
    elif len(tokens) >= 4:
        n_phases = 2
    else:
        n_phases = 1

    sent_ends = find_sentence_ends(tokens)
    n_sents   = len(sent_ends)
    n_groups  = min(n_phases, n_sents)

    # Pad to n_phases groups by subdividing the last group if needed
    groups = group_sentences_into_n(sent_ends, len(tokens), n_groups)
    while len(groups) < n_phases:
        # Split the largest group in half
        largest = max(range(len(groups)), key=lambda i: groups[i][1] - groups[i][0])
        s, e = groups[largest]
        mid  = (s + e) // 2
        if mid == s:
            mid = s + 1
        if mid >= e:
            groups.append(groups[-1])
        else:
            groups[largest] = (s, mid)
            groups.insert(largest + 1, (mid, e))

    center_phrase, center_span = pick_center_title(tokens, sent_ends)

    phases = []
    for i, (gs, ge) in enumerate(groups[:n_phases]):
        img_p, img_sp, lbl_p, lbl_sp = assign_group_phrases(tokens, gs, ge)
        phases.append({
            "phase_id":    f"phase_{i+1}",
            "img_phrase":  img_p,  "img_span":   img_sp,
            "label_phrase": lbl_p, "label_span": lbl_sp,
        })
    # Pad remaining phases with empty entries so downstream always sees 4
    for i in range(n_phases, 4):
        phases.append({
            "phase_id":    f"phase_{i+1}",
            "img_phrase":  "",     "img_span":   [0, 0],
            "label_phrase": "",    "label_span": [0, 0],
        })

    out = {
        "scene_id":           scene_id,
        "scene_text":         scene_text,
        "tokens":             tokens,
        "center_title":       center_phrase,
        "center_title_span":  center_span,
        "phases":             phases,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_14_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_path}")
    print(f"  center_title: '{center_phrase}'")
    for p in phases:
        print(f"  {p['phase_id']}: img='{p['img_phrase']}' | label='{p['label_phrase']}'")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
