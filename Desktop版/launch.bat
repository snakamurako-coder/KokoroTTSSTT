@echo off
chcp 65001 >nul
title Kokoro TTS & STT Studio (Desktop)
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 main.py
) else (
    python main.py
)

if errorlevel 1 (
    echo.
    echo ========================================================
    echo アプリの起動に失敗しました。
    echo 依存ライブラリの不足が疑われる場合は、以下を実行してください:
    echo   py -3 -m pip install -r requirements.txt
    echo ========================================================
    echo.
    pause
)
