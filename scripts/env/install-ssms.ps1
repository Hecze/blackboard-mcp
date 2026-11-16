# Install SQL Server Management Studio with winget (the student approves UAC if asked).
#   powershell -ExecutionPolicy Bypass -File scripts\env\install-ssms.ps1 [-Version 22|21]
param([ValidateSet('22', '21')][string]$Version = '22')
$id = "Microsoft.SQLServerManagementStudio.$Version"
$log = Join-Path $env:TEMP "winget-$id.log"
Write-Host "Instalando $id. Registro: $log"
Write-Host 'Si SSMS dice "no se puede ejecutar si la instalacion esta en curso", hay un setup.exe colgado: cierralo desde el Administrador de tareas.'
winget install --id $id --exact --accept-package-agreements --accept-source-agreements --log $log
exit $LASTEXITCODE
