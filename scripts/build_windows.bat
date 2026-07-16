@echo off
REM ============================================================================
REM Build script for GHS Label System (SGA) - Windows Executable
REM ============================================================================
REM This script creates a standalone .exe file for Windows
REM 
REM Prerequisites:
REM   1. Python 3.8+ installed
REM   2. pip install pyinstaller pillow pandas reportlab openpyxl
REM
REM Usage: Run this script from the project directory
REM ============================================================================

echo.
echo ========================================
echo   GHS Label System - Windows Build
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

REM Install/upgrade required packages
echo.
echo [2/4] Installing build dependencies...
pip install --upgrade pyinstaller pillow pandas reportlab openpyxl hdbcli

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Clean previous builds
echo.
echo [3/4] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
if exist "SGA_GHS_Labels.exe" del /f SGA_GHS_Labels.exe

REM Build the executable
echo.
echo [4/4] Building executable...
echo This may take a few minutes...
echo.

python -m PyInstaller sga_app.spec --clean

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo Check the error messages above.
    pause
    exit /b 1
)

REM Check if exe was created
if exist "dist\SGA_GHS_Labels.exe" (
    echo.
    echo ========================================
    echo   BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Executable created at:
    echo   dist\SGA_GHS_Labels.exe
    echo.
    echo You can now distribute this file.
    echo The exe includes all dependencies.
    echo.
    
    REM Copy to root for convenience
    copy "dist\SGA_GHS_Labels.exe" "SGA_GHS_Labels.exe" >nul
    echo Also copied to: SGA_GHS_Labels.exe
    echo.
) else (
    echo.
    echo ERROR: Executable was not created
    echo Check the build output for errors.
)

pause
