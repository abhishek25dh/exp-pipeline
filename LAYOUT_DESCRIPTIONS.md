# Layout Descriptions — All 39 Templates

> **Scene Length Guide**
> - **Short** = ≤ 100 chars (~10–20 words) — 1–3 phrases needed
> - **Medium** = 100–200 chars (~20–40 words) — 3–6 phrases needed
> - **Long** = 200–320 chars (~40–65 words) — 6–12+ phrases needed
>
> These are YouTube-style explainer video scripts: direct, conversational, self-improvement or educational topics.
> Sentences often start with "You…" or "Here's why…", describe habits, give examples, or present steps.

---

## Layout 1 — Image Collage (Multi-Column)

**Visual**: Multiple AI images arranged into left/center/right column stacks with a jittered "collage" feel.
Scale adapts automatically based on image count (1 big image → 0.60 scale; 5+ → 0.24 scale).
No text labels on screen — purely visual.

**Scene Length**: Short / Medium / Long (very flexible, adapts to any token count)

**Best For**:
- Visually rich scenes that mention many examples or objects
- Abstract concept illustration ("here are things that represent X")
- Opening montages or scene-setters with lots of imagery
- Scenes where you want a dynamic, energetic feel without on-screen text

**Avoid When**: The scene has a specific structure (steps, comparisons, cause-effect) that a labelled layout would serve better.

---

## Layout 2 — Grouped Image Clusters

**Visual**: Images grouped into 1–8 thematic clusters, each cluster placed in its own bounding zone across the canvas.
Groups adapt to available screen space (1 big cluster, 4 in corners, 6 in spread pattern, etc.).
No text — pure image grouping.

**Scene Length**: Short / Medium / Long (flexible)

**Best For**:
- Scenes that enumerate multiple categories or themed groups of things
- "There are three types of..." or "in each area of your life..."
- Visual scenes where grouping aids comprehension but labels aren't needed

**Avoid When**: You need on-screen text to clarify what each item is.

---

## Layout 3 — Scattered Image Groups (Full-Canvas)

**Visual**: Image groups scattered randomly across the FULL canvas with organic jitter.
Physics-based collision avoidance ensures no overlaps.
Feels busy and energetic — maximizes visual coverage. No text.

**Scene Length**: Short / Medium / Long (highly flexible)

**Best For**:
- High-energy, fast-paced sections
- Montage-style scenes ("all the ways you can use AI", "every situation where this happens")
- Scenes needing maximum visual density

**Avoid When**: The scene requires clarity and structure — the random scatter can look chaotic.

---

## Layout 4 — Fully Random Scatter (Host Corner)

**Visual**: Host/narrator image in a random corner, title text in the opposite corner, floating AI images scattered randomly across the middle.
Very dynamic — nothing is in the same place twice across scenes.

**Scene Length**: Short / Medium / Long (flexible)

**Best For**:
- Narrator-driven scenes where the presenter "walks through" several examples
- Casual, playful, or conversational tone scenes
- Scenes with "you know how…" or "think about…" framing
- Good variety-breaker between structured layouts

**Avoid When**: The scene needs precise structure (steps, comparisons, lists).

---

## Layout 5 — Cause → Effect

**Visual**: 1–3 horizontal strips, each strip: [CAUSE IMAGE] → [ARROW] → [EFFECT IMAGE].
Arrow direction alternates (left→right, then right→left) for visual variety.
Optional text label near one image per strip.
Physics relaxation prevents strip overlaps.

**Scene Length**: Short / Medium (≤200 chars; each pair needs at least 4–6 words)

**Best For**:
- Explicit causal relationships: "X leads to Y", "doing X causes Y"
- "Interrupting others makes you seem disengaged" type sentences
- Before/after or action/consequence framing
- Behavioral psychology cause-effect chains

**Avoid When**: There's no clear causal link, or the scene has more than 3 cause-effect pairs.

---

## Layout 6 — Two Rows (Image + Text Pairs)

**Visual**: Screen split into top and bottom rows.
Top row: [IMAGE on left] [TEXT on right]
Bottom row: [TEXT on left] [IMAGE on right] (alignment alternates)
Text is stacked inside each half, scale computed from longest phrase.

**Scene Length**: Medium (100–220 chars — needs content for exactly 2 groups)

**Best For**:
- Two distinct but related concepts shown in parallel
- Contrasting pairs: "smart people do X; less effective people do Y"
- Two examples or two sides of the same idea
- Scenes with exactly two narrative beats

**Avoid When**: The scene has more or fewer than 2 clear groups of content.

---

## Layout 7 — Host Center + 4 Quadrant Images

**Visual**: Host/narrator image large at center (960, 560 scale=0.9).
4 AI images in the 4 corners: top-left, bottom-left, top-right, bottom-right (scale=0.32 each).
Host emotion adapts (happy/sad/angry/explaining).

**Scene Length**: Medium / Long (needs phrases for host + 4 images ≈ 5 phrases, ~30–60 words)

**Best For**:
- Narrator explaining a concept with 4 surrounding visual examples
- "Here are four reasons why…" or "this affects four areas of your life"
- Explanatory/educational tone scenes with a presenter
- When you want a talking-head feel with supporting imagery

**Avoid When**: Short scenes (too few words for 5 elements) or no host character.

---

## Layout 8 — Timeline / Process Path

**Visual**: 3–4 steps arranged left-to-right in a zigzag (alternating high/low y-positions).
Each step has an image + step text label.
Decorative connecting arrows between adjacent steps.

**Scene Length**: Medium / Long (needs ~5–10 words per step; 3–4 steps = 150–320 chars)

**Best For**:
- Step-by-step processes: "first you do X, then Y, then Z"
- Historical timelines or evolution of something
- "Here's how it works, step by step"
- Habits or routines broken into sequential stages

**Avoid When**: The content isn't sequential/ordered, or fewer than 3 clear steps.

---

## Layout 9 — 2×2 Comic Grid

**Visual**: Canvas divided into 4 quadrants (top-left, top-right, bottom-left, bottom-right).
Each quadrant: one image centered + one short text label below the image.

**Scene Length**: Medium (needs exactly 4 labeled items; ~20–50 words)

**Best For**:
- Enumerating exactly 4 examples, habits, types, or categories
- "There are four ways this shows up…"
- Grid-style visual lists where each item gets equal treatment
- "The four signs that you…"

**Avoid When**: Fewer or more than 4 items, or items can't be represented as equal-weight examples.

---

## Layout 10 — Macro to Micro (Zoom Map)

**Visual**: One large "Macro" image on the left half (scale=0.50), centered at ~(550, 590).
2–3 smaller "Micro" images stacked vertically on the right half.
Arrows connect macro → each micro image.
Title text appears above the macro image.

**Scene Length**: Medium / Long (~120–300 chars; macro title + 2–3 micro labels needed)

**Best For**:
- One overarching concept + 2–3 supporting details
- "The big picture is X; here are the details"
- Zooming in: "Think about intelligence broadly — specifically, verbal reasoning, memory, and adaptability"
- Main idea → specific examples structure

**Avoid When**: All items are at the same conceptual level (use grid or list instead).

---

## Layout 11 — Mind-Map Orbit

**Visual**: Core concept word/phrase displayed LARGE in the center.
4–5 image nodes in fixed "safe slots" orbiting around the center: top-left, top-right, bottom-left, bottom-right, top-center.
Each node: image + text label below.

**Scene Length**: Medium / Long (~150–320 chars; needs core concept + 4–5 labeled nodes)

**Best For**:
- A topic that radiates into multiple connected sub-ideas
- "Quick judgment affects your relationships, career, decisions, reputation, and growth"
- Central habit/concept with multiple manifestations
- "All of these connect back to one thing: X"

**Avoid When**: The ideas are sequential (use timeline) or the scene is too short for 5 labels.

---

## Layout 12 — VS Comparison

**Visual**: Screen split down the middle with a bold "VS" divider.
Left side: image + label. Right side: image + label.
Symmetrical, high-contrast visual.

**Scene Length**: Short / Medium (4–8 phrases needed; works at ~80–200 chars)

**Best For**:
- Direct "X vs Y" comparisons
- "Intelligent people admit mistakes; insecure people double down"
- Contrasting two behaviors, mindsets, or outcomes
- Before/after or old/new scenarios

**Avoid When**: More than 2 sides need comparing, or the scene isn't truly contrastive.

---

## Layout 13 — Staircase (Step-Up)

**Visual**: 4 steps arranged diagonally from bottom-left to top-right — ascending staircase.
Each step: image at the step position + text label below the image.
Positions: step1 (bottom-left), step2, step3, step4 (top-right).

**Scene Length**: Medium / Long (needs 4 labeled steps; ~120–280 chars)

**Best For**:
- Progressive improvement or ascending difficulty
- "The higher you climb in X, the more you need Y"
- 4-stage habit building: "start here → grow → level up → master"
- Skills, knowledge, or status that accumulates upward

**Avoid When**: The steps aren't ordered/progressive, or fewer/more than 4 steps.

---

## Layout 14 — Circular Flow / Cycle

**Visual**: Center title text + 4 image nodes at 12, 3, 6, 9 o'clock positions.
Connecting arrows at 45°, 135°, 225°, 315° between adjacent nodes.
Text labels placed outside the circle, away from center.

**Scene Length**: Medium / Long (center title + 4 nodes + labels; ~150–280 chars)

**Best For**:
- Ongoing cycles or feedback loops
- "This creates a pattern that repeats itself…"
- Habits that reinforce themselves: "judge → act on judgment → reinforce bias → judge again"
- Recurring processes that have no clear start/end

**Avoid When**: The process is linear (use timeline) or has a clear beginning and end.

---

## Layout 15 — Hero + Bullets

**Visual**: Large hero image on the LEFT (x=490, y=540, scale=0.44).
Section title text top-right.
3 bullet text items stacked vertically on the right.
Optional call-to-action line at the bottom-right.

**Scene Length**: Medium / Long (title + 3 bullets + CTA = 5 elements; ~150–300 chars)

**Best For**:
- One key claim or concept supported by 3 reasons/facts
- "Here's why [X] is a problem: reason 1, reason 2, reason 3"
- Listicle-style scenes with a dominant visual anchor
- Educational breakdowns of a topic

**Avoid When**: Fewer than 3 supporting points, or the scene is too short for all 5 elements.

---

## Layout 16 — Filmstrip

**Visual**: Strip title at top center.
Strip subtitle/context below title.
5 images in a horizontal row at mid-screen.
Caption text directly beneath each image.
Feels like a film roll or memory strip.

**Scene Length**: Long (13 elements: title + subtitle + 5 images + 5 captions = needs ~200–320 chars)

**Best For**:
- Nostalgia and memory references: "remember when you used to…"
- A series of sequential moments or snapshots in time
- "Here are five moments that defined…"
- Scenes with a warm, reflective, or story-telling tone

**Avoid When**: Short scenes — this layout needs many phrases to fill all 13 elements meaningfully.

---

## Layout 17 — Triangle (Three-Point Triforce)

**Visual**: 3 image+label pairs at the vertices of an equilateral triangle (top, bottom-right, bottom-left).
Central concept word displayed in the middle.
Circumradius R=350 from center (960, 540).

**Scene Length**: Medium / Long (center + 3 nodes + 3 labels = 7 elements; ~150–280 chars)

**Best For**:
- Exactly 3 interconnected pillars of a concept
- "Intelligence has three components: awareness, adaptation, and action"
- A triangle of interdependent ideas that all connect to a center theme
- "It comes down to three things…"

**Avoid When**: More or fewer than 3 pillars, or the ideas don't connect to a unifying center.

---

## Layout 18 — Polaroid Wall

**Visual**: Wall title at top center.
4 polaroid-style photos arranged in a loose 2×2 pattern with slight rotations (±7–9°).
Each polaroid has a handwritten-style caption below it.
Warm, nostalgic, personal feel.

**Scene Length**: Medium / Long (title + 4 polaroids + 4 captions = 9 elements; ~180–320 chars)

**Best For**:
- Nostalgic or memory-evoking scenes
- Personal examples: "think about the last time you…"
- Scenes with warmth, humanity, and emotional resonance
- "Snapshots" of a person's behavioral patterns
- 4 personal scenarios or real-life moments

**Avoid When**: Short, analytical, or emotionally neutral scenes.

---

## Layout 19 — Pyramid Stack

**Visual**: Title text at top center.
Hero image centered in the upper area (large scale).
Two supporting images in the middle row (left + right).
Three keyword text labels spread across the bottom row.
Forms a visual pyramid: 1 → 2 → 3.

**Scene Length**: Medium / Long (7 elements total; ~150–300 chars)

**Best For**:
- Concept that builds from one big idea to multiple details
- "It starts with one thing and branches into three consequences"
- Topic + 2 supporting visuals + 3 keyword takeaways
- Scenes that want a strong visual hierarchy

**Avoid When**: The scene doesn't have a clear pyramid/hierarchy structure.

---

## Layout 20 — Top Text + Arrows + Images

**Visual**: Large main text heading at top center (y=315).
1–3 image groups below, each with an arrow pointing down from the text.
Adaptive: 1 group = center only; 2 groups = left+right balanced; 3 groups = full spread.

**Scene Length**: Short / Medium / Long (very adaptive — text-only if too short, up to 7 elements if long)

**Best For**:
- Text statement that introduces/explains, followed by visual examples
- "There are three main reasons why…" + 3 images
- Punchy headline with supporting visuals
- Works for both short (just the heading) and long scenes (heading + 3 image groups)

**Avoid When**: The scene has no clear "heading then examples" structure.

---

## Layout 21 — Text + Arrow + Image

**Visual**: Text heading at top center (y=310).
One arrow pointing to a single image (alternating left/right per scene).
Image at center-ish (y=713).
Can also render as text-only if scene is too short.

**Scene Length**: Short (perfect for ≤100 chars) / Medium (up to ~180 chars)

**Best For**:
- Short punchy statements with one key visual
- Single direct address: "You interrupt people" + image of interrupting
- Hook sentences at the start of a paragraph
- Any scene that makes one clear point with one example

**Avoid When**: The scene has multiple distinct points that need separate visuals.

---

## Layout 22 — Text Only

**Visual**: Multiple text lines centered horizontally and vertically on the canvas.
Lines spaced 150 scene px apart, centered around y=540.
No images at all — pure typography.
Text type varies (highlighted/red/black) seeded per scene.

**Scene Length**: Short / Medium / Long (1–4 lines, fully adapts to phrase length)

**Best For**:
- Pure statement scenes where text IS the visual
- Rhetorical questions: "Why does this happen?"
- Powerful punchlines or conclusions: "The real risk is standing still"
- Moments of emphasis where an image would distract
- Emotional or philosophical statements

**Avoid When**: The scene is dry or factual — would benefit from visual reinforcement.

---

## Layout 23 — Hero + Supporting Images

**Visual**: Hero image (largest, most prominent) + 1–3 supporting images in flexible positions.
Scale and position adapt based on how many images are active.
No text. Pure visual.

**Scene Length**: Short / Medium (very flexible, 1–4 images)

**Best For**:
- One dominant visual concept with a few supporting visuals
- "Think of it like this…" scenes where you want images to carry the meaning
- Abstract concept → concrete examples visually
- Scenes with a main subject and secondary context

**Avoid When**: You need on-screen text to guide the viewer.

---

## Layout 24 — Two Images + Bottom Text

**Visual**: 1–2 images in the upper portion (y=380).
Bottom text phrase at y=870 (with images) or y=540 (text-only).
Images fire first (P1, P2), then text reveals last (P3).

**Scene Length**: Short / Medium (2–4 elements; ~80–200 chars)

**Best For**:
- Visual setup followed by text punchline
- "Show two things, then explain them" structure
- "You do X [image], and Y [image] — and here's why that matters [text]"
- Scenes where the visual context precedes the verbal insight

**Avoid When**: The text needs to come first, or the scene is very long.

---

## Layout 25 — Host Right + 4 Images Left (2×2)

**Visual**: Static host/narrator on the right (x=1497, y=559, scale=1.608).
4 AI images in a 2×2 grid on the left side.
Host "presents" the examples on the left.

**Scene Length**: Medium / Long (host + 4 images = 5 phrases; ~130–280 chars)

**Best For**:
- Narrator presenting 4 examples or evidence points
- "Here are four things to watch for…"
- Host-led educational scenes with visual examples
- Engaging presenter format with multiple supporting images

**Avoid When**: Short scenes or scenes without a clear host/narrator element.

---

## Layout 26 — Text Top-Left + Image Clusters

**Visual**: Text phrase top-left (x=553, y=400).
2 images below-left (stacked, x=287–886, y=813).
4 images in 2×2 grid on the right side (x=1314–1629, y=440–820).
Text + 6 images total.

**Scene Length**: Long (text + 6 images = 7+ elements; ~200–320 chars)

**Best For**:
- Long scenes with rich visual content and a key text anchor
- "This habit shows up in your personal life, professional life..." + many examples
- Scenes where a short text phrase contextualizes a lot of imagery
- Maximum visual variety while keeping one text anchor

**Avoid When**: Short scenes — too many elements for few tokens.

---

## Layout 27 — Host Center + Side Texts

**Visual**: Static host image in the center (x=964, y=576, scale=1.748).
Text callout on the left (x=404, y=425).
Text callout on the right (x=1542, y=426).
Host flanked by two short keyword phrases.

**Scene Length**: Medium / Long (host + 2 side texts; ~120–280 chars)

**Best For**:
- Narrator with two flanking text labels
- "On one hand: X [left text], on the other: Y [right text] — here's what I mean [host]"
- Educational presenter scenes with key terms flanking
- Scenes that contrast two sides while maintaining host presence

**Avoid When**: Side text zones are narrow — avoid assigning too many words to each text slot.

---

## Layout 28 — Side-by-Side Images + Punchline Text

**Visual**: Two large images side by side (x=493 left, x=1371 right, scale=0.6+).
Text punchline at the bottom center (y=922).
Images fire first (P1, P2), text fires last (P3).

**Scene Length**: Short / Medium (3 elements; ~100–220 chars)

**Best For**:
- Visual comparison followed by a conclusion
- "Look at these two situations [images]… the difference is X [text]"
- Contrast pairs: two habits, two outcomes, two approaches
- When the reveal text is the "punchline" of the scene

**Avoid When**: You want text to appear before or alongside images (not after).

---

## Layout 29 — Statement Stack (4 Lines Alternating)

**Visual**: 4 text statements stacked vertically, evenly distributed across the canvas.
Types alternate: text_black / text_red / text_black / text_red.
Pure text — no images. Creates visual rhythm through color alternation.

**Scene Length**: Long (4 text slots that each need a full phrase; ~200–320 chars)

**Best For**:
- Lists of 4 distinct points, each deserving its own line
- "Point one. Point two. Point three. Point four." rhythm
- Declarative statement scenes: facts, rules, or habits listed
- Scenes with strong enumeration structure

**Avoid When**: The scene has fewer than 4 distinct points, or a visual would reinforce the message better.

---

## Layout 30 — Host Left + Image Right

**Visual**: Static host/narrator on the left (x=445–497, y=553–567).
Single AI image on the right.
Simple, clean two-element composition.

**Scene Length**: Short (2 elements; ≤150 chars)

**Best For**:
- Short explanatory scenes with one key visual
- "Here's what that looks like" with a single image
- Conversational narrator scenes with a single example
- Quick transitions or scene openings

**Avoid When**: The scene needs multiple visuals or complex structure.

---

## Layout 31 — Image → Arrow → Image + Label

**Visual**: Image on the left, arrow in the center, image on the right.
Text label top-right (above the right image).
Priority-based: starts with just the left image, adds elements if tokens allow.

**Scene Length**: Short / Medium (1–4 active elements; ~80–200 chars)

**Best For**:
- Sequential cause-effect with a labeled outcome
- "This behavior [image] leads to [arrow] this result [image], specifically: [label]"
- Action → consequence with a keyword annotation
- Compact cause-effect with a named outcome

**Avoid When**: The cause-effect is more complex than a single pair.

---

## Layout 32 — Two Images Side by Side (No Text)

**Visual**: Two AI images placed symmetrically left (x=493) and right (x=1371).
No text at all — pure visual juxtaposition.

**Scene Length**: Short / Medium (2 phrases only; ≤150 chars)

**Best For**:
- Visual comparison without verbal labels
- Two contrasting concepts where the image says it all
- Abstract visual storytelling moments
- Pace-breaking scene with pure imagery

**Avoid When**: The viewer needs text guidance to understand the connection.

---

## Layout 33 — Heading + Visual Comparison

**Visual**: Text heading at top (x=929, y=332, full-canvas width).
Image left below (x=363, y=711) → Arrow center → Image right (x=1520, y=700).

**Scene Length**: Medium (heading + arrow + 2 images = 3–4 elements; ~100–220 chars)

**Best For**:
- A titled scene that shows a visual transition or comparison
- "The key difference is X [heading] → here's the old way [image left] → and the new way [image right]"
- Headed cause-effect or before/after with a text anchor at top

**Avoid When**: The heading is too long (wraps into 3+ lines and pushes into images).

---

## Layout 34 — Multi-Element Complex (5 Slots)

**Visual**: Image left + image right (flanking, large).
Two text phrases centered vertically between the images.
Image at the bottom center.
5 elements total: P1=img_left, P2=img_right, P3=text_1, P4=text_2, P5=img_bottom.

**Scene Length**: Long (5 elements; ~200–320 chars)

**Best For**:
- Rich, multi-point scenes with both images and text labels
- "On the left, on the right, and in the middle you have X and Y — but ultimately Z [bottom image]"
- Complex scenes that benefit from layered visual composition
- Longer educational explanations with multiple visual anchors

**Avoid When**: Short scenes — only the first 1–2 elements would fire.

---

## Layout 35 — Host Left + Text Right

**Visual**: Static host/narrator on the left (x=497, y=567, scale=1.983).
Text block on the right column (x=1372, y=446).
Text wraps into multiple lines if needed (TEXT_SAFE_W=850).

**Scene Length**: Short / Medium (2 elements, text wraps as needed; ≤220 chars)

**Best For**:
- Narrator making a concise statement with text on screen
- "The host says: [spoken words], and the key phrase appears [text]"
- Single host + text explanation — the simplest "presenter + point" format
- Scenes with a clear presenter voice

**Avoid When**: The scene needs multiple images or the text block is very long (>5 lines).

---

## Layout 36 — Host Right + Multi-Image + Text

**Visual**: Host right (x=1497, y=559, scale=1.608) as anchor.
Image left, arrow, image center on the left portion.
Text callout bottom-left.
5 active elements: P1=host, P2=img_left, P3=arrow, P4=img_center, P5=text.

**Scene Length**: Long (5 elements; ~200–320 chars)

**Best For**:
- Complex narrator-driven scenes with cause-effect plus a text callout
- "The host introduces the concept; two images show the progression; a keyword phrase anchors the bottom"
- Long explanatory scenes where the host anchors attention on the right

**Avoid When**: Short scenes — lower-priority elements won't appear.

---

## Layout 37 — 6-Image Mosaic

**Visual**: Large center image (main visual anchor, P1).
2 images on the left side.
3 images on the right side.
6 AI images total. No text.

**Scene Length**: Long (6 phrases; ~180–320 chars)

**Best For**:
- Scenes with many visual examples and no text needed
- "Here are six things that represent this idea…"
- Maximum visual variety and density
- Abstract or conceptual scenes where imagery drives meaning

**Avoid When**: The scene needs text context for the images to make sense.

---

## Layout 38 — Text First + Two Images

**Visual**: Text phrase fires FIRST at bottom center (x=942, y=934) — unusual timing.
Then two AI images appear (left x=415, right x=1443).
Text leads; images follow as supporting visuals.

**Scene Length**: Short / Medium (3 elements; ~100–200 chars)

**Best For**:
- Punchline-first scenes where the statement precedes the evidence
- "Here is the truth: [text fires] … and here's what it looks like [images appear]"
- Inverted structure: claim → visual proof
- Scenes with a strong opening statement

**Avoid When**: The images need to set context before the text lands.

---

## Layout 39 — Image Grid + Bullet Text List

**Visual**: 2×2 image grid on the LEFT side (4 AI images).
4 text bullet rows stacked on the RIGHT side.
Left = visual examples; Right = text list.
Up to 8 elements in priority order (images P1–P4, text P5–P8).

**Scene Length**: Long (up to 8 elements; ~200–320 chars needed for full layout)

**Best For**:
- Enumeration scenes with both visual and text bullets
- "Here are four habits [image grid] — and here's what they have in common [text list]"
- Long list-style scenes with visual and verbal parallel structure
- Educational content that needs both showing and telling

**Avoid When**: Short scenes — many elements won't fire and the layout will feel sparse.

---

## Quick Reference: Scene Length → Best Layouts

| Scene Length | Layouts to Prefer |
|---|---|
| **Short** (≤100 chars) | 21, 22, 24, 30, 32, 38 |
| **Short/Medium** (80–180 chars) | 5, 12, 20, 21, 28, 31, 33, 35 |
| **Medium** (100–220 chars) | 6, 9, 10, 13, 14, 17, 23, 24, 25, 27, 28 |
| **Medium/Long** (150–280 chars) | 7, 11, 15, 18, 19, 20, 29, 34, 36 |
| **Long** (200–320 chars) | 8, 16, 26, 29, 34, 36, 37, 39 |
| **Any length** | 1, 2, 3, 4, 20, 22 |

## Quick Reference: Content Type → Best Layouts

| Content Type | Layouts to Prefer |
|---|---|
| **Hook / single statement** | 21, 22, 38 |
| **Cause → Effect** | 5, 31, 33 |
| **Two contrasts / VS** | 12, 28, 32, 6 |
| **Three pillars** | 17 |
| **Four items / examples** | 9, 18, 11, 39 |
| **Five+ items / enumeration** | 29, 15, 16, 37 |
| **Step-by-step process** | 8, 13 |
| **Cycles / loops** | 14 |
| **One big idea + details** | 10, 15 |
| **Mind-map / fan-out** | 11, 17 |
| **Narrator-driven** | 4, 7, 25, 27, 30, 35, 36 |
| **Nostalgic / memories** | 16, 18 |
| **Pure visuals** | 1, 2, 3, 23, 32, 37 |
| **Text-dominant** | 22, 29 |
| **Text + visuals combined** | 20, 24, 26, 39 |
