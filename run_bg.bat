@echo off
cd /d %~dp0

:: Kill old processes (Both UI and Backend)
taskkill /F /IM electron.exe /T 2>nul
taskkill /F /IM python.exe /T 2>nul

:: Create system_reports if not exists
if not exist system_reports mkdir system_reports

echo [LAUNCH] Starting EgoGate UI and Backend...
:: Start the full app (Electron will spawn simple_chat.py)
:: Redirect terminal output to log file
npm start > system_reports\latest_report.log 2>&1
