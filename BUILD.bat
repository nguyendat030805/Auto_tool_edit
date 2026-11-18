
@echo off
title BUILD COMMENT VIDEO

cd /d "%~dp0"

echo =================================
echo    DANG DONG GOI COMMENT VIDEO
echo =================================

if not exist ".venv\Scripts\python.exe" (
    echo Khong tim thay moi truong Python!
    pause
    exit /b 1
)

rmdir /s /q build 2>nul

.venv\Scripts\python.exe -m PyInstaller ^
--clean ^
--noconfirm ^
--onefile ^
--console ^
--name app ^
--add-data "jobs;jobs" ^
--add-data "services;services" ^
--add-data "templates;templates" ^
--add-data "web;web" ^
--add-data "make_video.py;." ^
--add-data "post_template.py;." ^
app.py

if errorlevel 1 (
    echo DONG GOI THAT BAI!
    pause
    exit /b 1
)

echo =================================
echo DONG GOI THANH CONG!
echo File: dist\app.exe
echo =================================

pause
