@echo off
title GHS Print Agent
echo ══════════════════════════════════════════════
echo   Starting GHS Print Agent...
echo ══════════════════════════════════════════════
echo.

:: Check if Python is available
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Install Python from https://python.org
    pause
    exit /b 1
)

:: Check/install dependencies
echo Checking dependencies...
pip show flask >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r "%~dp0requirements.txt"
)

:: Start the agent
cd /d "%~dp0"
python print_agent.py %*

pause
