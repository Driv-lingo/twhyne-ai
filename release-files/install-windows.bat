@echo off
echo 🚀 SNF-AI Windsurf Installer for Windows
echo ==========================================

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed. Please install Docker Desktop first:
    echo    https://docs.docker.com/desktop/windows/
    pause
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose is not installed. Please install Docker Desktop first:
    echo    https://docs.docker.com/desktop/windows/
    pause
    exit /b 1
)

echo ✅ Docker and Docker Compose found

REM Download docker-compose.yml
echo 📥 Downloading configuration...
curl -L -o docker-compose.yml https://github.com/Driv-lingo/twhyne-ai/releases/download/v1.0.0/docker-compose.yml

if %errorlevel% neq 0 (
    echo ❌ Failed to download configuration file
    pause
    exit /b 1
)

echo ✅ Configuration downloaded

REM Start the application
echo 🚀 Starting SNF-AI Windsurf...
docker-compose up -d

if %errorlevel% equ 0 (
    echo.
    echo 🎉 SNF-AI Windsurf is starting up!
    echo.
    echo 📍 Access Points:
    echo    🌐 Dashboard: http://localhost:5002/dashboard/
    echo    🔧 API: http://localhost:5002/query
    echo    📊 Status: http://localhost:5002/status
    echo.
    echo ⏳ First run takes 2-3 minutes to download AI models
    echo 📋 Monitor progress: docker-compose logs -f
    echo.
    echo 🛑 To stop: docker-compose down
    echo.
    pause
) else (
    echo ❌ Failed to start SNF-AI Windsurf
    pause
    exit /b 1
)
