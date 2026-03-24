"""
cleanup.py — Delete all pipeline-generated files so you can start fresh.
Keeps: inputs/  and  assets/outputs/ root files (arrow.png, host images, etc.)
Only deletes scene_* subfolders inside assets/outputs/.
"""

import shutil
from pathlib import Path

BASE = Path(__file__).parent

# Entire folders to wipe
FOLDERS = [
    "tmp",
    "assets/para",
    "assets/scene_prompts",
    "assets/scenes",
    "assets/directorscript",
    "assets/scenes_audio",
    "assets/timings",
    "assets/image_prompts",
    "assets/tmp",
]

# Individual files to delete
FILES = [
    "assets/sections_timeline.json",
    "pipeline_state.json",
    "pipeline_timing.json",
]

# Inside assets/outputs — delete scene_* subdirs but keep arrow.png
OUTPUTS_DIR = BASE / "assets/outputs"


def collect_scene_output_dirs():
    if not OUTPUTS_DIR.exists():
        return []
    return [d for d in OUTPUTS_DIR.iterdir() if d.is_dir() and d.name.startswith("scene_")]


def main():
    print("=" * 54)
    print("  Pipeline Cleanup")
    print("  Keeps: inputs/  and  assets/outputs/ root files (arrow.png, host images, etc.)")
    print("=" * 54)
    print()

    to_delete_folders = [BASE / f for f in FOLDERS if (BASE / f).exists()]
    to_delete_files   = [BASE / f for f in FILES   if (BASE / f).exists()]
    scene_out_dirs    = collect_scene_output_dirs()

    if not to_delete_folders and not to_delete_files and not scene_out_dirs:
        print("Nothing to clean up — already empty.")
        return

    print("Will delete:")
    for p in to_delete_folders:
        count = sum(1 for _ in p.rglob("*") if _.is_file())
        print(f"  [folder]  {p.relative_to(BASE)}  ({count} files)")
    for p in to_delete_files:
        print(f"  [file]    {p.relative_to(BASE)}")
    for d in scene_out_dirs:
        count = sum(1 for _ in d.rglob("*") if _.is_file())
        print(f"  [folder]  {d.relative_to(BASE)}  ({count} files)")

    print()
    answer = input("Confirm delete? (yes / no): ").strip().lower()
    if answer != "yes":
        print("Cancelled.")
        return

    print()
    for p in to_delete_folders:
        shutil.rmtree(p)
        print(f"  Deleted: {p.relative_to(BASE)}/")

    for p in to_delete_files:
        p.unlink()
        print(f"  Deleted: {p.relative_to(BASE)}")

    for d in scene_out_dirs:
        shutil.rmtree(d)
        print(f"  Deleted: {d.relative_to(BASE)}/")

    print()
    print("Done. inputs/ is untouched. Ready for a new video.")


if __name__ == "__main__":
    main()
