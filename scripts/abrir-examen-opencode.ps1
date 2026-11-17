# Abre una pestaña NUEVA en OpenCode, con el prompt del examen escrito en el input (SIN enviarlo).
#
# Lo lanza el botón "Hacer con OpenCode" de la alarma (protocolo bbexam://, registrado por blackboard_mcp/alarms.py)
# o a mano:  powershell -File scripts\abrir-examen-opencode.ps1 "bbexam://abrir?data=..."
#
# Por qué UI y no la API: la API crea la sesión y manda el mensaje (se envía solo). Aquí lo que se quiere es que el
# texto quede en el input y que el alumno decida cuándo enviarlo. Se hace como lo haría una persona, rápido:
#   1. trae la ventana de OpenCode al frente (la abre si no está)
#   2. clic en "Nueva sesión"
#   3. pega el prompt en el compositor (Ctrl+V) y COMPRUEBA con Ctrl+A/Ctrl+C que el texto quedó; si no, reintenta
# Nunca pulsa Enter. Log: %TEMP%\bbexam-opencode.log
param([Parameter(Position = 0)][string]$Url = "", [switch]$DryRun)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path $env:TEMP 'bbexam-opencode.log'
$script:sw = [Diagnostics.Stopwatch]::StartNew()

function Log([string]$m) {
    "{0}  [{1,5} ms]  {2}" -f (Get-Date -Format 'HH:mm:ss'), $script:sw.ElapsedMilliseconds, $m |
        Add-Content -Path $log -Encoding utf8
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public struct RECT { public int Left, Top, Right, Bottom; }
public class Win {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool at);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, int d, IntPtr e);
  public static string Title(IntPtr h) { var sb = new StringBuilder(512); GetWindowText(h, sb, 512); return sb.ToString(); }
  public static IntPtr Find(string match) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      var t = Title(h);
      if (t.IndexOf(match, StringComparison.OrdinalIgnoreCase) >= 0) { found = h; return false; }
      return true; }, IntPtr.Zero);
    return found;
  }
  public static void Force(IntPtr h) {
    IntPtr fg = GetForegroundWindow(); uint pid; uint fgThread = GetWindowThreadProcessId(fg, out pid);
    uint me = GetCurrentThreadId();
    AttachThreadInput(me, fgThread, true);
    ShowWindow(h, 3); BringWindowToTop(h); SetForegroundWindow(h);
    AttachThreadInput(me, fgThread, false);
  }
}
"@

function App {
    $h = [Win]::Find("OpenCode")
    if ($h -eq [IntPtr]::Zero) {
        Log "app cerrada: abriendo"
        Start-Process (Join-Path $env:LOCALAPPDATA 'Programs\ai.opencode.desktop\OpenCode.exe') | Out-Null
        for ($i = 0; $i -lt 40; $i++) { Start-Sleep -Milliseconds 250; $h = [Win]::Find("OpenCode"); if ($h -ne [IntPtr]::Zero) { break } }
    }
    return $h
}

function ClickRel($r, [int]$x, [int]$y) {
    [Win]::SetCursorPos($r.Left + $x, $r.Top + $y) | Out-Null
    Start-Sleep -Milliseconds 120
    [Win]::mouse_event(0x02,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 50
    [Win]::mouse_event(0x04,0,0,0,[IntPtr]::Zero)
}

function InputHas([string]$text) {
    # Ctrl+A + Ctrl+C dentro del compositor y comparar (restaura el portapapeles después)
    $old = Get-Clipboard -Raw -ErrorAction SilentlyContinue
    Set-Clipboard -Value "___bbexam___"
    [System.Windows.Forms.SendKeys]::SendWait("^a")
    Start-Sleep -Milliseconds 60
    [System.Windows.Forms.SendKeys]::SendWait("^c")
    Start-Sleep -Milliseconds 220
    $got = Get-Clipboard -Raw -ErrorAction SilentlyContinue
    if ($old) { Set-Clipboard -Value $old } else { Set-Clipboard -Value " " }
    return ($got -ne "___bbexam___" -and $got -and $got.Trim() -eq $text.Trim())
}

try {
    Log "url=$Url"

    # --- botón "Entendido (no insistir)": marca la actividad como silenciada y no vuelve a sonar
    if ($Url -match '^bbexam://entendido') {
        $md = @{}
        if ($Url -match '[?&]data=([^&]+)') { $md = [uri]::UnescapeDataString($Matches[1]) | ConvertFrom-Json }
        $key = $md.key
        if (-not $key) { throw "Sin key para silenciar" }
        $file = Join-Path $HOME '.blackboard-mcp\alarms.json'
        $st = @{}
        if (Test-Path $file) {
            $obj = Get-Content $file -Raw -Encoding utf8 | ConvertFrom-Json
            foreach ($p in $obj.PSObject.Properties) { $st[$p.Name] = $p.Value }
        }
        $entry = $st[$key]
        if (-not $entry) { $entry = [pscustomobject]@{ title = "$($md.title)" } }
        $entry | Add-Member -NotePropertyName muted -NotePropertyValue $true -Force
        $st[$key] = $entry
        New-Item -ItemType Directory -Force -Path (Split-Path $file) | Out-Null
        $st | ConvertTo-Json -Depth 6 | Set-Content -Path $file -Encoding utf8
        Log "silenciada: $key ($($md.title))"
        exit 0
    }
    # --- examen desde el protocolo
    $exam = @{ title = "evaluación"; course = ""; due = "" }
    if ($Url -match '[?&]data=([^&]+)') {
        $exam = [uri]::UnescapeDataString($Matches[1]) | ConvertFrom-Json
    }
    Log "examen: $($exam.title) | $($exam.course)"

    $skills = Join-Path $repo '.claude\skills'
    $mode = if ($exam.mode) { $exam.mode } else { 'repo' }
    if ($mode -eq 'blackboard') {
        # formulario/cuestionario dentro de Blackboard: se resuelve en la web y se deja antes de "Enviar"
        $prompt = @(
            "Resuelve la actividad «$($exam.title)» de $($exam.course) en Blackboard: $($exam.url)"
            "Es un formulario dentro de Blackboard: avanza página por página y déjalo completo en la última, SIN pulsar Enviar (yo verifico y envío)."
            "Si algo no se puede (archivo adjunto, límite de intentos), dime qué falta antes de tocar nada."
        ) -join " "
    } else {
        # T1/T2/EF: el enunciado es un .docx y se resuelve en el repo
        $prompt = @(
            "Resuelve «$($exam.title)» de $($exam.course)."
            "Trabaja en $repo y lee .claude\skills\obtener-contexto-evaluacion\SKILL.md (expediente: enunciado, rúbrica, sílabo, anuncios, transcripciones)."
            "Para entregar, .claude\skills\entregables-sin-huella\SKILL.md."
        ) -join " "
    }
    Log "mode=$mode prompt: $($prompt.Length) chars"
    if ($DryRun) {
        [IO.File]::WriteAllText((Join-Path $env:TEMP 'bbexam-prompt.txt'), $prompt, (New-Object Text.UTF8Encoding($false)))
        Write-Output $prompt
        exit 0
    }

    $h = App
    if ($h -eq [IntPtr]::Zero) { throw "No encuentro la ventana de OpenCode" }
    [Win]::Force($h)
    Start-Sleep -Milliseconds 250
    $r = New-Object RECT
    [Win]::GetWindowRect($h, [ref]$r) | Out-Null
    Log "ventana $($r.Left),$($r.Top) $($r.Right - $r.Left)x$($r.Bottom - $r.Top)"

    # 1) pestaña nueva (sidebar: "Nueva sesión")
    ClickRel $r 89 176
    Log "clic en Nueva sesión"
    Start-Sleep -Milliseconds 1500                    # el compositor de la pestaña nueva se autofocaliza

    # 2) pegar y comprobar (hasta 3 intentos, re-afirmando el foco en cada uno)
    $ok = $false
    for ($i = 1; $i -le 3 -and -not $ok; $i++) {
        [Win]::Force($h)
        Start-Sleep -Milliseconds 120
        Set-Clipboard -Value $prompt
        Start-Sleep -Milliseconds 80
        [System.Windows.Forms.SendKeys]::SendWait("^a"); Start-Sleep -Milliseconds 40
        [System.Windows.Forms.SendKeys]::SendWait("{DEL}"); Start-Sleep -Milliseconds 40
        [System.Windows.Forms.SendKeys]::SendWait("^v")
        Start-Sleep -Milliseconds 350
        $ok = InputHas $prompt
        Log "intento $i -> $(if ($ok) {'ok'} else {'fallo'})"
        if (-not $ok) { Start-Sleep -Milliseconds 900 }   # quizá la pestaña aún no existía
    }
    if (-not $ok) { throw "No pude dejar el prompt en el input (ver $log)" }
    [System.Windows.Forms.SendKeys]::SendWait("{END}")     # quita la selección del Ctrl+A de la comprobación
    Set-Clipboard -Value $prompt
    Log "listo: prompt en el input, SIN enviar ($($script:sw.ElapsedMilliseconds) ms)"
}
catch {
    Log "ERROR: $($_.Exception.Message)"
    try {
        [System.Windows.Forms.MessageBox]::Show("No pude preparar la sesión de OpenCode.`n`n$($_.Exception.Message)`n`nDetalle: $log",
            'Alarmas de exámenes', 'OK', 'Warning') | Out-Null
    } catch { }
    exit 1
}
