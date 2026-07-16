@echo off
cd /d "%~dp0"

:loop
echo =======================================================
echo Iniciando SGA Production Server (Waitress)...
echo =======================================================

:: Ejecutar el servidor Python
python run_production.py

:: Si el servidor falla o se cierra, el script llegará aquí
echo =======================================================
echo El servidor se cerro inesperadamente.
echo Reiniciando en 5 segundos...
echo =======================================================
timeout /t 5 /nobreak
goto loop
