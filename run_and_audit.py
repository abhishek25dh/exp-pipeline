"""
run_and_audit.py
================
Runs the layout pipeline scene-by-scene (same logic as layout_creator.py)
and immediately audits each director script for:
  - Empty phrases on any element
  - Duplicate phrases across different visual groups (cross-element collision)

Usage:
  py -u run_and_audit.py [start_scene]
"""

import sys
import json
import subprocess
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Grouping logic
# ---------------------------------------------------------------------------

PREFIXES = sorted([
    'image_group', 'text_group', 'arrow_group',
    'img', 'cap', 'txt', 'label', 'sub', 'arrow',
    'text', 'wall', 'strip', 'hero', 'section', 'bullet', 'vs', 'cta',
], key=len, reverse=True)  # longest-first so image_group matches before img

# Element IDs that are intentionally part of the same simultaneous visual unit
# but have structurally different ID prefixes — treat them as the same group.
SAME_GROUP_OVERRIDES = [
    {'hero_image', 'section_title'},   # layout 15: hero + title appear together
]


def get_group(eid):
    """Return the visual-unit group key for an element ID.
    Elements in the same group legitimately share a phrase (they appear together).
    """
    # Elements whose IDs start with 'strip_' all appear together as the header unit
    if eid.startswith('strip_'):
        return '__strip__'

    key = eid
    for p in PREFIXES:
        if key.startswith(p + '_'):
            key = key[len(p) + 1:]
            break
        elif key == p:
            key = ''
            break
    # Strip split-caption suffix (_l1, _l2, etc.)
    key = re.sub(r'_l\d+$', '', key)
    # For layout-6-style keys like "2_1" (group_num + element_index), use just group_num
    if re.match(r'^\d+_\d+$', key):
        key = key.split('_')[0]
    return key if key else eid


def same_override_group(eid_a, eid_b):
    """True if two element IDs belong to a known same-unit override pair."""
    for group_set in SAME_GROUP_OVERRIDES:
        if eid_a in group_set and eid_b in group_set:
            return True
    return False


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------

def audit_director(path):
    """Audit a director JSON. Returns list of issue strings (empty = all good)."""
    issues = []
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [f"  ERROR reading file: {e}"]

    elements = data.get('elements', [])
    phrase_to_entries = {}  # phrase_lower -> [(eid, group), ...]

    for el in elements:
        eid   = el.get('element_id', '?')
        etype = el.get('type', '')
        phrase = (el.get('phrase') or '').strip()

        # Arrows legitimately carry no phrase
        if etype == 'arrow' or re.match(r'^arrow', eid):
            if not phrase:
                continue  # OK
            # fall through to duplicate check if they do have a phrase

        if not phrase:
            issues.append(f"  EMPTY phrase: [{eid}] (type={etype})")
            continue

        group = get_group(eid)
        key   = phrase.lower()
        phrase_to_entries.setdefault(key, []).append((eid, group))

    # Cross-group duplicate check
    for phrase_lower, entries in phrase_to_entries.items():
        if len(entries) < 2:
            continue
        groups = [g for _, g in entries]
        if len(set(groups)) <= 1:
            continue  # All in same group — OK
        # Check if ALL pairs are covered by same-unit overrides
        eids = [e for e, _ in entries]
        bad_pairs = []
        for i in range(len(eids)):
            for j in range(i + 1, len(eids)):
                ga, gb = get_group(eids[i]), get_group(eids[j])
                if ga != gb and not same_override_group(eids[i], eids[j]):
                    bad_pairs.append((eids[i], eids[j]))
        if bad_pairs:
            issues.append(
                f"  DUPLICATE phrase across groups: \"{phrase_lower}\" -> {eids}"
            )

    return issues


# ---------------------------------------------------------------------------
# Pipeline runner (mirrors layout_creator.py)
# ---------------------------------------------------------------------------

def get_step_num(path):
    m = re.search(r'_step_(\d+)\.py$', path.name)
    return int(m.group(1)) if m else 0


def run_script(script_path, scene_num, retries=2):
    print(f"    -> {script_path.name} {scene_num}")
    for attempt in range(1, retries + 2):
        result = subprocess.run([sys.executable, str(script_path), str(scene_num)])
        if result.returncode == 0:
            return True
        print(f"    ERROR: {script_path.name} exited with code {result.returncode} "
              f"(attempt {attempt}/{retries+1})")
        if attempt <= retries:
            print(f"    Retrying...")
    return False


def main():
    start_scene = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    scene_dir = Path("assets/scene_prompts")
    if not scene_dir.exists():
        print(f"Error: {scene_dir} does not exist.")
        return

    scene_files = sorted(
        (
            p for p in scene_dir.glob("scene_*_prompt.json")
            if len(p.stem.split("_")) >= 2 and p.stem.split("_")[1].isdigit()
            and int(p.stem.split("_")[1]) >= start_scene
        ),
        key=lambda p: int(p.stem.split("_")[1])
    )

    if not scene_files:
        print(f"No scene prompt files found starting from scene {start_scene}.")
        return

    print(f"Processing {len(scene_files)} scene(s) from scene {start_scene}.")
    print("=" * 60)

    total_scenes   = 0
    scenes_ok      = 0
    scenes_issues  = 0

    for scene_file in scene_files:
        scene_num = int(scene_file.stem.split("_")[1])

        with open(scene_file, "r", encoding="utf-8") as f:
            scene_data = json.load(f)

        layout = scene_data.get("layout", "").strip()
        if not layout:
            print(f"\n[Scene {scene_num}] ERROR: No layout in {scene_file.name}. Skipping.")
            continue

        print(f"\n[Scene {scene_num}] Layout {layout}")

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
            print(f"  WARNING: {generator.name} not found.")

        # ── Audit the produced director script ─────────────────────────
        director_path = Path(f"assets/directorscript/scene_{scene_num}_director.json")
        total_scenes += 1

        if not director_path.exists():
            print(f"  AUDIT: director script not found!")
            scenes_issues += 1
        else:
            issues = audit_director(director_path)
            if issues:
                print(f"  AUDIT FAILED ({len(issues)} issue(s)):")
                for iss in issues:
                    print(iss)
                scenes_issues += 1
            else:
                print(f"  AUDIT OK - all phrases unique and non-empty")
                scenes_ok += 1

    print("\n" + "=" * 60)
    print(f"Done. {total_scenes} scene(s) processed.")
    print(f"  OK:     {scenes_ok}")
    print(f"  Issues: {scenes_issues}")


if __name__ == "__main__":
    main()
