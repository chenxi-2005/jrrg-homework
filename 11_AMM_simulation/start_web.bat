@echo off
setlocal

title AMM Exchange Simulation - Web Launcher
cd /d "%~dp0"

echo ================================================
echo   AMM Exchange Simulation - Web
echo ================================================
echo.

set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found in PATH.
        echo Please install Python 3.10+ or run this from an environment with Python available.
        echo.
        pause
        exit /b 1
    )

    echo Creating local virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        echo.
        pause
        exit /b 1
    )
)

"%PYTHON_EXE%" -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo Installing Python dependencies...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        echo.
        pause
        exit /b 1
    )
    echo.
)

echo Starting Web interface...
echo Browser will open at http://localhost:8000
echo Press Ctrl+C in this window to stop the server.
echo.

"%PYTHON_EXE%" run_web.py

echo.
echo Server stopped.
pause
