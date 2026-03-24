"""
Layout 9 Step 1 — Deterministic 4-Group Split
==============================================
Layout 9: 2×2 grid — 4 panels, each panel = 1 image + 1 short text label.

FULLY DETERMINISTIC — no AI calls.
Tokenizes script, splits into 4 balanced groups using DP (sentence-boundary biased).
Within each group: img_phrase = majority tokens, txt_phrase = last 2-3 tokens (short label).
Outputs {moments} for Step 2 to add AI image descriptions.
"""

import json
import math
import re
import sys
from pathlib import Path

PUNCT_END = (".", "!", "?")
TXT_MAX_TOKENS = 3   # short grid label — keeps it readable at scale


def strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def ends_sentence(tok):
    return bool(tok) and tok.rstrip()[-1] in PUNCT_END


def partition_into_4(tokens):
    """DP split into 4 balanced contiguous groups, biased to sentence boundaries."""
    n = len(tokens)
    if n < 8:
        # Fallback: equal chunks
        k = n // 4
        return [(0, k), (k, 2*k), (2*k, 3*k), (3*k, n)]

    target = n / 4.0
    INF = float("inf")
    # dp[i][k] = min cost to cover tokens[0:i] with k groups
    dp   = [[INF] * 5 for _ in range(n + 1)]
    back = [[None] * 5 for _ in range(n + 1)]
    dp[0][0] = 0.0

    for i in range(1, n + 1):
        for k in range(1, 5):
            for j in range(max(0, i - 20), i):   # cap segment search at 20 tokens
                if dp[j][k - 1] == INF:
                    continue
                seg = i - j
                cost = (seg - target) ** 2
                # Prefer segment ending at sentence boundary
                if not ends_sentence(tokens[i - 1]):
                    cost += 8
                val = dp[j][k - 1] + cost
                if val < dp[i][k]:
                    dp[i][k] = val
                    back[i][k] = j

    # Backtrack
    spans = []
    pos = n
    for k in range(4, 0, -1):
        start = back[pos][k]
        if start is None:
            # Fallback: equal split
            chunk = n // 4
            return [(0, chunk), (chunk, 2*chunk), (2*chunk, 3*chunk), (3*chunk, n)]
        spans.append((start, pos))
        pos = start
    spans.reverse()
    return spans


def assign_group_phrases(tokens, s, e):
    """
    Split group [s, e) into img_phrase (most tokens) + txt_phrase (last 2-3 tokens).
    txt_phrase is the short visible label; img_phrase fires the image.
    """
    n = e - s
    txt_len = min(TXT_MAX_TOKENS, max(2, n // 4))
    txt_len = max(1, min(txt_len, n - 2))   # img must have ≥ 2 tokens

    img_end = e - txt_len
    return (
        " ".join(tokens[s:img_end]), [s, img_end],
        " ".join(tokens[img_end:e]),  [img_end, e],
    )


def validate_tiling(tokens, moments):
    covered = []
    for m in moments:
        is_, ie = m["img_span"]
        ts_, te = m["txt_span"]
        covered.extend(tokens[is_:ie])
        covered.extend(tokens[ts_:te])
    return covered == tokens


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id  = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text  = strip_scene_prefix(prompt_data.get("prompt", ""))
    tokens      = scene_text.split()

    if len(tokens) < 1:
        print(f"Error: script too short for Layout 9 (need ≥1 tokens), got {len(tokens)}.")
        return 1

    # Priority allocation: use as many panels as tokens allow (min 2 tokens each).
    # P1=4 panels, fall back to 3, 2, or 1 panel(s) for very short scripts.
    if len(tokens) >= 8:
        n_panels = 4
    elif len(tokens) >= 6:
        n_panels = 3
    elif len(tokens) >= 4:
        n_panels = 2
    else:
        n_panels = 1

    if n_panels == 4:
        spans = partition_into_4(tokens)
    else:
        # Simple equal-chunk split for reduced panel counts
        n = len(tokens)
        k = n // n_panels
        r = n % n_panels
        spans = []
        pos = 0
        for i in range(n_panels):
            size = k + (1 if i < r else 0)
            spans.append((pos, pos + size))
            pos += size

    moments = []
    for idx, (s, e) in enumerate(spans, start=1):
        if e <= s:
            continue
        img_phrase, img_span, txt_phrase, txt_span = assign_group_phrases(tokens, s, e)
        moments.append({
            "moment_id":  f"moment_{idx}",
            "img_phrase": img_phrase,
            "img_span":   img_span,
            "txt_phrase": txt_phrase,
            "txt_span":   txt_span,
        })
    # Pad remaining moments with empty entries so downstream always sees 4
    for idx in range(len(moments) + 1, 5):
        moments.append({
            "moment_id":  f"moment_{idx}",
            "img_phrase": "",
            "img_span":   [0, 0],
            "txt_phrase": "",
            "txt_span":   [0, 0],
        })

    if not validate_tiling(tokens, [m for m in moments if m["img_phrase"] or m["txt_phrase"]]):
        print("Warning: tiling validation failed — continuing with best-effort output.")


    print(f"  Tokens: {len(tokens)}  |  4 moments:")
    for m in moments:
        print(f"    {m['moment_id']}: img='{m['img_phrase']}'  |  txt='{m['txt_phrase']}'")

    out = {
        "scene_id":   scene_id,
        "scene_text": scene_text,
        "tokens":     tokens,
        "moments":    moments,
    }
    out_dir  = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_9_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete -> {out_path}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main() or 0)
