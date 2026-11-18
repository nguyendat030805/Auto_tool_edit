@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Chua cai Python. Hay cai tu python.org va tick "Add Python to PATH".
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo Chua cai ffmpeg. Mo PowerShell chay: winget install ffmpeg  roi mo lai file nay.
  pause
  exit /b 1
)

if not exist .venv (
  echo Lan dau chay: dang tao moi truong va cai thu vien, vui long doi...
  python -m venv .venv
  call .venv\Scripts\activate
  python -m pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)

python app.py
pause
