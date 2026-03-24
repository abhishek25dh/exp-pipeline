#!/usr/bin/env python3
"""
MVP: Scene text -> AI generates HTML with real images -> Playwright records -> MP4

Pipeline:
  1. AI (OpenRouter) generates HTML/CSS layout with Pollinations.ai image URLs
  2. Python downloads each image & embeds as base64 (no network needed during recording)
  3. Playwright opens the HTML, records it for SCENE_DURATION ms
  4. FFmpeg converts webm -> mp4

Usage:
    python mvp_html_video.py
    python mvp_html_video.py "Your 2-3 sentence scene text."

API key: set OPENROUTER_API_KEY env var, or put key in 'openrouter_key.txt'
"""

import os
import re
import sys
import time
import base64
import requests
import subprocess
from pathlib import Path
from urllib.parse import quote

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
MODEL          = "openai/gpt-4o-mini"   # swap to claude-3-haiku etc. for better quality
SCENE_DURATION = 7000                   # ms to record
VIEWPORT_W     = 1920
VIEWPORT_H     = 1080
OUTPUT_DIR     = Path("mvp_output")
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are building an explainer video scene in HTML/CSS that looks like an educational whiteboard.
Return ONLY raw HTML (complete <!DOCTYPE html> document). No markdown, no code fences, no explanation.

━━━ VISUAL STYLE — THIS IS CRITICAL ━━━
The output MUST look like this:
- **WHITE background** (#ffffff). Not dark. Not gradient. Pure white.
- **Comic Sans MS** font for all text. font-family: 'Comic Sans MS', cursive;
- Images look like PHOTOS PINNED to a whiteboard — slight rotation, drop shadow
- Clean, fun, educational — like a teacher explaining with pictures

━━━ CANVAS ━━━
body {
  margin:0; padding:0; position:relative;
  width:1920px; height:1080px; overflow:hidden;
  background:#ffffff;
  font-family: 'Comic Sans MS', 'Comic Sans', cursive;
}

━━━ THREE TEXT TYPES — you must use at least 2 different types ━━━

1. text_black — black text, white text-stroke for readability:
   color:#000000; font-weight:bold;
   -webkit-text-stroke: 2px white; paint-order: stroke fill;

2. text_red — crimson red text, white text-stroke:
   color:#DC143C; font-weight:bold;
   -webkit-text-stroke: 2px white; paint-order: stroke fill;

3. text_highlighted — white text on orange background (like a highlighter):
   color:#ffffff; background:#FFA500; padding:8px 18px; display:inline-block;

━━━ IMAGES — MUST HAVE 2-4 IMAGES ━━━
Use LoremFlickr for real photos: https://loremflickr.com/WIDTH/HEIGHT/keyword1,keyword2

Image styling — make them look pinned/collaged on a whiteboard:
  width: 280px; height: 280px;   (square, like polaroids — or 320x240 landscape)
  object-fit: cover;
  box-shadow: 4px 6px 18px rgba(0,0,0,0.35);
  transform: rotate(Xdeg);       (slight rotation: -5deg to 5deg, vary per image)

IMPORTANT: Each image MUST have a different slight rotation angle for collage feel.
Use: -4deg, 3deg, -2deg, 5deg etc.

━━━ LAYOUT PATTERNS — pick one ━━━

[A] CENTER IMAGE + FOUR CORNER TEXTS:
  1 large image center: x:960, y:540, ~350x350, rotation:0
  4 text phrases in extreme corners:
    top-left (120, 80), top-right (1800, 80), bottom-left (120, 1000), bottom-right (1800, 1000)
  Mix text types: 2 text_highlighted, 1 text_red, 1 text_black

[B] 2x2 GRID (Comic Panels):
  4 images in a grid, each ~280x280:
    top-left (480, 250), top-right (1440, 250)
    bottom-left (480, 700), bottom-right (1440, 700)
  Below each image: a short keyword label (text_highlighted or text_red)
  Each image slightly rotated differently

[C] THREE COLUMNS:
  left column (360px center), middle (960px), right (1560px)
  Each column: stack of 1-3 images vertically
  Text labels at top (~y:160) in each column
  Images below (~y:340 to 900), scaled to fit, slight rotation

[D] LEFT IMAGE + RIGHT TEXT STACK:
  1 large image: left side, x:420, y:450, ~400x400, slight rotation
  Right side: 3-4 text phrases stacked vertically
    Starting at x:1200, y:200
    Each separated by ~120px vertical gap
    Mix: first text_highlighted, then text_black, then text_red

[E] CAUSE-EFFECT:
  Left image (cause): x:380, y:480, ~300x300
  Right image (effect): x:1540, y:480, ~300x300
  Arrow between them: a simple CSS arrow (or the text "→" at 120px)
  Labels beneath each image

━━━ TEXT SIZING ━━━
- Main phrases: font-size: 52px to 72px (bold, punchy, 2-5 words)
- Labels beneath images: font-size: 38px to 48px
- All text uses position:absolute with explicit top/left pixel values

━━━ ANIMATIONS — stagger element appearances ━━━
All elements start hidden (opacity:0) and animate in one by one.

animation shorthand: animation: KEYFRAME DURATION ease DELAY both;
"both" = fill-mode both. Always use it. Always set iteration-count to 1 (default).

Stagger order with delays:
  Image 1:  0.3s (pop — instant appear via fadeIn 0.1s)
  Text 1:   0.7s (slideIn from left or right)
  Image 2:  1.2s (pop)
  Text 2:   1.6s (slideIn)
  Image 3:  2.0s (pop)
  Text 3:   2.4s (slideIn)
  Image 4:  2.8s (pop)
  Text 4:   3.2s (slideIn)

Required @keyframes:
  @keyframes pop       { from{opacity:0;transform:scale(0.7)} to{opacity:1;transform:scale(1)} }
  @keyframes fadeIn    { from{opacity:0} to{opacity:1} }
  @keyframes slideLeft { from{opacity:0;transform:translateX(-80px)} to{opacity:1;transform:translateX(0)} }
  @keyframes slideRight{ from{opacity:0;transform:translateX(80px)} to{opacity:1;transform:translateX(0)} }
  @keyframes slideUp   { from{opacity:0;transform:translateY(50px)} to{opacity:1;transform:translateY(0)} }

━━━ CRITICAL: ANIMATION + TRANSFORM BUG ━━━
If an element has BOTH a static transform (like rotate) AND an animation with transform,
they will conflict. Solution: use a WRAPPER div for position + rotation, animate the INNER element.

Example for rotated image that pops in:
  <div style="position:absolute; left:380px; top:250px; transform:rotate(-3deg);">
    <img src="..." style="width:280px; height:280px; object-fit:cover;
         box-shadow:4px 6px 18px rgba(0,0,0,0.35);
         opacity:0; animation: pop 0.3s ease 0.3s both;" />
  </div>

Example for highlighted text that slides in:
  <div style="position:absolute; left:1200px; top:200px;">
    <span style="color:#fff; background:#FFA500; padding:8px 18px;
           font-size:56px; font-weight:bold; display:inline-block;
           opacity:0; animation: slideLeft 0.5s ease 0.7s both;">
      Water Supply
    </span>
  </div>

━━━ CONTENT RULES ━━━
- Extract SHORT phrases from the input (2-5 words each). Do NOT paste full sentences.
- Each image should depict a key visual concept from the text
- Use 2-4 keywords per LoremFlickr URL that visually match the concept
- The scene should feel like a fun educational infographic
"""


def get_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    key_file = Path(__file__).parent / "openrouter_key.txt"
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            print("Using API key from openrouter_key.txt")
            return key
    print("\nERROR: No API key found.")
    print("Create 'openrouter_key.txt' with your OpenRouter key, or set OPENROUTER_API_KEY env var.\n")
    sys.exit(1)


def generate_html(scene_text: str, api_key: str) -> str:
    print(f"[1/4] Generating HTML scene with {MODEL}...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Create an animated explainer video scene for this text:\n\n{scene_text}"}
        ]
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=payload, timeout=60
    )
    if resp.status_code != 200:
        print(f"API error {resp.status_code}: {resp.text[:400]}")
        sys.exit(1)

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if model wraps in them
    if "```" in content:
        # find first ``` and last ```, take content between
        start = content.find("```")
        # skip the language tag line (```html)
        start = content.find("\n", start) + 1
        end = content.rfind("```")
        content = content[start:end].strip()

    return content


def fetch_image_as_base64(url: str) -> str | None:
    """Download a URL and return a base64 data URI, or None on failure."""
    try:
        r = requests.get(url, timeout=25, allow_redirects=True)
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
            ct = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
            return f"data:{ct};base64,{base64.b64encode(r.content).decode()}"
    except Exception:
        pass
    return None


def download_images_as_base64(html: str) -> str:
    """Find image URLs in HTML, download them, replace with base64 data URIs."""
    pattern = r'https://(?:image\.pollinations\.ai|loremflickr\.com|picsum\.photos)/[^\s"\'<>]+'
    urls = list(dict.fromkeys(re.findall(pattern, html)))

    if not urls:
        print("[2/4] No image URLs found in HTML — skipping download.")
        return html

    print(f"[2/4] Downloading {len(urls)} image(s)...")

    SVG_PLACEHOLDER = "data:image/svg+xml;base64," + base64.b64encode(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480">'
        b'<rect width="640" height="480" fill="#1a2a4a"/>'
        b'<text x="320" y="240" font-family="Arial" font-size="24" fill="#ffffff40"'
        b' text-anchor="middle" dominant-baseline="middle">image</text></svg>'
    ).decode()

    for i, url in enumerate(urls, 1):
        print(f"      [{i}/{len(urls)}] {url[:85]}...")
        data_uri = None

        # 1. Try the URL as-is (covers loremflickr, picsum, and working pollinations)
        data_uri = fetch_image_as_base64(url)
        if data_uri:
            print(f"             OK")
        else:
            # 2. LoremFlickr fallback — extract keywords from URL
            print(f"             failed — trying LoremFlickr fallback...")
            kw_raw = re.sub(r'https?://[^/]+/', '', url).split('?')[0]
            keywords = re.sub(r'[^a-zA-Z,]', ',', kw_raw)
            keywords = ','.join(k for k in keywords.split(',') if len(k) > 2)[:60] or "photography"
            w_match = re.search(r'/(\d{3,4})[x/](\d{3,4})', url)
            w, h = (w_match.group(1), w_match.group(2)) if w_match else ("640", "480")
            flickr_url = f"https://loremflickr.com/{w}/{h}/{keywords}"
            data_uri = fetch_image_as_base64(flickr_url)
            if data_uri:
                print(f"             LoremFlickr OK")
            else:
                # 3. Picsum last resort (random beautiful photo, no keywords)
                picsum_url = f"https://picsum.photos/{w}/{h}"
                data_uri = fetch_image_as_base64(picsum_url)
                if data_uri:
                    print(f"             Picsum OK (random photo)")
                else:
                    print(f"             all failed — using dark placeholder")
                    data_uri = SVG_PLACEHOLDER

        html = html.replace(url, data_uri)

    return html


# Keyframes that should always be present — inject if AI forgot them
REQUIRED_KEYFRAMES = """
<style id="mvp-keyframes">
  @keyframes fadeIn  { from{opacity:0}                               to{opacity:1} }
  @keyframes fadeUp  { from{opacity:0;transform:translateY(35px)}   to{opacity:1;transform:translateY(0)} }
  @keyframes slideUp { from{opacity:0;transform:translateY(50px)}   to{opacity:1;transform:translateY(0)} }
  @keyframes slideLeft{from{opacity:0;transform:translateX(-50px)}  to{opacity:1;transform:translateX(0)} }
  @keyframes slideRight{from{opacity:0;transform:translateX(50px)}  to{opacity:1;transform:translateX(0)} }
  @keyframes scaleW  { from{transform:scaleX(0)}                    to{transform:scaleX(1)} }
  body { margin:0; padding:0; width:1920px; height:1080px; overflow:hidden; }
</style>
"""

def ensure_html_structure(html: str) -> str:
    """Ensure the HTML has proper structure and required keyframes."""
    # Inject keyframes if missing
    if "@keyframes fadeIn" not in html:
        if "</head>" in html:
            html = html.replace("</head>", REQUIRED_KEYFRAMES + "</head>")
        elif "<body" in html:
            html = html.replace("<body", REQUIRED_KEYFRAMES + "<body", 1)
        else:
            html = REQUIRED_KEYFRAMES + html

    # Wrap bare <body> HTML in full document if needed
    if not html.strip().startswith("<!DOCTYPE") and not html.strip().startswith("<html"):
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'></head>{html}</html>"

    return html


def record_with_playwright(html_path: Path, output_webm: Path) -> None:
    print("[3/4] Recording with Playwright...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                print("Run: playwright install chromium")
                sys.exit(1)
            raise

        context = browser.new_context(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            record_video_dir=str(output_webm.parent),
            record_video_size={"width": VIEWPORT_W, "height": VIEWPORT_H}
        )
        page = context.new_page()
        # domcontentloaded = don't wait for images (they're base64 embedded anyway)
        page.goto(html_path.resolve().as_uri(), wait_until="domcontentloaded")

        # Wait for animations to play
        page.wait_for_timeout(SCENE_DURATION)

        context.close()   # flushes and saves video
        browser.close()

    # Playwright names the video with a random UUID — find and rename it
    candidates = sorted(
        output_webm.parent.glob("*.webm"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    if not candidates:
        print("ERROR: Playwright did not produce a .webm file.")
        sys.exit(1)
    candidates[0].replace(output_webm)
    print(f"      Saved: {output_webm}")


def convert_to_mp4(webm_path: Path, mp4_path: Path) -> None:
    print("[4/4] Converting webm to mp4 with FFmpeg...")
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(webm_path),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(mp4_path)
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg error:\n{result.stderr[-600:]}")
        sys.exit(1)
    print(f"      Saved: {mp4_path}")


def main():
    if len(sys.argv) > 1:
        scene_text = " ".join(sys.argv[1:])
    else:
        print("Enter scene text (2-3 sentences). Blank line to finish:")
        lines = []
        while True:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
        scene_text = " ".join(lines).strip()

    if not scene_text:
        print("No scene text. Exiting.")
        sys.exit(1)

    print(f"\nScene: {scene_text[:120]}{'...' if len(scene_text)>120 else ''}\n")
    OUTPUT_DIR.mkdir(exist_ok=True)

    api_key  = get_api_key()

    # Step 1: AI generates HTML with Pollinations image URLs
    html = generate_html(scene_text, api_key)

    # Step 2: Download images, embed as base64
    html = download_images_as_base64(html)

    # Step 2b: Ensure keyframes and proper HTML structure
    html = ensure_html_structure(html)

    # Save final HTML (open in browser to preview)
    html_path = OUTPUT_DIR / "scene.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"      HTML saved: {html_path}")

    # Step 3: Record with Playwright
    webm_path = OUTPUT_DIR / "scene.webm"
    mp4_path  = OUTPUT_DIR / "scene.mp4"
    record_with_playwright(html_path, webm_path)

    # Step 4: Convert to mp4
    convert_to_mp4(webm_path, mp4_path)

    size_mb = mp4_path.stat().st_size / (1024 * 1024)
    print(f"\nDone!")
    print(f"  Video:   {mp4_path.resolve()}  ({size_mb:.1f} MB)")
    print(f"  Preview: {html_path.resolve()}")


if __name__ == "__main__":
    main()
