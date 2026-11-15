@echo off
setlocal
title MAYHEM LAB - web
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-web.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" echo [launcher] exit code %RC%
echo Window can be closed now.
pause
