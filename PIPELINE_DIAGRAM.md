# Pipeline Diagram — Sequential vs Parallel

## Legend
```
[SCRIPT]          = run this script
→                 = produces output used by next step
⟹               = must wait for this before continuing
║                 = runs in PARALLEL with other track
✦ MERGE           = wait for BOTH tracks before continuing
```

---

## Full Pipeline

```
INPUTS NEEDED UPFRONT
─────────────────────────────────────────────────────────────
  inputs/background_audio.mp3       (your full voiceover recording)
  inputs/script.docx                (your written script)
═════════════════════════════════════════════════════════════



  ╔══════════════════════════════╗  ║  ╔══════════════════════════════╗
  ║      AUDIO TRACK             ║  ║  ║      SCRIPT TRACK            ║
  ╠══════════════════════════════╣  ║  ╠══════════════════════════════╣
  ║                              ║  ║  ║                              ║
  ║  [script.py]                 ║  ║  ║  [docx_to_paras.py]          ║
  ║   inputs/background_audio    ║  ║  ║   inputs/script.docx         ║
  ║   → tmp/background_audio     ║  ║  ║   → assets/para/para_N.json  ║
  ║     _transcript_full.json    ║  ║  ║                    ↓         ║
  ║                              ║  ║  ║  [layout_selector.py N]      ║
  ║                              ║  ║  ║   assets/para/para_N.json    ║
  ║                              ║  ║  ║   → assets/scene_prompts/    ║
  ║                              ║  ║  ║     scene_N_prompt.json      ║
  ╚══════════════════════════════╝  ║  ╚══════════════════════════════╝
                                    ║
  ─────── both tracks run at same time, no dependency on each other ───────



                          ✦ MERGE POINT A
         (need: scene_prompts/ ready from layout_selector)
  ─────────────────────────────────────────────────────────────────────


  ╔══════════════════════════════╗  ║  ╔══════════════════════════════╗
  ║  [para_to_scenes.py N]       ║  ║  ║  [layout_creator.py]         ║
  ║   assets/para/               ║  ║  ║   assets/scene_prompts/      ║
  ║   assets/scene_prompts/      ║  ║  ║   → assets/directorscript/   ║
  ║   → assets/scenes/paraN.json ║  ║  ║     scene_N_director.json    ║
  ╚══════════════════════════════╝  ║  ╚══════════════════════════════╝
                                    ║
  ─── both run at same time, they read the same files but don't depend ───
  ─── on each other                                                     ───



                          ✦ MERGE POINT B
   (need: audio transcript from AUDIO TRACK + scenes/ from para_to_scenes)
  ─────────────────────────────────────────────────────────────────────

  ╔══════════════════════════════════════════════════════════════════╗
  ║  [audiocutter.py N N N ...]                                      ║
  ║   tmp/background_audio_transcript_full.json                      ║
  ║   assets/scenes/paraN.json                                       ║
  ║   inputs/background_audio.mp3                                    ║
  ║   → assets/scenes_audio/scene_N.mp3   (one per scene)           ║
  ╚══════════════════════════════════════════════════════════════════╝
                              ↓
  ╔══════════════════════════════════════════════════════════════════╗
  ║  [scenes_scripts.py]                                             ║
  ║   assets/scenes_audio/scene_N.mp3                               ║
  ║   → assets/scenes_audio/scene_N_transcript_full.json            ║
  ║   (transcribes EVERY scene mp3 in that folder in one run)        ║
  ╚══════════════════════════════════════════════════════════════════╝



                          ✦ MERGE POINT C
        (need: directorscripts from layout_creator
             + scene transcripts from scenes_scripts)
  ─────────────────────────────────────────────────────────────────

  ╔══════════════════════════════════════════════════════════════════════╗
  ║  [generate_prompts.py 1]  [generate_prompts.py 2]  [generate_prompts.py N]  ║
  ║   (run ALL scenes in parallel — each is independent)                ║
  ║   assets/directorscript/scene_N_director.json                       ║
  ║   → assets/image_prompts/scene_N_image_prompts.json                 ║
  ╚══════════════════════════════════════════════════════════════════════╝
                              ↓
  ╔══════════════════════════════════════════════════════════════════╗
  ║  [image.py]  — send ALL scenes to ComfyUI queue at once          ║
  ║   assets/image_prompts/scene_N_image_prompts.json                ║
  ║   → assets/outputs/scene_N/filename.png                          ║
  ╚══════════════════════════════════════════════════════════════════╝

  ╔══════════════════════════════════════════════════════════════════╗  (runs in parallel with image.py)
  ║  [timings.py a]                                                  ║
  ║   assets/directorscript/scene_N_director.json                   ║
  ║   assets/scenes_audio/scene_N_transcript_full.json              ║
  ║   → assets/timings/scene_N_timings.json                         ║
  ╚══════════════════════════════════════════════════════════════════╝



                          ✦ MERGE POINT D
          (need: images + timings + scene audio — all ready)
  ─────────────────────────────────────────────────────────────────

  ╔══════════════════════════════════════════════════════════════════╗
  ║  [render_video.py]  → http://localhost:5566                      ║
  ║   assets/directorscript/scene_N_director.json                   ║
  ║   assets/timings/scene_N_timings.json                           ║
  ║   assets/scenes_audio/scene_N.mp3                               ║
  ║   assets/outputs/scene_N/*.png                                  ║
  ║   → scene_N.mp4                                                  ║
  ╚══════════════════════════════════════════════════════════════════╝
```

---

## Simplified Run Order

```
Step 1 (parallel — start both at same time):
    python script.py
    python docx_to_paras.py

Step 2 (after docx_to_paras finishes):
    python layout_selector.py 1      ← repeat for each para number

Step 3 (parallel — start both at same time):
    python para_to_scenes.py 1       ← repeat for each para number
    python layout_creator.py

Step 4 (after BOTH script.py AND para_to_scenes finish):
    python audiocutter.py 1 2 3      ← pass all para numbers

Step 5 (after audiocutter finishes):
    python scenes_scripts.py

Step 6 (after BOTH layout_creator AND scenes_scripts finish — run both in parallel):
    python generate_prompts.py 1
    python generate_prompts.py 2
    python generate_prompts.py 3     ← all scenes in parallel

    python timings.py a              ← also at same time as generate_prompts

Step 7 (after ALL generate_prompts finish):
    python image.py                  ← send all to ComfyUI at once

Step 8 (after images + timings done):
    python render_video.py           ← http://localhost:5566
```

---

## What You Missed

Nothing critical was missed. One clarification:

- `para_to_scenes.py` is needed **before** `audiocutter.py`, not before `layout_creator.py`.
  `layout_creator.py` reads from `assets/scene_prompts/` directly — it does NOT need `assets/scenes/`.
  So `layout_creator.py` can start immediately after `layout_selector.py`, without waiting for `para_to_scenes.py`.

---

## Speed-Up Tips

### 1. Batch all image prompts, then queue all at once to ComfyUI

**Current (slow):** generate_prompts → image.py → generate_prompts → image.py (ComfyUI sits idle between scenes)

**Fast:** Run `generate_prompts.py` for ALL scenes first (in parallel), then send ALL image jobs to ComfyUI in one `image.py` run. ComfyUI queues them internally and never sits idle.

`image.py` currently only reads one JSON file. It needs to be updated to loop over all scene image_prompt files in one run.

### 2. Run generate_prompts.py for all scenes in parallel

Each call is an independent API call (no shared state). They can all fire at the same time:
```
python generate_prompts.py 1 &
python generate_prompts.py 2 &
python generate_prompts.py 3 &
```
Or update `generate_prompts.py` to accept multiple scene numbers and thread them.

### 3. script.py and docx_to_paras.py have zero dependency — start both immediately

These read from completely different inputs. Always run them at the same time.

### 4. layout_creator.py can run while para_to_scenes.py runs

They both read from `assets/scene_prompts/` but write to different output folders. No conflict.

### 5. timings.py and image generation are fully independent — run in parallel

`timings.py` needs director scripts + scene transcripts.
`generate_prompts.py` / `image.py` need director scripts + image prompts.
They share the director scripts as read-only input — no conflict, both can run simultaneously.
