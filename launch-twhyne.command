#!/bin/bash
# Twhyne AI - macOS/Linux Launcher

set -e

echo "============================================================"
echo " Twhyne AI - Launcher"
echo "============================================================"
echo ""

IMAGE="twhyne/twhyne:cpu"
TWHYNE_DIR="$HOME/.twhyne"
LICENSE_FILE="$TWHYNE_DIR/license.key"
mkdir -p "$TWHYNE_DIR"

# -- License key: remembered after the first run --------------
if [ -z "$SNF_LICENSE_KEY" ] && [ -f "$LICENSE_FILE" ]; then
    SNF_LICENSE_KEY="$(cat "$LICENSE_FILE")"
    echo "Using saved license key. (Delete $LICENSE_FILE to change it.)"
fi
if [ -z "$SNF_LICENSE_KEY" ]; then
    read -rp "Enter your Twhyne license key (TWHYNE-...): " SNF_LICENSE_KEY
fi
if [ -z "$SNF_LICENSE_KEY" ]; then
    echo "ERROR: No license key provided."
    echo "Get a license at https://twhyne.com"
    read -rp "Press Enter to exit..."
    exit 1
fi
printf '%s\n' "$SNF_LICENSE_KEY" > "$LICENSE_FILE"

# -- Start Docker automatically if it isn't running -----------
if ! command -v docker > /dev/null 2>&1; then
    if [ "$(uname)" = "Darwin" ]; then
        echo "ERROR: Docker is not installed. Install Docker Desktop from"
        echo "  https://www.docker.com/products/docker-desktop/"
    else
        echo "ERROR: Docker is not installed. Install Docker Engine, e.g.:"
        echo "  curl -fsSL https://get.docker.com | sh"
        echo "  sudo usermod -aG docker \$USER   (then log out and back in)"
    fi
    read -rp "Press Enter to exit..."
    exit 1
fi
if ! docker version > /dev/null 2>&1; then
    if [ "$(uname)" = "Darwin" ]; then
        echo "Docker is not running. Starting Docker Desktop..."
        open -a Docker 2>/dev/null || true
    else
        echo "Docker is not running. Trying to start the Docker service..."
        (sudo systemctl start docker 2>/dev/null || systemctl start docker 2>/dev/null) || true
    fi
    WAITED=0
    until docker version > /dev/null 2>&1; do
        sleep 5
        WAITED=$((WAITED + 5))
        if [ "$WAITED" -ge 120 ]; then
            if [ "$(uname)" = "Darwin" ]; then
                echo "ERROR: Docker did not start in time. Start Docker Desktop manually and re-run."
            else
                echo "ERROR: Docker did not start in time. Start it manually and re-run:"
                echo "  sudo systemctl start docker"
                echo "If your user lacks Docker access: sudo usermod -aG docker \$USER (then re-login)."
            fi
            read -rp "Press Enter to exit..."
            exit 1
        fi
    done
fi
echo "Docker is running."
echo ""

# -- Model directory (downloaded once) ----------------------
MODELS_DIR="$TWHYNE_DIR/models"
mkdir -p "$MODELS_DIR"
RAG_DIR="$TWHYNE_DIR/rag"
mkdir -p "$RAG_DIR"

get_model() {
    local fname="$1"; local url="$2"
    if [ -f "$MODELS_DIR/$fname" ]; then
        echo "[OK] $fname already downloaded."; return
    fi
    echo ""
    echo "Downloading $fname (a few GB, one time only)..."
    if ! curl -L -o "$MODELS_DIR/$fname" "$url"; then
        echo "WARNING: Failed to download $fname. That node will be unavailable."
        rm -f "$MODELS_DIR/$fname"
    fi
}

get_model "mistral-7b-instruct-q4.gguf" "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
get_model "qwen2.5-coder-7b-instruct-q4.gguf" "https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"
get_model "llava-v1.5-7b-Q4_K.gguf"      "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/ggml-model-q4_k.gguf"
get_model "mmproj-model-f16.gguf"        "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/mmproj-model-f16.gguf"
get_model "bge-small-en-v1.5-f16.gguf"    "https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/main/bge-small-en-v1.5-f16.gguf"

echo ""
echo "Models ready in $MODELS_DIR"
echo ""

# -- Pull latest image (automatic updates) -------------------
echo "Checking for updates..."
docker pull "$IMAGE"
echo ""

# -- Stop any existing container -----------------------------
docker stop twhyne-ai 2>/dev/null || true
docker rm   twhyne-ai 2>/dev/null || true

# -- Open browser after startup -----------------------------
(sleep 12 && (open "http://localhost:3000" 2>/dev/null || xdg-open "http://localhost:3000" 2>/dev/null)) &

echo "Starting Twhyne AI..."
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:5002"
echo ""
echo "(First response may take up to a minute while the model loads.)"
echo "Press Ctrl+C to stop."
echo "============================================================"

# No --rm: keep the stopped container so `docker logs twhyne-ai`
# survives a crash for diagnosis (removed on next launch above).
docker run --name twhyne-ai \
  -e SNF_LICENSE_KEY="$SNF_LICENSE_KEY" \
  -e LICENSE_API_URL=https://twhyne.com \
  -e SNF_LICENSE_API=https://twhyne.com \
  -v "$MODELS_DIR:/app/models" \
  -v "$RAG_DIR:/app/backend/rag_storage" \
  -p 3000:3000 \
  -p 5002:5002 \
  -m 12g \
  "$IMAGE"

echo ""
echo "Twhyne AI has stopped. If your license was rejected, delete"
echo "$LICENSE_FILE and re-run."
