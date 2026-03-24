#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Startup: FileBrowser + ComfyUI + all Explainer services
# ─────────────────────────────────────────────────────────

PROJECT_DIR=/root/apps/explainer-project

echo "============================================"
echo "  Starting all services..."
echo "============================================"

# 0. Create .env from RunPod env var if set
if [ -n "$OPENROUTER_API_KEY" ]; then
    echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" > "$PROJECT_DIR/.env"
    echo "[env] Created .env with OPENROUTER_API_KEY"
fi

# 1. FileBrowser (port 8080)
echo "[1/6] Starting FileBrowser on port 8080..."
if command -v filebrowser &> /dev/null; then
    nohup filebrowser -a 0.0.0.0 -p 8080 -r / --noauth > /dev/null 2>&1 &
else
    echo "  FileBrowser not installed, skipping..."
fi

# 2. ComfyUI (port 8188)
echo "[2/6] Starting ComfyUI on port 8188..."
cd /root/apps/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 &

# 3. Pipeline Runner (port 5577)
echo "[3/6] Starting Pipeline Runner on port 5577..."
cd "$PROJECT_DIR"
python pipeline_runner.py &

# 4. Layout Maker (port 5557)
echo "[4/6] Starting Layout Maker on port 5557..."
cd "$PROJECT_DIR"
python layout_maker.py &

# 5. Layout Tester (port 5555)
echo "[5/6] Starting Layout Tester on port 5555..."
cd "$PROJECT_DIR"
python layout_tester.py &

# 6. Render Video (port 5566)
echo "[6/6] Starting Render Video on port 5566..."
cd "$PROJECT_DIR"
python render_video.py &

# Wait for ComfyUI to be ready
echo ""
echo "Waiting for ComfyUI to initialize..."
until curl -s http://localhost:8188 > /dev/null 2>&1; do
    sleep 2
done

echo ""
echo "============================================"
echo "  ALL SERVICES RUNNING"
echo "============================================"
echo "  FileBrowser:      http://localhost:8080"
echo "  ComfyUI:          http://localhost:8188"
echo "  Pipeline Runner:  http://localhost:5577"
echo "  Layout Maker:     http://localhost:5557"
echo "  Layout Tester:    http://localhost:5555"
echo "  Render Video:     http://localhost:5566"
echo "============================================"

# Keep container alive
wait
