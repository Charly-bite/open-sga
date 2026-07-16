@echo off
echo =========================================================
echo Disabling Old SGA Services (Pre-Production and Watchdog)
echo =========================================================

:: Require Admin privileges
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo [ERROR] Administrator privileges required.
    echo Please right-click this script and select "Run as Administrator".
    pause
    exit /b 1
)

echo Stopping SGA_Watchdog service...
nssm stop SGA_Watchdog >nul 2>&1
net stop SGA_Watchdog >nul 2>&1
sc config SGA_Watchdog start= disabled >nul 2>&1

echo Stopping SGA_PreProd service...
nssm stop SGA_PreProd >nul 2>&1
net stop SGA_PreProd >nul 2>&1
sc config SGA_PreProd start= disabled >nul 2>&1

echo Killing any lingering watchdog or Python waitress/flask processes...
taskkill /F /IM python.exe /T >nul 2>&1

echo.
echo =========================================================
echo Done! Old production footprint has been stripped.
echo The new server will not be interfered with.
echo =========================================================
pause
