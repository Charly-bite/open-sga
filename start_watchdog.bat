@echo off
REM ============================================================
REM  SGA Server Watchdog - Inicio automatico
REM  Monitorea el share SMB y el servidor web SGA.
REM  Si alguno cae, intenta reconectar / reiniciar.
REM ============================================================

title SGA Server Watchdog

cd /d "%~dp0"

REM Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Verificar que el directorio de logs exista
if not exist "logs" mkdir logs

echo.
echo ============================================================
echo   SGA Server Watchdog
echo ============================================================
echo   Monitoreando:
echo     - Share SMB : \\192.168.2.237\SGA_Database
echo     - Web server: http://localhost:5000
echo.
echo   Logs: logs\watchdog.log
echo   Stats: logs\watchdog_stats.json
echo.
echo   Presiona Ctrl+C para detener.
echo ============================================================
echo.

:RETRY
echo [%DATE% %TIME%] Iniciando watchdog...

python watchdog.py

REM Si el watchdog sale inesperadamente, reiniciar tras 15 segundos
echo.
echo [%DATE% %TIME%] El watchdog termino inesperadamente.
echo Reiniciando en 15 segundos... (Ctrl+C para cancelar)
timeout /t 15 /nobreak
goto RETRY
