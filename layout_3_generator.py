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


def get_scattered_bounds(num_groups):
    """
    Dynamically returns bounding boxes spread across the ENTIRE canvas.
    Adds a slight random 'jitter' so the grid doesn't look too robotic.
    """
    bounds = []
    
    def add_bound(cx, cy, w, h):
        # Add random jitter to coordinates for a more organic, scattered look
        jitter_x = random.randint(-50, 50)
        jitter_y = random.randint(-50, 50)
        bounds.append({"cx": cx + jitter_x, "cy": cy + jitter_y, "w": w, "h": h})
        
    # Full Canvas Dimensions (1920x1080)
    if num_groups == 1:
        add_bound(960, 540, 1600, 900)
        
    elif num_groups == 2:
        add_bound(560, 540, 800, 800)
        add_bound(1360, 540, 800, 800)
        
    elif num_groups == 3:
        # 2 Top, 1 Bottom (or vice versa via random shuffle)
        add_bound(560, 340, 800, 500)
        add_bound(1360, 340, 800, 500)
        add_bound(960, 780, 800, 500)
        
    elif num_groups == 4:
        # 4 Corners taking up all space
        add_bound(560, 320, 800, 450)
        add_bound(1360, 320, 800, 450)
        add_bound(460, 780, 700, 450)
        add_bound(1460, 780, 700, 450)
        
    elif num_groups == 5:
        # 5-Dice Pattern (4 corners + center)
        add_bound(460, 280, 600, 400)
        add_bound(1460, 280, 600, 400)
        add_bound(960, 540, 600, 400) # Dead Center
        add_bound(460, 800, 600, 400)
        add_bound(1460, 800, 600, 400)
        
    elif num_groups == 6:
        # 2 Rows of 3
        add_bound(360, 320, 550, 450)
        add_bound(960, 320, 550, 450)
        add_bound(1560, 320, 550, 450)
        add_bound(360, 780, 550, 450)
        add_bound(960, 780, 550, 450)
        add_bound(1560, 780, 550, 450)
        
    elif num_groups == 7:
        # 3 Top, 1 Center, 3 Bottom
        add_bound(360, 280, 550, 400)
        add_bound(960, 280, 550, 400)
        add_bound(1560, 280, 550, 400)
        add_bound(960, 540, 550, 400) # Center offset
        add_bound(360, 800, 550, 400)
        add_bound(960, 800, 550, 400)
        add_bound(1560, 800, 550, 400)
        
    else: 
        # 8 Groups: 3 Top, 2 Mid-edges, 3 Bottom
        add_bound(360, 250, 550, 350)
        add_bound(960, 250, 550, 350)
        add_bound(1560, 250, 550, 350)
        add_bound(460, 540, 600, 300) # Mid Left
        add_bound(1460, 540, 600, 300) # Mid Right
        add_bound(360, 830, 550, 350)
        add_bound(960, 830, 550, 350)
        add_bound(1560, 830, 550, 350)
        
    # Shuffle the geometric bounds so groups are assigned randomly to different locations on the screen!
    random.shuffle(bounds)
    return bounds


# --- PHYSICS COLLISION HELPERS ---
def check_overlap(el1, el2, base_size, gap=40):
    w1, h1 = base_size * el1['scale'] + gap, base_size * el1['scale'] + gap
    w2, h2 = base_size * el2['scale'] + gap, base_size * el2['scale'] + gap
    
    l1, r1 = el1['x'] - w1/2, el1['x'] + w1/2
    t1, b1 = el1['y'] - h1/2, el1['y'] + h1/2
    
    l2, r2 = el2['x'] - w2/2, el2['x'] + w2/2
    t2, b2 = el2['y'] - h2/2, el2['y'] + h2/2
    
    return not (r1 <= l2 or l1 >= r2 or b1 <= t2 or t1 >= b2)

def resolve_overlap(el1, el2, base_size, gap=40):
    w1, h1 = base_size * el1['scale'] + gap, base_size * el1['scale'] + gap
    w2, h2 = base_size * el2['scale'] + gap, base_size * el2['scale'] + gap
    
    l1, r1 = el1['x'] - w1/2, el1['x'] + w1/2
    t1, b1 = el1['y'] - h1/2, el1['y'] + h1/2
    
    l2, r2 = el2['x'] - w2/2, el2['x'] + w2/2
    t2, b2 = el2['y'] - h2/2, el2['y'] + h2/2
    
    overlap_x = min(r1 - l2, r2 - l1)
    overlap_y = min(b1 - t2, b2 - t1)
    
    # Anti-locking jitter (in case they share the exact same coordinate)
    if el1['x'] == el2['x']: el1['x'] += random.uniform(-2, 2)
    if el1['y'] == el2['y']: el1['y'] += random.uniform(-2, 2)
    
    # Push apart on the axis with the smallest overlap
    if overlap_x < overlap_y:
        push = (overlap_x / 2) + 1
        if el1['x'] < el2['x']:
            el1['x'] -= push
            el2['x'] += push
        else:
            el1['x'] += push
            el2['x'] -= push
    else:
        push = (overlap_y / 2) + 1
        if el1['y'] < el2['y']:
            el1['y'] -= push
            el2['y'] += push
        else:
            el1['y'] += push
            el2['y'] -= push

def constrain_to_canvas(el, base_size, canvas_w=1920, canvas_h=1080, margin=40):
    w = base_size * el['scale']
    h = base_size * el['scale']
    
    if el['x'] - w/2 < margin:
        el['x'] = w/2 + margin
    elif el['x'] + w/2 > canvas_w - margin:
        el['x'] = canvas_w - w/2 - margin
        
    if el['y'] - h/2 < margin:
        el['y'] = h/2 + margin
    elif el['y'] + h/2 > canvas_h - margin:
        el['y'] = canvas_h - h/2 - margin


def main():
    scene_num = sys.argv[1] if len(sys.argv) > 1 else "1"
    scene_id = f"scene_{scene_num}"
    # Seed random deterministically so layout is stable across reruns
    random.seed(int(scene_num) * 31337 if str(scene_num).isdigit() else hash(scene_num))

    # 1. Setup Input/Output Paths
    # Note: Layout 3 only requires Step 2 output since there's no central text
    step_2_path = f"assets/tmp/{scene_id}_layout_3_step_2_tmp.json"
    output_dir = "assets/directorscript"
    output_path = os.path.join(output_dir, f"{scene_id}_director.json")
    
    os.makedirs(output_dir, exist_ok=True)

    # 2. Load the AI output data
    try:
        with open(step_2_path, "r") as f:
            step_2_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {step_2_path} not found. Please run Step 2 first.")
        return 1

    # ── Load scene text for verbatim phrase allocation ────────────────────────
    try:
        with open(f"assets/scene_prompts/{scene_id}_prompt.json", encoding="utf-8") as f:
            _prompt_data = json.load(f)
        _scene_text = _strip_scene_prefix(_prompt_data.get("prompt", ""))
    except FileNotFoundError:
        _scene_text = ""
    _tokens = _scene_text.split()

    _all_images = step_2_data.get("grouped_elements", [])
    _n_images = len(_all_images)
    n_tokens = len(_tokens)
    n_active = min(_n_images, max(1, n_tokens // 2))
    print(f"   Token budget: {n_tokens} tokens -> {n_active}/{_n_images} active slots")
    _phrases = allot_phrases(_tokens, n_active)
    # Pad with None so indices beyond n_active are skipped
    _phrases += [None] * (_n_images - n_active)

    # 3. Initialize the final Director Script Structure
    director_script = {
        "scene_id": scene_id,
        "elements": []
    }

    # --- CANVAS MATH CONSTANTS ---
    BASE_IMG_SIZE = 1000       
    MAX_ITEMS_PER_ROW = 2      
    MAX_SCALE_LIMIT = 0.45     # Images can be massive in Layout 3 since there is no central text!
    MIN_PAD_RATIO = 0.30       # Maintain the comfortable 30% gap

    # 4. Process and Layout the Images dynamically
    images = step_2_data.get("grouped_elements", [])
    
    # Bundle images by their dynamic group_id
    group_dict = {}
    for img in images:
        gid = img.get("group_id", "group_1")
        if gid not in group_dict:
            group_dict[gid] = []
        group_dict[gid].append(img)
        
    group_ids = sorted(group_dict.keys())
    num_groups = len(group_ids)
    
    if num_groups > 0:
        # Get the scattered bounding boxes
        bounds_list = get_scattered_bounds(num_groups)
        
        img_counter = 0
        
        for i, gid in enumerate(group_ids):
            group_images = group_dict[gid]
            if not group_images:
                continue
                
            # Assign the geometric bounds to this group
            bounds_idx = min(i, len(bounds_list) - 1)
            bounds = bounds_list[bounds_idx]
            
            # Chunk the images in this group into rows 
            rows = []
            for j in range(0, len(group_images), MAX_ITEMS_PER_ROW):
                rows.append(group_images[j:j + MAX_ITEMS_PER_ROW])
                
            num_rows = len(rows)
            max_items_in_row = max(len(row) for row in rows)
            
            # --- PROPORTIONAL COLLISION PROOF MATH ---
            eff_rows = num_rows + (num_rows - 1) * MIN_PAD_RATIO
            eff_cols = max_items_in_row + (max_items_in_row - 1) * MIN_PAD_RATIO
            
            scale_h = bounds["h"] / (eff_rows * BASE_IMG_SIZE) if eff_rows > 0 else MAX_SCALE_LIMIT
            scale_w = bounds["w"] / (eff_cols * BASE_IMG_SIZE) if eff_cols > 0 else MAX_SCALE_LIMIT
            
            optimal_scale = min(scale_h, scale_w, MAX_SCALE_LIMIT)
            optimal_scale = max(optimal_scale, 0.05)
            
            item_size = BASE_IMG_SIZE * optimal_scale
            
            # --- DYNAMIC SPACING WITHIN THE ZONE ---
            if num_rows == 1:
                row_y_centers = [bounds["cy"]]
            else:
                total_item_h = num_rows * item_size
                available_pad_y = (bounds["h"] - total_item_h) / (num_rows - 1)
                
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
                    
                    pad_x = min(available_pad_x, item_size * 1.2)
                    pad_x = max(pad_x, item_size * MIN_PAD_RATIO)
                    
                    row_w = total_item_w + (items_in_row - 1) * pad_x
                    start_x = bounds["cx"] - (row_w / 2) + (item_size / 2)
                    item_x_centers = [start_x + k * (item_size + pad_x) for k in range(items_in_row)]
                
                # Write final coordinates for the images
                for j, img in enumerate(row):
                    current_x = item_x_centers[j]
                    _img_allot_phrase = _phrases[img_counter] if img_counter < len(_phrases) else None
                    if _img_allot_phrase is None:
                        img_counter += 1
                        continue
                    director_script["elements"].append({
                        "element_id": img.get("element_id", f"image_{gid}_{img_counter}"),
                        "type": "image",
                        "phrase": _img_allot_phrase,
                        "filename": f"{gid}_image_{img_counter}.jpg", 
                        "description": img.get("visual_description", ""),
                        "x": current_x, # Temporarily float for physics math
                        "y": current_y,
                        "scale": optimal_scale,
                        "angle": random.randint(-4, 4), 
                        "animation": "pop",
                        "property": "shadow",
                        "reason": img.get("reason", ""),
                        "text_content": ""
                    })
                    img_counter += 1

    # --- PHYSICS / COLLISION RESOLVER ALGORITHM ---
    MAX_RELAX_ITERATIONS = 50
    MAX_SHRINK_PASSES = 10
    GAP_BETWEEN_IMAGES = 40
    
    for shrink_pass in range(MAX_SHRINK_PASSES):
        any_overlap_at_end = False
        
        # Iteratively try to push images apart
        for relax_iter in range(MAX_RELAX_ITERATIONS):
            overlapped_this_iter = False
            
            # Check every image against every other image
            for i in range(len(director_script["elements"])):
                for j in range(i + 1, len(director_script["elements"])):
                    el1 = director_script["elements"][i]
                    el2 = director_script["elements"][j]
                    
                    if check_overlap(el1, el2, BASE_IMG_SIZE, gap=GAP_BETWEEN_IMAGES):
                        resolve_overlap(el1, el2, BASE_IMG_SIZE, gap=GAP_BETWEEN_IMAGES)
                        overlapped_this_iter = True
            
            # Keep them inside the 1920x1080 canvas
            for el in director_script["elements"]:
                constrain_to_canvas(el, BASE_IMG_SIZE, margin=40)
                
            # If nothing touched this iteration, the layout is perfect!
            if not overlapped_this_iter:
                break
        else:
            # If the loop finished without breaking, they are stuck in a corner and physically can't fit
            any_overlap_at_end = True
            
        if any_overlap_at_end:
            # Drop the scale of all images by 5% and run the physics simulation again
            for el in director_script["elements"]:
                el['scale'] = max(0.05, el['scale'] * 0.95)
        else:
            # Escaped with no overlaps!
            break
            
    # Round off coordinates for final output
    for el in director_script["elements"]:
        el['x'] = int(el['x'])
        el['y'] = int(el['y'])
        el['scale'] = round(el['scale'], 3)

    # 5. Save the Final Output
    with open(output_path, "w") as f:
        json.dump(director_script, f, indent=2)
        
    print(f"Director Script successfully generated: {output_path}")

if __name__ == "__main__":
    import sys; sys.exit(main() or 0)