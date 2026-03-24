# ─────────────────────────────────────────────────────────────
#  Custom ComfyUI + Explainer Video Pipeline
#  Target: RunPod / Massed Compute GPU instances
#  Base: NVIDIA CUDA 12.8 + Ubuntu 22.04
# ─────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV HOME=/root

# ── 1. System packages ──────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    git wget curl \
    ffmpeg \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

# ── 1b. Install FileBrowser ──────────────────────────────────
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

# ── 2. Install ComfyUI ──────────────────────────────────────
RUN mkdir -p /root/apps && \
    cd /root/apps && \
    git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd ComfyUI && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128 && \
    pip install --no-cache-dir -r requirements.txt

# ── 3. ComfyUI-Manager ──────────────────────────────────────
RUN cd /root/apps/ComfyUI/custom_nodes && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install --no-cache-dir -r requirements.txt || true

# ── 4. Download AI Models ───────────────────────────────────

# Text Encoder — Qwen 3 4B
ADD https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors \
    /root/apps/ComfyUI/models/text_encoders/qwen_3_4b.safetensors

# LoRA — Pixel Art Style
ADD https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo/resolve/main/pixel_art_style_z_image_turbo.safetensors \
    /root/apps/ComfyUI/models/loras/pixel_art_style_z_image_turbo.safetensors

# Diffusion Model — Z Image Turbo BF16
ADD https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors \
    /root/apps/ComfyUI/models/diffusion_models/z_image_turbo_bf16.safetensors

# VAE — Autoencoder
ADD https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors \
    /root/apps/ComfyUI/models/vae/ae.safetensors

# ── 5. Python deps for Explainer project ────────────────────
RUN pip install --no-cache-dir \
    gradio \
    moviepy \
    numpy \
    pillow \
    proglog \
    pydub \
    rapidfuzz \
    requests \
    websocket-client \
    flask

# ── 6. Clone Explainer project from GitHub ───────────────────
RUN git clone https://github.com/abhishek25dh/exp-pipeline.git /root/apps/explainer-project/

# ── 7. Startup script ───────────────────────────────────────
COPY start.sh /root/start.sh
RUN chmod +x /root/start.sh

# ── 8. Expose all ports ─────────────────────────────────────
#  8188 = ComfyUI
#  5577 = Pipeline Runner
#  5557 = Layout Maker
#  5555 = Layout Tester
#  5566 = Render Video
#  8080 = FileBrowser
EXPOSE 8188 5577 5557 5555 5566 8080

CMD ["/root/start.sh"]
