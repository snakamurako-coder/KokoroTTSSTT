@echo off
title Kokoro TTS and STT Studio (Desktop)
cd /d "%~dp0"

echo [1/2] Checking Python environment...
where py >nul 2>&1
if %errorlevel%==0 (
    echo [2/2] Starting Kokoro TTS and STT Studio with Python launcher...
    py -3 main.py
) else (
    echo [2/2] Starting Kokoro TTS and STT Studio with python.exe...
    python main.py
)

if errorlevel 1 (
    echo.
    echo ========================================================
    echo Application exited with an error.
    echo If packages are missing, run:
    echo   py -3 -m pip install -r requirements.txt
    echo ========================================================
    echo.
    pause
)