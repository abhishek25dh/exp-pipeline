import json
import re
import sys
from pathlib import Path

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "from", "by", "it", "its", "is", "was", "are", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "not", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "up", "out", "as", "so", "if", "then", "than",
    "also", "just", "about", "into", "over", "after", "before", "now",
    "when", "what", "where", "who", "how",
    "very",
    "without",
    # Common contractions that tend to create awkward anchor phrases.
    "you're", "we're", "they're", "i'm", "it's", "that's", "there's", "he's", "she's",
}

BAD_END_TOKENS = {"you're", "we're", "they're", "i'm"}
PUNCT_END = (".", "!", "?")
OK_START_STOP_WORDS = {"you", "your"}


def normalize_token(token: str) -> str:
    return re.sub(r"^[^\w']+|[^\w']+$", "", (token or "").lower())


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def span_phrase(tokens, span):
    s, e = span
    return " ".join(tokens[s:e]).strip()


def span_score(tokens, s, e):
    words = [normalize_token(t) for t in tokens[s:e]]
    content = [w for w in words if w and w not in STOP_WORDS]
    if not content:
        return -999
    length = e - s
    length_bonus = {2: 3, 3: 2, 4: 1, 1: 1}.get(length, 0)

    end_tok = tokens[e - 1] if e - 1 < len(tokens) else ""
    end_norm = normalize_token(end_tok)
    punct_bonus = 0
    if end_tok.endswith((".", "!", "?")):
        punct_bonus = 2
    elif end_tok.endswith(","):
        punct_bonus = 1

    dangling_penalty = 0
    if end_norm in BAD_END_TOKENS and e < len(tokens):
        dangling_penalty = 3

    return (len(content) * 4) + length_bonus + punct_bonus - dangling_penalty


def content_words_for_span(tokens, span):
    s, e = span
    out = set()
    for t in tokens[s:e]:
        w = normalize_token(t)
        if w and w not in STOP_WORDS:
            out.add(w)
    return out


def build_sentence_spans(tokens):
    n = len(tokens)
    spans = []
    s = 0
    for i, tok in enumerate(tokens):
        if tok.endswith(PUNCT_END):
            spans.append([s, i + 1])
            s = i + 1
    if s < n:
        spans.append([s, n])
    if not spans:
        spans = [[0, n]]
    return spans


def spans_in_region(sentence_spans, region_start, region_end):
    out = []
    for s, e in sentence_spans:
        if s >= region_start and e <= region_end and s < e:
            out.append([s, e])
    return out


def build_anchor_candidates(tokens, sentence_spans, region_start, region_end, prefer_start=None):
    candidates = []
    sents = spans_in_region(sentence_spans, region_start, region_end)
    if not sents:
        sents = [[region_start, region_end]] if region_end > region_start else []

    # 1) Single-sentence candidates (full sentence if small enough + sliding windows).
    for ss, se in sents:
        ln = se - ss
        if 3 <= ln <= 6:
            candidates.append([ss, se])
        for start in range(ss, se):
            for wlen in (4, 3, 5, 2, 6):
                end = start + wlen
                if end > se:
                    continue
                if end - start < 2:
                    continue
                candidates.append([start, end])

    # 2) Merge consecutive short sentences for better readability (e.g. "You're resting. You're recharging.")
    for i in range(len(sents)):
        cur_s = sents[i][0]
        cur_e = sents[i][1]
        for j in range(i + 1, min(i + 4, len(sents))):
            nxt_e = sents[j][1]
            if (nxt_e - cur_s) > 6:
                break
            cur_e = nxt_e
            if (cur_e - cur_s) >= 3:
                candidates.append([cur_s, cur_e])

    # De-dupe while preserving order.
    seen = set()
    uniq = []
    for s, e in candidates:
        if s >= e:
            continue
        key = (int(s), int(e))
        if key in seen:
            continue
        seen.add(key)
        uniq.append([int(s), int(e)])
    return uniq


def best_anchor_in_region(
    tokens,
    sentence_spans,
    region_start,
    region_end,
    banned_words=None,
    prefer_start=None,
    require_sentence_start=False,
):
    banned_words = banned_words or set()
    n = len(tokens)
    region_start = max(0, region_start)
    region_end = min(n, region_end)
    best = None
    best_key = None

    candidates = build_anchor_candidates(tokens, sentence_spans, region_start, region_end, prefer_start=prefer_start)
    if not candidates and region_start < region_end:
        candidates = [[region_start, min(region_end, region_start + 3)]]

    sentence_starts = {s for s, _ in sentence_spans}
    has_start_candidate = any(s in sentence_starts for s, _ in candidates)

    for s, e in candidates:
        if require_sentence_start and has_start_candidate and (s not in sentence_starts):
            continue

        words = content_words_for_span(tokens, [s, e])
        if not words:
            continue
        if banned_words and (words & banned_words):
            continue

        sc = span_score(tokens, s, e)

        # Readability bonuses.
        if prefer_start is not None and s == int(prefer_start):
            start_norm = normalize_token(tokens[s])
            sc += 4 if start_norm and start_norm not in STOP_WORDS else 1
        if require_sentence_start or prefer_start is not None:
            if s in sentence_starts:
                sc += 2
            else:
                sc -= 3
        if tokens[e - 1].endswith(PUNCT_END):
            sc += 2
        if normalize_token(tokens[s]) in STOP_WORDS and normalize_token(tokens[s]) not in OK_START_STOP_WORDS:
            sc -= 2
        if normalize_token(tokens[e - 1]) in STOP_WORDS:
            sc -= 2

        # Sort key: higher score, prefer mid-length, then earlier span.
        key = (sc, -abs((e - s) - 4), -s)
        if best_key is None or key > best_key:
            best_key = key
            best = [s, e]

    if best is None:
        # Fallback: shortest safe window in region.
        if region_start < region_end:
            j = min(region_start + 2, region_end)
            best = [region_start, j]
        else:
            best = [0, min(1, n)]
    return best


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"
    prompt_path = Path(f"assets/scene_prompts/{scene_id}_prompt.json")
    if not prompt_path.exists():
        print(f"Error: {prompt_path} not found.")
        return 1

    scene_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    script = strip_scene_prefix(scene_data.get("prompt", ""))
    tokens = script.split()
    if len(tokens) < 1:
        print(f"Error: script too short for layout_1 anchors ({len(tokens)} tokens, need >=1).")
        return 1

    mid = len(tokens) // 2
    sentence_spans = build_sentence_spans(tokens)

    # Prefer splitting between sentences so anchors don't stitch two sentences together.
    split_end = None
    for s, e in sentence_spans:
        if s <= mid < e:
            split_end = e
            break

    if split_end is None or split_end >= (len(tokens) - 2):
        left_region_end = max(2, mid + 1)
        right_region_start = min(mid, len(tokens) - 1)
    else:
        left_region_end = split_end
        right_region_start = split_end

    left_span = best_anchor_in_region(tokens, sentence_spans, 0, left_region_end)

    # If we would leave a leading "You" orphan at the start of a sentence, absorb it into the anchor.
    sentence_starts = {s for s, _ in sentence_spans}
    if left_span[0] > 0:
        prev = left_span[0] - 1
        if prev in sentence_starts and normalize_token(tokens[prev]) == "you":
            left_span[0] = prev
    left_words = content_words_for_span(tokens, left_span)
    right_span = best_anchor_in_region(
        tokens,
        sentence_spans,
        right_region_start,
        len(tokens),
        banned_words=left_words,
        prefer_start=right_region_start,
        require_sentence_start=False,
    )

    # Ensure right span differs from left span.
    if left_span == right_span:
        alt_start = min(right_span[1], len(tokens) - 1)
        right_span = [alt_start, min(len(tokens), alt_start + 2)]

    # If sentence splitting failed (e.g. no punctuation), keep anchors from drifting too far apart.
    if right_span[0] < left_span[1]:
        right_span[0] = left_span[1]

    text_1 = span_phrase(tokens, left_span)
    text_2 = span_phrase(tokens, right_span)

    out = {
        "scene_id": scene_id,
        "script_tokens": tokens,
        "anchor_spans": {
            "text_1": left_span,
            "text_2": right_span,
        },
        "main_texts": [
            {
                "element_id": "text_1",
                "type": "text_highlighted",
                "text_content": text_1,
                "column": "left",
                "reason": "Deterministic left anchor from first narrative half.",
            },
            {
                "element_id": "text_2",
                "type": "text_red",
                "text_content": text_2,
                "column": "right",
                "reason": "Deterministic right anchor from second narrative half.",
            },
        ],
    }

    out_path = Path(f"assets/tmp/{scene_id}_layout_1_step_1_tmp.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_path}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
