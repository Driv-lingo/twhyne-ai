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
call :get_model "codellama-7b-q4.gguf"        "https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q4_K_M.gguf"
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
echo (First response may take up to a minute while the model loads.)
echo Close this window or press Ctrl+C to stop Twhyne.
echo ============================================================

docker run --name twhyne-ai --rm ^
  -e SNF_LICENSE_KEY=%SNF_LICENSE_KEY% ^
  -e LICENSE_API_URL=https://twhyne.com ^
  -e SNF_LICENSE_API=https://twhyne.com ^
  -v "%MODELS_DIR%:/app/models" ^
  -v "%RAG_DIR%:/app/backend/rag_storage" ^
  -p 3000:3000 ^
  -p 5002:5002 ^
  %IMAGE%

echo.
echo ============================================================
echo  Twhyne AI has stopped.
echo  If your license was rejected, delete this file and re-run:
echo    %LICENSE_FILE%
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
