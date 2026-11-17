# Instala IBM Rhapsody 8.4 (curso Analisis y Diseno de Software) y deja lista la licencia de evaluacion.
# Lo ejecuta el estudiante como administrador (UAC). Idempotente: si ya esta instalado, solo revisa licencia.
#
#   .\install-rhapsody.ps1 -Media "C:\ruta\IBM_Rational_Rhapsody_8.4_64Bits.rar"
#
# -Media admite el .rar del profesor (MediaFire) o una carpeta ya extraida.
# La licencia de evaluacion expira el 28-jul-2021: abre Rhapsody con RunAsDate (ver SKILL 5.4).

param(
    [Parameter(Mandatory = $true)][string]$Media,
    [string]$LicensePath = "C:\ProgramData\IBM\Rational\Rhapsody\8.4\Rhapsody_Eval_Key.dat",
    [string]$InstallRoot = "C:\Program Files\IBM\Rational\Rhapsody\8.4"
)

$ErrorActionPreference = "Stop"
Write-Host "== IBM Rhapsody 8.4 =="

if (Test-Path (Join-Path $InstallRoot "rhapsody.exe")) {
    Write-Host "Rhapsody ya esta instalado en $InstallRoot"
} else {
    $work = Join-Path $env:TEMP ("rhapsody_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Force -Path $work | Out-Null

    if ($Media -like "*.rar") {
        # bsdtar (tar.exe de Windows) lee RAR: no hace falta 7-Zip
        Write-Host "Extrayendo $Media con tar.exe ..."
        & tar -xf $Media -C $work
    } else {
        Copy-Item $Media $work -Recurse
    }

    $msi = Get-ChildItem $work -Recurse -Filter "*.msi" | Where-Object { $_.Name -match "Rhapsody" } | Select-Object -First 1
    if (-not $msi) { throw "No encontre el MSI de Rhapsody dentro de $work" }

    $log = Join-Path $env:TEMP "rhapsody_msi.log"
    Write-Host "Instalando $($msi.Name) (silencioso, ~3 min) ..."
    $p = Start-Process msiexec.exe -ArgumentList "/i", "`"$($msi.FullName)`"", "/qn", "/l*v", "`"$log`"", "ALLUSERS=1" -PassThru -Wait
    Write-Host "msiexec exit=$($p.ExitCode)  log=$log"
    if ($p.ExitCode -ne 0) { throw "La instalacion fallo (ver $log)" }

    # la licencia viene junto al media del profesor
    $dat = Get-ChildItem $work -Recurse -Filter "*Eval_Key.dat" | Select-Object -First 1
    if ($dat) {
        New-Item -ItemType Directory -Force -Path (Split-Path $LicensePath) | Out-Null
        Copy-Item $dat.FullName $LicensePath -Force
        Write-Host "Licencia copiada a $LicensePath"
    } else {
        Write-Warning "No encontre Rhapsody_Eval_Key.dat en el media; copiala a mano en $LicensePath"
    }
}

if (Test-Path $LicensePath) {
    [Environment]::SetEnvironmentVariable("TELELOGIC_LICENSE_FILE", $LicensePath, "Machine")
    Write-Host "TELELOGIC_LICENSE_FILE = $([Environment]::GetEnvironmentVariable('TELELOGIC_LICENSE_FILE','Machine'))"
} else {
    Write-Warning "Falta $LicensePath (define TELELOGIC_LICENSE_FILE cuando la tengas)"
}

Write-Host @"

Listo. Para abrirlo (la clave de evaluacion expira el 28-jul-2021):
  RunAsDate.exe /movetime 01\07\2021 12:00:00 "$InstallRoot\rhapsody.exe"
RunAsDate (NirSoft, portable): https://www.nirsoft.net/utils/runasdate-x64.zip
Perfiles (los entrega el profesor): PERFILES.zip -> BusinessModelingProfile, AnalysisProfile, DesignProfile
Se cargan POR PROYECTO, no una vez por instalacion.
"@
