import json
import re
from pathlib import Path


def load(scene_num):
    prompt = Path("assets/scene_prompts") / f"scene_{scene_num}_prompt.json"
    director = Path("assets/directorscript") / f"scene_{scene_num}_director.json"
    return json.loads(prompt.read_text(encoding="utf-8")), json.loads(director.read_text(encoding="utf-8"))


def tokenize_whitespace(s: str):
    return s.split()


def find_span(tokens, phrase_tokens):
    n = len(phrase_tokens)
    for i in range(len(tokens) - n + 1):
        if tokens[i:i+n] == phrase_tokens:
            return i, i+n
    return None


def strip_punct_lower(w):
    return re.sub(r"^[^\w']+|[^\w']+$", "", w).lower()


def validate(scene_num: int):
    prompt, director = load(scene_num)
    script = prompt.get("prompt", "").strip()
    script = re.sub(r'^\s*scene_\d+[:\-]\s*', '', script, flags=re.I)
    tokens = tokenize_whitespace(script)

    host_phrase = director.get("host_phrase", "")
    host_tokens = tokenize_whitespace(host_phrase)

    print("Host phrase:", repr(host_phrase))

    # check host phrase exists verbatim
    span = find_span(tokens, host_tokens)
    if not span:
        print("FAIL: host_phrase not found verbatim in script")
        return
    host_span = span
    print("Host span indices:", host_span)

    # collect remaining tokens as expected coverage
    remaining_tokens = tokens[:host_span[0]] + tokens[host_span[1]:]

    # validate each image phrase
    images = [e for e in director.get("elements", []) if e.get("type") == "image"]
    used_indices = []
    all_image_tokens = []
    stopwords = set(["the","a","an","and","or","to","into","with","you","your","you're","youre","been","this","is"])

    host_token_set = set(strip_punct_lower(t) for t in host_tokens if strip_punct_lower(t))

    for img in images:
        phrase = img.get("phrase", "")
        ptokens = tokenize_whitespace(phrase)
        print(f"Checking image {img.get('element_id')} phrase={repr(phrase)} tokens={ptokens}")

        # length check
        if not (1 <= len(ptokens) <= 5):
            print(f"FAIL: image phrase '{phrase}' must be 1-5 words")

        # host exclusion
        for t in ptokens:
            if strip_punct_lower(t) in host_token_set:
                print(f"FAIL: image phrase '{phrase}' contains host token '{t}'")

        # contiguous check in original script
        span = find_span(tokens, ptokens)
        if not span:
            print(f"FAIL: image phrase '{phrase}' is not a contiguous substring of the original script")
        else:
            used_indices.append(span)
            all_image_tokens.extend(ptokens)

    # uniqueness of non-stopwords across images
    content_words = [strip_punct_lower(t) for t in all_image_tokens if strip_punct_lower(t) and strip_punct_lower(t) not in stopwords]
    dupes = {w for w in content_words if content_words.count(w) > 1}
    if dupes:
        print("FAIL: non-stopword duplicates across images:", dupes)

    # coverage check: all_image_tokens should equal remaining_tokens in order
    # but since tokens may have punctuation, compare raw sequence
    if all_image_tokens == remaining_tokens:
        print("PASS: image phrases exactly tile remaining script tokens")
    else:
        print("FAIL: image phrases do not tile remaining tokens exactly")
        print("Remaining tokens:", remaining_tokens)
        print("Image phrase tokens:", all_image_tokens)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("usage: python layout_7_validator.py <scene_no>")
        sys.exit(1)
    validate(int(sys.argv[1]))
