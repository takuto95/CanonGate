@echo off
setlocal
cd /d %~dp0

REM If port 8080 is in use, uncomment the next line to use 8081:
REM set WS_PORT=8081

echo ==============================================
echo [DEBUG MODE] Alter-Ego Launch Sequence
echo ==============================================

echo [1/3] Checking Ollama command...
where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] 'ollama' command not found in PATH.
    echo Automatic startup might fail. Please install Ollama or add to PATH.
) else (
    echo [OK] Ollama found.
)

echo [2/3] Checking Python Environment...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found or not in PATH.
    pause
    exit /b
)

echo [3/3] Starting simple_chat.py...
echo ----------------------------------------------
python simple_chat.py
echo ----------------------------------------------

echo [STOPPED] The program has exited.
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Exited with error code: %ERRORLEVEL%
)

pause
