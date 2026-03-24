import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "assets" / "scene_prompts"
DIRECTORS_DIR = ROOT / "assets" / "directorscript"

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
}

BAD_END_TOKENS = {"you're", "we're", "they're", "i'm"}
OK_START_STOP_WORDS = {"you", "your"}


def normalize_token(token: str) -> str:
    return re.sub(r"^[^\w']+|[^\w']+$", "", (token or "").lower())


def tokenize_phrase(phrase: str):
    return [t for t in (phrase or "").strip().split() if t]


def phrase_col(filename: str) -> str:
    name = (filename or "").lower()
    if name.startswith("left_"):
        return "left"
    if name.startswith("right_"):
        return "right"
    if name.startswith("middle_"):
        return "middle"
    return "unknown"


def audit_director(scene_id: str, director_path: Path):
    if not director_path.exists():
        return {"scene_id": scene_id, "missing": True, "flags": ["missing_director_json"]}

    data = json.loads(director_path.read_text(encoding="utf-8"))
    elements = data.get("elements", [])
    flags = []

    phrases = []
    for el in elements:
        p = (el.get("phrase") or "").strip()
        if not p:
            flags.append(f"empty_phrase:{el.get('element_id','?')}")
        phrases.append(p.lower())

    # Uniqueness check (simple normalize).
    seen = set()
    dups = set()
    for p in phrases:
        k = re.sub(r"\s+", " ", p).strip()
        if not k:
            continue
        if k in seen:
            dups.add(k)
        seen.add(k)
    if dups:
        flags.append(f"duplicate_phrases:{len(dups)}")

    texts = [e for e in elements if (e.get("type") or "").startswith("text")]
    images = [e for e in elements if (e.get("type") or "") == "image"]

    # Text readability heuristics.
    for t in texts:
        phrase = (t.get("phrase") or "").strip()
        toks = tokenize_phrase(phrase)
        if len(toks) < 2:
            flags.append(f"short_text:{t.get('element_id','?')}:{len(toks)}")
        if toks:
            start = normalize_token(toks[0])
            end = normalize_token(toks[-1])
            if start in STOP_WORDS and start not in OK_START_STOP_WORDS:
                flags.append(f"text_starts_stop:{t.get('element_id','?')}")
            if end in STOP_WORDS:
                flags.append(f"text_ends_stop:{t.get('element_id','?')}")
            if end in BAD_END_TOKENS:
                flags.append(f"text_ends_contraction:{t.get('element_id','?')}")

    # Image readability + "dynamism" checks.
    short_imgs = 0
    dangling_imgs = 0
    cols = {"left": [], "middle": [], "right": [], "unknown": []}
    for im in images:
        phrase = (im.get("phrase") or "").strip()
        toks = tokenize_phrase(phrase)
        if len(toks) < 3:
            short_imgs += 1
        if toks and normalize_token(toks[-1]) in BAD_END_TOKENS:
            dangling_imgs += 1
        cols[phrase_col(im.get("filename", ""))].append(im)

    if short_imgs:
        flags.append(f"short_image_phrases:{short_imgs}/{len(images) if images else 0}")
    if dangling_imgs:
        flags.append(f"dangling_image_contractions:{dangling_imgs}/{len(images) if images else 0}")

    # If all x in a column are identical, it's a rigid stack.
    rigid_cols = 0
    for col, items in cols.items():
        if col in ("unknown", "middle"):
            continue
        if len(items) >= 2:
            xs = {int(it.get("x", 0)) for it in items}
            if len(xs) == 1:
                rigid_cols += 1
    if rigid_cols:
        flags.append(f"rigid_columns:{rigid_cols}")

    return {
        "scene_id": scene_id,
        "missing": False,
        "num_text": len(texts),
        "num_images": len(images),
        "text_phrases": [t.get("phrase", "") for t in texts],
        "flags": flags,
    }


def main():
    layout1_nums = []
    for p in sorted(PROMPTS_DIR.glob("scene_*_prompt.json")):
        m = re.match(r"^scene_(\d+)_prompt\.json$", p.name)
        if not m:
            continue
        num = int(m.group(1))
        j = json.loads(p.read_text(encoding="utf-8"))
        if str(j.get("layout", "")).strip() == "1":
            layout1_nums.append(num)

    if not layout1_nums:
        print("No layout_1 scenes found in assets/scene_prompts.")
        return

    print(f"layout_1 scenes ({len(layout1_nums)}): {', '.join('scene_'+str(n) for n in layout1_nums)}")
    print("")

    any_flags = False
    for num in layout1_nums:
        scene_id = f"scene_{num}"
        director_path = DIRECTORS_DIR / f"{scene_id}_director.json"
        res = audit_director(scene_id, director_path)
        flags = res.get("flags", [])
        if flags:
            any_flags = True
        text_summary = "; ".join([t.strip() for t in (res.get("text_phrases") or []) if t.strip()])
        if len(text_summary) > 120:
            text_summary = text_summary[:117] + "..."
        status = "OK" if not flags else "FLAGS"
        print(f"{scene_id}: {status} | text={res.get('num_text',0)} imgs={res.get('num_images',0)}")
        if text_summary:
            print(f"  text: {text_summary}")
        if flags:
            print(f"  flags: {', '.join(flags)}")

    if any_flags:
        print("\nResult: some layout_1 scenes have issues (see flags).")
    else:
        print("\nResult: all layout_1 scenes look clean by current heuristics.")


if __name__ == "__main__":
    main()
