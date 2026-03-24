"""
Layout 17 Step 1 — Deterministic Phrase Segmentation (Triforce / Three-Point Triangle)
======================================================================================
Follows LAYOUT_DESIGN_APPROACH.md: no AI, purely deterministic.

Layout 17 has 7 elements:
  - center_word: 1-2 token anchor from the script
  - 3 vertex groups (top, bottom_right, bottom_left):
      each with img_phrase + lbl_phrase (consecutive fragments)

Pipeline:
  1. Tokenize script (strip scene prefix)
  2. Split into sentence spans
  3. Map sentences → 3 vertex groups
  4. Extract center_word from the first sentence
  5. Split each group into img_phrase + lbl_phrase via DP scoring
  6. Validate all 7 phrases (non-empty, unique, no prefix collisions)
"""

import json
import math
import re
import sys
from pathlib import Path


# ── Utilities ────────────────────────────────────────────────────────────────

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "from", "by", "it", "its", "is", "was", "are", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "not", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "up", "out", "as", "so", "if", "then", "than",
    "also", "just", "about", "into", "over", "after", "before",
    "no", "now", "when", "what", "where", "who", "how", "never",
    "always", "ever", "still", "even", "yet", "own", "maybe", "like",
    "youre", "dont", "cant", "wont", "isnt", "wasnt", "didnt", "hasnt",
    "havent", "shouldnt", "wouldnt", "couldnt", "theyre", "thats",
    "youve", "ive", "weve", "theyve", "arent", "doesnt", "hadnt", "werent",
    "im", "hed", "shed", "wed", "theyd", "youll", "hell", "shell",
    "well", "theyll",
}

BAD_END_WORDS = {"youre", "im", "were", "theyre"}
PUNCT_END = (".", "!", "?")


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def normalize_word(w: str) -> str:
    w = (w or "").lower()
    w = w.replace("\u2019", "'").replace("'", "")
    w = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", w)
    return w


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def clean_phrase_tuple(phrase: str):
    return tuple(clean_word(w) for w in (phrase or "").split() if clean_word(w))


def is_prefix_tuple(a, b) -> bool:
    if not a or not b or len(a) > len(b):
        return False
    return b[: len(a)] == a


def content_words(phrase: str):
    out = set()
    for raw in re.findall(r"[A-Za-z0-9']+", (phrase or "").lower()):
        w = normalize_word(raw)
        if not w or len(w) <= 1 or w in STOP_WORDS:
            continue
        out.add(w)
    return out


def _span_phrase(tokens, s, e):
    return " ".join(tokens[s:e]).strip()


# ── Sentence splitting ───────────────────────────────────────────────────────

def split_sentences(tokens):
    """Return list of [start, end) spans, split on terminal punctuation."""
    spans = []
    start = 0
    for i, tok in enumerate(tokens):
        if tok.endswith(PUNCT_END):
            spans.append((start, i + 1))
            start = i + 1
    if start < len(tokens):
        spans.append((start, len(tokens)))
    return spans


def group_sentences(sentence_spans, num_groups=3):
    """Map N sentence spans into exactly `num_groups` groups.
    Each group is a (start, end) token span covering one or more sentences.
    """
    n = len(sentence_spans)
    if n == 0:
        return []

    if n <= num_groups:
        # Fewer sentences than groups: split the longest sentence(s) to fill
        groups = [(s, e) for s, e in sentence_spans]
        while len(groups) < num_groups:
            # Find the longest group and split it in half
            longest_idx = max(range(len(groups)), key=lambda i: groups[i][1] - groups[i][0])
            s, e = groups[longest_idx]
            mid = s + (e - s) // 2
            if mid == s:
                mid = s + 1
            if mid >= e:
                # Can't split further; duplicate the last group's range
                groups.append(groups[-1])
            else:
                groups[longest_idx] = (s, mid)
                groups.insert(longest_idx + 1, (mid, e))
        return groups[:num_groups]

    # More sentences than groups: merge adjacent sentences
    # Distribute as evenly as possible
    base = n // num_groups
    extra = n % num_groups
    groups = []
    idx = 0
    for g in range(num_groups):
        count = base + (1 if g < extra else 0)
        g_start = sentence_spans[idx][0]
        g_end = sentence_spans[idx + count - 1][1]
        groups.append((g_start, g_end))
        idx += count
    return groups


# ── Center word extraction ───────────────────────────────────────────────────

def find_center_word(tokens, group_spans):
    """Find a 1-2 token center_word that is a strong content word from the script.
    Prefer words that appear early and are not consumed by a critical phrase position.
    Returns (center_start, center_end) span and the phrase string.
    """
    candidates = []

    for length in (1, 2):
        for i in range(len(tokens) - length + 1):
            phrase = _span_phrase(tokens, i, i + length)
            cw = content_words(phrase)
            if not cw:
                continue

            norm_end = normalize_word(tokens[i + length - 1])
            sc = len(cw) * 20

            # Prefer content-dense single words
            if length == 1:
                sc += 10
            # Penalize stop-word starts
            if normalize_word(tokens[i]) in STOP_WORDS:
                sc -= 5
            # Penalize bad endings
            if norm_end in BAD_END_WORDS:
                sc -= 8
            # Prefer words that end on punctuation (natural break)
            if tokens[i + length - 1].endswith(PUNCT_END):
                sc += 3
            # Slight preference for earlier positions
            sc -= i * 0.5

            candidates.append((sc, i, i + length, phrase))

    if not candidates:
        # Ultimate fallback: first content-ish token
        return 0, 1, _span_phrase(tokens, 0, 1)

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, s, e, phrase = candidates[0]
    return s, e, phrase


# ── Phrase scoring for img/lbl splits ────────────────────────────────────────

def _phrase_score(tokens, s, e, is_label=False):
    """Score a phrase span. Higher is better."""
    phrase = _span_phrase(tokens, s, e)
    if not phrase:
        return -1000

    length = e - s
    cw = content_words(phrase)
    start_norm = normalize_word(tokens[s])
    end_norm = normalize_word(tokens[e - 1])

    sc = len(cw) * 10
    if not cw:
        sc -= 60

    if is_label:
        # Labels are displayed on-screen, keep them SHORT (2-4 tokens)
        pref_min, pref_max = 2, 4
    else:
        # Image phrases are only used for timing, can be longer
        pref_min, pref_max = 2, 10

    if length < pref_min:
        sc -= (pref_min - length) * 14
    if length > pref_max:
        # Steep penalty for labels exceeding max — they overflow on canvas
        penalty = 15 if is_label else 4
        sc -= (length - pref_max) * penalty

    if start_norm in STOP_WORDS:
        sc -= 3
    if end_norm in STOP_WORDS:
        sc -= 2
    if end_norm in BAD_END_WORDS:
        sc -= 4
    if tokens[e - 1].endswith(PUNCT_END):
        sc += 2

    # Penalize internal sentence breaks
    for tok in tokens[s:max(s, e - 1)]:
        if tok.endswith(PUNCT_END):
            sc -= 60

    return sc


def best_split(tokens, start, end, center_span=None):
    """Find the best split point to divide [start, end) into img_phrase + lbl_phrase.
    Skips any tokens consumed by center_word (center_span).
    Returns (img_start, img_end, lbl_start, lbl_end).
    """
    length = end - start
    if length < 2:
        # Too short to split meaningfully
        return start, end, start, end

    best_score = -9999
    best = None

    # Try every valid split point
    for split_at in range(start + 1, end):
        img_s, img_e = start, split_at
        lbl_s, lbl_e = split_at, end

        # Skip splits that would create empty halves after center_word removal
        img_len = img_e - img_s
        lbl_len = lbl_e - lbl_s

        if img_len < 1 or lbl_len < 1:
            continue

        sc_img = _phrase_score(tokens, img_s, img_e, is_label=False)
        sc_lbl = _phrase_score(tokens, lbl_s, lbl_e, is_label=True)

        # Prefer shorter labels (displayed on screen) — no balance bonus needed
        # Instead, bonus for label being <=4 words
        short_lbl_bonus = 10 if lbl_len <= 4 else 0
        total = sc_img + sc_lbl + short_lbl_bonus

        if total > best_score:
            best_score = total
            best = (img_s, img_e, lbl_s, lbl_e)

    if best is None:
        mid = start + length // 2
        return start, mid, mid, end

    return best


# ── Validation ───────────────────────────────────────────────────────────────

def validate_phrases(all_phrases):
    """Check all phrase rules. Returns list of error strings (empty = all good)."""
    errors = []

    for name, phrase in all_phrases:
        if not phrase or not phrase.strip():
            errors.append(f"{name}: EMPTY phrase")

    clean = [(name, clean_phrase_tuple(p)) for name, p in all_phrases]
    seen = {}
    for name, c in clean:
        if not c:
            continue
        key = c
        if key in seen:
            errors.append(f"DUPLICATE: {name} == {seen[key]} ('{' '.join(c)}')")
        seen[key] = name

    tuples = sorted(set(c for _, c in clean if c), key=lambda x: (len(x), x))
    for i in range(len(tuples)):
        for j in range(i + 1, len(tuples)):
            a, b = tuples[i], tuples[j]
            if is_prefix_tuple(a, b) or is_prefix_tuple(b, a):
                errors.append(f"PREFIX COLLISION: '{' '.join(a)}' ~ '{' '.join(b)}'")

    return errors


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_file = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_file.exists():
        print(f"Error: {prompt_file} not found.")
        return 1

    scene_data = json.loads(prompt_file.read_text(encoding="utf-8"))
    script = strip_scene_prefix(scene_data.get("prompt", ""))
    tokens = script.split()

    if len(tokens) < 1:
        print(f"Error: script too short for Layout 17 (need >= 1 tokens), got {len(tokens)}.")
        return 1

    # Priority allocation: use as many vertices as tokens allow.
    # Each vertex needs img_phrase + lbl_phrase (2 tokens min) plus center_word (1 token).
    # P1=3 vertices (needs 6+1=7), P2=2 vertices (needs 4+1=5), P3=1 vertex (needs 2+1=3).
    if len(tokens) >= 7:
        n_vertices = 3
    elif len(tokens) >= 5:
        n_vertices = 2
    else:
        n_vertices = 1

    print(f"Scene: {scene_id}")
    print(f"Script: {script}")
    print(f"Tokens: {len(tokens)}")
    print()

    # 1. Split into sentences
    sentence_spans = split_sentences(tokens)
    print(f"Sentences: {len(sentence_spans)}")
    for i, (s, e) in enumerate(sentence_spans):
        print(f"  S{i+1}: [{s},{e}) = \"{_span_phrase(tokens, s, e)}\"")
    print()

    # 2. Group sentences into n_vertices vertex groups
    groups = group_sentences(sentence_spans, num_groups=n_vertices)
    print(f"Groups ({n_vertices} vertices):")
    for i, (s, e) in enumerate(groups):
        print(f"  G{i+1}: [{s},{e}) = \"{_span_phrase(tokens, s, e)}\"")
    print()

    # 3. Extract center_word from the entire script
    cw_start, cw_end, center_word = find_center_word(tokens, groups)
    print(f"Center word: \"{center_word}\" [{cw_start},{cw_end})")
    print()

    # 4. Build phrases for each vertex group
    #    Each group → remove center_word tokens if they fall inside → split into img + lbl
    all_vertex_ids = ["top", "bottom_right", "bottom_left"]
    vertex_ids = all_vertex_ids[:n_vertices]
    vertices = []

    for vid, (g_start, g_end) in zip(vertex_ids, groups):
        # Check if center_word overlaps this group
        if cw_start >= g_start and cw_end <= g_end:
            # Center word is inside this group — build phrases from the remaining tokens
            # Split into: before-center + after-center
            before_tokens = list(range(g_start, cw_start))
            after_tokens = list(range(cw_end, g_end))
            remaining = before_tokens + after_tokens

            if len(remaining) < 2:
                # Not enough tokens after removing center word; use full group
                img_s, img_e, lbl_s, lbl_e = best_split(tokens, g_start, g_end)
            else:
                # Split the remaining tokens into two contiguous halves
                # Find the best contiguous split from the remaining range
                if before_tokens and after_tokens:
                    # Center word is in the middle — use before as img, after as lbl
                    img_s, img_e = before_tokens[0], before_tokens[-1] + 1
                    lbl_s, lbl_e = after_tokens[0], after_tokens[-1] + 1
                elif before_tokens:
                    mid = len(before_tokens) // 2
                    img_s = before_tokens[0]
                    img_e = before_tokens[mid] + 1 if mid > 0 else before_tokens[0] + 1
                    lbl_s = img_e
                    lbl_e = before_tokens[-1] + 1
                else:
                    mid = len(after_tokens) // 2
                    img_s = after_tokens[0]
                    img_e = after_tokens[mid] + 1 if mid > 0 else after_tokens[0] + 1
                    lbl_s = img_e
                    lbl_e = after_tokens[-1] + 1
        else:
            # Center word is not in this group — split normally
            img_s, img_e, lbl_s, lbl_e = best_split(tokens, g_start, g_end)

        img_phrase = _span_phrase(tokens, img_s, img_e)
        lbl_phrase = _span_phrase(tokens, lbl_s, lbl_e)

        vertices.append({
            "vertex_id": vid,
            "img_phrase": img_phrase,
            "lbl_phrase": lbl_phrase,
        })

        print(f"  {vid}:")
        print(f"    img_phrase: \"{img_phrase}\" [{img_s},{img_e})")
        print(f"    lbl_phrase: \"{lbl_phrase}\" [{lbl_s},{lbl_e})")

    # Pad remaining vertices with empty entries so downstream always sees 3
    for vid in all_vertex_ids[n_vertices:]:
        vertices.append({
            "vertex_id": vid,
            "img_phrase": "",
            "lbl_phrase": "",
        })

    print()

    # 5. Validate all active phrases (center_word + populated vertices)
    all_phrases = [("center_word", center_word)]
    for v in vertices:
        if v["img_phrase"] or v["lbl_phrase"]:
            all_phrases.append((f"{v['vertex_id']}_img", v["img_phrase"]))
            all_phrases.append((f"{v['vertex_id']}_lbl", v["lbl_phrase"]))

    errors = validate_phrases(all_phrases)
    if errors:
        print("WARNING: Validation issues:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("OK: All 7 phrases pass validation (non-empty, unique, no prefix collisions)")

    # 6. Save output
    out = {
        "scene_id": scene_id,
        "center_word": center_word,
        "vertices": vertices,
        "script": script,
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{scene_id}_layout_17_step_1_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
