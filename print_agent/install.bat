@echo off
title GHS Print Agent - Install
echo ══════════════════════════════════════════════
echo   Installing GHS Print Agent Dependencies
echo ══════════════════════════════════════════════
echo.

pip install -r "%~dp0requirements.txt"

echo.
echo ══════════════════════════════════════════════
echo   Done! Run start_agent.bat to start.
echo ══════════════════════════════════════════════
pause
