@echo off
chcp 65001 >nul 2>&1
title NetTool Setup

echo.
echo ============================================
echo   NetTool V100R008C00SPC600 - Setup
echo ============================================
echo.

echo [*] Installing pip into embedded Python...
cd python
python.exe get-pip.py --no-warn-script-location
if errorlevel 1 (
    cd ..
    echo [ERROR] pip install failed
    pause
    exit /b 1
)
cd ..

echo.
echo [*] Installing all dependencies...
python\python.exe -m pip install --no-index --find-links=wheels PySide6 pyftpdlib ping3 paramiko pyinstaller
if errorlevel 1 (
    echo [ERROR] Install failed
    pause
    exit /b 1
)
echo.
echo [OK] All packages installed.

echo.
echo ============================================
echo   Setup complete! Now run: build.bat
echo ============================================
echo.
pause
