@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
if not defined HOST set HOST=127.0.0.1
if not defined PORT set PORT=8765
if defined PYTHON_EXE goto custom_python
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3.9+ was not found. Install Python or set PYTHON_EXE to python.exe.
pause
exit /b 1
:custom_python
"%PYTHON_EXE%" server.py
goto finished
:use_py
py -3 server.py
goto finished
:use_python
python server.py
:finished
echo.
echo Server stopped. Keep this window open while using Hehu.
echo If startup failed, read the error above.
pause
