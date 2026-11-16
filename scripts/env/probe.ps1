# Describe this Windows machine for an agent: architecture, language, OS, runtimes and the course tools
# that are already installed. Read-only. Works in Windows PowerShell 5.1 and PowerShell 7.
#   powershell -ExecutionPolicy Bypass -File scripts\env\probe.ps1          # table
#   powershell -ExecutionPolicy Bypass -File scripts\env\probe.ps1 -Json    # JSON (for agents)
param([switch]$Json)

function First-Line($exe, [string[]]$argv) {
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $cmd) { return $null }
    try { return ((& $cmd.Source @argv 2>&1 | Select-Object -First 1) | Out-String).Trim() } catch { return $null }
}

$os = Get-CimInstance Win32_OperatingSystem
$home_ = $env:USERPROFILE
$uv = Get-Command uv -ErrorAction SilentlyContinue
$py314 = $null
if ($uv) { $py314 = (& $uv.Source python find 3.14 2>$null | Select-Object -First 1) }
$pkgs = @(Get-Package -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'SQL Server 20\d\d \(64-bit\)|Microsoft SQL Server 20\d\d$|Management Studio|yEd|OpenJDK|Microsoft Office|Microsoft 365|Graphviz' } |
    ForEach-Object { "$($_.Name) $($_.Version)".Trim() } | Sort-Object -Unique)
$svc = Get-Service -Name 'MSSQLSERVER', 'MSSQL$SQLEXPRESS' -ErrorAction SilentlyContinue | Select-Object -First 1

# Real CPU architecture. $env:PROCESSOR_ARCHITECTURE is the *process* architecture: an x64 PowerShell running
# emulated on an ARM64 PC reports AMD64, so read the processor instead (Win32_Processor.Architecture: 9 = x64, 12 = ARM64).
$cpuArch = switch ((Get-CimInstance Win32_Processor | Select-Object -First 1).Architecture) {
    9 { 'AMD64' } 12 { 'ARM64' } 5 { 'ARM' } 0 { 'x86' } default { $env:PROCESSOR_ARCHITECTURE } }

$r = [ordered]@{
    arch               = $cpuArch                           # AMD64 (x86_64) or ARM64 — the machine
    process_arch       = $env:PROCESSOR_ARCHITECTURE        # differs from arch => this shell runs emulated
    ui_culture         = [System.Globalization.CultureInfo]::CurrentUICulture.Name
    os                 = "$($os.Caption) $($os.Version)"
    is_admin           = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    winget             = First-Line 'winget' @('--version')
    python             = First-Line 'python' @('--version')
    uv                 = First-Line 'uv' @('--version')
    python_3_14_via_uv = $py314
    node               = First-Line 'node' @('--version')
    java_on_path       = First-Line 'java' @('-version')
    jdk_arm64_tools    = Test-Path "$home_\tools\jdk-21-arm64\bin\javaw.exe"
    yed_jar            = Test-Path "$home_\yEd\yed.jar"
    sql_service        = if ($svc) { "$($svc.Name) $($svc.Status)" } else { $null }
    sqlcmd             = (Get-Command sqlcmd -ErrorAction SilentlyContinue).Source
    edge               = Test-Path "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    installed          = $pkgs
}
if ($Json) { $r | ConvertTo-Json -Depth 3 } else { [pscustomobject]$r | Format-List }
