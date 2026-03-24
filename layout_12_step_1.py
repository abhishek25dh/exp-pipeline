"""
Layout 12 Step 1 — Phrase Segmentation
=======================================
3-image layout: img_2 (center, P1) + img_1 (left, P2) + img_3 (right, P3).
Splits the script into up to 3 verbatim phrases in priority order.
No API call — fully deterministic.

Output: assets/tmp/{scene_id}_layout_12_step_1_tmp.json
"""

import json, re, sys
from pathlib import Path

# Image slots in priority order (P1 fires first, gets first tokens)
IMAGES = [
    {"image_id": "img_2", "priority": 1, "x": 780,  "y": 520, "scale": 0.411},
    {"image_id": "img_1", "priority": 2, "x": 260,  "y": 540, "scale": 0.239},
    {"image_id": "img_3", "priority": 3, "x": 1500, "y": 500, "scale": 0.683},
]

MIN_TOKENS_PER_IMAGE = 2


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (w or "").lower())


def clean_phrase_tuple(phrase: str):
    return tuple(clean_word(w) for w in (phrase or "").split() if clean_word(w))


def is_prefix(a, b) -> bool:
    return bool(a) and bool(b) and len(a) <= len(b) and b[:len(a)] == a


def validate_phrases(tokens, spans):
    errors = []
    phrases = [" ".join(tokens[s:e]) for s, e in spans]
    cleans  = [clean_phrase_tuple(p) for p in phrases]
    seen = set()
    for c in cleans:
        if not c:
            errors.append("empty phrase"); continue
        if c in seen:
            errors.append(f"DUPLICATE: {' '.join(c)}")
        seen.add(c)
    uniq = sorted(set(c for c in cleans if c), key=lambda x: (len(x), x))
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            if is_prefix(uniq[i], uniq[j]) or is_prefix(uniq[j], uniq[i]):
                errors.append(f"PREFIX: {' '.join(uniq[i])} ~ {' '.join(uniq[j])}")
    tiled = [clean_word(w) for p in phrases for w in p.split() if clean_word(w)]
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    if tiled != script_clean:
        errors.append("TILING_MISMATCH")
    return errors


def split_proportional(tokens, n):
    """Split tokens into n chunks as evenly as possible."""
    total = len(tokens)
    base, rem = divmod(total, n)
    spans, pos = [], 0
    for i in range(n):
        size = max(1, base + (1 if i < rem else 0))
        spans.append((pos, pos + size))
        pos += size
    return spans


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    prompt_file = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_file.exists():
        print(f"Error: {prompt_file} not found.")
        return 1

    scene_data = json.loads(prompt_file.read_text(encoding="utf-8"))
    script     = strip_scene_prefix(scene_data.get("prompt", ""))
    tokens     = script.split()
    n_tokens   = len(tokens)

    if n_tokens < 1:
        print(f"Error: empty script for {scene_id}.")
        return 1

    # How many images can we activate?
    n_active = min(len(IMAGES), max(1, n_tokens // MIN_TOKENS_PER_IMAGE))
    print(f"   {n_tokens} tokens -> {n_active}/{len(IMAGES)} active images")

    active_images = IMAGES[:n_active]
    spans = split_proportional(tokens, n_active)

    errors = validate_phrases(tokens, spans)
    if errors:
        print("   Validation warnings:")
        for e in errors[:10]:
            print(f"     - {e}")

    images_out = []
    for img_def, (s, e) in zip(active_images, spans):
        images_out.append({
            "image_id": img_def["image_id"],
            "priority": img_def["priority"],
            "phrase":   " ".join(tokens[s:e]),
            "span":     [s, e],
        })

    out = {
        "scene_id": scene_id,
        "script":   script,
        "tokens":   tokens,
        "images":   images_out,
    }

    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{scene_id}_layout_12_step_1_tmp.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_file}")
    for img in images_out:
        print(f"   {img['image_id']} (P{img['priority']}): {repr(img['phrase'])}")


if __name__ == "__main__":
    sys.exit(main() or 0)
