# Layout Pipeline Architecture: A Guide for Future AIs

## 1. The Core Purpose
This project is an **automated explainer video layout generator**. 
The goal is to take a raw narrative scene script (e.g. "A child riding a bike at sunset") and physically manifest it on a 1920x1080 canvas using a combination of images, text, animations, and coordinates.

### The Big AI Problem We Solved
Originally, there was an urge to let the LLM (Large Language Model) decide *where* things should go (X, Y coordinates). **This is a mistake that must always be avoided.**
LLMs have zero spatial awareness. When an LLM picks X/Y coordinates, elements will overlap, drift off-screen, or clump together randomly. 

### The Solution: The 3-Step Decoupled Pipeline
To fix the hallucinated placement issue, we completely decoupled "Creative Intelligence" from "Spatial Intelligence." Every layout follows a strict 3-step pipeline:

#### Step 1: Semantic Parsing (AI / OpenRouter)
A python script (`layout_X_step_1.py`) sends the scene prompt to an LLM. The LLM's only job is to act as a *Narrative Structurer*. 
It reads the scene and extracts an array of logical items depending on the layout (e.g., 4 chronological timeline steps, or 1 core concept and 5 orbiting details). It returns this semantic structure as JSON. No visual descriptions or coordinates are generated here.

#### Step 2: Visual Detailing (AI / OpenRouter)
A second python script (`layout_X_step_2.py`) takes the Step 1 structure and sends it back to the LLM. Now the LLM acts as a *Visual Director*.
For every narrative node extracted in Step 1, it writes a highly detailed Midjourney-style image prompt and figures out text highlight colors. It returns this detailed JSON payload.

#### Step 3: Deterministic Generation (Python Math)
A final generator script (`layout_X_generator.py`) takes the Step 2 data. **This script does not use AI.**
It uses hardcoded Trigonometry, Grids, and absolute math to place the AI's content onto the 1920x1080 canvas. The math guarantees zero overlap because it calculates the absolute bounding boxes of the images (based on scale) and the text.

---

## 2. The Layout Catalog

Each layout has its own 3-step pipeline.

*   **Layout 1 (Four Corners):** Places an image in the absolute center. Places 4 text phrases in the four extreme corners of the screen pointing towards the center.
*   **Layout 2 (Diagonal Split):** Screen is mathematically sliced diagonally. Top-Left zone gets an image and text; Bottom-Right zone gets an image and text.
*   **Layout 3 (Horizontal Banners):** Two ultra-wide "banner" text phrases span the screen (top/bottom), sandwiching an image in the dead center.
*   **Layout 4 (Z-Pattern):** Reads like a book (Top-Left -> Top-Right -> Bottom-Left -> Bottom-Right). The user's eye follows Zig-Zag animations.
*   **Layout 6 (Two Rows / Top-Bottom Split):** Screen divided horizontally. Group 1 is on top (Image on Left, Texts on Right). Group 2 is on bottom (Image on Right, Texts on Left).
*   **Layout 7 (Host Center + Sides):** A narrator/host graphic is dead center. 2-3 images stack vertically on the left side, 2-3 images stack vertically on the right side.
*   **Layout 8 (Timeline Path):** Extracts 3-4 chronological steps. Plots them mathematically across the X-axis from left-to-right, connecting them with generated Arrow graphics pointing to the next node.
*   **Layout 9 (Comic Grid):** Screen sliced into 4 perfect quadrants. An image sits in the center of each quadrant with a keyword text phrase sitting perfectly beneath it.
*   **Layout 10 (Macro & Micro / Zoom Out):** Extracts the "Big Picture" concept (Macro) placing it massive at 80% opacity on the left. Extracts 3 "Small Detail" concepts (Micro) and stacks them small on the right.
*   **Layout 11 (Mind-Map Orbit):** Extracts one giant core concept word dead center. Calculates an elliptical orbit around the text where 4-5 detail nodes (images + labels) orbit the center perfectly.

---

## 3. Critical Pitfalls & Mistakes We Fixed (DO NOT REPEAT)

If you are modifying this codebase, learn from these specific bugs we encountered and fixed:

### Pitfall A: Text and Image Overlap (The Coordinate Sizing Trap)
**The Bug:** In Layout 9 and 11, the text labels were overlapping either the images or the central node.
**The Fix:** You cannot just place text "+50 pixels" from an image center. You have to account for the physical size of the image based on its scale. 
*Example:* If the base Fabric.js render size is 1024px, and `IMG_SCALE = 0.35`, the image is ~358px tall. That means the bottom edge is `179px` from the center node. You must place the text further than `Y + 179` to clear the image. *We shrunk the Layout 9 image scale to 0.28 to make the math fit on 1080p.*

### Pitfall B: Elliptical vs Circular Orbits
**The Bug:** In Layout 11, a central root text string of "NOSTALGIC CHILDHOOD" is incredibly wide. When we used trigonometric sine/cosine to build a perfect Circle orbit with a radius of 360px, the nodes landing on diagonal angles (like 45 degrees) clipped into the corners of that huge rectangular text.
**The Fix:** We completely scrapped a math-driven ellipse and instead hand-coded an array of **Safe Slots** (Top-Left, Top-Right, Bottom-Left, Bottom-Right, Top-Center) pushed out to the absolute furthest X and Y coordinates (e.g. `X=400, Y=250`). This bypasses geometric bounding limits entirely and forces a perfect safe gap.

### Pitfall C: OpenRouter / LLM JSON Parsing Failures
**The Bug:** When asking the LLM for JSON, the OpenRouter models (like Deepseek) would often return conversational preamble: `"Here is your JSON:\n\n```json\n { ... } \n```"`. The `json.loads` function in Python would instantly crash.
**The Fix:**
1. We injected `"response_format": {"type": "json_object"}` into the API payload.
2. We rewrote `clean_json_response(content)` in every script to use `content.find('{')` and `content.rfind('}')`. This substring extraction mathematically isolates the JSON dictionary regardless of whatever random markdown ticks or preamble the LLM decides to throw above or below it.

---

## 4. How the "Layout Tester" App Works
The file `layout_tester.py` is the visualizer. It boots up a local server (`http://localhost:5555`) running Fabric.js.
Instead of actually reading real generated PNGs, it parses the `assets/directorscript/scene_X_director.json` file. 
It uses Fabric.js to immediately draw gray placeholder boxes representing the exact scaled dimensions of the final images, draws the text objects with their colors (`text_red`, `text_black`), and applies simple CSS hover animations (like `pulse`, `pop`, `slide`). 

By building this web tester, we were able to immediately see if our Python math was resulting in overlaps without waiting for image generators to finish.
