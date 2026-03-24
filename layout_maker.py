"""
Layout Maker — Visual Layout Designer
======================================
Design new layouts visually with priority groups, scaling rules, and phrase allocation.
Run:  python layout_maker.py
Open: http://localhost:5557

Saves layouts to: layouts/layout_XX_definition.json
"""

import os, json
from datetime import date
from flask import Flask, render_template_string, request, jsonify, send_from_directory

app = Flask(__name__)
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
LAYOUTS_DIR = os.path.join(BASE_DIR, 'layouts')
ASSETS_DIR  = os.path.join(BASE_DIR, 'assets')
os.makedirs(LAYOUTS_DIR, exist_ok=True)

PORT = 5557

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/save_layout', methods=['POST'])
def save_layout():
    data = request.json
    num  = str(data.get('layout_number', 'new')).strip()
    path = os.path.join(LAYOUTS_DIR, f'layout_{num}_definition.json')
    data['saved'] = date.today().isoformat()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return jsonify({'ok': True, 'path': path})

@app.route('/load_layout/<num>')
def load_layout(num):
    path = os.path.join(LAYOUTS_DIR, f'layout_{num}_definition.json')
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    with open(path, encoding='utf-8') as f:
        return jsonify(json.load(f))

@app.route('/list_layouts')
def list_layouts():
    nums = []
    for fn in sorted(os.listdir(LAYOUTS_DIR)):
        if fn.startswith('layout_') and fn.endswith('_definition.json'):
            n = fn[7:fn.index('_definition')]
            try: nums.append(int(n))
            except: nums.append(n)
    nums.sort(key=lambda x: (isinstance(x, str), x))
    return jsonify(nums)

@app.route('/image/<path:filename>')
def serve_image(filename):
    return send_from_directory(ASSETS_DIR, filename)

# ─── HTML ─────────────────────────────────────────────────────────────────────

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Layout Maker</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.1/fabric.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #0f0f0f; color: #e0e0e0;
  height: 100vh; display: flex; flex-direction: column; overflow: hidden;
}

/* ── TOP BAR ── */
.top-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  padding: 6px 14px; border-bottom: 1px solid #333; flex-shrink: 0;
}
.logo { font-size: 15px; color: #fff; font-weight: 700; white-space: nowrap; }
.logo span { color: #ffa500; }
.sep { width: 1px; height: 24px; background: #444; flex-shrink: 0; }
.top-bar label { font-size: 11px; color: #888; }
.top-bar input[type=number], .top-bar input[type=text] {
  padding: 4px 7px; border-radius: 4px; border: 1px solid #444;
  background: #1a1a2e; color: #fff; font-size: 12px;
}
.top-bar input[type=number] { width: 55px; }
.top-bar input[type=text]   { width: 160px; }
.btn { padding: 4px 11px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.15s; white-space: nowrap; }
.btn-save    { background: #1b5e20; color: #8eff8e; border: 1px solid #2e7d32; }
.btn-save:hover { background: #256a2a; }
.btn-load    { background: #0d47a1; color: #90caf9; border: 1px solid #1565c0; }
.btn-load:hover { background: #1565c0; }
.btn-add     { background: #2a2a2a; color: #ccc; border: 1px solid #444; }
.btn-add:hover { background: #333; }
.btn-add-img  { background: #0d2a5e; color: #90caf9; border-color: #1a4a8a; }
.btn-add-text { background: #5e2a0d; color: #ffc8a0; border-color: #8a4a1a; }
.btn-add-arr  { background: #3a1a5e; color: #d0a0ff; border-color: #5a2a8a; }
.btn-danger  { background: #b71c1c; color: #ffcdd2; border: 1px solid #c62828; }
.btn-danger:hover { background: #c62828; }
.btn-sm { font-size: 11px; padding: 3px 9px; }
.tag { font-size: 10px; background: #222; color: #888; padding: 2px 7px; border-radius: 10px; border: 1px solid #333; white-space: nowrap; }

/* ── MAIN AREA ── */
.main-area {
  flex: 1; display: flex; overflow: hidden;
}

/* ── GROUPS SIDEBAR ── */
.groups-sidebar {
  width: 240px; background: #141414; border-right: 1px solid #222;
  display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0;
}
.groups-header {
  padding: 8px 10px; font-size: 11px; color: #ffa500; font-weight: 700;
  letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #222;
  display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;
}
.groups-list { flex: 1; overflow-y: auto; padding: 6px; }

.group-card {
  border-radius: 6px; border: 2px solid #333; margin-bottom: 8px;
  overflow: hidden; transition: border-color 0.15s;
}
.group-card.active-group { border-color: #ffa500; }
.group-head {
  display: flex; align-items: center; gap: 5px; padding: 5px 8px;
  cursor: pointer; user-select: none;
}
.group-priority-badge {
  font-size: 10px; font-weight: 700; color: #fff; padding: 1px 5px;
  border-radius: 3px; white-space: nowrap;
}
.group-name { font-size: 12px; font-weight: 600; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.group-name-input {
  font-size: 12px; font-weight: 600; flex: 1; background: transparent;
  border: none; border-bottom: 1px dashed #555; color: #fff; outline: none;
  min-width: 0;
}
.group-btns { display: flex; gap: 2px; flex-shrink: 0; }
.gbn {
  padding: 1px 5px; font-size: 10px; cursor: pointer; border: 1px solid #444;
  border-radius: 3px; background: #222; color: #aaa;
}
.gbn:hover { background: #333; color: #fff; }
.gbn-del { color: #ef5350; border-color: #5a1a1a; }
.gbn-del:hover { background: #5a1a1a; color: #ff8a80; }
.gbn-add { color: #90caf9; border-color: #1a3a5a; }
.gbn-add:hover { background: #1a3a5a; }

.group-meta {
  padding: 4px 8px; background: rgba(0,0,0,0.3);
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
}
.group-meta label { font-size: 9px; color: #666; }
.group-meta input[type=number] {
  width: 38px; padding: 1px 4px; font-size: 11px;
  background: #1a1a1a; border: 1px solid #444; border-radius: 3px; color: #fff;
}
.group-meta input[type=checkbox] { cursor: pointer; }
.atomic-label { font-size: 10px; color: #888; cursor: pointer; }

.group-elements { padding: 4px 6px 4px 14px; }
.elem-row {
  display: flex; align-items: center; gap: 5px; padding: 2px 4px;
  border-radius: 4px; cursor: pointer; font-size: 11px; color: #bbb;
  transition: background 0.1s;
}
.elem-row:hover { background: #222; }
.elem-row.active-elem { background: #2a2a3a; color: #fff; }
.elem-type-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.elem-id { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace; }
.elem-del { color: #555; cursor: pointer; font-size: 11px; padding: 0 3px; }
.elem-del:hover { color: #ef5350; }
.no-elems { font-size: 10px; color: #444; padding: 3px 0; font-style: italic; }

/* ── CANVAS AREA ── */
.canvas-section {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; background: #111; position: relative; overflow: hidden;
}
.canvas-wrap { border: 2px solid #333; border-radius: 4px; overflow: hidden; background: #fff; box-shadow: 0 4px 40px rgba(0,0,0,0.6); }
.canvas-info { position: absolute; top: 8px; left: 14px; font-size: 11px; color: #555; background: rgba(0,0,0,0.6); padding: 2px 8px; border-radius: 4px; }
.canvas-sel-info {
  position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
  background: rgba(0,0,0,0.85); color: #fff; padding: 4px 12px; border-radius: 5px;
  font-size: 11px; font-family: monospace; display: none; z-index: 50; white-space: nowrap;
}
.canvas-sel-info.visible { display: block; }

/* ── PROPERTIES PANEL ── */
.props-sidebar {
  width: 290px; background: #141414; border-left: 1px solid #222;
  display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0;
}
.props-header {
  padding: 8px 10px; font-size: 11px; color: #ffa500; font-weight: 700;
  letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #222;
  flex-shrink: 0;
}
.props-body { flex: 1; overflow-y: auto; padding: 10px; }
.props-section { margin-bottom: 12px; }
.props-section-title { font-size: 10px; color: #555; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; border-bottom: 1px solid #222; padding-bottom: 3px; }
.prop-row { margin-bottom: 6px; }
.prop-row label { font-size: 10px; color: #777; display: block; margin-bottom: 2px; }
.prop-row input, .prop-row select, .prop-row textarea {
  width: 100%; padding: 3px 6px; border-radius: 4px; border: 1px solid #444;
  background: #1a1a1a; color: #fff; font-size: 12px;
}
.prop-row input[readonly] { color: #555; }
.prop-row textarea { height: 50px; resize: none; font-size: 11px; font-family: monospace; }
.prop-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }

/* Scale advisor */
.scale-advisor {
  background: #0a0a0a; border: 1px solid #333; border-radius: 4px;
  padding: 7px 8px; font-size: 11px; font-family: monospace; line-height: 1.6;
}
.sa-fits   { color: #66bb6a; }
.sa-warn   { color: #ffa500; }
.sa-over   { color: #ef5350; }
.sa-info   { color: #888; }
.sa-rec    { color: #90caf9; font-weight: 700; }
.no-select { color: #444; font-style: italic; font-size: 12px; padding: 20px 10px; text-align: center; }

/* ── BOTTOM JSON ── */
.bottom-panel { flex-shrink: 0; background: #141414; border-top: 1px solid #2a2a2a; transition: height 0.2s; }
.bottom-panel.collapsed { height: 30px; }
.bottom-panel.expanded  { height: 200px; }
.bottom-head { height: 30px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; cursor: pointer; }
.bottom-head:hover { background: #1a1a1a; }
.bottom-head .title { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
.bottom-body { height: calc(100% - 30px); display: flex; gap: 6px; padding: 6px; }
.json-out { flex: 1; background: #0a0a0a; color: #4fc3f7; border: 1px solid #333; border-radius: 4px; font-family: monospace; font-size: 10px; padding: 6px; resize: none; }
.bottom-actions { display: flex; flex-direction: column; gap: 4px; }

/* Misc */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #111; }
::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
</style>
</head>
<body>

<!-- ── TOP BAR ── -->
<div class="top-bar">
  <div class="logo">🎨 Layout <span>Maker</span></div>
  <div class="sep"></div>
  <label>Layout #</label>
  <input type="number" id="layout-num" value="40" min="1" style="width:55px;">
  <label>Name</label>
  <input type="text" id="layout-name" value="New Layout" style="width:160px;">
  <div class="sep"></div>
  <button class="btn btn-save" onclick="saveLayout()">💾 Save</button>
  <button class="btn btn-load" onclick="promptLoadLayout()">📂 Load</button>
  <div class="sep"></div>
  <button class="btn btn-add btn-add-img"  onclick="addElement('image')">+ Image</button>
  <button class="btn btn-add btn-add-text" onclick="addElement('text_black')">+ Text ▾</button>
  <select id="text-type-pick" style="padding:3px;background:#1a1a1a;border:1px solid #444;color:#ffc8a0;font-size:11px;border-radius:4px;" onchange="addElement(this.value);this.value='text_black'">
    <option value="text_black">text_black</option>
    <option value="text_red">text_red</option>
    <option value="text_highlighted">text_highlighted</option>
  </select>
  <button class="btn btn-add btn-add-arr"  onclick="addElement('arrow')">+ Arrow</button>
  <div class="sep"></div>
  <button class="btn btn-add btn-sm" onclick="moveLayer('up')">▲ Front</button>
  <button class="btn btn-add btn-sm" onclick="moveLayer('down')">▼ Back</button>
  <button class="btn btn-danger btn-sm" onclick="deleteSelected()">🗑 Delete</button>
  <div class="sep"></div>
  <label><input type="checkbox" id="show-grid" onchange="toggleGrid()"> Grid</label>
  <label style="margin-left:6px;"><input type="checkbox" id="snap-grid" checked> Snap</label>
  <div class="sep"></div>
  <label>Tiling?</label>
  <input type="checkbox" id="tiling-check" checked style="cursor:pointer;">
  <label style="margin-left:4px;">Coverage?</label>
  <input type="checkbox" id="coverage-check" checked style="cursor:pointer;">
  <div class="sep"></div>
  <button class="btn btn-add btn-sm" onclick="clearAll()" style="color:#ef5350;">✕ Clear All</button>
</div>

<!-- ── MAIN AREA ── -->
<div class="main-area">

  <!-- Groups Sidebar -->
  <div class="groups-sidebar">
    <div class="groups-header">
      <span>Priority Groups</span>
      <button class="btn btn-add btn-sm" onclick="addGroup()" style="font-size:12px;padding:2px 7px;">+ Group</button>
    </div>
    <div class="groups-list" id="groups-list">
      <div style="color:#444;font-size:11px;padding:12px;text-align:center;">Add a group to start</div>
    </div>
  </div>

  <!-- Canvas -->
  <div class="canvas-section">
    <div class="canvas-info">960 × 540 (1920×1080 ÷ 2)</div>
    <div class="canvas-wrap">
      <canvas id="maker-canvas" width="960" height="540"></canvas>
    </div>
    <div class="canvas-sel-info" id="sel-info"></div>
  </div>

  <!-- Properties Sidebar -->
  <div class="props-sidebar">
    <div class="props-header">Element Properties</div>
    <div class="props-body" id="props-body">
      <div class="no-select">Select an element on canvas<br>or click one in the sidebar</div>
    </div>
  </div>

</div>

<!-- ── BOTTOM JSON ── -->
<div class="bottom-panel expanded" id="bottom-panel">
  <div class="bottom-head" onclick="toggleBottom()">
    <span class="title">▼ Layout JSON (saved output)</span>
    <span id="bottom-tog">▼</span>
  </div>
  <div class="bottom-body">
    <textarea class="json-out" id="json-out" readonly></textarea>
    <div class="bottom-actions">
      <button class="btn btn-add btn-sm" onclick="copyJSON()">📋 Copy</button>
      <button class="btn btn-save btn-sm" onclick="saveLayout()">💾 Save</button>
    </div>
  </div>
</div>

<script>
// ══════════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ══════════════════════════════════════════════════════════════════════════════
const W = 960, H = 540;  // canvas px (= scene / 2)
const SCENE_W = 1920, SCENE_H = 1080;

const GROUP_COLORS = [
  '#1565c0','#2e7d32','#c66800','#6a1b9a',
  '#00838f','#ad1457','#4e342e','#37474f',
  '#e65100','#1a5276'
];

const TYPE_COLORS = {
  image: '#1a3a6a',
  arrow: '#5a1a5a',
  text_black: '#1a3a1a',
  text_red: '#5a1a1a',
  text_highlighted: '#5a3a00',
};

const TYPE_DOT_COLORS = {
  image: '#90caf9', arrow: '#d0a0ff',
  text_black: '#b0d4a0', text_red: '#ff8a80', text_highlighted: '#ffcc80',
};

const ROLE_OPTIONS = [
  'heading','punchline','label','sublabel','image','arrow',
  'title','subtitle','callout','badge','step_text',
];
const PHRASE_ALLOC_OPTIONS = [
  'proportional','first_sentence','last_sentence','callout','full',
  'half_first','half_second','arrow_transition',
];

// ══════════════════════════════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════════════════════════════
let layoutData = makeEmptyLayout();
let nextGroupNum  = 1;
let elemCounters  = {};   // type -> count for auto-IDs (unused now, kept for compat)
let activeGroupId = null; // which group newly added elements go to
let selectedObj   = null;
let dragElemId    = null; // element being dragged between groups
let dragFromGroup = null;

function makeEmptyLayout() {
  return {
    layout_number: 40,
    layout_name: 'New Layout',
    description: '',
    canvas: { w: SCENE_W, h: SCENE_H },
    scaling_defaults: {
      char_px_caps: 30,
      char_px_mixed: 20,
      line_height: 110,
      canvas_margin: 40,
      min_scale: 1.0,
    },
    phrase_rules: {
      tiling: true,
      coverage_required: true,
      notes: '',
    },
    priority_groups: [],
  };
}

// ══════════════════════════════════════════════════════════════════════════════
// FABRIC CANVAS
// ══════════════════════════════════════════════════════════════════════════════
const canvas = new fabric.Canvas('maker-canvas', {
  backgroundColor: '#ffffff',
  selection: true,
  snapAngle: 5,
});

// Grid lines (non-interactive)
let gridLines = [];

function toggleGrid() {
  gridLines.forEach(l => canvas.remove(l));
  gridLines = [];
  if (!document.getElementById('show-grid').checked) { canvas.renderAll(); return; }
  const step = 60;  // 120 scene px
  for (let x = 0; x <= W; x += step) {
    let l = new fabric.Line([x,0,x,H], { stroke:'#ddd', strokeWidth:0.5, selectable:false, evented:false, excludeFromExport:true });
    gridLines.push(l); canvas.add(l);
  }
  for (let y = 0; y <= H; y += step) {
    let l = new fabric.Line([0,y,W,y], { stroke:'#ddd', strokeWidth:0.5, selectable:false, evented:false, excludeFromExport:true });
    gridLines.push(l); canvas.add(l);
  }
  // Midlines
  let mx = new fabric.Line([W/2,0,W/2,H], { stroke:'#f0a0a0', strokeWidth:0.5, selectable:false, evented:false, excludeFromExport:true });
  let my = new fabric.Line([0,H/2,W,H/2], { stroke:'#f0a0a0', strokeWidth:0.5, selectable:false, evented:false, excludeFromExport:true });
  gridLines.push(mx, my); canvas.add(mx); canvas.add(my);
  gridLines.forEach(l => canvas.sendToBack(l));
  canvas.renderAll();
}

// Snap to grid
canvas.on('object:moving', function(e) {
  if (!document.getElementById('snap-grid').checked) return;
  let obj = e.target;
  let snap = 10;  // 20 scene px
  obj.set({ left: Math.round(obj.left / snap) * snap, top: Math.round(obj.top / snap) * snap });
});

canvas.on('object:modified', (e) => { syncFromCanvas(e.target); syncJSON(); });
canvas.on('selection:created', (e) => onCanvasSelect(e));
canvas.on('selection:updated', (e) => onCanvasSelect(e));
canvas.on('selection:cleared', () => {
  selectedObj = null;
  document.getElementById('sel-info').classList.remove('visible');
  renderPropsPanel(null);
  renderGroupsPanel();
});

function onCanvasSelect(e) {
  let obj = e.selected ? e.selected[0] : (e.target || canvas.getActiveObject());
  if (!obj || !obj._elemDef) return;
  selectedObj = obj;
  syncFromCanvas(obj);
  let info = document.getElementById('sel-info');
  let el = obj._elemDef;
  info.textContent = `${el.element_id}  |  x:${el.x} y:${el.y}  |  scale:${el.scale}  |  angle:${el.angle}°  |  [${obj._groupId}]`;
  info.classList.add('visible');
  renderPropsPanel(obj);
  renderGroupsPanel();
}

function syncFromCanvas(obj) {
  if (!obj || !obj._elemDef) return;
  let el = obj._elemDef;
  el.x     = Math.round(obj.left  * 2);
  el.y     = Math.round(obj.top   * 2);
  el.scale = parseFloat((obj.scaleX * 2).toFixed(3));
  el.angle = Math.round(obj.angle);
}

// After-render: draw priority badges
canvas.on('after:render', function() {
  let ctx = canvas.getContext();
  canvas.getObjects().forEach(obj => {
    if (!obj._elemDef || !obj._groupId) return;
    let g = layoutData.priority_groups.find(g => g.group_id === obj._groupId);
    if (!g) return;
    let bx = obj.left + (obj.getScaledWidth() / 2);
    let by = obj.top  - (obj.getScaledHeight() / 2) - 2;
    ctx.save();
    ctx.fillStyle    = g.color || '#555';
    ctx.font         = 'bold 9px monospace';
    ctx.textAlign    = 'right';
    ctx.textBaseline = 'bottom';
    ctx.globalAlpha  = 0.9;
    let label = `P${g.priority}`;
    let tw = ctx.measureText(label).width;
    ctx.fillRect(bx - tw - 4, by - 10, tw + 6, 11);
    ctx.fillStyle = '#fff';
    ctx.fillText(label, bx - 1, by);
    ctx.restore();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// ADD / DELETE ELEMENTS
// ══════════════════════════════════════════════════════════════════════════════
function addElement(type) {
  // Auto-assign to activeGroupId; create new group if none
  if (!activeGroupId || !layoutData.priority_groups.find(g => g.group_id === activeGroupId)) {
    addGroup(true);
  }
  let g = layoutData.priority_groups.find(g => g.group_id === activeGroupId);
  if (!g) return;

  // Auto-ID: find lowest unused number for this base type
  let base = type === 'image' ? 'img' : type === 'arrow' ? 'arrow' : 'text';
  let usedNums = new Set(
    layoutData.priority_groups.flatMap(g => g.elements)
      .filter(e => e.element_id.startsWith(base + '_'))
      .map(e => parseInt(e.element_id.slice(base.length + 1)))
      .filter(n => !isNaN(n))
  );
  let n = 1; while (usedNums.has(n)) n++;
  let eid = `${base}_${n}`;

  let cx = W / 2, cy = H / 2;

  let elemDef = {
    element_id: eid,
    type: type,
    x: cx * 2, y: cy * 2,     // scene coords
    scale: type === 'image' ? 0.3 : type === 'arrow' ? 0.15 : 1.4,
    angle: 0,
    animation: type === 'arrow' ? 'none' : 'pop',
    property: '',
    role: type === 'image' ? 'image' : type === 'arrow' ? 'arrow' : 'label',
    phrase_allocation: type === 'image' ? 'proportional' : type === 'arrow' ? 'arrow_transition' : 'proportional',
    safe_width: 1800,
    char_px: type === 'text_highlighted' ? 30 : 20,
    notes: '',
  };

  g.elements.push(elemDef);

  // Build fabric object
  let obj = buildFabricObj(elemDef, g);
  canvas.add(obj);
  canvas.setActiveObject(obj);
  canvas.renderAll();

  activeGroupId = g.group_id;
  renderGroupsPanel();
  syncJSON();
}

function buildFabricObj(elemDef, group) {
  let cx = elemDef.x / 2;
  let cy = elemDef.y / 2;
  let sc = elemDef.scale / 2;
  let ang = elemDef.angle || 0;
  let gc  = group ? group.color : '#555';

  let common = {
    left: cx, top: cy,
    scaleX: sc, scaleY: sc,
    angle: ang,
    originX: 'center', originY: 'center',
    selectable: true, evented: true,
    borderColor: gc, cornerColor: gc,
    cornerSize: 8, transparentCorners: false, cornerStyle: 'circle',
  };

  let obj;
  if (elemDef.type.startsWith('text_')) {
    let fill = '#000';
    let bg   = null;
    if (elemDef.type === 'text_red')         fill = '#dc143c';
    if (elemDef.type === 'text_highlighted') { fill = '#fff'; bg = '#ffa500'; }
    obj = new fabric.IText(elemDef.element_id, {
      ...common,
      fontSize: 40,
      fontFamily: 'Comic Sans MS, Comic Sans, cursive',
      fill, backgroundColor: bg,
    });
  } else if (elemDef.type === 'arrow') {
    let items = [
      new fabric.Rect({ width: 1024, height: 1024, fill: 'rgba(160,0,200,0.18)', stroke: gc, strokeWidth: 8, originX: 'center', originY: 'center' }),
      new fabric.Text(`\u2192 ${elemDef.element_id}`, { fontSize: 56, fontFamily: 'monospace', fill: '#cc44ff', originX: 'center', originY: 'center', textAlign: 'center' }),
    ];
    obj = new fabric.Group(items, { ...common, width: 1024, height: 1024 });
  } else {
    // image placeholder
    let items = [
      new fabric.Rect({ width: 1024, height: 1024, fill: 'rgba(0,80,200,0.12)', stroke: gc, strokeWidth: 8, rx: 12, ry: 12, originX: 'center', originY: 'center' }),
      new fabric.Text(`\uD83D\uDDBC ${elemDef.element_id}`, { fontSize: 56, fontFamily: 'Segoe UI', fill: '#4a90d9', originX: 'center', originY: 'center', textAlign: 'center' }),
    ];
    obj = new fabric.Group(items, { ...common, width: 1024, height: 1024 });
  }

  obj._elemDef  = elemDef;
  obj._groupId  = group ? group.group_id : null;
  return obj;
}

function deleteSelected() {
  let obj = canvas.getActiveObject();
  if (!obj || !obj._elemDef) return;
  let eid = obj._elemDef.element_id;
  canvas.remove(obj);
  // Remove from layoutData
  for (let g of layoutData.priority_groups) {
    g.elements = g.elements.filter(e => e.element_id !== eid);
  }
  selectedObj = null;
  renderGroupsPanel();
  renderPropsPanel(null);
  syncJSON();
  canvas.renderAll();
}

function moveLayer(dir) {
  let obj = canvas.getActiveObject();
  if (!obj) return;
  if (dir === 'up')   canvas.bringForward(obj);
  else                canvas.sendBackwards(obj);
  canvas.renderAll();
}

// ══════════════════════════════════════════════════════════════════════════════
// GROUPS MANAGEMENT
// ══════════════════════════════════════════════════════════════════════════════
function addGroup(activate = true) {
  let idx = layoutData.priority_groups.length;
  let g = {
    group_id: 'G' + nextGroupNum,
    label: 'Group ' + nextGroupNum,
    priority: idx + 1,
    min_tokens: 2,
    atomic: false,
    color: GROUP_COLORS[idx % GROUP_COLORS.length],
    notes: '',
    elements: [],
  };
  nextGroupNum++;
  layoutData.priority_groups.push(g);
  if (activate) activeGroupId = g.group_id;
  renderGroupsPanel();
  syncJSON();
  return g;
}

function deleteGroup(groupId) {
  let g = layoutData.priority_groups.find(g => g.group_id === groupId);
  if (!g) return;
  // Remove all canvas objects in this group
  canvas.getObjects().filter(o => o._groupId === groupId).forEach(o => {
    canvas.remove(o);
  });
  layoutData.priority_groups = layoutData.priority_groups.filter(g => g.group_id !== groupId);
  // Re-number priorities
  layoutData.priority_groups.forEach((g, i) => g.priority = i + 1);
  if (activeGroupId === groupId) activeGroupId = layoutData.priority_groups[0]?.group_id || null;
  renderGroupsPanel();
  syncJSON();
  canvas.renderAll();
}

function moveGroup(groupId, dir) {
  let arr = layoutData.priority_groups;
  let idx = arr.findIndex(g => g.group_id === groupId);
  if (idx < 0) return;
  let swap = idx + (dir === 'up' ? -1 : 1);
  if (swap < 0 || swap >= arr.length) return;
  [arr[idx], arr[swap]] = [arr[swap], arr[idx]];
  arr.forEach((g, i) => g.priority = i + 1);
  renderGroupsPanel();
  syncJSON();
}

function addElementToGroup(groupId) {
  activeGroupId = groupId;
  // Show a quick type picker or default to image
  let type = prompt('Element type:\nimage / text_black / text_red / text_highlighted / arrow', 'image');
  if (!type) return;
  type = type.trim().toLowerCase();
  if (!['image','text_black','text_red','text_highlighted','arrow'].includes(type)) {
    type = 'image';
  }
  addElement(type);
}

function removeElemFromGroup(groupId, elemId) {
  let g = layoutData.priority_groups.find(g => g.group_id === groupId);
  if (!g) return;
  g.elements = g.elements.filter(e => e.element_id !== elemId);
  // Remove from canvas
  canvas.getObjects().filter(o => o._elemDef && o._elemDef.element_id === elemId).forEach(o => {
    canvas.remove(o);
  });
  renderGroupsPanel();
  syncJSON();
  canvas.renderAll();
}

function selectElemOnCanvas(elemId) {
  let obj = canvas.getObjects().find(o => o._elemDef && o._elemDef.element_id === elemId);
  if (!obj) return;
  canvas.setActiveObject(obj);
  canvas.renderAll();
  onCanvasSelect({ selected: [obj] });
}

// ══════════════════════════════════════════════════════════════════════════════
// RENDER GROUPS PANEL
// ══════════════════════════════════════════════════════════════════════════════
function renderGroupsPanel() {
  let container = document.getElementById('groups-list');
  if (layoutData.priority_groups.length === 0) {
    container.innerHTML = '<div style="color:#444;font-size:11px;padding:12px;text-align:center;">No groups yet — click + Group</div>';
    return;
  }

  let selEid = selectedObj?._elemDef?.element_id;

  let html = '';
  for (let g of layoutData.priority_groups) {
    let isActive = g.group_id === activeGroupId;
    let selElem  = g.elements.find(e => e.element_id === selEid);
    html += `
    <div class="group-card${isActive ? ' active-group' : ''}" id="gc-${g.group_id}" style="border-color:${isActive ? '#ffa500' : g.color}44;">
      <div class="group-head" onclick="setActiveGroup('${g.group_id}')">
        <span class="group-priority-badge" style="background:${g.color}">P${g.priority}</span>
        <input class="group-name-input" value="${esc(g.label)}"
          onclick="event.stopPropagation()"
          oninput="updateGroupLabel('${g.group_id}',this.value)">
        <div class="group-btns">
          <span class="gbn" onclick="event.stopPropagation();moveGroup('${g.group_id}','up')" title="Move up">↑</span>
          <span class="gbn" onclick="event.stopPropagation();moveGroup('${g.group_id}','down')" title="Move down">↓</span>
          <span class="gbn gbn-add" onclick="event.stopPropagation();addElementToGroup('${g.group_id}')" title="Add element">+</span>
          <span class="gbn gbn-del" onclick="event.stopPropagation();deleteGroup('${g.group_id}')" title="Delete group">✕</span>
        </div>
      </div>
      <div class="group-meta">
        <label>min tokens</label>
        <input type="number" min="1" max="20" value="${g.min_tokens}"
          onchange="updateGroupProp('${g.group_id}','min_tokens',+this.value)"
          onclick="event.stopPropagation()" title="Minimum tokens needed for this group to appear">
        <label class="atomic-label" title="Atomic: all elements appear together or not at all">
          <input type="checkbox" ${g.atomic ? 'checked' : ''}
            onchange="updateGroupProp('${g.group_id}','atomic',this.checked)"
            onclick="event.stopPropagation()">
          atomic
        </label>
      </div>
      <div class="group-elements" id="ge-${g.group_id}"
           ondragover="event.preventDefault();document.getElementById('ge-${g.group_id}').style.background='rgba(255,165,0,0.1)'"
           ondragleave="document.getElementById('ge-${g.group_id}').style.background=''"
           ondrop="onDropToGroup(event,'${g.group_id}')">`;

    if (g.elements.length === 0) {
      html += '<div class="no-elems" style="pointer-events:none;">drop here or click + to add</div>';
    } else {
      for (let el of g.elements) {
        let dot = TYPE_DOT_COLORS[el.type] || '#888';
        html += `
        <div class="elem-row${el.element_id === selEid ? ' active-elem' : ''}"
             draggable="true"
             ondragstart="onDragElem(event,'${g.group_id}','${el.element_id}')"
             onclick="selectElemOnCanvas('${el.element_id}')">
          <span style="cursor:grab;color:#555;font-size:12px;margin-right:2px;">⠿</span>
          <span class="elem-type-dot" style="background:${dot}"></span>
          <span class="elem-id">${esc(el.element_id)}</span>
          <span class="elem-del" onclick="event.stopPropagation();removeElemFromGroup('${g.group_id}','${el.element_id}')" title="Remove">✕</span>
        </div>`;
      }
    }

    html += `</div></div>`;
  }
  container.innerHTML = html;
}

function setActiveGroup(groupId) {
  activeGroupId = groupId;
  renderGroupsPanel();
}

function onDragElem(event, fromGroupId, elemId) {
  dragElemId    = elemId;
  dragFromGroup = fromGroupId;
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', elemId);
}

function onDropToGroup(event, toGroupId) {
  event.preventDefault();
  document.getElementById('ge-' + toGroupId).style.background = '';
  if (!dragElemId || dragFromGroup === toGroupId) { dragElemId = null; dragFromGroup = null; return; }

  let fromG = layoutData.priority_groups.find(g => g.group_id === dragFromGroup);
  let toG   = layoutData.priority_groups.find(g => g.group_id === toGroupId);
  if (!fromG || !toG) return;

  let elemDef = fromG.elements.find(e => e.element_id === dragElemId);
  if (!elemDef) return;

  // Move element definition between groups
  fromG.elements = fromG.elements.filter(e => e.element_id !== dragElemId);
  toG.elements.push(elemDef);

  // Update canvas object's groupId and border color
  let obj = canvas.getObjects().find(o => o._elemDef && o._elemDef.element_id === dragElemId);
  if (obj) {
    obj._groupId = toGroupId;
    obj.set({ borderColor: toG.color, cornerColor: toG.color });
    canvas.renderAll();
  }

  dragElemId = null; dragFromGroup = null;
  renderGroupsPanel();
  syncJSON();
}

function updateGroupLabel(groupId, val) {
  let g = layoutData.priority_groups.find(g => g.group_id === groupId);
  if (g) { g.label = val; syncJSON(); }
}

function updateGroupProp(groupId, key, val) {
  let g = layoutData.priority_groups.find(g => g.group_id === groupId);
  if (g) { g[key] = val; syncJSON(); }
}

// ══════════════════════════════════════════════════════════════════════════════
// PROPERTIES PANEL
// ══════════════════════════════════════════════════════════════════════════════
function renderPropsPanel(obj) {
  let body = document.getElementById('props-body');
  if (!obj || !obj._elemDef) {
    body.innerHTML = '<div class="no-select">Select an element on canvas<br>or click one in the sidebar</div>';
    return;
  }
  let el = obj._elemDef;
  let g  = layoutData.priority_groups.find(g => g.group_id === obj._groupId);

  let groupOptions = layoutData.priority_groups.map(gr =>
    `<option value="${gr.group_id}" ${gr.group_id === obj._groupId ? 'selected' : ''}>${gr.label} (P${gr.priority})</option>`
  ).join('');

  let roleOptions = ROLE_OPTIONS.map(r =>
    `<option value="${r}" ${r === el.role ? 'selected' : ''}>${r}</option>`
  ).join('');

  let allocOptions = PHRASE_ALLOC_OPTIONS.map(p =>
    `<option value="${p}" ${p === el.phrase_allocation ? 'selected' : ''}>${p}</option>`
  ).join('');

  let animOptions = ['pop','slide_in_left','slide_in_right','slide_in_up','typing','none'].map(a =>
    `<option value="${a}" ${a === el.animation ? 'selected' : ''}>${a}</option>`
  ).join('');

  let typeOptions = ['image','arrow','text_black','text_red','text_highlighted'].map(t =>
    `<option value="${t}" ${t === el.type ? 'selected' : ''}>${t}</option>`
  ).join('');

  let isText = el.type.startsWith('text_');

  body.innerHTML = `
  <div class="props-section">
    <div class="props-section-title">Identity</div>
    <div class="prop-row">
      <label>Element ID</label>
      <input type="text" value="${esc(el.element_id)}" oninput="applyProp('element_id',this.value)">
    </div>
    <div class="prop-row">
      <label>Type</label>
      <select onchange="applyProp('type',this.value)">${typeOptions}</select>
    </div>
    <div class="prop-row">
      <label>Priority Group</label>
      <select onchange="reassignGroup(this.value)">${groupOptions}</select>
    </div>
    <div class="prop-row">
      <label>Role</label>
      <select onchange="applyProp('role',this.value)">${roleOptions}</select>
    </div>
  </div>

  <div class="props-section">
    <div class="props-section-title">Geometry</div>
    <div class="prop-2col">
      <div class="prop-row">
        <label>X (scene)</label>
        <input type="number" value="${el.x}" oninput="applyCoord('x',+this.value)">
      </div>
      <div class="prop-row">
        <label>Y (scene)</label>
        <input type="number" value="${el.y}" oninput="applyCoord('y',+this.value)">
      </div>
    </div>
    <div class="prop-2col">
      <div class="prop-row">
        <label>Scale</label>
        <input type="number" step="0.01" value="${el.scale}" oninput="applyCoord('scale',+this.value)">
      </div>
      <div class="prop-row">
        <label>Angle °</label>
        <input type="number" value="${el.angle}" oninput="applyCoord('angle',+this.value)">
      </div>
    </div>
  </div>

  <div class="props-section">
    <div class="props-section-title">Phrase Allocation</div>
    <div class="prop-row">
      <label>Phrase Allocation</label>
      <select onchange="applyProp('phrase_allocation',this.value)">${allocOptions}</select>
    </div>
    ${isText ? `
    <div class="prop-row">
      <label>Safe Width (scene px)</label>
      <input type="number" value="${el.safe_width}" oninput="applyProp('safe_width',+this.value);updateScaleAdvisor()">
    </div>
    <div class="prop-row">
      <label>Char PX (30=caps, 20=mixed)</label>
      <input type="number" value="${el.char_px}" oninput="applyProp('char_px',+this.value);updateScaleAdvisor()">
    </div>` : ''}
  </div>

  <div class="props-section">
    <div class="props-section-title">Display</div>
    <div class="prop-row">
      <label>Animation</label>
      <select onchange="applyProp('animation',this.value)">${animOptions}</select>
    </div>
    <div class="prop-row">
      <label>Property</label>
      <select onchange="applyProp('property',this.value)">
        <option value="">none</option>
        <option value="shadow" ${el.property==='shadow'?'selected':''}>shadow</option>
      </select>
    </div>
  </div>

  ${isText ? `
  <div class="props-section">
    <div class="props-section-title">Scale Advisor</div>
    <div class="scale-advisor" id="scale-advisor">
      ${buildScaleAdvisor(el)}
    </div>
    <div style="margin-top:5px;">
      <button class="btn btn-add btn-sm" style="width:100%;margin-top:4px;" onclick="applyRecommendedScale()">
        ▶ Apply Recommended Scale
      </button>
    </div>
  </div>` : ''}

  <div class="props-section">
    <div class="props-section-title">Notes</div>
    <div class="prop-row">
      <textarea oninput="applyProp('notes',this.value)">${esc(el.notes||'')}</textarea>
    </div>
  </div>
  `;
}

function buildScaleAdvisor(el) {
  // Use element_id as sample phrase since no real script at design time
  // User can mentally substitute their phrase length
  let sw   = el.safe_width  || 1800;
  let cpx  = el.char_px     || 20;
  let sc   = el.scale       || 1.0;

  // Sample phrase for estimation: ask user to think of phrase length
  // We'll compute for a range of phrase lengths
  let out = `<span class="sa-info">safe_width: ${sw} px | char_px: ${cpx}</span>\n`;
  out += `<span class="sa-info">─────────────────────────────</span>\n`;
  out += `<span class="sa-info">chars  max_scale  recommended</span>\n`;

  let current_sc = sc;
  for (let chars of [8, 12, 18, 24, 36, 49, 60, 72]) {
    let words = Math.max(1, Math.round(chars / 5));
    let preferred = Math.min(3.5, 18.0 / words);
    let safe_sc   = sw / (cpx * chars);
    let rec = Math.max(1.0, Math.min(preferred, safe_sc));
    rec = Math.round(rec * 1000) / 1000;

    let w_scene = chars * cpx * rec;
    let fits    = w_scene <= sw + 1;
    let cls     = fits ? 'sa-fits' : 'sa-over';

    out += `<span class="${cls}">${String(chars).padStart(4)}ch  ${safe_sc.toFixed(2).padStart(6)}    ${rec.toFixed(3)}</span>\n`;
  }

  let w_at_current = Math.round(1) ; // placeholder
  out += `\n<span class="sa-info">─────────────────────────────</span>\n`;
  out += `<span class="sa-rec">Current scale: ${sc} | W = chars × ${cpx} × ${sc}</span>\n`;
  out += `<span class="sa-info">At 24 chars: W = ${Math.round(24*cpx*sc)} scene px ${24*cpx*sc <= sw ? '✓ fits' : '✗ overflows'} (safe: ${sw})</span>`;
  return out;
}

function updateScaleAdvisor() {
  if (!selectedObj || !selectedObj._elemDef) return;
  let el = selectedObj._elemDef;
  let el2 = document.getElementById('scale-advisor');
  if (el2) el2.innerHTML = buildScaleAdvisor(el);
}

function applyRecommendedScale() {
  if (!selectedObj || !selectedObj._elemDef) return;
  let el  = selectedObj._elemDef;
  // Default: assume medium phrase ~18 chars
  let sw  = el.safe_width || 1800;
  let cpx = el.char_px    || 20;
  let chars = 18;
  let words = Math.round(chars / 5);
  let preferred = Math.min(3.5, 18.0 / words);
  let safe_sc   = sw / (cpx * chars);
  let rec = Math.max(1.0, Math.min(preferred, safe_sc));
  rec = Math.round(rec * 100) / 100;
  el.scale = rec;
  selectedObj.set({ scaleX: rec/2, scaleY: rec/2 });
  canvas.renderAll();
  renderPropsPanel(selectedObj);
  syncJSON();
}

function applyProp(key, val) {
  if (!selectedObj || !selectedObj._elemDef) return;
  let el = selectedObj._elemDef;
  el[key] = val;

  // If type changed, update visual
  if (key === 'type') {
    refreshElemVisual(selectedObj, el);
  }
  syncJSON();
  if (key === 'safe_width' || key === 'char_px') updateScaleAdvisor();
}

function applyCoord(key, val) {
  if (!selectedObj || !selectedObj._elemDef) return;
  let el = selectedObj._elemDef;
  el[key] = val;
  if (key === 'x')     { selectedObj.set({ left: val/2 }); }
  if (key === 'y')     { selectedObj.set({ top:  val/2 }); }
  if (key === 'scale') { selectedObj.set({ scaleX: val/2, scaleY: val/2 }); }
  if (key === 'angle') { selectedObj.set({ angle: val }); }
  canvas.renderAll();
  syncJSON();
}

function refreshElemVisual(obj, el) {
  let fill = '#000', bg = null;
  if (el.type === 'text_red')         fill = '#dc143c';
  if (el.type === 'text_highlighted') { fill = '#fff'; bg = '#ffa500'; }
  if (el.type.startsWith('text_')) {
    if (obj.type === 'i-text' || obj.type === 'text') {
      obj.set({ fill, backgroundColor: bg });
    }
  }
  let g = layoutData.priority_groups.find(g => g.group_id === obj._groupId);
  let gc = g ? g.color : '#555';
  obj.set({ borderColor: gc, cornerColor: gc });
  canvas.renderAll();
}

function reassignGroup(newGroupId) {
  if (!selectedObj || !selectedObj._elemDef) return;
  let eid = selectedObj._elemDef.element_id;
  let oldGroupId = selectedObj._groupId;

  // Remove from old group
  let og = layoutData.priority_groups.find(g => g.group_id === oldGroupId);
  if (og) og.elements = og.elements.filter(e => e.element_id !== eid);

  // Add to new group
  let ng = layoutData.priority_groups.find(g => g.group_id === newGroupId);
  if (ng) ng.elements.push(selectedObj._elemDef);

  selectedObj._groupId = newGroupId;

  // Update border color
  if (ng) selectedObj.set({ borderColor: ng.color, cornerColor: ng.color });
  canvas.renderAll();
  activeGroupId = newGroupId;
  renderGroupsPanel();
  syncJSON();
}

// ══════════════════════════════════════════════════════════════════════════════
// SYNC / JSON OUTPUT
// ══════════════════════════════════════════════════════════════════════════════
function syncJSON() {
  layoutData.layout_number = +document.getElementById('layout-num').value || 40;
  layoutData.layout_name   = document.getElementById('layout-name').value || '';
  layoutData.phrase_rules.tiling            = document.getElementById('tiling-check').checked;
  layoutData.phrase_rules.coverage_required = document.getElementById('coverage-check').checked;
  document.getElementById('json-out').value = JSON.stringify(layoutData, null, 2);
}

// ══════════════════════════════════════════════════════════════════════════════
// SAVE / LOAD
// ══════════════════════════════════════════════════════════════════════════════
async function saveLayout() {
  syncJSON();
  let res = await fetch('/save_layout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(layoutData),
  });
  let data = await res.json();
  if (data.ok) {
    showToast(`Saved: ${data.path}`, 'green');
  } else {
    showToast('Save failed', 'red');
  }
}

async function promptLoadLayout() {
  // Fetch list first
  let res = await fetch('/list_layouts');
  let nums = await res.json();
  let hint = nums.length ? `Available: ${nums.join(', ')}` : 'No saved layouts yet';
  let num = prompt(`Load layout number?\n${hint}`);
  if (!num) return;
  loadLayout(num);
}

async function loadLayout(num) {
  let res = await fetch(`/load_layout/${num}`);
  if (!res.ok) { showToast(`Layout ${num} not found`, 'red'); return; }
  let data = await res.json();

  canvas.clear(); canvas.backgroundColor = '#ffffff';
  layoutData  = data;
  nextGroupNum = 1 + Math.max(0, ...layoutData.priority_groups.map(g => +g.group_id.replace(/\D/g,'')));
  elemCounters = {};

  document.getElementById('layout-num').value   = layoutData.layout_number || '';
  document.getElementById('layout-name').value  = layoutData.layout_name   || '';
  document.getElementById('tiling-check').checked   = layoutData.phrase_rules?.tiling            !== false;
  document.getElementById('coverage-check').checked = layoutData.phrase_rules?.coverage_required !== false;

  // Rebuild canvas
  for (let g of layoutData.priority_groups) {
    for (let el of g.elements) {
      let obj = buildFabricObj(el, g);
      canvas.add(obj);
    }
  }

  activeGroupId = layoutData.priority_groups[0]?.group_id || null;
  renderGroupsPanel();
  renderPropsPanel(null);
  syncJSON();
  canvas.renderAll();
  showToast(`Loaded layout ${num}`, 'green');
}

function copyJSON() {
  let ta = document.getElementById('json-out');
  ta.select();
  document.execCommand('copy');
  showToast('Copied!', 'blue');
}

// ══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════════════════════
function clearAll() {
  if (!confirm('Clear all elements and groups?')) return;
  canvas.clear(); canvas.backgroundColor = '#ffffff';
  layoutData       = makeEmptyLayout();
  layoutData.layout_number = +document.getElementById('layout-num').value || 40;
  layoutData.layout_name   = document.getElementById('layout-name').value || '';
  nextGroupNum = 1;
  elemCounters = {};
  activeGroupId = null;
  selectedObj   = null;
  renderGroupsPanel();
  renderPropsPanel(null);
  syncJSON();
  canvas.renderAll();
}

function toggleBottom() {
  let p = document.getElementById('bottom-panel');
  let t = document.getElementById('bottom-tog');
  if (p.classList.contains('expanded')) { p.classList.replace('expanded','collapsed'); t.textContent='▲'; }
  else { p.classList.replace('collapsed','expanded'); t.textContent='▼'; }
}

function showToast(msg, color) {
  let t = document.createElement('div');
  t.textContent = msg;
  t.style.cssText = `position:fixed;bottom:20px;right:20px;background:${color==='green'?'#1b5e20':color==='red'?'#b71c1c':'#0d47a1'};color:#fff;padding:8px 16px;border-radius:5px;font-size:13px;z-index:9999;transition:opacity 0.4s;`;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity='0'; setTimeout(()=>t.remove(),500); }, 2500);
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────
canvas.on('mouse:dblclick', function(e) {
  if (!e.target) {
    // Double-click empty area: add element to active group
    let type = 'image';
    if (activeGroupId) addElement(type);
  }
});

syncJSON();
renderGroupsPanel();
</script>
</body>
</html>
"""

# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = '127.0.0.1'
    print(f"\n  Layout Maker running on:")
    print(f"    http://localhost:{PORT}")
    print(f"    http://{local_ip}:{PORT}")
    print(f"\n  Layouts saved to: {LAYOUTS_DIR}\n")
    app.run(host='0.0.0.0', port=PORT, debug=False)
