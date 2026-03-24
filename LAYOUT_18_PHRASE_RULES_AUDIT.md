# Layout 18 Phrase Rules Compliance (Proof Report)

Generated: `2026-03-10 17:37:45`

## Rules Referenced (Authoritative Sources)

- Universal rules: `LAYOUT_PHRASE_RULES.md`
- Layout 18 rules: `LAYOUT_PHRASE_RULES.md` (Polaroid Wall section)

## Universal Phrase Rules (All Layouts)

From `LAYOUT_PHRASE_RULES.md`:
- Rule 1: every element must have a non-empty `phrase` (except purely decorative arrows).
- Rule 2: every `phrase` must be copied verbatim from the scene script (no invention/paraphrase).
- Rule 3: phrases must be unique within the scene, and must not cause timing collisions (no duplicates; no prefix-collisions).
- Rule 4: when two elements share one beat, their phrases must be consecutive fragments (split at word boundaries, no repeated words).
- Rule 5: for tiling layouts, chosen phrases should cover the full script in order (no gaps, no overlaps).

## Scenes Using Layout 18

- `scene_10`: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_10_prompt.json`
- `scene_16`: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_16_prompt.json`
- `scene_23`: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_23_prompt.json`

## Scene 10

- Prompt: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_10_prompt.json`
- Director: `D:/AI Tools/Explainer content/Testing/assets/directorscript/scene_10_director.json`

### Scene Script (from prompt)

> You've always been this way. Even as a kid, you took things apart to see how they worked. You read instruction manuals. You taught yourself skills because asking for help felt harder than just doing it alone.

### Rule Checks (Pass/Fail)

- Rule 1 (no empty phrases): `PASS`
- Rule 2 (phrases verbatim from script): `PASS`
- Rule 3 (unique + no prefix collisions): `PASS`
- Rule 4 (img+cap consecutive per polaroid): `PASS`
- Rule 5 (tiling coverage): `FAIL`
- Layout 18 phrase count (expected 9): `9` (`PASS`)
- Proof: Tiling mismatch. First mismatch token index=4. script_window='youve always been this way even as a kid you' vs tiled_window='youve always been this even as a kid you took'.

### Polaroid Pair Check (Image + Caption Consecutive Fragments)

| polaroid | consecutive | proof |
|---|---|---|
| bl | YES | img[15:17] then cap[17:20] |
| br | YES | img[20:22] then cap[22:25] |
| tl | YES | img[5:7] then cap[7:10] |
| tr | YES | img[10:12] then cap[12:15] |

### Element-by-Element Proof

| element_id | type | phrase (raw) | clean_phrase | in_script | director line |
|---|---|---|---|---:|---:|
| `wall_title` | `text_highlighted` | You've always been this | `youve always been this` | YES | 7 |
| `img_tl` | `image` | Even as | `even as` | YES | 22 |
| `cap_tl` | `text_black` | a kid, you | `a kid you` | YES | 37 |
| `img_tr` | `image` | took things | `took things` | YES | 52 |
| `cap_tr` | `text_black` | apart to see | `apart to see` | YES | 67 |
| `img_bl` | `image` | how they | `how they` | YES | 82 |
| `cap_bl` | `text_black` | worked. You read | `worked you read` | YES | 97 |
| `img_br` | `image` | instruction manuals. | `instruction manuals` | YES | 112 |
| `cap_br` | `text_black` | You taught yourself | `you taught yourself` | YES | 127 |

## Scene 16

- Prompt: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_16_prompt.json`
- Director: `D:/AI Tools/Explainer content/Testing/assets/directorscript/scene_16_director.json`

### Scene Script (from prompt)

> When you do socialize, it's intentional. Coffee with one friend. Dinner with your spouse. A long phone call with someone you trust. These interactions fill you up instead of draining you.

### Rule Checks (Pass/Fail)

- Rule 1 (no empty phrases): `PASS`
- Rule 2 (phrases verbatim from script): `PASS`
- Rule 3 (unique + no prefix collisions): `PASS`
- Rule 4 (img+cap consecutive per polaroid): `PASS`
- Rule 5 (tiling coverage): `FAIL`
- Layout 18 phrase count (expected 9): `9` (`PASS`)
- Proof: Tiling mismatch. First mismatch token index=4. script_window='when you do socialize its intentional coffee with one friend' vs tiled_window='when you do socialize coffee with one friend dinner with'.

### Polaroid Pair Check (Image + Caption Consecutive Fragments)

| polaroid | consecutive | proof |
|---|---|---|
| bl | YES | img[14:16] then cap[16:18] |
| br | YES | img[22:24] then cap[24:27] |
| tl | YES | img[6:8] then cap[8:10] |
| tr | YES | img[10:12] then cap[12:14] |

### Element-by-Element Proof

| element_id | type | phrase (raw) | clean_phrase | in_script | director line |
|---|---|---|---|---:|---:|
| `wall_title` | `text_highlighted` | When you do socialize | `when you do socialize` | YES | 7 |
| `img_tl` | `image` | Coffee with | `coffee with` | YES | 22 |
| `cap_tl` | `text_black` | one friend | `one friend` | YES | 37 |
| `img_tr` | `image` | Dinner with | `dinner with` | YES | 52 |
| `cap_tr` | `text_black` | your spouse | `your spouse` | YES | 67 |
| `img_bl` | `image` | A long | `a long` | YES | 82 |
| `cap_bl` | `text_black` | phone call | `phone call` | YES | 97 |
| `img_br` | `image` | These interactions | `these interactions` | YES | 112 |
| `cap_br` | `text_black` | fill you up | `fill you up` | YES | 127 |

## Scene 23

- Prompt: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_23_prompt.json`
- Director: `D:/AI Tools/Explainer content/Testing/assets/directorscript/scene_23_director.json`

### Scene Script (from prompt)

> Your home isn't just where you live. It's your refuge. You've spent years making it exactly how you want it. The lighting is right. The furniture is comfortable. Everything has a place. Walking through your front door feels like exhaling after holding your breath all day.

### Rule Checks (Pass/Fail)

- Rule 1 (no empty phrases): `PASS`
- Rule 2 (phrases verbatim from script): `FAIL`
- Rule 3 (unique + no prefix collisions): `FAIL`
- Rule 4 (img+cap consecutive per polaroid): `FAIL`
- Rule 5 (tiling coverage): `FAIL`
- Layout 18 phrase count (expected 9): `9` (`PASS`)
- Proof: Tiling mismatch. First mismatch token index=4. script_window='your home isnt just where you live its your refuge' vs tiled_window='your home isnt just your home youve spent years making'.

### Polaroid Pair Check (Image + Caption Consecutive Fragments)

| polaroid | consecutive | proof |
|---|---|---|
| bl | YES | img[20:22] then cap[22:26] |
| br | YES | img[32:34] then cap[34:38] |
| tl | NO | no consecutive match found |
| tr | YES | img[10:12] then cap[12:16] |

### Prefix Collisions (Rule 3 Fail)

- `your home` is a prefix of `your home isnt just` (collides at script token start indices: [0])

### Element-by-Element Proof

| element_id | type | phrase (raw) | clean_phrase | in_script | director line |
|---|---|---|---|---:|---:|
| `wall_title` | `text_highlighted` | Your home isn't just | `your home isnt just` | YES | 7 |
| `img_tl` | `image` | Your home | `your home` | YES | 22 |
| `cap_tl` | `text_black` | is your refuge | `is your refuge` | NO | 37 |
| `img_tr` | `image` | You've spent | `youve spent` | YES | 52 |
| `cap_tr` | `text_black` | years making it exactly | `years making it exactly` | YES | 67 |
| `img_bl` | `image` | The lighting | `the lighting` | YES | 82 |
| `cap_bl` | `text_black` | is right. The furniture | `is right the furniture` | YES | 97 |
| `img_br` | `image` | Walking through | `walking through` | YES | 112 |
| `cap_br` | `text_black` | your front door feels | `your front door feels` | YES | 127 |
