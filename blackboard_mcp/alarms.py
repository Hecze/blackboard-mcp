"""Exam alarms: a window that keeps coming back until Blackboard shows the exam as submitted.

Only "big" evaluations (T1, T2, T3…, sustitutorio, examen final / parcial…) by default — not quizzes or attendance.
The student can postpone (snooze) but not dismiss: the alarm stops only when the evaluation's status in Blackboard
is submitted or graded. Snoozes get shorter as the deadline gets closer, and the window always shows the exact
local deadline and the time left.

Run by a scheduled task every 15 min (scripts/install-alarms.ps1):  blackboard-mcp alarms
Try the window without Blackboard:                                   blackboard-mcp alarms --demo
"""
from __future__ import annotations

import json
import re
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .bb import parse_dt
from .config import Settings

DEFAULT_INCLUDE = r"\bT\s*-?\s*\d+\b|\bEF\b|examen|sustitutori|parcial|final"
DEFAULT_EXCLUDE = r"minicuestionario|cuestionario|asistencia|quiz|foro"
OPEN = ("pending", "draft")            # still to hand in (overdue can't be submitted any more: late attempts are off)
LIMA = timezone(timedelta(hours=-5))


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


def snooze_options(left: timedelta) -> list[int]:
    """Minutes the student may postpone, shrinking near the deadline so a snooze can never skip past it."""
    h = left.total_seconds() / 3600
    if h > 24:
        opts = [60, 120, 240]
    elif h > 6:
        opts = [60, 120]
    elif h > 2:
        opts = [30, 60]
    elif h > 0.5:
        opts = [15]
    else:
        opts = [5]
    return [m for m in opts if m * 60 < left.total_seconds()] or [max(1, int(left.total_seconds() // 120))]


def human_left(left: timedelta) -> str:
    mins = int(left.total_seconds() // 60)
    d, rem = divmod(mins, 1440)
    h, m = divmod(rem, 60)
    parts = ([f"{d} d"] if d else []) + ([f"{h} h"] if h or d else []) + [f"{m} min"]
    return " ".join(parts)


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
            out.append({"key": key, "course": course, "title": e.get("title"), "due": due, "left": left,
                        "status": e.get("status"), "attempts_allowed": e.get("attempts_allowed"),
                        "url": e.get("open_in_blackboard")})
    return sorted(out, key=lambda a: a["due"])


def show_window(alarm: dict, now: datetime) -> int:
    """Topmost window with the deadline and snooze buttons; no way to dismiss it for good. Returns minutes snoozed."""
    import tkinter as tk
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass
    opts = snooze_options(alarm["left"])
    chosen = {"m": opts[0]}
    root = tk.Tk()
    root.title("Evaluación pendiente")
    root.attributes("-topmost", True)
    root.configure(bg="#7a0010" if alarm["left"] < timedelta(hours=6) else "#1f2937", padx=24, pady=18)
    root.protocol("WM_DELETE_WINDOW", lambda: root.destroy())     # closing = shortest snooze, never "off"
    fg, bg = "white", root["bg"]
    local = alarm["due"].astimezone(LIMA)
    tk.Label(root, text=f"⏰ {alarm['title']}", font=("Segoe UI", 20, "bold"), fg=fg, bg=bg).pack(anchor="w")
    tk.Label(root, text=alarm["course"], font=("Segoe UI", 12), fg=fg, bg=bg).pack(anchor="w")
    tk.Label(root, text=f"Vence: {local:%A %d/%m %H:%M} (hora de Lima)", font=("Segoe UI", 14, "bold"),
             fg="#fde68a", bg=bg).pack(anchor="w", pady=(12, 0))
    tk.Label(root, text=f"Quedan {human_left(alarm['left'])}", font=("Segoe UI", 14), fg=fg, bg=bg).pack(anchor="w")
    extra = "Borrador guardado, aún sin enviar." if alarm["status"] == "draft" else "Aún no enviada."
    if alarm.get("attempts_allowed"):
        extra += f" Intentos: {alarm['attempts_allowed']}."
    tk.Label(root, text=extra + "  Esta alarma solo se apaga cuando Blackboard la marque como enviada.",
             font=("Segoe UI", 10), fg=fg, bg=bg, wraplength=520, justify="left").pack(anchor="w", pady=(8, 12))
    row = tk.Frame(root, bg=bg)
    row.pack(anchor="w")

    def snooze(m):
        chosen["m"] = m
        root.destroy()
    for m in opts:
        label = f"Posponer {m // 60} h" if m >= 60 and m % 60 == 0 else f"Posponer {m} min"
        tk.Button(row, text=label, command=lambda m=m: snooze(m), font=("Segoe UI", 11), padx=10).pack(side="left", padx=(0, 8))
    if alarm.get("url"):
        tk.Button(row, text="Abrir en Blackboard", font=("Segoe UI", 11, "bold"), padx=10,
                  command=lambda: (webbrowser.open(alarm["url"]), snooze(opts[0]))).pack(side="left")
    root.lift()
    root.focus_force()
    root.mainloop()
    return chosen["m"]


def run(settings: Settings, bb, now: datetime | None = None, show=show_window) -> list[dict]:
    """One check: ring every due alarm (one window at a time) and store the snoozes."""
    from .sync import Syncer
    now = now or datetime.now(timezone.utc)
    cfg = {"days": settings.alarm_days, "include": settings.alarm_include or DEFAULT_INCLUDE,
           "exclude": settings.alarm_exclude or DEFAULT_EXCLUDE}
    from .bb import course_labels
    courses = Syncer(settings, bb).courses()
    labels = course_labels(courses)
    by_course = {}
    for c in courses:
        evs = bb.evaluations(c)
        for e in evs:
            e["open_in_blackboard"] = e.get("open_in_blackboard") or c.url
        by_course[labels[c.id]] = evs
    state = load_state(settings)
    rang = due_alarms(by_course, now, state, **cfg)
    for a in rang:
        minutes = show(a, now)
        state[a["key"]] = {"title": a["title"], "course": a["course"],
                           "snoozed_until": (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()}
        save_state(settings, state)
    return rang


def session_lost_window(message: str) -> None:
    import tkinter as tk
    root = tk.Tk()
    root.title("Blackboard desconectado")
    root.attributes("-topmost", True)
    root.configure(bg="#7a0010", padx=24, pady=18)
    tk.Label(root, text="🚨 Sesión de Blackboard cerrada", font=("Segoe UI", 18, "bold"), fg="white", bg="#7a0010").pack(anchor="w")
    tk.Label(root, text="No puedo revisar tus exámenes pendientes hasta que vuelvas a iniciar sesión:\n"
             ".venv\\Scripts\\blackboard-mcp.exe login\n\n" + message[:300], font=("Segoe UI", 11),
             fg="white", bg="#7a0010", justify="left", wraplength=520).pack(anchor="w", pady=8)
    tk.Button(root, text="Entendido", command=root.destroy).pack(anchor="w")
    root.mainloop()
