@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VictorOS Windows Prototype
set "PYTHONUTF8=1"

echo ==============================================================
echo   VictorOS Windows Prototype
echo   Local-first ^| Persistent ^| Governed ^| Human STOP
echo ==============================================================
echo.

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo ERROR: Python 3.10 or newer is required.
    echo Install Python from https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: VictorOS requires Python 3.10 or newer.
    %PY% --version
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating isolated Victor environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
) else (
    echo [1/3] Victor environment found.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo [2/3] Verifying dependencies...
python -m pip install --disable-pip-version-check --quiet -r requirements.txt
if errorlevel 1 goto :fail

echo [3/3] Booting Victor...
echo State:    %CD%\state
echo Interface http://127.0.0.1:8500
echo.
start "" "http://127.0.0.1:8500"
python -m streamlit run vos_ui\windows_victor.py --server.address 127.0.0.1 --server.port 8500 --server.headless true
set "RC=%ERRORLEVEL%"

echo.
echo VictorOS stopped with code %RC%.
pause
exit /b %RC%

:fail
echo.
echo VictorOS bootstrap FAILED. No state files were intentionally deleted.
pause
exit /b 1
