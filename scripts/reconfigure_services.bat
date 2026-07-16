@echo off
echo === Reconfiguring SGA Services ===

set NSSM=C:\Users\QB_DESARROLLO\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_Microsoft.Winget.Source_8wekyb3d8bbwe\nssm-2.24-101-g897c7ad\win64\nssm.exe
set PYTHON=C:\Users\QB_DESARROLLO\Desktop\SGA PROD\.venv\Scripts\python.exe
set ROOT=C:\Users\QB_DESARROLLO\Desktop\SGA PROD

echo.
echo [1/2] Configuring SGA_PreProd...
"%NSSM%" set SGA_PreProd Application "%PYTHON%"
"%NSSM%" set SGA_PreProd AppDirectory "%ROOT%\sga_web"
"%NSSM%" set SGA_PreProd AppParameters "%ROOT%\sga_web\run_production.py"

echo.
echo [2/2] Configuring SGA_Watchdog...
"%NSSM%" set SGA_Watchdog Application "%PYTHON%"
"%NSSM%" set SGA_Watchdog AppDirectory "%ROOT%"
"%NSSM%" set SGA_Watchdog AppParameters "%ROOT%\watchdog.py"

echo.
echo Starting services...
"%NSSM%" start SGA_PreProd
timeout /t 5 /nobreak >nul
"%NSSM%" start SGA_Watchdog
timeout /t 3 /nobreak >nul

echo.
echo === Verifying ===
"%NSSM%" status SGA_PreProd
"%NSSM%" get SGA_PreProd Application
"%NSSM%" get SGA_PreProd AppDirectory
"%NSSM%" get SGA_PreProd AppParameters
echo ---
"%NSSM%" status SGA_Watchdog
"%NSSM%" get SGA_Watchdog Application
"%NSSM%" get SGA_Watchdog AppDirectory
"%NSSM%" get SGA_Watchdog AppParameters

echo.
echo DONE!
pause
