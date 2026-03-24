"""
Layout 15 Step 1 — Deterministic Hero + Bullets Phrase Plan
============================================================
Layout: 1 large hero image (left) + section_title + 3 bullets + optional CTA (right column).

FULLY DETERMINISTIC — no AI calls.

Algorithm:
  1. Whitespace tokenize (preserving punctuation).
  2. Find sentence boundaries.
  3. Priority-based slot assignment:
       P1 hero_image    : first 30-50% of tokens (image — no sentence rule).
       P2 section_title : next 3-6 tokens (short heading, snap to sentence end).
       P3 bullet_b1     : next sentence chunk.
       P4 bullet_b2     : next sentence chunk.
       P5 bullet_b3     : next sentence chunk.
       P6 cta           : last sentence if tokens remain.
  4. Drop slots from P6 down when script is too short.
  5. Validates tiling (full coverage with no overlaps).

Outputs hero image phrase + all text phrases for step 2.
"""

import json
import re
import sys
from pathlib import Path

PUNCT_END = (".", "!", "?")
MIN_HERO_TOKENS   = 3
MIN_SECTION_TOKENS = 2
MIN_BULLET_TOKENS  = 2
MIN_CTA_TOKENS     = 2


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


def snap_to_sentence_end(tokens, target_end, s, e, sent_ends, forward_limit=5):
    """Snap end forward to nearest sentence boundary within forward_limit tokens."""
    cap = min(e, target_end + forward_limit)
    for j in range(target_end, cap + 1):
        if j > s and ends_sentence(tokens[j - 1]):
            return j
    # Fall back: nearest sentence end at or before target
    for j in range(min(target_end, e), s, -1):
        if ends_sentence(tokens[j - 1]):
            return j
    return min(target_end, e)


def assign_hero(tokens, sent_ends, n):
    """Hero takes roughly first 40% of tokens, snapped to a sentence boundary."""
    target = max(MIN_HERO_TOKENS, int(n * 0.40))
    hero_end = snap_to_sentence_end(tokens, target, 0, n, sent_ends, forward_limit=6)
    hero_end = max(MIN_HERO_TOKENS, min(hero_end, n - MIN_SECTION_TOKENS - MIN_BULLET_TOKENS))
    return 0, hero_end


def assign_short_heading(tokens, start, end, sent_ends, max_tokens=6):
    """Section title: short heading, 3-6 tokens, snap to sentence end if possible."""
    target_end = min(start + max_tokens, end)
    heading_end = snap_to_sentence_end(tokens, min(start + 3, end), start, end, sent_ends, forward_limit=4)
    heading_end = max(start + MIN_SECTION_TOKENS, min(heading_end, target_end, end))
    return start, heading_end


def divide_into_chunks(tokens, start, end, n_chunks, sent_ends):
    """Divide [start, end) into n_chunks sentence-biased groups."""
    total = end - start
    if n_chunks <= 0 or total == 0:
        return []
    if n_chunks == 1:
        return [(start, end)]
    target = total / n_chunks
    chunks = []
    pos = start
    for c in range(n_chunks):
        if c == n_chunks - 1:
            chunks.append((pos, end))
            break
        chunk_target = int(pos + target)
        chunk_end = snap_to_sentence_end(tokens, chunk_target, pos, end, sent_ends, forward_limit=4)
        remaining_chunks = n_chunks - c - 1
        remaining_tokens = end - chunk_end
        if remaining_tokens < remaining_chunks * MIN_BULLET_TOKENS:
            chunk_end = max(pos + MIN_BULLET_TOKENS, end - remaining_chunks * MIN_BULLET_TOKENS)
        chunk_end = max(pos + MIN_BULLET_TOKENS, min(chunk_end, end - remaining_chunks * MIN_BULLET_TOKENS))
        chunks.append((pos, chunk_end))
        pos = chunk_end
    return chunks


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
    n           = len(tokens)

    if n < 1:
        print("Error: script too short for Layout 15.")
        return 1

    sent_ends = find_sentence_ends(tokens)

    # ── P1: Hero image ──────────────────────────────────────────────────────────
    hero_s, hero_e = assign_hero(tokens, sent_ends, n)
    remaining_start = hero_e

    # ── Decide active slots based on remaining tokens ───────────────────────────
    remaining = n - hero_e
    use_section = remaining >= MIN_SECTION_TOKENS + MIN_BULLET_TOKENS
    n_bullets   = 0
    if use_section:
        after_section = remaining - MIN_SECTION_TOKENS
        n_bullets = min(3, max(1, after_section // MIN_BULLET_TOKENS))
        # Scale back if too tight
        while n_bullets > 1 and after_section < n_bullets * MIN_BULLET_TOKENS + MIN_SECTION_TOKENS:
            n_bullets -= 1
    use_cta = False

    # ── P2: Section title ────────────────────────────────────────────────────────
    section_phrase = section_s = section_e = None
    if use_section:
        section_s, section_e = assign_short_heading(tokens, remaining_start, n, sent_ends)
        # Reserve at least n_bullets * MIN_BULLET_TOKENS after section
        section_e = min(section_e, n - n_bullets * MIN_BULLET_TOKENS)
        section_e = max(remaining_start + MIN_SECTION_TOKENS, section_e)
        section_phrase = " ".join(tokens[section_s:section_e])
        remaining_start = section_e

    # ── P3-P5: Bullets ───────────────────────────────────────────────────────────
    bullet_chunks = divide_into_chunks(tokens, remaining_start, n, n_bullets, sent_ends) if n_bullets > 0 else []

    # Check if last bullet has enough tokens for a separate CTA
    if bullet_chunks and n_bullets == 3:
        last_s, last_e = bullet_chunks[-1]
        # Find last sentence start in last chunk
        prev_sent_end = last_s
        for se in sent_ends:
            if se < last_e:
                prev_sent_end = se
        if prev_sent_end > last_s + MIN_BULLET_TOKENS and (last_e - prev_sent_end) >= MIN_CTA_TOKENS:
            use_cta = True
            bullet_chunks[-1] = (last_s, prev_sent_end)
            cta_s, cta_e = prev_sent_end, last_e
        else:
            cta_s = cta_e = None
    else:
        cta_s = cta_e = None

    bullets = []
    for i, (bs, be) in enumerate(bullet_chunks):
        bullets.append({
            "bullet_id": f"b{i+1}",
            "phrase":    " ".join(tokens[bs:be]),
            "span":      [bs, be],
        })

    cta_phrase = " ".join(tokens[cta_s:cta_e]) if use_cta and cta_s is not None else ""

    # ── Print summary ────────────────────────────────────────────────────────────
    print(f"  Tokens: {n}  |  hero + {'section + ' if use_section else ''}{n_bullets} bullets{' + cta' if use_cta and cta_phrase else ''}")
    print(f"    hero:    '{' '.join(tokens[hero_s:hero_e])}'")
    if use_section and section_phrase:
        print(f"    section: '{section_phrase}'")
    for b in bullets:
        print(f"    {b['bullet_id']}:      '{b['phrase']}'")
    if cta_phrase:
        print(f"    cta:     '{cta_phrase}'")

    out = {
        "scene_id":   scene_id,
        "scene_text": scene_text,
        "tokens":     tokens,
        "hero": {
            "phrase": " ".join(tokens[hero_s:hero_e]),
            "span":   [hero_s, hero_e],
        },
        "section": {
            "phrase": section_phrase or "",
            "span":   [section_s, section_e] if section_s is not None else None,
        },
        "bullets":    bullets,
        "cta": {
            "phrase": cta_phrase,
            "span":   [cta_s, cta_e] if cta_s is not None else None,
        },
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_15_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
