@echo off
setlocal
cd /d %~dp0
echo [Mascot] Starting local web server on port 8000...
start "Mascot Web Server" /MIN python -m http.server 8000
echo Waiting for server to be ready...
timeout /t 2 /nobreak >nul
echo Opening browser at http://localhost:8000
start http://localhost:8000
echo.
echo Mascot UI is open. Keep this window; close the "Mascot Web Server" window when done.
pause
