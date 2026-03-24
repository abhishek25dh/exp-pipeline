#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Run this on a cloud machine (RunPod/Massed Compute)
#  to build and push the Docker image
# ─────────────────────────────────────────────────────────

set -e

DOCKER_USER="abhishek25dh"
IMAGE_NAME="comfyui-explainer"
TAG="latest"

echo "============================================"
echo "  Cloud Docker Build Script"
echo "============================================"

# Step 1: Login to Docker Hub
echo ""
echo "[1/3] Logging into Docker Hub..."
docker login -u "$DOCKER_USER"

# Step 2: Build
echo ""
echo "[2/3] Building image: $DOCKER_USER/$IMAGE_NAME:$TAG"
echo "       This will take 15-30 minutes..."
docker build -t "$DOCKER_USER/$IMAGE_NAME:$TAG" .

# Step 3: Push
echo ""
echo "[3/3] Pushing to Docker Hub..."
docker push "$DOCKER_USER/$IMAGE_NAME:$TAG"

echo ""
echo "============================================"
echo "  DONE!"
echo "  Image: $DOCKER_USER/$IMAGE_NAME:$TAG"
echo "  Ready to use as a RunPod template."
echo "============================================"
