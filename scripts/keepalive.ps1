# Keeps the Blackboard (and its Microsoft SSO) session alive. Run by the "Blackboard keep-alive"
# scheduled task; see scripts/install-keepalive.ps1. On failure it pops up a warning straight away.
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$exe  = Join-Path $repo '.venv\Scripts\blackboard-mcp.exe'
$log  = Join-Path $HOME '.blackboard-mcp\keepalive.log'

$out = & $exe refresh 2>&1 | Out-String
$code = $LASTEXITCODE
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Add-Content -Path $log -Encoding utf8 -Value "$stamp exit=$code $($out -replace '\s+', ' ')"

# Keep the log small.
$lines = Get-Content $log -ErrorAction SilentlyContinue
if ($lines.Count -gt 500) { $lines | Select-Object -Last 300 | Set-Content $log -Encoding utf8 }

# Exit codes of `blackboard-mcp refresh`: 0 renewed, 2 sign-in needed, 3 Blackboard unreachable (network), 1 other.
$shell = New-Object -ComObject WScript.Shell
switch ($code) {
    0 { }
    2 {
        $msg = "Se cerró tu sesión de Blackboard (Cibertec).`n`nAbre tu agente y pídele que te vuelva a conectar (bb_login), " +
               "o ejecuta:`n$exe login"
        $shell.Popup($msg, 0, 'CRÍTICO: Blackboard desconectado', 0x30) | Out-Null
    }
    3 {
        $msg = "Blackboard no responde desde esta red, pero tu sesión no se cerró.`n`n" +
               "Revisa tu internet: si estás en Wi-Fi, prueba con los datos del celular o reinicia el router. " +
               "Se volverá a intentar solo en unas horas."
        $shell.Popup($msg, 0, 'Blackboard no responde', 0x40) | Out-Null
    }
    default {
        $msg = "La renovación automática de Blackboard falló por un error técnico (no por tu contraseña).`n`n" +
               "Pídele a tu agente que revise:`n$log"
        $shell.Popup($msg, 0, 'Blackboard: error al renovar la sesión', 0x30) | Out-Null
    }
}
