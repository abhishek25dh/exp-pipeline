import sys
import json
import subprocess
import re
from pathlib import Path

ALLOWED_TOKENS = {"vs", "or", "but", "->", ""}
BACKGROUND_TYPES = {"arrow"}
PREFIXES = sorted(
    [
        "image_group",
        "text_group",
        "arrow_group",
        "img",
        "cap",
        "txt",
        "label",
        "sub",
        "arrow",
        "text",
        "wall",
        "strip",
        "hero",
        "section",
        "bullet",
        "vs",
        "cta",
    ],
    key=len,
    reverse=True,
)
SAME_GROUP_OVERRIDES = [
    {"hero_image", "section_title"},
]


def get_step_num(path):
    """Extract the step number from a layout_X_step_N.py filename."""
    m = re.search(r'_step_(\d+)\.py$', path.name)
    return int(m.group(1)) if m else 0


def run_script(script_path, scene_num, retries=2):
    """Run a Python script with scene_num as the CLI argument. Retries on failure. Returns True on success."""
    print(f"    -> {script_path.name} {scene_num}")
    for attempt in range(1, retries + 2):
        try:
            result = subprocess.run([sys.executable, str(script_path), str(scene_num)], timeout=120)
        except subprocess.TimeoutExpired:
            print(f"    TIMEOUT: {script_path.name} exceeded 120s (attempt {attempt}/{retries+1})")
            continue
        if result.returncode == 0:
            return True
        print(f"    ERROR: {script_path.name} exited with code {result.returncode} (attempt {attempt}/{retries+1})")
        if attempt <= retries:
            print(f"    Retrying...")
    return False


def normalize(text):
    text = text.lower()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def phrase_in_script(phrase, scene_text_norm):
    p = normalize(phrase)
    if not p or p in ALLOWED_TOKENS:
        return True
    if re.match(r"^\d{1,2}$", p):
        return True
    return p in scene_text_norm


def clean_word(word: str) -> str:
    # Match timings.py: lowercase + strip non-alnum.
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def clean_phrase_tuple(phrase: str):
    return tuple([clean_word(w) for w in (phrase or "").split() if clean_word(w)])


def is_prefix_tuple(a, b) -> bool:
    if not a or not b:
        return False
    if len(a) > len(b):
        return False
    return b[: len(a)] == a


def count_tuple_matches(haystack_words, needle_tuple) -> int:
    if not needle_tuple:
        return 0
    n = len(needle_tuple)
    count = 0
    for i in range(0, len(haystack_words) - n + 1):
        if tuple(haystack_words[i : i + n]) == needle_tuple:
            count += 1
    return count


def first_tuple_match(haystack_words, needle_tuple):
    """Return first start index where needle_tuple matches, else None."""
    if not needle_tuple:
        return None
    n = len(needle_tuple)
    for i in range(0, len(haystack_words) - n + 1):
        if tuple(haystack_words[i : i + n]) == needle_tuple:
            return i
    return None


def all_tuple_matches(haystack_words, needle_tuple):
    if not needle_tuple:
        return []
    n = len(needle_tuple)
    out = []
    for i in range(0, len(haystack_words) - n + 1):
        if tuple(haystack_words[i : i + n]) == needle_tuple:
            out.append(i)
    return out


def get_element_index(element_id: str) -> int:
    """Extract numerical suffix for stable ordering (matches timings.py behavior)."""
    m = re.search(r"\d+", element_id or "")
    return int(m.group()) if m else 999


def audit_layout_5_coverage(elements, script_clean_words):
    """
    Layout 5 is a tiling layout: group phrases must cover the full script (no gaps/overlaps).
    We reconstruct phrase order by group index + role (cause -> arrow -> effect -> optional text).
    """
    by_group = {}
    for el in elements:
        eid = el.get("element_id", "")
        phrase = (el.get("phrase") or "").strip()
        if not phrase:
            continue
        m = re.match(r"^(image|arrow|text)_group_(\d+)(?:_(cause|effect))?$", eid)
        if not m:
            continue
        kind, gnum, role = m.group(1), int(m.group(2)), m.group(3)
        by_group.setdefault(gnum, {})
        if kind == "image":
            by_group[gnum][role or "image"] = phrase
        else:
            by_group[gnum][kind] = phrase

    ordered = []
    for gnum in sorted(by_group.keys()):
        g = by_group[gnum]
        if "cause" in g:
            ordered.append(g["cause"])
        if "arrow" in g:
            ordered.append(g["arrow"])
        if "effect" in g:
            ordered.append(g["effect"])
        # Optional label (rare)
        if "text" in g:
            ordered.append(g["text"])

    built = []
    for p in ordered:
        built.extend(list(clean_phrase_tuple(p)))

    if built != script_clean_words:
        return False

    # Extra robustness: ensure each element would fire at its intended script offset,
    # i.e., the phrase tuple's *first* match aligns to where it appears in the tiling.
    # (If a phrase repeats earlier in the script, timings.py would fire it too early.)
    offsets = {}  # (group_num, role) -> intended_start_index
    cursor = 0
    for gnum in sorted(by_group.keys()):
        g = by_group[gnum]
        for k in ("cause", "arrow", "effect", "text"):
            if k in g:
                ct = clean_phrase_tuple(g[k])
                offsets[(gnum, k)] = cursor
                cursor += len(ct)

    for el in elements:
        eid = el.get("element_id", "")
        phrase = (el.get("phrase") or "").strip()
        if not phrase:
            continue
        m = re.match(r"^(image|arrow|text)_group_(\d+)(?:_(cause|effect))?$", eid)
        if not m:
            continue
        kind = m.group(1)
        gnum = int(m.group(2))
        img_role = m.group(3)
        role = "arrow" if kind == "arrow" else ("text" if kind == "text" else (img_role or ""))
        if role not in {"cause", "effect", "arrow", "text"}:
            continue

        ct = clean_phrase_tuple(phrase)
        if not ct:
            continue
        intended = offsets.get((gnum, role), None)
        if intended is None:
            continue
        first = first_tuple_match(script_clean_words, ct)
        if first is None or first != intended:
            return False

    return True


def is_intentional_empty(element_id):
    eid = element_id.lower()
    # _lN suffix (N >= 2): wrapped continuation lines — only first line carries the phrase
    if re.search(r"_l[2-9]\d*$", eid):
        return True
    # center_title / center_title_N: static decorative labels (layout 14 circular flow)
    if eid == "center_title" or re.match(r"^center_title_\d+$", eid):
        return True
    return False


def is_host_element(element_id):
    eid = element_id.lower()
    return eid.startswith("host_") or eid == "host_character"


def get_group(eid):
    if eid.startswith("strip_"):
        return "__strip__"

    key = eid
    for p in PREFIXES:
        if key.startswith(p + "_"):
            key = key[len(p) + 1 :]
            break
        elif key == p:
            key = ""
            break

    key = re.sub(r"_l\d+$", "", key)
    if re.match(r"^\d+_\d+$", key):
        key = key.split("_")[0]
    return key if key else eid


def same_override_group(eid_a, eid_b):
    for group_set in SAME_GROUP_OVERRIDES:
        if eid_a in group_set and eid_b in group_set:
            return True
    return False


def audit_director_for_scene(scene_num):
    prompt_path = Path("assets/scene_prompts") / f"scene_{scene_num}_prompt.json"
    director_path = Path("assets/directorscript") / f"scene_{scene_num}_director.json"
    if not prompt_path.exists() or not director_path.exists():
        return [f"Missing prompt/director file for scene {scene_num}"]

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    director_data = json.loads(director_path.read_text(encoding="utf-8"))
    raw_prompt = prompt_data.get("prompt", "")
    scene_text = re.sub(r"^scene_\d+:", "", raw_prompt).strip()
    scene_norm = normalize(scene_text)
    layout = str(prompt_data.get("layout", "")).strip()
    script_clean_words = [clean_word(w) for w in scene_text.split() if clean_word(w)]

    issues = []
    elements = director_data.get("elements", [])
    phrase_to_entries = {}
    clean_tuple_to_eids = {}
    clean_tuple_to_elements = {}

    for el in elements:
        eid = el.get("element_id", "?")
        etype = el.get("type", "")
        phrase = (el.get("phrase") or "").strip()

        if is_host_element(eid):
            continue

        if not phrase:
            if etype in BACKGROUND_TYPES or is_intentional_empty(eid):
                continue
            issues.append(f"EMPTY phrase: [{eid}] (type={etype})")
            continue

        if not phrase_in_script(phrase, scene_norm):
            issues.append(f"NON-VERBATIM phrase: [{eid}] -> {repr(phrase)}")

        phrase_to_entries.setdefault(phrase.lower(), []).append((eid, get_group(eid)))
        ct = clean_phrase_tuple(phrase)
        clean_tuple_to_eids.setdefault(ct, []).append(eid)
        clean_tuple_to_elements.setdefault(ct, []).append(el)

    # Rule 3 (timings-accurate): duplicates are only safe if the script contains enough occurrences.
    for ct, eids in clean_tuple_to_eids.items():
        if not ct or len(eids) < 2:
            continue
        occ = count_tuple_matches(script_clean_words, ct)
        if occ < len(eids):
            issues.append(
                f'DUPLICATE phrase tuple without enough matches: {eids} -> "{ " ".join(ct) }" (occ={occ})'
            )

    # Rule 3 (timings-accurate): simulate timing assignment and flag true start-index collisions.
    assigned = {}  # eid -> start_index
    for ct, els in clean_tuple_to_elements.items():
        if not ct:
            continue
        # Skip decorative design tokens (VS, OR, ->, etc.) that don't appear in the voiceover
        if " ".join(ct) in ALLOWED_TOKENS:
            continue
        starts = all_tuple_matches(script_clean_words, ct)
        els_sorted = sorted(els, key=lambda e: get_element_index(e.get("element_id", "")))
        for idx, el in enumerate(els_sorted):
            eid = el.get("element_id", "?")
            if not starts:
                assigned[eid] = None
            elif idx < len(starts):
                assigned[eid] = starts[idx]
            else:
                assigned[eid] = starts[-1]

    # Missing matches.
    for eid, st in assigned.items():
        if st is None:
            issues.append(f"NO MATCH in script for phrase tuple: [{eid}]")

    # Collisions: same start index for multiple elements.
    start_to_eids = {}
    for eid, st in assigned.items():
        if st is None:
            continue
        start_to_eids.setdefault(st, []).append(eid)
    for st, eids in start_to_eids.items():
        if len(eids) > 1:
            issues.append(f"TIMING COLLISION (same start word): {eids} (start_index={st})")

    # Rule 5 (coverage) for tiling layouts: currently enforced for Layout 5 only.
    if layout == "5" and script_clean_words:
        if not audit_layout_5_coverage(elements, script_clean_words):
            issues.append("COVERAGE FAIL (layout 5): phrases do not tile the full script")

    return issues


def main():
    scene_dir = Path("assets/scene_prompts")
    if not scene_dir.exists():
        print(f"Error: {scene_dir} does not exist.")
        return 1

    if len(sys.argv) > 1:
        # Single scene mode: process only this exact scene number
        only = int(sys.argv[1])
        p = scene_dir / f"scene_{only}_prompt.json"
        if not p.exists():
            print(f"No prompt file found for scene {only}.")
            return
        scene_files = [p]
    else:
        # All scenes mode
        scene_files = sorted(
            (
                p for p in scene_dir.glob("scene_*_prompt.json")
                if len(p.stem.split("_")) >= 2 and p.stem.split("_")[1].isdigit()
            ),
            key=lambda p: int(p.stem.split("_")[1])
        )

    if not scene_files:
        print("No scene prompt files found.")
        return

    print(f"Processing {len(scene_files)} scene(s).\n")
    print("=" * 60)

    for scene_file in scene_files:
        scene_num = int(scene_file.stem.split("_")[1])

        with open(scene_file, "r", encoding="utf-8") as f:
            scene_data = json.load(f)

        layout = scene_data.get("layout", "").strip()
        if not layout:
            print(f"\n[Scene {scene_num}] ERROR: No layout found in {scene_file.name}. Skipping.")
            continue

        print(f"\n[Scene {scene_num}] Layout {layout}")

        # Find all step files for this layout, sorted by step number
        step_files = sorted(
            Path(".").glob(f"layout_{layout}_step_*.py"),
            key=get_step_num
        )

        generator = Path(f"layout_{layout}_generator.py")

        if not step_files and not generator.exists():
            print(f"  ERROR: No files found for layout {layout}. Skipping.")
            continue

        failed = False
        for step_file in step_files:
            if not run_script(step_file, scene_num):
                failed = True
                break

        if failed:
            print(f"  Skipping generator (step failed).")
            continue

        if generator.exists():
            if not run_script(generator, scene_num):
                print(f"  Generator failed.")
                continue
        else:
            print(f"  WARNING: layout_{layout}_generator.py not found.")

        issues = audit_director_for_scene(scene_num)
        if not issues:
            print("  Phrase rules: PASS")
            scene_ok = True
        else:
            print(f"  Phrase rules: FAIL ({len(issues)} issue(s))")
            for iss in issues[:6]:
                print(f"    - {iss}")
            if len(issues) > 6:
                print(f"    - ... {len(issues)-6} more")
            scene_ok = False

        if scene_ok:
            print(f"  Scene {scene_num} complete.")
        else:
            print(f"  Scene {scene_num} ended with phrase-rule violations.")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
