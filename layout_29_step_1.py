"""
Layout 29 Step 1 - Statement Stack (4 Text Lines, Alternating Black/Red)
=========================================================================
Visual structure:
  [ TEXT 1 (black, y=282,  P1) ]   ← first sentence / clause
  [ TEXT 2 (red,   y=497,  P2) ]   ← second sentence / clause
  [ TEXT 3 (black, y=694,  P3) ]   ← third sentence / clause
  [ TEXT 4 (red,   y=925,  P4) ]   ← fourth sentence / clause (punchline)

No images. Pure text layout.

Priority: top-to-bottom (P1 fires first, P4 fires last).
Colors: position-fixed alternating (text_black / text_red), not randomly chosen.

n_active determination (two-tier):
  1. Sentence-driven (primary): count sentence ends (.!?)
     n_sentences >= 2 → n_active = min(4, n_sentences)
  2. Clause-driven fallback: when only 1 sentence, count clause ends (,;:—)
     n_clauses >= 2 → n_active = min(4, n_clauses)
     n_clauses < 2  → proportional split (best effort)

Priority-based cap: n_active <= total_tokens // MIN_TOKENS_PER_SLOT.
Never emit a slot with fewer than MIN_TOKENS_PER_SLOT tokens.

Split strategy: choose n_active-1 boundary points (sentence ends preferred,
clause ends as fallback) distributed evenly across the script.

No AI in Step 2 — this layout passes through step 1 output unchanged.
"""

import json
import re
import sys
from pathlib import Path


SLOT_TYPES = ["text_black", "text_red", "text_black", "text_red"]  # position-fixed

MIN_TOKENS_PER_SLOT = 3  # priority-based cap — never emit a slot with fewer tokens


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def ends_clause(tok: str) -> bool:
    """Token ends at a clause boundary: comma, semicolon, colon, or em-dash."""
    if not tok:
        return False
    last = tok.rstrip()[-1]
    return last in ",;:\u2014"  # comma, semicolon, colon, em-dash


def find_sentence_ends(tokens: list) -> list:
    """Return 1-based indices where each sentence ends."""
    return [i for i in range(1, len(tokens) + 1) if ends_sentence(tokens[i - 1])]


def find_clause_ends(tokens: list) -> list:
    """Return 1-based indices where a clause ends (comma, semicolon, colon, em-dash).
    Excludes the very last token (that's a sentence end, not an internal clause)."""
    ends = []
    for i in range(1, len(tokens)):  # skip last token
        if ends_clause(tokens[i - 1]):
            ends.append(i)
    return ends


def choose_n_active(tokens: list) -> int:
    """Determine how many slots to fill.

    Two-tier strategy:
      1. Sentence-driven: n_sentences >= 2 → use sentence count
      2. Clause-driven fallback: single sentence → count internal clause boundaries
      3. Priority-based cap: never exceed total_tokens // MIN_TOKENS_PER_SLOT
    """
    total = len(tokens)
    sent_ends = find_sentence_ends(tokens)
    n_sentences = len(sent_ends)

    if n_sentences >= 2:
        n = min(4, n_sentences)
    else:
        # Single sentence (or no punctuation) — fall back to clause boundaries
        clause_ends = find_clause_ends(tokens)
        n_clauses = len(clause_ends) + 1  # N boundaries → N+1 segments
        if n_clauses >= 2:
            n = min(4, n_clauses)
        else:
            # No internal clause boundaries either — proportional best-effort
            n = min(4, max(1, total // MIN_TOKENS_PER_SLOT))

    # Priority-based cap: ensure every slot gets at least MIN_TOKENS_PER_SLOT
    max_by_tokens = max(1, total // MIN_TOKENS_PER_SLOT)
    n = min(n, max_by_tokens)
    return max(1, n)


def _split_at_boundaries(tokens: list, boundaries: list, n_active: int) -> list:
    """Split tokens into n_active phrases using the nearest boundary to each target.

    boundaries: 1-based indices of valid split points (sentence or clause ends).
    The final phrase always runs to the end of the token list.
    """
    total = len(tokens)

    if n_active == 1 or not boundaries:
        return [" ".join(tokens)]

    # We need n_active-1 split points
    targets = [round(total * i / n_active) for i in range(1, n_active)]
    split_pts = []
    for t in targets:
        min_allowed = (split_pts[-1] + 1) if split_pts else 1
        candidates = [e for e in boundaries if e >= min_allowed]
        if not candidates:
            break
        best = min(candidates, key=lambda x: abs(x - t))
        split_pts.append(best)

    bounds = [0] + split_pts + [total]
    phrases = [" ".join(tokens[bounds[i]:bounds[i + 1]]) for i in range(len(bounds) - 1)]
    phrases = [p for p in phrases if p.strip()]
    return phrases


def build_text_phrases(tokens: list, n_active: int) -> list:
    """Split tokens into n_active phrases.

    Strategy (two-tier):
      1. If multiple sentences exist, split at sentence boundaries (Rule 6).
      2. If single sentence, split at clause boundaries (commas etc.).
      3. If no internal boundaries at all, proportional word split (best effort).
    The final phrase always ends at the script's terminal punctuation.
    """
    total = len(tokens)

    if n_active == 1:
        return [" ".join(tokens)]

    sent_ends = find_sentence_ends(tokens)

    # Tier 1: sentence boundaries (multiple sentences available)
    if len(sent_ends) >= 2:
        return _split_at_boundaries(tokens, sent_ends, n_active)

    # Tier 2: clause boundaries (single sentence)
    clause_ends = find_clause_ends(tokens)
    if clause_ends:
        return _split_at_boundaries(tokens, clause_ends, n_active)

    # Tier 3: proportional fallback — no boundaries at all
    chunk = max(1, total // n_active)
    phrases = []
    for i in range(n_active):
        start = i * chunk
        end = (i + 1) * chunk if i < n_active - 1 else total
        phrase = " ".join(tokens[start:end])
        if phrase.strip():
            phrases.append(phrase)
    return phrases


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
    n_sents  = len(find_sentence_ends(tokens))
    n_clauses = len(find_clause_ends(tokens))
    n_active = choose_n_active(tokens)
    tier = "sentence" if n_sents >= 2 else ("clause" if n_clauses >= 1 else "proportional")
    print(f"  Tokens: {n}  Sentences: {n_sents}  Clauses: {n_clauses+1}  ->  Active slots: {n_active} (split={tier})")

    phrases = build_text_phrases(tokens, n_active)
    # Clamp to n_active (safety — build_text_phrases may return fewer if ends are scarce)
    phrases = phrases[:n_active]
    n_active = len(phrases)

    # Priority-based post-split validation: reduce n_active if any slot is too thin
    while n_active > 1 and any(len(p.split()) < MIN_TOKENS_PER_SLOT for p in phrases):
        thin = [p for p in phrases if len(p.split()) < MIN_TOKENS_PER_SLOT]
        print(f"  NOTE: slot too thin ({[len(p.split()) for p in thin]} tokens < {MIN_TOKENS_PER_SLOT}), reducing n_active {n_active} -> {n_active - 1}")
        n_active -= 1
        phrases = build_text_phrases(tokens, n_active)
        phrases = phrases[:n_active]
        n_active = len(phrases)

    for i, phrase in enumerate(phrases):
        slot_type = SLOT_TYPES[i]
        ends_ok   = ends_sentence(phrase.split()[-1]) if phrase.split() else False
        print(f"  slot_{i+1} ({slot_type:12s}): '{phrase[:60]}' | ends_at_sentence={ends_ok}")

    # --- Tiling validation ---
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean  = []
    for phrase in phrases:
        built_clean.extend([clean_word(w) for w in phrase.split() if clean_word(w)])

    if built_clean != script_clean:
        print("WARNING: tiling mismatch.")
        print(f"  Script : {script_clean}")
        print(f"  Built  : {built_clean}")
        return 1

    # --- Build slot list ---
    slots_out = [
        {
            "slot_id":   f"slot_{i + 1}",
            "priority":  i + 1,
            "type":      SLOT_TYPES[i],
            "phrase":    phrase,
        }
        for i, phrase in enumerate(phrases)
    ]

    out = {
        "scene_id":   scene_id,
        "layout":     "29",
        "scene_text": scene_text,
        "n_active":   n_active,
        "slots":      slots_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_29_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
