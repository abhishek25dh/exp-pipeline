import json
import sys
import requests
import websocket
import uuid
import os
import random
from pathlib import Path

# --- CONFIGURATION ---
RUNPOD_URL = os.environ.get("RUNPOD_URL", "1ke81hlfzpqxqs-8188.proxy.runpod.net")
INPUT_DIR = Path("./assets/image_prompts")
OUTPUT_BASE_DIR = Path("./assets/outputs")

# Connect to the RunPod API
SERVER_ADDRESS = RUNPOD_URL
CLIENT_ID = str(uuid.uuid4())

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": CLIENT_ID}
    headers = {'Content-Type': 'application/json'}
    res = requests.post(f"https://{SERVER_ADDRESS}/prompt", data=json.dumps(p), headers=headers, timeout=60)
    return res.json()

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = requests.compat.urlencode(data)
    res = requests.get(f"https://{SERVER_ADDRESS}/view?{url_values}", timeout=120)
    return res.content

def wait_and_download(prompt, save_path):
    ws = websocket.WebSocket()
    try:
        ws.settimeout(300)  # 5 min max wait per image
        ws.connect(f"wss://{SERVER_ADDRESS}/ws?clientId={CLIENT_ID}")

        prompt_id = queue_prompt(prompt)['prompt_id']
        print(f"Queued generation... (ID: {prompt_id})")

        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break
            else:
                continue

        history_res = requests.get(f"https://{SERVER_ADDRESS}/history/{prompt_id}", timeout=120).json()
        history = history_res[prompt_id]

        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])

                    # Save to the specific scene folder
                    with open(save_path, "wb") as f:
                        f.write(image_data)
                    print(f"Saved to: {save_path}")
    finally:
        ws.close()

def run_automation():
    # Sort scene files by scene number so they process in order
    import re as _re
    def _scene_num(p):
        m = _re.search(r'scene_(\d+)', p.stem)
        return int(m.group(1)) if m else 0

    json_files = sorted(INPUT_DIR.glob("scene_*_image_prompts.json"), key=_scene_num)
    
    # Filter by SCENES_TO_GEN if provided
    import os
    scene_filter_env = os.environ.get("SCENES_TO_GEN", "").strip()
    if scene_filter_env:
        try:
            allowed = {int(x.strip()) for x in scene_filter_env.split(',')}
            json_files = [f for f in json_files if _scene_num(f) in allowed]
            print(f"\nApplying scene filter: {allowed}")
        except Exception as e:
            print(f"\nWarning: Could not parse SCENES_TO_GEN \'{scene_filter_env}\': {e}")

    if not json_files:
        print(f"No JSON files found in {INPUT_DIR} matching the filter.")
        return

    print(f"Found {len(json_files)} scene(s) to process. RunPod: {SERVER_ADDRESS}\n")

    workflow_template = {
        "60": {"inputs": {"filename_prefix": "remote_gen", "images": ["83:8", 0]}, "class_type": "SaveImage"},
        "83:30": {"inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}, "class_type": "CLIPLoader"},
        "83:29": {"inputs": {"vae_name": "ae.safetensors"}, "class_type": "VAELoader"},
        "83:13": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptySD3LatentImage"},
        "83:33": {"inputs": {"conditioning": ["83:27", 0]}, "class_type": "ConditioningZeroOut"},
        "83:8": {"inputs": {"samples": ["83:3", 0], "vae": ["83:29", 0]}, "class_type": "VAEDecode"},
        "83:3": {"inputs": {"seed": 0, "steps": 4, "cfg": 1, "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1, "model": ["83:28", 0], "positive": ["83:27", 0], "negative": ["83:33", 0], "latent_image": ["83:13", 0]}, "class_type": "KSampler"},
        "83:27": {"inputs": {"text": "", "clip": ["83:30", 0]}, "class_type": "CLIPTextEncode"},
        "83:28": {"inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"}
    }

    total_images = 0
    done_images = 0
    failed_images = []

    # Validate JSON files — skip corrupted ones instead of aborting
    corrupted = []
    for json_file in json_files:
        with open(json_file, "r") as f:
            job_data = json.load(f)
        for el in job_data.get("elements", []):
            if not isinstance(el, dict) or "image_prompt" not in el or "filename" not in el:
                corrupted.append(json_file.name)
                break
    if corrupted:
        print(f"WARNING: Skipping corrupted image prompt files: {corrupted}")
        print("Each element must have 'image_prompt' and 'filename' keys.")
        json_files = [f for f in json_files if f.name not in corrupted]
        if not json_files:
            print("ERROR: All image prompt files are corrupted. Nothing to generate.")
            sys.exit(1)

    # Count total images needed
    for json_file in json_files:
        with open(json_file, "r") as f:
            job_data = json.load(f)
        total_images += len(job_data.get("elements", []))

    for scene_idx, json_file in enumerate(json_files, 1):
        with open(json_file, "r") as f:
            job_data = json.load(f)

        scene_id = job_data.get("scene_id", json_file.stem)
        elements = job_data.get("elements", [])

        scene_output_dir = OUTPUT_BASE_DIR / scene_id
        scene_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== Scene {scene_idx}/{len(json_files)}: {scene_id} ({len(elements)} images) ===")

        for el_idx, element in enumerate(elements, 1):
            prompt_text = element["image_prompt"]
            file_name = element["filename"]
            full_save_path = scene_output_dir / file_name

            if full_save_path.exists():
                print(f"  [{el_idx}/{len(elements)}] Skipped (exists): {file_name}")
                done_images += 1
                continue

            print(f"  [{el_idx}/{len(elements)}] Generating: {file_name}")

            import copy
            workflow = copy.deepcopy(workflow_template)
            workflow["83:27"]["inputs"]["text"] = prompt_text
            workflow["83:3"]["inputs"]["seed"] = random.randint(1, 10**15)

            success = False
            for attempt in range(1, 4):
                try:
                    wait_and_download(workflow, full_save_path)
                    success = True
                    break
                except Exception as e:
                    print(f"  ERROR (attempt {attempt}/3): {e}")
                    if attempt < 3:
                        print(f"  Retrying...")

            if success:
                done_images += 1
            else:
                failed_images.append(f"{scene_id}/{file_name}")
                print(f"  FAILED {file_name} after 3 attempts.")
            print(f"  Progress: {done_images}/{total_images} images total")

    print(f"\nDone. {done_images}/{total_images} images generated.")
    if failed_images:
        print(f"\nWARNING: {len(failed_images)} image(s) failed (will use placeholder):")
        for f in failed_images:
            print(f"  - {f}")
        # Don't exit(1) — partial success is fine, render_video handles missing images

if __name__ == "__main__":
    run_automation()