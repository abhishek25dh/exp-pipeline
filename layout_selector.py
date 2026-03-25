import sys
import json
import os
import re
import argparse
import time
import requests
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
if not API_KEY:
    _kp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openrouter_key.txt')
    if os.path.exists(_kp):
        with open(_kp, encoding='utf-8') as _f:
            API_KEY = _f.read().strip()
MODEL   = "deepseek/deepseek-chat"

# ─── Minimum token counts per layout ─────────────────────────────────────────
# Below this threshold the layout's generator/steps will produce broken output.
# If a scene is too short for the chosen layout, we override to a simpler one.
MIN_TOKENS_FOR_LAYOUT = {
    "1": 4, "2": 4, "3": 2, "4": 4, "5": 6, "6": 4, "7": 4,
    "8": 6, "9": 4, "10": 6, "11": 6, "12": 4, "13": 4, "14": 6,
    "15": 4, "16": 6, "17": 4, "18": 6, "19": 6, "20": 6, "21": 4,
    "22": 2, "23": 4, "24": 4, "25": 4, "26": 4, "27": 4, "28": 4,
    "29": 4, "30": 4, "31": 4, "32": 4, "33": 4, "34": 6, "35": 4,
    "36": 4, "37": 4, "38": 4, "39": 4,
}
# Layouts safe for very short scenes (≤3 tokens)
SHORT_SCENE_FALLBACKS = ["22", "3", "21"]

# ─── Layout descriptions (used by AI to pick the right template) ─────────────
LAYOUT_DESCRIPTIONS = {
    "1":  "Image Collage: Multiple AI images in left/center/right column stacks with a collage feel. Best for visually-rich scenes with many examples; no on-screen text.",
    "2":  "Grouped Image Clusters: Images arranged in 1–8 thematic groups across the canvas. Best when the scene enumerates categories or themed groups of things; no text.",
    "3":  "Scattered Images (Full-Canvas): Image groups scattered randomly across the full canvas. Best for high-energy montage-style scenes with maximum visual density; no text.",
    "4":  "Host Corner + Scattered Images: Host image in a corner, title in opposite corner, images scattered in the middle. Best for casual narrator-driven scenes with multiple examples.",
    "5":  "Cause → Effect: 1–3 horizontal strips each showing [cause image] → [arrow] → [effect image]. Best for explicit causal statements like 'X leads to Y' or 'doing X causes Y'.",
    "6":  "Two Rows: Top row = image-left + text-right; bottom row = text-left + image-right. Best for two related but distinct concepts shown in parallel.",
    "7":  "Host Center + 4 Quadrant Images: Large host image at center with 4 AI images in the corners. Best for narrator explaining a concept with 4 surrounding visual examples.",
    "8":  "Timeline Path: 3–4 steps in a left-to-right zigzag, each with image + label. Best for step-by-step processes, sequences, or historical timelines.",
    "9":  "2×2 Comic Grid: 4 quadrants each with an image + keyword label below. Best for enumerating exactly 4 items, categories, or examples.",
    "10": "Macro to Micro: One large concept image left + 2–3 smaller detail images stacked right, with arrows. Best for one big idea + 2–3 supporting details.",
    "11": "Mind-Map Orbit: Core concept word large at center; 4–5 image+label nodes orbiting around it. Best for a central topic radiating into multiple connected sub-ideas.",
    "12": "VS Comparison: Screen split with a 'VS' divider; image+label on each side. Best for direct X vs Y comparisons or contrasting two behaviors or mindsets.",
    "13": "Staircase: 4 image+label pairs arranged as an ascending staircase bottom-left to top-right. Best for progressive improvement or 4-stage skill building.",
    "14": "Circular Flow: Center title + 4 image nodes at clock positions with connecting arrows. Best for ongoing cycles, feedback loops, or repeating processes.",
    "15": "Hero + Bullets: Large hero image on the left; section title + 3 bullet text items on the right. Best for one key claim supported by 3 reasons or facts.",
    "16": "Filmstrip: Title + subtitle + 5 images in a horizontal row + 5 captions. Best for nostalgia, memory sequences, or 'remember when' scenes (needs long scene text).",
    "17": "Triangle Triforce: 3 image+label pairs at triangle vertices; central concept in the middle. Best for exactly 3 interconnected pillars of a concept.",
    "18": "Polaroid Wall: Wall title + 4 polaroid-style rotated photos with captions. Best for nostalgic or memory-evoking scenes with 4 personal examples.",
    "19": "Pyramid Stack: Title top + 1 hero image + 2 supporting images + 3 keyword text labels forming a pyramid. Best for one big idea branching into multiple details.",
    "20": "Top Text + Arrows + Images: Large heading at top; 1–3 image groups below with arrows pointing down. Best for a punchy headline followed by 1–3 visual examples.",
    "21": "Text + Arrow + Image: Heading at top + one arrow + one image below. Best for short punchy statements with one key visual; also renders as text-only if scene is very short.",
    "22": "Text Only: Multiple text lines centered on canvas, no images. Best for rhetorical questions, emotional punchlines, or scenes where text IS the visual.",
    "23": "Hero + Supporting Images: Hero image (dominant) + 1–3 supporting images in flexible positions. Best for one main visual concept with a few supporting visuals; no text.",
    "24": "Two Images + Bottom Text: 1–2 images at top + text punchline at bottom. Best for 'show images first, then reveal the insight' structure.",
    "25": "Host Right + 4 Images Left: Static host on the right presenting a 2×2 image grid on the left. Best for narrator presenting 4 examples or evidence points.",
    "26": "Text Top-Left + Image Clusters: Text phrase top-left + 2 images below-left + 4 images in 2×2 grid right. Best for long scenes with one text anchor and many visual examples.",
    "27": "Host Center + Side Texts: Large host image center-screen; short text callout on the left and right. Best for narrator with two contrasting keyword phrases flanking each side.",
    "28": "Side-by-Side Images + Punchline Text: Two large images side by side; text punchline fires last at the bottom center. Best for visual comparison followed by a reveal conclusion.",
    "29": "Statement Stack (4 Lines): 4 text statements stacked vertically, alternating black/red text colors. Best for 4-point lists, rules, or declarative enumeration scenes.",
    "30": "Host Left + Image Right: Host/narrator on the left + single AI image on the right. Best for short explanatory scenes with one key visual.",
    "31": "Image → Arrow → Image + Label: Left image + center arrow + right image + text label top-right. Best for compact cause-effect with a labeled outcome.",
    "32": "Two Images (No Text): Two AI images placed symmetrically left and right, no text. Best for visual juxtaposition where images alone tell the story.",
    "33": "Heading + Visual Comparison: Text heading at top + left image → arrow → right image below. Best for a titled before/after or transition scene.",
    "34": "Multi-Element Complex (5 Slots): Image-left + image-right flanking; two center text phrases; one image at bottom. Best for long complex scenes with multiple visual and text anchors.",
    "35": "Host Left + Text Right: Static host left + text block on the right column. Best for narrator making a concise statement with key text visible on screen.",
    "36": "Host Right + Multi-Image + Text: Host right + left image + arrow + center image + text callout bottom-left. Best for complex narrator scenes with cause-effect and a keyword phrase.",
    "37": "6-Image Mosaic: 1 large center image + 2 left + 3 right images; no text. Best for scenes with many visual examples and no text needed.",
    "38": "Text First + Two Images: Text punchline fires FIRST at bottom; then two images appear. Best for punchline-first scenes where the statement precedes visual evidence.",
    "39": "Image Grid + Bullet Text List: 2×2 image grid on the left + 4 text bullet rows on the right. Best for enumeration scenes with both visual examples and text bullets.",
}

# ─── System prompts ────────────────────────────────────────────────────────────
SCENE_BREAK_SYSTEM = """You are a scene structure expert for explainer videos.
Your task is to break a paragraph into scenes for an explainer video.

RULES:
1. Each scene uses EXACT consecutive text from the original paragraph. No paraphrasing, no reordering, no inserting words.
2. You may split at ANY natural pause point: sentence endings (. ! ?), or clause boundaries (comma, semicolon, colon, em-dash) when the clause forms a meaningful standalone unit.
3. Each scene must be 320 characters or fewer. If adding the next clause or sentence would exceed 320 characters, start a new scene instead.
4. If a single sentence is already over 320 characters, it still gets its own scene — do NOT truncate it.
5. A scene can be as short as a comma-ending phrase (e.g. "For example,") or as long as 3 sentences. Aim for 1–3 sentences; never group more than 3 sentences together.
6. Group thematically related consecutive clauses/sentences into the same scene only when they are tightly linked in meaning. Prefer shorter scenes when in doubt.
7. Output MUST be valid JSON only. No extra text, no markdown.

OUTPUT FORMAT MUST BE EXACTLY:
{
  "scenes": [
    {"scene_text": "Exact text from the paragraph."},
    {"scene_text": "More exact text from the paragraph."}
  ]
}"""

LAYOUT_ASSIGN_SYSTEM = """You are a layout expert for explainer videos.
Given a list of scenes, assign the best visual layout template to each scene.

AVAILABLE LAYOUTS (use ONLY the NUMBER as the identifier):
{layout_descriptions}

SCENE LENGTH GUIDANCE (use character count to judge):
- Very short (≤50 chars, e.g. a single phrase or clause): prefer layouts 21, 22, 38
- Short (≤100 chars): prefer layouts 21, 22, 24, 30, 32, 38
- Short/Medium (80–180 chars): prefer layouts 5, 12, 20, 21, 28, 31, 33, 35
- Medium (100–220 chars): prefer layouts 6, 9, 10, 13, 14, 17, 23, 24, 25, 27, 28
- Medium/Long (150–280 chars): prefer layouts 7, 11, 15, 18, 19, 20, 29, 34, 36
- Long (200–320 chars): prefer layouts 8, 16, 26, 29, 34, 36, 37, 39
- Any length: prefer layouts 1, 2, 3, 4, 20, 22

CONTENT TYPE GUIDANCE:
- Hook / single statement → 21, 22, 38
- Cause → Effect → 5, 31, 33
- Two contrasts / VS → 12, 28, 32, 6
- Three pillars → 17
- Four items / examples → 9, 18, 11, 39
- Five+ items / enumeration → 29, 15, 16, 37
- Step-by-step process → 8, 13
- Cycles / loops → 14
- One big idea + details → 10, 15
- Narrator-driven → 4, 7, 25, 27, 30, 35, 36
- Nostalgic / memories → 16, 18
- Pure visuals (no text needed) → 1, 2, 3, 23, 32, 37
- Text-dominant → 22, 29
- Text + visuals combined → 20, 24, 26, 39

RULES:
1. Match the layout to the scene content — pick the layout whose structure best fits what the scene is saying.
2. Consider both narrative tone and scene length — a short scene with a single statement fits layout 21 or 22; a long enumeration fits 29 or 39.
3. For each scene return your TOP 3 layout NUMBERS ranked from best to worst (used as fallbacks).
4. Layouts should feel varied across the video — avoid assigning the same layout to consecutive scenes.
5. "ranked_layouts" values MUST be the layout NUMBER as a string (e.g. "16", "18", "3") — NOT the layout name.
6. Output MUST be valid JSON only. No extra text, no markdown.

OUTPUT FORMAT MUST BE EXACTLY:
{{
  "assignments": [
    {{"scene_index": 0, "ranked_layouts": ["16", "3", "15"]}},
    {{"scene_index": 1, "ranked_layouts": ["12", "2", "10"]}}
  ]
}}"""


def clean_json_response(content):
    content = content.strip()
    start = content.find('{')
    end   = content.rfind('}')
    if start != -1 and end != -1:
        content = content[start:end+1]
    return content.strip()


def call_api(system_prompt, user_content):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    fallback_models = [
        m.strip()
        for m in os.getenv(
            "OPENROUTER_MODEL_FALLBACKS",
            f"{MODEL},deepseek/deepseek-v3.2,openai/gpt-4o-mini",
        ).split(",")
        if m.strip()
    ]
    models = [MODEL] + [m for m in fallback_models if m != MODEL]

    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        }

        for attempt in range(1, 5):
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90,
                )
            except Exception as e:
                wait_s = min(2 ** attempt, 10)
                print(f"Network error on {model} (attempt {attempt}/4): {e}. Retrying in {wait_s}s...")
                time.sleep(wait_s)
                continue

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']

            if response.status_code in (429, 500, 502, 503, 504):
                wait_s = min(2 ** attempt, 10)
                print(
                    f"API Error {response.status_code} on {model} "
                    f"(attempt {attempt}/4). Retrying in {wait_s}s..."
                )
                print(response.text[:300])
                time.sleep(wait_s)
                continue

            print(f"API Error {response.status_code} on {model}: {response.text}")
            break

        print(f"Switching model fallback after failures: {model}")

    return None


def parse_exclude(raw):
    if not raw:
        return set()
    parts = re.split(r"[,\s]+", raw.strip())
    out = set()
    for p in parts:
        if not p:
            continue
        if p.isdigit():
            out.add(p)
    return out


LAYOUT_HISTORY_FILE = "layout_history.json"


def load_layout_history(out_dir):
    """Return ordered list of (scene_num, layout) tuples from history file."""
    path = out_dir / LAYOUT_HISTORY_FILE
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return sorted(
                [(int(e["scene"]), str(e["layout"]))
                 for e in data.get("history", [])
                 if e.get("layout")],
                key=lambda x: x[0],
            )
        except Exception:
            pass
    return []


def save_layout_history(out_dir, new_entries):
    """Merge new (scene_num, layout) pairs into history file."""
    path = out_dir / LAYOUT_HISTORY_FILE
    history = {sn: lay for sn, lay in load_layout_history(out_dir)}
    for sn, lay in new_entries:
        if lay:
            history[sn] = lay
    ordered = sorted(history.items())
    path.write_text(
        json.dumps({"history": [{"scene": sn, "layout": lay} for sn, lay in ordered]}, indent=2),
        encoding="utf-8",
    )


def get_layout_counts(out_dir, allowed):
    counts = {k: 0 for k in allowed}
    for p in out_dir.glob("scene_*_prompt.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            layout = str(data.get("layout", "")).strip()
            if layout in counts:
                counts[layout] += 1
        except Exception:
            pass
    return counts


def pick_layout(ranked_choices, used_layouts, layout_counts, allowed):
    """Pick a layout enforcing no-repeat within the last 13 scenes (hard constraint).

    Priority order:
    1. Never-used layouts in AI's ranked choices, not in last 13.
    2. AI-ranked choices not in last 13, prefer least-used.
    3. ANY allowed layout not in last 13 — expands beyond AI's choices when they are all recent.
    4. Hard fallback only: all layouts exhausted in window; pick least-used AI choice.
    """
    allowed_set = set(allowed)
    last13 = set(used_layouts[-13:])
    ranked_allowed = [l for l in ranked_choices if l in allowed_set]

    def rank_idx(l):
        return ranked_choices.index(l) if l in ranked_choices else 99

    # 1. Never-used + AI-ranked + not recent
    never_used_ranked = [
        l for l in ranked_allowed
        if layout_counts.get(l, 0) == 0 and l not in last13
    ]
    if never_used_ranked:
        return never_used_ranked[0]

    # 2. AI-ranked not in last 13
    ranked_non_recent = [l for l in ranked_allowed if l not in last13]
    if ranked_non_recent:
        return min(ranked_non_recent, key=lambda l: (layout_counts.get(l, 0), rank_idx(l)))

    # 3. Expand to ALL allowed layouts not in last 13 (breaks AI's narrow repetition)
    all_non_recent = [l for l in sorted(allowed_set, key=int) if l not in last13]
    if all_non_recent:
        return min(all_non_recent, key=lambda l: (layout_counts.get(l, 0), rank_idx(l)))

    # 4. Hard fallback: recency window fully exhausted — pick least-used AI choice
    candidates = ranked_allowed or sorted(allowed_set, key=int)
    return min(candidates, key=lambda l: (layout_counts.get(l, 0), rank_idx(l)))


def main():
    parser = argparse.ArgumentParser(description="Layout selector")
    parser.add_argument("para_id", nargs="?", default="1")
    parser.add_argument("start_override", nargs="?", type=int, default=None)
    parser.add_argument("--exclude", "--avoid", dest="exclude", default="")
    args = parser.parse_args()

    para_id = args.para_id
    start_override = args.start_override  # optional: force start scene

    env_exclude = os.getenv("LAYOUT_EXCLUDE", "")
    exclude_set = parse_exclude(env_exclude) | parse_exclude(args.exclude)

    para_file = Path(f"assets/para/para_{para_id}.json")
    if not para_file.exists():
        print(f"Error: {para_file} not found.")
        return 1

    with open(para_file, "r", encoding="utf-8") as f:
        para_data = json.load(f)

    para_key  = f"para_{para_id}"
    para_text = para_data.get(para_key, "")
    if not para_text:
        print(f"Error: Key '{para_key}' not found in {para_file}")
        return 1

    print(f"Para {para_id} loaded ({len(para_text)} chars)")
    print(f"Text: {para_text[:80]}...")
    if not API_KEY:
        print("Error: OPENROUTER_API_KEY is not set.")
        sys.exit(1)

    # ── CALL 1: Break paragraph into scenes ───────────────────────────────────
    print("\n[Step 1] Calling API: Scene breaker...")
    raw1 = call_api(SCENE_BREAK_SYSTEM, f"Paragraph:\n{para_text}")
    if not raw1:
        sys.exit(1)

    try:
        scenes_data = json.loads(clean_json_response(raw1))
        scenes = [s["scene_text"] for s in scenes_data["scenes"]]
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Scene break parse error: {e}")
        print("Raw response:", raw1)
        return

    print(f"Broke into {len(scenes)} scenes:")
    for i, s in enumerate(scenes):
        print(f"  Scene {i+1} ({len(s)} chars): {s[:70]}{'...' if len(s) > 70 else ''}")

    # ── CALL 2: Assign layouts to each scene ──────────────────────────────────
    allowed_layouts = [k for k in sorted(LAYOUT_DESCRIPTIONS.keys(), key=int) if k not in exclude_set]
    if not allowed_layouts:
        allowed_layouts = sorted(LAYOUT_DESCRIPTIONS.keys(), key=int)
    layout_desc_text = "\n".join(f"{k}: {LAYOUT_DESCRIPTIONS[k]}" for k in allowed_layouts)
    system2 = LAYOUT_ASSIGN_SYSTEM.format(layout_descriptions=layout_desc_text)
    if exclude_set:
        system2 += f"\n\nEXCLUDED LAYOUTS: {sorted(exclude_set)}. Do not use them."

    scenes_payload = json.dumps(
        [{"scene_index": i, "scene_text": t} for i, t in enumerate(scenes)],
        indent=2
    )

    print("\n[Step 2] Calling API: Layout assignment...")
    raw2 = call_api(system2, f"Scenes:\n{scenes_payload}")
    if not raw2:
        sys.exit(1)

    try:
        assign_data  = json.loads(clean_json_response(raw2))
        assignments  = {a["scene_index"]: a["ranked_layouts"] for a in assign_data["assignments"]}
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Layout assign parse error: {e}")
        print("Raw response:", raw2)
        return

    # ── Apply last-5 constraint & write scene_prompt files ────────────────────
    out_dir = Path("assets/scene_prompts")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Find all existing scene files and which para they belong to
    all_scene_nums = sorted(
        int(p.stem.split("_")[1])
        for p in out_dir.glob("scene_*_prompt.json")
        if p.stem.split("_")[1].isdigit()
    )

    # Check if any existing scenes already belong to THIS para (by stored para_id field)
    this_para_scenes = []
    for sn in all_scene_nums:
        try:
            with open(out_dir / f"scene_{sn}_prompt.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("para_id") == para_id:
                    this_para_scenes.append(sn)
        except Exception:
            pass

    if start_override:
        start_scene = start_override
        print(f"Starting from scene {start_scene} (manual override).")
    elif this_para_scenes:
        # Overwrite the same scene range we used before for this para
        start_scene = this_para_scenes[0]
        print(f"Para {para_id} previously occupied scenes {this_para_scenes[0]}-{this_para_scenes[-1]}. Regenerating in place.")
    else:
        # Fresh para — always start from scene_1 if folder empty, else after last existing scene
        start_scene = (all_scene_nums[-1] + 1) if all_scene_nums else 1
        if all_scene_nums:
            print(f"No existing scenes for para {para_id}. Continuing from scene {start_scene} (after existing scenes).")
        else:
            print(f"Scene folder empty. Starting from scene 1.")

    # Seed used_layouts from the last 13 scenes BEFORE this para's range (for the no-repeat rule).
    # Primary source: layout_history.json (robust, no missing-field gaps).
    # Fallback: read individual scene files (first run before history exists).
    history = load_layout_history(out_dir)
    hist_before = [(sn, lay) for sn, lay in history if sn < start_scene]
    used_layouts = [lay for _, lay in hist_before[-13:]]

    if len(used_layouts) < 13:
        # History sparse or missing — supplement from scene files (skip any already covered).
        covered = {sn for sn, _ in hist_before}
        scenes_before = sorted(sn for sn in all_scene_nums if sn < start_scene and sn not in covered)
        extra = []
        for sn in scenes_before:
            try:
                with open(out_dir / f"scene_{sn}_prompt.json", "r", encoding="utf-8") as f:
                    lay = str(json.load(f).get("layout", "")).strip()
                    if lay:
                        extra.append((sn, lay))
            except Exception:
                pass
        # Merge with history entries and take last 13 before start_scene
        all_before = sorted(hist_before + extra, key=lambda x: x[0])
        used_layouts = [lay for _, lay in all_before[-13:]]

    # Layout usage counts for balancing (exclude this para's existing scenes if regenerating)
    layout_counts = get_layout_counts(out_dir, set(allowed_layouts))
    if this_para_scenes:
        for sn in this_para_scenes:
            try:
                with open(out_dir / f"scene_{sn}_prompt.json", "r", encoding="utf-8") as f:
                    prev_layout = str(json.load(f).get("layout", "")).strip()
                    if prev_layout in layout_counts:
                        layout_counts[prev_layout] = max(0, layout_counts[prev_layout] - 1)
            except Exception:
                pass

    print()
    new_history_entries = []
    for i, scene_text in enumerate(scenes):
        scene_num = start_scene + i
        ranked    = assignments.get(i, ["1", "3", "15"])
        layout    = pick_layout(ranked, used_layouts, layout_counts, set(allowed_layouts))

        # ── Token-count guard: override layout if scene is too short ──────
        n_tokens = len(scene_text.split())
        min_needed = MIN_TOKENS_FOR_LAYOUT.get(layout, 4)
        if n_tokens < min_needed:
            original = layout
            # Try ranked choices that fit
            for alt in ranked:
                if alt in allowed_layouts and n_tokens >= MIN_TOKENS_FOR_LAYOUT.get(alt, 4):
                    layout = alt
                    break
            else:
                # None of AI's choices fit — pick safest short-scene layout
                for fb in SHORT_SCENE_FALLBACKS:
                    if fb in allowed_layouts and n_tokens >= MIN_TOKENS_FOR_LAYOUT.get(fb, 4):
                        layout = fb
                        break
            if layout != original:
                print(f"  ⚠ Scene {scene_num}: {n_tokens} tokens too few for layout {original} (needs {min_needed}), overriding to layout {layout}")

        used_layouts.append(layout)
        if layout in layout_counts:
            layout_counts[layout] += 1

        new_history_entries.append((scene_num, layout))

        scene_id    = f"scene_{scene_num}"
        prompt_text = f"{scene_id}:{scene_text}"

        out_data = {
            "prompt": prompt_text,
            "layout": layout,
            "para_id": para_id
        }

        out_file = out_dir / f"{scene_id}_prompt.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=4)

        ai_top   = ranked[0] if ranked else "?"
        fallback = " (fallback)" if layout != ai_top else ""
        print(f"  {out_file}  ->  layout {layout}{fallback}  |  AI ranked: {ranked}")

    # Persist layout history so future para runs seed correctly even across pipeline invocations.
    save_layout_history(out_dir, new_history_entries)

    print(f"\nDone! {len(scenes)} scene prompts written to assets/scene_prompts/")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
