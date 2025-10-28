#!/bin/bash
# Release script for SNF-AI Windsurf

set -e

# Check if version provided
if [ -z "$1" ]; then
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 1.0.1"
    exit 1
fi

VERSION=$1
IMAGE_BASE="twhyne/twhyne"

echo "🚀 Building SNF-AI Windsurf v${VERSION}"
echo "============================================"

# Build the image
echo "Building Docker image..."
docker build -t ${IMAGE_BASE}:${VERSION} .

# Tag as latest and licensed
docker tag ${IMAGE_BASE}:${VERSION} ${IMAGE_BASE}:latest
docker tag ${IMAGE_BASE}:${VERSION} ${IMAGE_BASE}:licensed

echo ""
echo "✅ Build complete. Tags created:"
echo "  - ${IMAGE_BASE}:${VERSION}"
echo "  - ${IMAGE_BASE}:latest"
echo "  - ${IMAGE_BASE}:licensed"

# Test license enforcement
echo ""
echo "🧪 Testing license enforcement..."
docker run --rm ${IMAGE_BASE}:${VERSION} python3 /app/backend/simple_license_check.py 2>&1 | head -5 || true

# Push to Docker Hub
echo ""
read -p "Push to Docker Hub? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pushing to Docker Hub..."
    docker push ${IMAGE_BASE}:${VERSION}
    docker push ${IMAGE_BASE}:latest
    docker push ${IMAGE_BASE}:licensed
    echo "✅ Pushed successfully!"
fi

# Create git tag
echo ""
read -p "Create git tag v${VERSION}? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git tag -a "v${VERSION}" -m "Release version ${VERSION}"
    git push origin "v${VERSION}"
    echo "✅ Git tag created!"
fi

echo ""
echo "🎉 Release v${VERSION} complete!"
echo ""
echo "Customer update command:"
echo "  docker pull ${IMAGE_BASE}:${VERSION}"
echo "  docker pull ${IMAGE_BASE}:latest"
