@echo off
echo ===================================
echo   MacroMaster Pro - Launcher
echo ===================================
echo.

:: Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/2] Installing dependencies...
pip install pynput pyautogui pyperclip --quiet
IF ERRORLEVEL 1 (
    echo [WARN] pip install failed. Try: pip install pynput manually.
)

echo [2/2] Starting MacroMaster Pro...
echo.
python macro_app.py

pause
