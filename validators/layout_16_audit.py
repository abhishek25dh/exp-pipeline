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
    "not", "this", "that", "i", "you", "he", "she", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his", "our", "their",
    "up", "out", "as", "so", "if", "then", "than", "also", "just", "about",
    "into", "over", "after", "before", "now", "when", "what", "where", "who", "how",
}


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def normalize_word(w: str) -> str:
    w = (w or "").lower().replace("\u2019", "'").replace("'", "")
    w = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", w)
    return w


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


def audit_scene(scene_id: str):
    director_path = DIRECTORS_DIR / f"{scene_id}_director.json"
    if not director_path.exists():
        return {"scene_id": scene_id, "ok": False, "flags": ["missing_director_json"]}

    data = json.loads(director_path.read_text(encoding="utf-8"))
    els = data.get("elements", [])
    flags = []

    title = [e for e in els if e.get("element_id") == "strip_title"]
    subtitle = [e for e in els if e.get("element_id") == "strip_subtitle"]
    imgs = [e for e in els if (e.get("element_id") or "").startswith("img_frame_")]
    caps = [e for e in els if (e.get("element_id") or "").startswith("cap_frame_")]

    if len(title) != 1:
        flags.append("missing_strip_title")
    if len(subtitle) != 1:
        flags.append("missing_strip_subtitle")
    if len(imgs) != 5:
        flags.append(f"images={len(imgs)}")
    if len(caps) != 5:
        flags.append(f"captions={len(caps)}")
    if len(els) != 12:
        flags.append(f"elements={len(els)}")

    phrases = []
    for e in els:
        p = (e.get("phrase") or "").strip()
        if not p:
            flags.append(f"empty_phrase:{e.get('element_id','?')}")
        phrases.append((e.get("element_id", "?"), p))

    # Flag phrases that contain a sentence terminator internally (e.g. "loser. You").
    for eid, p in phrases:
        toks = (p or "").split()
        if len(toks) >= 2:
            for t in toks[:-1]:
                if t.endswith((".", "!", "?")):
                    flags.append(f"internal_sentence_break:{eid}")
                    break

    norm = [(eid, normalize_text(p)) for eid, p in phrases if p.strip()]
    groups = {}
    for eid, p in norm:
        groups.setdefault(p, []).append(eid)
    dups = {k: v for k, v in groups.items() if len(v) > 1}
    if dups:
        flags.append(f"duplicate_phrases:{len(dups)}")

    # Prefix conflicts: the timing engine matches phrases by exact cleaned word tuples.
    clean = [(eid, clean_phrase_tuple(p)) for eid, p in phrases]
    for i, (id1, t1) in enumerate(clean):
        for id2, t2 in clean[i + 1 :]:
            if is_prefix_tuple(t1, t2) or is_prefix_tuple(t2, t1):
                flags.append(f"prefix:{id1}~{id2}")
                break

    # Content overlap (coarse): flag only if overlap is sizable, to avoid false alarms on common words.
    for i, (id1, p1) in enumerate(phrases):
        cw1 = content_words(p1)
        if not cw1:
            continue
        for id2, p2 in phrases[i + 1 :]:
            cw2 = content_words(p2)
            if not cw2:
                continue
            overlap = cw1 & cw2
            if len(overlap) >= 2:
                flags.append(f"content_overlap:{id1}~{id2}")
                break

    return {"scene_id": scene_id, "ok": not flags, "flags": flags}


def main():
    scene_nums = []
    for p in sorted(PROMPTS_DIR.glob("scene_*_prompt.json")):
        m = re.match(r"^scene_(\d+)_prompt\.json$", p.name)
        if not m:
            continue
        num = int(m.group(1))
        j = json.loads(p.read_text(encoding="utf-8"))
        if str(j.get("layout", "")).strip() == "16":
            scene_nums.append(num)

    if not scene_nums:
        print("No layout_16 scenes found.")
        return

    print(f"layout_16 scenes ({len(scene_nums)}): {', '.join('scene_'+str(n) for n in scene_nums)}")
    print("")

    any_flags = False
    for n in scene_nums:
        sid = f"scene_{n}"
        res = audit_scene(sid)
        if not res["ok"]:
            any_flags = True
        status = "OK" if res["ok"] else "FLAGS"
        print(f"{sid}: {status}")
        if res["flags"]:
            print(f"  flags: {', '.join(res['flags'][:12])}")

    if any_flags:
        print("\nResult: some layout_16 scenes have issues (see flags).")
    else:
        print("\nResult: all layout_16 scenes look structurally clean by current audit.")


if __name__ == "__main__":
    main()
