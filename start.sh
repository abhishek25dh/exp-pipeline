#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Startup: ComfyUI + all Explainer services
# ─────────────────────────────────────────────────────────

PROJECT_DIR=/root/apps/explainer-project

echo "============================================"
echo "  Starting all services..."
echo "============================================"

# 1. ComfyUI (port 8188)
echo "[1/5] Starting ComfyUI on port 8188..."
cd /root/apps/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 &

# 2. Pipeline Runner (port 5577)
echo "[2/5] Starting Pipeline Runner on port 5577..."
cd "$PROJECT_DIR"
python pipeline_runner.py &

# 3. Layout Maker (port 5557)
echo "[3/5] Starting Layout Maker on port 5557..."
cd "$PROJECT_DIR"
python layout_maker.py &

# 4. Layout Tester (port 5555)
echo "[4/5] Starting Layout Tester on port 5555..."
cd "$PROJECT_DIR"
python layout_tester.py &

# 5. Render Video (port 5566)
echo "[5/5] Starting Render Video on port 5566..."
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
echo "  ComfyUI:          http://localhost:8188"
echo "  Pipeline Runner:  http://localhost:5577"
echo "  Layout Maker:     http://localhost:5557"
echo "  Layout Tester:    http://localhost:5555"
echo "  Render Video:     http://localhost:5566"
echo "============================================"

# Keep container alive
wait
