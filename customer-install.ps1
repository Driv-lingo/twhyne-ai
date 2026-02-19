# SNF-AI Windsurf - Customer Installation Script (Windows)

Write-Host "🚀 SNF-AI Windsurf Installation" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    docker --version | Out-Null
    Write-Host "✓ Docker found" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker not found. Please install Docker Desktop first:" -ForegroundColor Red
    Write-Host "   https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

# Get license key
$LICENSE_KEY = Read-Host "Enter your license key (SNF-XXXXXXXX-XXXXXXXX)"

if ([string]::IsNullOrWhiteSpace($LICENSE_KEY)) {
    Write-Host "❌ License key required" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📥 Pulling SNF-AI Windsurf image..." -ForegroundColor Yellow
docker pull twhyne/twhyne:prod

Write-Host ""
Write-Host "🚀 Starting SNF-AI Windsurf..." -ForegroundColor Yellow
docker run -d `
  --name twhyne `
  -e SNF_LICENSE_KEY="$LICENSE_KEY" `
  -p 3000:3000 `
  -p 5002:5002 `
  --mount source=snf_models,target=/app/models `
  --mount source=snf_logs,target=/app/logs `
  --restart unless-stopped `
  twhyne/twhyne:prod

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Access your application at:" -ForegroundColor Cyan
Write-Host "   http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "📋 Useful commands:" -ForegroundColor Cyan
Write-Host "   View logs:    docker logs -f twhyne" -ForegroundColor White
Write-Host "   Stop:         docker stop twhyne" -ForegroundColor White
Write-Host "   Start:        docker start twhyne" -ForegroundColor White
Write-Host "   Remove:       docker rm -f twhyne" -ForegroundColor White
Write-Host ""
