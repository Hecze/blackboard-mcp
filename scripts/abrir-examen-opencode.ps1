# Abre el proyecto de Blackboard en OpenCode, en una sesión nueva, con el prompt del examen ya enviado.
#
# Lo lanza el botón "Hacer con OpenCode" de la alarma (protocolo bbexam://, registrado por blackboard_mcp/alarms.py):
#   bbexam://abrir?data=<json urlencoded con title, course y due>
#
# Funciona contra el servidor local que ya usa la app de escritorio:
#   1. POST /api/session            {title, location:{directory: <repo>}}   -> id de la sesión
#   2. POST /api/session/<id>/prompt {text: <prompt del examen>}
#   3. trae la app al frente (una segunda instancia la enfoca).
# Auth: Basic opencode:<password de ~/.config/opencode/service.json>.
# Log: %TEMP%\bbexam-opencode.log
param([Parameter(Position = 0)][string]$Url = "")

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path $env:TEMP 'bbexam-opencode.log'

function Log([string]$m) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Add-Content -Path $log -Encoding utf8
}

try {
    Log "url=$Url"

    # --- datos del examen desde el protocolo
    if (-not $Url -or $Url -notmatch '^bbexam://') { throw "URL inesperada: $Url" }
    $data = ''
    if ($Url -match '[?&]data=([^&]+)') { $data = [uri]::UnescapeDataString($Matches[1]) }
    if (-not $data) { throw "Sin parámetro data" }
    $exam = $data | ConvertFrom-Json
    Log "examen: $($exam.title) | $($exam.course) | $($exam.due)"

    # --- CLI y servidor de OpenCode
    $cli = Get-ChildItem (Join-Path $env:APPDATA 'ai.opencode.desktop\cli') -Recurse -Filter 'opencode-cli.exe' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (-not $cli) { throw "No encuentro opencode-cli.exe" }
    $base = (& $cli service status 2>$null | Select-Object -First 1)
    if (-not $base) {
        Log "servicio apagado; arrancando la app"
        Start-Process (Join-Path $env:LOCALAPPDATA 'Programs\ai.opencode.desktop\OpenCode.exe') | Out-Null
        Start-Sleep -Seconds 8
        $base = (& $cli service status 2>$null | Select-Object -First 1)
    }
    if (-not $base) { throw "El servidor de OpenCode no responde" }
    $base = $base.Trim().TrimEnd('/')
    Log "servidor: $base"

    $pw = $null
    foreach ($f in @((Join-Path $HOME '.config\opencode\service.json'), (Join-Path $HOME '.config\opencode\service-local.json'))) {
        if (Test-Path $f) { $pw = (Get-Content $f -Raw | ConvertFrom-Json).password; if ($pw) { break } }
    }
    if (-not $pw) { throw "No encuentro la contraseña del servicio en ~/.config/opencode/service.json" }
    $auth = @{ Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("opencode:$pw")) }

    # --- 1) sesión nueva en el proyecto de Blackboard
    $title = "$($exam.title) · $($exam.course)"
    $body = @{ title = $title; location = @{ directory = $repo } } | ConvertTo-Json -Depth 4 -Compress
    $ses = Invoke-RestMethod "$base/api/session" -Method Post -Headers $auth -ContentType 'application/json' -Body $body -TimeoutSec 20
    $id = $ses.data.id
    Log "sesión creada: $id"

    # --- 2) prompt del examen
    $prompt = @"
Resuelve la evaluación «$($exam.title)» del curso $($exam.course) (vence $($exam.due)).
Repo: $repo

1) Primero arma el expediente con la skill obtener-contexto-evaluacion: enunciado, rúbrica, sílabo, anuncios y transcripciones de las clases (si falta alguna transcripción, genérala).
2) Después resuélvela y entrega el Word + PDF aplicando la skill entregables-sin-huella.
3) Si el profesor prohíbe IA en esa evaluación, avísame antes de empezar.
"@
    $pbody = @{ text = $prompt } | ConvertTo-Json -Compress
    Invoke-RestMethod "$base/api/session/$id/prompt" -Method Post -Headers $auth -ContentType 'application/json' -Body $pbody -TimeoutSec 30 | Out-Null
    Log "prompt enviado a $id"

    # --- 3) la app al frente (segunda instancia = mismo proceso, enfoca la ventana)
    Start-Process (Join-Path $env:LOCALAPPDATA 'Programs\ai.opencode.desktop\OpenCode.exe') -ErrorAction SilentlyContinue | Out-Null
    Log "listo"
}
catch {
    Log "ERROR: $($_.Exception.Message)"
    # que el fallo se vea: un aviso simple en el centro de notificaciones
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show("No pude abrir OpenCode con el examen.`n`n$($_.Exception.Message)`n`nDetalle: $log",
            'Alarmas de exámenes', 'OK', 'Warning') | Out-Null
    } catch { }
    exit 1
}
