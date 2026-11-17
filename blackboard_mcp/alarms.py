"""Exam alarms: a native Windows alarm notification that keeps coming back until Blackboard shows the exam submitted.

Only "big" evaluations (T1, T2, T3…, sustitutorio, examen final / parcial…) by default — not quizzes or attendance.
The notification uses Windows' *alarm* scenario (stays on screen, looping alarm sound, like the Clock app) and has a
single button, "Posponer": 2 h, or less so the last ring lands at least 1 h before the deadline; in that last hour it
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
from xml.sax.saxutils import escape

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
    """Evaluations that should ring now: big, still open, due within `days`, not snoozed. Most urgent first."""
    out = []
    for course, evs in evals_by_course.items():
        for e in evs:
            due = parse_dt(e.get("due"))
            if not due or e.get("kind") != "submission" or e.get("status") not in OPEN or not is_big(e.get("title"), include, exclude):
                continue
            left = due - now
            if left <= timedelta(0) or left > timedelta(days=days):
                continue
            key = e.get("column_id") or f"{course}|{e.get('title')}"
            until = parse_dt((state.get(key) or {}).get("snoozed_until"))
            if until and until > now:
                continue
            out.append({"key": key, "course": course, "title": e.get("title"), "due": due, "left": left})
    return sorted(out, key=lambda a: a["due"])


def course_title(label: str) -> str:
    """"GDAT5373 BASE DE DATOS [CIBERTEC…]" -> "Base de Datos" (short, for the notification)."""
    name = re.sub(r"\s*\[.*?\]$", "", label)
    name = re.sub(r"^[A-Z]{2,5}\d{3,5}\s+|^\d{3,5}\s+", "", name)
    small = {"de", "del", "la", "las", "los", "y", "e", "en", "a", "para"}
    return " ".join(w.lower() if i and w.lower() in small else w.capitalize() for i, w in enumerate(name.split()))


def toast_xml(title: str, course: str, left: timedelta, snooze: timedelta) -> str:
    return (
        '<toast scenario="alarm" duration="long">'
        '<visual><binding template="ToastGeneric">'
        # Windows bolds only the first line: exam + course there (both tell you where to look), time left below.
        f'<text>{escape(title)} · {escape(course)}</text><text>Quedan {escape(human_left(left))}</text>'
        '</binding></visual>'
        '<audio src="ms-winsoundevent:Notification.Looping.Alarm" loop="true"/>'
        f'<actions><action activationType="system" arguments="dismiss" content="Posponer {escape(human_span(snooze))}"/></actions>'
        '</toast>')


def register_app() -> None:
    """Show notifications as "Alarmas de exámenes" (HKCU AppUserModelId registration; no admin, no shortcut)."""
    if sys.platform != "win32":
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}") as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(k, "ShowInSettings", 0, winreg.REG_DWORD, 1)


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
    """Show the alarm; return how long it is snoozed for (the next ring)."""
    snooze = snooze_for(alarm["left"])
    show_toast(toast_xml(alarm["title"], course_title(alarm["course"]), alarm["left"], snooze), alarm["key"])
    return snooze


def run(settings: Settings, bb, now: datetime | None = None, notify=ring) -> list[dict]:
    """One check: ring every due alarm and store when each may ring again (the snooze starts when it rings)."""
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
        state[a["key"]] = {"title": a["title"], "course": a["course"], "snoozed_until": (now + snooze).isoformat()}
    if rang:
        save_state(settings, state)
    return rang


def session_lost() -> None:
    show_toast('<toast scenario="reminder"><visual><binding template="ToastGeneric">'
               '<text>Blackboard desconectado</text>'
               '<text>Sin sesión no puedo revisar tus exámenes. Vuelve a iniciar sesión: blackboard-mcp login</text>'
               '</binding></visual><actions><action activationType="system" arguments="dismiss" content="Entendido"/>'
               '</actions></toast>', "session")
