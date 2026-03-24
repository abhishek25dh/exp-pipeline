import os
import json
from pydub import AudioSegment


def process_scene(scene_id, loaded_sfx, output_dir):
    """Processes a single scene and returns status."""
    
    director_path = os.path.join("directorscript", f"{scene_id}_director.json")
    timings_path = os.path.join("timings", f"{scene_id}_timings.json")
    output_path = os.path.join(output_dir, f"{scene_id}_sfx.mp3")

    # Skip if files don't exist
    if not os.path.exists(director_path) or not os.path.exists(timings_path):
        print(f"⏭️ Skipping {scene_id} (files missing)")
        return "missing"

    print(f"\n🎧 Mixing audio for {scene_id}...")

    with open(director_path, 'r', encoding='utf-8') as f:
        director_data = json.load(f)

    with open(timings_path, 'r', encoding='utf-8') as f:
        timings_data = json.load(f)

    animations_lookup = {
        el["element_id"]: el.get("animation", "")
        for el in director_data.get("elements", [])
    }

    max_start = max([t.get("start", 0) for t in timings_data], default=0)
    total_duration_ms = int((max_start + 5) * 1000)

    final_audio = AudioSegment.silent(duration=total_duration_ms)

    for item in timings_data:
        el_id = item.get("element_id")
        start_sec = item.get("start", 0)

        anim_type = animations_lookup.get(el_id, "").lower()
        if not anim_type:
            continue

        sfx_key = None

        if "jump_cut" in anim_type:
            sfx_key = "click"
        elif "pop" in anim_type:
            sfx_key = "pop"
        elif "draw" in anim_type:
            sfx_key = "whoosh"
        elif "slide" in anim_type or "fade" in anim_type:
            sfx_key = "whoosh"
        elif "typing" in anim_type:
            sfx_key = "typing"

        if sfx_key and sfx_key in loaded_sfx:
            start_ms = int(start_sec * 1000)
            final_audio = final_audio.overlay(
                loaded_sfx[sfx_key], position=start_ms
            )
            print(f"  ✅ Added {sfx_key}.mp3 for '{el_id}' at {start_sec}s")

    print(f"💾 Exporting {scene_id} to {output_path}")
    final_audio.export(output_path, format="mp3")

    return "processed"


def main():

    sfx_dir = "sound_effects"
    output_dir = "SFX"

    os.makedirs(output_dir, exist_ok=True)

    sfx_files = {
        "click": os.path.join(sfx_dir, "click.mp3"),
        "pop": os.path.join(sfx_dir, "pop.mp3"),
        "whoosh": os.path.join(sfx_dir, "whoosh.mp3"),
        "typing": os.path.join(sfx_dir, "typing.mp3")
    }

    loaded_sfx = {}

    print("Loading sound effects into memory...")

    for name, path in sfx_files.items():
        if os.path.exists(path):
            loaded_sfx[name] = AudioSegment.from_file(path)
        else:
            print(f"⚠️ Missing sound effect -> {path}")

    # Process many scenes even if some are missing
    MAX_SCENES = 1000

    processed_count = 0

    for scene_num in range(1, MAX_SCENES + 1):

        scene_id = f"scene_{scene_num}"

        result = process_scene(scene_id, loaded_sfx, output_dir)

        if result == "processed":
            processed_count += 1

    print(f"\n🚀 Finished scanning scenes. Total processed: {processed_count}")


if __name__ == "__main__":
    main()