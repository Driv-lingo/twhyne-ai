@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  Twhyne AI - Launcher
echo ============================================================
echo.

set IMAGE=ghcr.io/driv-lingo/twhyne:cpu

REM -- License key --------------------------------------------
if "%SNF_LICENSE_KEY%"=="" (
    set /p SNF_LICENSE_KEY="Enter your Twhyne license key (TWHYNE-...): "
)
if "%SNF_LICENSE_KEY%"=="" (
    echo ERROR: No license key provided.
    echo Get a license at https://twhyne.com
    pause
    exit /b 1
)

REM -- Check Docker is running ---------------------------------
docker version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM -- Model directory (downloaded once) ----------------------
set MODELS_DIR=%USERPROFILE%\.twhyne\models
if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

call :get_model "mistral-7b-instruct-q4.gguf" "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
call :get_model "codellama-7b-q4.gguf"        "https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q4_K_M.gguf"
call :get_model "llava-v1.5-7b-Q4_K.gguf"       "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/ggml-model-q4_k.gguf"
call :get_model "mmproj-model-f16.gguf"         "https://huggingface.co/mys/ggml_llava-v1.5-7b/resolve/main/mmproj-model-f16.gguf"

echo.
echo Models ready in %MODELS_DIR%
echo.

REM -- Pull latest image --------------------------------------
echo Checking for updates...
docker pull %IMAGE%
echo.

REM -- Stop any existing container -----------------------------
docker stop twhyne-ai 2>nul
docker rm   twhyne-ai 2>nul

REM -- Open browser after startup ------------------------------
start "" /min cmd /c "timeout /t 12 >nul & start http://localhost:3000"

echo Starting Twhyne AI...
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:5002
echo.
echo (First response may take up to a minute while the model loads.)
echo Press Ctrl+C to stop.
echo ============================================================

docker run --name twhyne-ai --rm ^
  -e SNF_LICENSE_KEY=%SNF_LICENSE_KEY% ^
  -e LICENSE_API_URL=https://twhyne.com ^
  -e SNF_LICENSE_API=https://twhyne.com ^
  -v "%MODELS_DIR%:/app/models" ^
  -p 3000:3000 ^
  -p 5002:5002 ^
  %IMAGE%

echo.
echo ============================================================
echo  Twhyne AI has stopped. See output above for details.
echo ============================================================
pause
exit /b 0

REM -- Helper: download a model if not already present --------
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
