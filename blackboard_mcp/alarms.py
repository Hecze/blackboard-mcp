"""Alarmas de evaluaciones: una notificación nativa de Windows que insiste hasta que Blackboard muestre la entrega hecha.

Suena con **cualquier** entrega pendiente con fecha. T1/T2/T3/EF/sustitutorio/parcial/final insisten hasta que aparezcan
enviadas; el resto avisa una sola vez. Van **de una en una**: se muestra la más urgente y, al cerrarla, aparece la
siguiente — así no se apilan tres notificaciones cuando hay varias pendientes.

La notificación usa el escenario *alarma* de Windows (se queda en pantalla con sonido en bucle, como la app Reloj) y
tiene dos botones:

- **Hacer con OpenCode** (izquierda): abre una pestaña nueva de OpenCode con el prompt ya escrito, sin enviar
  (`bbexam://abrir` → scripts/abrir-examen-opencode.ps1). La siguiente alarma espera **10 min**: estás ocupado.
- **Posponer 1 h** (T1/T2/EF…) o **Entendido (no insistir)** (el resto): la siguiente aparece **al instante**.
- Cerrar con la **X** cuenta como posponer: vuelve a sonar en 1 h, y la siguiente también aparece al instante.

Se ejecuta cada 15 min (scripts/install-alarms.ps1):  blackboard-mcp alarms
Probarlo sin Blackboard:                            blackboard-mcp alarms --demo
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from .bb import parse_dt
from .config import Settings

DEFAULT_INCLUDE = r"\bT\s*-?\s*\d+\b|\bEF\b|examen|sustitutori|parcial|final"
DEFAULT_EXCLUDE = r"minicuestionario|cuestionario|asistencia|quiz|foro"
OPEN = ("pending", "draft")            # still to hand in (overdue can't be submitted any more: late attempts are off)
SNOOZE = timedelta(hours=1)            # cerrar con la X (o posponer) = volver a sonar en 1 h
MARGIN = timedelta(hours=1)            # …shortened so the last ring is at least this long before the deadline
LAST_HOUR_EVERY = timedelta(minutes=15)
OPENCODE_PAUSE = timedelta(minutes=10)  # tras "Hacer con OpenCode": la siguiente puede esperar, estás resolviendo
WAIT_MAX = timedelta(hours=4)          # si nadie toca la notificación, la tanda termina (y la siguiente vuelve a sonar)
MARKER = Path(tempfile.gettempdir()) / "bbexam-boton.json"   # lo escribe el handler del protocolo al pulsar un botón
AUMID = "Blackboard.Alarmas"           # app id the notifications are shown under (registered in HKCU, no admin)
APP_NAME = "Alarmas de exámenes"
PROTOCOL = "bbexam"                    # bbexam://abrir?data=<json> → scripts/abrir-examen-opencode.ps1
OPENCODE_BUTTON = "Hacer con OpenCode"
OPENCODE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "abrir-examen-opencode.ps1"



def state_path(s: Settings) -> Path:
    return s.home / "alarms.json"


def load_state(s: Settings) -> dict:
    try:
        return json.loads(state_path(s).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(s: Settings, st: dict) -> None:
    state_path(s).write_text(json.dumps(st, indent=1, ensure_ascii=False), encoding="utf-8")


def is_big(title: str, include: str = DEFAULT_INCLUDE, exclude: str = DEFAULT_EXCLUDE) -> bool:
    t = title or ""
    return bool(re.search(include, t, re.I)) and not re.search(exclude, t, re.I)


def snooze_for(left: timedelta) -> timedelta:
    """2 h, or less so the next ring is still ≥ 1 h before the deadline; inside the last hour, every 15 min."""
    room = left - MARGIN
    if room >= SNOOZE:
        return SNOOZE
    if room >= LAST_HOUR_EVERY:
        return room
    return min(LAST_HOUR_EVERY, max(left, timedelta(minutes=1)))


def human_left(left: timedelta) -> str:
    mins = max(0, int(left.total_seconds() // 60))
    d, rem = divmod(mins, 1440)
    h, m = divmod(rem, 60)
    if d:
        return f"{d} d {h} h"
    return f"{h} h {m} min" if h else f"{m} min"


def human_span(span: timedelta) -> str:
    m = round(span.total_seconds() / 60)
    return f"{m // 60} h" if m >= 60 and m % 60 == 0 else (f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min")


def due_alarms(evals_by_course: dict, now: datetime, state: dict, days: int = 7,
               include: str = DEFAULT_INCLUDE, exclude: str = DEFAULT_EXCLUDE) -> list[dict]:
    """Everything still to hand in and due within `days`, most urgent first.

    Two kinds:
    - `big=True`  (T1/T2/T3…, EF, sustitutorio, parcial, final): insists — snooze and ring again until Blackboard shows
      it submitted.
    - `big=False` (any other submission: cuestionarios, simulaciones, entregables, tareas): rings **once**; one snooze
      and it never comes back (`muted` in the state).
    """
    out = []
    for course, evs in evals_by_course.items():
        for e in evs:
            due = parse_dt(e.get("due"))
            if not due or e.get("kind") != "submission" or e.get("status") not in OPEN:
                continue
            left = due - now
            if left <= timedelta(0) or left > timedelta(days=days):
                continue
            big = is_big(e.get("title"), include, exclude)
            key = e.get("column_id") or f"{course}|{e.get('title')}"
            st = state.get(key) or {}
            if st.get("muted"):
                continue
            until = parse_dt(st.get("snoozed_until"))
            if until and until > now:
                continue
            out.append({"key": key, "course": course, "title": e.get("title"), "due": due, "left": left,
                        "big": big, "content_id": e.get("content_id"), "url": e.get("open_in_blackboard")})
    return sorted(out, key=lambda a: a["due"])


def course_title(label: str) -> str:
    """"GDAT5373 BASE DE DATOS [CIBERTEC…]" -> "Base de Datos" (short, for the notification)."""
    name = re.sub(r"\s*\[.*?\]$", "", label)
    name = re.sub(r"^[A-Z]{2,5}\d{3,5}\s+|^\d{3,5}\s+", "", name)
    small = {"de", "del", "la", "las", "los", "y", "e", "en", "a", "para"}
    return " ".join(w.lower() if i and w.lower() in small else w.capitalize() for i, w in enumerate(name.split()))


def toast_tag(key: str) -> str:
    """Windows tag: same tag replaces the older notification instead of stacking; only [A-Za-z0-9_] and ≤ 64 chars."""
    return re.sub(r"[^A-Za-z0-9_]", "_", key or "")[:60]


def exam_arg(alarm: dict) -> str:
    """`bbexam://abrir?data=<json>` for the "Hacer con OpenCode" button: what the PowerShell handler needs.

    `mode`: "repo"        → T1/T2/EF… el enunciado es un .docx: se trabaja en el repo blackboard.
            "blackboard"  → cualquier otra actividad: es un formulario/cuestionario dentro de Blackboard; se avanza
                            página por página y se deja antes de "Enviar".
    """
    data = {"title": alarm.get("title") or "", "course": alarm.get("course") or "",
            "due": alarm["due"].isoformat() if alarm.get("due") else "",
            "mode": "repo" if alarm.get("big") else "blackboard",
            "url": alarm.get("url") or "", "key": alarm.get("key") or "",
            "tag": toast_tag(alarm.get("key") or "")}
    return f"{PROTOCOL}://abrir?data={quote(json.dumps(data, ensure_ascii=False))}"


def mute_arg(alarm: dict) -> str:
    """`bbexam://entendido?data=<json>`: el botón "Entendido (no insistir)" de las actividades que no son examen.

    Va por protocolo (no `activationType="system"`) porque Windows no distingue ese botón de cerrar la notificación
    con la X: así sabemos que el alumno lo pulsó y lo silenciamos de verdad."""
    data = {"key": alarm.get("key") or "", "title": alarm.get("title") or "",
            "tag": toast_tag(alarm.get("key") or "")}
    return f"{PROTOCOL}://entendido?data={quote(json.dumps(data, ensure_ascii=False))}"


def toast_xml(title: str, course: str, left: timedelta, snooze: timedelta, open_arg: str | None = None,
              big: bool = True, mute: str | None = None) -> str:
    # Two buttons, left to right in the order declared: OpenCode first, then the snooze/silence one.
    actions = ""
    if open_arg:
        actions += (f'<action activationType="protocol" arguments={quoteattr(open_arg)} '
                    f'content="{escape(OPENCODE_BUTTON)}"/>')
    if big or not mute:
        # cerrar con la X (o este botón) vuelve a sonar en `snooze`
        actions += (f'<action activationType="system" arguments="dismiss" '
                    f'content="Posponer {escape(human_span(snooze))}"/>')
    else:
        # solo este botón silencia; la X vuelve a sonar en `snooze`
        actions += (f'<action activationType="protocol" arguments={quoteattr(mute)} '
                    f'content="Entendido (no insistir)"/>')
    return (
        '<toast scenario="alarm" duration="long">'
        '<visual><binding template="ToastGeneric">'
        # Windows bolds only the first line: exam + course there (both tell you where to look), time left below.
        f'<text>{escape(title)} · {escape(course)}</text><text>Quedan {escape(human_left(left))}</text>'
        '</binding></visual>'
        '<audio src="ms-winsoundevent:Notification.Looping.Alarm" loop="true"/>'
        f'<actions>{actions}</actions>'
        '</toast>')



def register_app() -> None:
    """Show notifications as "Alarmas de exámenes" and register `bbexam://` for the OpenCode button (HKCU, no admin)."""
    if sys.platform != "win32":
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}") as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(k, "ShowInSettings", 0, winreg.REG_DWORD, 1)
    if not OPENCODE_SCRIPT.exists():
        return
    cmd = f'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{OPENCODE_SCRIPT}" "%1"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL}") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"URL:{APP_NAME}")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL}\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)



_PS = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$in = [Console]::In.ReadToEnd() | ConvertFrom-Json
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml($in.xml)
$t = [Windows.UI.Notifications.ToastNotification]::new($x)
$t.Tag = $in.tag; $t.Group = 'alarmas'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($in.app).Show($t)
if (-not $in.wait) { Write-Output 'shown'; exit 0 }

# Espera a que el alumno haga algo. PowerShell no puede suscribirse a eventos de WinRT (Register-ObjectEvent no
# funciona con Windows Runtime), así que se vigila de dos formas:
#   - el botón de protocolo (bbexam://) escribe $in.marker con {tag, action}: es la señal fiable de "lo pulsó";
#   - si la notificación desaparece del centro de actividades, la cerró con la X o con "Posponer".
$app = $in.app; $tag = $in.tag; $marker = $in.marker
$deadline = (Get-Date).AddSeconds([int]$in.timeout)
$res = 'timeout'
function Marker($path) {
    if (-not (Test-Path $path)) { return $null }
    try { return (Get-Content $path -Raw -Encoding utf8 | ConvertFrom-Json) } catch { return $null }
}
while ((Get-Date) -lt $deadline) {
    $m = Marker $marker
    if ($m -and $m.tag -eq $tag) { $res = "$($m.action)"; break }
    $seen = $false
    try {
        foreach ($n in [Windows.UI.Notifications.ToastNotificationManager]::History.GetHistory($app)) {
            if ($n.Tag -eq $tag) { $seen = $true }
        }
    } catch { }
    if (-not $seen) {
        Start-Sleep -Milliseconds 1500          # margen: el handler del protocolo escribe la marca antes
        $m = Marker $marker
        if ($m -and $m.tag -eq $tag) { $res = "$($m.action)" } else { $res = 'dismissed' }
        break
    }
    Start-Sleep -Milliseconds 750
}
try { [Windows.UI.Notifications.ToastNotificationManager]::History.Remove($tag, 'alarmas', $app) } catch { }
Write-Output $res
"""


def _run_ps(script: str, payload: str | None = None, timeout: float = 60, env: dict | None = None) -> str:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", script], input=payload, capture_output=True, text=True, encoding="utf-8",
                       creationflags=flags, timeout=timeout, env=env)
    if r.returncode:
        raise RuntimeError(f"toast failed: {(r.stderr or '').strip()[:400]}")
    return (r.stdout or "").strip()


def show_toast(xml: str, tag: str, wait: bool = False, timeout: timedelta = WAIT_MAX) -> str:
    """Show a toast through Windows PowerShell's WinRT bridge (no extra Python packages; works on x64 and ARM64).

    With `wait=True` it blocks until the student does something and returns what: `opencode` (pulsó el botón de la
    izquierda), `entendido` (silenciar), `dismissed` (X o Posponer) o `timeout` (nadie la tocó en `timeout`)."""
    register_app()
    payload = json.dumps({"xml": xml, "tag": toast_tag(tag), "app": AUMID, "wait": bool(wait),
                          "marker": str(MARKER), "timeout": int(timeout.total_seconds())})
    out = _run_ps(_PS, payload, timeout=timeout.total_seconds() + 120 if wait else 60).splitlines()
    result = out[-1].strip().lower() if out else "shown"
    return result if result in ("dismissed", "opencode", "entendido", "timeout", "shown") else "shown"


def clear_toasts() -> None:
    """Quita de la pantalla y del centro de actividades las alarmas anteriores: una sola a la vez."""
    register_app()
    _run_ps(r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
try { [Windows.UI.Notifications.ToastNotificationManager]::History.Clear($env:BB_APP) } catch { }
""", env={**os.environ, "BB_APP": AUMID})


def ring(alarm: dict) -> str:
    """Show ONE alarm and wait for the student; return `opencode` / `entendido` / `dismissed` / `timeout`."""
    try:
        MARKER.unlink()
    except OSError:
        pass
    big = alarm.get("big", True)
    snooze = snooze_for(alarm["left"])
    xml = toast_xml(alarm["title"], course_title(alarm["course"]), alarm["left"], snooze,
                    open_arg=exam_arg(alarm), big=big, mute=None if big else mute_arg(alarm))
    return show_toast(xml, alarm["key"], wait=True)


def ring_queue(rang: list[dict], show=ring, sleep=time.sleep, pause: timedelta = OPENCODE_PAUSE) -> list[str]:
    """One at a time, most urgent first. After `opencode` the next one waits `pause`; otherwise it comes right away."""
    outcomes = []
    for i, a in enumerate(rang):
        outcome = show(a)
        outcomes.append(outcome)
        if outcome == "opencode" and i < len(rang) - 1:
            sleep(pause.total_seconds())
    return outcomes


def tanda_lock(settings: Settings):
    """One run at a time: the scheduled task fires every 15 min and a run can sit waiting for the student for hours."""
    f = open(settings.home / "alarms.lock", "a+b")
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        return f
    except OSError:
        f.close()
        return None


def run(settings: Settings, bb, now: datetime | None = None, show=ring, sleep=time.sleep) -> list[dict]:
    """One check: ring the pending alarms one after another and remember what happens next.

    T1/T2/EF… (`big`): snooze, and ring again until Blackboard shows it submitted.
    Anything else: rings once (one "Entendido" and it never comes back)."""
    from .bb import course_labels
    from .sync import Syncer
    now = now or datetime.now(timezone.utc)
    lock = tanda_lock(settings)
    if lock is None:
        return []                                   # ya hay una tanda enseñando alarmas
    try:
        courses = Syncer(settings, bb).courses()
        labels = course_labels(courses)
        by_course = {labels[c.id]: bb.evaluations(c) for c in courses}
        state = load_state(settings)
        rang = due_alarms(by_course, now, state, days=settings.alarm_days,
                          include=settings.alarm_include or DEFAULT_INCLUDE,
                          exclude=settings.alarm_exclude or DEFAULT_EXCLUDE)
        if not rang:
            return []
        clear_toasts()

        def show_and_remember(a: dict) -> str:
            outcome = show(a)
            # cerrar con la X (o posponer) vuelve a sonar en 1 h; las no-examen se silencian con su propio botón
            left = a["due"] - datetime.now(timezone.utc)
            state[a["key"]] = {"title": a["title"], "course": a["course"],
                               "snoozed_until": (datetime.now(timezone.utc) + snooze_for(left)).isoformat()}
            save_state(settings, state)
            a["outcome"] = outcome
            return outcome

        ring_queue(rang, show_and_remember, sleep=sleep)
        return rang
    finally:
        lock.close()


def session_lost() -> None:
    show_toast('<toast scenario="reminder"><visual><binding template="ToastGeneric">'
               '<text>Blackboard desconectado</text>'
               '<text>Sin sesión no puedo revisar tus exámenes. Vuelve a iniciar sesión: blackboard-mcp login</text>'
               '</binding></visual><actions><action activationType="system" arguments="dismiss" content="Entendido"/>'
               '</actions></toast>', "session")
