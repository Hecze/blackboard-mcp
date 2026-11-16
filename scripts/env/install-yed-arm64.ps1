# Make yEd work on Windows ARM64: its bundled Java (jre\) is x64 and crashes under emulation, so run yed.jar on a
# native ARM64 JDK. Installs Microsoft OpenJDK 21 (portable zip, no admin) in ~\tools\jdk-21-arm64 and creates
# "yEd (ARM64)" shortcuts in the Start menu and on the Desktop. Idempotent.
#   powershell -ExecutionPolicy Bypass -File scripts\env\install-yed-arm64.ps1 [-YedDir C:\Users\me\yEd]
param([string]$YedDir = "$env:USERPROFILE\yEd", [string]$JdkDir = "$env:USERPROFILE\tools\jdk-21-arm64")
$ErrorActionPreference = 'Stop'
if (-not (Test-Path "$YedDir\yed.jar")) { throw "No encuentro $YedDir\yed.jar. Instala yEd primero (winget install yWorks.yEd)." }

if (-not (Test-Path "$JdkDir\bin\javaw.exe")) {
    $zip = Join-Path $env:TEMP 'jdk21-arm64.zip'; $tmp = Join-Path $env:TEMP 'jdk21-arm64'
    Write-Host 'Descargando Microsoft OpenJDK 21 (ARM64)...'
    Invoke-WebRequest -UseBasicParsing 'https://aka.ms/download-jdk/microsoft-jdk-21-windows-aarch64.zip' -OutFile $zip
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip $tmp
    New-Item -ItemType Directory -Force (Split-Path $JdkDir) | Out-Null
    Move-Item (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName $JdkDir
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
# java -version prints to stderr, which Windows PowerShell 5.1 turns into an error under 'Stop': go through cmd.
"JDK: " + (cmd /c "`"$JdkDir\bin\java.exe`" -version 2>&1" | Select-Object -First 1)

$sh = New-Object -ComObject WScript.Shell
$links = @("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\yEd (ARM64).lnk",
           (Join-Path ([Environment]::GetFolderPath('Desktop')) 'yEd (ARM64).lnk'))
foreach ($t in $links) {
    $l = $sh.CreateShortcut($t)
    $l.TargetPath = "$JdkDir\bin\javaw.exe"
    $l.Arguments = "-jar `"$YedDir\yed.jar`""
    $l.WorkingDirectory = $YedDir
    $l.IconLocation = "$YedDir\yEd.exe,0"
    $l.Description = 'yEd con Java ARM64 nativo'
    $l.Save()
    "Acceso directo: $t"
}
"Listo. Abrir un archivo: & `"$JdkDir\bin\javaw.exe`" -jar `"$YedDir\yed.jar`" archivo.graphml"
