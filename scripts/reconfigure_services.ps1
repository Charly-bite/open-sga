# Reconfigure SGA services via registry (bypassing nssm path issues)
# Must be run as Administrator

$sgaProdRoot = 'C:\Users\QB_DESARROLLO\Desktop\SGA PROD'
$pythonExe   = "$sgaProdRoot\.venv\Scripts\python.exe"

$regBase = 'HKLM:\SYSTEM\CurrentControlSet\Services'

# --- SGA_PreProd ---
$params = "$regBase\SGA_PreProd\Parameters"
Set-ItemProperty -Path $params -Name 'Application'    -Value $pythonExe
Set-ItemProperty -Path $params -Name 'AppDirectory'   -Value "$sgaProdRoot\sga_web"
Set-ItemProperty -Path $params -Name 'AppParameters'  -Value "$sgaProdRoot\sga_web\run_production.py"

# --- SGA_Watchdog ---
$params = "$regBase\SGA_Watchdog\Parameters"
Set-ItemProperty -Path $params -Name 'Application'    -Value $pythonExe
Set-ItemProperty -Path $params -Name 'AppDirectory'   -Value $sgaProdRoot
Set-ItemProperty -Path $params -Name 'AppParameters'  -Value "$sgaProdRoot\watchdog.py"

# --- Start services ---
Start-Service SGA_PreProd  -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5
Start-Service SGA_Watchdog -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

# --- Output verification ---
$pp = Get-ItemProperty "$regBase\SGA_PreProd\Parameters"
$wd = Get-ItemProperty "$regBase\SGA_Watchdog\Parameters"

"=== SGA_PreProd ==="
"  Application:   $($pp.Application)"
"  AppDirectory:  $($pp.AppDirectory)"
"  AppParameters: $($pp.AppParameters)"
"  Status:        $((Get-Service SGA_PreProd).Status)"
""
"=== SGA_Watchdog ==="
"  Application:   $($wd.Application)"
"  AppDirectory:  $($wd.AppDirectory)"
"  AppParameters: $($wd.AppParameters)"
"  Status:        $((Get-Service SGA_Watchdog).Status)"
""
"DONE"

# Write results to a temp file so we can read it back
$output = @"
PreProd_App=$($pp.Application)
PreProd_Dir=$($pp.AppDirectory)
PreProd_Params=$($pp.AppParameters)
PreProd_Status=$((Get-Service SGA_PreProd).Status)
Watchdog_App=$($wd.Application)
Watchdog_Dir=$($wd.AppDirectory)
Watchdog_Params=$($wd.AppParameters)
Watchdog_Status=$((Get-Service SGA_Watchdog).Status)
"@
$output | Out-File "$sgaProdRoot\scripts\.service_result.txt" -Encoding utf8
