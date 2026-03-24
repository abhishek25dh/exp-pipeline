import json
import os
import random
import re
import sys

def _strip_scene_prefix(text):
    return re.sub(r"^\s*scene_\d+[:\-]\s*", "", text or "", flags=re.I).strip()


def allot_phrases(tokens, n_slots):
    """Split tokens proportionally into n_slots phrases.
    Returns list[str|None] — None means element gets no phrase and must be skipped."""
    n = len(tokens)
    if n == 0:
        return [None] * n_slots
    results = []
    t = 0
    for i in range(n_slots):
        remaining_tokens = n - t
        remaining_slots  = n_slots - i
        if remaining_tokens <= 0:
            results.append(None)
        else:
            give = max(1, remaining_tokens // remaining_slots)
            if i == n_slots - 1:
                give = remaining_tokens
            results.append(" ".join(tokens[t: t + give]))
            t += give
    return results


def get_group_bounds(num_groups, scene_seed=0):
    """
    Dynamically returns bounding boxes for the groups based on how many exist.
    bounds structure: {"cx": center_x, "cy": center_y, "w": max_width, "h": max_height}
    """
    bounds = []
    
    # Pre-calculated Y-axis layers to avoid vertical overlap (expanded for larger images)
    TOP_Y = 240
    BOT_Y = 840
    MID_Y = 540
    
    # Safe heights (Increased to allow 2 rows of larger scaled images)
    ROW_H = 460
    MID_H = 360 # Slightly shorter so it doesn't overlap top/bottom rows
    
    if num_groups == 1:
        bounds.append({"cx": 960, "cy": TOP_Y, "w": 1000, "h": ROW_H})
        
    elif num_groups == 2:
        bounds.append({"cx": 960, "cy": TOP_Y, "w": 1000, "h": ROW_H})
        bounds.append({"cx": 960, "cy": BOT_Y, "w": 1000, "h": ROW_H})
        
    elif num_groups == 3:
        # Triangular random (2 up 1 down, or 1 up 2 down)
        if random.choice([True, False]):
            bounds.append({"cx": 560, "cy": TOP_Y, "w": 600, "h": ROW_H})
            bounds.append({"cx": 1360, "cy": TOP_Y, "w": 600, "h": ROW_H})
            bounds.append({"cx": 960, "cy": BOT_Y, "w": 1000, "h": ROW_H})
        else:
            bounds.append({"cx": 960, "cy": TOP_Y, "w": 1000, "h": ROW_H})
            bounds.append({"cx": 560, "cy": BOT_Y, "w": 600, "h": ROW_H})
            bounds.append({"cx": 1360, "cy": BOT_Y, "w": 600, "h": ROW_H})
            
    elif num_groups == 4:
        # Square (4 corners)
        bounds.append({"cx": 560, "cy": TOP_Y, "w": 600, "h": ROW_H})
        bounds.append({"cx": 1360, "cy": TOP_Y, "w": 600, "h": ROW_H})
        bounds.append({"cx": 560, "cy": BOT_Y, "w": 600, "h": ROW_H})
        bounds.append({"cx": 1360, "cy": BOT_Y, "w": 600, "h": ROW_H})
        
    elif num_groups == 5:
        # 2 up, 2 down, 1 random side
        bounds.append({"cx": 660, "cy": TOP_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 1260, "cy": TOP_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 660, "cy": BOT_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 1260, "cy": BOT_Y, "w": 500, "h": ROW_H})
        if random.choice([True, False]):
            bounds.append({"cx": 250, "cy": MID_Y, "w": 400, "h": MID_H}) # Left
        else:
            bounds.append({"cx": 1670, "cy": MID_Y, "w": 400, "h": MID_H}) # Right
            
    elif num_groups == 6:
        # 2 up, 2 down, 1 left, 1 right
        bounds.append({"cx": 660, "cy": TOP_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 1260, "cy": TOP_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 660, "cy": BOT_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 1260, "cy": BOT_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 250, "cy": MID_Y, "w": 400, "h": MID_H})
        bounds.append({"cx": 1670, "cy": MID_Y, "w": 400, "h": MID_H})
        
    elif num_groups == 7:
        # 3 up, 2 down, 1 left, 1 right
        bounds.append({"cx": 320, "cy": TOP_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 960, "cy": TOP_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 1600, "cy": TOP_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 660, "cy": BOT_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 1260, "cy": BOT_Y, "w": 500, "h": ROW_H})
        bounds.append({"cx": 250, "cy": MID_Y, "w": 400, "h": MID_H})
        bounds.append({"cx": 1670, "cy": MID_Y, "w": 400, "h": MID_H})
        
    else: 
        # 8 groups (Maximum robust fit): 3 up, 3 down, 1 left, 1 right
        bounds.append({"cx": 320, "cy": TOP_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 960, "cy": TOP_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 1600, "cy": TOP_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 320, "cy": BOT_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 960, "cy": BOT_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 1600, "cy": BOT_Y, "w": 550, "h": ROW_H})
        bounds.append({"cx": 250, "cy": MID_Y, "w": 400, "h": MID_H})
        bounds.append({"cx": 1670, "cy": MID_Y, "w": 400, "h": MID_H})
        
    return bounds


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"
    # Seed random deterministically so layout is stable across reruns
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))
    
    # 1. Setup Input/Output Paths
    step_1_path = f"assets/tmp/{scene_id}_layout_2_step_1_tmp.json"
    step_3_path = f"assets/tmp/{scene_id}_layout_2_step_3_tmp.json"
    output_dir = "assets/directorscript"
    output_path = os.path.join(output_dir, f"{scene_id}_director.json")
    
    os.makedirs(output_dir, exist_ok=True)

    # 2. Load the AI output data (Use default empty dicts if files don't exist yet for testing)
    try:
        with open(step_1_path, "r") as f:
            step_1_data = json.load(f)
    except FileNotFoundError:
        step_1_data = {"main_texts": []}

    try:
        with open(step_3_path, "r") as f:
            step_3_data = json.load(f)
    except FileNotFoundError:
        step_3_data = {"grouped_elements": []}

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{scene_id}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()

    _main_texts = step_1_data.get("main_texts", [])
    _all_images = step_3_data.get("grouped_elements", [])
    _n_texts = len(_main_texts)
    _n_images = len(_all_images)

    # Allot tokens: P1..n_texts = text triggers, remaining = images
    _phrases = allot_phrases(_tokens, _n_texts + _n_images)
    _text_phrases = _phrases[:_n_texts]
    _image_phrases = _phrases[_n_texts:]

    # 3. Initialize the final Director Script Structure
    director_script = {
        "scene_id": scene_id,
        "elements": []
    }

    # --- CANVAS MATH CONSTANTS (1920x1080 Base) ---
    W = 1920
    CENTER_X = 960
    CENTER_Y = 540
    CHAR_PX = 30
    MARGIN  = 60
    
    BASE_IMG_SIZE = 1000       
    MAX_ITEMS_PER_ROW = 2      # Keeps blocks chunky instead of long horizontal lines
    MAX_SCALE_LIMIT = 0.35     # Increased significantly to allow big punchy images!
    
    # PROPORTIONAL SPACING RULE:
    # 30% of the image's own size MUST be empty space. 
    # If the box is too tight to allow this, it shrinks the image scale!
    MIN_PAD_RATIO = 0.30       

    # 4. Add the Main Central Text (From Step 1)
    for _ti, txt in enumerate(step_1_data.get("main_texts", [])):
        _txt_phrase = _text_phrases[_ti] if _ti < len(_text_phrases) else None
        if _txt_phrase is None:
            continue
        # text_content = allot phrase (what's being said at this timing position)
        _tc = _txt_phrase
        _chars = max(1, len(_tc))
        _n_words = max(1, len(_tc.split()))
        _avail = min(CENTER_X - MARGIN, W - CENTER_X - MARGIN)
        _canvas_safe = (2 * max(10, _avail)) / (_chars * CHAR_PX)
        _preferred = min(3.5, 14.0 / _n_words)
        _text_scale = round(max(1.0, min(_preferred, _canvas_safe)), 3)
        director_script["elements"].append({
            "element_id": txt.get("element_id", "text_main"),
            "type": txt.get("type", "text_red"),
            "phrase": _txt_phrase,   # verbatim from scene text
            "text_content": _tc,     # uppercase for display
            "x": CENTER_X,
            "y": CENTER_Y,
            "scale": _text_scale,
            "angle": 0,
            "animation": "pop", 
            "property": "",
            "reason": txt.get("reason", ""),
            "typing_speed": 0.5,
            "filename": "",
            "description": ""
        })

    # 5. Process and Layout the Images dynamically (From Step 3 directly)
    images = step_3_data.get("grouped_elements", [])
    
    # Bundle images by their dynamic group_id
    group_dict = {}
    for img in images:
        gid = img.get("group_id", "group_1")
        if gid not in group_dict:
            group_dict[gid] = []
        group_dict[gid].append(img)
        
    # Figure out how many unique groups we have
    group_ids = sorted(group_dict.keys())
    num_groups = len(group_ids)
    
    if num_groups > 0:
        # Get the geometric bounding boxes for this specific layout size
        bounds_list = get_group_bounds(num_groups)
        
        img_counter = 0
        
        for i, gid in enumerate(group_ids):
            group_images = group_dict[gid]
            if not group_images:
                continue
                
            # Assign the geometric bounds to this group
            bounds_idx = min(i, len(bounds_list) - 1) # Failsafe just in case
            bounds = bounds_list[bounds_idx]
            
            # Chunk the images in this group into rows 
            rows = []
            for j in range(0, len(group_images), MAX_ITEMS_PER_ROW):
                rows.append(group_images[j:j + MAX_ITEMS_PER_ROW])
                
            num_rows = len(rows)
            max_items_in_row = max(len(row) for row in rows)
            
            # --- PROPORTIONAL COLLISION PROOF MATH ---
            # Calculates how many 'virtual' images fit into the box when including the mandatory 30% padding gaps
            eff_rows = num_rows + (num_rows - 1) * MIN_PAD_RATIO
            eff_cols = max_items_in_row + (max_items_in_row - 1) * MIN_PAD_RATIO
            
            scale_h = bounds["h"] / (eff_rows * BASE_IMG_SIZE) if eff_rows > 0 else MAX_SCALE_LIMIT
            scale_w = bounds["w"] / (eff_cols * BASE_IMG_SIZE) if eff_cols > 0 else MAX_SCALE_LIMIT
            
            # Shrink scale if necessary to maintain the gap, otherwise use MAX_SCALE_LIMIT
            optimal_scale = min(scale_h, scale_w, MAX_SCALE_LIMIT)
            optimal_scale = max(optimal_scale, 0.05)
            
            item_size = BASE_IMG_SIZE * optimal_scale
            
            # --- DYNAMIC SPACING WITHIN THE ZONE ---
            if num_rows == 1:
                row_y_centers = [bounds["cy"]]
            else:
                total_item_h = num_rows * item_size
                available_pad_y = (bounds["h"] - total_item_h) / (num_rows - 1)
                
                # Push them apart as much as possible, up to 1.2x their size, but NEVER less than MIN_PAD_RATIO
                pad_y = min(available_pad_y, item_size * 1.2) 
                pad_y = max(pad_y, item_size * MIN_PAD_RATIO)
                
                total_grid_height = total_item_h + (num_rows - 1) * pad_y
                start_y = bounds["cy"] - (total_grid_height / 2) + (item_size / 2)
                row_y_centers = [start_y + k * (item_size + pad_y) for k in range(num_rows)]
            
            for r_idx, row in enumerate(rows):
                current_y = row_y_centers[r_idx]
                items_in_row = len(row)
                
                if items_in_row == 1:
                    item_x_centers = [bounds["cx"]]
                else:
                    total_item_w = items_in_row * item_size
                    available_pad_x = (bounds["w"] - total_item_w) / (items_in_row - 1)
                    
                    # Push them apart as much as possible, up to 1.2x their size, but NEVER less than MIN_PAD_RATIO
                    pad_x = min(available_pad_x, item_size * 1.2)
                    pad_x = max(pad_x, item_size * MIN_PAD_RATIO)
                    
                    row_w = total_item_w + (items_in_row - 1) * pad_x
                    start_x = bounds["cx"] - (row_w / 2) + (item_size / 2)
                    item_x_centers = [start_x + k * (item_size + pad_x) for k in range(items_in_row)]
                
                # Write final coordinates for the images
                for j, img in enumerate(row):
                    current_x = item_x_centers[j]
                    _img_allot_phrase = _image_phrases[img_counter] if img_counter < len(_image_phrases) else None
                    if _img_allot_phrase is None:
                        img_counter += 1
                        continue
                    director_script["elements"].append({
                        "element_id": img.get("element_id", f"image_{gid}_{img_counter}"),
                        "type": "image",
                        "phrase": _img_allot_phrase,
                        "filename": f"{gid}_image_{img_counter}.jpg", 
                        "description": img.get("visual_description", ""),
                        "x": int(current_x),
                        "y": int(current_y),
                        "scale": round(optimal_scale, 2),
                        "angle": 0,    
                        "animation": "pop",
                        "property": "shadow",
                        "reason": img.get("reason", ""),
                        "text_content": ""
                    })
                    img_counter += 1

    # 6. Save the Final Output
    with open(output_path, "w") as f:
        json.dump(director_script, f, indent=2)
        
    print(f"Director Script successfully generated: {output_path}")

if __name__ == "__main__":
    import sys; sys.exit(main() or 0)