#!/bin/bash
echo "==================================="
echo "  MacroMaster Pro - Launcher"
echo "==================================="
echo

# Check python3
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found."
    echo "Install via: sudo apt install python3  OR  brew install python"
    exit 1
fi

echo "[1/2] Installing dependencies..."
pip3 install pynput pyautogui pyperclip --quiet 2>/dev/null || \
pip3 install pynput pyautogui pyperclip --break-system-packages --quiet 2>/dev/null || \
echo "[WARN] pip install failed — run: pip3 install pynput pyautogui pyperclip"

echo "[2/2] Starting MacroMaster Pro..."
echo
python3 macro_app.py
