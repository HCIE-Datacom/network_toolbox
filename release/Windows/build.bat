@echo off
chcp 65001 >nul 2>&1
title NetTool Build

echo.
echo ============================================
echo   NetTool V100R009C00SPC500 - Build
echo ============================================
echo.

:: Use embedded Python
set PYTHON=python\python.exe
set NETTOOL_VERSION=V100R009C00SPC500
set RELEASE_NAME=NetTool-%NETTOOL_VERSION%

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
del /q "%RELEASE_NAME%.spec" 2>nul
del /q version_info_build.txt 2>nul

echo [*] Generating Windows version metadata...
"%PYTHON%" generate_version_info.py version_info_build.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to generate Windows version metadata!
    pause
    exit /b 1
)

echo [*] Building standalone app (this may take several minutes)...
%PYTHON% -m PyInstaller --name="%RELEASE_NAME%" --onefile --windowed --icon="netool.ico" --version-file="version_info_build.txt" --add-data="data;data" --add-data="templates;templates" --add-data="image_icon.png;." --collect-all modules --hidden-import="queue" --hidden-import="core.admin_helper" --hidden-import="pyftpdlib" --hidden-import="paramiko" --hidden-import="ping3" --hidden-import="PySide6" --noconfirm --clean network_toolbox.py

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
