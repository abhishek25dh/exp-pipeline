import json
import os
import re
import sys


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

W, H = 1920, 1080
HOST_POS = (960, 560)
HOST_SCALE = 0.9
IMG_SCALE = 0.32
IMG_POSITIONS = [(300, 220), (300, 860), (1620, 220), (1620, 860)]
EMOTIONS = {"happy", "sad", "angry", "explaining"}


def safe_slug(text: str, max_len: int = 40) -> str:
    text = (text or "").strip()
    if not text:
        return "image"
    slug = re.sub(r"\s+", "_", text)
    slug = re.sub(r"[^A-Za-z0-9_'-]", "", slug)
    return slug[:max_len] or "image"


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    sid = f"scene_{scene_num}"

    s1_path = f"assets/tmp/{sid}_layout_7_step_1_tmp.json"
    s2_path = f"assets/tmp/{sid}_layout_7_step_2_tmp.json"
    odir = "assets/directorscript"
    opath = os.path.join(odir, f"{sid}_director.json")
    os.makedirs(odir, exist_ok=True)

    try:
        with open(s1_path, "r", encoding="utf-8") as f:
            step1 = json.load(f)
        with open(s2_path, "r", encoding="utf-8") as f:
            step2 = json.load(f)
    except FileNotFoundError:
        print(f"Error: Step 1 or Step 2 tmp JSON not found for {sid}. Run them first.")
        return 1

    host_emotion = str(step1.get("host_emotion", "explaining")).strip().lower()
    if host_emotion not in EMOTIONS:
        host_emotion = "explaining"

    groups = step2.get("detailed_groups", [])
    flattened = []
    for g in groups:
        for img in g.get("images", []):
            flattened.append(img)

    if len(flattened) != 4:
        print(f"Error: Layout 7 expects exactly 4 images from step 2, got {len(flattened)}.")
        return 1

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{sid}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()
    n_tokens = len(_tokens)
    # Priority-based dropping: P1=host (1 token), P2-P5=images (2 tokens each)
    n_active_imgs = min(4, max(0, (n_tokens - 1) // 2))
    n_active = 1 + n_active_imgs
    _phrases = allot_phrases(_tokens, n_active)
    _host_phrase = _phrases[0] or ""
    _img_phrases = (_phrases[1:] + [None] * 4)[:4]  # pad to 4, extras are None
    print(f"   Token budget: {n_tokens} tokens -> host + {n_active_imgs}/4 images active")

    script = {
        "scene_id": sid,
        "host_emotion": host_emotion,
        "host_phrase": _host_phrase,
        "elements": [],
    }

    script["elements"].append(
        {
            "element_id": f"host_center_{host_emotion}",
            "type": "host",
            "phrase": _host_phrase,
            "description": f"Host in center expressing {host_emotion}",
            "filename": f"host_{host_emotion}.png",
            "x": int(HOST_POS[0]),
            "y": int(HOST_POS[1]),
            "scale": HOST_SCALE,
            "angle": 0,
            "animation": "fade_in",
        }
    )

    for i, img in enumerate(flattened):
        _img_phrase = _img_phrases[i] if i < len(_img_phrases) else None
        if _img_phrase is None:
            continue
        visual = str(img.get("visual_description", "")).strip()
        span = img.get("span")
        filename = f"quad_{i}_{safe_slug(_img_phrase)}.jpg"
        script["elements"].append(
            {
                "element_id": f"image_quad_{i}",
                "type": "image",
                "phrase": _img_phrase,
                "visual_description": visual,
                "description": visual,
                "is_realistic": bool(img.get("is_realistic", True)),
                "filename": filename,
                "x": IMG_POSITIONS[i][0],
                "y": IMG_POSITIONS[i][1],
                "scale": IMG_SCALE,
                "angle": 0,
                "animation": "pop",
                "span": span,
            }
        )

    with open(opath, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"Saved: {opath}")
    print("  1 Host + 4 quad images")


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
