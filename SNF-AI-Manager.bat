@echo off
:: SNF-AI Manager - Windows Batch Script
:: No Python needed - pure batch file management

setlocal enabledelayedexpansion
title SNF-AI Windsurf Manager
color 0A

:MENU
cls
echo ============================================
echo         SNF-AI WINDSURF MANAGER
echo ============================================
echo.
echo   1. Start SNF-AI
echo   2. Stop SNF-AI
echo   3. Update SNF-AI
echo   4. View Status
echo   5. Enter License Key
echo   6. Open Application (Browser)
echo   7. View Logs
echo   8. Backup Data
echo   9. Exit
echo.
echo ============================================
set /p choice="Select option (1-9): "

if "%choice%"=="1" goto START
if "%choice%"=="2" goto STOP
if "%choice%"=="3" goto UPDATE
if "%choice%"=="4" goto STATUS
if "%choice%"=="5" goto LICENSE
if "%choice%"=="6" goto OPEN
if "%choice%"=="7" goto LOGS
if "%choice%"=="8" goto BACKUP
if "%choice%"=="9" goto EXIT
goto MENU

:START
cls
echo Starting SNF-AI Windsurf...
echo.

:: Check for license
if not exist "%APPDATA%\SNF-AI\license.txt" (
    echo ERROR: No license key found!
    echo Please select option 5 to enter your license key first.
    pause
    goto MENU
)

:: Read license key
set /p LICENSE_KEY=<"%APPDATA%\SNF-AI\license.txt"

:: Pull latest image
echo Downloading latest version...
docker pull twhyne/twhyne:licensed

:: Stop and remove old container if exists
docker stop twhyne 2>nul
docker rm twhyne 2>nul

:: Start new container
echo Starting container...
docker run -d ^
  --name twhyne ^
  -e SNF_LICENSE_KEY=%LICENSE_KEY% ^
  -p 3000:3000 ^
  -p 5001:5001 ^
  --mount source=snf_models,target=/app/models ^
  --mount source=snf_logs,target=/app/logs ^
  --mount source=snf_data,target=/app/data ^
  --mount source=snf_uploads,target=/app/uploads ^
  --mount source=snf_rag,target=/app/rag_storage ^
  --mount source=snf_conversations,target=/app/conversations ^
  --restart unless-stopped ^
  twhyne/twhyne:licensed

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: SNF-AI is now running!
    echo Access at: http://localhost:3000
    
    :: Clean up old images
    echo.
    echo Cleaning up old images to save space...
    docker image prune -f >nul 2>&1
) else (
    echo.
    echo ERROR: Failed to start SNF-AI
)

pause
goto MENU

:STOP
cls
echo Stopping SNF-AI Windsurf...
docker stop twhyne
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: SNF-AI stopped
) else (
    echo ERROR: Failed to stop or not running
)
pause
goto MENU

:UPDATE
cls
echo Updating SNF-AI Windsurf...
echo.

:: Check for license
if not exist "%APPDATA%\SNF-AI\license.txt" (
    echo ERROR: No license key found!
    pause
    goto MENU
)

set /p LICENSE_KEY=<"%APPDATA%\SNF-AI\license.txt"

:: Pull latest
echo Downloading latest version...
docker pull twhyne/twhyne:latest

:: Stop old
echo Stopping current version...
docker stop twhyne 2>nul
docker rm twhyne 2>nul

:: Start new (data preserved in volumes)
echo Starting updated version...
docker run -d ^
  --name twhyne ^
  -e SNF_LICENSE_KEY=%LICENSE_KEY% ^
  -p 3000:3000 ^
  -p 5001:5001 ^
  --mount source=snf_models,target=/app/models ^
  --mount source=snf_logs,target=/app/logs ^
  --mount source=snf_data,target=/app/data ^
  --mount source=snf_uploads,target=/app/uploads ^
  --mount source=snf_rag,target=/app/rag_storage ^
  --mount source=snf_conversations,target=/app/conversations ^
  --restart unless-stopped ^
  twhyne/twhyne:latest

:: Clean up old images
echo Cleaning up old versions...
docker image prune -f >nul 2>&1

echo.
echo UPDATE COMPLETE!
pause
goto MENU

:STATUS
cls
echo SNF-AI Status:
echo ==============
echo.
docker ps -a --filter name=twhyne --format "Status: {{.Status}}"
echo.
docker ps -a --filter name=twhyne --format "Image: {{.Image}}"
echo.
docker ps -a --filter name=twhyne --format "Ports: {{.Ports}}"
echo.
echo Volume Usage:
docker volume ls | findstr snf_
echo.
pause
goto MENU

:LICENSE
cls
echo License Key Setup
echo =================
echo.
echo Enter your license key (SNF-XXXXXXXX-XXXXXXXX):
set /p NEW_LICENSE=

if "%NEW_LICENSE%"=="" (
    echo ERROR: No license key entered
    pause
    goto MENU
)

:: Save license
if not exist "%APPDATA%\SNF-AI" mkdir "%APPDATA%\SNF-AI"
echo %NEW_LICENSE%> "%APPDATA%\SNF-AI\license.txt"

echo.
echo License key saved!
echo.
echo You can now start SNF-AI with option 1
pause
goto MENU

:OPEN
cls
echo Opening SNF-AI in browser...
start http://localhost:3000
timeout /t 2 >nul
goto MENU

:LOGS
cls
echo SNF-AI Logs (last 50 lines):
echo ============================
echo.
docker logs --tail 50 twhyne
echo.
pause
goto MENU

:BACKUP
cls
echo Creating backup...
echo.

:: Create backup directory with timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set BACKUP_DIR=snf-ai-backup-%datetime:~0,8%-%datetime:~8,6%

mkdir %BACKUP_DIR% 2>nul

echo Backing up to: %BACKUP_DIR%
echo.

:: Stop container for safe backup
docker stop twhyne 2>nul

:: Export volumes
echo Backing up data...
docker run --rm -v snf_data:/source:ro -v "%CD%\%BACKUP_DIR%":/backup alpine tar czf /backup/data.tar.gz -C /source .
docker run --rm -v snf_conversations:/source:ro -v "%CD%\%BACKUP_DIR%":/backup alpine tar czf /backup/conversations.tar.gz -C /source .
docker run --rm -v snf_rag:/source:ro -v "%CD%\%BACKUP_DIR%":/backup alpine tar czf /backup/rag.tar.gz -C /source .
docker run --rm -v snf_uploads:/source:ro -v "%CD%\%BACKUP_DIR%":/backup alpine tar czf /backup/uploads.tar.gz -C /source .

:: Restart container
docker start twhyne 2>nul

echo.
echo BACKUP COMPLETE: %BACKUP_DIR%
pause
goto MENU

:EXIT
cls
echo Thank you for using SNF-AI Manager!
timeout /t 2 >nul
exit
