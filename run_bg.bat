@echo off
cd /d %~dp0

:: Kill old processes (Both UI and Backend)
taskkill /F /IM electron.exe /T 2>nul
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM python3.13.exe /T 2>nul

:: Create system_reports if not exists
if not exist system_reports mkdir system_reports
if not exist logs mkdir logs

:: --- Resolve Python: prefer sibling .venv ---
set PYTHON=python
if exist "%~dp0..\.venv\Scripts\python.exe" set PYTHON=%~dp0..\.venv\Scripts\python.exe

:: --- Commander API (port 8000) ---
set CANON_ROOT=..\Canon
if not exist "%CANON_ROOT%\scripts\liaison\commander_api.py" set CANON_ROOT=..\canon
if exist "%CANON_ROOT%\scripts\liaison\commander_api.py" (
    start "Commander API" cmd /c "cd /d %~dp0%CANON_ROOT% && "%PYTHON%" scripts\liaison\commander_api.py >> "%~dp0logs\commander_api.log" 2>&1"
    timeout /t 2 /nobreak >nul
)

:: --- ALE: %1 = tech / life / dual（VBS で選択した値。未指定時は tech） ---
set ALE_DOMAIN=tech
if not "%~1"=="" set ALE_DOMAIN=%~1
set ALE_PATH=%CANON_ROOT%\scripts\guardian\auto_loop_engine.py
set LIFE_ENV=%USERPROFILE%\.alterego\env.life

if exist "%ALE_PATH%" (
    if "%ALE_DOMAIN%"=="tech" (
        start /B "ALE-Tech" cmd /c "cd /d %~dp0%CANON_ROOT% && "%PYTHON%" scripts\guardian\auto_loop_engine.py --domain tech >> "%~dp0logs\ale_tech.log" 2>&1"
    ) else if "%ALE_DOMAIN%"=="life" (
        start /B "ALE-Life" cmd /c "cd /d %~dp0%CANON_ROOT% && "%PYTHON%" scripts\guardian\auto_loop_engine.py --domain life >> "%~dp0logs\ale_life.log" 2>&1"
    ) else if "%ALE_DOMAIN%"=="dual" (
        start /B "ALE-Tech" cmd /c "cd /d %~dp0%CANON_ROOT% && "%PYTHON%" scripts\guardian\auto_loop_engine.py --domain tech >> "%~dp0logs\ale_tech.log" 2>&1"
        if exist "%LIFE_ENV%" (
            start /B "ALE-Life" cmd /c "cd /d %~dp0%CANON_ROOT% && "%PYTHON%" scripts\guardian\auto_loop_engine.py --domain life >> "%~dp0logs\ale_life.log" 2>&1"
        )
    ) else (
        start /B "ALE-Tech" cmd /c "cd /d %~dp0%CANON_ROOT% && "%PYTHON%" scripts\guardian\auto_loop_engine.py --domain tech >> "%~dp0logs\ale_tech.log" 2>&1"
    )
    timeout /t 1 /nobreak >nul
)

echo [LAUNCH] Starting CanonGate UI and Backend (ALE=%ALE_DOMAIN%)...
:: Start the full app (Electron will spawn simple_chat.py). --domain で simple_chat に渡す（dual のときは tech）
set NPM_DOMAIN=%ALE_DOMAIN%
if "%NPM_DOMAIN%"=="dual" set NPM_DOMAIN=tech
npm start -- --domain %NPM_DOMAIN% > system_reports\latest_report.log 2>&1
