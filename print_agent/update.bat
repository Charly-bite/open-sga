@echo off
setlocal enabledelayedexpansion
title GHS Print Agent — Updater

:: ════════════════════════════════════════════════════════════════════
::  GHS Print Agent — Update Script
::  Copies the latest agent files from the source path to this folder.
::  Config (print_agent_config.json) is PRESERVED unless --reset is passed.
::
::  Usage:
::    update.bat                    — update from default source
::    update.bat --source \\server\share\Script
::    update.bat --reset            — also reset config to defaults
::    update.bat --restart          — restart agent after update
::    update.bat --source \\... --reset --restart
:: ════════════════════════════════════════════════════════════════════

:: ── Default source path ──────────────────────────────────────────────
:: Change this to your network share or developer machine path.
:: Example: \\QB-DESARROLLO\Script  or  \\192.168.2.x\Script
set "DEFAULT_SOURCE=E:\Script"

:: ── Parse arguments ───────────────────────────────────────────────────
set "SOURCE_PATH=%DEFAULT_SOURCE%"
set "RESET_CONFIG=0"
set "RESTART_AGENT=0"

:PARSE_ARGS
if "%~1"=="" goto ARGS_DONE
if /i "%~1"=="--source"  ( set "SOURCE_PATH=%~2" & shift & shift & goto PARSE_ARGS )
if /i "%~1"=="--reset"   ( set "RESET_CONFIG=1"  & shift & goto PARSE_ARGS )
if /i "%~1"=="--restart" ( set "RESTART_AGENT=1" & shift & goto PARSE_ARGS )
shift
goto PARSE_ARGS
:ARGS_DONE

:: ── Paths ─────────────────────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%SCRIPT_DIR%update_log.txt"
set "TIMESTAMP=%DATE% %TIME%"

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║        🔄  GHS Print Agent — Updater                    ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Init log ──────────────────────────────────────────────────────────
echo ════════════════════════════════════════════════════════════ >> "%LOG_FILE%"
echo  GHS Print Agent — Update Log >> "%LOG_FILE%"
echo  Date: %TIMESTAMP% >> "%LOG_FILE%"
echo  Machine: %COMPUTERNAME% >> "%LOG_FILE%"
echo  User: %USERNAME% >> "%LOG_FILE%"
echo  Target: %SCRIPT_DIR% >> "%LOG_FILE%"
echo  Source: %SOURCE_PATH% >> "%LOG_FILE%"
echo  Reset config: %RESET_CONFIG% >> "%LOG_FILE%"
echo ════════════════════════════════════════════════════════════ >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

echo    Target : %SCRIPT_DIR%
echo    Source : %SOURCE_PATH%
if "%RESET_CONFIG%"=="1" (
    echo    Config : WILL BE RESET to source defaults
) else (
    echo    Config : PRESERVED ^(local settings kept^)
)
echo.

:: ════════════════════════════════════════════════════════════════════
:: [STEP 1/4] Verify source is reachable
:: ════════════════════════════════════════════════════════════════════
echo ┌──────────────────────────────────────────────────────────┐
echo │  [STEP 1/4] Checking source path...                      │
echo └──────────────────────────────────────────────────────────┘
echo [STEP 1/4] Checking source path >> "%LOG_FILE%"

if not exist "%SOURCE_PATH%\" (
    echo    [FAIL] Source path not found or unreachable:
    echo           %SOURCE_PATH%
    echo.
    echo    If you are on the client machine, provide the network path:
    echo      update.bat --source \\QB-DESARROLLO\Script
    echo    or copy the files manually from the developer machine.
    echo.
    echo    [FAIL] Source path not found: %SOURCE_PATH% >> "%LOG_FILE%"
    goto UPDATE_FAILED
)

if not exist "%SOURCE_PATH%\print_agent.py" (
    echo    [FAIL] print_agent.py not found in source path.
    echo           Are you pointing to the right folder?
    echo    [FAIL] print_agent.py missing in source >> "%LOG_FILE%"
    goto UPDATE_FAILED
)

echo    [OK] Source reachable: %SOURCE_PATH%
echo    Source reachable >> "%LOG_FILE%"

:: ════════════════════════════════════════════════════════════════════
:: [STEP 2/4] Stop running agent (if any)
:: ════════════════════════════════════════════════════════════════════
echo.
echo ┌──────────────────────────────────────────────────────────┐
echo │  [STEP 2/4] Stopping agent (if running)...               │
echo └──────────────────────────────────────────────────────────┘
echo [STEP 2/4] Stopping agent >> "%LOG_FILE%"

:: Check if agent is running on port 5555
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5555 "') do (
    set "AGENT_PID=%%p"
)

if defined AGENT_PID (
    echo    Found agent on port 5555 ^(PID: !AGENT_PID!^) — stopping...
    taskkill /PID !AGENT_PID! /F >nul 2>&1
    timeout /t 2 /nobreak >nul
    echo    [OK] Agent stopped
    echo    Agent stopped ^(PID: !AGENT_PID!^) >> "%LOG_FILE%"
) else (
    echo    [OK] Agent was not running
    echo    Agent was not running >> "%LOG_FILE%"
)

:: ════════════════════════════════════════════════════════════════════
:: [STEP 3/4] Copy updated files
:: ════════════════════════════════════════════════════════════════════
echo.
echo ┌──────────────────────────────────────────────────────────┐
echo │  [STEP 3/4] Copying files...                             │
echo └──────────────────────────────────────────────────────────┘
echo [STEP 3/4] Copying files >> "%LOG_FILE%"

set "ERRORS_FOUND=0"

:: ── Files that are ALWAYS updated ─────────────────────────────────
set "UPDATE_FILES=print_agent.py requirements.txt"

for %%f in (%UPDATE_FILES%) do (
    if exist "%SOURCE_PATH%\%%f" (
        :: Backup old version
        if exist "%SCRIPT_DIR%%%f" (
            copy /y "%SCRIPT_DIR%%%f" "%SCRIPT_DIR%%%f.bak" >nul 2>&1
        )
        copy /y "%SOURCE_PATH%\%%f" "%SCRIPT_DIR%%%f" >nul 2>&1
        if errorlevel 1 (
            echo    [FAIL] Could not copy %%f
            echo    [FAIL] Copy failed: %%f >> "%LOG_FILE%"
            set "ERRORS_FOUND=1"
        ) else (
            for %%s in ("%SOURCE_PATH%\%%f") do set "SRC_SIZE=%%~zs"
            echo           [OK] %%f  ^(!SRC_SIZE! bytes^)
            echo    Copied: %%f >> "%LOG_FILE%"
        )
    ) else (
        echo    [WARN] %%f not found in source ^(skipped^)
        echo    [WARN] %%f not in source >> "%LOG_FILE%"
    )
)

:: ── Config: only copy if --reset or no local config exists ────────
if "%RESET_CONFIG%"=="1" (
    echo           Resetting config to source defaults...
    copy /y "%SOURCE_PATH%\print_agent_config.json" "%SCRIPT_DIR%print_agent_config.json" >nul 2>&1
    echo           [OK] print_agent_config.json reset to defaults
    echo    Config reset to source defaults >> "%LOG_FILE%"
) else (
    if not exist "%SCRIPT_DIR%print_agent_config.json" (
        copy /y "%SOURCE_PATH%\print_agent_config.json" "%SCRIPT_DIR%print_agent_config.json" >nul 2>&1
        echo           [OK] print_agent_config.json installed ^(new^)
        echo    Config installed ^(was missing^) >> "%LOG_FILE%"
    ) else (
        echo           [SKIP] print_agent_config.json preserved ^(local settings kept^)
        echo    Config preserved ^(use --reset to overwrite^) >> "%LOG_FILE%"
    )
)

:: ── Also copy bat helpers if they exist in source ─────────────────
set "BAT_FILES=start_agent.bat add_to_startup.bat list_printers.bat configure_printer.bat update.bat"
for %%f in (%BAT_FILES%) do (
    if exist "%SOURCE_PATH%\%%f" (
        copy /y "%SOURCE_PATH%\%%f" "%SCRIPT_DIR%%%f" >nul 2>&1
        if not errorlevel 1 (
            echo           [OK] %%f
            echo    Copied: %%f >> "%LOG_FILE%"
        )
    )
)

echo.
if "%ERRORS_FOUND%"=="1" (
    echo    [WARN] Some files could not be copied. Check update_log.txt.
    echo    Completed with copy errors >> "%LOG_FILE%"
) else (
    echo    [OK] All files copied successfully
    echo    All files copied OK >> "%LOG_FILE%"
)

:: ════════════════════════════════════════════════════════════════════
:: [STEP 4/4] Verify updated agent syntax
:: ════════════════════════════════════════════════════════════════════
echo.
echo ┌──────────────────────────────────────────────────────────┐
echo │  [STEP 4/4] Verifying update...                          │
echo └──────────────────────────────────────────────────────────┘
echo [STEP 4/4] Verifying >> "%LOG_FILE%"

:: Find python executable (venv first, then global)
set "PYTHON_EXE=python"
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
)

:: Syntax check
"%PYTHON_EXE%" -m py_compile "%SCRIPT_DIR%print_agent.py" >nul 2>&1
if errorlevel 1 (
    echo    [FAIL] print_agent.py has syntax errors after update!
    echo    Reverting to backup...
    if exist "%SCRIPT_DIR%print_agent.py.bak" (
        copy /y "%SCRIPT_DIR%print_agent.py.bak" "%SCRIPT_DIR%print_agent.py" >nul 2>&1
        echo    [OK] Reverted to previous version
        echo    Reverted print_agent.py to backup >> "%LOG_FILE%"
    )
    set "ERRORS_FOUND=1"
    echo    [FAIL] Syntax error in updated print_agent.py >> "%LOG_FILE%"
) else (
    echo    [OK] print_agent.py syntax valid
    echo    Syntax check: OK >> "%LOG_FILE%"
)

:: Show version/size info
for %%f in ("%SCRIPT_DIR%print_agent.py") do set "PA_SIZE=%%~zf"
echo    [OK] print_agent.py size: !PA_SIZE! bytes
echo    print_agent.py size: !PA_SIZE! bytes >> "%LOG_FILE%"

:: ════════════════════════════════════════════════════════════════════
:: Final Report
:: ════════════════════════════════════════════════════════════════════
echo.
echo ╔══════════════════════════════════════════════════════════╗
if "%ERRORS_FOUND%"=="0" (
    echo ║  ✅  Update completed successfully!                     ║
) else (
    echo ║  ⚠️   Update completed with warnings — check log        ║
)
echo ╠══════════════════════════════════════════════════════════╣
echo ║  Log saved to: update_log.txt                           ║
echo ╠══════════════════════════════════════════════════════════╣
echo ║  Next steps:                                            ║
echo ║    • Run start_agent.bat to restart the agent           ║
echo ║    • Visit http://127.0.0.1:5555 to verify              ║
echo ╚══════════════════════════════════════════════════════════╝

echo. >> "%LOG_FILE%"
if "%ERRORS_FOUND%"=="0" (
    echo Update COMPLETED OK >> "%LOG_FILE%"
) else (
    echo Update COMPLETED WITH WARNINGS >> "%LOG_FILE%"
)
echo ════════════════════════════════════════════════════════════ >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

:: ── Restart agent if requested ────────────────────────────────────
if "%RESTART_AGENT%"=="1" (
    echo.
    echo    Restarting agent...
    echo    Restart requested >> "%LOG_FILE%"
    start "" "%SCRIPT_DIR%start_agent.bat"
)

echo.
goto END

:UPDATE_FAILED
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║  ❌  Update FAILED — source not reachable               ║
echo ╠══════════════════════════════════════════════════════════╣
echo ║  Check the source path and try again:                   ║
echo ║    update.bat --source \\SERVER\ShareName               ║
echo ╚══════════════════════════════════════════════════════════╝
echo. >> "%LOG_FILE%"
echo Update FAILED >> "%LOG_FILE%"
echo ════════════════════════════════════════════════════════════ >> "%LOG_FILE%"
echo.
pause
exit /b 1

:END
echo.
pause
endlocal
