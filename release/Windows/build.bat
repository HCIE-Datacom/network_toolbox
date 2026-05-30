@echo off
chcp 65001 >nul 2>&1
title NetTool Build

echo.
echo ============================================
echo   NetTool V100R008C00SPC700 - Build
echo ============================================
echo.

:: Use embedded Python
set PYTHON=python\python.exe
set RELEASE_NAME=NetTool-V100R008C00SPC700

if not exist "%PYTHON%" (
    echo [ERROR] Embedded Python not found.
    echo         Run setup.bat first!
    pause
    exit /b 1
)

echo [OK] Using embedded Python

echo.
echo [*] Cleaning old build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q NetTool.spec 2>nul

echo [*] Building standalone app (this may take several minutes)...
%PYTHON% -m PyInstaller --name="%RELEASE_NAME%" --onefile --windowed --uac-admin --icon="netool.ico" --version-file="version_info.txt" --add-data="data;data" --add-data="templates;templates" --add-data="image_icon.png;." --collect-all modules --hidden-import="queue" --hidden-import="pyftpdlib" --hidden-import="paramiko" --hidden-import="ping3" --hidden-import="PySide6" --noconfirm --clean network_toolbox.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo.
echo   Output: dist\%RELEASE_NAME%.exe
echo ============================================
echo.
pause
