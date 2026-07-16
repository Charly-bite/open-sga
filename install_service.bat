@echo off
echo ==================================================
echo Installing SGA Pre-Production Server Windows Service
echo ==================================================

:: Require Admin privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Administrator privileges confirmed.
) else (
    echo Failure: Please run this script as Administrator.
    pause
    exit /b 1
)

:: Install NSSM if not present
where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo NSSM not found. Installing via winget...
    winget install nssm --accept-package-agreements --accept-source-agreements
    if %errorLevel% neq 0 (
        echo Failed to install NSSM automatically. Please install it manually.
        pause
        exit /b 1
    )
)

set SERVICE_NAME="SGA_PreProd"
set APP_DIR=%~dp0
set EXECUTABLE=python.exe
set SCRIPT_NAME=sga_web\run_production.py

echo Stopping and removing existing service if it exists...
nssm stop %SERVICE_NAME% >nul 2>&1
nssm remove %SERVICE_NAME% confirm >nul 2>&1

echo Installing Service: %SERVICE_NAME%...
nssm install %SERVICE_NAME% "%EXECUTABLE%" "%APP_DIR%%SCRIPT_NAME%"
nssm set %SERVICE_NAME% AppDirectory "%APP_DIR%"
nssm set %SERVICE_NAME% DisplayName "SGA Pre-Production Web Server"
nssm set %SERVICE_NAME% Description "Host service for the QuimicaBoss Sistema de Gestion de Almacen (SGA)"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% AppStdout "%APP_DIR%logs\service.log"
nssm set %SERVICE_NAME% AppStderr "%APP_DIR%logs\service_error.log"

echo Setup complete. Starting the service...
nssm start %SERVICE_NAME%

echo.
echo Service %SERVICE_NAME% status:
sc query %SERVICE_NAME% | findstr "STATE"

pause
