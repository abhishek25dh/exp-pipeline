"""
Layout 2 Step 1 — Deterministic Tokenization + Anchor Candidates
=================================================================
Layout 2: one center text anchor (large, fires at script midpoint) + scattered images around it.

FULLY DETERMINISTIC — no AI calls.
Outputs anchor candidates (verbatim spans) for Step 2's AI selector.
"""

import json
import re
import sys
from pathlib import Path

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "from", "by", "it", "its", "is", "was", "are", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can",
    "not", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "up", "out", "as", "so", "if", "then", "than",
    "also", "just", "about", "into", "over", "after", "before", "now",
    "when", "what", "where", "who", "how", "very", "without",
}

MAX_CANDIDATES = 6
PREFERRED_LENGTHS = {2, 3}


def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def normalize_token(t):
    return re.sub(r"[^a-z0-9']", "", (t or "").lower())


def ends_sentence(tok):
    return bool(tok) and tok.rstrip()[-1] in ".!?"


def content_words(tokens, s, e):
    return [normalize_token(t) for t in tokens[s:e]
            if normalize_token(t) and normalize_token(t) not in STOP_WORDS]


def score_candidate(tokens, s, e, n):
    cw = content_words(tokens, s, e)
    length = e - s
    length_bonus = 2 if length in PREFERRED_LENGTHS else (1 if length == 1 else 0)
    punct_bonus = 1 if ends_sentence(tokens[e - 1]) else 0
    center_dist = abs((s + e) / 2.0 - n / 2.0)
    center_bonus = max(0, 2 - int(center_dist / max(1, n / 4)))
    return len(cw) * 4 + length_bonus + punct_bonus + center_bonus


def build_candidates(tokens):
    """Build anchor candidates. Sentence-ending spans are preferred (Rule 6 compliance)."""
    n = len(tokens)
    seen = set()
    cands = []
    for s in range(n):
        for e in range(s + 1, min(s + 5, n + 1)):
            phrase = " ".join(tokens[s:e])
            key = phrase.lower()
            if key in seen:
                continue
            if not content_words(tokens, s, e):
                continue
            seen.add(key)
            cands.append({
                "id": f"C{len(cands) + 1}",
                "span": [s, e],
                "phrase": phrase,
                "score": score_candidate(tokens, s, e, n),
                "ends_at_sentence": ends_sentence(tokens[e - 1]),
            })

    # Sort: sentence-ending first (Rule 6 preference), then by score
    cands.sort(key=lambda c: (-int(c["ends_at_sentence"]), -c["score"]))
    out, used_spans = [], set()
    for c in cands:
        key = (c["span"][0], c["span"][1])
        if key in used_spans:
            continue
        used_spans.add(key)
        out.append(c)
        if len(out) >= MAX_CANDIDATES:
            break
    for i, c in enumerate(out):
        c["id"] = f"C{i + 1}"
    return out


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text = strip_scene_prefix(prompt_data.get("prompt", ""))
    tokens = scene_text.split()

    if not tokens:
        print(f"Error: empty scene text for {scene_id}.")
        return 1

    candidates = build_candidates(tokens)
    if not candidates:
        print(f"Error: no anchor candidates for {scene_id}.")
        return 1

    print(f"  Tokens: {len(tokens)}  |  Candidates: {len(candidates)}")
    for c in candidates:
        print(f"    {c['id']}  score={c['score']}  '{c['phrase']}'  span={c['span']}")

    out = {
        "scene_id": scene_id,
        "scene_text": scene_text,
        "tokens": tokens,
        "candidates": candidates,
        "default_candidate_id": candidates[0]["id"],
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_2_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
