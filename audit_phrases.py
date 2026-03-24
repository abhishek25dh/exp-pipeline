"""
audit_phrases.py
================
Two-pass audit:

PASS 1 — Scene prompts vs para text
  For every scene_X_prompt.json that has a para_id:
  - Load the para text
  - Check the scene text is verbatim in the para (case-insensitive)

PASS 2 — Director script phrases vs scene text
  For every scene_X_director.json that has a matching scene_X_prompt.json:
  - For each element: check phrase is a substring of the scene text
  - Flag: empty phrases (nothing assigned)
  - Flag: phrases not found in the scene text (invented)
  - Ignore structural tokens: "VS", "OR", "BUT", arrows, intentional empty second lines

Usage:
    py audit_phrases.py
"""

import json
import re
from pathlib import Path

SCENE_PROMPT_DIR  = Path("assets/scene_prompts")
DIRECTOR_DIR      = Path("assets/directorscript")
PARA_DIR          = Path("assets/para")

# These short structural tokens are allowed even if not literally in the script
ALLOWED_TOKENS = {"vs", "or", "but", "→", "->", ""}

# Element types where an empty phrase is acceptable (they appear on-screen without a cue)
BACKGROUND_TYPES = {"arrow"}


def normalize(text):
    """Lowercase + collapse whitespace + normalize smart quotes + strip punctuation."""
    text = text.lower()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Strip punctuation (keep letters, digits, spaces, apostrophes)
    text = re.sub(r"[^\w\s']", ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def phrase_in_script(phrase, scene_text_norm):
    """Return True if phrase (normalized) appears in scene_text (normalized)."""
    p = normalize(phrase)
    if not p or p in ALLOWED_TOKENS:
        return True   # empty or structural — skip
    if re.match(r'^\d{1,2}$', p):
        return True   # step numbers like "01", "02" are structural
    return p in scene_text_norm


def is_intentional_empty(element_id):
    """Second lines of split captions have intentionally empty phrases."""
    return element_id.endswith("_l2")


def is_host_element(element_id):
    """Host character elements have structural label phrases, not sync cues."""
    eid = element_id.lower()
    return eid.startswith("host_") or eid == "host_character"


def run_audit():
    issues = []
    warnings = []

    # ── Load all para texts ───────────────────────────────────────────────────
    para_texts = {}
    for pf in sorted(PARA_DIR.glob("para_*.json")):
        pid = pf.stem.split("_")[1]
        data = json.loads(pf.read_text(encoding="utf-8"))
        key  = f"para_{pid}"
        para_texts[pid] = normalize(data.get(key, ""))

    # ── Load all scene prompts ────────────────────────────────────────────────
    scene_prompts = {}   # scene_num -> {text_norm, para_id}
    for sf in sorted(SCENE_PROMPT_DIR.glob("scene_*_prompt.json"),
                     key=lambda p: int(p.stem.split("_")[1])):
        snum = sf.stem.split("_")[1]
        data = json.loads(sf.read_text(encoding="utf-8"))
        raw_prompt = data.get("prompt", "")
        # Strip "scene_X:" prefix
        scene_text = re.sub(r'^scene_\d+:', '', raw_prompt).strip()
        para_id    = data.get("para_id", None)
        scene_prompts[snum] = {
            "text":      scene_text,
            "text_norm": normalize(scene_text),
            "para_id":   para_id,
            "layout":    data.get("layout", "?"),
        }

    print("=" * 70)
    print("PASS 1 — Scene prompts vs para text")
    print("=" * 70)

    pass1_ok = 0
    for snum, sp in scene_prompts.items():
        pid = sp["para_id"]
        if pid is None:
            warnings.append(f"  scene_{snum}: no para_id stored — can't verify source")
            continue
        if pid not in para_texts:
            issues.append(f"  scene_{snum}: para_id={pid} but para_{pid}.json not found")
            continue
        scene_norm = sp["text_norm"]
        para_norm  = para_texts[pid]
        if scene_norm in para_norm:
            pass1_ok += 1
            print(f"  [OK]  scene_{snum} (para {pid}): verbatim match")
        else:
            issues.append(
                f"  [FAIL] scene_{snum} (para {pid}): text NOT found in para\n"
                f"         Scene text: {sp['text'][:100]}"
            )

    for w in warnings:
        print(f"  [WARN] {w}")

    print(f"\n  {pass1_ok}/{len(scene_prompts)} scene prompts verified verbatim.\n")

    # ── PASS 2 ────────────────────────────────────────────────────────────────
    print("=" * 70)
    print("PASS 2 — Director script phrases vs scene text")
    print("=" * 70)

    pass2_scenes = 0
    pass2_elements = 0
    director_files = sorted(DIRECTOR_DIR.glob("scene_*_director.json"),
                            key=lambda p: int(p.stem.split("_")[1]))

    for df in director_files:
        snum = df.stem.split("_")[1]
        if snum not in scene_prompts:
            print(f"  [SKIP] scene_{snum}: no matching scene prompt — director script is from old run")
            continue

        sp         = scene_prompts[snum]
        scene_norm = sp["text_norm"]
        director   = json.loads(df.read_text(encoding="utf-8"))
        elements   = director.get("elements", [])

        scene_issues = []
        for el in elements:
            eid    = el.get("element_id", "?")
            etype  = el.get("type", "")
            phrase = el.get("phrase", "")

            # Host elements have structural labels, not sync phrases — skip
            if is_host_element(eid):
                continue

            # Empty phrase check
            if not phrase.strip():
                if etype in BACKGROUND_TYPES or is_intentional_empty(eid):
                    pass  # arrows and split-caption second lines are fine
                else:
                    scene_issues.append(
                        f"    [EMPTY PHRASE] {eid} (type={etype}) — no sync phrase assigned"
                    )
                continue

            # Phrase in script check
            if not phrase_in_script(phrase, scene_norm):
                scene_issues.append(
                    f"    [INVENTED] {eid} (type={etype}) phrase={repr(phrase)}"
                )
            else:
                pass2_elements += 1

        if scene_issues:
            print(f"\n  scene_{snum} (layout {sp['layout']})  ISSUES:")
            for si in scene_issues:
                print(si)
            issues.extend(scene_issues)
        else:
            print(f"  [OK]  scene_{snum} (layout {sp['layout']}) — all {len(elements)} elements clean")
            pass2_scenes += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if not issues:
        print("  No issues found. All phrases verified.")
    else:
        print(f"  {len(issues)} issue(s) found:\n")
        for iss in issues:
            print(iss)


if __name__ == "__main__":
    run_audit()
