@echo off
cd /d "%~dp0"
echo Downloading VRM model to mascot-web\test.vrm ...
python scripts\download_vrm.py
echo.
pause
