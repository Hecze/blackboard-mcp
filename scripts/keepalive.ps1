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

if ($code -ne 0) {
    $msg = "Se cerró tu sesión de Blackboard (Cibertec).`n`nAbre Claude y pídele que te vuelva a conectar (bb_login), " +
           "o ejecuta:`n$exe login"
    (New-Object -ComObject WScript.Shell).Popup($msg, 0, 'CRÍTICO: Blackboard desconectado', 0x30) | Out-Null
}
