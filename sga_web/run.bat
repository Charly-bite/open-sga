@echo off
REM ============================================
REM SGA Web Application - Windows Startup Script
REM ============================================

echo.
echo ======================================
echo   SGA Web Application
echo   Sistema Global Armonizado v1.0
echo ======================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Por favor instale Python 3.10+
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install/update dependencies
echo Verificando dependencias...
pip install -q -r requirements.txt

REM Start the application
echo.
echo Iniciando servidor web...
echo.
echo ================================================
echo   Abra su navegador en: http://localhost:5000
echo   Credenciales: admin / admin123
echo ================================================
echo.
echo Presione Ctrl+C para detener el servidor
echo.

python app.py

pause
