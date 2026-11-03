@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap-windows.ps1"
set "HEHU_EXIT=%ERRORLEVEL%"
echo.
echo Hehu has stopped. If startup failed, read the error above.
pause
exit /b %HEHU_EXIT%
