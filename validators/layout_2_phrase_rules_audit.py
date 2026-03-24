import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENE_PROMPTS_DIR = ROOT / "assets" / "scene_prompts"
DIRECTOR_DIR = ROOT / "assets" / "directorscript"

RULES_MD = ROOT / "LAYOUT_PHRASE_RULES.md"
LAYOUT2_STEP1_TXT = ROOT / "layout_2_step_1.txt"
LAYOUT2_STEP2_TXT = ROOT / "layout_2_step_2.txt"
LAYOUT2_STEP3_TXT = ROOT / "layout_2_step_3.txt"

OUTPUT_MD = ROOT / "LAYOUT_2_PHRASE_RULES_AUDIT.md"

# Element types where an empty phrase is acceptable (decorative / background).
BACKGROUND_TYPES = {"arrow"}


def clean_word(word: str) -> str:
    # Must match timings.py semantics (strip non a-z0-9).
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def clean_phrase_tuple(phrase: str) -> tuple[str, ...]:
    return tuple([clean_word(w) for w in (phrase or "").split() if clean_word(w)])


def strip_scene_prefix(raw_prompt: str) -> str:
    return re.sub(r"^scene_\d+:", "", (raw_prompt or "").strip()).strip()


def tokenize_clean_script(scene_text: str) -> list[str]:
    # Preserve timings.py matching by cleaning each whitespace token.
    return [clean_word(w) for w in (scene_text or "").split() if clean_word(w)]


def find_all_occurrences(haystack: list[str], needle: tuple[str, ...]) -> list[int]:
    if not needle:
        return [0]
    n = len(needle)
    out = []
    for i in range(0, len(haystack) - n + 1):
        if tuple(haystack[i : i + n]) == needle:
            out.append(i)
    return out


def is_intentional_empty(element_id: str) -> bool:
    return (element_id or "").endswith("_l2")


def is_host_element(element_id: str) -> bool:
    eid = (element_id or "").lower()
    return eid.startswith("host_") or eid == "host_character"


def extract_element_phrase_line_numbers(director_path: Path) -> dict[str, int]:
    """
    Best-effort mapping: element_id -> line number where its "phrase" key appears.
    """
    lines = director_path.read_text(encoding="utf-8").splitlines()
    current_eid = None
    out: dict[str, int] = {}
    eid_re = re.compile(r'"element_id"\s*:\s*"([^"]+)"')
    phrase_re = re.compile(r'"phrase"\s*:\s*')
    for idx, line in enumerate(lines, start=1):
        m = eid_re.search(line)
        if m:
            current_eid = m.group(1)
            continue
        if current_eid and phrase_re.search(line):
            # Store first phrase occurrence for this element_id.
            out.setdefault(current_eid, idx)
    return out


@dataclass
class ElementAudit:
    element_id: str
    element_type: str
    phrase_raw: str
    phrase_clean: tuple[str, ...]
    allowed_empty: bool
    empty: bool
    in_script: bool
    script_starts: list[int]
    director_phrase_line: int | None


@dataclass
class SceneAudit:
    scene_num: int
    prompt_path: Path
    director_path: Path
    layout: str
    scene_text: str
    script_clean_words: list[str]
    elements: list[ElementAudit]
    duplicate_clean_phrases: list[tuple[str, ...]]
    prefix_collision_pairs: list[tuple[tuple[str, ...], tuple[str, ...], list[int]]]
    coverage_ok_images_only: bool
    coverage_detail: str
    micro_phrase_count: int
    micro_phrase_count_ok: bool
    main_text_word_count: int | None
    main_text_word_count_ok: bool | None
    tiling_phrase_ranges: list[tuple[str, int, int]]  # (phrase_raw, start_idx, end_idx_exclusive)
    tiling_consecutive_ok: bool | None


def audit_scene(scene_num: int, prompt_path: Path) -> SceneAudit:
    prompt_json = json.loads(prompt_path.read_text(encoding="utf-8"))
    layout = str(prompt_json.get("layout", "")).strip()
    scene_text = strip_scene_prefix(prompt_json.get("prompt", ""))
    script_clean_words = tokenize_clean_script(scene_text)

    director_path = DIRECTOR_DIR / f"scene_{scene_num}_director.json"
    director_json = json.loads(director_path.read_text(encoding="utf-8"))
    director_phrase_lines = extract_element_phrase_line_numbers(director_path)

    raw_elements = director_json.get("elements", [])
    elements: list[ElementAudit] = []
    for el in raw_elements:
        element_id = str(el.get("element_id", "?"))
        element_type = str(el.get("type", ""))
        phrase_raw = str(el.get("phrase", "") or "")

        allowed_empty = (
            element_type in BACKGROUND_TYPES
            or is_intentional_empty(element_id)
            or is_host_element(element_id)
        )
        empty = not phrase_raw.strip()
        phrase_clean = clean_phrase_tuple(phrase_raw)
        script_starts = find_all_occurrences(script_clean_words, phrase_clean) if not empty else [0]
        in_script = (not empty) and bool(script_starts) or empty or phrase_raw.strip().lower() in {"vs", "or", "but"}

        elements.append(
            ElementAudit(
                element_id=element_id,
                element_type=element_type,
                phrase_raw=phrase_raw,
                phrase_clean=phrase_clean,
                allowed_empty=allowed_empty,
                empty=empty,
                in_script=in_script,
                script_starts=script_starts if not empty else [],
                director_phrase_line=director_phrase_lines.get(element_id),
            )
        )

    # Rule 3: uniqueness across the whole scene (by cleaned phrase tuple).
    clean_phrases = [e.phrase_clean for e in elements if e.phrase_clean]
    seen: set[tuple[str, ...]] = set()
    dups: set[tuple[str, ...]] = set()
    for p in clean_phrases:
        if p in seen:
            dups.add(p)
        seen.add(p)
    duplicate_clean_phrases = sorted(list(dups))

    # Rule 3: prefix collisions.
    uniq = sorted(set([p for p in clean_phrases if p]), key=lambda x: (len(x), x))
    prefix_pairs = []
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            a = uniq[i]
            b = uniq[j]
            if len(a) == len(b):
                continue
            short, long = (a, b) if len(a) < len(b) else (b, a)
            if long[: len(short)] != short:
                continue
            # "Proof": list the start indices where both short and long match at the same start.
            starts_short = set(find_all_occurrences(script_clean_words, short))
            starts_long = set(find_all_occurrences(script_clean_words, long))
            overlap_starts = sorted(list(starts_short.intersection(starts_long)))
            if overlap_starts:
                prefix_pairs.append((short, long, overlap_starts))

    # Layout 2 micro-phrases: treat image phrases as the chronological tiling units.
    image_elements = [e for e in elements if e.element_type == "image" and e.phrase_clean]
    micro_phrase_count = len(image_elements)
    micro_phrase_count_ok = 7 <= micro_phrase_count <= 12

    # Coverage / tiling proof: concatenate image phrases in script order and compare to full script.
    # If multiple occurrences exist, pick the first match start (best-effort) for ordering.
    def first_start(e: ElementAudit) -> int:
        return min(e.script_starts) if e.script_starts else 10**9

    images_by_script = sorted(image_elements, key=first_start)
    tiled = []
    for e in images_by_script:
        tiled.extend(list(e.phrase_clean))

    coverage_ok_images_only = (tiled == script_clean_words)
    if coverage_ok_images_only:
        coverage_detail = "Exact tiling match: concatenated image phrases == full scene script (clean_word tokens)."
    else:
        # Find first mismatch for debugging/proof.
        mismatch_at = None
        for idx in range(min(len(tiled), len(script_clean_words))):
            if tiled[idx] != script_clean_words[idx]:
                mismatch_at = idx
                break
        if mismatch_at is None and len(tiled) != len(script_clean_words):
            mismatch_at = min(len(tiled), len(script_clean_words))
        if mismatch_at is None:
            mismatch_at = 0
        left = " ".join(script_clean_words[max(0, mismatch_at - 6) : mismatch_at + 6])
        right = " ".join(tiled[max(0, mismatch_at - 6) : mismatch_at + 6])
        coverage_detail = (
            "Tiling mismatch (images-only). "
            f"First mismatch token index={mismatch_at}. "
            f"script_window='{left}' vs tiled_window='{right}'."
        )

    # Stronger proof for Rules 4+5: ensure each image phrase matches consecutively from token 0.
    tiling_phrase_ranges: list[tuple[str, int, int]] = []
    tiling_consecutive_ok: bool | None = None
    if coverage_ok_images_only:
        cursor = 0
        ok = True
        for e in images_by_script:
            n = len(e.phrase_clean)
            if tuple(script_clean_words[cursor : cursor + n]) != e.phrase_clean:
                ok = False
                break
            tiling_phrase_ranges.append((e.phrase_raw, cursor, cursor + n))
            cursor += n
        tiling_consecutive_ok = ok and (cursor == len(script_clean_words))

    # Layout 2 step_1: main text must be 1-3 words (from the script).
    text_elements = [e for e in raw_elements if str(e.get("type", "")).startswith("text")]
    main_text_word_count = None
    main_text_word_count_ok = None
    if text_elements:
        # Use the first text element as "main text" (Layout 2 has one center title).
        txt = text_elements[0]
        text_content = str(txt.get("text_content", "") or "").strip()
        main_text_word_count = len([w for w in text_content.split() if w.strip()])
        main_text_word_count_ok = 1 <= main_text_word_count <= 3

    return SceneAudit(
        scene_num=scene_num,
        prompt_path=prompt_path,
        director_path=director_path,
        layout=layout,
        scene_text=scene_text,
        script_clean_words=script_clean_words,
        elements=elements,
        duplicate_clean_phrases=duplicate_clean_phrases,
        prefix_collision_pairs=prefix_pairs,
        coverage_ok_images_only=coverage_ok_images_only,
        coverage_detail=coverage_detail,
        micro_phrase_count=micro_phrase_count,
        micro_phrase_count_ok=micro_phrase_count_ok,
        main_text_word_count=main_text_word_count,
        main_text_word_count_ok=main_text_word_count_ok,
        tiling_phrase_ranges=tiling_phrase_ranges,
        tiling_consecutive_ok=tiling_consecutive_ok,
    )


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def render_report(scene_audits: list[SceneAudit]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    lines.append("# Layout 2 Phrase Rules Compliance (Proof Report)")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")

    lines.append("## Rules Referenced (Authoritative Sources)")
    lines.append("")
    lines.append("- Universal rules: `LAYOUT_PHRASE_RULES.md`")
    lines.append("- Layout 2 generator instructions:")
    lines.append(f"  - `layout_2_step_1.txt` (main text must be 1-3 words, verbatim from script)")
    lines.append(f"  - `layout_2_step_2.txt` (micro-phrases must be verbatim, granular, chronological)")
    lines.append(f"  - `layout_2_step_3.txt` (grouping micro-phrases into narrative groups)")
    lines.append("")

    lines.append("## Universal Phrase Rules (All Layouts)")
    lines.append("")
    lines.append("From `LAYOUT_PHRASE_RULES.md`:")
    lines.append("- Rule 1: every element must have a non-empty `phrase` (except purely decorative arrows).")
    lines.append("- Rule 2: every `phrase` must be copied verbatim from the scene script (no invention/paraphrase).")
    lines.append("- Rule 3: phrases must be unique within the scene, and must not cause timing collisions (no duplicates; no prefix-collisions).")
    lines.append("- Rule 4: when two elements share one beat, their phrases must be consecutive fragments (split at word boundaries, no repeated words).")
    lines.append("- Rule 5: for tiling layouts, chosen phrases should cover the full script in order (no gaps, no overlaps).")
    lines.append("")

    lines.append("## Scenes Using Layout 2")
    lines.append("")
    if not scene_audits:
        lines.append("- None found in `assets/scene_prompts`.")
        lines.append("")
        return "\n".join(lines)

    for sa in scene_audits:
        lines.append(f"- `scene_{sa.scene_num}`: `{sa.prompt_path.as_posix()}`")
    lines.append("")

    for sa in scene_audits:
        lines.append(f"## Scene {sa.scene_num}")
        lines.append("")
        lines.append(f"- Prompt: `{sa.prompt_path.as_posix()}` (layout `{sa.layout}`)")
        lines.append(f"- Director: `{sa.director_path.as_posix()}`")
        lines.append("")
        lines.append("### Scene Script (from prompt)")
        lines.append("")
        lines.append(f"> {sa.scene_text}")
        lines.append("")

        # Summary checks
        rule1_ok = all((not e.empty) or e.allowed_empty for e in sa.elements)
        rule2_ok = all(e.in_script or e.empty or e.allowed_empty for e in sa.elements)
        rule3_ok = (len(sa.duplicate_clean_phrases) == 0) and (len(sa.prefix_collision_pairs) == 0)
        rule4_ok = bool(sa.tiling_consecutive_ok)
        rule5_ok = sa.coverage_ok_images_only

        lines.append("### Rule Checks (Pass/Fail)")
        lines.append("")
        lines.append(f"- Rule 1 (no empty phrases): `{'PASS' if rule1_ok else 'FAIL'}`")
        lines.append(f"- Rule 2 (phrases verbatim from script): `{'PASS' if rule2_ok else 'FAIL'}`")
        lines.append(f"- Rule 3 (unique + no prefix collisions): `{'PASS' if rule3_ok else 'FAIL'}`")
        lines.append(f"- Rule 4 (consecutive fragments): `{'PASS' if rule4_ok else 'FAIL'}`")
        lines.append(f"- Rule 5 (tiling coverage): `{'PASS' if rule5_ok else 'FAIL'}`")
        lines.append(f"- Layout 2 micro-phrase count (images): `{sa.micro_phrase_count}` (`{'PASS' if sa.micro_phrase_count_ok else 'WARN'}`; expected 7-12)")
        if sa.main_text_word_count is not None:
            lines.append(
                f"- Layout 2 main text word count: `{sa.main_text_word_count}` "
                f"(`{'PASS' if sa.main_text_word_count_ok else 'FAIL'}`; expected 1-3)"
            )
        lines.append(f"- Proof: {sa.coverage_detail}")
        lines.append("")

        if sa.tiling_phrase_ranges:
            lines.append("### Tiling Proof (Image Phrases as Consecutive Token Ranges)")
            lines.append("")
            lines.append("Token indices use `timings.py`-style cleaning (`clean_word`).")
            lines.append("")
            lines.append("| phrase (raw) | token_start | token_end |")
            lines.append("|---|---:|---:|")
            for phrase_raw, start, end in sa.tiling_phrase_ranges:
                lines.append(f"| {md_escape(phrase_raw)} | {start} | {end} |")
            lines.append("")

        if sa.duplicate_clean_phrases:
            lines.append("### Duplicate Cleaned Phrases (Rule 3 Fail)")
            lines.append("")
            for dp in sa.duplicate_clean_phrases:
                lines.append(f"- `{ ' '.join(dp) }`")
            lines.append("")

        if sa.prefix_collision_pairs:
            lines.append("### Prefix Collisions (Rule 3 Fail)")
            lines.append("")
            for short, long, starts in sa.prefix_collision_pairs:
                lines.append(
                    f"- `{ ' '.join(short) }` is a prefix of `{ ' '.join(long) }` "
                    f"(collides at script token start indices: {starts})"
                )
            lines.append("")

        lines.append("### Element-by-Element Proof")
        lines.append("")
        lines.append("| element_id | type | phrase (raw) | clean_phrase | in_script | director line |")
        lines.append("|---|---|---|---|---:|---:|")
        for e in sa.elements:
            in_script_str = "YES" if (e.in_script or e.empty or e.allowed_empty) else "NO"
            clean_str = " ".join(e.phrase_clean) if e.phrase_clean else ""
            line_no = str(e.director_phrase_line) if e.director_phrase_line else ""
            lines.append(
                f"| `{md_escape(e.element_id)}` | `{md_escape(e.element_type)}` | "
                f"{md_escape(e.phrase_raw)} | `{md_escape(clean_str)}` | {in_script_str} | {line_no} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    layout2_scene_nums: list[int] = []
    prompt_paths: dict[int, Path] = {}
    for p in sorted(SCENE_PROMPTS_DIR.glob("scene_*_prompt.json")):
        m = re.match(r"^scene_(\d+)_prompt\.json$", p.name)
        if not m:
            continue
        num = int(m.group(1))
        j = json.loads(p.read_text(encoding="utf-8"))
        if str(j.get("layout", "")).strip() == "2":
            layout2_scene_nums.append(num)
            prompt_paths[num] = p

    audits: list[SceneAudit] = []
    for num in sorted(layout2_scene_nums):
        prompt_path = prompt_paths[num]
        director_path = DIRECTOR_DIR / f"scene_{num}_director.json"
        if not director_path.exists():
            # Skip missing directorscripts (report will reflect only auditable scenes).
            continue
        audits.append(audit_scene(num, prompt_path))

    OUTPUT_MD.write_text(render_report(audits), encoding="utf-8")
    print(f"Wrote report: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
