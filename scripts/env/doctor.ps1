# Check that everything this repo relies on works, and say how to fix what doesn't. Read-only.
#   powershell -ExecutionPolicy Bypass -File scripts\env\doctor.ps1
# Exit code: 0 = all required checks pass, 1 = something required is missing.
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$p = & "$PSScriptRoot\probe.ps1" -Json | ConvertFrom-Json
$arm = $p.arch -eq 'ARM64'
$rows = New-Object System.Collections.Generic.List[object]
function Check($area, $name, [bool]$ok, $fix, [switch]$Optional) {
    $state = if ($ok) { 'OK' } elseif ($Optional) { 'opcional' } else { 'FALTA' }
    $rows.Add([pscustomobject]@{ Area = $area; Check = $name; Estado = $state; Arreglo = $(if ($ok) { '' } else { $fix }) })
}

# Blackboard MCP (this repo)
$venv = Test-Path "$repo\.venv\Scripts\blackboard-mcp.exe"
Check 'Blackboard' 'MCP instalado en .venv' $venv 'python -m venv .venv; .venv\Scripts\pip install -e .   (en ARM64: pip install --only-binary=:all: cryptography primero)'
$cfg = Join-Path $env:USERPROFILE '.blackboard-mcp\config.json'
Check 'Blackboard' 'config.json (base_url)' (Test-Path $cfg) 'Crear ~/.blackboard-mcp/config.json con {"base_url": "https://<tu-universidad>.blackboard.com"}'
$health = Join-Path $env:USERPROFILE '.blackboard-mcp\session-health.json'
$hok = $false; if (Test-Path $health) { try { $hok = [bool](Get-Content $health -Raw | ConvertFrom-Json).ok } catch {} }
Check 'Blackboard' 'sesion viva (session-health.json)' $hok '.venv\Scripts\blackboard-mcp.exe login   (el estudiante inicia sesion en la ventana)'
$task = Get-ScheduledTask -TaskName 'Blackboard keep-alive' -ErrorAction SilentlyContinue
Check 'Blackboard' 'tarea keep-alive' ([bool]$task) 'powershell -File scripts\install-keepalive.ps1'

# SQL Server
$sqlOk = $false
if ($p.sqlcmd) { & $p.sqlcmd -S localhost -E -C -l 5 -Q "SELECT 1" -h -1 2>$null | Out-Null; $sqlOk = ($LASTEXITCODE -eq 0) }
Check 'SQL Server' 'servicio' ([bool]$p.sql_service -and $p.sql_service -match 'Running') 'scripts\env\install-sqlserver.ps1 (como administrador)'
Check 'SQL Server' 'sqlcmd conecta con tu usuario de Windows' $sqlOk 'scripts\env\sql-login.ps1 -Grant (una vez, como administrador)'
Check 'SQL Server' 'SSMS' ([bool]($p.installed | Where-Object { $_ -match 'Management Studio' })) 'scripts\env\install-ssms.ps1' -Optional

# yEd
if ($arm) {
    Check 'yEd' 'yed.jar' $p.yed_jar 'winget install yWorks.yEd (o el instalador de yWorks)'
    Check 'yEd' 'JDK ARM64 (~\tools\jdk-21-arm64)' $p.jdk_arm64_tools 'scripts\env\install-yed-arm64.ps1'
} else {
    Check 'yEd' 'yEd instalado' ([bool]($p.installed | Where-Object { $_ -match 'yEd' }) -or $p.yed_jar) 'winget install yWorks.yEd' -Optional
}

# Python tools
$py = "$repo\.venv\Scripts\python.exe"
$pdfOk = $false; if (Test-Path $py) { & $py -c "import pymupdf" 2>$null; $pdfOk = ($LASTEXITCODE -eq 0) }
Check 'PDF' 'PyMuPDF en .venv' $pdfOk '.venv\Scripts\pip install "pymupdf==1.28.2"   (2.x no trae binario ARM64)' -Optional

# Desktop automation (Windows-MCP)
Check 'Escritorio' 'uv' ([bool]$p.uv) 'pip install uv' -Optional
Check 'Escritorio' 'Python 3.14 (para Windows-MCP)' ([bool]$p.python_3_14_via_uv) 'uv python install 3.14' -Optional

"Maquina: $($p.arch) | $($p.os) | idioma $($p.ui_culture) | admin=$($p.is_admin)"
$rows | Format-Table -AutoSize -Wrap | Out-String -Width 220
if ($rows | Where-Object Estado -eq 'FALTA') { exit 1 } else { exit 0 }
