@echo off
setlocal
cd /d %~dp0

echo [Cleanup] Preparing _archive folder...
if not exist _archive mkdir _archive

echo [Cleanup] Moving old files...

:: Move old batch files
move start_simple_chat.bat _archive\
move start_web_partner.bat _archive\
move start_full_avatar_chat.bat _archive\
move start_partner.bat _archive\
move temp_speech.mp3 _archive\

:: Move old python scripts
move agent_ollama.py _archive\
if exist simple_chat_v1.py move simple_chat_v1.py _archive\

:: Move LiveKit complex folder (if exists)
if exist livekit-voice-adr move livekit-voice-adr _archive\

:: Move VSeeFace (if exists)
if exist VSeeFace move VSeeFace _archive\

echo [Cleanup] Done!
echo The only important files left are:
echo   - simple_chat.py
echo   - start_full_avatar_chat.bat
echo   - mascot-web (folder)
echo.
pause
