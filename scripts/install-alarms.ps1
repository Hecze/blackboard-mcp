# Registers (or replaces) the "Blackboard alarmas" scheduled task for the current user (no admin): at sign-in and every
# 15 minutes it runs `blackboard-mcp alarms` without a console window. The alarm window for a pending T1/T2/EF…
# comes back after each snooze until Blackboard shows the evaluation as submitted.
#   powershell -ExecutionPolicy Bypass -File scripts\install-alarms.ps1
#   Remove:  Unregister-ScheduledTask -TaskName 'Blackboard alarmas' -Confirm:$false
$repo = Split-Path -Parent $PSScriptRoot
$pyw = Join-Path $repo '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pyw)) { throw "No encuentro $pyw. Instala el repo primero (README)." }
$action = New-ScheduledTaskAction -Execute $pyw -Argument '-m blackboard_mcp.cli alarms' -WorkingDirectory $repo
$every = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 12)
Register-ScheduledTask -TaskName 'Blackboard alarmas' -Action $action -Trigger @($every, $logon) -Settings $settings `
    -Description 'Avisa de examenes pendientes (T1, T2, EF...) hasta que se envien. blackboard-mcp alarms' -Force |
    Select-Object TaskName, State
