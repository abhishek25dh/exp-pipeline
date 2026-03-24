"""
Layout 31 Step 1 - Image Left + Arrow + Image Right + Text Label (Top-Right)
=============================================================================
Visual structure:
  [                          ] [ TEXT LABEL (P4, top-right, text_black) ]
  [ img_left (P1) ] [arrow(P2)] [ img_right (P3)                        ]

Priority / firing order:
  P1: img_left   -- fires first (the "before" / cause)
  P2: arrow      -- fires second (transition connector, MUST have a phrase per Rule 1)
  P3: img_right  -- fires third (the "after" / effect)
  P4: text_label -- fires last (labels/titles the right-side result, Rule 6 applies)

Token thresholds:
  N < 3  -> P1 only
  N < 5  -> P1 + P2 (img_left + arrow)
  N < 7  -> P1 + P2 + P3 (+ img_right)
  N >= 7 -> all 4 (+ text_label), IF label phrase fits in MAX_LINES_LABEL lines
            otherwise degrade to 3 (label dropped, img_right absorbs extra tokens)

Phrase allocation (all 4 active):
  text_label (P4): last sentence — backward search from end (~last N//4 tokens).
                   Must end at a sentence boundary (Rule 6, fires last = punchline).
  img_left, arrow, img_right: remaining tokens split evenly among 3.

Vertical bounds check (layout geometry):
  Label center: y=208 scene. Right image top edge: ~307 scene (y=557, scale=0.499,
  ~1000px image -> half-height ~250). Available below label center: 307-30-208=69px.
  At LINE_SPACING=110: max lines below center = floor(69/55)=1 -> MAX_LINES_LABEL=2.
  MAX_CHARS_LABEL = MAX_LINES_LABEL * MAX_CHARS_LINE = 2 * 36 = 72 chars.
  If the last sentence exceeds this, the label is dropped (n_active degrades to 3).
"""

import json
import re
import sys
from pathlib import Path

# Vertical bounds for the text_label slot (derived from layout geometry)
TEXT_SAFE_W      = 900      # scene px, right column
AVG_CHAR_W       = 25
MAX_CHARS_LINE   = TEXT_SAFE_W // AVG_CHAR_W    # 36
LINE_SPACING     = 110
MAX_LINES_LABEL  = 2                            # derived: available height ~69px below center
MAX_CHARS_LABEL  = MAX_LINES_LABEL * MAX_CHARS_LINE   # 72


def estimate_lines(phrase: str) -> int:
    """How many lines split_into_lines() would produce for this phrase."""
    if len(phrase) <= MAX_CHARS_LINE:
        return 1
    words = phrase.split()
    lines, current_len = 1, 0
    for word in words:
        add_len = len(word) + (1 if current_len > 0 else 0)
        if current_len + add_len > MAX_CHARS_LINE:
            lines += 1
            current_len = len(word)
        else:
            current_len += add_len
    return lines


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def choose_n_active(n: int) -> int:
    if n < 3: return 1
    if n < 5: return 2
    if n < 7: return 3
    return 4


def find_punchline_start(tokens: list, target: int) -> int:
    """Search backward from target for the last sentence boundary.
    The text label phrase = tokens[result:] — ends at script end (Rule 6)."""
    for i in range(target, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return i
    return max(1, target)


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

    n        = len(tokens)
    n_active = choose_n_active(n)
    has_text = n_active == 4
    print(f"  Tokens: {n}  ->  Active: {n_active} (img_left + {'arrow + ' if n_active >= 2 else ''}{'img_right + ' if n_active >= 3 else ''}{'text_label' if has_text else ''})")

    # --- Phrase allocation ---
    if n_active == 1:
        phrases      = [" ".join(tokens)]
        text_phrase  = ""
        label_phrase = ""

    elif n_active <= 3:
        # No text label — split evenly among active elements
        phrases      = split_evenly(tokens, n_active)
        text_phrase  = ""
        label_phrase = ""

    else:
        # All 4: reserve last sentence for text_label, split rest 3 ways
        label_target = max(3, n - max(2, n // 4))
        label_start  = find_punchline_start(tokens, label_target)
        label_phrase = " ".join(tokens[label_start:])

        # Vertical bounds check: if label would produce more lines than the
        # available space above the right image allows, degrade to n_active=3.
        label_lines = estimate_lines(label_phrase)
        if label_lines > MAX_LINES_LABEL:
            print(f"  NOTE: label phrase has {label_lines} lines > MAX {MAX_LINES_LABEL} "
                  f"({len(label_phrase)} chars). Degrading to n_active=3 — img_right absorbs label tokens.")
            n_active     = 3
            has_text     = False
            label_phrase = ""
            phrases      = split_evenly(tokens, 3)
        else:
            phrases      = split_evenly(tokens[:label_start], 3)  # img_left, arrow, img_right
        text_phrase  = label_phrase

    # Map phrases to elements in priority order
    active_ids = ["img_left", "arrow", "img_right", "text_label"][:n_active]
    all_phrases = phrases + ([label_phrase] if has_text else [])

    for eid, phrase in zip(active_ids, all_phrases):
        ends_ok = ends_sentence(phrase.split()[-1]) if phrase.split() else False
        flag = " (Rule 6 OK)" if eid == "text_label" and ends_ok else (" (Rule 6 FAIL!)" if eid == "text_label" else "")
        print(f"  {eid:12s}: '{phrase[:65]}'{flag}")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = []
    for phrase in all_phrases:
        built_clean.extend([clean_word(w) for w in phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    out = {
        "scene_id":     scene_id,
        "layout":       "31",
        "scene_text":   scene_text,
        "n_active":     n_active,
        "img_left_phrase":   all_phrases[0] if len(all_phrases) > 0 else "",
        "arrow_phrase":      all_phrases[1] if len(all_phrases) > 1 else "",
        "img_right_phrase":  all_phrases[2] if len(all_phrases) > 2 else "",
        "label_phrase":      label_phrase,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_31_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
