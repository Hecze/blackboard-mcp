# Install SQL Server with winget. Must be run by the student in an ELEVATED PowerShell (UAC) — agents never
# hold admin rights. Default media language is en-US: on a Spanish (es-ES) Windows the es-ES media failed
# with a language-mismatch dialog while the English (ENU) media installed fine.
#   powershell -ExecutionPolicy Bypass -File scripts\env\install-sqlserver.ps1 [-Version 2025|2022] [-Edition Developer|Express] [-Locale en-US]
param([ValidateSet('2025', '2022', '2019')][string]$Version = '2025',
      [ValidateSet('Developer', 'Express')][string]$Edition = 'Developer',
      [string]$Locale = 'en-US')
$id = "Microsoft.SQLServer.$Version.$Edition"
$log = Join-Path $env:TEMP "winget-$id.log"
Write-Host "Instalando $id (idioma del medio: $Locale). Registro: $log"
Write-Host "Si aparece un error de idioma, repite con otro -Locale (en-US funciona aunque Windows este en espanol)."
winget install --id $id --exact --locale $Locale --accept-package-agreements --accept-source-agreements --log $log
if ($LASTEXITCODE -ne 0) { Write-Warning "winget termino con codigo $LASTEXITCODE. Revisa $log"; exit $LASTEXITCODE }
Get-Service MSSQL* | Format-Table Name, Status, StartType
Write-Host 'Siguiente: scripts\env\sql-login.ps1 -Grant (para que tu usuario use sqlcmd sin elevacion) y scripts\env\install-ssms.ps1'
