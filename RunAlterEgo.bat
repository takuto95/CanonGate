@echo off
cd /d "%~dp0"
title CanonGate Process Manager

:: --- ログディレクトリを作成 ---
if not exist "logs" mkdir logs
set STARTUP_LOG=logs\startup.log
echo [%DATE% %TIME%] === CanonGate Starting === > "%STARTUP_LOG%"

:: --- npm install ---
if not exist "node_modules\electron" (
    echo [System] Installing npm packages... >> "%STARTUP_LOG%"
    call npm install >> "%STARTUP_LOG%" 2>&1
)

:: --- Check & Start Ollama ---
echo [System] Checking Ollama Status... >> "%STARTUP_LOG%"
where ollama >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Ollama not found in PATH. >> "%STARTUP_LOG%"
) else (
    tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
    if %ERRORLEVEL% neq 0 (
        echo [System] Starting Ollama in background... >> "%STARTUP_LOG%"
        start /B "" ollama serve >> "logs\ollama.log" 2>&1
        timeout /t 5 /nobreak >nul
    ) else (
        echo [System] Ollama is already running. >> "%STARTUP_LOG%"
    )
)

:: --- Start Commander API (port 8000: Hub & CanonGate config) ---
set CANON_ROOT=..\Canon
if not exist "%CANON_ROOT%\scripts\liaison\commander_api.py" set CANON_ROOT=..\canon
if exist "%CANON_ROOT%\scripts\liaison\commander_api.py" (
    echo [System] Starting Commander API on port 8000... >> "%STARTUP_LOG%"
    start "Commander API" cmd /c "cd /d %~dp0%CANON_ROOT% && python scripts\liaison\commander_api.py >> "%~dp0logs\commander_api.log" 2>&1"
    timeout /t 2 /nobreak >nul
) else (
    echo [WARNING] Commander API not found. Expected: %CANON_ROOT%\scripts\liaison\commander_api.py >> "%STARTUP_LOG%"
)

:: --- Start Auto-Loop Engine (ALE) ---
set ALE_PATH=%CANON_ROOT%\scripts\guardian\auto_loop_engine.py
set LIFE_ENV=%USERPROFILE%\.alterego\env.life

if not exist "%ALE_PATH%" (
    echo [WARNING] ALE script not found at %ALE_PATH% >> "%STARTUP_LOG%"
    goto START_LIVETALK
)

if "%~1"=="tech" (
    echo [System] Starting ALE in TECH mode (work only)... >> "%STARTUP_LOG%"
    start /B "ALE-Tech" python "%ALE_PATH%" --domain tech >> "logs\ale_tech.log" 2>&1
) else if "%~1"=="life" (
    echo [System] Starting ALE in LIFE mode (private only)... >> "%STARTUP_LOG%"
    start /B "ALE-Life" python "%ALE_PATH%" --domain life >> "logs\ale_life.log" 2>&1
) else if "%~1"=="dual" (
    echo [System] Starting ALE in Dual Mode (tech + life)... >> "%STARTUP_LOG%"
    start /B "ALE-Tech" python "%ALE_PATH%" --domain tech >> "logs\ale_tech.log" 2>&1
    if exist "%LIFE_ENV%" (
        start /B "ALE-Life" python "%ALE_PATH%" --domain life >> "logs\ale_life.log" 2>&1
    ) else (
        echo [Info] Private env not found. Skipping LIFE domain. >> "%STARTUP_LOG%"
    )
) else (
    :: デフォルト: 仕事（tech）のみ。life も使う場合は RunAlterEgo.bat dual
    echo [System] Starting ALE in TECH mode (work only, default)... >> "%STARTUP_LOG%"
    start /B "ALE-Tech" python "%ALE_PATH%" --domain tech >> "logs\ale_tech.log" 2>&1
)

:START_LIVETALK

:: --- Start LiveTalk (Mascot + Python brain) ---
echo [System] Starting CanonGate Desktop... >> "%STARTUP_LOG%"
if "%~1"=="" (
    npm start 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath 'logs\electron.log' -Append"
) else (
    npm start -- --domain %~1 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath 'logs\electron.log' -Append"
)
