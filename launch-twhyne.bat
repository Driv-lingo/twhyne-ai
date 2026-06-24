@echo off
setlocal

echo ============================================================
echo  Twhyne AI - Launcher
echo ============================================================
echo.

REM ── License key ─────────────────────────────────────────────
if "%SNF_LICENSE_KEY%"=="" (
    set /p SNF_LICENSE_KEY="Enter your Twhyne license key (TWHYNE-...): "
)

if "%SNF_LICENSE_KEY%"=="" (
    echo ERROR: No license key provided.
    echo Get a license at https://twhyne.com
    pause
    exit /b 1
)

REM ── Check Docker is running ──────────────────────────────────
docker version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM ── Pull latest image ────────────────────────────────────────
echo Checking for updates...
docker pull --platform linux/arm64 twhyne/twhyne:licensed
echo.

REM ── Stop any existing container ─────────────────────────────
docker stop twhyne-ai 2>nul
docker rm   twhyne-ai 2>nul

REM ── Write patched app_launcher.py (starts frontend, no tkinter) ──
set PATCH_DIR=%TEMP%\twhyne-patch
mkdir "%PATCH_DIR%" 2>nul
(
echo import subprocess
echo import threading
echo import time
echo import os
echo import sys
echo.
echo def start_frontend^(^):
echo     os.chdir^("/app/frontend"^)
echo     env = os.environ.copy^(^)
echo     env["PORT"] = "3000"
echo     env["BROWSER"] = "none"
echo     env["CI"] = "false"
echo     subprocess.run^(["npm", "start"], env=env^)
echo.
echo t = threading.Thread^(target=start_frontend, daemon=True^)
echo t.start^(^)
echo.
echo # Keep main thread alive
echo while True:
echo     time.sleep^(60^)
) > "%PATCH_DIR%\app_launcher.py"

REM ── Launch ──────────────────────────────────────────────────
echo Starting Twhyne AI...
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:5002
echo.
echo Press Ctrl+C to stop.
echo ============================================================

docker run --name twhyne-ai --rm ^
  --platform linux/arm64 ^
  -e SNF_LICENSE_KEY=%SNF_LICENSE_KEY% ^
  -e LICENSE_API_URL=https://twhyne.com ^
  -e SNF_LICENSE_API=https://twhyne.com ^
  -v "%PATCH_DIR%\app_launcher.py:/app/backend/app_launcher.py:ro" ^
  -p 3000:3001 ^
  -p 5002:5002 ^
  twhyne/twhyne:licensed

echo.
echo ============================================================
echo  Twhyne AI has stopped. See output above for details.
echo ============================================================
pause
endlocal
