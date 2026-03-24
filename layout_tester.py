"""
Layout Tester — Pipeline Runner + Preview + Editor Web App
============================================================
Run: python layout_tester.py
Open: http://localhost:5555

Features:
  1. "Run Pipeline"  — pick layout + scene → runs all steps → shows preview
  2. "Paste JSON"    — paste any director script JSON → instant preview
  3. Canvas Editor   — add/delete/move elements, edit properties, drag & drop
  4. "Render PNG"    — export canvas as 1920×1080 PNG
"""

import os, sys, json, glob, subprocess, time, threading, queue, random, uuid, socket, re
import requests
import websocket
from flask import Flask, render_template_string, request, jsonify, Response, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
IMAGE_PROMPTS_DIR = os.path.join(ASSETS_DIR, 'image_prompts')
DIRECTOR_DIR = os.path.join(ASSETS_DIR, 'directorscript')
OUTPUTS_DIR = os.path.join(ASSETS_DIR, 'outputs')
os.makedirs(IMAGE_PROMPTS_DIR, exist_ok=True)

DEFAULT_RUNPOD_URL = os.environ.get("COMFYUI_RUNPOD_URL", "3fprhqv1uk7th5-8188.proxy.runpod.net")
COMFY_CLIENT_ID = str(uuid.uuid4())
LIVE_DIRECTOR_CACHE = {}

# ─── HTML Template ────────────────────────────────────────────────────────────

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Layout Tester</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0f0f0f; color: #e0e0e0; overflow: hidden; height: 100vh; display: flex; flex-direction: column; }

  /* ── TOP BAR ── */
  .top-bar {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    padding: 6px 16px; border-bottom: 1px solid #333; flex-shrink: 0;
  }
  .top-bar .logo { font-size: 16px; color: #fff; font-weight: 700; white-space: nowrap; }
  .top-bar .logo span { color: #ffa500; }
  .top-bar .sep { width: 1px; height: 26px; background: #444; }

  .top-bar select, .top-bar input[type=number] {
    padding: 5px 8px; border-radius: 4px; border: 1px solid #444;
    background: #1a1a2e; color: #fff; font-size: 12px;
  }
  .top-bar select { min-width: 170px; }
  .top-bar input[type=number] { width: 50px; }
  .top-bar label { font-size: 11px; color: #888; margin-right: 2px; }

  .btn { padding: 5px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.15s; white-space: nowrap; }
  .btn-run { background: linear-gradient(135deg, #ff8c00, #ff6600); color: #fff; }
  .btn-run:hover { background: linear-gradient(135deg, #ff9f33, #ff7722); }
  .btn-run:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-sm { padding: 4px 10px; font-size: 11px; background: #2a2a2a; color: #ccc; border: 1px solid #444; }
  .btn-sm:hover { background: #333; }
  .btn-green { background: #1b5e20; color: #8eff8e; border-color: #2e7d32; }

  /* ── EDITOR TOOLBAR (inside canvas area) ── */
  .editor-toolbar {
    position: absolute; top: 8px; left: 50%; transform: translateX(-50%);
    display: flex; gap: 4px; z-index: 100; padding: 4px 8px;
    background: rgba(0,0,0,0.75); border-radius: 6px; backdrop-filter: blur(6px);
  }
  .editor-toolbar .tbtn {
    padding: 4px 10px; font-size: 11px; font-weight: 600; border: 1px solid #555;
    border-radius: 4px; cursor: pointer; transition: all 0.15s; white-space: nowrap;
  }
  .tbtn-img { background: #0d47a1; color: #90caf9; border-color: #1565c0; }
  .tbtn-txt { background: #e65100; color: #ffe0b2; border-color: #ef6c00; }
  .tbtn-arr { background: #880e4f; color: #f8bbd0; border-color: #ad1457; }
  .tbtn-layer { background: #333; color: #ccc; }
  .tbtn-del { background: #b71c1c; color: #ffcdd2; border-color: #c62828; }
  .tbtn:hover { filter: brightness(1.2); }

  /* ── MAIN AREA ── */
  .canvas-area {
    flex: 1; display: flex; align-items: center; justify-content: center;
    background: #111; position: relative; overflow: hidden;
  }
  .canvas-wrap {
    border: 2px solid #333; border-radius: 6px; overflow: hidden; background: #fff;
    box-shadow: 0 4px 40px rgba(0,0,0,0.6);
  }
  .canvas-badge { position: absolute; top: 8px; left: 14px; font-size: 11px; color: #555; background: rgba(0,0,0,0.6); padding: 2px 8px; border-radius: 4px; }
  .element-badge { position: absolute; top: 8px; right: 14px; font-size: 12px; color: #ffa500; background: rgba(0,0,0,0.6); padding: 2px 8px; border-radius: 4px; }

  /* ── PROPERTIES PANEL (right side overlay) ── */
  .props-panel {
    position: absolute; right: 10px; top: 50px; width: 260px;
    background: rgba(20,20,20,0.92); border: 1px solid #333; border-radius: 8px;
    padding: 12px; z-index: 90; backdrop-filter: blur(8px);
    display: none;
  }
  .props-panel.visible { display: block; }
  .props-panel h4 { font-size: 12px; color: #ffa500; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }
  .props-panel label { font-size: 10px; color: #888; display: block; margin-top: 6px; }
  .props-panel input, .props-panel select {
    width: 100%; padding: 4px 6px; margin-top: 2px; border-radius: 4px;
    border: 1px solid #444; background: #1a1a1a; color: #fff; font-size: 12px;
  }
  .props-panel input[readonly] { color: #666; }
  .props-row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .filename-row { display: flex; gap: 4px; align-items: flex-end; }
  .filename-row input { flex: 1; }
  .btn-load { padding: 4px 8px; font-size: 10px; font-weight: 700; background: #0d47a1; color: #90caf9; border: 1px solid #1565c0; border-radius: 4px; cursor: pointer; white-space: nowrap; margin-top: 2px; }
  .btn-load:hover { background: #1565c0; }
  .btn-load.loading { opacity: 0.5; cursor: wait; }
  .img-status { font-size: 9px; margin-top: 2px; }
  .img-status.loaded { color: #66bb6a; }
  .img-status.error { color: #ef5350; }
  .img-status.pending { color: #888; }

  /* Selected element tooltip */
  .selected-info {
    position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
    background: rgba(0,0,0,0.85); color: #fff; padding: 4px 12px;
    border-radius: 5px; font-size: 11px; font-family: 'Consolas', monospace;
    display: none; z-index: 50; white-space: nowrap;
  }
  .selected-info.visible { display: block; }

  /* ── BOTTOM DRAWER ── */
  .bottom-drawer { flex-shrink: 0; background: #141414; border-top: 1px solid #2a2a2a; transition: height 0.25s ease; overflow: hidden; }
  .bottom-drawer.collapsed { height: 32px; }
  .bottom-drawer.expanded { height: 240px; }
  .drawer-header {
    height: 32px; display: flex; align-items: center; justify-content: space-between;
    padding: 0 14px; cursor: pointer; user-select: none;
  }
  .drawer-header:hover { background: #1a1a1a; }
  .drawer-header .title { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
  .drawer-header .toggle { font-size: 13px; color: #666; }
  .drawer-body { display: flex; height: calc(100% - 32px); overflow: hidden; }

  .log-pane {
    flex: 1; padding: 6px 12px; overflow-y: auto;
    font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; line-height: 1.5;
    background: #0a0a0a; border-right: 1px solid #222;
  }
  .log-step { color: #4fc3f7; } .log-ok { color: #66bb6a; } .log-err { color: #ef5350; } .log-info { color: #666; } .log-time { color: #ffa500; }

  .json-pane { flex: 1; display: flex; flex-direction: column; padding: 6px; }
  .json-pane textarea { flex: 1; background: #0a0a0a; color: #4fc3f7; border: 1px solid #333; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 11px; padding: 6px; resize: none; }
  .json-pane .json-actions { display: flex; gap: 4px; margin-top: 4px; }

  .table-pane { flex: 1; overflow-y: auto; border-left: 1px solid #222; }
  .table-pane table { width: 100%; border-collapse: collapse; font-size: 11px; }
  .table-pane th { text-align: left; color: #888; padding: 3px 6px; border-bottom: 1px solid #333; font-weight: 600; position: sticky; top: 0; background: #141414; }
  .table-pane td { padding: 2px 6px; border-bottom: 1px solid #1a1a1a; color: #ccc; font-family: 'Consolas', monospace; }
  .table-pane tr:hover td { background: #1a1a1a; }

  .drop-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,165,0,0.1); border: 3px dashed #ffa500; display: none; align-items: center; justify-content: center; font-size: 18px; color: #ffa500; font-weight: 600; z-index: 100; }
  .drop-overlay.visible { display: flex; }

  /* ── GRID VIEW ── */
  .grid-view {
    display: none; position: fixed; inset: 0; z-index: 200;
    background: #0d0d0d; flex-direction: column;
  }
  .grid-view.visible { display: flex; }
  .grid-header {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    padding: 8px 16px; background: #1a1a2e; border-bottom: 1px solid #333; flex-shrink: 0;
  }
  .grid-title { font-size: 15px; font-weight: 700; color: #ffa500; }
  .grid-header input[type=number] { width: 72px; padding: 5px 8px; border-radius: 4px; border: 1px solid #444; background: #1a1a2e; color: #fff; font-size: 12px; }
  .grid-header label { font-size: 11px; color: #888; }
  .grid-body { flex: 1; overflow-y: auto; padding: 16px; }
  .scene-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; max-width: 1500px; margin: 0 auto; }
  .scene-card {
    background: #1a1a1a; border: 2px solid #333; border-radius: 8px;
    overflow: hidden; cursor: pointer; transition: border-color 0.15s, transform 0.1s;
  }
  .scene-card:hover { border-color: #ffa500; transform: scale(1.015); }
  .scene-card-header {
    padding: 6px 10px; font-size: 12px; font-weight: 700; color: #ffa500;
    background: #111; border-bottom: 1px solid #2a2a2a;
    display: flex; justify-content: space-between; align-items: center;
  }
  .scene-card canvas { display: block; width: 100%; height: auto; background: #fff; }
  .scene-card-footer { padding: 4px 10px; font-size: 10px; color: #555; background: #0f0f0f; }
  .scene-card-missing { opacity: 0.35; cursor: default; }
  .scene-card-missing:hover { border-color: #333; transform: none; }
  .scene-card-missing-msg { padding: 40px 10px; text-align: center; color: #555; font-size: 12px; background: #fff; }
</style>
</head>
<body>

<!-- ── TOP BAR ── -->
<div class="top-bar">
  <div class="logo">🎬 Layout <span>Tester</span></div>
  <div class="sep"></div>
  <label>Layout</label>
  <select id="layout-num">
    <option value="1">1 — Left vs Right</option>
    <option value="2">2 — Central Concept</option>
    <option value="3">3 — Full Scatter</option>
    <option value="4">4 — Host + Float</option>
    <option value="5">5 — Cause → Effect</option>
    <option value="6">6 — Two Rows (Image + Texts)</option>
    <option value="7">7 — Center Host + Side Groups</option>
    <option value="8">8 — Timeline Path</option>
    <option value="9">9 — 2x2 Grid / Comic Panels</option>
    <option value="10">10 — Macro to Micro (Zoom)</option>
    <option value="11">11 — Core Mind-Map</option>
    <option value="12">12 — Layout 12</option>
    <option value="13">13 — Layout 13</option>
    <option value="14">14 — Layout 14</option>
    <option value="15">15 — Layout 15</option>
    <option value="16">16 — Layout 16</option>
    <option value="17">17 — Layout 17</option>
    <option value="18">18 — Layout 18</option>
    <option value="19">19 — Pyramid Stack</option>
  </select>
  <label>Scene</label>
  <input type="number" id="scene-num" value="1" min="1">
  <button class="btn btn-run" id="run-btn" onclick="runPipeline()">▶ Run Pipeline</button>
  <div class="sep"></div>
  <button class="btn btn-sm" onclick="previewPastedJSON()">👁 Preview JSON</button>
  <button class="btn btn-sm" onclick="loadFromDisk()">📂 Load from Disk</button>
  <button class="btn btn-sm" onclick="saveToDisk()">💾 Save to Disk</button>
  <button class="btn btn-sm" onclick="loadImagePrompts()">🗂 Load Img Prompts</button>
  <button class="btn btn-sm" onclick="generateImagePrompts()">✨ Generate Img Prompts</button>
  <label>RunPod</label>
  <input type="text" id="runpod-url" value="3fprhqv1uk7th5-8188.proxy.runpod.net" style="min-width:260px;width:260px;">
  <button class="btn btn-sm btn-green" onclick="generateImagesComfyUI()">🖼 Generate Images</button>
  <button class="btn btn-sm btn-green" id="run-img-pipeline-btn" onclick="runImagePipeline()">🚀 Run Image Pipeline</button>
  <div class="sep"></div>
  <span id="access-urls" style="font-size:11px;color:#9aa;max-width:520px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></span>
  <div class="sep"></div>
  <button class="btn btn-sm btn-green" onclick="renderPNG()">📸 Render PNG</button>
  <button class="btn btn-sm" onclick="openGridView()" style="background:#0d47a1;color:#90caf9;border-color:#1565c0;">⊞ Browse Scenes</button>
  <div class="sep"></div>
  <label>Font</label>
  <select id="preview-font" onchange="onPreviewFontChanged()" style="min-width:150px;">
    <option value="Comic Sans MS, Comic Sans, cursive">Comic Sans</option>
    <option value="Arial, Helvetica, sans-serif">Arial</option>
    <option value="Verdana, Geneva, sans-serif">Verdana</option>
    <option value="Trebuchet MS, Arial, sans-serif">Trebuchet MS</option>
    <option value="Times New Roman, Times, serif">Times New Roman</option>
    <option value="Georgia, serif">Georgia</option>
    <option value="Courier New, Courier, monospace">Courier New</option>
    <option value="Impact, sans-serif">Impact</option>
  </select>
  <label style="display:flex;align-items:center;gap:4px;cursor:pointer;">
    <input type="checkbox" id="preview-bold" onchange="onPreviewFontChanged()" style="cursor:pointer;">Bold
  </label>
</div>

<!-- ── CANVAS AREA ── -->
<div class="canvas-area" id="canvas-area">
  <div class="canvas-badge">960 × 540 (1920×1080 ÷ 2)</div>
  <div class="element-badge" id="element-badge"></div>

  <!-- Editor Toolbar (floating above canvas) -->
  <div class="editor-toolbar">
    <button class="tbtn tbtn-img" onclick="addElement('image')">+ Image</button>
    <button class="tbtn tbtn-txt" onclick="addElement('text_highlighted')">+ Text</button>
    <button class="tbtn tbtn-txt" onclick="addElement('text_red')">+ Red</button>
    <button class="tbtn tbtn-txt" onclick="addElement('text_black')">+ Black</button>
    <button class="tbtn tbtn-arr" onclick="addElement('arrow')">+ Arrow</button>
    <span style="color:#555">|</span>
    <button class="tbtn tbtn-layer" onclick="moveLayer('up')">▲ Front</button>
    <button class="tbtn tbtn-layer" onclick="moveLayer('down')">▼ Back</button>
    <button class="tbtn tbtn-del" onclick="deleteSelected()">🗑 Delete</button>
  </div>

  <!-- Properties Panel (right side overlay) -->
  <div class="props-panel" id="props-panel">
    <h4>🛠 Element Properties</h4>
    <div class="props-row">
      <div><label>ID</label><input id="prop-id" readonly></div>
      <div>
        <label>Type</label>
        <select id="prop-type" onchange="applyProps()">
          <option value="image">image</option>
          <option value="arrow">arrow</option>
          <option value="text_black">text_black</option>
          <option value="text_red">text_red</option>
          <option value="text_highlighted">text_highlighted</option>
        </select>
      </div>
    </div>
    <div id="prop-phrase-div"><label>Phrase</label><input id="prop-phrase" oninput="applyProps()"></div>
    <div id="prop-filename-div">
      <label>Filename</label>
      <div class="filename-row">
        <input id="prop-filename" oninput="applyProps()">
        <button class="btn-load" id="btn-load-img" onclick="loadImageForSelected()">📥 Load</button>
      </div>
      <div class="img-status pending" id="img-status"></div>
    </div>
    <div id="prop-text-div"><label>Text Content</label><input id="prop-text" oninput="applyProps()"></div>
    <div id="prop-desc-div"><label>AI Description</label><input id="prop-desc" oninput="applyProps()"></div>
    <div class="props-row" style="margin-top:6px;">
      <div>
        <label>Animation</label>
        <select id="prop-anim" onchange="applyProps()">
          <option value="pop">pop</option>
          <option value="slide_in_left">slide_in_left</option>
          <option value="slide_in_right">slide_in_right</option>
          <option value="slide_in_up">slide_in_up</option>
          <option value="typing">typing</option>
          <option value="none">none</option>
        </select>
      </div>
      <div>
        <label>Property</label>
        <select id="prop-property" onchange="applyProps()">
          <option value="">none</option>
          <option value="shadow">shadow</option>
        </select>
      </div>
    </div>
  </div>

  <div class="canvas-wrap">
    <canvas id="preview-canvas" width="960" height="540"></canvas>
  </div>
  <div class="selected-info" id="selected-info"></div>
  <div class="drop-overlay" id="drop-overlay">Drop .json file to preview</div>
</div>

<!-- ── BOTTOM DRAWER ── -->
<div class="bottom-drawer expanded" id="bottom-drawer">
  <div class="drawer-header" onclick="toggleDrawer()">
    <span class="title">▼ Log / JSON / Elements</span>
    <span class="toggle" id="drawer-toggle">▼</span>
  </div>
  <div class="drawer-body">
    <div class="log-pane" id="progress-log">
      <div class="log-info">Ready. Select a layout and click ▶ Run Pipeline.</div>
    </div>
    <div class="json-pane">
      <textarea id="json-input" placeholder='Paste director script JSON here...'></textarea>
      <div class="json-actions">
        <button class="btn btn-sm" onclick="previewPastedJSON()">👁 Preview</button>
        <button class="btn btn-sm" onclick="copyJSON()">📋 Copy</button>
      </div>
    </div>
    <div class="table-pane" id="info-panel">
      <table><tr><th colspan="8" style="color:#666">Elements will appear here</th></tr></table>
    </div>
  </div>
</div>

<script>
// ── Drawer ──
function toggleDrawer() {
  let d = document.getElementById('bottom-drawer');
  let t = document.getElementById('drawer-toggle');
  if (d.classList.contains('expanded')) { d.classList.replace('expanded','collapsed'); t.textContent='▲'; }
  else { d.classList.replace('collapsed','expanded'); t.textContent='▼'; }
}

// ══════════════════════════════════════════════════════════════════════════════
// FABRIC CANVAS
// ══════════════════════════════════════════════════════════════════════════════
let canvas = new fabric.Canvas('preview-canvas', { backgroundColor: '#ffffff', selection: true });

function getPreviewFontFamily() {
  const el = document.getElementById('preview-font');
  return el ? el.value : 'Comic Sans MS, Comic Sans, cursive';
}

function isPreviewBold() {
  const el = document.getElementById('preview-bold');
  return el ? el.checked : false;
}

function normalizeTextCase(text) {
  if (!text) return text;
  if (text === text.toUpperCase() && /[A-Z]/.test(text)) {
    return text.toLowerCase().replace(/(^\w|\s+\w)/g, c => c.toUpperCase());
  }
  return text;
}

function onPreviewFontChanged() {
  canvas.getObjects().forEach(obj => {
    if (obj.type === 'i-text' || obj.type === 'text') {
      obj.set({ fontFamily: getPreviewFontFamily(), fontWeight: isPreviewBold() ? 'bold' : 'normal' });
    }
  });
  canvas.renderAll();
}

canvas.on('selection:created', onSelect);
canvas.on('selection:updated', onSelect);
canvas.on('selection:cleared', () => {
  document.getElementById('selected-info').classList.remove('visible');
  document.getElementById('props-panel').classList.remove('visible');
});
canvas.on('object:modified', (e) => { onSelect(e); syncJSON(); });

// ── Selection / Info ──
function onSelect(e) {
  let obj = e.selected ? e.selected[0] : (e.target || canvas.getActiveObject());
  if (!obj || !obj._el) return;
  let el = obj._el;
  let info = document.getElementById('selected-info');
  info.textContent = `${el.element_id||'?'}  |  x:${Math.round(obj.left*2)} y:${Math.round(obj.top*2)}  |  scale:${(obj.scaleX*2).toFixed(2)}  |  angle:${Math.round(obj.angle)}°`;
  info.classList.add('visible');
  loadProps(obj);
}

// ── Sync canvas → JSON pane ──
function syncJSON() {
  let elements = [];
  canvas.getObjects().forEach(obj => {
    if (!obj._el) return;
    let el = { ...obj._el };
    el.x = Math.round(obj.left * 2);
    el.y = Math.round(obj.top * 2);
    el.scale = parseFloat((obj.scaleX * 2).toFixed(3));
    el.angle = Math.round(obj.angle);
    elements.push(el);
  });
  let sceneNum = document.getElementById('scene-num').value || '1';
  let data = { scene_id: canvas._sceneId || `scene_${sceneNum}`, elements };
  document.getElementById('json-input').value = JSON.stringify(data, null, 2);
  updateTable(elements);
  document.getElementById('element-badge').textContent = `${elements.length} elements | ${data.scene_id}`;
}

function updateTable(elements) {
  let h = '<table><tr><th>#</th><th>ID</th><th>Type</th><th>X</th><th>Y</th><th>Scale</th><th>°</th><th>Content</th></tr>';
  elements.forEach((el, i) => {
    let c = el.text_content || el.phrase || el.filename || '';
    h += `<tr><td>${i+1}</td><td>${el.element_id||'—'}</td><td>${el.type||''}</td><td>${el.x||0}</td><td>${el.y||0}</td><td>${el.scale||0}</td><td>${el.angle||0}°</td><td>${c.substring(0,25)}</td></tr>`;
  });
  document.getElementById('info-panel').innerHTML = h + '</table>';
}

// ══════════════════════════════════════════════════════════════════════════════
// RENDER DIRECTOR SCRIPT → CANVAS
// ══════════════════════════════════════════════════════════════════════════════
function renderDirectorScript(data) {
  canvas.clear(); canvas.backgroundColor = '#ffffff';
  canvas._sceneId = data.scene_id || 'scene_1';
  let elements = data.elements || [];
  const useCenteredCoords = isCenteredCoordinateScene(elements);

  elements.forEach(el => {
    let type = el.type || 'image';
    let sceneX = (typeof el.x === 'number') ? el.x : 960;
    let sceneY = (typeof el.y === 'number') ? el.y : 540;
    if (useCenteredCoords) {
      sceneX += 960;
      sceneY += 540;
    }
    let x = sceneX / 2.0;
    let y = sceneY / 2.0;
    let scale = (el.scale || 1.0) / 2.0;
    let angle = el.angle || 0;
    let shadow = (el.property === 'shadow') ? new fabric.Shadow({color:'rgba(0,0,0,0.4)',blur:12,offsetX:4,offsetY:4}) : null;

    let common = {
      left: x, top: y, scaleX: scale, scaleY: scale,
      originX: 'center', originY: 'center', angle: angle, shadow: shadow,
      selectable: true, evented: true,
      borderColor: '#ffa500', cornerColor: '#ff6600', cornerSize: 8,
      transparentCorners: false, cornerStyle: 'circle'
    };

    if (type.startsWith('text_')) {
      let text = normalizeTextCase(el.text_content || el.phrase || 'TEXT');
      let fill = '#000', bg = null;
      if (type === 'text_red') fill = '#dc143c';
      else if (type === 'text_highlighted') { fill = '#fff'; bg = '#ffa500'; }
      let t = new fabric.IText(text, {
        ...common, fontSize: 40, fontFamily: getPreviewFontFamily(),
        fontWeight: isPreviewBold() ? 'bold' : 'normal',
        fill, backgroundColor: bg
      });
      t._el = { ...el };
      canvas.add(t);
    } else if (type === 'arrow' || type === 'image') {
      // Try to load actual image from disk
      let fname = el.filename || (type === 'arrow' ? 'arrow.png' : '');
      let sceneId = data.scene_id || 'scene_1';
      if (fname) {
        _addImageWithFallback(fname, sceneId, el, common, type);
      } else {
        _addPlaceholder(el, common, type);
      }
    } else {
      _addPlaceholder(el, common, type);
    }
  });

  canvas.renderAll();
  syncJSON();
}

function isCenteredCoordinateScene(elements) {
  if (!elements.length) return false;
  let xs = [];
  let ys = [];
  elements.forEach(el => {
    if (typeof el.x === 'number') xs.push(el.x);
    if (typeof el.y === 'number') ys.push(el.y);
  });
  if (!xs.length || !ys.length) return false;
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const hasNegative = (minX < 0) || (minY < 0);
  const centeredRange = (maxX <= 960 && minX >= -960 && maxY <= 540 && minY >= -540);
  return hasNegative && centeredRange;
}

// Try loading image from scene folder first, then global, then show placeholder
function _isDefaultAssetFilename(filename) {
  let base = (filename || '').toLowerCase().replace(/\.[^.]+$/, '');
  return base === 'arrow' || base.startsWith('host');
}

function _addImageWithFallback(filename, sceneId, elData, common, type) {
  let sceneUrl = '/image/' + sceneId + '/' + encodeURIComponent(filename);
  let globalUrl = '/image/' + encodeURIComponent(filename);
  let firstUrl = _isDefaultAssetFilename(filename) ? globalUrl : sceneUrl;
  let secondUrl = _isDefaultAssetFilename(filename) ? sceneUrl : globalUrl;

  fabric.Image.fromURL(firstUrl, function(img) {
    if (img && img.width && img.width > 1) {
      img.set(common);
      img._el = { ...elData };
      img._el._loaded = true;
      canvas.add(img);
      canvas.renderAll();
      syncJSON();
    } else {
      // Try global fallback
      fabric.Image.fromURL(secondUrl, function(img2) {
        if (img2 && img2.width && img2.width > 1) {
          img2.set(common);
          img2._el = { ...elData };
          img2._el._loaded = true;
          canvas.add(img2);
          canvas.renderAll();
          syncJSON();
        } else {
          _addPlaceholder(elData, common, type);
        }
      }, { crossOrigin: 'anonymous' });
    }
  }, { crossOrigin: 'anonymous' });
}

// Placeholder for images/arrows that can't be loaded
function _addPlaceholder(elData, common, type) {
  if (type === 'arrow') {
    let rect = new fabric.Rect({
      ...common, width: 1024, height: 1024,
      fill: 'rgba(255,0,0,0.3)', stroke: '#f44336', strokeWidth: 4
    });
    rect._el = { ...elData };
    canvas.add(rect);
  } else {
    let label = elData.element_id || 'img';
    let phrase = elData.phrase || '';
    let items = [
      new fabric.Rect({ width:1024, height:1024, fill:'#e8e8e8', stroke:'#bbb', strokeWidth:2, rx:12, ry:12, originX:'center', originY:'center' }),
      new fabric.Text(label, { fontSize:56, fontFamily:'Segoe UI', fill:'#888', originX:'center', originY:'center', top:-40, textAlign:'center' })
    ];
    if (phrase) items.push(new fabric.Text(phrase, { fontSize:44, fontFamily:'Segoe UI', fill:'#aaa', originX:'center', top:60, textAlign:'center' }));
    let grp = new fabric.Group(items, { ...common, width:1024, height:1024 });
    grp._el = { ...elData };
    canvas.add(grp);
  }
  canvas.renderAll();
  syncJSON();
}

// ══════════════════════════════════════════════════════════════════════════════
// ADD / DELETE / LAYER
// ══════════════════════════════════════════════════════════════════════════════
function addElement(type) {
  let newId = type + '_' + Date.now();
  let baseScale = type.startsWith('text') ? 1.74 : 0.2;
  let common = {
    left: 480, top: 270, scaleX: baseScale/2, scaleY: baseScale/2,
    originX: 'center', originY: 'center',
    borderColor: '#ffa500', cornerColor: '#ff6600', cornerSize: 8,
    transparentCorners: false, cornerStyle: 'circle', angle: 0
  };

  let elData = {
    element_id: newId, type: type,
    x: 960, y: 540, scale: baseScale, angle: 0,
    phrase: '', description: '', filename: '', text_content: '',
    animation: 'pop', property: ''
  };

  if (type.startsWith('text')) {
    let fill = '#000', bg = null;
    if (type === 'text_red') fill = '#dc143c';
    else if (type === 'text_highlighted') { fill = '#fff'; bg = '#ffa500'; }
    elData.text_content = 'NEW TEXT';
    elData.phrase = 'new text';
    let obj = new fabric.IText('NEW TEXT', {
      ...common, fontSize: 40, fontFamily: getPreviewFontFamily(),
      fontWeight: isPreviewBold() ? 'bold' : 'normal', fill, backgroundColor: bg
    });
    obj._el = elData;
    canvas.add(obj);
    canvas.setActiveObject(obj);
    canvas.renderAll();
    syncJSON();
    loadProps(obj);
  } else if (type === 'arrow') {
    elData.filename = 'arrow.png';
    // Auto-load arrow.png from disk
    let sceneId = canvas._sceneId || 'scene_1';
    _loadAndAddImage('arrow.png', sceneId, elData, common, function(obj) {
      canvas.setActiveObject(obj);
      loadProps(obj);
    });
  } else {
    elData.filename = '';
    elData.phrase = 'new element';
    elData.description = 'Describe this element...';
    let items = [
      new fabric.Rect({ width:1024, height:1024, fill:'#ccc', stroke:'#f44336', strokeWidth:4, strokeDashArray:[20,20], rx:12, ry:12, originX:'center', originY:'center' }),
      new fabric.Text(newId, { fontSize:56, fontFamily:'Segoe UI', fill:'#888', originX:'center', originY:'center', textAlign:'center' })
    ];
    let obj = new fabric.Group(items, { ...common, width: 1024, height: 1024 });
    obj._el = elData;
    canvas.add(obj);
    canvas.setActiveObject(obj);
    canvas.renderAll();
    syncJSON();
    loadProps(obj);
  }
  addLog2('log-ok', `Added ${type}: ${newId}`);
}

// Load image from disk and add to canvas, with callback on success
function _loadAndAddImage(filename, sceneId, elData, common, onDone) {
  let sceneUrl = '/image/' + sceneId + '/' + encodeURIComponent(filename);
  let globalUrl = '/image/' + encodeURIComponent(filename);
  let firstUrl = _isDefaultAssetFilename(filename) ? globalUrl : sceneUrl;
  let secondUrl = _isDefaultAssetFilename(filename) ? sceneUrl : globalUrl;

  fabric.Image.fromURL(firstUrl, function(img) {
    if (img && img.width && img.width > 1) {
      img.set(common);
      img._el = { ...elData, _loaded: true };
      canvas.add(img);
      canvas.renderAll();
      syncJSON();
      if (onDone) onDone(img);
    } else {
      fabric.Image.fromURL(secondUrl, function(img2) {
        if (img2 && img2.width && img2.width > 1) {
          img2.set(common);
          img2._el = { ...elData, _loaded: true };
          canvas.add(img2);
          canvas.renderAll();
          syncJSON();
          if (onDone) onDone(img2);
        } else {
          // Fallback to placeholder
          _addPlaceholder(elData, common, elData.type);
          addLog2('log-err', 'Image not found: ' + filename);
        }
      }, { crossOrigin: 'anonymous' });
    }
  }, { crossOrigin: 'anonymous' });
}

function deleteSelected() {
  let a = canvas.getActiveObject();
  if (!a) return;
  let id = a._el ? a._el.element_id : '?';
  canvas.remove(a);
  document.getElementById('props-panel').classList.remove('visible');
  document.getElementById('selected-info').classList.remove('visible');
  canvas.renderAll();
  syncJSON();
  addLog2('log-info', `Deleted: ${id}`);
}

function moveLayer(dir) {
  let a = canvas.getActiveObject(); if (!a) return;
  if (dir === 'up') a.bringForward(); else a.sendBackwards();
  canvas.renderAll(); syncJSON();
}

// ══════════════════════════════════════════════════════════════════════════════
// PROPERTIES PANEL
// ══════════════════════════════════════════════════════════════════════════════
function loadProps(obj) {
  if (!obj || !obj._el) return;
  let el = obj._el;
  let p = document.getElementById('props-panel');
  p.classList.add('visible');

  document.getElementById('prop-id').value = el.element_id || '';
  document.getElementById('prop-type').value = el.type || 'image';
  document.getElementById('prop-phrase').value = el.phrase || '';
  document.getElementById('prop-filename').value = el.filename || '';
  document.getElementById('prop-text').value = el.text_content || '';
  document.getElementById('prop-desc').value = el.description || '';
  document.getElementById('prop-anim').value = el.animation || 'pop';
  document.getElementById('prop-property').value = el.property || '';

  // Show/hide relevant fields
  let isText = (el.type || '').startsWith('text');
  let isArrow = el.type === 'arrow';
  document.getElementById('prop-filename-div').style.display = isText ? 'none' : 'block';
  document.getElementById('prop-text-div').style.display = isText ? 'block' : 'none';
  document.getElementById('prop-desc-div').style.display = (isText || isArrow) ? 'none' : 'block';

  // Update image status indicator
  let statusEl = document.getElementById('img-status');
  if (!isText) {
    if (el._loaded) {
      statusEl.className = 'img-status loaded';
      statusEl.textContent = '✓ Image loaded';
    } else if (el.filename) {
      statusEl.className = 'img-status pending';
      statusEl.textContent = 'Not loaded — click Load';
    } else {
      statusEl.className = 'img-status pending';
      statusEl.textContent = 'Enter filename & click Load';
    }
  }
}

function applyProps() {
  let a = canvas.getActiveObject();
  if (!a || !a._el) return;

  a._el.type = document.getElementById('prop-type').value;
  a._el.phrase = document.getElementById('prop-phrase').value;
  a._el.filename = document.getElementById('prop-filename').value;
  a._el.text_content = document.getElementById('prop-text').value;
  a._el.description = document.getElementById('prop-desc').value;
  a._el.animation = document.getElementById('prop-anim').value;
  a._el.property = document.getElementById('prop-property').value;

  // Update text on canvas if it's a text element
  if (a._el.type.startsWith('text') && a.set && typeof a.text !== 'undefined') {
    a.set({ text: a._el.text_content });

    // Update colors based on type
    if (a._el.type === 'text_red') a.set({ fill: '#dc143c', backgroundColor: null });
    else if (a._el.type === 'text_highlighted') a.set({ fill: '#fff', backgroundColor: '#ffa500' });
    else a.set({ fill: '#000', backgroundColor: null });
  }

  // Update shadow
  if (a._el.property === 'shadow') a.set({ shadow: new fabric.Shadow({color:'rgba(0,0,0,0.4)',blur:12,offsetX:4,offsetY:4}) });
  else a.set({ shadow: null });

  // Show/hide fields
  let isText = a._el.type.startsWith('text');
  let isArrow = a._el.type === 'arrow';
  document.getElementById('prop-filename-div').style.display = isText ? 'none' : 'block';
  document.getElementById('prop-text-div').style.display = isText ? 'block' : 'none';
  document.getElementById('prop-desc-div').style.display = (isText || isArrow) ? 'none' : 'block';

  canvas.renderAll();
  syncJSON();
}

// ══════════════════════════════════════════════════════════════════════════════
// LOAD IMAGE FOR SELECTED ELEMENT
// ══════════════════════════════════════════════════════════════════════════════
function loadImageForSelected() {
  let a = canvas.getActiveObject();
  if (!a || !a._el) { addLog2('log-err', 'No element selected.'); return; }

  let filename = document.getElementById('prop-filename').value.trim();
  if (!filename) { addLog2('log-err', 'Enter a filename first.'); return; }

  a._el.filename = filename;
  let sceneId = canvas._sceneId || 'scene_1';
  let btn = document.getElementById('btn-load-img');
  let statusEl = document.getElementById('img-status');
  btn.classList.add('loading');
  btn.textContent = '⏳...';
  statusEl.className = 'img-status pending';
  statusEl.textContent = 'Loading...';

  // Save current transform
  let savedLeft = a.left, savedTop = a.top;
  let savedScaleX = a.scaleX, savedScaleY = a.scaleY;
  let savedAngle = a.angle;
  let savedEl = { ...a._el };
  let shadow = a.shadow;

  let sceneUrl = '/image/' + sceneId + '/' + encodeURIComponent(filename);
  let globalUrl = '/image/' + encodeURIComponent(filename);
  let firstUrl = _isDefaultAssetFilename(filename) ? globalUrl : sceneUrl;
  let secondUrl = _isDefaultAssetFilename(filename) ? sceneUrl : globalUrl;

  function onSuccess(img) {
    img.set({
      left: savedLeft, top: savedTop,
      scaleX: savedScaleX, scaleY: savedScaleY,
      originX: 'center', originY: 'center',
      angle: savedAngle, shadow: shadow,
      selectable: true, evented: true,
      borderColor: '#ffa500', cornerColor: '#ff6600', cornerSize: 8,
      transparentCorners: false, cornerStyle: 'circle'
    });
    savedEl._loaded = true;
    img._el = savedEl;

    // Replace old object
    let idx = canvas.getObjects().indexOf(a);
    canvas.remove(a);
    canvas.insertAt(img, idx >= 0 ? idx : canvas.getObjects().length);
    canvas.setActiveObject(img);
    canvas.renderAll();
    syncJSON();
    loadProps(img);

    btn.classList.remove('loading');
    btn.textContent = '📥 Load';
    statusEl.className = 'img-status loaded';
    statusEl.textContent = '✓ Image loaded';
    addLog2('log-ok', 'Loaded image: ' + filename);
  }

  function onFail() {
    btn.classList.remove('loading');
    btn.textContent = '📥 Load';
    statusEl.className = 'img-status error';
    statusEl.textContent = '✗ File not found';
    addLog2('log-err', 'Image not found: ' + filename + ' (checked ' + sceneId + '/ and global)');
  }

  fabric.Image.fromURL(firstUrl, function(img) {
    if (img && img.width && img.width > 1) {
      onSuccess(img);
    } else {
      fabric.Image.fromURL(secondUrl, function(img2) {
        if (img2 && img2.width && img2.width > 1) {
          onSuccess(img2);
        } else {
          onFail();
        }
      }, { crossOrigin: 'anonymous' });
    }
  }, { crossOrigin: 'anonymous' });
}

// ══════════════════════════════════════════════════════════════════════════════
// PIPELINE RUNNER (SSE)
// ══════════════════════════════════════════════════════════════════════════════
let running = false;
function runPipeline() {
  if (running) return; running = true;
  let layoutNum = document.getElementById('layout-num').value;
  let sceneNum = document.getElementById('scene-num').value;
  let btn = document.getElementById('run-btn');
  let log = document.getElementById('progress-log');
  btn.disabled = true; btn.textContent = '⏳ Running...'; log.innerHTML = '';

  let d = document.getElementById('bottom-drawer');
  if (d.classList.contains('collapsed')) toggleDrawer();

  function addLog(cls, msg) { let div = document.createElement('div'); div.className = cls; div.textContent = msg; log.appendChild(div); log.scrollTop = log.scrollHeight; }
  addLog('log-info', `Starting Layout ${layoutNum}, Scene ${sceneNum}...`);

  let evtSource = new EventSource(`/run?layout=${layoutNum}&scene=${sceneNum}`);
  evtSource.onmessage = function(e) {
    let data = JSON.parse(e.data);
    if (data.type === 'step') addLog('log-step', `▶ ${data.msg}`);
    else if (data.type === 'stdout') addLog('log-info', `  ${data.msg}`);
    else if (data.type === 'ok') addLog('log-ok', `✓ ${data.msg}`);
    else if (data.type === 'error') addLog('log-err', `✗ ${data.msg}`);
    else if (data.type === 'time') addLog('log-time', `  ⏱ ${data.msg}`);
    else if (data.type === 'done') {
      addLog('log-ok', `\n✅ ${data.msg}`);
      evtSource.close(); running = false; btn.disabled = false; btn.textContent = '▶ Run Pipeline';
      fetch(`/load_director?scene=${sceneNum}`).then(r => r.json()).then(d => {
        if (d.error) addLog('log-err', d.error);
        else { renderDirectorScript(d); addLog('log-ok', `Preview: ${(d.elements||[]).length} elements`); }
      });
    } else if (data.type === 'fail') {
      addLog('log-err', `\n❌ ${data.msg}`);
      evtSource.close(); running = false; btn.disabled = false; btn.textContent = '▶ Run Pipeline';
    }
  };
  evtSource.onerror = function() { addLog('log-err', 'Connection lost.'); evtSource.close(); running = false; btn.disabled = false; btn.textContent = '▶ Run Pipeline'; };
}

// ══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════════════════════
function previewPastedJSON() {
  let raw = document.getElementById('json-input').value.trim();
  if (!raw) return;
  try { renderDirectorScript(JSON.parse(raw)); addLog2('log-ok', 'Preview updated.'); }
  catch(e) { addLog2('log-err', 'Invalid JSON: ' + e.message); }
}

function loadFromDisk() {
  let sceneNum = document.getElementById('scene-num').value;
  fetch(`/load_director?scene=${sceneNum}`).then(r => r.json()).then(d => {
    if (d.error) addLog2('log-err', d.error);
    else { renderDirectorScript(d); addLog2('log-ok', `Loaded scene_${sceneNum} from disk.`); }
  });
}

function saveToDisk() {
  let raw = document.getElementById('json-input').value.trim();
  if (!raw) { addLog2('log-err', 'Nothing to save.'); return; }
  let sceneNum = document.getElementById('scene-num').value || '1';
  let payload;
  try { payload = JSON.parse(raw); } catch(e) { addLog2('log-err', 'Invalid JSON.'); return; }
  payload.scene_id = `scene_${sceneNum}`;
  fetch('/save_director', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) })
    .then(r => r.json()).then(d => {
      if (d.error) addLog2('log-err', d.error);
      else addLog2('log-ok', d.msg);
    });
}

function loadImagePrompts() {
  let sceneNum = document.getElementById('scene-num').value;
  fetch(`/load_image_prompts?scene=${sceneNum}`).then(r => r.json()).then(d => {
    if (d.error) {
      addLog2('log-err', d.error);
      return;
    }
    let count = (d.elements || []).length;
    addLog2('log-ok', `Loaded ${count} image prompts from ${d.path}`);
    (d.elements || []).slice(0, 5).forEach((el, idx) => {
      let name = el.filename || `item_${idx + 1}`;
      let p = (el.image_prompt || '').slice(0, 90);
      addLog2('log-info', `${name}: ${p}${p.length >= 90 ? '...' : ''}`);
    });
  });
}

function generateImagePrompts() {
  let sceneNum = document.getElementById('scene-num').value;
  let raw = document.getElementById('json-input').value.trim();
  let body = {};

  if (raw) {
    try { body = JSON.parse(raw); }
    catch (e) {
      addLog2('log-err', 'Invalid JSON in editor. Save/fix JSON first.');
      return;
    }
  }

  fetch('/set_live_director_for_prompts', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  }).then(() => {
    let evt = new EventSource(`/generate_image_prompts_stream?scene=${sceneNum}`);
    addLog2('log-info', `Generating image prompts for scene_${sceneNum}...`);
    evt.onmessage = function(e) {
      let d = JSON.parse(e.data);
      if (d.type === 'info') addLog2('log-info', d.msg);
      else if (d.type === 'ok') addLog2('log-ok', d.msg);
      else if (d.type === 'error') addLog2('log-err', d.msg);
      else if (d.type === 'done') {
        addLog2('log-ok', d.msg);
        evt.close();
      }
    };
    evt.onerror = function() {
      addLog2('log-err', 'Prompt generation stream disconnected.');
      evt.close();
    };
  });
}

function generateImagesComfyUI() {
  let sceneNum = document.getElementById('scene-num').value;
  let runpodUrl = document.getElementById('runpod-url').value.trim();
  if (!runpodUrl) {
    addLog2('log-err', 'RunPod URL is required.');
    return;
  }

  addLog2('log-info', `Generating images for scene_${sceneNum} via ${runpodUrl} ...`);
  let evt = new EventSource(`/generate_images_comfyui_stream?scene=${sceneNum}&runpod_url=${encodeURIComponent(runpodUrl)}`);
  evt.onmessage = function(e) {
    let d = JSON.parse(e.data);
    if (d.type === 'progress') addLog2('log-info', d.msg);
    else if (d.type === 'ok') addLog2('log-ok', d.msg);
    else if (d.type === 'error') addLog2('log-err', d.msg);
    else if (d.type === 'done') {
      addLog2('log-ok', d.msg);
      if (d.generated !== undefined && d.total !== undefined) {
        addLog2('log-info', `Generated ${d.generated}/${d.total} images`);
      }
      evt.close();
      // Re-render current scene to swap placeholders with newly generated assets.
      previewPastedJSON();
    }
  };
  evt.onerror = function() {
    addLog2('log-err', 'Image generation stream disconnected.');
    evt.close();
  };
}

let imagePipelineRunning = false;
function runImagePipeline() {
  if (imagePipelineRunning) return;
  let startScene = document.getElementById('scene-num').value;
  let runpodUrl = document.getElementById('runpod-url').value.trim();
  if (!runpodUrl) {
    addLog2('log-err', 'RunPod URL is required.');
    return;
  }

  let raw = document.getElementById('json-input').value.trim();
  let body = {};
  if (raw) {
    try { body = JSON.parse(raw); }
    catch (e) {
      addLog2('log-err', 'Invalid JSON in editor. Save/fix JSON first.');
      return;
    }
  }

  let btn = document.getElementById('run-img-pipeline-btn');
  imagePipelineRunning = true;
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Running...'; }

  fetch('/set_live_director_for_prompts', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  }).then(() => {
    addLog2('log-info', `Starting image pipeline from scene_${startScene} ...`);
    let evt = new EventSource(`/run_image_pipeline_stream?start_scene=${startScene}&runpod_url=${encodeURIComponent(runpodUrl)}`);
    evt.onmessage = function(e) {
      let d = JSON.parse(e.data);
      if (d.type === 'scene') addLog2('log-step', d.msg);
      else if (d.type === 'progress') addLog2('log-info', d.msg);
      else if (d.type === 'ok') addLog2('log-ok', d.msg);
      else if (d.type === 'error') addLog2('log-err', d.msg);
      else if (d.type === 'done') {
        addLog2('log-ok', d.msg);
        evt.close();
        imagePipelineRunning = false;
        if (btn) { btn.disabled = false; btn.textContent = '🚀 Run Image Pipeline'; }
        previewPastedJSON();
      }
    };
    evt.onerror = function() {
      addLog2('log-err', 'Image pipeline stream disconnected.');
      evt.close();
      imagePipelineRunning = false;
      if (btn) { btn.disabled = false; btn.textContent = '🚀 Run Image Pipeline'; }
    };
  });
}

function initComfyUIConfig() {
  fetch('/comfyui_config').then(r => r.json()).then(d => {
    if (!d || d.error) return;
    let input = document.getElementById('runpod-url');
    if (input && d.default_runpod_url) input.value = d.default_runpod_url;
  }).catch(() => {});
}

function initAccessUrls() {
  fetch('/access_urls').then(r => r.json()).then(d => {
    let el = document.getElementById('access-urls');
    if (!el) return;
    let parts = [];
    if (d.lan_url) parts.push(`Phone (LAN): ${d.lan_url}`);
    if (d.public_url) parts.push(`Public: ${d.public_url}`);
    if (!d.public_url) parts.push('Public URL: set LAYOUT_TESTER_PUBLIC_URL env var');
    el.textContent = parts.join('  |  ');
  }).catch(() => {});
}

function renderPNG() {
  canvas.discardActiveObject(); canvas.renderAll();
  let dataURL = canvas.toDataURL({ format: 'png', multiplier: 2 });
  let link = document.createElement('a');
  link.download = (canvas._sceneId || 'scene') + '_layout_preview.png';
  link.href = dataURL; document.body.appendChild(link); link.click(); document.body.removeChild(link);
  addLog2('log-ok', 'Rendered PNG (1920×1080)');
}

function copyJSON() {
  let ta = document.getElementById('json-input'); ta.select(); document.execCommand('copy');
  addLog2('log-ok', 'JSON copied.');
}

function addLog2(cls, msg) {
  let log = document.getElementById('progress-log');
  let div = document.createElement('div'); div.className = cls; div.textContent = msg;
  log.appendChild(div); log.scrollTop = log.scrollHeight;
}

// ── Drag & Drop files ──
let canvasArea = document.getElementById('canvas-area');
let dropOverlay = document.getElementById('drop-overlay');
canvasArea.addEventListener('dragover', (e) => { e.preventDefault(); dropOverlay.classList.add('visible'); });
canvasArea.addEventListener('dragleave', () => { dropOverlay.classList.remove('visible'); });
canvasArea.addEventListener('drop', (e) => {
  e.preventDefault(); dropOverlay.classList.remove('visible');
  let file = e.dataTransfer.files[0]; if (!file) return;
  let reader = new FileReader();
  reader.onload = (ev) => {
    try { renderDirectorScript(JSON.parse(ev.target.result)); addLog2('log-ok', 'Dropped: ' + file.name); }
    catch(err) { addLog2('log-err', 'Invalid JSON: ' + err.message); }
  };
  reader.readAsText(file);
});

initComfyUIConfig();
initAccessUrls();

// ══════════════════════════════════════════════════════════════════════════════
// GRID VIEW — 10-scene browser
// ══════════════════════════════════════════════════════════════════════════════
let gridCurrentStart = 1;
const GRID_COUNT = 10;
const miniCanvasInstances = {};  // sceneNum -> fabric.Canvas

function openGridView() {
  document.getElementById('grid-view').classList.add('visible');
  loadGridRange(gridCurrentStart);
}

function closeGridView() {
  document.getElementById('grid-view').classList.remove('visible');
  _disposeMiniCanvases();
}

function _disposeMiniCanvases() {
  Object.keys(miniCanvasInstances).forEach(k => {
    try { miniCanvasInstances[k].dispose(); } catch(e) {}
    delete miniCanvasInstances[k];
  });
}

function gridPrevSet() {
  loadGridRange(Math.max(1, gridCurrentStart - GRID_COUNT));
}

function gridNextSet() {
  loadGridRange(gridCurrentStart + GRID_COUNT);
}

function gridLoadCustomRange() {
  const from = parseInt(document.getElementById('grid-from').value) || 1;
  loadGridRange(Math.max(1, from));
}

function loadGridRange(start) {
  gridCurrentStart = start;
  document.getElementById('grid-from').value = start;
  _disposeMiniCanvases();
  const grid = document.getElementById('scene-grid');
  grid.innerHTML = '<div style="color:#888;padding:20px;grid-column:span 3;">Loading scenes ' + start + '\u2013' + (start + GRID_COUNT - 1) + '...</div>';
  fetch('/load_director_batch?start=' + start + '&count=' + GRID_COUNT)
    .then(r => r.json())
    .then(data => renderGrid(data.scenes))
    .catch(err => { grid.innerHTML = '<div style="color:#ef5350;grid-column:span 3;">Error: ' + err + '</div>'; });
}

function renderGrid(scenes) {
  const grid = document.getElementById('scene-grid');
  grid.innerHTML = '';
  scenes.forEach(scene => {
    const card = document.createElement('div');
    if (scene.exists) {
      const nc = (scene.data.elements || []).length;
      card.className = 'scene-card';
      card.innerHTML =
        '<div class="scene-card-header">' +
          '<span>Scene ' + scene.scene_num + '</span>' +
          '<span style="color:#666;font-weight:400;font-size:10px;">' + nc + ' elements</span>' +
        '</div>' +
        '<canvas id="mini-c-' + scene.scene_num + '" width="480" height="270"></canvas>' +
        '<div class="scene-card-footer">' + (scene.data.scene_id || '') + '</div>';
      card.onclick = function() { selectSceneFromGrid(scene.scene_num, scene.data); };
    } else {
      card.className = 'scene-card scene-card-missing';
      card.innerHTML =
        '<div class="scene-card-header"><span>Scene ' + scene.scene_num + '</span><span style="color:#555;font-size:10px;font-weight:400;">missing</span></div>' +
        '<div class="scene-card-missing-msg">No director script</div>';
    }
    grid.appendChild(card);
    if (scene.exists) {
      requestAnimationFrame(function() { renderMiniSceneFabric('mini-c-' + scene.scene_num, scene.scene_num, scene.data); });
    }
  });
}

function renderMiniSceneFabric(canvasId, sceneNum, data) {
  const canvasEl = document.getElementById(canvasId);
  if (!canvasEl) return;

  // StaticCanvas: no upper-canvas overlay, no event interception, pure rendering
  const fc = new fabric.StaticCanvas(canvasEl, { backgroundColor: '#ffffff', renderOnAddRemove: false });
  miniCanvasInstances[sceneNum] = fc;

  // Mini canvas is 480x270; director space is 1920x1080 → scale = 480/1920 = 0.25
  const MINI_SCALE = 0.25;
  const sceneId = data.scene_id || 'scene_' + sceneNum;
  const elements = data.elements || [];
  const useCenteredCoords = isCenteredCoordinateScene(elements);

  let pendingImages = 0;
  function onImageLoaded() { pendingImages--; if (pendingImages <= 0) fc.renderAll(); }

  elements.forEach(el => {
    const type = el.type || 'image';
    let ex = (typeof el.x === 'number') ? el.x : 960;
    let ey = (typeof el.y === 'number') ? el.y : 540;
    if (useCenteredCoords) { ex += 960; ey += 540; }

    const common = {
      left: ex * MINI_SCALE,
      top: ey * MINI_SCALE,
      scaleX: (el.scale || 1.0) * MINI_SCALE,
      scaleY: (el.scale || 1.0) * MINI_SCALE,
      originX: 'center', originY: 'center',
      angle: el.angle || 0
    };

    if (type.startsWith('text_')) {
      let text = normalizeTextCase(el.text_content || el.phrase || 'TEXT');
      let fill = '#000', bg = null;
      if (type === 'text_red') fill = '#dc143c';
      else if (type === 'text_highlighted') { fill = '#fff'; bg = '#ffa500'; }
      fc.add(new fabric.Text(text, {
        ...common, fontSize: 40, fontFamily: getPreviewFontFamily(),
        fontWeight: isPreviewBold() ? 'bold' : 'normal', fill, backgroundColor: bg
      }));
    } else if (type === 'arrow' || type === 'image') {
      const fname = el.filename || (type === 'arrow' ? 'arrow.png' : '');
      if (fname) {
        pendingImages++;
        const sceneUrl  = '/image/' + sceneId + '/' + encodeURIComponent(fname);
        const globalUrl = '/image/' + encodeURIComponent(fname);
        const firstUrl  = _isDefaultAssetFilename(fname) ? globalUrl : sceneUrl;
        const secondUrl = _isDefaultAssetFilename(fname) ? sceneUrl  : globalUrl;
        fabric.Image.fromURL(firstUrl, function(img) {
          if (img && img.width > 1) {
            img.set(common); fc.add(img); onImageLoaded();
          } else {
            fabric.Image.fromURL(secondUrl, function(img2) {
              if (img2 && img2.width > 1) { img2.set(common); fc.add(img2); }
              else {
                fc.add(new fabric.Rect({ ...common, width: 1024, height: 1024, fill: '#e8e8e8', stroke: '#bbb', strokeWidth: 4 }));
              }
              onImageLoaded();
            }, { crossOrigin: 'anonymous' });
          }
        }, { crossOrigin: 'anonymous' });
      } else {
        fc.add(new fabric.Rect({ ...common, width: 1024, height: 1024, fill: type === 'arrow' ? 'rgba(244,67,54,0.2)' : '#e8e8e8', stroke: '#bbb', strokeWidth: 4 }));
      }
    } else {
      fc.add(new fabric.Rect({ ...common, width: 1024, height: 1024, fill: '#e8e8e8', stroke: '#bbb', strokeWidth: 4 }));
    }
  });

  fc.renderAll();
}

function selectSceneFromGrid(sceneNum, data) {
  closeGridView();
  document.getElementById('scene-num').value = sceneNum;
  renderDirectorScript(data);
  addLog2('log-ok', 'Loaded scene ' + sceneNum + ' from grid view');
}
</script>

<!-- ── GRID VIEW OVERLAY ── -->
<div class="grid-view" id="grid-view">
  <div class="grid-header">
    <span class="grid-title">⊞ Browse Scenes</span>
    <div class="sep" style="width:1px;height:26px;background:#444;"></div>
    <label>From scene</label>
    <input type="number" id="grid-from" value="1" min="1">
    <button class="btn btn-sm" onclick="gridLoadCustomRange()">Load</button>
    <div class="sep" style="width:1px;height:26px;background:#444;"></div>
    <button class="btn btn-sm" onclick="gridPrevSet()">&#8592; Prev 10</button>
    <button class="btn btn-sm" onclick="gridNextSet()">Next 10 &#8594;</button>
    <div style="flex:1;"></div>
    <button class="btn btn-sm" onclick="closeGridView()" style="background:#b71c1c;color:#ffcdd2;border-color:#c62828;">&#10005; Close</button>
  </div>
  <div class="grid-body">
    <div class="scene-grid" id="scene-grid">
      <div style="color:#666;padding:20px;grid-column:span 3;">Enter a scene number and click Load.</div>
    </div>
  </div>
</div>

</body>
</html>
"""


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/comfyui_config')
def comfyui_config():
    return jsonify({'default_runpod_url': DEFAULT_RUNPOD_URL})


@app.route('/access_urls')
def access_urls():
    lan_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = None

    lan_url = f"http://{lan_ip}:5555" if lan_ip else None
    public_url = os.environ.get("LAYOUT_TESTER_PUBLIC_URL", "").strip() or None
    return jsonify({
        "lan_url": lan_url,
        "public_url": public_url
    })


@app.route('/set_live_director_for_prompts', methods=['POST'])
def set_live_director_for_prompts():
    payload = request.get_json(silent=True) or {}
    scene_id = payload.get("scene_id")
    if scene_id and payload.get("elements"):
        LIVE_DIRECTOR_CACHE[scene_id] = payload
    return jsonify({'ok': True})


def _normalize_text(value):
    return " ".join(str(value or "").strip().split())


def _build_image_prompt_payload(scene_id, director_data):
    elements = []
    for el in director_data.get("elements", []):
        el_type = (el.get("type") or "").strip()
        filename = _normalize_text(el.get("filename"))

        # Only image assets need prompts; arrows are static assets.
        if el_type not in {"image"}:
            continue
        if not filename:
            continue

        phrase = _normalize_text(el.get("phrase"))
        description = _normalize_text(el.get("description"))

        if description:
            image_prompt = description
        elif phrase:
            image_prompt = (
                f"{phrase}. realistic, isolated subject, white background, "
                f"clean composition, no text, no watermark"
            )
        else:
            image_prompt = (
                "realistic isolated subject, white background, "
                "clean composition, no text, no watermark"
            )

        elements.append({
            "element_id": el.get("element_id", ""),
            "filename": filename,
            "phrase": phrase,
            "image_prompt": image_prompt
        })

    return {
        "scene_id": scene_id,
        "elements": elements
    }


def _is_default_asset_filename(filename):
    base = os.path.splitext((filename or "").strip().lower())[0]
    return base == "arrow" or base.startswith("host")


def _default_asset_path(filename):
    # Default reusable assets live in global assets/outputs (not scene subfolders).
    candidate = os.path.join(OUTPUTS_DIR, (filename or "").strip())
    if os.path.isfile(candidate):
        return candidate
    return None


def _queue_comfy_prompt(prompt_workflow, runpod_url):
    payload = {"prompt": prompt_workflow, "client_id": COMFY_CLIENT_ID}
    headers = {"Content-Type": "application/json"}
    res = requests.post(f"https://{runpod_url}/prompt", data=json.dumps(payload), headers=headers, timeout=60)
    res.raise_for_status()
    return res.json()


def _get_comfy_image(filename, subfolder, folder_type, runpod_url):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = requests.compat.urlencode(data)
    res = requests.get(f"https://{runpod_url}/view?{url_values}", timeout=120)
    res.raise_for_status()
    return res.content


def _generate_single_image_comfy(prompt_text, save_path, runpod_url):
    workflow = {
        "60": {"inputs": {"filename_prefix": "remote_gen", "images": ["83:8", 0]}, "class_type": "SaveImage"},
        "83:30": {"inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}, "class_type": "CLIPLoader"},
        "83:29": {"inputs": {"vae_name": "ae.safetensors"}, "class_type": "VAELoader"},
        "83:13": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptySD3LatentImage"},
        "83:33": {"inputs": {"conditioning": ["83:27", 0]}, "class_type": "ConditioningZeroOut"},
        "83:8": {"inputs": {"samples": ["83:3", 0], "vae": ["83:29", 0]}, "class_type": "VAEDecode"},
        "83:3": {
            "inputs": {
                "seed": random.randint(1, 10**15),
                "steps": 4,
                "cfg": 1,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1,
                "model": ["83:28", 0],
                "positive": ["83:27", 0],
                "negative": ["83:33", 0],
                "latent_image": ["83:13", 0]
            },
            "class_type": "KSampler"
        },
        "83:27": {"inputs": {"text": prompt_text, "clip": ["83:30", 0]}, "class_type": "CLIPTextEncode"},
        "83:28": {"inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"}
    }

    ws = None
    try:
        ws = websocket.WebSocket()
        ws_url = f"wss://{runpod_url}/ws?clientId={COMFY_CLIENT_ID}"
        ws.connect(ws_url, header={"Origin": f"https://{runpod_url}"})

        prompt_id = _queue_comfy_prompt(workflow, runpod_url)["prompt_id"]

        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message.get("type") == "executing":
                    data = message.get("data", {})
                    if data.get("node") is None and data.get("prompt_id") == prompt_id:
                        break

        history_res = requests.get(f"https://{runpod_url}/history/{prompt_id}", timeout=120)
        history_res.raise_for_status()
        history = history_res.json()[prompt_id]

        for node_id in history.get("outputs", {}):
            node_output = history["outputs"][node_id]
            if "images" in node_output:
                for image in node_output["images"]:
                    image_data = _get_comfy_image(image["filename"], image["subfolder"], image["type"], runpod_url)
                    with open(save_path, "wb") as f:
                        f.write(image_data)
                    return True
    except Exception:
        return False
    finally:
        try:
            if ws is not None:
                ws.close()
        except Exception:
            pass
    return False


@app.route('/run')
def run_pipeline():
    """SSE endpoint — runs all steps + generator and streams progress."""
    layout_num = request.args.get('layout', '1')
    scene_num = request.args.get('scene', '1')

    def generate():
        def send(type, msg):
            return f"data: {json.dumps({'type': type, 'msg': msg})}\n\n"

        pattern = os.path.join(BASE_DIR, f"layout_{layout_num}_step_*.py")
        step_files = sorted(glob.glob(pattern))

        if not step_files:
            yield send('fail', f'No step files found for layout {layout_num}')
            return

        generator_file = os.path.join(BASE_DIR, f"layout_{layout_num}_generator.py")
        has_generator = os.path.exists(generator_file)
        total = len(step_files) + (1 if has_generator else 0)
        yield send('step', f'Found {len(step_files)} steps + {"1 generator" if has_generator else "no generator"}')

        for i, step_file in enumerate(step_files):
            fname = os.path.basename(step_file)
            yield send('step', f'[{i+1}/{total}] Running {fname}...')
            t0 = time.time()
            try:
                result = subprocess.run([sys.executable, step_file, scene_num], capture_output=True, text=True, timeout=120, cwd=BASE_DIR)
                elapsed = time.time() - t0
                if result.stdout.strip():
                    for line in result.stdout.strip().split('\n'): yield send('stdout', line)
                if result.returncode == 0:
                    yield send('ok', f'{fname} completed'); yield send('time', f'{elapsed:.1f}s')
                else:
                    yield send('error', f'{fname} failed (exit {result.returncode})')
                    if result.stderr.strip():
                        for line in result.stderr.strip().split('\n')[-5:]: yield send('error', line)
                    yield send('fail', 'Pipeline aborted.'); return
            except subprocess.TimeoutExpired:
                yield send('error', f'{fname} timed out'); yield send('fail', 'Aborted.'); return
            except Exception as e:
                yield send('error', str(e)); yield send('fail', 'Aborted.'); return

        if has_generator:
            gname = os.path.basename(generator_file)
            yield send('step', f'[{total}/{total}] Running {gname}...')
            t0 = time.time()
            try:
                result = subprocess.run([sys.executable, generator_file, scene_num], capture_output=True, text=True, timeout=30, cwd=BASE_DIR)
                elapsed = time.time() - t0
                if result.stdout.strip():
                    for line in result.stdout.strip().split('\n'): yield send('stdout', line)
                if result.returncode == 0:
                    yield send('ok', f'{gname} completed'); yield send('time', f'{elapsed:.1f}s')
                else:
                    yield send('error', f'{gname} failed (exit {result.returncode})')
                    if result.stderr.strip():
                        for line in result.stderr.strip().split('\n')[-5:]: yield send('error', line)
                    yield send('fail', 'Generator failed.'); return
            except Exception as e:
                yield send('error', str(e)); yield send('fail', 'Generator failed.'); return

        yield send('done', f'Pipeline complete! Layout {layout_num}, Scene {scene_num}')

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/load_director')
def load_director():
    scene_num = request.args.get('scene', '1')
    scene_id = f"scene_{scene_num}"
    path = os.path.join(DIRECTOR_DIR, f'{scene_id}_director.json')
    if not os.path.exists(path):
        return jsonify({'error': f'File not found: {path}'})
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/load_director_batch')
def load_director_batch():
    try:
        start = int(request.args.get('start', 1))
        count = int(request.args.get('count', 10))
    except Exception:
        start, count = 1, 10
    count = max(1, min(count, 20))
    results = []
    for n in range(start, start + count):
        path = os.path.join(DIRECTOR_DIR, f'scene_{n}_director.json')
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                results.append({'scene_num': n, 'exists': True, 'data': data})
            except Exception:
                results.append({'scene_num': n, 'exists': False, 'data': None})
        else:
            results.append({'scene_num': n, 'exists': False, 'data': None})
    return jsonify({'scenes': results})


@app.route('/save_director', methods=['POST'])
def save_director():
    """Save the current director script JSON to disk."""
    try:
        data = request.get_json()
        scene_id = data.get('scene_id', 'scene_unknown')
        os.makedirs(DIRECTOR_DIR, exist_ok=True)
        path = os.path.join(DIRECTOR_DIR, f'{scene_id}_director.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return jsonify({'msg': f'Saved to assets/directorscript/{scene_id}_director.json'})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/load_image_prompts')
def load_image_prompts():
    scene_num = request.args.get('scene', '1')
    scene_id = f"scene_{scene_num}"
    path = os.path.join(IMAGE_PROMPTS_DIR, f'{scene_id}_image_prompts.json')
    if not os.path.exists(path):
        return jsonify({'error': f'File not found: assets/image_prompts/{scene_id}_image_prompts.json'})
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({
            'scene_id': scene_id,
            'path': f'assets/image_prompts/{scene_id}_image_prompts.json',
            'elements': data.get('elements', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/generate_image_prompts', methods=['POST'])
def generate_image_prompts():
    try:
        scene_num = request.args.get('scene', '1')
        scene_id = f"scene_{scene_num}"
        payload = request.get_json(silent=True) or {}

        # Prefer live editor JSON if provided; otherwise load from disk.
        director_data = payload if payload.get('elements') else None
        if not director_data:
            director_path = os.path.join(DIRECTOR_DIR, f'{scene_id}_director.json')
            if not os.path.exists(director_path):
                return jsonify({'error': f'Director script not found: assets/directorscript/{scene_id}_director.json'})
            with open(director_path, 'r', encoding='utf-8') as f:
                director_data = json.load(f)

        scene_id = director_data.get('scene_id', scene_id)
        director_path = os.path.join(DIRECTOR_DIR, f'{scene_id}_director.json')
        with open(director_path, 'w', encoding='utf-8') as f:
            json.dump(director_data, f, indent=2)

        # Primary path: call existing generate_prompts.py
        gen_script = os.path.join(BASE_DIR, 'generate_prompts.py')
        out_path = os.path.join(IMAGE_PROMPTS_DIR, f'{scene_id}_image_prompts.json')
        prompt_data = None
        script_error = None

        if os.path.exists(gen_script):
            scene_number = scene_id.replace("scene_", "")
            result = subprocess.run(
                [sys.executable, gen_script, scene_number],
                capture_output=True,
                text=True,
                cwd=BASE_DIR
            )
            if result.returncode != 0:
                script_error = (result.stderr or result.stdout or "").strip()

            if os.path.exists(out_path):
                with open(out_path, 'r', encoding='utf-8') as f:
                    prompt_data = json.load(f)

        # Fallback path: deterministic local prompt generation.
        if prompt_data is None:
            prompt_data = _build_image_prompt_payload(scene_id, director_data)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(prompt_data, f, indent=2)

        return jsonify({
            'msg': f'Generated image prompts for {scene_id}',
            'scene_id': scene_id,
            'path': f'assets/image_prompts/{scene_id}_image_prompts.json',
            'elements': prompt_data.get('elements', []),
            'warning': script_error
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/generate_image_prompts_stream')
def generate_image_prompts_stream():
    scene_num = request.args.get('scene', '1')
    scene_id = f"scene_{scene_num}"

    def stream():
        def send(type_, msg, extra=None):
            payload = {'type': type_, 'msg': msg}
            if extra:
                payload.update(extra)
            return f"data: {json.dumps(payload)}\n\n"

        try:
            director_data = LIVE_DIRECTOR_CACHE.pop(scene_id, None)
            director_path = os.path.join(DIRECTOR_DIR, f'{scene_id}_director.json')

            if director_data:
                yield send('info', 'Using live editor JSON.')
            else:
                if not os.path.exists(director_path):
                    yield send('error', f'Director script not found: assets/directorscript/{scene_id}_director.json')
                    yield send('done', 'Prompt generation failed.')
                    return
                with open(director_path, 'r', encoding='utf-8') as f:
                    director_data = json.load(f)
                yield send('info', 'Loaded director script from disk.')

            # Save latest director state first
            with open(director_path, 'w', encoding='utf-8') as f:
                json.dump(director_data, f, indent=2)
            yield send('info', f'Saved director: assets/directorscript/{scene_id}_director.json')

            gen_script = os.path.join(BASE_DIR, 'generate_prompts.py')
            out_path = os.path.join(IMAGE_PROMPTS_DIR, f'{scene_id}_image_prompts.json')
            prompt_data = None

            if os.path.exists(gen_script):
                yield send('info', 'Running generate_prompts.py ...')
                proc = subprocess.Popen(
                    [sys.executable, gen_script, str(scene_num)],
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                for line in iter(proc.stdout.readline, ''):
                    line = line.strip()
                    if line:
                        yield send('info', line)
                proc.wait()
                if proc.returncode != 0:
                    yield send('error', f'generate_prompts.py failed with exit code {proc.returncode}.')
                if os.path.exists(out_path):
                    with open(out_path, 'r', encoding='utf-8') as f:
                        prompt_data = json.load(f)

            if prompt_data is None:
                yield send('info', 'Using local fallback prompt generator.')
                prompt_data = _build_image_prompt_payload(scene_id, director_data)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(prompt_data, f, indent=2)

            count = len(prompt_data.get('elements', []))
            yield send('ok', f'Saved {count} prompts to assets/image_prompts/{scene_id}_image_prompts.json')
            yield send('done', f'Image prompt generation complete for {scene_id}.', {'count': count})
        except Exception as e:
            yield send('error', str(e))
            yield send('done', 'Prompt generation failed.')

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/generate_images_comfyui', methods=['POST'])
def generate_images_comfyui():
    try:
        scene_num = request.args.get('scene', '1')
        scene_id = f"scene_{scene_num}"
        payload = request.get_json(silent=True) or {}
        runpod_url = (payload.get("runpod_url") or DEFAULT_RUNPOD_URL).strip().replace("https://", "").replace("http://", "")

        prompts_path = os.path.join(IMAGE_PROMPTS_DIR, f"{scene_id}_image_prompts.json")
        if not os.path.exists(prompts_path):
            return jsonify({'error': f'Prompt file missing: assets/image_prompts/{scene_id}_image_prompts.json. Run Generate Img Prompts first.'})

        with open(prompts_path, 'r', encoding='utf-8') as f:
            prompt_data = json.load(f)

        prompt_elements = prompt_data.get("elements", [])
        if not prompt_elements:
            return jsonify({'error': f'No prompt elements found in assets/image_prompts/{scene_id}_image_prompts.json'})

        out_dir = os.path.join(OUTPUTS_DIR, scene_id)
        os.makedirs(out_dir, exist_ok=True)

        total = 0
        generated = 0
        failed = []
        skipped_defaults = []
        for el in prompt_elements:
            p_text = (el.get("image_prompt") or el.get("image-prompt") or "").strip()
            filename = (el.get("filename") or "").strip()
            if not p_text or not filename:
                continue
            if _is_default_asset_filename(filename) or _default_asset_path(filename):
                skipped_defaults.append(filename)
                continue
            total += 1
            save_path = os.path.join(out_dir, filename)
            ok = _generate_single_image_comfy(p_text, save_path, runpod_url)
            if ok:
                generated += 1
            else:
                failed.append(filename)

        msg = f"Image generation done for {scene_id} via {runpod_url}"
        return jsonify({
            'msg': msg,
            'scene_id': scene_id,
            'generated': generated,
            'total': total,
            'failed': failed,
            'skipped_defaults': skipped_defaults,
            'output_dir': f'assets/outputs/{scene_id}'
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/generate_images_comfyui_stream')
def generate_images_comfyui_stream():
    scene_num = request.args.get('scene', '1')
    scene_id = f"scene_{scene_num}"
    runpod_url = (request.args.get('runpod_url', DEFAULT_RUNPOD_URL) or DEFAULT_RUNPOD_URL).strip()
    runpod_url = runpod_url.replace("https://", "").replace("http://", "")

    def stream():
        def send(type_, msg, extra=None):
            payload = {'type': type_, 'msg': msg}
            if extra:
                payload.update(extra)
            return f"data: {json.dumps(payload)}\n\n"

        try:
            prompts_path = os.path.join(IMAGE_PROMPTS_DIR, f"{scene_id}_image_prompts.json")
            if not os.path.exists(prompts_path):
                yield send('error', f'Prompt file missing: assets/image_prompts/{scene_id}_image_prompts.json')
                yield send('done', 'Image generation failed.')
                return

            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompt_data = json.load(f)

            prompt_elements = prompt_data.get("elements", [])
            if not prompt_elements:
                yield send('error', f'No prompt elements found in assets/image_prompts/{scene_id}_image_prompts.json')
                yield send('done', 'Image generation failed.')
                return

            out_dir = os.path.join(OUTPUTS_DIR, scene_id)
            os.makedirs(out_dir, exist_ok=True)
            total = 0
            generated = 0
            failed = []
            skipped_defaults = []

            for el in prompt_elements:
                p_text = (el.get("image_prompt") or el.get("image-prompt") or "").strip()
                filename = (el.get("filename") or "").strip()
                if not p_text or not filename:
                    continue
                if _is_default_asset_filename(filename) or _default_asset_path(filename):
                    skipped_defaults.append(filename)
                    yield send('progress', f'Using default asset from outputs/{filename} (skip generation)')
                    continue
                total += 1
                yield send('progress', f'[{total}] Generating {filename} ...')
                save_path = os.path.join(out_dir, filename)
                ok = _generate_single_image_comfy(p_text, save_path, runpod_url)
                if ok:
                    generated += 1
                    yield send('ok', f'Generated {filename}')
                else:
                    failed.append(filename)
                    yield send('error', f'Failed {filename}')

            yield send(
                'done',
                f'Image generation complete for {scene_id} via {runpod_url}',
                {'generated': generated, 'total': total, 'failed': failed, 'skipped_defaults': skipped_defaults}
            )
        except Exception as e:
            yield send('error', str(e))
            yield send('done', 'Image generation failed.')

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/run_image_pipeline_stream')
def run_image_pipeline_stream():
    start_scene = request.args.get('start_scene', '1')
    runpod_url = (request.args.get('runpod_url', DEFAULT_RUNPOD_URL) or DEFAULT_RUNPOD_URL).strip()
    runpod_url = runpod_url.replace("https://", "").replace("http://", "")

    def stream():
        def send(type_, msg, extra=None):
            payload = {'type': type_, 'msg': msg}
            if extra:
                payload.update(extra)
            return f"data: {json.dumps(payload)}\n\n"

        try:
            try:
                start_num = int(start_scene)
            except Exception:
                start_num = 1

            director_files = glob.glob(os.path.join(DIRECTOR_DIR, 'scene_*_director.json'))
            scene_nums = []
            for p in director_files:
                name = os.path.basename(p)
                m = re.match(r'scene_(\d+)_director\.json$', name)
                if m:
                    n = int(m.group(1))
                    if n >= start_num:
                        scene_nums.append(n)
            scene_nums = sorted(scene_nums)

            if not scene_nums:
                yield send('done', f'No director scenes found from scene_{start_num}.')
                return

            total_scenes = len(scene_nums)
            done_scenes = 0

            for idx, scene_num in enumerate(scene_nums, start=1):
                scene_id = f"scene_{scene_num}"
                yield send('scene', f'[{idx}/{total_scenes}] Processing {scene_id} ...')

                director_data = LIVE_DIRECTOR_CACHE.pop(scene_id, None)
                director_path = os.path.join(DIRECTOR_DIR, f'{scene_id}_director.json')
                if director_data:
                    yield send('progress', f'{scene_id}: using live editor JSON')
                else:
                    if not os.path.exists(director_path):
                        yield send('error', f'{scene_id}: director file missing, skipping')
                        continue
                    with open(director_path, 'r', encoding='utf-8') as f:
                        director_data = json.load(f)

                with open(director_path, 'w', encoding='utf-8') as f:
                    json.dump(director_data, f, indent=2)

                # Step 1: generate prompts
                out_path = os.path.join(IMAGE_PROMPTS_DIR, f'{scene_id}_image_prompts.json')
                prompt_data = None
                gen_script = os.path.join(BASE_DIR, 'generate_prompts.py')
                if os.path.exists(gen_script):
                    yield send('progress', f'{scene_id}: running generate_prompts.py')
                    proc = subprocess.Popen(
                        [sys.executable, gen_script, str(scene_num)],
                        cwd=BASE_DIR,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    for line in iter(proc.stdout.readline, ''):
                        line = line.strip()
                        if line:
                            yield send('progress', f'{scene_id}: {line}')
                    proc.wait()
                    if proc.returncode != 0:
                        yield send('error', f'{scene_id}: generate_prompts.py failed (exit {proc.returncode})')
                    if os.path.exists(out_path):
                        with open(out_path, 'r', encoding='utf-8') as f:
                            prompt_data = json.load(f)

                if prompt_data is None:
                    yield send('progress', f'{scene_id}: using local fallback prompt generation')
                    prompt_data = _build_image_prompt_payload(scene_id, director_data)
                    with open(out_path, 'w', encoding='utf-8') as f:
                        json.dump(prompt_data, f, indent=2)

                prompt_elements = prompt_data.get("elements", [])
                yield send('ok', f'{scene_id}: prompts ready ({len(prompt_elements)})')

                # Step 2: generate images
                out_dir = os.path.join(OUTPUTS_DIR, scene_id)
                os.makedirs(out_dir, exist_ok=True)
                total = 0
                generated = 0
                skipped_defaults = 0
                for el in prompt_elements:
                    p_text = (el.get("image_prompt") or el.get("image-prompt") or "").strip()
                    filename = (el.get("filename") or "").strip()
                    if not p_text or not filename:
                        continue
                    if _is_default_asset_filename(filename) or _default_asset_path(filename):
                        skipped_defaults += 1
                        yield send('progress', f'{scene_id}: using default outputs/{filename} (skip generation)')
                        continue
                    total += 1
                    yield send('progress', f'{scene_id}: generating {filename} ({total})')
                    save_path = os.path.join(out_dir, filename)
                    ok = _generate_single_image_comfy(p_text, save_path, runpod_url)
                    if ok:
                        generated += 1
                        yield send('ok', f'{scene_id}: generated {filename}')
                    else:
                        yield send('error', f'{scene_id}: failed {filename}')

                done_scenes += 1
                yield send('ok', f'{scene_id}: image generation done {generated}/{total}, skipped defaults={skipped_defaults}')

            yield send('done', f'Image pipeline complete. Processed {done_scenes}/{total_scenes} scenes (start scene_{start_num}).')
        except Exception as e:
            yield send('error', str(e))
            yield send('done', 'Image pipeline failed.')

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/image/<path:filepath>')
def serve_image(filepath):
    """Serve image files from assets/outputs.
    URLs:
      /image/scene_1/arrow.png  → assets/outputs/scene_1/arrow.png
      /image/arrow.png          → assets/outputs/arrow.png
    """
    outputs_dir = OUTPUTS_DIR
    full_path = os.path.normpath(os.path.join(outputs_dir, filepath))
    # Security: ensure we don't escape the outputs directory
    if not full_path.startswith(os.path.normpath(outputs_dir)):
        return 'Forbidden', 403
    if not os.path.isfile(full_path):
        return 'Not found', 404
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename)


@app.route('/list_images')
def list_images():
    """List available images for a given scene."""
    scene = request.args.get('scene', '1')
    scene_id = f'scene_{scene}'
    outputs_dir = OUTPUTS_DIR
    scene_dir = os.path.join(outputs_dir, scene_id)
    images = []
    # Scene-specific images
    if os.path.isdir(scene_dir):
        for f in os.listdir(scene_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                images.append({'filename': f, 'path': f'{scene_id}/{f}', 'source': 'scene'})
    # Global images
    for f in os.listdir(outputs_dir):
        fp = os.path.join(outputs_dir, f)
        if os.path.isfile(fp) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
            images.append({'filename': f, 'path': f, 'source': 'global'})
    return jsonify(images)


if __name__ == '__main__':
    # Avoid non-ASCII output so this works in default Windows consoles (cp1252).
    print("\n  Layout Tester running at http://localhost:5555\n")
    app.run(host='0.0.0.0', port=5555, debug=False, threaded=True)
