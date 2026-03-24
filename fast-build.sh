#!/bin/bash
# ─────────────────────────────────────────────────────────
#  Fast Docker Build on RunPod using Kaniko
#  Run this inside a RunPod CPU pod terminal
# ─────────────────────────────────────────────────────────

set -e

DOCKER_USER="abhishek25dh"
IMAGE_NAME="comfyui-explainer"
TAG="latest"

echo "============================================"
echo "  Fast Docker Build with Kaniko"
echo "============================================"

# 1. Get Docker Hub credentials
if [ -z "$DOCKER_PASSWORD" ]; then
    echo "Enter your Docker Hub password or access token:"
    read -s DOCKER_PASSWORD
fi

# 2. Setup Docker Hub auth for kaniko
echo "[1/4] Setting up Docker Hub auth..."
mkdir -p /kaniko/.docker
cat > /kaniko/.docker/config.json <<AUTHEOF
{
    "auths": {
        "https://index.docker.io/v1/": {
            "auth": "$(echo -n "${DOCKER_USER}:${DOCKER_PASSWORD}" | base64)"
        }
    }
}
AUTHEOF

# 3. Clone repo if not already there
echo "[2/4] Getting source code..."
if [ ! -d /workspace/build-context ]; then
    git clone https://github.com/${DOCKER_USER}/exp-pipeline.git /workspace/build-context
else
    cd /workspace/build-context && git pull
fi

# 4. Download kaniko executor
echo "[3/4] Downloading kaniko executor..."
if [ ! -f /workspace/kaniko-executor ]; then
    wget -q -O /workspace/kaniko-executor https://github.com/GoogleContainerTools/kaniko/releases/download/v1.23.2/executor-v1.23.2-linux-amd64
    chmod +x /workspace/kaniko-executor
fi

# 5. Build and push
echo "[4/4] Building and pushing image..."
echo "  Target: ${DOCKER_USER}/${IMAGE_NAME}:${TAG}"
echo "  This will take ~10-15 minutes..."
echo ""

/workspace/kaniko-executor \
    --context=/workspace/build-context \
    --dockerfile=/workspace/build-context/Dockerfile \
    --destination=${DOCKER_USER}/${IMAGE_NAME}:${TAG} \
    --cache=true \
    --cache-ttl=168h \
    --snapshotMode=redo \
    --compressed-caching=false

echo ""
echo "============================================"
echo "  BUILD COMPLETE!"
echo "  Image: ${DOCKER_USER}/${IMAGE_NAME}:${TAG}"
echo "============================================"
