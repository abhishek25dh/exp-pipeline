# Universal Phrase Rules — All Layouts

## Why This Matters
Every element in every layout fires (appears on screen) when its `phrase` is spoken in the voiceover.
- If two elements share the same phrase → both fire at the same time → visual conflict.
- If an element has an empty phrase → it NEVER appears.
- If a phrase is invented (not in the script) → it NEVER fires.

---

## The 5 Non-Negotiable Rules

### 1. Every Element Must Have a Phrase
No element may have `phrase: ""` — except arrows in layouts where arrows are purely decorative
and have no timing requirement. If an arrow needs to appear at a specific moment, it MUST
have a phrase. Prefer giving arrows a phrase (the transition words spoken just before the
element they point to appears).

**Host characters are NOT exempt.** `"phrase": "Host"` is FORBIDDEN — "Host" is not in the
script so the host will never appear on screen. The host must receive a unique verbatim phrase
from the script. Best practice: assign the host the **first token(s) of the script** as its
phrase (P0 priority) so it appears immediately when the scene starts. This token must be carved
out of the first image span — no element other than the host may start at that same token.

### 2. Every Phrase Must Be Verbatim from the Script
Copy exact words. Never paraphrase, summarize, or invent.
- WRONG: `"Adaptability is key"` when script says `"This adaptability is a big part of your psychology."`
- RIGHT: `"big part of your psychology"`

### 2B. text_content Must Also Be Verbatim from the Script
`text_content` is what the viewer **reads on screen**. It must be a word or short phrase
the speaker actually says — never an AI-invented label, summary, or paraphrase.

The viewer reads what the speaker says. If the screen shows a word not in the audio, the
experience breaks. There is no exception for "descriptive labels", "narrative focus keywords",
or "conceptual summaries" — all are forbidden.

- WRONG: script says `"your whole life"`, text_content = `"Lifetime"` (AI-invented)
- WRONG: script says `"it might feel natural"`, text_content = `"Unconscious"` (AI-invented)
- RIGHT: text_content = `"life"` (verbatim word from the script)
- RIGHT: text_content = `"natural"` (verbatim word from the script)

`text_content` may be shorter than `phrase` (e.g. phrase triggers on `"your whole life"`,
text_content shows just `"life"`) — but it must still be a word that exists in the script.

`text_content` must be derived from the element's own phrase span — never pulled from a
longer span stored in step_1 data. If step_1 stores a full sentence as `text_content` but
the element's phrase only covers part of that sentence, the generator must use the phrase
span (or a verbatim subset of it) as `text_content`, not the step_1 value. Showing words
beyond the phrase span means displaying text the speaker hasn't said yet.

### 3. Every Phrase Must Be Unique Across the Entire Scene
Phrases can share words. The real requirement is: phrases must not create timing collisions.
The timing generator (`timings.py`) matches phrases as an exact sequence of cleaned words
(lowercased, punctuation removed; e.g. `"don't"` becomes `"dont"`).

- OK: Shared words across different phrases (e.g. `you don't need validation` vs `you don't need constant plans`).
- WRONG: Exact duplicates after cleaning (same words in the same order) unless the script repeats it and you intend multiple matches.
- WRONG: Prefix collisions where one phrase is the first part of another (e.g. `shaped your brain` and `shaped your brain in a big way`) -- both fire at the same start word.
- FIX: Pick different sequences, or split into consecutive halves per Rule 4.

### 4. Consecutive Fragments — Split at Word Boundaries
When two elements represent the same visual moment (e.g. image + caption, image + label,
arrow + image), their phrases must be CONSECUTIVE parts of the script, split at a word boundary.
- WRONG: `img="hoped their parents"` cap=`"hoped their parents didn't answer"` — repeated words
- RIGHT: `img="hoped their parents"` cap=`"didn't answer"`

### 5. Coverage — Required for Tiling Layouts, Optional for Sparse Layouts
For tiling layouts (where the design is meant to track the narration), element phrases must
cover the full script in order, with no gaps and no overlaps.

For sparse layouts (where the design intentionally visualizes only a few key beats), full
coverage is not required. However:
- Don't omit meaning-critical operators from the chosen phrases (negations like "not", comparators like "than",
  quantities like "two", "15", etc.).
- Prefer covering the most narrative-important phrases, and avoid leaving the ending tagline orphaned if possible.

---

## Per-Layout Element → Phrase Mapping

### Layout 5 (Cause → Effect)
Each group: `cause` (image) + `arrow_phrase` (arrow) + `effect` (image) + optional `text_label`.
This layout is a TILING layout: all group phrases must cover the full script in order, with no gaps and no overlaps.
All phrases must still be verbatim, and avoid timing collisions (Rule 3). The arrow_phrase must be different from
the cause/effect phrases.

### Layout 10 (Macro & Micro)
Each macro: `img_phrase` (image) + `txt_phrase` (title text) — 2 consecutive fragments.
Each micro: `arrow_phrase` (arrow) + `img_phrase` (image) + `txt_phrase` (label) — 3 consecutive fragments.
The arrow fires FIRST (transition cue), then image, then label as the narrator speaks through the concept.

### Layout 15 (Hero + Bullets)
`hero_phrase` (image) + `section_title` (header text) + 3× bullet `text` + optional `cta`.
All 5-6 phrases must tile the script with no gaps and no overlaps.
If the script is too short to supply a unique cta, set cta="" rather than invent one.

### Layout 16 (Filmstrip)
`strip_title` (3-5 words from start of script) + `strip_subtitle` (4-7 words from end) +
5 frames each with `img_phrase` (first half) + `cap_phrase` (second half).
12 unique phrases total. strip_title and strip_subtitle must not overlap with any frame phrase.

### Layout 6 (Two Rows)
Each group: `img_phrase` (image) + 1-3 `text_content` texts — all consecutive, no overlaps.
Image fires FIRST (img_phrase), then texts in order. Max 3 texts per group — keep each text
≤5 words to avoid canvas overflow at scale 1.6. If the second sentence is long, break it into
2-3 text elements rather than one long text. Together both groups must tile the full script.

### Layout 12 (VS / Comparison)
`title` + `vs_label` + `img_left` (= left.concept) + `label_left` + `sub_left` + `img_right`
(= right.concept) + `label_right` + `sub_right`. label must differ in content words from concept.
If script too short for sub descriptors, set descriptor="" to skip cleanly.

### Layout 18 (Polaroid Wall)
`wall_title` (from step 1) + 4 polaroids each with `img_phrase` + `cap_phrase` — 9 phrases total.
All 9 must be unique. Together they must tile the full script.

### All Other Layouts
Every text element gets its own unique phrase fragment from the script.
Every image element gets its own unique phrase fragment from the script.
Every arrow element gets an `arrow_phrase` from the script — the transition words spoken just
before the element it connects to appears.

### 6. Text Element Phrases Must Be Independently Readable

A text element appears alone on screen. Its phrase must make complete sense in isolation — no dangling clauses, no unfinished thoughts.

**Rule A — No crossing sentence boundaries:**
A text phrase must NEVER span two sentences.
`"risk embarrassment. But"` is wrong — it ends sentence 1 mid-phrase and starts sentence 2.
A text phrase must belong entirely to ONE sentence (or multiple complete sentences).
If the phrase contains a `.` `!` or `?` in the middle (not at the end), it is crossing sentences — reject it.

**Rule B — Must end at a sentence boundary (`.`, `!`, `?`).**

This applies to:
- Heading / top-text elements (layout 20, 21, 26, etc.) — fires first as the visual headline
- Anchor / bottom-text elements (layout 24, etc.) — fires last as the punchline
- Any standalone text element in any layout

**Implementation pattern (for text that fires first):**
```python
def find_text_end_sentence(tokens, target, max_end):
    # Search FORWARD — but cap at target+5 to prevent grabbing too many tokens.
    # If the next sentence end is more than 5 tokens away, use the PREVIOUS sentence
    # end instead. This keeps text visually short and avoids overlapping images.
    forward_limit = min(target + 5, max_end)
    for i in range(max(1, target), forward_limit + 1):
        if ends_sentence(tokens[i - 1]):   # ends_sentence = last char in ".!?"
            return i
    # Next sentence end too far — fall back to previous sentence end
    for i in range(target - 1, 0, -1):
        if ends_sentence(tokens[i - 1]):
            return max(1, i)
    return max(1, min(target, max_end))
```

**The +5 cap is critical:** without it, a single long sentence causes text to consume dozens of tokens, producing many visual lines that overflow into the image area below.

**For text that fires last (punchline):** search BACKWARD from the end for the last sentence start — same principle in reverse.

**Why forward for headings, backward for punchlines:**
- Heading (fires first): extend to the next complete sentence so it reads as a self-contained opening statement.
- Punchline (fires last): trim backward to the last sentence so it reads as a self-contained closing statement.

If no sentence boundary exists in the entire script, use the proportional fallback (best effort). This should be rare — always use punctuated scripts.

---

## Text Scale / Canvas Overflow Rule

Text elements must never render wider than the canvas. Use the character-count formula
from LAYOUT_DESIGN_APPROACH.md in every generator that produces text elements:

```
max_safe_scale = 72 / num_chars    (where num_chars = len(phrase))
final_scale    = min(aesthetic_preferred, max_safe_scale)
```

Key numbers (scene 1920×1080 coords, Comic Sans fontSize=40):
- 8 chars  → max scale 9.0   (aesthetic preferred ≈ 3.5)
- 24 chars → max scale 3.0
- 36 chars → max scale 2.0
- 49 chars → max scale 1.47
- 72 chars → max scale 1.0   (readability floor)

If the phrase exceeds 72 characters, split it into wrapped lines rather than shrinking below scale 1.0.

---

## Common Mistakes to Avoid

| Mistake | Fix |
|---------|-----|
| Image and its label share same phrase | Split into img_phrase + txt_phrase (consecutive halves) |
| Arrow has empty phrase | Assign the connector words spoken just before the arrow's target |
| Section title uppercased in `phrase` field | Store original lowercase in `phrase`, uppercase only in `text_content` |
| CTA invented when script too short | Set `cta: ""` to skip the element cleanly |
| strip_subtitle = same as frame_5 cap | step_1 validation + retry logic enforces uniqueness |
| Layout 6 image steals first text's phrase | Generator uses `img_phrase` field from step_2 output |
| Layout 18 img and cap share same phrase | Generator uses `img_phrase` + `cap_phrase` split fields |
| AI produces wrong phrase partition | Add validate_phrases() + retry loop to step_N.py (see layout_16/6/18 for pattern) |
| Phrase is a prefix of another phrase | Both fire at the same start word -- split differently |
