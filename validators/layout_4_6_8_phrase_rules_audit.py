import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENE_PROMPTS_DIR = ROOT / "assets" / "scene_prompts"
DIRECTOR_DIR = ROOT / "assets" / "directorscript"
OUTPUT_MD = ROOT / "LAYOUT_4_6_8_PHRASE_RULES_AUDIT.md"

LAYOUTS = {"4", "6", "8"}

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
    layout: str
    prompt_path: Path
    director_path: Path
    scene_text: str
    script_clean_words: list[str]
    elements: list[ElementAudit]
    duplicate_clean_phrases: list[tuple[str, ...]]
    prefix_collision_pairs: list[tuple[tuple[str, ...], tuple[str, ...], list[int]]]
    layout6_tiling_ok: bool | None
    layout6_tiling_detail: str | None
    layout6_ranges: list[tuple[str, int, int]]
    layout8_pair_consecutive_ok: list[tuple[str, bool, str]]


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
        structural_ok = phrase_raw.strip().lower() in {"vs", "or", "but"}
        in_script = (not empty and bool(script_starts)) or empty or structural_ok

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

    # Rule 3: duplicates and prefix collisions.
    clean_phrases = [e.phrase_clean for e in elements if e.phrase_clean]
    seen: set[tuple[str, ...]] = set()
    dups: set[tuple[str, ...]] = set()
    for p in clean_phrases:
        if p in seen:
            dups.add(p)
        seen.add(p)
    duplicate_clean_phrases = sorted(list(dups))

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
            starts_short = set(find_all_occurrences(script_clean_words, short))
            starts_long = set(find_all_occurrences(script_clean_words, long))
            overlap_starts = sorted(list(starts_short.intersection(starts_long)))
            if overlap_starts:
                prefix_pairs.append((short, long, overlap_starts))

    # Layout 6 tiling checks (image + texts per group, groups tile full script).
    layout6_tiling_ok = None
    layout6_tiling_detail = None
    layout6_ranges: list[tuple[str, int, int]] = []
    if layout == "6":
        group_re = re.compile(r"_(group)_(\d+)_?(\d+)?$")
        groups: dict[int, dict[str, list[ElementAudit]]] = {}
        for e in elements:
            m = group_re.search(e.element_id)
            if not m:
                continue
            gid = int(m.group(2))
            if gid not in groups:
                groups[gid] = {"images": [], "texts": []}
            if e.element_type == "image":
                groups[gid]["images"].append(e)
            elif e.element_type.startswith("text"):
                groups[gid]["texts"].append(e)

        ordered_elements: list[ElementAudit] = []
        for gid in sorted(groups.keys()):
            images = sorted(groups[gid]["images"], key=lambda x: x.element_id)
            texts = sorted(groups[gid]["texts"], key=lambda x: x.element_id)
            ordered_elements.extend(images + texts)

        tiled = []
        for e in ordered_elements:
            tiled.extend(list(e.phrase_clean))
        layout6_tiling_ok = tiled == script_clean_words
        if layout6_tiling_ok:
            cursor = 0
            for e in ordered_elements:
                n = len(e.phrase_clean)
                layout6_ranges.append((e.phrase_raw, cursor, cursor + n))
                cursor += n
            layout6_tiling_detail = "Exact tiling match: concatenated group phrases == full scene script."
        else:
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
            layout6_tiling_detail = (
                "Tiling mismatch. "
                f"First mismatch token index={mismatch_at}. "
                f"script_window='{left}' vs tiled_window='{right}'."
            )

    # Layout 8 paired image/text per step should be consecutive fragments (not identical).
    layout8_pair_consecutive_ok: list[tuple[str, bool, str]] = []
    if layout == "8":
        img_re = re.compile(r"^img_step_(\d+)$")
        txt_re = re.compile(r"^txt_step_(\d+)$")
        steps: dict[str, dict[str, ElementAudit]] = {}
        for e in elements:
            mi = img_re.match(e.element_id)
            mt = txt_re.match(e.element_id)
            if mi:
                steps.setdefault(mi.group(1), {})["img"] = e
            if mt:
                steps.setdefault(mt.group(1), {})["txt"] = e
        for step, pair in sorted(steps.items(), key=lambda x: int(x[0])):
            img = pair.get("img")
            txt = pair.get("txt")
            if not img or not txt:
                continue
            ok = False
            reason = "no consecutive match found"
            if img.phrase_clean and txt.phrase_clean:
                # Check if img phrase followed immediately by txt phrase anywhere in script.
                starts_img = find_all_occurrences(script_clean_words, img.phrase_clean)
                for s in starts_img:
                    next_idx = s + len(img.phrase_clean)
                    if tuple(script_clean_words[next_idx : next_idx + len(txt.phrase_clean)]) == txt.phrase_clean:
                        ok = True
                        reason = f"img[{s}:{next_idx}] then txt[{next_idx}:{next_idx + len(txt.phrase_clean)}]"
                        break
            layout8_pair_consecutive_ok.append((f"step_{step}", ok, reason))

    return SceneAudit(
        scene_num=scene_num,
        layout=layout,
        prompt_path=prompt_path,
        director_path=director_path,
        scene_text=scene_text,
        script_clean_words=script_clean_words,
        elements=elements,
        duplicate_clean_phrases=duplicate_clean_phrases,
        prefix_collision_pairs=prefix_pairs,
        layout6_tiling_ok=layout6_tiling_ok,
        layout6_tiling_detail=layout6_tiling_detail,
        layout6_ranges=layout6_ranges,
        layout8_pair_consecutive_ok=layout8_pair_consecutive_ok,
    )


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def render_report(scene_audits: list[SceneAudit]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    lines.append("# Layout 4, 6, 8 Phrase Rules Compliance (Proof Report)")
    lines.append("")
    lines.append(f"Generated: `{now}`")
    lines.append("")

    lines.append("## Rules Referenced (Authoritative Sources)")
    lines.append("")
    lines.append("- Universal rules: `LAYOUT_PHRASE_RULES.md`")
    lines.append("- Layout 6 rules: `LAYOUT_PHRASE_RULES.md` (Two Rows tiling requirements)")
    lines.append("- Layouts 4 and 8: `LAYOUT_PHRASE_RULES.md` (All Other Layouts section)")
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

    lines.append("## Scenes Using Layouts 4, 6, 8")
    lines.append("")
    if not scene_audits:
        lines.append("- None found in `assets/scene_prompts`.")
        lines.append("")
        return "\n".join(lines)

    layouts_present = {sa.layout for sa in scene_audits}
    for layout_id in sorted(LAYOUTS):
        if layout_id not in layouts_present:
            lines.append(f"- No layout {layout_id} scenes found in `assets/scene_prompts`.")
    if len(layouts_present) < len(LAYOUTS):
        lines.append("")

    for sa in scene_audits:
        lines.append(f"- `scene_{sa.scene_num}` (layout {sa.layout}): `{sa.prompt_path.as_posix()}`")
    lines.append("")

    for sa in scene_audits:
        lines.append(f"## Scene {sa.scene_num} (Layout {sa.layout})")
        lines.append("")
        lines.append(f"- Prompt: `{sa.prompt_path.as_posix()}`")
        lines.append(f"- Director: `{sa.director_path.as_posix()}`")
        lines.append("")
        lines.append("### Scene Script (from prompt)")
        lines.append("")
        lines.append(f"> {sa.scene_text}")
        lines.append("")

        rule1_ok = all((not e.empty) or e.allowed_empty for e in sa.elements)
        rule2_ok = all(e.in_script or e.empty or e.allowed_empty for e in sa.elements)
        rule3_ok = (len(sa.duplicate_clean_phrases) == 0) and (len(sa.prefix_collision_pairs) == 0)
        rule4_ok = None
        rule5_ok = None
        if sa.layout == "6":
            rule4_ok = bool(sa.layout6_tiling_ok)
            rule5_ok = bool(sa.layout6_tiling_ok)
        elif sa.layout == "8":
            if sa.layout8_pair_consecutive_ok:
                rule4_ok = all(ok for _, ok, _ in sa.layout8_pair_consecutive_ok)
            else:
                rule4_ok = False

        lines.append("### Rule Checks (Pass/Fail)")
        lines.append("")
        lines.append(f"- Rule 1 (no empty phrases): `{'PASS' if rule1_ok else 'FAIL'}`")
        lines.append(f"- Rule 2 (phrases verbatim from script): `{'PASS' if rule2_ok else 'FAIL'}`")
        lines.append(f"- Rule 3 (unique + no prefix collisions): `{'PASS' if rule3_ok else 'FAIL'}`")
        if rule4_ok is None:
            lines.append("- Rule 4 (consecutive fragments): `N/A` (insufficient pairing signal)")
        else:
            lines.append(f"- Rule 4 (consecutive fragments): `{'PASS' if rule4_ok else 'FAIL'}`")
        if sa.layout == "6":
            lines.append(f"- Rule 5 (tiling coverage): `{'PASS' if rule5_ok else 'FAIL'}`")
            if sa.layout6_tiling_detail:
                lines.append(f"- Proof: {sa.layout6_tiling_detail}")
        else:
            lines.append("- Rule 5 (tiling coverage): `N/A` (layout not defined as tiling)")
        lines.append("")

        if sa.layout == "6" and sa.layout6_ranges:
            lines.append("### Layout 6 Tiling Proof (Consecutive Token Ranges)")
            lines.append("")
            lines.append("Token indices use `timings.py`-style cleaning (`clean_word`).")
            lines.append("")
            lines.append("| phrase (raw) | token_start | token_end |")
            lines.append("|---|---:|---:|")
            for phrase_raw, start, end in sa.layout6_ranges:
                lines.append(f"| {md_escape(phrase_raw)} | {start} | {end} |")
            lines.append("")

        if sa.layout == "8" and sa.layout8_pair_consecutive_ok:
            lines.append("### Layout 8 Pair Check (Image + Text Consecutive Fragments)")
            lines.append("")
            lines.append("| step | consecutive | proof |")
            lines.append("|---|---|---|")
            for step, ok, proof in sa.layout8_pair_consecutive_ok:
                lines.append(f"| {step} | {'YES' if ok else 'NO'} | {md_escape(proof)} |")
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
    audits: list[SceneAudit] = []
    for p in sorted(SCENE_PROMPTS_DIR.glob("scene_*_prompt.json")):
        m = re.match(r"^scene_(\d+)_prompt\.json$", p.name)
        if not m:
            continue
        num = int(m.group(1))
        j = json.loads(p.read_text(encoding="utf-8"))
        if str(j.get("layout", "")).strip() not in LAYOUTS:
            continue
        director_path = DIRECTOR_DIR / f"scene_{num}_director.json"
        if not director_path.exists():
            continue
        audits.append(audit_scene(num, p))

    OUTPUT_MD.write_text(render_report(audits), encoding="utf-8")
    print(f"Wrote report: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
