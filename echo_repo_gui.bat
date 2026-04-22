@echo off
REM EchoRepo Manager - GUI Launcher
REM Requires Python 3.10+ and PyQt6

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo PyQt6 not found. Installing...
    pip install PyQt6
    if errorlevel 1 (
        echo ERROR: PyQt6 install failed. Run manually: pip install PyQt6
        pause
        exit /b 1
    )
)

start "" pythonw echo_repo_gui.py
