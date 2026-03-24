import re
import os

path = 'd:/AI Tools/Explainer content/Testing/image.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """    json_files = sorted(INPUT_DIR.glob("scene_*_image_prompts.json"), key=_scene_num)
    if not json_files:
        print(f"No JSON files found in {INPUT_DIR}")
        return

    print(f"Found {len(json_files)} scene(s) to process. RunPod: {SERVER_ADDRESS}\\n")"""

replacement = """    json_files = sorted(INPUT_DIR.glob("scene_*_image_prompts.json"), key=_scene_num)
    
    # Filter by SCENES_TO_GEN if provided
    import os
    scene_filter_env = os.environ.get("SCENES_TO_GEN", "").strip()
    if scene_filter_env:
        try:
            allowed = {int(x.strip()) for x in scene_filter_env.split(',')}
            json_files = [f for f in json_files if _scene_num(f) in allowed]
            print(f"\\nApplying scene filter: {allowed}")
        except Exception as e:
            print(f"\\nWarning: Could not parse SCENES_TO_GEN \\'{scene_filter_env}\\': {e}")

    if not json_files:
        print(f"No JSON files found in {INPUT_DIR} matching the filter.")
        return

    print(f"Found {len(json_files)} scene(s) to process. RunPod: {SERVER_ADDRESS}\\n")"""

if target in text:
    new_text = text.replace(target, replacement)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("image.py updated successfully.")
else:
    print("Warning: target string not found in image.py.")
