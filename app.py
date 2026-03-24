import gradio as gr
import json
import os
import sys
import asyncio
import base64
import io
import requests
import websocket
import uuid
import random
import subprocess
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import ImageClip, CompositeVideoClip, AudioFileClip, ColorClip

# =======================================================================
# 0. CONFIGURATION & SETUP
# =======================================================================
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
DIRS_TO_CREATE = [
    os.path.join(ASSETS_DIR, 'scene_prompts'),
    os.path.join(ASSETS_DIR, 'directorscript'),
    os.path.join(ASSETS_DIR, 'image_prompts'),
    os.path.join(ASSETS_DIR, 'outputs'),
    os.path.join(ASSETS_DIR, 'scenes_audio'),
    os.path.join(ASSETS_DIR, 'timings'),
    os.path.join(ASSETS_DIR, 'layouts') 
]
for d in DIRS_TO_CREATE:
    os.makedirs(d, exist_ok=True)

RUNPOD_URL = "3fprhqv1uk7th5-8188.proxy.runpod.net"
CLIENT_ID = str(uuid.uuid4())

# =======================================================================
# 1. COMFYUI GENERATION ENGINE
# =======================================================================
def queue_comfy_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    headers = {'Content-Type': 'application/json'}
    res = requests.post(f"https://{RUNPOD_URL}/prompt", data=json.dumps(p), headers=headers)
    return res.json()

def get_comfy_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = requests.compat.urlencode(data)
    res = requests.get(f"https://{RUNPOD_URL}/view?{url_values}")
    return res.content

def generate_single_image(prompt_text, save_path):
    print(f"--- ComfyUI Call ---\nPrompt: {prompt_text}\nSaving to: {save_path}\n--------------------")
    workflow = {
        "60": {"inputs": {"filename_prefix": "remote_gen", "images": ["83:8", 0]}, "class_type": "SaveImage"},
        "83:30": {"inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}, "class_type": "CLIPLoader"},
        "83:29": {"inputs": {"vae_name": "ae.safetensors"}, "class_type": "VAELoader"},
        "83:13": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptySD3LatentImage"},
        "83:33": {"inputs": {"conditioning": ["83:27", 0]}, "class_type": "ConditioningZeroOut"},
        "83:8": {"inputs": {"samples": ["83:3", 0], "vae": ["83:29", 0]}, "class_type": "VAEDecode"},
        "83:3": {"inputs": {"seed": random.randint(1, 10**15), "steps": 4, "cfg": 1, "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1, "model": ["83:28", 0], "positive": ["83:27", 0], "negative": ["83:33", 0], "latent_image": ["83:13", 0]}, "class_type": "KSampler"},
        "83:27": {"inputs": {"text": prompt_text, "clip": ["83:30", 0]}, "class_type": "CLIPTextEncode"},
        "83:28": {"inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"}
    }
    try:
        ws = websocket.WebSocket()
        ws_url = f"wss://{RUNPOD_URL}/ws?clientId={CLIENT_ID}"
        ws.connect(ws_url, header={"Origin": f"https://{RUNPOD_URL}"})
        
        prompt_id = queue_comfy_prompt(workflow)['prompt_id']

        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break 
        ws.close()

        history_res = requests.get(f"https://{RUNPOD_URL}/history/{prompt_id}").json()
        history = history_res[prompt_id]
        
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = get_comfy_image(image['filename'], image['subfolder'], image['type'])
                    with open(save_path, "wb") as f:
                        f.write(image_data)
                    return True
    except Exception as e:
        print(f"ComfyUI Error: {e}")
    return False

# =======================================================================
# 2. MEDIA LOADERS & PIPELINE LOGIC
# =======================================================================
def create_image_clip_safe(filepath, add_shadow=False, angle=0):
    img = Image.open(filepath).convert("RGBA")
    if add_shadow:
        blur_radius, offset = 20, (10, 10)
        padding = blur_radius * 2 + max(abs(offset[0]), abs(offset[1]))
        new_w, new_h = img.width + 2 * padding, img.height + 2 * padding
        canvas = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        alpha = img.split()[3]
        shadow_color = Image.new("RGBA", img.size, (0, 0, 0, 130))
        canvas.paste(shadow_color, (padding + offset[0], padding + offset[1]), mask=alpha)
        canvas = canvas.filter(ImageFilter.GaussianBlur(blur_radius))
        canvas.paste(img, (padding, padding), mask=img)
        img = canvas
    if angle != 0:
        resample_mode = getattr(Image, 'Resampling', Image).BICUBIC
        img = img.rotate(-angle, expand=True, resample=resample_mode)
    img_np = np.array(img)
    rgb_np = img_np[:, :, :3]
    alpha_np = img_np[:, :, 3] / 255.0
    clip = ImageClip(rgb_np)
    mask = ImageClip(alpha_np, ismask=True)
    return clip.set_mask(mask)

def create_text_clip_with_pillow(text, fontsize=70, color=(255, 255, 255), stroke_color=(0, 0, 0), stroke_width=3, bg_color=None, font_type="comic", angle=0):
    font_path = None
    font_names = ["comic.ttf", "Comic Sans MS.ttf", "Comic Sans.ttf", "arial.ttf"]
    for fn in font_names:
        for path in [fn, f"/Library/Fonts/{fn}", f"C:\\Windows\\Fonts\\{fn}"]:
            if os.path.exists(path): font_path = path; break
        if font_path: break
    try: font = ImageFont.truetype(font_path, fontsize) if font_path else ImageFont.load_default()
    except: font = ImageFont.load_default()
    dummy_img = Image.new('RGBA', (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    h_padding, v_padding = int(fontsize * 0.1), int(fontsize * 0.1)
    img_width, img_height = int(text_w + (h_padding * 2) + (stroke_width * 2)), int(text_h + (v_padding * 2) + (stroke_width * 2))
    img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if bg_color: draw.rectangle([0, 0, img_width, img_height], fill=bg_color)
    draw.text((h_padding + stroke_width - bbox[0], v_padding + stroke_width - bbox[1]), text, font=font, fill=color, stroke_width=stroke_width if not bg_color else 0, stroke_fill=stroke_color)
    if angle != 0:
        resample_mode = getattr(Image, 'Resampling', Image).BICUBIC
        img = img.rotate(-angle, expand=True, resample=resample_mode)
    img_np = np.array(img)
    rgb_np = img_np[:, :, :3]
    alpha_np = img_np[:, :, 3] / 255.0
    clip = ImageClip(rgb_np)
    mask = ImageClip(alpha_np, ismask=True)
    return clip.set_mask(mask)

def build_image_dict(images_list, scene_id=None):
    img_dict = {}
    local_dir = os.path.join(ASSETS_DIR, 'outputs')
    if os.path.exists(local_dir):
        for f in os.listdir(local_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                img_dict[os.path.splitext(f)[0].lower()] = os.path.join(local_dir, f)
    if scene_id:
        scene_dir = os.path.join(local_dir, scene_id)
        if os.path.exists(scene_dir):
            for f in os.listdir(scene_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    img_dict[os.path.splitext(f)[0].lower()] = os.path.join(scene_dir, f)
    if images_list:
        for img in images_list:
            p = str(img)
            img_dict[os.path.splitext(os.path.basename(p))[0].lower()] = p
    return img_dict

def get_asset_prompts(scene_id):
    """Refined to ensure we always get the absolute latest from disk."""
    if not scene_id:
        return []
    prompt_file = os.path.join(ASSETS_DIR, 'image_prompts', f"{scene_id}_image_prompts.json")
    if not os.path.exists(prompt_file):
        print(f"Warning: Prompt file {prompt_file} not found.")
        return []
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            elements = data.get("elements", [])
            print(f"Fetched {len(elements)} image prompts from {prompt_file}")
            return elements
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        return []

def rebuild_canvas_payload(scene_id, live_dir_json, live_time_json, images_list):
    try:
        dir_data = json.loads(live_dir_json)
        time_state = json.loads(live_time_json) if live_time_json else []
        img_dict = build_image_dict(images_list, scene_id=scene_id)
        
        canvas_items = []
        elements_list = dir_data.get("elements", [])

        for item in elements_list:
            el_id = item.get("element_id")
            el_type = item.get("type", "image")
            
            t_info = next((t for t in time_state if t.get("element_id") == el_id), {})
            start_time = t_info.get("start", 0)
            end_time = t_info.get("end", 10.0)

            filename = "arrow.png" if el_type == "arrow" else item.get("filename", "")

            base_item = {
                "id": el_id, "type": el_type, "filename": filename,
                "text_content": item.get("text_content", ""), "left": item.get("x", 960) / 2.0, 
                "top": item.get("y", 540) / 2.0, "scale": item.get("scale", 1.0) / 2.0, 
                "property": item.get("property", ""), "angle": item.get("angle", 0), 
                "start": start_time, "end": end_time, "animation": item.get("animation", "none"), 
                "typing_speed": item.get("typing_speed", 0.5), "original_data": item
            }

            if el_type.startswith("text_"):
                base_item.update({"fabric_type": "text"})
                canvas_items.append(base_item)
            else:
                base_name = os.path.splitext(filename)[0].lower()
                if base_name in img_dict:
                    try:
                        with Image.open(img_dict[base_name]).convert("RGBA") as img:
                            buf = io.BytesIO(); img.save(buf, format="PNG")
                            base_item.update({"fabric_type": "image", "src": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"})
                            canvas_items.append(base_item)
                    except: pass
                else:
                    base_item.update({"fabric_type": "missing_image"})
                    canvas_items.append(base_item)
                    
        return json.dumps({"scene_id": scene_id, "items": canvas_items})
    except Exception as e:
        print(f"Payload rebuild failed: {e}")
        return "[]"

def get_gallery_html(scene_id):
    prompt_elements = get_asset_prompts(scene_id)
    output_dir = os.path.join(ASSETS_DIR, 'outputs', scene_id)
    
    html = "<div style='display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 10px; margin-top: 10px;'>"
    for el in prompt_elements:
        fname = el.get("filename")
        if not fname: continue
        fpath = os.path.join(output_dir, fname)
        exists = os.path.exists(fpath)
        status_color = "#4CAF50" if exists else "#f44336"
        img_src = ""
        if exists:
            try:
                with open(fpath, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode()
                    img_src = f"data:image/png;base64,{encoded_string}"
            except: pass
        
        html += f"""
        <div style='border: 1px solid #ddd; padding: 5px; text-align: center; border-radius: 4px; background: #fafafa;'>
            <div style='height: 80px; display: flex; align-items: center; justify-content: center; background: #eee; margin-bottom: 5px;'>
                {f'<img src="{img_src}" style="max-height: 100%; max-width: 100%;">' if exists else '❌'}
            </div>
            <div style='font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: {status_color}; font-weight: bold;'>{fname}</div>
        </div>
        """
    return html + "</div>"

# =======================================================================
# 3. PIPELINE AUTOMATION FUNCTIONS
# =======================================================================

def generate_pipeline_director_script(prompt_text, scene_no, layout_no, progress=gr.Progress()):
    if not prompt_text or not scene_no:
        raise gr.Error("Provide Prompt and Scene Number.")
    
    scene_id = f"scene_{int(scene_no)}"
    progress(0.1, desc="Saving prompt and layout choice...")
    prompt_data = {
        "prompt": f"{scene_id}: {prompt_text}",
        "layout": layout_no
    }
    prompt_path = os.path.join(ASSETS_DIR, 'scene_prompts', f"{scene_id}_prompt.json")
    with open(prompt_path, "w") as f:
        json.dump(prompt_data, f, indent=4)
        
    progress(0.4, desc="Generating Director Script (Python)...")
    try:
        subprocess.run(["python", "generate_director_script.py", str(int(scene_no)), str(layout_no)], check=True)
    except Exception as e:
        print(f"Warning: generate_director_script.py execution error: {e}")

    progress(0.9, desc="Pulling generated script...")
    director_path = os.path.join(ASSETS_DIR, 'directorscript', f"{scene_id}_director.json")
    if not os.path.exists(director_path):
        raise gr.Error(f"Generation failed: {director_path} not found.")
        
    return handle_manual_load(director_path, None, None, None, None, scene_no)

def generate_pipeline_image_prompts(scene_id_store, live_dir_json, scene_no_input, progress=gr.Progress()):
    resolved_scene_id = scene_id_store
    if not resolved_scene_id and scene_no_input:
        resolved_scene_id = f"scene_{int(scene_no_input)}"
    
    if not live_dir_json and resolved_scene_id:
        disk_path = os.path.join(ASSETS_DIR, 'directorscript', f"{resolved_scene_id}_director.json")
        if os.path.exists(disk_path):
            with open(disk_path, 'r', encoding='utf-8') as f:
                live_dir_json = f.read()

    if not resolved_scene_id or not live_dir_json:
        raise gr.Error(f"No scene active or no director script data found.")
    
    progress(0.2, desc="Saving script state...")
    try:
        dir_data = json.loads(live_dir_json)
        scene_number = resolved_scene_id.replace("scene_", "")
        director_path = os.path.join(ASSETS_DIR, 'directorscript', f"{resolved_scene_id}_director.json")
        with open(director_path, "w", encoding='utf-8') as f:
            json.dump(dir_data, f, indent=4)
            f.flush()
            os.fsync(f.fileno()) 
    except Exception as e:
        raise gr.Error(f"Failed to process script JSON: {e}")
        
    progress(0.5, desc="Generating Image Prompts (Python)...")
    try:
        subprocess.run(["python", "generate_prompts.py", str(scene_number)], check=True)
    except Exception as e:
        print(f"Warning: generate_prompts.py execution error: {e}")
        
    progress(0.9, desc="Updating UI...")
    prompt_list = [el.get("filename") for el in get_asset_prompts(resolved_scene_id) if el.get("filename")]
    
    return gr.update(choices=prompt_list), get_gallery_html(resolved_scene_id), f"✅ Image Prompts generated for {resolved_scene_id}!", resolved_scene_id

def run_ai_image_generation(live_dir_json, live_time_json, images_list, scene_no_input, progress=gr.Progress()):
    resolved_scene_id = f"scene_{int(scene_no_input)}" if scene_no_input else "default_scene"
    
    if not live_dir_json and resolved_scene_id:
        disk_path = os.path.join(ASSETS_DIR, 'directorscript', f"{resolved_scene_id}_director.json")
        if os.path.exists(disk_path):
            with open(disk_path, 'r', encoding='utf-8') as f:
                live_dir_json = f.read()

    if not live_dir_json: raise gr.Error("Load a Director Script first.")
    
    try:
        data = json.loads(live_dir_json)
        scene_id = data.get("scene_id", resolved_scene_id)
        
        prompt_elements = get_asset_prompts(scene_id)
        if not prompt_elements: 
            raise gr.Error(f"No prompt JSON found at image_prompts/{scene_id}_image_prompts.json. Run 'Generate Image Prompts' first.")

        output_dir = os.path.join(ASSETS_DIR, 'outputs', scene_id)
        os.makedirs(output_dir, exist_ok=True)
        
        gen_count = 0
        for idx, el in enumerate(prompt_elements):
            p_text = el.get("image_prompt") or el.get("image-prompt")
            f_name = el.get("filename")
            if not p_text or not f_name: continue
            
            progress(idx / len(prompt_elements), desc=f"Generating {f_name}...")
            save_path = os.path.join(output_dir, f_name)
            if generate_single_image(p_text, save_path): gen_count += 1
            
        filenames = [el.get("filename") for el in prompt_elements if el.get("filename")]
        new_payload = rebuild_canvas_payload(scene_id, live_dir_json, live_time_json, images_list)
        
        return f"✅ Generated {gen_count} images for {scene_id}.", get_gallery_html(scene_id), gr.update(choices=filenames), new_payload
    except Exception as e:
        raise gr.Error(f"AI Generation Failed: {str(e)}")

def regenerate_selected_asset(scene_id_store, target_regen, live_dir_json, live_time_json, images_list, scene_no_input):
    resolved_scene_id = None
    if live_dir_json:
        try: resolved_scene_id = json.loads(live_dir_json).get("scene_id")
        except: pass
    
    if not resolved_scene_id:
        resolved_scene_id = scene_id_store or (f"scene_{int(scene_no_input)}" if scene_no_input else None)
    
    if not resolved_scene_id or not target_regen: 
        raise gr.Error("No asset selected or scene ID missing.")
    
    prompt_elements = get_asset_prompts(resolved_scene_id)
    target = next((el for el in prompt_elements if el.get("filename") == target_regen), None)
    
    if not target:
        raise gr.Error(f"File {target_regen} not found in prompt list. Fetched {len(prompt_elements)} items.")

    target_prompt_text = target.get("image_prompt") or target.get("image-prompt")
    
    if not target_prompt_text:
        raise gr.Error(f"Prompt text not found for {target_regen}.")
    
    output_dir = os.path.join(ASSETS_DIR, 'outputs', resolved_scene_id)
    save_path = os.path.join(output_dir, target_regen)
    
    if generate_single_image(target_prompt_text, save_path):
        new_payload = rebuild_canvas_payload(resolved_scene_id, live_dir_json, live_time_json, images_list)
        return f"✅ Regenerated {target_regen}", get_gallery_html(resolved_scene_id), new_payload
    else:
        raise gr.Error(f"Failed to regenerate {target_regen}. WebSocket error.")

def handle_manual_load(director_file, images_list, current_audio, current_transcript, current_timings, scene_no_input):
    file_path = None
    if scene_no_input:
        potential_path = os.path.join(ASSETS_DIR, 'directorscript', f"scene_{int(scene_no_input)}_director.json")
        if os.path.exists(potential_path):
            file_path = potential_path
            
    if not file_path and director_file:
        file_path = director_file if isinstance(director_file, str) else director_file.name
            
    if not file_path or not os.path.exists(file_path):
        return "[]", "❌ No director script found to load.", current_audio, current_transcript, current_timings, "", gr.update(choices=[]), "", director_file
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f: director_script = json.load(f)
    except Exception as e:
        return "[]", f"❌ Error reading JSON: {e}", current_audio, current_transcript, current_timings, "", gr.update(choices=[]), "", director_file
        
    out_a, out_t, out_time = current_audio, current_transcript, current_timings
    if "output" in director_script and "scene_id" in director_script["output"]:
        director_script = director_script["output"]
    scene_id = director_script.get("scene_id", "scene_1")
    
    if scene_id:
        ea = os.path.join(ASSETS_DIR, 'scenes_audio', f"{scene_id}.mp3")
        et = os.path.join(ASSETS_DIR, 'scenes_audio', f"{scene_id}_transcript_full.json")
        etime = os.path.join(ASSETS_DIR, 'timings', f"{scene_id}_timings.json")
        if os.path.exists(ea): out_a = ea
        if os.path.exists(et): out_t = et
        if os.path.exists(etime): out_time = etime
    
    timings_data = []
    if out_time and os.path.exists(out_time) and isinstance(out_time, str):
        with open(out_time, 'r', encoding='utf-8') as f: timings_data = json.load(f)
    elif out_time and not isinstance(out_time, str):
         with open(out_time.name, 'r', encoding='utf-8') as f: timings_data = json.load(f)
    
    img_dict = build_image_dict(images_list, scene_id=scene_id)
    canvas_items = []
    elements_list = director_script.get("elements", director_script.get("images", []))
    
    for item in elements_list:
        el_id = item.get("element_id", item.get("filename", "unknown"))
        el_type = item.get("type", "image")
        t_override = next((t for t in timings_data if t.get("element_id") == el_id), {})
        start_time, end_time = t_override.get("start", item.get("start", 0)), t_override.get("end", item.get("end", 10.0))
        filename = "arrow.png" if el_type == "arrow" else item.get("filename", "")
        
        base_item = {
            "id": el_id, "type": el_type, "filename": filename, "text_content": item.get("text_content", ""), 
            "left": item.get("x", 960)/2.0, "top": item.get("y", 540)/2.0, "scale": item.get("scale", 1.0)/2.0, 
            "property": item.get("property", ""), "angle": item.get("angle", 0), "start": start_time, 
            "end": end_time, "animation": item.get("animation", "none"), "typing_speed": item.get("typing_speed", 0.5), 
            "original_data": item
        }
        
        if el_type.startswith("text_"):
            base_item.update({"fabric_type": "text"})
            canvas_items.append(base_item)
        else:
            base_name = os.path.splitext(filename)[0].lower()
            if base_name in img_dict:
                try:
                    with Image.open(img_dict[base_name]).convert("RGBA") as img:
                        buf = io.BytesIO(); img.save(buf, format="PNG")
                        base_item.update({"fabric_type": "image", "src": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"})
                except: base_item.update({"fabric_type": "missing_image"})
            else:
                base_item.update({"fabric_type": "missing_image"})
            canvas_items.append(base_item)
    
    asset_html = get_gallery_html(scene_id)
    prompt_list = [el.get("filename") for el in get_asset_prompts(scene_id) if el.get("filename")]
    return json.dumps({"scene_id": scene_id, "items": canvas_items}), f"✅ Reloaded: {scene_id}", out_a, out_t, out_time, asset_html, gr.update(choices=prompt_list), scene_id, file_path

def render_final_video(audio_file, transcript_file, timings_file, live_dir_json, live_time_json, images_list, render_quality, hw_accel):
    try:
        dir_state = json.loads(live_dir_json) if live_dir_json else {}
        time_state = json.loads(live_time_json) if live_time_json else []
        scene_id = dir_state.get("scene_id", "final_output")
        audio = AudioFileClip(audio_file)
        res_w, res_h, res_mult = (3840, 2160, 2.0) if "4K" in render_quality else (1920, 1080, 1.0)
        bg_clip = ColorClip(size=(res_w, res_h), color=(255, 255, 255)).set_duration(audio.duration + 1.0)
        all_clips = [bg_clip]
        img_dict = build_image_dict(images_list, scene_id=scene_id)
        target_list = dir_state.get("elements", dir_state.get("images", []))
        for item in target_list:
            el_id, el_type = item.get("element_id", item.get("filename", "")), item.get("type", "image")
            add_shadow = item.get("property") == "shadow"
            t_info = next((t for t in time_state if t.get("element_id") == el_id), {})
            start_time, end_time = t_info.get("start", item.get("start", 0)), t_info.get("end", item.get("end", audio.duration))
            anim_type, rotation = item.get("animation", "none"), item.get('angle', 0)
            cx, cy, js = item.get("x", 960) * res_mult, item.get("y", 540) * res_mult, item.get("scale", 1.0)
            if el_type.startswith("text_"):
                content = item.get("text_content", "")
                t_fs = max(10, int(40 * js * res_mult))
                if el_type == "text_red": clip = create_text_clip_with_pillow(content.strip(), fontsize=t_fs, color=(220, 20, 60), stroke_color=(255, 255, 255), stroke_width=int(4*res_mult), font_type="comic", angle=rotation)
                elif el_type == "text_black": clip = create_text_clip_with_pillow(content.strip(), fontsize=t_fs, color=(0, 0, 0), stroke_color=(255, 255, 255), stroke_width=int(4*res_mult), font_type="comic", angle=rotation)
                elif el_type == "text_highlighted": clip = create_text_clip_with_pillow(content.strip(), fontsize=t_fs, color=(255, 255, 255), bg_color=(255, 165, 0), font_type="comic", angle=rotation)
                else: clip = create_text_clip_with_pillow(content.strip(), fontsize=t_fs, color=(0, 0, 0), stroke_width=0, angle=rotation)
                clip = clip.set_start(start_time).set_end(end_time); sc = 1.0
            else:
                filename = "arrow.png" if el_type == "arrow" else item.get("filename", "")
                base_name = os.path.splitext(filename)[0].lower()
                if base_name not in img_dict: continue
                clip = create_image_clip_safe(img_dict[base_name], add_shadow=add_shadow, angle=rotation).set_start(start_time).set_end(end_time)
                sc = js * res_mult
            bw, bh = clip.size
            if anim_type == "pop":
                def pop_scale(t, s=sc, w=bw, h=bh):
                    m = max(0.001, 2.0 / min(w, h))
                    v = s * 1.2 * (t / 0.2) if t < 0.2 else (s * (1.2 - 0.2 * ((t - 0.2) / 0.1)) if t < 0.3 else s)
                    return max(m, v)
                def pop_pos(t, x=cx, y=cy, w=bw, h=bh, s=sc):
                    curr = pop_scale(t, s, w, h); return (x - (w * curr) / 2, y - (h * curr) / 2)
                clip = clip.resize(pop_scale).set_position(pop_pos)
            elif anim_type == "fade_up":
                clip = clip.resize(sc)
                def move_up(t, x=cx, y=cy, w=bw, h=bh, s=sc):
                    curr_y = y + (150*res_mult) * (1 - (t / 0.4)) if t < 0.4 else y
                    return (x - (w * s) / 2, curr_y - (h * s) / 2)
                clip = clip.set_position(move_up).crossfadein(0.4)
            elif anim_type == "typing":
                clip = clip.resize(sc); cw, ch = clip.size
                typing_dur = item.get("typing_speed", 0.5)
                def typing_mask(gf, t, dur=typing_dur, width=cw):
                    f = gf(t); prog = min(1.0, t / dur) if dur > 0 else 1.0
                    limit = int(width * prog); new_f = np.zeros_like(f)
                    if limit > 0: new_f[:, :limit] = f[:, :limit]
                    return new_f
                if clip.mask: clip.mask = clip.mask.fl(typing_mask)
                clip = clip.set_position((cx - cw / 2, cy - ch / 2))
            else:
                clip = clip.resize(sc).set_position((cx - (bw * sc) / 2, cy - (bh * sc) / 2))
            all_clips.append(clip)
        final_video = CompositeVideoClip(all_clips, size=(res_w, res_h)).set_audio(audio).set_duration(audio.duration)
        output_filename = f"{scene_id}.mp4"
        codec_map = {"CPU (Standard)": ("libx264", "ultrafast"), "NVIDIA GPU (Fast)": ("h264_nvenc", "fast"), "AMD GPU": ("h264_amf", None), "Mac (M1/M2/M3)": ("h264_videotoolbox", None)}
        sel_c, sel_p = codec_map.get(hw_accel, ("libx264", "ultrafast"))
        render_args = {"fps": 30, "audio_codec": "aac", "threads": os.cpu_count() or 4, "ffmpeg_params": ["-pix_fmt", "yuv420p"]}
        if sel_p: render_args["preset"] = sel_p
        try: final_video.write_videofile(output_filename, codec=sel_c, **render_args)
        except: final_video.write_videofile(output_filename, codec="libx264", preset="ultrafast", **render_args)
        return output_filename
    except Exception as e:
        import traceback; print(traceback.format_exc())
        raise gr.Error(f"Render failed: {str(e)}")

def save_modified_director_script(live_dir_json):
    if not live_dir_json: raise gr.Error("No director script data to save.")
    try:
        dir_data = json.loads(live_dir_json)
        scene_id = dir_data.get("scene_id", "scene_unknown")
        filename = f"{scene_id}_director.json"
        filepath = os.path.join(ASSETS_DIR, 'directorscript', filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dir_data, f, indent=2)
        return gr.update(value=filepath, visible=True, label=f"✅ Saved to: assets/directorscript/{filename}")
    except Exception as e:
        raise gr.Error(f"Failed to save script: {str(e)}")

# =======================================================================
# 4. FRONTEND JAVASCRIPT & EDITOR LOGIC
# =======================================================================

custom_js = """
window.v_canvas = null;
window.v_scene_id = "scene_1";

function initInstanceCanvas(dataStr) {
    if (!dataStr || dataStr === "[]") return;
    function start() {
        if (!window.v_canvas) {
            window.v_canvas = new fabric.Canvas('main-canvas', { backgroundColor: '#ffffff' });
            window.v_canvas.on('object:modified', updatePy);
            window.v_canvas.on('object:rotating', updatePy);
            window.v_canvas.on('selection:created', loadProperties);
            window.v_canvas.on('selection:updated', loadProperties);
            window.v_canvas.on('selection:cleared', clearProperties);
        }
        loadItems(dataStr);
    }
    if (typeof fabric === 'undefined') {
        let s = document.createElement('script'); s.src = 'https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js';
        s.onload = start; document.head.appendChild(s);
    } else { start(); }
    function loadItems(str) {
        let parsed = JSON.parse(str); window.v_scene_id = parsed.scene_id || "scene_1";
        let c = window.v_canvas; c.clear(); c.backgroundColor = '#ffffff';
        let items = parsed.items || [];
        items.forEach(item => {
            let sh = item.property === "shadow" ? new fabric.Shadow({color:'rgba(0,0,0,0.5)', blur:15, offsetX:5, offsetY:5}) : null;
            let common = { id:item.id, left:item.left, top:item.top, scaleX:item.scale, scaleY:item.scale, originX:'center', originY:'center', borderColor:'#00ff00', cornerColor:'#00ff00', shadow:sh, angle:item.angle||0, customData:item };
            if (item.fabric_type === "text") {
                let fill = item.type === "text_red" ? "#dc143c" : "#000000";
                let bg = item.type === "text_highlighted" ? "#ffa500" : null;
                let textColor = item.type === "text_highlighted" ? "#ffffff" : fill;
                c.add(new fabric.IText(item.text_content, {...common, fontSize: 40, fontFamily: 'Comic Sans MS, cursive', fill: textColor, backgroundColor: bg}));
            } else if (item.fabric_type === "missing_image") {
                // IMPORTANT: Ensure placeholders use the 1024 base dimensions to keep scale constant
                let rect = new fabric.Rect({...common, width: 1024, height: 1024, fill: '#cccccc', stroke: '#ff0000', strokeWidth: 5, strokeDashArray: [20, 20]});
                c.add(rect);
            } else {
                fabric.Image.fromURL(item.src, (img) => { if(img){ img.set(common); c.add(img); } });
            }
        });
        setTimeout(() => { c.renderAll(); updatePy(); }, 300);
    }
}

function updatePy() {
    let c = window.v_canvas; if(!c) return;
    let d_el = []; let t_el = [];
    c.getObjects().forEach(obj => {
        let r = obj.customData.original_data ? JSON.parse(JSON.stringify(obj.customData.original_data)) : {};
        r.element_id = obj.id; r.type = obj.customData.type;
        if (obj.customData.filename) r.filename = obj.customData.filename;
        if (obj.customData.text_content) r.text_content = obj.customData.text_content;
        if (obj.customData.phrase) r.phrase = obj.customData.phrase;
        if (obj.customData.description) r.description = obj.customData.description;
        
        // Convert canvas pos back to director coordinate system (1920x1080)
        r.x = Math.round(obj.left * 2); 
        r.y = Math.round(obj.top * 2);
        
        // Scale is relative to the base dimension (1024 for images, or visually for text)
        r.scale = Number((obj.scaleX * 2).toFixed(2)); 
        r.angle = Math.round(obj.angle);
        
        r.animation = obj.customData.animation || "pop"; 
        r.property = obj.customData.property || ""; 
        if (r.animation === "typing") r.typing_speed = obj.customData.typing_speed || 0.5;
        
        let dir_r = {...r}; delete dir_r.start; delete dir_r.end; d_el.push(dir_r);
        t_el.push({element_id: obj.id, phrase: r.phrase || "", start: obj.customData.start || 0, end: obj.customData.end || 10});
    });
    let db = document.getElementById('live-dir-box'); 
    if (db) { 
        let ta = db.querySelector('textarea'); 
        if (ta) { 
            ta.value = JSON.stringify({scene_id: window.v_scene_id, elements: d_el}, null, 2); 
            ta.dispatchEvent(new Event('input', { bubbles: true })); 
            ta.dispatchEvent(new Event('change', { bubbles: true })); 
        } 
    }
}

window.moveLayer = function(dir) {
    let c = window.v_canvas; let a = c.getActiveObject(); if (!a) return;
    if (dir === 'up') a.bringForward(); else a.sendBackwards();
    c.renderAll(); updatePy();
}

window.deleteSelected = function() {
    let c = window.v_canvas; let a = c.getActiveObject(); if (!a) return;
    c.remove(a); clearProperties(); updatePy();
}

window.addNewElement = function(type) {
    let c = window.v_canvas; if(!c) return;
    let newId = type + '_' + Date.now();
    
    // Default visually appropriate scale for a 1024 base on 960 canvas
    let baseScale = 0.2; 
    let common = { 
        id: newId, 
        left: 480, top: 270, 
        scaleX: baseScale, scaleY: baseScale, 
        originX:'center', originY:'center', 
        borderColor:'#00ff00', cornerColor:'#00ff00', 
        angle: 0 
    };
    
    // Initialize original_data structure immediately
    let customData = { 
        id: newId, 
        type: type, 
        animation: "pop", 
        x: 960, y: 540, 
        scale: baseScale * 2, 
        angle: 0,
        original_data: {
            element_id: newId,
            type: type,
            animation: "pop",
            x: 960, y: 540,
            scale: baseScale * 2,
            angle: 0
        }
    };
    
    if (type.startsWith("text")) {
        customData.text_content = "NEW TEXT"; customData.phrase = "new text";
        customData.original_data.text_content = "NEW TEXT";
        customData.original_data.phrase = "new text";
        let t = new fabric.IText("NEW TEXT", {...common, fontSize: 40, fontFamily: 'Comic Sans MS, cursive', fill: '#000'});
        t.customData = customData; c.add(t);
    } else if (type === "arrow") {
        customData.filename = "arrow.png";
        customData.original_data.filename = "arrow.png";
        let rect = new fabric.Rect({...common, width: 1024, height: 1024, fill: 'rgba(255,0,0,0.5)', stroke: 'red', strokeWidth: 10});
        rect.customData = customData; c.add(rect);
    } else {
        customData.filename = "new_image_" + Date.now() + ".jpg";
        customData.phrase = "new element"; 
        customData.description = "Describe this element for AI generation...";
        customData.original_data.filename = customData.filename;
        customData.original_data.phrase = "new element";
        customData.original_data.description = "Describe this element for AI generation...";
        
        let rect = new fabric.Rect({...common, width: 1024, height: 1024, fill: '#cccccc', stroke: '#ff0000', strokeWidth: 5});
        rect.customData = customData; c.add(rect);
    }
    c.setActiveObject(c.getObjects()[c.getObjects().length - 1]);
    c.renderAll(); updatePy();
}

function loadProperties() {
    let c = window.v_canvas; let a = c.getActiveObject(); if (!a) return;
    let cd = a.customData || {};
    let od = cd.original_data || {};

    document.getElementById('prop-id').value = cd.id || '';
    document.getElementById('prop-type').value = cd.type || od.type || '';
    document.getElementById('prop-filename').value = cd.filename || od.filename || '';
    document.getElementById('prop-phrase').value = cd.phrase || od.phrase || '';
    document.getElementById('prop-desc').value = cd.description || od.description || '';
    document.getElementById('prop-text').value = cd.text_content || od.text_content || '';
    
    document.getElementById('prop-filename-div').style.display = cd.type.startsWith('text') ? 'none' : 'block';
    document.getElementById('prop-desc-div').style.display = cd.type.startsWith('text') || cd.type === 'arrow' ? 'none' : 'block';
    document.getElementById('prop-text-div').style.display = cd.type.startsWith('text') ? 'block' : 'none';
}

function clearProperties() {
    document.getElementById('prop-id').value = '';
    ['prop-type', 'prop-filename', 'prop-phrase', 'prop-desc', 'prop-text'].forEach(id => {
        let el = document.getElementById(id);
        if(el) el.value = '';
    });
}

window.applyProperties = function() {
    let c = window.v_canvas; let a = c.getActiveObject(); if (!a) return;
    
    if (!a.customData.original_data) a.customData.original_data = {};
    
    a.customData.type = document.getElementById('prop-type').value;
    a.customData.filename = document.getElementById('prop-filename').value;
    a.customData.phrase = document.getElementById('prop-phrase').value;
    a.customData.description = document.getElementById('prop-desc').value;
    a.customData.text_content = document.getElementById('prop-text').value;
    
    a.customData.original_data.type = a.customData.type;
    a.customData.original_data.filename = a.customData.filename;
    a.customData.original_data.phrase = a.customData.phrase;
    a.customData.original_data.description = a.customData.description;
    a.customData.original_data.text_content = a.customData.text_content;

    if (a.customData.type.startsWith('text') && a.set) { a.set({text: a.customData.text_content}); }
    c.renderAll(); updatePy();
}
"""

editor_html = """
<div style="padding: 15px; background: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; margin-top: 10px;">
    <h4 style="margin-top:0;">🛠️ Element Properties</h4>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <div><label>ID:</label> <input id="prop-id" type="text" readonly style="width:100%; padding:4px;"></div>
        <div><label>Type:</label> <select id="prop-type" onchange="applyProperties()" style="width:100%; padding:4px;">
            <option value="image">Image</option>
            <option value="arrow">Arrow</option>
            <option value="text_black">Text (Black)</option>
            <option value="text_red">Text (Red)</option>
            <option value="text_highlighted">Text (Highlighted)</option>
        </select></div>
        <div><label>Phrase (Timing sync):</label> <input id="prop-phrase" type="text" oninput="applyProperties()" style="width:100%; padding:4px;"></div>
        <div id="prop-filename-div"><label>Filename:</label> <input id="prop-filename" type="text" oninput="applyProperties()" style="width:100%; padding:4px;"></div>
        <div id="prop-text-div" style="grid-column: span 2;"><label>Text Content:</label> <input id="prop-text" type="text" oninput="applyProperties()" style="width:100%; padding:4px;"></div>
        <div id="prop-desc-div" style="grid-column: span 2;"><label>AI Image Description:</label> <input id="prop-desc" type="text" oninput="applyProperties()" style="width:100%; padding:4px;"></div>
    </div>
</div>
"""

canvas_html = '''
<div style="width: 960px; height: 540px; margin: auto; border: 2px solid #ccc; position: relative; background: #fff;">
    <div style="position: absolute; top:10px; right:10px; z-index:1000; display:flex; gap:5px;">
        <button onclick="window.addNewElement('image')" style="padding:6px; cursor:pointer; background:#e0f7fa; border:1px solid #999; border-radius:4px;">+ Image</button>
        <button onclick="window.addNewElement('text_highlighted')" style="padding:6px; cursor:pointer; background:#fff9c4; border:1px solid #999; border-radius:4px;">+ Text</button>
        <button onclick="window.addNewElement('arrow')" style="padding:6px; cursor:pointer; background:#ffcdd2; border:1px solid #999; border-radius:4px;">+ Arrow</button>
        <button onclick="window.moveLayer('up')" style="padding:6px; cursor:pointer; background:#f0f0f0; border:1px solid #999; border-radius:4px;">▲ Front</button>
        <button onclick="window.moveLayer('down')" style="padding:6px; cursor:pointer; background:#f0f0f0; border:1px solid #999; border-radius:4px;">▼ Back</button>
        <button onclick="window.deleteSelected()" style="padding:6px; cursor:pointer; background:#ffebee; border:1px solid #f44336; border-radius:4px; color:red;">🗑️ Delete</button>
    </div>
    <canvas id="main-canvas" width="960" height="540"></canvas>
</div>
'''

with gr.Blocks(theme=gr.themes.Monochrome(), head=f"<script>{custom_js}</script>") as app:
    gr.Markdown("# 🎬 Minimal AI Video Compositor")
    
    with gr.Group():
        gr.Markdown("### 1️⃣ Director Script Generation Pipeline")
        with gr.Row():
            in_prompt = gr.Textbox(label="Scene Prompt", placeholder="e.g. You can't focus on work emails...", scale=3)
            in_scene = gr.Number(label="Scene Number", value=1, scale=1)
            in_layout = gr.Dropdown(label="Layout Pattern", choices=["1", "2", "3", "4"], value="1", scale=1)
            gen_script_btn = gr.Button("🚀 Generate & Load Director Script", variant="primary")
            
    gr.HTML("<hr style='margin: 20px 0;'>")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📂 Media Overrides & Fallbacks")
            audio = gr.File(label="Background Audio (.mp3)", type="filepath")
            transcript = gr.File(label="AssemblyAI Transcript", type="filepath")
            timings = gr.File(label="Timings Override", type="filepath")
            director = gr.File(label="Manual Director Script Upload", type="filepath")
            images = gr.File(label="Manual Images Overrides", file_count="multiple", type="filepath")
            load_manual_btn = gr.Button("🔄 Force Load from Files", variant="secondary")
            status = gr.Markdown("*Status: Idle*")
            
            with gr.Group():
                gr.Markdown("### 🎨 AI Image Generation Pipeline")
                gen_prompts_btn = gr.Button("📝 1. Generate Image Prompts (Uses Live Edits)", variant="primary")
                ai_gen_btn = gr.Button("✨ 2. Generate Missing Assets (ComfyUI)", variant="secondary")
                gallery_view = gr.HTML("<div style='color:gray; font-style:italic;'>Thumbnails will appear here...</div>")
                with gr.Row():
                    target_regen = gr.Dropdown(label="Regenerate Specific Asset", choices=[], interactive=True)
                    regen_btn = gr.Button("🔄 Reroll", variant="secondary")
                scene_id_store = gr.State("")

        with gr.Column(scale=2):
            gr.Markdown("### 🖌️ Real-Time Layout Editor")
            gr.HTML(canvas_html)
            gr.HTML(editor_html)
            init_state = gr.Textbox(visible=False)
            with gr.Accordion("Developer Data (Live Sync)", open=False):
                with gr.Row():
                    live_dir_state = gr.Textbox(label="Live Director Script", lines=10, elem_id="live-dir-box", interactive=True)
                    live_time_state = gr.Textbox(label="Live Timings Script", lines=10, elem_id="live-time-box", interactive=True)
            with gr.Row():
                save_dir_btn = gr.Button("💾 Save Current Script to Disk", variant="secondary")
                save_dir_file = gr.File(label="Saved File", visible=False)
            with gr.Row():
                quality = gr.Radio(["1080p (Normal)", "4K (Ultra HD)"], value="1080p (Normal)", label="Resolution", interactive=True)
                hw = gr.Radio(["CPU (Standard)", "NVIDIA GPU (Fast)", "Mac (M1/M2/M3)"], value="CPU (Standard)", label="Hardware Accel", interactive=True)
            render_btn = gr.Button("🔥 Render Final Video", variant="primary", size="lg")
            output_vid = gr.Video(label="Final Output")

    gen_script_btn.click(
        fn=generate_pipeline_director_script,
        inputs=[in_prompt, in_scene, in_layout],
        outputs=[init_state, status, audio, transcript, timings, gallery_view, target_regen, scene_id_store, director]
    )
    
    gen_prompts_btn.click(
        fn=generate_pipeline_image_prompts,
        inputs=[scene_id_store, live_dir_state, in_scene],
        outputs=[target_regen, gallery_view, status, scene_id_store]
    )

    load_manual_btn.click(
        fn=handle_manual_load, 
        inputs=[director, images, audio, transcript, timings, in_scene], 
        outputs=[init_state, status, audio, transcript, timings, gallery_view, target_regen, scene_id_store, director]
    )
    
    init_state.change(fn=None, inputs=[init_state], outputs=None, js="(val) => { initInstanceCanvas(val); }")
    save_dir_btn.click(fn=save_modified_director_script, inputs=[live_dir_state], outputs=[save_dir_file])
    render_btn.click(
        fn=render_final_video, 
        inputs=[audio, transcript, timings, live_dir_state, live_time_state, images, quality, hw], 
        outputs=output_vid
    )
    
    ai_gen_btn.click(
        fn=run_ai_image_generation, 
        inputs=[live_dir_state, live_time_state, images, in_scene], 
        outputs=[status, gallery_view, target_regen, init_state]
    )
    
    regen_btn.click(
        fn=regenerate_selected_asset, 
        inputs=[scene_id_store, target_regen, live_dir_state, live_time_state, images, in_scene], 
        outputs=[status, gallery_view, init_state]
    )

if __name__ == "__main__":
    app.launch()