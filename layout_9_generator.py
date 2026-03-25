"""
Layout 9 Generator — 2x2 Grid / Comic Panels
==============================================
Director space: 1920×1080

4 quadrant panels — each has 1 image (center of quadrant) + 1 short text label below.
Text scale computed from phrase length using approach.md formula (TEXT_SAFE_W = 900).
Deterministic seed for reproducibility.
"""

import json, os, random, re, sys

W, H    = 1920, 1080
RENDER  = 1024
IMG_SCALE = 0.28
IMG_SIZE  = RENDER * IMG_SCALE   # 286.72 px

# Quadrant centers — manually set to avoid overlap
Q_TL = {"x": int(W * 0.28), "y": 250}
Q_TR = {"x": int(W * 0.72), "y": 250}
Q_BL = {"x": int(W * 0.28), "y": 680}
Q_BR = {"x": int(W * 0.72), "y": 680}
QUADRANTS = [Q_TL, Q_TR, Q_BL, Q_BR]

# Text typography — approach.md formula
TEXT_SAFE_W = 900     # scene px available per quadrant (half canvas ≈ 960, minus buffers)
AVG_CHAR_W  = 30      # Comic Sans fontSize=40 at scale=1 — wider than average

TEXT_Y_OFFSET = int(IMG_SIZE / 2) + 60   # below image center


def _strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def allot_phrases(tokens, n_slots):
    """Split tokens proportionally into n_slots phrases.
    Returns list[str|None] — None means element gets no phrase and must be skipped."""
    n = len(tokens)
    if n == 0:
        return [None] * n_slots
    results = []
    t = 0
    for i in range(n_slots):
        remaining_tokens = n - t
        remaining_slots  = n_slots - i
        if remaining_tokens <= 0:
            results.append(None)
        else:
            give = max(1, remaining_tokens // remaining_slots)
            if i == n_slots - 1:
                give = remaining_tokens
            results.append(" ".join(tokens[t: t + give]))
            t += give
    return results


def compute_text_scale(phrase: str) -> float:
    n_chars = max(1, len(phrase))
    n_words = max(1, len(phrase.split()))
    preferred = min(2.5, 14.0 / n_words)
    safe      = TEXT_SAFE_W / (AVG_CHAR_W * n_chars)
    return round(max(1.0, min(preferred, safe)), 3)


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid       = f"scene_{scene_num}"
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    s2_path = f"assets/tmp/{sid}_layout_9_step_2_tmp.json"
    odir    = "assets/directorscript"
    opath   = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s2_path, encoding="utf-8") as f:
            step2 = json.load(f)
    except FileNotFoundError:
        print(f"Error: {s2_path} not found. Run Step 2 first.")
        return 1

    moments = step2.get("detailed_moments", [])
    if len(moments) == 0:
        print(f"Error: Layout 9 got 0 moments. Cannot proceed.")
        return 1
    if len(moments) < 4:
        print(f"   Warning: Layout 9 expects 4 moments, got {len(moments)}. Padding with duplicates.")
        while len(moments) < 4:
            moments.append(dict(moments[-1], moment_id=f"moment_{len(moments)+1}"))
    elif len(moments) > 4:
        print(f"   Warning: Layout 9 expects 4 moments, got {len(moments)}. Dropping extras.")
        moments = moments[:4]

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    # P1/P2 = moment1 img/txt, P3/P4 = moment2 img/txt, etc.
    _n_moments = min(4, len(moments))
    _total_slots = _n_moments * 2
    n_tokens = len(_tokens)
    n_active = min(_total_slots, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_total_slots} active slots")
    _phrases = allot_phrases(_tokens, n_active)
    # Pad with None so indices beyond n_active are skipped
    _phrases += [None] * (_total_slots - n_active)

    script = {"scene_id": sid, "elements": []}
    print("   Generating 2x2 Grid Layout...")

    for i, moment in enumerate(moments[:4]):
        _img_phrase = _phrases[i * 2] if (i * 2) < len(_phrases) else None
        _txt_phrase = _phrases[i * 2 + 1] if (i * 2 + 1) < len(_phrases) else None
        if _img_phrase is None and _txt_phrase is None:
            continue
        mid      = moment.get("moment_id", f"moment_{i + 1}")
        img_data = moment.get("image", {})
        txt_data = moment.get("text", {})
        q_pos    = QUADRANTS[i]
        txt_type   = txt_data.get("text_type", "text_highlighted")

        # ── Image ──────────────────────────────────────────────────────────
        if _img_phrase is not None:
            script["elements"].append({
                "element_id":  f"img_{mid}",
                "type":        "image",
                "phrase":      _img_phrase,
                "filename":    f"{mid}_img.jpg",
                "description": img_data.get("visual_description", ""),
                "x":           int(q_pos["x"]),
                "y":           int(q_pos["y"]),
                "scale":       IMG_SCALE,
                "angle":       0,
                "animation":   "pop",
                "property":    "shadow" if img_data.get("is_realistic") else "",
                "reason":      f"Grid panel {i + 1}",
                "text_content": ""
            })

        # ── Text label ─────────────────────────────────────────────────────
        if _txt_phrase is not None:
            txt_scale = compute_text_scale(_txt_phrase)
            script["elements"].append({
                "element_id":   f"txt_{mid}",
                "type":         txt_type,
                "phrase":       _txt_phrase,
                "text_content": _txt_phrase,
                "x":            int(q_pos["x"]),
                "y":            int(q_pos["y"]) + TEXT_Y_OFFSET,
                "scale":        txt_scale,
                "angle":        0,
                "animation":    "pop",
                "property":     "",
                "reason":       "Grid panel label",
                "filename":     "",
                "description":  ""
            })
            print(f"   Panel {i + 1}: {mid} | txt_scale={txt_scale} | '{_txt_phrase}'")

    with open(opath, "w") as f:
        json.dump(script, f, indent=2)

    total_el = len(script["elements"])
    num_imgs = sum(1 for e in script["elements"] if e["type"] == "image")
    print(f"\nSaved: {opath}")
    print(f"   {num_imgs} grid panels | {total_el} total elements")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
