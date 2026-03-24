"""
Layout 10 Step 1 — Deterministic Macro/Micro Phrase Plan
=========================================================
Layout 10: 1 large macro image (left) + 2-3 small micro images (right) + arrows.

FULLY DETERMINISTIC — no AI calls.

Algorithm:
  1. Tokenize by whitespace (preserving punctuation — matches timing checker).
  2. Split into sentence spans at terminal punctuation.
  3. Group sentences into (1 macro + N micro) groups, balanced by token count.
  4. Within macro group: img_phrase = first portion, txt_phrase = rest.
  5. Within each micro group: arrow_phrase = first 1-2 tokens,
     img_phrase = next 2-4 tokens, txt_phrase = remaining.
  6. Validate: unique clean start-positions, no prefix collisions.

Outputs {macro, micros} phrase plan for Step 2 to add AI image descriptions.
"""

import json
import re
import sys
from pathlib import Path

PUNCT_END = (".", "!", "?")


# ── Tokenization ──────────────────────────────────────────────────────────────

def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def ends_sentence(tok):
    return bool(tok) and tok.rstrip()[-1] in PUNCT_END


def clean_token(tok):
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def find_sentence_end_positions(tokens):
    """Return list of exclusive-end indices for each sentence."""
    ends = []
    for i, tok in enumerate(tokens):
        if ends_sentence(tok):
            ends.append(i + 1)
    if not ends or ends[-1] != len(tokens):
        ends.append(len(tokens))   # treat remainder as one sentence
    return ends


# ── Group splitting ────────────────────────────────────────────────────────────

def group_sentences(sent_ends, n_groups):
    """
    Partition sentences into n_groups contiguous spans (by cumulative token end).
    Returns list of (token_start, token_end) per group.
    Each group contains one or more consecutive sentences.
    Uses greedy approach: build groups by assigning sentences to keep groups balanced.
    """
    n_sents = len(sent_ends)
    starts = [0] + sent_ends[:-1]   # sentence start positions
    total  = sent_ends[-1]
    target = total / n_groups

    groups = []
    g_start = 0
    sent_idx = 0
    for g in range(n_groups):
        if g == n_groups - 1:
            # Last group absorbs all remaining
            groups.append((g_start, total))
            break
        g_end = g_start
        while sent_idx < n_sents:
            new_end = sent_ends[sent_idx]
            sent_idx += 1
            g_end = new_end
            # Stop when we've covered enough tokens for this group
            # but always assign at least 1 sentence per group
            remaining_groups = n_groups - g - 1
            remaining_sents  = n_sents - sent_idx
            if remaining_sents >= remaining_groups and (g_end - g_start) >= target * 0.6:
                break
        groups.append((g_start, g_end))
        g_start = g_end
    return groups


# ── Within-group phrase assignment ────────────────────────────────────────────

def assign_macro_phrases(tokens, s, e):
    """macro group → img_phrase (first ~half) + txt_phrase (rest)."""
    n = e - s
    # img gets min 2, max 6, ~half the group; prefer ending at sentence boundary
    img_target = max(2, min(6, n // 2))
    img_end = s + img_target
    # Snap img_end forward to sentence boundary if close
    for offset in range(0, min(4, e - img_end)):
        if ends_sentence(tokens[img_end - 1 + offset]):
            img_end = img_end + offset
            break
    img_end = max(s + 2, min(img_end, e - 1))
    return (
        " ".join(tokens[s:img_end]),   [s, img_end],
        " ".join(tokens[img_end:e]),   [img_end, e],
    )


def assign_micro_phrases(tokens, s, e):
    """micro group → arrow_phrase (1-2) + img_phrase (2-4) + txt_phrase (rest)."""
    n = e - s
    # Arrow: 1-2 tokens — short transition cue
    arrow_len = 1 if n <= 5 else 2
    arrow_end = s + arrow_len
    # img: 2-4 tokens
    img_len    = max(2, min(4, (n - arrow_len) // 2))
    img_end    = arrow_end + img_len
    img_end    = max(arrow_end + 2, min(img_end, e - 1))
    return (
        " ".join(tokens[s:arrow_end]),      [s, arrow_end],
        " ".join(tokens[arrow_end:img_end]), [arrow_end, img_end],
        " ".join(tokens[img_end:e]),         [img_end, e],
    )


# ── Timing-collision check ────────────────────────────────────────────────────

def clean_phrase(phrase):
    return tuple(clean_token(w) for w in phrase.split() if clean_token(w))


def first_occurrence(clean_tokens, clean_phrase_tup):
    n = len(clean_tokens)
    k = len(clean_phrase_tup)
    for i in range(n - k + 1):
        if tuple(clean_tokens[i:i + k]) == clean_phrase_tup:
            return i
    return -1


def check_collisions(phrases, clean_tokens):
    """Return list of collision descriptions, empty if clean."""
    errors = []
    cleaned = [(p, clean_phrase(p)) for p in phrases]
    starts  = [(p, cp, first_occurrence(clean_tokens, cp)) for p, cp in cleaned]

    # Duplicate start positions
    seen_pos = {}
    for p, cp, pos in starts:
        if pos == -1:
            errors.append(f"NOT_VERBATIM: '{p}'")
            continue
        if pos in seen_pos:
            errors.append(f"COLLISION at pos {pos}: '{p}' vs '{seen_pos[pos]}'")
        else:
            seen_pos[pos] = p

    # Prefix collisions
    for i, (p1, cp1, _) in enumerate(starts):
        for p2, cp2, _ in starts[i + 1:]:
            if not cp1 or not cp2:
                continue
            if cp2[:len(cp1)] == cp1 or cp1[:len(cp2)] == cp2:
                errors.append(f"PREFIX: '{p1}' ~ '{p2}'")
    return errors


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text  = strip_scene_prefix(prompt_data.get("prompt", ""))
    tokens      = scene_text.split()          # whitespace split — preserves punct

    if len(tokens) < 1:
        print("Error: script too short for Layout 10.")
        return 1

    clean_toks   = [clean_token(t) for t in tokens if clean_token(t)]
    sent_ends    = find_sentence_end_positions(tokens)
    n_sentences  = len(sent_ends)

    # Priority allocation: scale micros down for short scripts.
    # Macro needs >=3 tokens; each micro needs >=4 (arrow+img+txt).
    n_micros = 2 if (len(tokens) < 20 or n_sentences <= 3) else 3
    n_groups = 1 + n_micros

    # If not enough sentences to fill groups, reduce (allow down to 1 = macro only)
    while n_groups > n_sentences and n_groups > 1:
        n_groups  -= 1
        n_micros  -= 1

    # If not enough tokens for all groups (each needs ~3), drop lower-priority micros
    while n_groups > 1 and n_groups * 3 > len(tokens):
        n_groups -= 1
        n_micros -= 1

    groups = group_sentences(sent_ends, n_groups)

    # Assign phrases
    macro_s, macro_e = groups[0]
    m_img, m_img_sp, m_txt, m_txt_sp = assign_macro_phrases(tokens, macro_s, macro_e)

    micros = []
    for i in range(n_micros):
        ms, me = groups[1 + i]
        arr, arr_sp, img, img_sp, txt, txt_sp = assign_micro_phrases(tokens, ms, me)
        micros.append({
            "micro_id":    f"micro_{i}",
            "arrow_phrase": arr, "arrow_span": arr_sp,
            "img_phrase":   img, "img_span":   img_sp,
            "txt_phrase":   txt, "txt_span":   txt_sp,
        })

    # Validate timing collisions
    all_phrases = [m_img, m_txt] + [p for m in micros for p in
                   [m["arrow_phrase"], m["img_phrase"], m["txt_phrase"]]]
    collisions  = check_collisions(all_phrases, clean_toks)
    if collisions:
        print(f"  WARNING — timing issues detected:")
        for c in collisions:
            print(f"    {c}")
    else:
        print(f"  Collision check: PASS")

    print(f"  Tokens: {len(tokens)}  |  1 macro + {n_micros} micros")
    print(f"    macro_img : '{m_img}'")
    print(f"    macro_txt : '{m_txt}'")
    for m in micros:
        print(f"    {m['micro_id']} arrow='{m['arrow_phrase']}' "
              f"img='{m['img_phrase']}' txt='{m['txt_phrase']}'")

    out = {
        "scene_id":  scene_id,
        "scene_text": scene_text,
        "tokens":    tokens,
        "macro": {
            "img_phrase": m_img, "img_span": m_img_sp,
            "txt_phrase": m_txt, "txt_span": m_txt_sp,
        },
        "micros": micros,
        "n_micros": n_micros,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_10_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
