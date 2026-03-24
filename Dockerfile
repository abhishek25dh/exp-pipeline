# ─────────────────────────────────────────────────────────────
#  Custom ComfyUI + Explainer Video Pipeline
#  Base: RunPod PyTorch (has SSH, JupyterLab, web terminal)
#  PyTorch cu124 — works on ALL RunPod GPUs
# ─────────────────────────────────────────────────────────────
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV HOME=/root
ENV PYTHONPATH=/usr/lib/python3.11:$PYTHONPATH

# ── 1. System packages ──────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl ffmpeg \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ── 2. Install PyTorch cu124 (overrides base image torch) ──
RUN python -m pip install --target=/usr/lib/python3.11 --upgrade --force-reinstall \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# ── 3. Install ComfyUI ──────────────────────────────────────
RUN mkdir -p /root/apps && \
    cd /root/apps && \
    git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd ComfyUI && \
    python -m pip install --target=/usr/lib/python3.11 -r requirements.txt

# ── 4. ComfyUI-Manager ──────────────────────────────────────
RUN cd /root/apps/ComfyUI/custom_nodes && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    python -m pip install --target=/usr/lib/python3.11 -r requirements.txt || true

# ── 5. Download AI Models ───────────────────────────────────

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

# ── 6. Install FileBrowser ────────────────────────────────────
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

# ── 7. Python deps for Explainer project ────────────────────
RUN python -m pip install --target=/usr/lib/python3.11 \
    flask \
    flask-cors \
    "moviepy==1.0.3" \
    numpy \
    pillow \
    proglog \
    pydub \
    rapidfuzz \
    requests \
    websocket-client \
    python-docx \
    python-dotenv \
    whisper-timestamped

# ── 8. Clone Explainer project from GitHub ───────────────────
RUN git clone https://github.com/abhishek25dh/exp-pipeline.git /root/apps/explainer-project/

# ── 9. Fix pipeline_runner port to 5555 ──────────────────────
RUN sed -i 's/PORT = 5577/PORT = 5555/' /root/apps/explainer-project/pipeline_runner.py

# ── 10. Create inputs directory ───────────────────────────────
RUN mkdir -p /root/apps/explainer-project/inputs

# ── 11. Startup script ────────────────────────────────────────
COPY start.sh /root/start.sh
RUN chmod +x /root/start.sh

# ── 12. Expose all ports ──────────────────────────────────────
#  8080 = FileBrowser
#  8188 = ComfyUI
#  5555 = Pipeline Runner
#  5566 = Render Video
#  8888 = JupyterLab (from base image)
#  22   = SSH (from base image)
EXPOSE 8080 8188 5555 5566 8888 22

CMD ["/root/start.sh"]
