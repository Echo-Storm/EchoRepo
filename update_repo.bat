@echo off
REM EchoRepo Maintenance - Windows Batch Wrapper
REM This script runs the Python maintenance script

echo ============================================================
echo EchoRepo Maintenance
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.6+ from https://www.python.org/
    pause
    exit /b 1
)

REM Run the maintenance script
python "%~dp0update_repo.py" %*

echo.
pause
