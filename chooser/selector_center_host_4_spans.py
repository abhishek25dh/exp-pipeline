import json
import re
from pathlib import Path


def read_prompt(scene_num: int):
    p = Path("assets/scene_prompts") / f"scene_{scene_num}_prompt.json"
    return json.loads(p.read_text(encoding="utf-8"))


def tokenize(s: str):
    return s.split()


def strip_punct(w: str):
    return re.sub(r"^[^\w']+|[^\w']+$", "", w)


def find_host_span(tokens):
    lowered = [strip_punct(t).lower() for t in tokens]
    target = {"you", "you're", "youre", "your"}
    # try to find a token in target and return a 3-7 window centered
    for i, w in enumerate(lowered):
        if w in target:
            for size in range(3, 8):
                start = max(0, i - size // 2)
                end = start + size
                if end > len(tokens):
                    start = max(0, len(tokens) - size)
                    end = start + size
                phrase = tokens[start:end]
                return start, end
    # fallback first 3-7 words
    size = min(5, max(3, len(tokens)))
    return 0, size


def remove_span(tokens, span):
    s, e = span
    return tokens[:s] + tokens[e:]


def partition_into_n_spans(tokens, n=4, max_word=5, host_span=None):
    # tokens is the remaining list after removing host span
    L = len(tokens)
    if L == 0:
        return [(0, 0)] * n
    # try balanced sizes
    base = L // n
    rem = L % n
    sizes = [base + (1 if i < rem else 0) for i in range(n)]
    # cap sizes to max_word; if any > max_word, leave as is but warn
    spans = []
    idx = 0
    for sz in sizes:
        end = min(idx + sz, L)
        spans.append((idx, end))
        idx = end
    # if tokens left, append to last
    if idx < L:
        spans[-1] = (spans[-1][0], L)
    return spans


def to_global_spans(remaining_spans, host_span):
    # remaining spans indices are relative to tokens-without-host; need mapping
    s, e = host_span
    def map_index(idx):
        return idx if idx < s else idx + (e - s)
    return [(map_index(a), map_index(b)) for (a, b) in remaining_spans]


def build_selection(scene_num: int):
    data = read_prompt(scene_num)
    script = data.get("prompt", "").strip()
    script = re.sub(r'^\s*scene_\d+[:\-]\s*', '', script, flags=re.I)
    tokens = tokenize(script)

    host_span = find_host_span(tokens)
    host_phrase = " ".join(tokens[host_span[0]:host_span[1]]).strip()

    remaining = remove_span(tokens, host_span)
    rem_spans = partition_into_n_spans(remaining, n=4, max_word=5, host_span=host_span)
    global_spans = to_global_spans(rem_spans, host_span)

    images = []
    for gi, (a, b) in enumerate(global_spans):
        phrase = " ".join(tokens[a:b]).strip()
        images.append({
            "group_id": f"image_{gi}",
            "span": [a, b],
            "phrase": phrase
        })

    out = {
        "scene_id": f"scene_{scene_num}",
        "host_span": [host_span[0], host_span[1]],
        "host_phrase": host_phrase,
        "images": images,
        "script_tokens": tokens
    }

    odir = Path("assets/choices")
    odir.mkdir(parents=True, exist_ok=True)
    opath = odir / f"scene_{scene_num}_selection.json"
    opath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote selection to {opath}")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("usage: python selector_center_host_4_spans.py <scene_no>")
        sys.exit(1)
    build_selection(int(sys.argv[1]))
