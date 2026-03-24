import json
import math
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
    "also", "just", "about", "into", "over", "after", "before",
    "no", "now", "when", "what", "where", "who", "how", "never",
    "always", "ever", "still", "even", "yet", "own", "maybe", "like",
    # contracted forms (apostrophe stripped by normalize_word)
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
    return tuple([clean_word(w) for w in (phrase or "").split() if clean_word(w)])


def is_prefix_tuple(a, b) -> bool:
    if not a or not b:
        return False
    if len(a) > len(b):
        return False
    return b[: len(a)] == a


def content_words(phrase: str):
    out = set()
    for raw in re.findall(r"[A-Za-z0-9']+", (phrase or "").lower()):
        w = normalize_word(raw)
        if not w or len(w) <= 1:
            continue
        if w in STOP_WORDS:
            continue
        out.add(w)
    return out


def _span_phrase(tokens, s, e):
    return " ".join(tokens[s:e]).strip()


def _phrase_score(tokens, s, e, idx):
    phrase = _span_phrase(tokens, s, e)
    if not phrase:
        return None

    length = e - s
    cw = content_words(phrase)
    start_norm = normalize_word(tokens[s])
    end_norm = normalize_word(tokens[e - 1])

    sc = len(cw) * 10
    if not cw:
        sc -= 60

    # Prefer compact phrases, but allow longer when needed.
    if idx % 2 == 0:
        pref_min, pref_max = 2, 4  # image phrase
        if length < pref_min:
            sc -= (pref_min - length) * 14
        if length > pref_max:
            sc -= (length - pref_max) * 6
    else:
        pref_min, pref_max = 2, 6  # caption phrase
        if length < pref_min:
            sc -= (pref_min - length) * 10
        if length > pref_max:
            sc -= (length - pref_max) * 4

    if start_norm in STOP_WORDS:
        sc -= 3
    if end_norm in STOP_WORDS:
        sc -= 2
    if end_norm in BAD_END_WORDS:
        sc -= 4
    if tokens[e - 1].endswith(PUNCT_END):
        sc += 2

    # Penalize internal sentence breaks.
    internal_breaks = 0
    for tok in tokens[s : max(s, e - 1)]:
        if tok.endswith(PUNCT_END):
            internal_breaks += 1
    if internal_breaks:
        sc -= 60 * internal_breaks

    return sc


def build_min_lens(total_tokens):
    min_lens = [2 for _ in range(8)]
    min_total = sum(min_lens)
    if total_tokens >= min_total:
        return min_lens

    deficit = min_total - total_tokens
    # Reduce mins (caps first), but never below 1.
    order = [1, 3, 5, 7, 0, 2, 4, 6]
    i = 0
    while deficit > 0 and i < 1000:
        for idx in order:
            if deficit <= 0:
                break
            if min_lens[idx] > 1:
                min_lens[idx] -= 1
                deficit -= 1
        i += 1
    return min_lens


def build_max_lens(total_tokens, min_lens):
    n = len(min_lens)
    avg = int(math.ceil(total_tokens / max(n, 1)))
    base_img = max(6, avg + 2)
    base_cap = max(8, avg + 3)
    max_lens = [
        (base_img if i % 2 == 0 else base_cap) for i in range(n)
    ]
    for i in range(n):
        if max_lens[i] < min_lens[i]:
            max_lens[i] = min_lens[i]

    while sum(max_lens) < total_tokens:
        for i in range(n):
            max_lens[i] += 1
            if sum(max_lens) >= total_tokens:
                break
    return max_lens


def segment_into_phrases(tokens, start, end, min_lens, max_lens):
    total = end - start
    n = len(min_lens)
    dp = [[None for _ in range(n + 1)] for _ in range(total + 1)]
    back = [[None for _ in range(n + 1)] for _ in range(total + 1)]
    dp[0][0] = 0.0

    min_suffix = [0] * (n + 1)
    max_suffix = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        min_suffix[i] = min_suffix[i + 1] + min_lens[i]
        max_suffix[i] = max_suffix[i + 1] + max_lens[i]

    for pos in range(total + 1):
        for k in range(n):
            if dp[pos][k] is None:
                continue
            remaining = total - pos
            if remaining < min_suffix[k] or remaining > max_suffix[k]:
                continue
            for ln in range(min_lens[k], max_lens[k] + 1):
                nxt = pos + ln
                if nxt > total:
                    break
                rem2 = total - nxt
                if rem2 < min_suffix[k + 1] or rem2 > max_suffix[k + 1]:
                    continue
                s = start + pos
                e = start + nxt
                sc = _phrase_score(tokens, s, e, k)
                if sc is None:
                    continue
                val = dp[pos][k] + sc
                if dp[nxt][k + 1] is None or val > dp[nxt][k + 1]:
                    dp[nxt][k + 1] = val
                    back[nxt][k + 1] = ln

    if dp[total][n] is None:
        return None

    spans = []
    pos = total
    k = n
    while k > 0:
        ln = back[pos][k]
        if ln is None:
            return None
        spans.append([start + (pos - ln), start + pos])
        pos -= ln
        k -= 1
    spans.reverse()
    return spans


def build_title_candidates(tokens, min_title, max_title, min_remaining):
    candidates = []
    for end in range(min_title, min(max_title, len(tokens) - min_remaining) + 1):
        phrase = " ".join(tokens[0:end]).strip()
        if not phrase:
            continue
        cw = content_words(phrase)
        if not cw:
            continue
        end_norm = normalize_word(tokens[end - 1])
        sc = len(cw) * 6
        if tokens[end - 1].endswith(PUNCT_END):
            sc += 2
        if end_norm in STOP_WORDS:
            sc -= 2
        if end_norm in BAD_END_WORDS and end < len(tokens):
            sc -= 3
        candidates.append((sc, [0, end]))

    if not candidates:
        max_end = max(1, min(max_title, len(tokens) - min_remaining))
        return [[0, max_end]]

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in candidates]


def validate_phrases(tokens, title_phrase, spans):
    errors = []
    phrases = [title_phrase]
    for s, e in spans:
        phrases.append(_span_phrase(tokens, s, e))

    for i, p in enumerate(phrases):
        if not p:
            errors.append(f"phrase_{i} is empty")

    clean = [clean_phrase_tuple(p) for p in phrases]
    seen = set()
    for c in clean:
        if not c:
            continue
        if c in seen:
            errors.append(f"EXACT DUPLICATE: {' '.join(c)}")
        seen.add(c)

    uniq = sorted(set([c for c in clean if c]), key=lambda x: (len(x), x))
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            a, b = uniq[i], uniq[j]
            if is_prefix_tuple(a, b) or is_prefix_tuple(b, a):
                errors.append(f"PREFIX: {' '.join(a)} ~ {' '.join(b)}")

    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    tiled = []
    for p in phrases:
        tiled.extend([clean_word(w) for w in p.split() if clean_word(w)])
    if tiled != script_clean:
        errors.append("TILING_MISMATCH")

    return errors


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
        print(f"Error: script too short for Layout 18 (need >=1 tokens), got {len(tokens)}.")
        return 1

    # Priority allocation: use as many polaroids as tokens allow.
    # Each polaroid needs img_phrase + cap_phrase (2 tokens min) plus title (1 token min).
    # P1=4 polaroids (needs 9+), P2=3 polaroids (needs 7), P3=2 polaroids (needs 5), P4=1 (needs 3).
    if len(tokens) >= 9:
        n_polaroids = 4
    elif len(tokens) >= 7:
        n_polaroids = 3
    elif len(tokens) >= 5:
        n_polaroids = 2
    else:
        n_polaroids = 1

    if len(tokens) >= 19:
        min_title = 3
    elif len(tokens) >= 10:
        min_title = 2
    else:
        min_title = 1
    max_title = 6

    phrase_count_18 = n_polaroids * 2  # img + cap per polaroid
    min_lens_base = build_min_lens(len(tokens) - min_title)[:phrase_count_18]
    # Rebuild min_lens for actual phrase count
    min_lens_base = [2 for _ in range(phrase_count_18)]
    deficit = sum(min_lens_base) - (len(tokens) - min_title)
    if deficit > 0:
        order_18 = [i for i in range(phrase_count_18) if i % 2 == 1] + [i for i in range(phrase_count_18) if i % 2 == 0]
        it = 0
        while deficit > 0 and it < 1000:
            for idx in order_18:
                if deficit <= 0:
                    break
                if min_lens_base[idx] > 1:
                    min_lens_base[idx] -= 1
                    deficit -= 1
            it += 1
    min_remaining = sum(min_lens_base)

    title_candidates = build_title_candidates(tokens, min_title, max_title, min_remaining)

    best_spans = None
    best_title = None
    best_errors = None

    for title_span in title_candidates:
        mid_start = title_span[1]
        remaining = len(tokens) - mid_start
        if remaining <= 0:
            continue

        min_lens = [2 for _ in range(phrase_count_18)]
        deficit2 = sum(min_lens) - remaining
        if deficit2 > 0:
            order_2 = [i for i in range(phrase_count_18) if i % 2 == 1] + [i for i in range(phrase_count_18) if i % 2 == 0]
            it2 = 0
            while deficit2 > 0 and it2 < 1000:
                for idx in order_2:
                    if deficit2 <= 0:
                        break
                    if min_lens[idx] > 1:
                        min_lens[idx] -= 1
                        deficit2 -= 1
                it2 += 1
        max_lens = build_max_lens(remaining, min_lens)
        if sum(min_lens) > remaining or sum(max_lens) < remaining:
            continue

        spans = segment_into_phrases(tokens, mid_start, len(tokens), min_lens, max_lens)
        if spans is None:
            continue

        title_phrase = _span_phrase(tokens, title_span[0], title_span[1])
        errors = validate_phrases(tokens, title_phrase, spans)
        if not errors:
            best_spans = spans
            best_title = title_span
            best_errors = []
            break
        if best_spans is None or (best_errors is not None and len(errors) < len(best_errors)):
            best_spans = spans
            best_title = title_span
            best_errors = errors

    if best_spans is None or best_title is None:
        print(f"Error: Unable to build phrases for {scene_id}.")
        return 1

    title_phrase = _span_phrase(tokens, best_title[0], best_title[1])
    if best_errors:
        print(f"Validation warnings for {scene_id}:")
        for err in best_errors[:20]:
            print(f"  - {err}")

    pid_order = ["tl", "tr", "bl", "br"]
    polaroids = []
    span_map = {}
    for i, pid in enumerate(pid_order[:n_polaroids]):
        img_s, img_e = best_spans[i * 2]
        cap_s, cap_e = best_spans[i * 2 + 1]
        polaroids.append(
            {
                "polaroid_id": pid,
                "img_phrase": _span_phrase(tokens, img_s, img_e),
                "cap_phrase": _span_phrase(tokens, cap_s, cap_e),
            }
        )
        span_map[pid] = {
            "img_span": [img_s, img_e],
            "cap_span": [cap_s, cap_e],
        }
    # Pad remaining polaroids with empty entries so downstream always sees 4
    for pid in pid_order[n_polaroids:]:
        polaroids.append({"polaroid_id": pid, "img_phrase": "", "cap_phrase": ""})
        span_map[pid] = {"img_span": [0, 0], "cap_span": [0, 0]}

    out = {
        "scene_id": scene_id,
        "wall_title": title_phrase,
        "polaroids": polaroids,
        "spans": {
            "wall_title": [best_title[0], best_title[1]],
            "polaroids": span_map,
        },
        "script": script,
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{scene_id}_layout_18_step_1_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_file}")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
