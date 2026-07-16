# ============================================================
#  Registra el SGA Server Watchdog en el Programador de Tareas
# ============================================================
param(
    [switch]$Remove   # Pasa -Remove para desinstalar la tarea
)

$TaskName  = "SGA_ServerWatchdog"
# Resolve path relative to the repo root (parent of the tools\ folder)
$RepoRoot  = Split-Path -Parent $PSScriptRoot
$BatFile   = Join-Path $RepoRoot "start_watchdog.bat"
$TaskDesc  = "Monitorea el share SMB (\\192.168.2.237\SGA_Database) y el servidor web SGA (puerto 5000). Reconecta/reinicia automaticamente cuando caen."

# ── Desinstalar ──────────────────────────────────────────────
if ($Remove) {
    Write-Host "Eliminando tarea '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarea eliminada." -ForegroundColor Green
    exit 0
}

# ── Verificar el bat ─────────────────────────────────────────
if (-not (Test-Path $BatFile)) {
    Write-Error "No se encontro el archivo: $BatFile"
    exit 1
}

# ── Construir la tarea ───────────────────────────────────────
$action = New-ScheduledTaskAction `
    -Execute  "cmd.exe" `
    -Argument "/c `"$BatFile`""

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit 0 `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId   "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel  Highest

# ── Registrar ────────────────────────────────────────────────
try {
    $task = Register-ScheduledTask `
        -TaskName   $TaskName `
        -Action     $action `
        -Trigger    $trigger `
        -Settings   $settings `
        -Principal  $principal `
        -Description $TaskDesc `
        -Force

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Tarea registrada exitosamente" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Nombre  : $($task.TaskName)"
    Write-Host "  Estado  : $($task.State)"
    Write-Host "  Trigger : Al iniciar sesion ($env:USERNAME)"
    Write-Host "  Accion  : $BatFile"
    Write-Host ""
    Write-Host "  Para verla: Programador de tareas > Biblioteca > $TaskName"
    Write-Host "  Para eliminarla: .\tools\register_watchdog_task.ps1 -Remove"
    Write-Host "============================================================" -ForegroundColor Cyan

    # Iniciar ahora sin esperar el reinicio
    $choice = Read-Host "Iniciar el watchdog ahora? (s/n)"
    if ($choice -match '^s') {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Watchdog iniciado." -ForegroundColor Green
    }

} catch {
    Write-Error "Error al registrar la tarea: $_"
    exit 1
}
