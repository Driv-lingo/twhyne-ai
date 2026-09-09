@echo off
setlocal enabledelayedexpansion
title Twhyne AI

echo ============================================================
echo  Twhyne AI - Launcher
echo ============================================================
echo.

set IMAGE=twhyne/twhyne:cpu
set TWHYNE_DIR=%USERPROFILE%\.twhyne
set LICENSE_FILE=%TWHYNE_DIR%\license.key
if not exist "%TWHYNE_DIR%" mkdir "%TWHYNE_DIR%"

REM -- License key: remembered after the first run --------------
REM Priority: environment variable > saved file > prompt once.
if "%SNF_LICENSE_KEY%"=="" (
    if exist "%LICENSE_FILE%" (
        set /p SNF_LICENSE_KEY=<"%LICENSE_FILE%"
        echo Using saved license key. ^(Delete %LICENSE_FILE% to change it.^)
    )
)
if "%SNF_LICENSE_KEY%"=="" (
    set /p SNF_LICENSE_KEY="Enter your Twhyne license key (TWHYNE-...): "
)
if "%SNF_LICENSE_KEY%"=="" (
    echo ERROR: No license key provided.
    echo Get a license at https://twhyne.com
    pause
    exit /b 1
)
REM Save for next time (validated by the app at startup).
>"%LICENSE_FILE%" echo %SNF_LICENSE_KEY%

REM -- Start Docker Desktop automatically if it isn't running ---
REM (labels cannot live inside parenthesized blocks in cmd, so this is
REM  structured with plain gotos)
docker version >nul 2>&1
if not errorlevel 1 goto dockerready
echo Docker is not running. Starting Docker Desktop...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else if exist "%LocalAppData%\Docker\Docker Desktop.exe" (
    start "" "%LocalAppData%\Docker\Docker Desktop.exe"
) else (
    echo ERROR: Docker Desktop not found. Install it from https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo Waiting for Docker to start ^(up to 2 minutes^)...
set /a WAITED=0
:dockerwait
timeout /t 5 /nobreak >nul
docker version >nul 2>&1
if not errorlevel 1 goto dockerready
set /a WAITED+=5
if %WAITED% lss 120 goto dockerwait
echo ERROR: Docker did not start in time. Start Docker Desktop manually and re-run.
pause
exit /b 1

:dockerready
echo Docker is running.
echo.

REM -- Model directory (downloaded once) ------------------------
set MODELS_DIR=%TWHYNE_DIR%\models
if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"
set RAG_DIR=%TWHYNE_DIR%\rag
if not exist "%RAG_DIR%" mkdir "%RAG_DIR%"

call :get_model "mistral-7b-instruct-q4.gguf" "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
call :get_model "qwen2.5-coder-7b-instruct-q4.gguf" "https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"
call :get_model "llava-v1.5-7b-Q4_K.gguf"       "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/ggml-model-q4_k.gguf"
call :get_model "mmproj-model-f16.gguf"         "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/mmproj-model-f16.gguf"
call :get_model "bge-small-en-v1.5-f16.gguf"     "https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/main/bge-small-en-v1.5-f16.gguf"

echo.
echo Models ready in %MODELS_DIR%
echo.

REM -- Pull latest image (automatic updates) --------------------
echo Checking for updates...
docker pull %IMAGE%
echo.

REM -- Stop any existing container ------------------------------
docker stop twhyne-ai >nul 2>&1
docker rm   twhyne-ai >nul 2>&1

REM -- Open browser after startup ------------------------------
start "" /min cmd /c "timeout /t 12 >nul & start http://localhost:3000"

echo Starting Twhyne AI...
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:5002
echo.
echo (Local models are loading. On CPU-only systems the FIRST response may take
echo  several minutes while a 7B model loads and generates; later responses are
echo  faster. Your reasoning stays on this machine - that is the trade for speed.)
echo Close this window or press Ctrl+C to stop Twhyne.
echo ============================================================

REM No --rm: keep the stopped container so `docker logs twhyne-ai`
REM survives a crash for diagnosis (removed on next launch above).
REM Memory: 12g default. Machines with 32GB+ RAM can set TWHYNE_MEM=18g and
REM TWHYNE_MAX_RESIDENT=2 to keep BOTH models loaded - eliminates the
REM multi-minute swap between code and chat questions.
if "%TWHYNE_MEM%"=="" set TWHYNE_MEM=12g
if "%TWHYNE_MAX_RESIDENT%"=="" set TWHYNE_MAX_RESIDENT=1

REM -- Fit the limit to the Docker VM ---------------------------
REM Docker Desktop runs containers inside a fixed-size Linux VM (default:
REM half of host RAM). A -m limit LARGER than the VM is not enforced by
REM anything real: the VM itself runs out of memory while the 7B model
REM loads and the whole engine drops ("unexpected EOF"). Cap the limit
REM at VM size minus 1 GB, and say so when the VM is too small.
set VM_GB=
for /f "usebackq delims=" %%m in (`powershell -NoProfile -Command "try { [math]::Floor([double](docker info --format '{{.MemTotal}}') / 1GB) } catch { 0 }"`) do set VM_GB=%%m
if not defined VM_GB set VM_GB=0
if %VM_GB% GTR 0 (
    set /a CAP_GB=%VM_GB%-1
    for /f "delims=g" %%v in ("%TWHYNE_MEM%") do set REQ_GB=%%v
    if !REQ_GB! GTR !CAP_GB! (
        set TWHYNE_MEM=!CAP_GB!g
        echo Docker VM has %VM_GB% GB; container memory limit set to !CAP_GB!g.
    )
    if %VM_GB% LSS 8 (
        echo.
        echo WARNING: Docker's VM only has %VM_GB% GB of memory. A 7B model needs about
        echo   6 GB to load and answer. Give Docker more memory: create or edit
        echo   %USERPROFILE%\.wslconfig with
        echo     [wsl2]
        echo     memory=12GB
        echo   then run "wsl --shutdown" and start Docker Desktop again.
        echo.
    )
)
docker run --name twhyne-ai ^
  -e SNF_LICENSE_KEY=%SNF_LICENSE_KEY% ^
  -e LICENSE_API_URL=https://twhyne.com ^
  -e SNF_LICENSE_API=https://twhyne.com ^
  -e TWHYNE_MAX_RESIDENT=%TWHYNE_MAX_RESIDENT% ^
  -v "%MODELS_DIR%:/app/models" ^
  -v "%RAG_DIR%:/app/backend/rag_storage" ^
  -v twhyne_modelcache:/app/model_cache ^
  -p 3000:3000 ^
  -p 5002:5002 ^
  -m %TWHYNE_MEM% ^
  %IMAGE%

echo.
echo ============================================================
echo  Twhyne AI has stopped.
echo ============================================================
REM Say WHY. The container is kept (no --rm) so its exit state survives.
set EXIT_INFO=
for /f "usebackq delims=" %%s in (`docker inspect twhyne-ai --format "{{.State.ExitCode}} oom={{.State.OOMKilled}}" 2^>nul`) do set EXIT_INFO=%%s
if defined EXIT_INFO (
    echo  Container exit: !EXIT_INFO!
    echo !EXIT_INFO! | findstr /C:"oom=true" >nul && (
        echo  The container ran out of memory ^(limit %TWHYNE_MEM%^).
    )
    echo !EXIT_INFO! | findstr /R /C:"^137 " >nul && (
        echo  Killed ^(exit 137^): out of memory, or Docker's VM was reset.
    )
    echo !EXIT_INFO! | findstr /R /C:"^1 " >nul && (
        echo  If the log above says the license was rejected, delete this file and re-run:
        echo    %LICENSE_FILE%
    )
) else (
    echo  Docker itself stopped responding ^(the engine or its VM went down^).
    echo  This is almost always the Docker VM running out of memory. Check
    echo  Docker Desktop ^> Settings ^> Resources, or %USERPROFILE%\.wslconfig.
)
echo  Full log: docker logs twhyne-ai
echo ============================================================
pause
exit /b 0

REM -- Helper: download a model if not already present ----------
:get_model
set "FNAME=%~1"
set "URL=%~2"
if exist "%MODELS_DIR%\%FNAME%" (
    echo [OK] %FNAME% already downloaded.
    goto :eof
)
echo.
echo Downloading %FNAME% (a few GB, one time only)...
curl -L -o "%MODELS_DIR%\%FNAME%" "%URL%"
if errorlevel 1 (
    echo WARNING: Failed to download %FNAME%. That node will be unavailable.
    del "%MODELS_DIR%\%FNAME%" 2>nul
)
goto :eof
