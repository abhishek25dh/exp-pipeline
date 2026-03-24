import re

path = 'd:/AI Tools/Explainer content/Testing/pipeline_runner.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

target = """  <label>RunPod URL</label>
  <input type="text" id="runpod-url" placeholder="xxxx-8188.proxy.runpod.net">

  <label>Para #s</label>"""

replacement = """  <label>RunPod URL</label>
  <input type="text" id="runpod-url" placeholder="xxxx-8188.proxy.runpod.net">

  <label style="color:#58a6ff; font-weight:bold;">Target Scenes</label>
  <input type="text" id="scene-filter" placeholder="e.g. 12, 15" title="Comma-separated scene numbers to generate" style="width:100px; border-color:#58a6ff;">

  <label>Para #s</label>"""

if target in text:
    text = text.replace(target, replacement)
    
    js_target = """    fetch('/gen_images', {
      method: 'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ runpod_url: url })
    })"""
    
    js_replacement = """    const scenes = document.getElementById('scene-filter') ? document.getElementById('scene-filter').value : '';
    fetch('/gen_images', {
      method: 'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ runpod_url: url, scene_filter: scenes })
    })"""
    
    if js_target in text:
        text = text.replace(js_target, js_replacement)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("pipeline_runner.py GUI patched successfully.")
else:
    print("Failed to find HTML target.")
