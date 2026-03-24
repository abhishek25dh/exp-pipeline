#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Startup: All services for Explainer Video Pipeline
# ─────────────────────────────────────────────────────────

PROJECT_DIR=/root/apps/explainer-project
COMFYUI_DIR=/root/apps/ComfyUI

echo "============================================"
echo "  Starting all services..."
echo "============================================"

# 0. Create .env from RunPod env var if set
if [ -n "$OPENROUTER_API_KEY" ]; then
    echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" > "$PROJECT_DIR/.env"
    echo "[env] OpenRouter key set"
fi

# 1. FileBrowser (port 8080)
echo "[1/4] Starting FileBrowser on port 8080..."
nohup filebrowser -a 0.0.0.0 -p 8080 -r / --noauth > /dev/null 2>&1 &

# 2. ComfyUI (port 8188)
echo "[2/4] Starting ComfyUI on port 8188..."
cd "$COMFYUI_DIR"
nohup python main.py --listen 0.0.0.0 --port 8188 > /tmp/comfyui.log 2>&1 &

# 3. Pipeline Runner (port 5555)
echo "[3/4] Starting Pipeline Runner on port 5555..."
cd "$PROJECT_DIR"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
nohup python pipeline_runner.py > /tmp/pipeline.log 2>&1 &

# 4. Render Video (port 5566)
echo "[4/4] Starting Render Video on port 5566..."
cd "$PROJECT_DIR"
nohup python render_video.py > /tmp/render.log 2>&1 &

# Wait for ComfyUI to be ready
echo ""
echo "Waiting for ComfyUI to initialize..."
for i in $(seq 1 120); do
    if curl -s http://localhost:8188 > /dev/null 2>&1; then
        echo "ComfyUI ready!"
        break
    fi
    sleep 2
done

echo ""
echo "============================================"
echo "  ALL SERVICES RUNNING"
echo "============================================"
echo "  FileBrowser:      http://localhost:8080"
echo "  ComfyUI:          http://localhost:8188"
echo "  Pipeline Runner:  http://localhost:5555"
echo "  Render Video:     http://localhost:5566"
echo "============================================"

# Keep container alive
wait
