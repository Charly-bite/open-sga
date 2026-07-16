$scriptDir = $PSScriptRoot
$batchPath = Join-Path -Path $scriptDir -ChildPath "run_server_loop.bat"

# Crear la acción para ejecutar el archivo batch de manera oculta
$action = New-ScheduledTaskAction -Execute "$batchPath"
# Configurar que corra siempre al arrancar el sistema
$trigger = New-ScheduledTaskTrigger -AtStartup

# Opciones recomendadas: no detener si se usa batería, reiniciar si falla el host (aunque el batch ya hace loop), etc.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Days 0)

Write-Host "Registrando tarea programada: SGA_Production_Server..."
# Registrar la tarea como el SYSTEM para que no requiera sesión iniciada y se ejecute silenciosamente de fondo
Register-ScheduledTask -TaskName "SGA_Production_Server" -Action $action -Trigger $trigger -Settings $settings -User "NT AUTHORITY\SYSTEM" -RunLevel Highest -Force

Write-Host "La tarea se ha registrado exitosamente."
Write-Host "Ahora el servidor se iniciara automaticamente cada vez que se encienda la computadora y se reiniciara automaticamente si presenta fallos."
Write-Host "Puede iniciarla manualmente ahora ejecutando: Start-ScheduledTask -TaskName SGA_Production_Server"
