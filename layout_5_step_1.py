import json
import math
import re
import sys
from pathlib import Path


# Layout 5 (Cause -> Effect) deterministic Step 1:
# Build groups whose phrases TILE the full script (no gaps / no overlaps).
# This fixes orphaned words and makes timings stable.

PUNCT_SENT_END = (".", "!", "?")

# Prefer these as arrow triggers when present near the split.
ARROW_CONNECTORS = {
    "or",
    "than",
    "because",
    "so",
    "then",
    "and",
    "but",
    "to",
    "into",
    "with",
    "without",
    "from",
    "before",
    "after",
    "while",
    "when",
    "until",
}


def strip_scene_prefix(prompt: str) -> str:
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", prompt or "", flags=re.I).strip()


def clean_word(word: str) -> str:
    # Match timings.py cleaning: lowercase + strip non-alnum.
    return re.sub(r"[^a-z0-9]", "", (word or "").lower())


def ends_sentence(tok: str) -> bool:
    t = (tok or "").rstrip()
    return bool(t) and t[-1] in PUNCT_SENT_END


def choose_group_count(n_tokens: int) -> int:
    # Cap at 2 groups max so images stay large enough to be visible.
    # Layout 5 strips are 3 elements wide (cause + arrow + effect); 4 groups = 12
    # canvas elements which forces images to ~0.07 rendered scale (invisible).
    # With 2 groups, images render at ~0.18 rendered scale (clearly visible).
    if n_tokens <= 16:
        return 1
    return 2


def partition_into_groups(tokens, k):
    """
    DP partition: choose k contiguous spans covering all tokens.
    Bias cuts to sentence boundaries and keep lengths balanced.
    Returns list of (start, end) spans (end is exclusive).
    """
    n = len(tokens)
    if k <= 1:
        return [(0, n)]

    target = n / float(k)

    # dp[g][i] = best cost to partition first i tokens into g groups.
    dp = [[math.inf] * (n + 1) for _ in range(k + 1)]
    prev = [[None] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0.0

    for g in range(1, k + 1):
        # Ensure at least 3 tokens per group (loose floor).
        for i in range(1, n + 1):
            best = math.inf
            best_j = None
            for j in range(0, i):
                if dp[g - 1][j] == math.inf:
                    continue
                seg_len = i - j
                if seg_len < 3:
                    continue

                cost = (seg_len - target) ** 2

                # Penalize very short / very long spans.
                if seg_len < 7:
                    cost += 18
                if seg_len > 22:
                    cost += 18 + (seg_len - 22) * 2

                # Prefer cutting at sentence ends (internal boundaries only).
                if i < n:
                    cost += 0 if ends_sentence(tokens[i - 1]) else 6

                cand = dp[g - 1][j] + cost
                if cand < best:
                    best = cand
                    best_j = j

            dp[g][i] = best
            prev[g][i] = best_j

    # Backtrack.
    spans = []
    i = n
    for g in range(k, 0, -1):
        j = prev[g][i]
        if j is None:
            # Fallback: single span if DP fails unexpectedly.
            return [(0, n)]
        spans.append((j, i))
        i = j
    spans.reverse()
    return spans


def choose_arrow_span(tokens, s, e):
    """
    Pick an arrow span [a0, a1) within [s, e) such that:
    - cause = [s, a0), arrow = [a0, a1), effect = [a1, e)
    - lengths are reasonable
    - arrow prefers connector words if present
    """
    n = e - s
    if n < 7:
        # Tiny group: force a 1-word arrow in the middle.
        a0 = s + max(2, n // 2)
        a1 = min(e - 2, a0 + 1)
        if a0 >= a1:
            a0 = max(s + 2, e - 3)
            a1 = a0 + 1
        return a0, a1

    min_cause = 3
    min_eff = 3
    max_arrow = 3

    mid = s + n / 2.0
    best = None
    best_score = -1e18

    for a0 in range(s + min_cause, e - min_eff):
        for alen in range(1, max_arrow + 1):
            a1 = a0 + alen
            if a1 > e - min_eff:
                continue
            cause_len = a0 - s
            eff_len = e - a1
            if cause_len < min_cause or eff_len < min_eff:
                continue

            span_words = [clean_word(t) for t in tokens[a0:a1]]
            span_words = [w for w in span_words if w]

            score = 0.0

            # Prefer starting the arrow at a sentence boundary (good "beat" marker).
            if a0 > s and ends_sentence(tokens[a0 - 1]):
                score += 12

            # Avoid splitting common collocations like "someone else".
            prev_w = clean_word(tokens[a0 - 1]) if a0 > s else ""
            cur_w = clean_word(tokens[a0]) if a0 < e else ""
            if prev_w in {"someone", "anyone", "everyone", "noone", "nobody"} and cur_w == "else":
                score -= 40

            # Prefer explicit transition words.
            if span_words:
                w0 = span_words[0]
                if w0 in {"or", "than", "because", "so"}:
                    score += 40
                elif w0 in ARROW_CONNECTORS:
                    score += 18
                if any(w in {"or", "than"} for w in span_words):
                    score += 10

            # Prefer near the middle of the group.
            center = (a0 + a1) / 2.0
            score -= abs(center - mid) * 0.9

            # Avoid arrow spans that end on a hard stop if possible (keeps effect cleaner).
            if tokens[a1 - 1].rstrip().endswith(","):
                score -= 4

            if score > best_score:
                best_score = score
                best = (a0, a1)

    if best is None:
        # Safe fallback.
        a0 = s + max(3, n // 2)
        a1 = min(e - 3, a0 + 1)
        return a0, a1
    return best


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"

    prompt_path = Path("assets/scene_prompts") / f"{scene_id}_prompt.json"
    if not prompt_path.exists():
        print(f"Error: missing {prompt_path}")
        return 1

    prompt_data = json.loads(prompt_path.read_text(encoding="utf-8"))
    scene_text = strip_scene_prefix(prompt_data.get("prompt", ""))

    tokens = scene_text.split()
    if not tokens:
        print("Error: empty scene text.")
        return 1

    k = choose_group_count(len(tokens))
    spans = partition_into_groups(tokens, k)

    # Build groups that tile exactly in order.
    groups = []
    for idx, (s, e) in enumerate(spans, start=1):
        a0, a1 = choose_arrow_span(tokens, s, e)
        cause = " ".join(tokens[s:a0]).strip()
        arrow = " ".join(tokens[a0:a1]).strip()
        effect = " ".join(tokens[a1:e]).strip()

        # Guardrails: never leave empty cause/effect; if it happens, push one token over.
        if not cause and s < a0:
            cause = tokens[s]
        if not effect and a1 < e:
            effect = tokens[a1]

        groups.append(
            {
                "group_id": f"group_{idx}",
                "cause_phrase": cause,
                "arrow_phrase": arrow,
                "effect_phrase": effect,
                "text_label": None,
            }
        )

    # Validate tiling: cleaned tuples must concatenate to script cleaned tuple.
    script_clean = [clean_word(t) for t in tokens if clean_word(t)]
    built_clean = []
    for g in groups:
        for key in ("cause_phrase", "arrow_phrase", "effect_phrase"):
            built_clean.extend([clean_word(w) for w in g[key].split() if clean_word(w)])
    if built_clean != script_clean:
        print("Error: layout_5_step_1 did not tile script tokens correctly.")
        return 1

    out = {
        "scene_id": scene_id,
        "layout": "5",
        "scene_text": scene_text,
        "groups": groups,
    }

    out_dir = Path("assets/tmp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{scene_id}_layout_5_step_1_tmp.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Step 1 complete. Saved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
