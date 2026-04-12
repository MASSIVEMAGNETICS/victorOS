@echo off
echo [VOS SETUP] Initializing environment for Windows 10...
python --version >nul 2>&1 || (
    echo ERROR: Python 3.10+ not found. Install from python.org
    pause
    exit /b 1
)
pip install -r requirements.txt --quiet
echo [VOS SETUP] Dependencies resolved.
echo.
echo [VOS SETUP] Choose launch mode:
echo   1) Creator Dashboard  (http://localhost:8501)
echo   2) Admin Portal       (http://localhost:8502)
echo   3) Both
set /p MODE="Enter 1, 2, or 3: "

if "%MODE%"=="1" (
    echo [VOS] Launching Creator Dashboard...
    streamlit run vos_ui/dashboard.py --server.headless true --server.port 8501
)
if "%MODE%"=="2" (
    echo [VOS] Launching Admin Portal...
    streamlit run vos_ui/admin_portal.py --server.headless true --server.port 8502
)
if "%MODE%"=="3" (
    echo [VOS] Launching Creator Dashboard on port 8501...
    start cmd /k "streamlit run vos_ui/dashboard.py --server.headless true --server.port 8501"
    echo [VOS] Launching Admin Portal on port 8502...
    streamlit run vos_ui/admin_portal.py --server.headless true --server.port 8502
)
pause
