@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    echo 未找到 .venv 虚拟环境。
    echo 请先在 PowerShell 中运行：
    echo powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install.ps1
    pause
)
