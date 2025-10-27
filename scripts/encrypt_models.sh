#!/bin/bash
# Script to encrypt model files before Docker build
# Run this once after downloading models from Hugging Face

set -e

echo "================================================"
echo "SNF-AI Model Encryption Script"
echo "================================================"
echo ""

# Check if master key is set
if [ -z "$SNF_MASTER_ENCRYPTION_KEY" ]; then
    echo "Error: SNF_MASTER_ENCRYPTION_KEY environment variable not set"
    echo ""
    echo "Usage:"
    echo "  export SNF_MASTER_ENCRYPTION_KEY='your-secret-master-key'"
    echo "  ./scripts/encrypt_models.sh"
    echo ""
    exit 1
fi

# Get project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="$PROJECT_ROOT/models"

echo "Project root: $PROJECT_ROOT"
echo "Models directory: $MODELS_DIR"
echo ""

# Check if models directory exists
if [ ! -d "$MODELS_DIR" ]; then
    echo "Error: Models directory not found: $MODELS_DIR"
    exit 1
fi

# Count .gguf files
GGUF_COUNT=$(find "$MODELS_DIR" -name "*.gguf" -type f | wc -l)

if [ $GGUF_COUNT -eq 0 ]; then
    echo "No .gguf files found in $MODELS_DIR"
    echo "Please download models first using model_downloader.py"
    exit 1
fi

echo "Found $GGUF_COUNT model file(s) to encrypt"
echo ""

# List files to be encrypted
echo "Files to be encrypted:"
find "$MODELS_DIR" -name "*.gguf" -type f | while read file; do
    size=$(du -h "$file" | cut -f1)
    echo "  - $(basename "$file") ($size)"
done
echo ""

# Confirm encryption
read -p "Encrypt these files? This will DELETE the originals! (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Encryption cancelled"
    exit 0
fi

echo ""
echo "Starting encryption..."
echo ""

# Run encryption
cd "$PROJECT_ROOT"
python3 backend/secure_model_manager.py encrypt

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "✓ Encryption complete!"
    echo "================================================"
    echo ""
    echo "Encrypted files in $MODELS_DIR:"
    find "$MODELS_DIR" -name "*.encrypted" -type f | while read file; do
        size=$(du -h "$file" | cut -f1)
        echo "  - $(basename "$file") ($size)"
    done
    echo ""
    echo "IMPORTANT:"
    echo "1. Original .gguf files have been deleted"
    echo "2. Keep SNF_MASTER_ENCRYPTION_KEY secret!"
    echo "3. You can now build the Docker image"
    echo ""
else
    echo ""
    echo "✗ Encryption failed"
    exit 1
fi
