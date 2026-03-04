@echo off
cd /d "%~dp0"
title Alter-Ego Process Manager

:: --- npm install ---
if not exist "node_modules\electron" (
    echo [System] Installing npm packages...
    call npm install
)

:: --- Check & Start Ollama ---
echo [System] Checking Ollama Status...
where ollama >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Ollama not found in PATH.
) else (
    tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
    if %ERRORLEVEL% neq 0 (
        echo [System] Starting Ollama in background...
        start /B "" ollama serve
        timeout /t 5 /nobreak >nul
    ) else (
        echo [System] Ollama is already running.
    )
)

:: --- Start Auto-Loop Engine (ALE) ---
set ALE_PATH=..\Alter-Ego\scripts\guardian\auto_loop_engine.py
set LIFE_ENV=%USERPROFILE%\.alterego\env.life

if not exist "%ALE_PATH%" (
    echo [WARNING] ALE script not found at %ALE_PATH%
    goto START_LIVETALK
)

if "%~1"=="tech" (
    echo [System] Starting ALE in TECH mode...
    start /B "ALE-Tech" python "%ALE_PATH%" --domain tech
) else if "%~1"=="life" (
    echo [System] Starting ALE in LIFE mode...
    start /B "ALE-Life" python "%ALE_PATH%" --domain life
) else (
    echo [System] Starting ALE in Dual Mode...
    start /B "ALE-Tech" python "%ALE_PATH%" --domain tech
    if exist "%LIFE_ENV%" (
        start /B "ALE-Life" python "%ALE_PATH%" --domain life
    ) else (
        echo [Info] Private env not found. Skipping LIFE domain.
    )
)

:START_LIVETALK

:: --- Start LiveTalk (Mascot + Python brain) ---
echo [System] Starting Alter-Ego Desktop...
if "%~1"=="" (
    call npm start
) else (
    call npm start -- --domain %~1
)
