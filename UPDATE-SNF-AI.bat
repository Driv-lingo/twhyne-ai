@echo off
:: Update SNF-AI - Just double-click!

echo ============================================
echo         SNF-AI UPDATE TOOL
echo ============================================
echo.

:: Check for license
set LICENSE_FILE=%USERPROFILE%\.snf-ai-license
if not exist "%LICENSE_FILE%" (
    echo ERROR: No license found. Run START-SNF-AI.bat first
    pause
    exit /b 1
)

set /p LICENSE_KEY=<"%LICENSE_FILE%"

echo Downloading latest version...
docker pull twhyne/twhyne:latest

echo.
echo Stopping current version...
docker stop twhyne >nul 2>&1
docker rm twhyne >nul 2>&1

echo Starting updated version...
docker run -d ^
  --name twhyne ^
  -e SNF_LICENSE_KEY=%LICENSE_KEY% ^
  -p 3000:3000 ^
  -p 5002:5002 ^
  --mount source=snf_models,target=/app/models ^
  --mount source=snf_logs,target=/app/logs ^
  --mount source=snf_data,target=/app/data ^
  --mount source=snf_uploads,target=/app/uploads ^
  --mount source=snf_rag,target=/app/rag_storage ^
  --mount source=snf_conversations,target=/app/conversations ^
  --restart unless-stopped ^
  twhyne/twhyne:latest >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Updated to latest version!
    echo.
    
    :: Clean up old images
    echo Cleaning up old versions to save space...
    docker image prune -f >nul 2>&1
    
    echo Your data has been preserved.
    echo.
    echo Opening in browser...
    start http://localhost:3000
) else (
    echo.
    echo ERROR: Update failed
)

pause
