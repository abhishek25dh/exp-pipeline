# Layout 9 Phrase Rules Compliance (Proof Report)

Generated: `2026-03-10 17:29:25`

## Rules Referenced (Authoritative Sources)

- Universal rules: `LAYOUT_PHRASE_RULES.md`
- Layout 9: `LAYOUT_PHRASE_RULES.md` (All Other Layouts section)

## Universal Phrase Rules (All Layouts)

From `LAYOUT_PHRASE_RULES.md`:
- Rule 1: every element must have a non-empty `phrase` (except purely decorative arrows).
- Rule 2: every `phrase` must be copied verbatim from the scene script (no invention/paraphrase).
- Rule 3: phrases must be unique within the scene, and must not cause timing collisions (no duplicates; no prefix-collisions).
- Rule 4: when two elements share one beat, their phrases must be consecutive fragments (split at word boundaries, no repeated words).
- Rule 5: for tiling layouts, chosen phrases should cover the full script in order (no gaps, no overlaps).

## Scenes Using Layout 9

- `scene_15`: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_15_prompt.json`
- `scene_41`: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_41_prompt.json`
- `scene_51`: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_51_prompt.json`
- `scene_8`: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_8_prompt.json`

## Scene 15

- Prompt: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_15_prompt.json`
- Director: `D:/AI Tools/Explainer content/Testing/assets/directorscript/scene_15_director.json`

### Scene Script (from prompt)

> You have friends. Good friends. But not many. You can count your real friends on one hand. You're not collecting acquaintances. You're investing in people who matter.

### Rule Checks (Pass/Fail)

- Rule 1 (no empty phrases): `PASS`
- Rule 2 (phrases verbatim from script): `PASS`
- Rule 3 (unique + no prefix collisions): `PASS`
- Rule 4 (consecutive fragments per moment): `PASS`
- Rule 5 (tiling coverage): `N/A` (layout not defined as tiling)

### Pair Check (Image + Text Consecutive Fragments)

| moment | consecutive | proof |
|---|---|---|
| moment_1 | YES | img[12:14] then txt[14:17] |
| moment_2 | YES | img[22:24] then txt[24:27] |
| moment_3 | YES | img[18:20] then txt[20:21] |
| moment_4 | YES | img[3:5] then txt[5:8] |

### Element-by-Element Proof

| element_id | type | phrase (raw) | clean_phrase | in_script | director line |
|---|---|---|---|---:|---:|
| `img_moment_1` | `image` | real friends | `real friends` | YES | 7 |
| `txt_moment_1` | `text_highlighted` | on one hand | `on one hand` | YES | 22 |
| `img_moment_2` | `image` | investing in | `investing in` | YES | 37 |
| `txt_moment_2` | `text_black` | people who matter | `people who matter` | YES | 52 |
| `img_moment_3` | `image` | not collecting | `not collecting` | YES | 67 |
| `txt_moment_3` | `text_red` | acquaintances | `acquaintances` | YES | 82 |
| `img_moment_4` | `image` | Good friends | `good friends` | YES | 97 |
| `txt_moment_4` | `text_highlighted` | But not many | `but not many` | YES | 112 |

## Scene 41

- Prompt: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_41_prompt.json`
- Director: `D:/AI Tools/Explainer content/Testing/assets/directorscript/scene_41_director.json`

### Scene Script (from prompt)

> You have hobbies that don't require other people. Woodworking in your garage. Gardening in your yard. Reading in your chair. Painting in your spare room.

### Rule Checks (Pass/Fail)

- Rule 1 (no empty phrases): `PASS`
- Rule 2 (phrases verbatim from script): `PASS`
- Rule 3 (unique + no prefix collisions): `PASS`
- Rule 4 (consecutive fragments per moment): `PASS`
- Rule 5 (tiling coverage): `N/A` (layout not defined as tiling)

### Pair Check (Image + Text Consecutive Fragments)

| moment | consecutive | proof |
|---|---|---|
| moment_1 | YES | img[8:10] then txt[10:12] |
| moment_2 | YES | img[12:14] then txt[14:16] |
| moment_3 | YES | img[16:18] then txt[18:20] |
| moment_4 | YES | img[20:22] then txt[22:25] |

### Element-by-Element Proof

| element_id | type | phrase (raw) | clean_phrase | in_script | director line |
|---|---|---|---|---:|---:|
| `img_moment_1` | `image` | Woodworking in | `woodworking in` | YES | 7 |
| `txt_moment_1` | `text_black` | your garage | `your garage` | YES | 22 |
| `img_moment_2` | `image` | Gardening in | `gardening in` | YES | 37 |
| `txt_moment_2` | `text_red` | your yard | `your yard` | YES | 52 |
| `img_moment_3` | `image` | Reading in | `reading in` | YES | 67 |
| `txt_moment_3` | `text_highlighted` | your chair | `your chair` | YES | 82 |
| `img_moment_4` | `image` | Painting in | `painting in` | YES | 97 |
| `txt_moment_4` | `text_black` | your spare room | `your spare room` | YES | 112 |

## Scene 51

- Prompt: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_51_prompt.json`
- Director: `D:/AI Tools/Explainer content/Testing/assets/directorscript/scene_51_director.json`

### Scene Script (from prompt)

> You people-watch. You think through problems. You plan your next project. You don't need external entertainment constantly because you generate your own internally.

### Rule Checks (Pass/Fail)

- Rule 1 (no empty phrases): `PASS`
- Rule 2 (phrases verbatim from script): `PASS`
- Rule 3 (unique + no prefix collisions): `PASS`
- Rule 4 (consecutive fragments per moment): `PASS`
- Rule 5 (tiling coverage): `N/A` (layout not defined as tiling)

### Pair Check (Image + Text Consecutive Fragments)

| moment | consecutive | proof |
|---|---|---|
| moment_1 | YES | img[0:1] then txt[1:2] |
| moment_2 | YES | img[3:5] then txt[5:6] |
| moment_3 | YES | img[7:9] then txt[9:11] |
| moment_4 | YES | img[12:14] then txt[14:16] |

### Element-by-Element Proof

| element_id | type | phrase (raw) | clean_phrase | in_script | director line |
|---|---|---|---|---:|---:|
| `img_moment_1` | `image` | You | `you` | YES | 7 |
| `txt_moment_1` | `text_black` | people-watch | `peoplewatch` | YES | 22 |
| `img_moment_2` | `image` | think through | `think through` | YES | 37 |
| `txt_moment_2` | `text_red` | problems | `problems` | YES | 52 |
| `img_moment_3` | `image` | plan your | `plan your` | YES | 67 |
| `txt_moment_3` | `text_highlighted` | next project | `next project` | YES | 82 |
| `img_moment_4` | `image` | don't need | `dont need` | YES | 97 |
| `txt_moment_4` | `text_black` | external entertainment | `external entertainment` | YES | 112 |

## Scene 8

- Prompt: `D:/AI Tools/Explainer content/Testing/assets/scene_prompts/scene_8_prompt.json`
- Director: `D:/AI Tools/Explainer content/Testing/assets/directorscript/scene_8_director.json`

### Scene Script (from prompt)

> Something breaks. Your first instinct isn't to call someone. It's to figure it out yourself. The leaky faucet. The computer acting up. The lamp that stopped working.

### Rule Checks (Pass/Fail)

- Rule 1 (no empty phrases): `PASS`
- Rule 2 (phrases verbatim from script): `PASS`
- Rule 3 (unique + no prefix collisions): `PASS`
- Rule 4 (consecutive fragments per moment): `PASS`
- Rule 5 (tiling coverage): `N/A` (layout not defined as tiling)

### Pair Check (Image + Text Consecutive Fragments)

| moment | consecutive | proof |
|---|---|---|
| moment_1 | YES | img[15:17] then txt[17:18] |
| moment_2 | YES | img[18:20] then txt[20:22] |
| moment_3 | YES | img[22:24] then txt[24:27] |
| moment_4 | YES | img[11:13] then txt[13:15] |

### Element-by-Element Proof

| element_id | type | phrase (raw) | clean_phrase | in_script | director line |
|---|---|---|---|---:|---:|
| `img_moment_1` | `image` | The leaky | `the leaky` | YES | 7 |
| `txt_moment_1` | `text_black` | faucet | `faucet` | YES | 22 |
| `img_moment_2` | `image` | The computer | `the computer` | YES | 37 |
| `txt_moment_2` | `text_red` | acting up | `acting up` | YES | 52 |
| `img_moment_3` | `image` | The lamp | `the lamp` | YES | 67 |
| `txt_moment_3` | `text_highlighted` | that stopped working | `that stopped working` | YES | 82 |
| `img_moment_4` | `image` | figure it | `figure it` | YES | 97 |
| `txt_moment_4` | `text_black` | out yourself | `out yourself` | YES | 112 |
