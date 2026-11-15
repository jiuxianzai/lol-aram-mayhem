@echo off
setlocal
title MAYHEM LAB - web
cd /d "%~dp0"

rem Double-click to start the web app. Closing this window stops the server.
rem The real work is in start-web.ps1; add -Port 5180 to change the port.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-web.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" echo [launcher] exit code %RC%
echo Server stopped. You can close this window.
pause
