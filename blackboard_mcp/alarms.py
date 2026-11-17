"""Exam alarms: a native Windows alarm notification that keeps coming back until Blackboard shows the exam submitted.

Only "big" evaluations (T1, T2, T3…, sustitutorio, examen final / parcial…) by default — not quizzes or attendance.
The notification uses Windows' *alarm* scenario (stays on screen, looping alarm sound, like the Clock app) and has two
buttons:

- **Hacer con OpenCode** (left): opens Blackboard's project in OpenCode with the exam already prompted — a new session
  in the repo, with the "get the dossier, then solve it" message sent automatically. Implemented with the `bbexam://`
  protocol registered in HKCU (scripts/abrir-examen-opencode.ps1 uses the local OpenCode API).
- **Posponer** (right): 2 h, or less so the last ring lands at least 1 h before the deadline; in that last hour it
  rings every 15 min. There is no "off": it stops only when the evaluation is submitted or graded in Blackboard.

Run by a scheduled task every 15 min (scripts/install-alarms.ps1):  blackboard-mcp alarms
Try it without Blackboard:                                          blackboard-mcp alarms --demo
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from .bb import parse_dt
from .config import Settings

DEFAULT_INCLUDE = r"\bT\s*-?\s*\d+\b|\bEF\b|examen|sustitutori|parcial|final"
DEFAULT_EXCLUDE = r"minicuestionario|cuestionario|asistencia|quiz|foro"
OPEN = ("pending", "draft")            # still to hand in (overdue can't be submitted any more: late attempts are off)
SNOOZE = timedelta(hours=2)            # the one snooze offered…
MARGIN = timedelta(hours=1)            # …shortened so the last ring is at least this long before the deadline
LAST_HOUR_EVERY = timedelta(minutes=15)
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


def exam_arg(alarm: dict) -> str:
    """`bbexam://abrir?data=<json>` for the "Hacer con OpenCode" button: what the PowerShell handler needs.

    `mode`: "repo"        → T1/T2/EF… el enunciado es un .docx: se trabaja en el repo blackboard.
            "blackboard"  → cualquier otra actividad: es un formulario/cuestionario dentro de Blackboard; se avanza
                            página por página y se deja antes de "Enviar".
    """
    data = {"title": alarm.get("title") or "", "course": alarm.get("course") or "",
            "due": alarm["due"].isoformat() if alarm.get("due") else "",
            "mode": "repo" if alarm.get("big") else "blackboard",
            "url": alarm.get("url") or ""}
    return f"{PROTOCOL}://abrir?data={quote(json.dumps(data, ensure_ascii=False))}"


def toast_xml(title: str, course: str, left: timedelta, snooze: timedelta, open_arg: str | None = None,
              big: bool = True) -> str:
    # Two buttons, left to right in the order declared: OpenCode first, then the snooze/silence one.
    actions = ""
    if open_arg:
        actions += (f'<action activationType="protocol" arguments={quoteattr(open_arg)} '
                    f'content="{escape(OPENCODE_BUTTON)}"/>')
    label = f"Posponer {escape(human_span(snooze))}" if big else "Entendido (no insistir)"
    actions += f'<action activationType="system" arguments="dismiss" content="{label}"/>'
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
"""


def show_toast(xml: str, tag: str) -> None:
    """Show a toast through Windows PowerShell's WinRT bridge (no extra Python packages; works on x64 and ARM64).
    The same tag replaces an older notification for the same exam instead of stacking a new one."""
    register_app()
    payload = json.dumps({"xml": xml, "tag": re.sub(r"[^A-Za-z0-9_]", "_", tag)[:60], "app": AUMID})
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _PS],
                       input=payload, capture_output=True, text=True, encoding="utf-8", creationflags=flags, timeout=60)
    if r.returncode:
        raise RuntimeError(f"toast failed: {r.stderr.strip()[:400]}")


def ring(alarm: dict) -> timedelta:
    """Show the alarm; return how long it is snoozed for (the next ring). Non-big ones never ring again."""
    big = alarm.get("big", True)
    snooze = snooze_for(alarm["left"])
    show_toast(toast_xml(alarm["title"], course_title(alarm["course"]), alarm["left"], snooze,
                         open_arg=exam_arg(alarm), big=big), alarm["key"])
    return snooze if big else timedelta(0)


def run(settings: Settings, bb, now: datetime | None = None, notify=ring) -> list[dict]:
    """One check: ring every due alarm and remember what happens next.

    T1/T2/EF… (`big`): snooze, and ring again until Blackboard shows it submitted.
    Anything else: rings once and is marked `muted` (one "Entendido" and it never comes back)."""
    from .bb import course_labels
    from .sync import Syncer
    now = now or datetime.now(timezone.utc)
    courses = Syncer(settings, bb).courses()
    labels = course_labels(courses)
    by_course = {labels[c.id]: bb.evaluations(c) for c in courses}
    state = load_state(settings)
    rang = due_alarms(by_course, now, state, days=settings.alarm_days,
                      include=settings.alarm_include or DEFAULT_INCLUDE, exclude=settings.alarm_exclude or DEFAULT_EXCLUDE)
    for a in rang:
        snooze = notify(a)
        entry = {"title": a["title"], "course": a["course"],
                 "snoozed_until": (now + snooze).isoformat()}
        if not a.get("big", True):
            entry["muted"] = True
        state[a["key"]] = entry
    if rang:
        save_state(settings, state)
    return rang


def session_lost() -> None:
    show_toast('<toast scenario="reminder"><visual><binding template="ToastGeneric">'
               '<text>Blackboard desconectado</text>'
               '<text>Sin sesión no puedo revisar tus exámenes. Vuelve a iniciar sesión: blackboard-mcp login</text>'
               '</binding></visual><actions><action activationType="system" arguments="dismiss" content="Entendido"/>'
               '</actions></toast>', "session")
