import json
import re
import sys
from pathlib import Path


# Layout 16 (Filmstrip) deterministic Step 1:
# - Build strip_title + strip_subtitle from script tokens
# - Build exactly 5 frames with img_phrase + cap_phrase (10 phrases)
# - No API calls; spans are deterministic and token-grounded.

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
    # contracted forms (apostrophe stripped by normalize_word)
    "youre", "dont", "cant", "wont", "isnt", "wasnt", "didnt", "hasnt",
    "havent", "shouldnt", "wouldnt", "couldnt", "theyre", "thats",
    "youve", "ive", "weve", "theyve", "arent", "doesnt", "hadnt", "werent",
    "im", "hed", "shed", "wed", "theyd", "youll", "hell", "shell",
    "well", "theyll",
    # extra glue words
    "very", "without",
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


def content_words(phrase: str, extra_stop=None):
    extra_stop = extra_stop or set()
    out = set()
    for raw in re.findall(r"[A-Za-z0-9']+", (phrase or "").lower()):
        w = normalize_word(raw)
        if not w or len(w) <= 1:
            continue
        if w in STOP_WORDS or w in extra_stop:
            continue
        out.add(w)
    return out


def clean_word(word: str) -> str:
    # Match the timings engine: strip non-alnum and lowercase.
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def clean_phrase_tuple(phrase: str):
    return tuple([clean_word(w) for w in (phrase or "").split() if clean_word(w)])


def is_prefix_tuple(a, b) -> bool:
    if not a or not b:
        return False
    if len(a) > len(b):
        return False
    return b[: len(a)] == a


def validate_phrases(parsed, extra_stop=None, expected_frames=5):
    errors = []
    frames = parsed.get("frames", [])
    active = [f for f in frames if f.get("img_phrase") or f.get("cap_phrase")]
    if len(active) < 1:
        errors.append(f"No active frames found")

    phrases = []
    labels = []

    strip_title = (parsed.get("strip_title") or "").strip()
    strip_subtitle = (parsed.get("strip_subtitle") or "").strip()

    if not strip_title:
        errors.append("strip_title is empty")
    else:
        phrases.append(strip_title)
        labels.append("strip_title")

    if not strip_subtitle:
        errors.append("strip_subtitle is empty")
    else:
        phrases.append(strip_subtitle)
        labels.append("strip_subtitle")

    for fr in frames:
        fid = fr.get("frame_id", "?")
        for key in ("img_phrase", "cap_phrase"):
            p = (fr.get(key) or "").strip()
            if not p:
                errors.append(f"{fid}.{key} is empty")
            else:
                phrases.append(p)
                labels.append(f"{fid}.{key}")

    norm_phr = []
    for p in phrases:
        p2 = re.sub(r"\s+", " ", p.strip().lower())
        norm_phr.append(p2)

    clean_tuples = [clean_phrase_tuple(p) for p in phrases]

    for i in range(len(phrases)):
        pi = norm_phr[i]
        cw_i = content_words(phrases[i], extra_stop=extra_stop)
        for j in range(i + 1, len(phrases)):
            pj = norm_phr[j]
            if pi == pj:
                errors.append(f"EXACT DUPLICATE: [{labels[i]}] == [{labels[j]}]")
                continue
            # Timing engine matches by exact word tuples. Prefix conflicts fire at the same transcript start.
            if is_prefix_tuple(clean_tuples[i], clean_tuples[j]) or is_prefix_tuple(clean_tuples[j], clean_tuples[i]):
                errors.append(f"PREFIX: [{labels[i]}] ~ [{labels[j]}]")
                continue
            cw_j = content_words(phrases[j], extra_stop=extra_stop)
            overlap = cw_i & cw_j
            if overlap:
                errors.append(f"CONTENT OVERLAP: [{labels[i]}] ~ [{labels[j]}] shared={sorted(overlap)[:6]}")
    return errors


def build_sentence_spans(tokens):
    spans = []
    s = 0
    for i, tok in enumerate(tokens):
        if tok.endswith(PUNCT_END):
            spans.append([s, i + 1])
            s = i + 1
    if s < len(tokens):
        spans.append([s, len(tokens)])
    if not spans:
        spans = [[0, len(tokens)]]
    return spans


def pick_title_span(tokens):
    # Must start at the beginning. Choose 3-5 words.
    best = [0, min(3, len(tokens))]
    best_sc = -10**9
    for end in range(3, min(5, len(tokens)) + 1):
        phrase = " ".join(tokens[0:end]).strip()
        cw = content_words(phrase)
        if not cw:
            continue
        end_norm = normalize_word(tokens[end - 1])
        sc = len(cw) * 5
        if tokens[end - 1].endswith(PUNCT_END):
            sc += 2
        if end_norm in STOP_WORDS:
            sc -= 2
        if end_norm in BAD_END_WORDS and end < len(tokens):
            sc -= 3
        if sc > best_sc:
            best_sc = sc
            best = [0, end]
    return best


def pick_subtitle_span(tokens, min_len=4, max_len=7, min_start=0):
    n = len(tokens)
    candidates = []
    for k in range(min_len, min(max_len, n) + 1):
        s = n - k
        if s < min_start:
            continue
        phrase = " ".join(tokens[s:n]).strip()
        cw = content_words(phrase)
        if not cw:
            continue
        s_norm = normalize_word(tokens[s])
        e_norm = normalize_word(tokens[n - 1])
        punct = 1 if tokens[n - 1].endswith(PUNCT_END) else 0
        start_bad = 1 if s_norm in STOP_WORDS else 0
        end_bad = 1 if e_norm in STOP_WORDS else 0
        # Primary goal: keep subtitle short to preserve middle tokens.
        sort_key = (k, start_bad, end_bad, -punct, -len(cw))
        candidates.append((sort_key, [s, n]))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # Fallback: minimum-length window even if content is weak.
    s = max(min_start, n - min_len)
    if s >= n:
        return [n, n]
    return [s, n]


def balanced_sizes(total, parts, min_each):
    sizes = [total // parts] * parts
    for i in range(total % parts):
        sizes[i] += 1
    # Ensure minimum size by borrowing from largest.
    for _ in range(1000):
        small = [i for i, s in enumerate(sizes) if s < min_each]
        if not small:
            break
        i = small[0]
        j = max(range(parts), key=lambda idx: sizes[idx])
        if sizes[j] <= min_each:
            break
        sizes[i] += 1
        sizes[j] -= 1
    return sizes


def _span_phrase(tokens, s, e):
    return " ".join(tokens[s:e]).strip()


def _phrase_score(tokens, s, e, phrase_index, extra_stop):
    phrase = _span_phrase(tokens, s, e)
    cw = content_words(phrase, extra_stop=extra_stop)
    if not phrase:
        return None

    length = e - s
    start_norm = normalize_word(tokens[s])
    end_norm = normalize_word(tokens[e - 1])
    if not cw:
        # Allow stop-word-only phrases when the script is short, but penalize heavily.
        sc = -80.0 - (15.0 if length == 1 else 0.0)
    else:
        sc = len(cw) * 10

    if phrase_index % 2 == 0:
        # Image phrase: prefer at least 2 tokens.
        if length < 2:
            sc -= 20
            if length == 1 and tokens[e - 1].endswith(PUNCT_END):
                sc += 12
        sc += min(6, length)
    else:
        # Caption phrase: prefer short, but avoid 1-token stopword-ish captions.
        if length == 1:
            sc -= 4
        if length > 4:
            sc -= (length - 4) * 6

        # Avoid captions that stitch across a sentence boundary (e.g. "loser. You").
        if length >= 2 and tokens[e - 2].endswith(PUNCT_END) and end_norm in STOP_WORDS:
            sc -= 50

    if start_norm in STOP_WORDS:
        sc -= 3
    if end_norm in STOP_WORDS:
        sc -= 2
    if end_norm in BAD_END_WORDS:
        sc -= 4
    if tokens[e - 1].endswith(PUNCT_END):
        sc += 2

    # Strongly discourage phrases that contain a sentence terminator internally.
    # They look nonsensical on screen and can break timing expectations.
    internal_breaks = 0
    for tok in tokens[s : max(s, e - 1)]:
        if tok.endswith(PUNCT_END):
            internal_breaks += 1
    if internal_breaks:
        sc -= 60 * internal_breaks

    return sc


def segment_middle_into_phrases(tokens, mid_s, mid_e, extra_stop, n_frames=5):
    """
    Segment the middle span into exactly n_frames*2 phrases (img/cap alternating) with a
    deterministic DP. This avoids creating junk one-word phrases like "over".
    """
    M = mid_e - mid_s
    n_phrases = n_frames * 2
    if M < n_phrases:
        return None

    # Allow 1-token phrases (short sentences), but score prefers >=2.
    min_lens = [1 for _ in range(n_phrases)]
    max_lens = [6 if i % 2 == 0 else 4 for i in range(n_phrases)]

    # DP[pos][k] = best score reaching pos with k phrases chosen.
    dp = [[None for _ in range(n_phrases + 1)] for _ in range(M + 1)]
    back = [[None for _ in range(n_phrases + 1)] for _ in range(M + 1)]
    dp[0][0] = 0.0

    for pos in range(M + 1):
        for k in range(n_phrases):
            if dp[pos][k] is None:
                continue
            remaining = M - pos
            # Feasibility bounds.
            min_need = sum(min_lens[k:])
            max_can = sum(max_lens[k:])
            if remaining < min_need or remaining > max_can:
                continue

            min_len = min_lens[k]
            max_len = max_lens[k]
            for ln in range(min_len, max_len + 1):
                nxt = pos + ln
                if nxt > M:
                    break
                rem2 = M - nxt
                min_need2 = sum(min_lens[k + 1 :])
                max_can2 = sum(max_lens[k + 1 :])
                if rem2 < min_need2 or rem2 > max_can2:
                    continue

                s = mid_s + pos
                e = mid_s + nxt
                sc = _phrase_score(tokens, s, e, k, extra_stop=extra_stop)
                if sc is None:
                    continue
                val = dp[pos][k] + sc
                if dp[nxt][k + 1] is None or val > dp[nxt][k + 1]:
                    dp[nxt][k + 1] = val
                    back[nxt][k + 1] = ln

    if dp[M][n_phrases] is None:
        return None

    # Reconstruct spans.
    spans = []
    pos = M
    k = n_phrases
    while k > 0:
        ln = back[pos][k]
        if ln is None:
            return None
        spans.append([mid_s + (pos - ln), mid_s + pos])
        pos -= ln
        k -= 1
    spans.reverse()
    return spans


def repair_prefix_conflicts(tokens, spans, extra_stop):
    """
    Repair prefix conflicts by shifting boundaries between adjacent spans.
    Prefer prepending a token (changes start words) over appending.
    """
    n_spans = len(spans)
    min_lens = [1 for _ in range(n_spans)]

    def span_ok(i):
        s, e = spans[i]
        if (e - s) < min_lens[i]:
            return False
        phrase = _span_phrase(tokens, s, e)
        return bool(content_words(phrase, extra_stop=extra_stop))

    for _ in range(200):
        phrases = [_span_phrase(tokens, s, e) for s, e in spans]
        tuples = [clean_phrase_tuple(p) for p in phrases]
        conflict = None
        for i in range(n_spans):
            for j in range(i + 1, n_spans):
                if is_prefix_tuple(tuples[i], tuples[j]) or is_prefix_tuple(tuples[j], tuples[i]):
                    conflict = (i, j)
                    break
            if conflict:
                break
        if not conflict:
            return spans

        i, j = conflict
        # Move the start of the shorter phrase left if possible.
        if len(tuples[i]) <= len(tuples[j]):
            short = i
        else:
            short = j

        fixed = False
        if short > 0:
            # Take last token from previous span.
            if spans[short - 1][1] - spans[short - 1][0] > min_lens[short - 1]:
                spans[short - 1][1] -= 1
                spans[short][0] -= 1
                if span_ok(short - 1) and span_ok(short):
                    fixed = True
                else:
                    spans[short][0] += 1
                    spans[short - 1][1] += 1

        if not fixed and short < n_spans - 1:
            # Take first token from next span.
            if spans[short + 1][1] - spans[short + 1][0] > min_lens[short + 1]:
                spans[short][1] += 1
                spans[short + 1][0] += 1
                if span_ok(short) and span_ok(short + 1):
                    fixed = True
                else:
                    spans[short + 1][0] -= 1
                    spans[short][1] -= 1

        if not fixed:
            return spans

    return spans


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
        print(f"Error: script too short for Layout 16 (need >=1 tokens), got {len(tokens)}.")
        return 1

    # Priority allocation: scale frames down based on available tokens.
    # Each frame needs img_phrase (>=1) + cap_phrase (>=1) = 2 tokens minimum.
    # Plus title (>=1) + subtitle (>=1) = 2 overhead = need at least 2*n_frames + 2 tokens.
    # P1=5 frames (needs 17+), P2=4 frames, P3=3 frames, P4=2 frames, P5=1 frame.
    if len(tokens) >= 17:
        n_frames = 5
    elif len(tokens) >= 13:
        n_frames = 4
    elif len(tokens) >= 9:
        n_frames = 3
    elif len(tokens) >= 6:
        n_frames = 2
    else:
        n_frames = 1

    # Dynamic stop words for overlap validation: if a content word repeats in the script,
    # it cannot be globally unique across phrases. Treat repeats as overlap-ignorable.
    counts = {}
    for t in tokens:
        w = normalize_word(t)
        if not w or w in STOP_WORDS:
            continue
        counts[w] = counts.get(w, 0) + 1
    dynamic_stop = {w for w, c in counts.items() if c >= 2}

    title_span = pick_title_span(tokens)
    # min_middle = n_frames * 2 phrases, each at least 1 token
    min_middle = n_frames * 2
    # For subtitle: scale length based on available tokens
    sub_min = min(4, max(1, len(tokens) // 6))
    sub_max = min(7, max(sub_min, len(tokens) // 4))
    subtitle_span = pick_subtitle_span(tokens, min_len=sub_min, max_len=sub_max,
                                       min_start=title_span[1] + min_middle)
    if subtitle_span[0] >= len(tokens) or not " ".join(tokens[subtitle_span[0] : subtitle_span[1]]).strip():
        subtitle_span = pick_subtitle_span(tokens, min_len=sub_min, max_len=sub_max,
                                           min_start=title_span[1] + min_middle)
    if subtitle_span[0] - title_span[1] < min_middle:
        # Last resort: shorten subtitle and title to make room for middle
        title_span = [0, min(3, len(tokens) - min_middle - sub_min)]
        if title_span[1] < 1:
            title_span = [0, 1]
        sub_start = max(title_span[1] + min_middle, len(tokens) - sub_min)
        subtitle_span = [sub_start, len(tokens)]

    mid_s, mid_e = title_span[1], subtitle_span[0]
    middle_len = mid_e - mid_s
    if middle_len < min_middle:
        # If still not enough, collapse subtitle to end and use everything else as middle
        title_span = [0, 1]
        subtitle_span = [len(tokens) - 1, len(tokens)]
        mid_s, mid_e = 1, len(tokens) - 1
        middle_len = mid_e - mid_s

    if middle_len < min_middle:
        print(f"Error: Not enough middle tokens for {n_frames} frames in {scene_id}.")
        return 1

    spans = segment_middle_into_phrases(tokens, mid_s, mid_e, extra_stop=dynamic_stop, n_frames=n_frames)
    if spans is None:
        # Fallback: equal chunks
        chunk = middle_len // (n_frames * 2)
        r = middle_len % (n_frames * 2)
        spans = []
        pos = mid_s
        for i in range(n_frames * 2):
            size = max(1, chunk + (1 if i < r else 0))
            spans.append([pos, pos + size])
            pos += size
    spans = repair_prefix_conflicts(tokens, spans, extra_stop=dynamic_stop)

    frames = []
    for i in range(n_frames):
        img_s, img_e = spans[i * 2]
        cap_s, cap_e = spans[i * 2 + 1]
        frames.append(
            {
                "frame_id": f"frame_{i+1}",
                "img_phrase": _span_phrase(tokens, img_s, img_e),
                "cap_phrase": _span_phrase(tokens, cap_s, cap_e),
            }
        )
    # Pad remaining frames with empty entries so downstream always sees 5
    for i in range(n_frames, 5):
        frames.append({
            "frame_id": f"frame_{i+1}",
            "img_phrase": "",
            "cap_phrase": "",
        })

    out = {
        "strip_title": " ".join(tokens[title_span[0]:title_span[1]]).strip(),
        "strip_subtitle": " ".join(tokens[subtitle_span[0]:subtitle_span[1]]).strip(),
        "frames": frames,
    }

    errors = validate_phrases(out, extra_stop=dynamic_stop)
    if errors:
        print(f"Validation warnings for {scene_id} (continuing, deterministic output):")
        for err in errors[:30]:
            print(f"  - {err}")

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{scene_id}_layout_16_step_1_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
