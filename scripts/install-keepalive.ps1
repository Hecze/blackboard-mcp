# Registers (or replaces) the "Blackboard keep-alive" scheduled task for the current user:
# at sign-in and every 4 hours, it silently renews the Blackboard session (scripts/keepalive.ps1).
$script = Join-Path $PSScriptRoot 'keepalive.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$every4h = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 4)
$logon   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'Blackboard keep-alive' -Action $action -Trigger @($every4h, $logon) `
    -Settings $settings -Description 'Renueva en silencio la sesión de Blackboard de Cibertec (blackboard-mcp).' -Force |
    Select-Object TaskName, State
