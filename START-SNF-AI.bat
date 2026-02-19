@echo off
:: SNF-AI Starter for Windows - Just double-click!
:: No command line knowledge needed

cls
color 0A
title SNF-AI Windsurf

echo ============================================
echo         SNF-AI WINDSURF STARTER
echo ============================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo ERROR: Docker is not running!
    echo.
    echo Please start Docker Desktop first, then run this again.
    echo.
    pause
    exit /b 1
)

:: Check for license file
set LICENSE_FILE=%USERPROFILE%\.snf-ai-license
if exist "%LICENSE_FILE%" (
    set /p LICENSE_KEY=<"%LICENSE_FILE%"
    echo License found: %LICENSE_KEY:~0,12%...
) else (
    echo First time setup - Enter your license key
    echo.
    echo Get your license at:
    echo https://sunny-imagination-production.up.railway.app
    echo.
    set /p LICENSE_KEY=License key (SNF-XXXXXXXX-XXXXXXXX): 
    
    if "%LICENSE_KEY%"=="" (
        color 0C
        echo ERROR: No license key entered
        pause
        exit /b 1
    )
    
    :: Save for next time
    echo %LICENSE_KEY%> "%LICENSE_FILE%"
    echo License saved for future use
)

echo.
echo Starting SNF-AI...
echo.

:: Stop old container if running
docker stop twhyne >nul 2>&1 && echo Stopped old instance
docker rm twhyne >nul 2>&1

:: Pull latest (will use cached if offline)
echo Checking for updates...
docker pull twhyne/twhyne:licensed >nul 2>&1 || echo Using cached version (offline mode)

:: Start container
echo Starting application...
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
  twhyne/twhyne:licensed >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    color 0A
    echo.
    echo SUCCESS: SNF-AI is running!
    echo.
    echo Opening in browser...
    timeout /t 3 /nobreak >nul
    start http://localhost:3000
    
    :: Clean up old images to save space
    echo Cleaning up old versions...
    docker image prune -f >nul 2>&1
    
    echo.
    echo ============================================
    echo   Access at: http://localhost:3000
    echo   To stop: Run STOP-SNF-AI.bat
    echo ============================================
) else (
    color 0C
    echo.
    echo ERROR: Failed to start
    echo Check that Docker is running and try again
)

echo.
pause
