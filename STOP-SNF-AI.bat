@echo off
:: Stop SNF-AI - Just double-click!

echo Stopping SNF-AI...
docker stop twhyne
if %ERRORLEVEL% EQU 0 (
    echo SNF-AI stopped successfully
) else (
    echo SNF-AI was not running
)
pause
