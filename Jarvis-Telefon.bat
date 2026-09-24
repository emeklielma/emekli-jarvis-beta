@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Jarvis Telefon
set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
echo Gerekli paketler kontrol ediliyor...
"%PY%" -m pip install -q numpy soundfile edge-tts SpeechRecognition python-dotenv
"%PY%" -m pip install -q audioop-lts standard-aifc 2>nul
"%PY%" jarvis_telefon.py
pause
