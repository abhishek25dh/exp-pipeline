"""
Layout 19 Step 1 — Deterministic Phrase Segmentation for Pyramid Stack
======================================================================
Splits the scene script into:
  - 1 title phrase (opening 2-5 words)
  - 3 image phrases (for pyramid: 1 hero + 2 supporting)
  - 3 text keyword phrases (bottom row labels)

Total: 6 body phrases alternating img/txt: img, txt, img, txt, img, txt
All phrases are verbatim spans from the script tokens — no AI needed.
"""

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

    # Image phrase: 2-6 words. Text phrase: 1-3 words.
    if idx % 2 == 0:
        pref_min, pref_max = 2, 6
    else:
        pref_min, pref_max = 1, 3

    if length < pref_min:
        sc -= (pref_min - length) * 14
    if length > pref_max:
        sc -= (length - pref_max) * 6

    if start_norm in STOP_WORDS:
        sc -= 3
    if end_norm in STOP_WORDS:
        sc -= 2
    if end_norm in BAD_END_WORDS:
        sc -= 4
    if tokens[e - 1].endswith(PUNCT_END):
        sc += 2

    internal_breaks = 0
    for tok in tokens[s : max(s, e - 1)]:
        if tok.endswith(PUNCT_END):
            internal_breaks += 1
    if internal_breaks:
        sc -= 60 * internal_breaks

    return sc


def build_min_lens(total_tokens, phrase_count):
    min_lens = [2 for _ in range(phrase_count)]
    min_total = sum(min_lens)
    if total_tokens >= min_total:
        return min_lens

    deficit = min_total - total_tokens
    order = [i for i in range(phrase_count) if i % 2 == 1] + [i for i in range(phrase_count) if i % 2 == 0]
    it = 0
    while deficit > 0 and it < 1000:
        for idx in order:
            if deficit <= 0:
                break
            if min_lens[idx] > 1:
                min_lens[idx] -= 1
                deficit -= 1
        it += 1
    return min_lens


def build_max_lens(total_tokens, min_lens):
    avg = int(math.ceil(total_tokens / len(min_lens)))
    base_img = max(6, avg + 2)
    base_txt = 4
    max_lens = [(base_img if i % 2 == 0 else base_txt) for i in range(len(min_lens))]
    for i in range(len(max_lens)):
        if max_lens[i] < min_lens[i]:
            max_lens[i] = min_lens[i]

    img_idxs = [i for i in range(len(max_lens)) if i % 2 == 0]
    k = 0
    while sum(max_lens) < total_tokens:
        idx = img_idxs[k % len(img_idxs)]
        max_lens[idx] += 1
        k += 1
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


def pick_title_span(tokens):
    max_title = 5
    min_title = 2
    candidates = []
    for end in range(min_title, min(max_title, len(tokens)) + 1):
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
        return [0, min(max_title, len(tokens))]

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


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
        print(f"Error: script too short for Layout 19 (need >=1 tokens), got {len(tokens)}.")
        return 1

    # Priority allocation: use as many panels as tokens allow.
    # Each panel needs img_phrase + txt_phrase (2 tokens min) plus title (1 token min).
    # P1=3 panels (needs 7+), P2=2 panels (needs 5), P3=1 panel (needs 3).
    if len(tokens) >= 7:
        n_panels = 3
    elif len(tokens) >= 5:
        n_panels = 2
    else:
        n_panels = 1

    title_span = pick_title_span(tokens)
    remaining = len(tokens) - title_span[1]

    # n_panels image phrases + n_panels text phrases = n_panels*2 body phrases
    phrase_count = n_panels * 2
    min_lens = build_min_lens(remaining, phrase_count)
    max_lens = build_max_lens(remaining, min_lens)

    spans = segment_into_phrases(tokens, title_span[1], len(tokens), min_lens, max_lens)
    if spans is None:
        # Fallback: equal chunks
        n = remaining
        k = n // phrase_count if phrase_count > 0 else n
        r = n % phrase_count if phrase_count > 0 else 0
        spans = []
        pos = title_span[1]
        for i in range(phrase_count):
            size = max(1, k + (1 if i < r else 0))
            spans.append([pos, pos + size])
            pos += size

    title_phrase = _span_phrase(tokens, title_span[0], title_span[1])

    # Build active panels
    panels = []
    for i in range(n_panels):
        img_s, img_e = spans[i * 2]
        txt_s, txt_e = spans[i * 2 + 1]
        panels.append({
            "panel_id": f"panel_{i+1}",
            "img_phrase": _span_phrase(tokens, img_s, img_e),
            "txt_phrase": _span_phrase(tokens, txt_s, txt_e),
        })
    # Pad remaining panels with empty entries so downstream always sees 3
    for i in range(n_panels, 3):
        panels.append({
            "panel_id": f"panel_{i+1}",
            "img_phrase": "",
            "txt_phrase": "",
        })

    out = {
        "scene_id": scene_id,
        "main_title": title_phrase,
        "panels": panels,
        "script": script,
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{scene_id}_layout_19_step_1_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_file}")
    print(f"   Title: {title_phrase}")
    for p in panels:
        print(f"   {p['panel_id']}: img='{p['img_phrase']}' | txt='{p['txt_phrase']}'")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
