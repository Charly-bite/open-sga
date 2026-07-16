@echo off
echo Attempting to connect to SGA Database...
net use \\192.168.2.237\SGA_Database /user:sga_user SGA2026! /PERSISTENT:YES
if %errorlevel% equ 0 (
    echo Connection successful!
) else (
    echo Connection failed using explicit credentials. Checking if already connected...
    if exist \\192.168.2.237\SGA_Database (
        echo Share is accessible.
    ) else (
        echo Share is NOT accessible.
        pause
    )
)
echo Starting SGA Web Application...
.venv\Scripts\python.exe app.py
pause
