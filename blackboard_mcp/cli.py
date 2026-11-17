"""Command line: `blackboard-mcp login | status | courses | sync [COURSE…] | serve`."""
from __future__ import annotations

import argparse
import json
import sys


def _alarms(demo: bool) -> int:
    """One alarm check (run every 15 min by a scheduled task)."""
    from datetime import timedelta

    from . import alarms
    if demo:
        snooze = alarms.ring({"key": "demo", "title": "Examen T1 (demo)", "course": "GDAT5373 BASE DE DATOS",
                              "left": timedelta(hours=15, minutes=20)})
        print(f"alarma mostrada; volvería a sonar en {alarms.human_span(snooze)}")
        return 0
    from .auth import LoginRequired
    from .bb import Blackboard
    from .config import load_settings
    s = load_settings()
    try:
        rang = alarms.run(s, Blackboard(s))
    except LoginRequired as e:
        alarms.session_lost()
        return 2
    print(json.dumps([{"title": a["title"], "course": a["course"], "due": a["due"].isoformat()} for a in rang],
                     ensure_ascii=False))
    return 0


def main() -> None:
    p = argparse.ArgumentParser(prog="blackboard-mcp", description="Blackboard Learn (Ultra) MCP server")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("login", help="sign in (opens Chrome)")
    sp.add_argument("--timeout", type=int, default=300)
    sub.add_parser("status", help="who you're signed in as")
    sub.add_parser("refresh", help="silently renew the session (for a scheduled keep-alive); exit 2 if sign-in is needed")
    sub.add_parser("courses", help="your current courses")
    sp = sub.add_parser("sync", help="download PDFs from every current course (or the ones named)")
    sp.add_argument("courses", nargs="*")
    sub.add_parser("serve", help="run the MCP server on stdio (the default)")
    sp = sub.add_parser("alarms", help="ring for pending exams (T1/T2/EF…) until Blackboard shows them submitted")
    sp.add_argument("--demo", action="store_true", help="show a sample alarm window without contacting Blackboard")
    args = p.parse_args()
    if args.cmd == "alarms":
        sys.exit(_alarms(args.demo))
    if args.cmd in (None, "serve"):
        from .server import main as serve
        serve()
        return

    import anyio
    from . import server
    if args.cmd == "refresh":
        from .auth import browser_login
        from .config import load_settings
        rep = browser_login(load_settings(), headless=True)
        if not rep.get("ok"):
            rep["login_required"] = True
    elif args.cmd == "login":
        rep = anyio.run(lambda: server.bb_login(args.timeout))
    elif args.cmd == "status":
        rep = anyio.run(server.bb_status)
    elif args.cmd == "courses":
        rep = anyio.run(server.bb_courses)
        if isinstance(rep, list):
            for c in rep:
                print(f"  {c['code'] or '':<12} {c['name']}")
            sys.exit(0)
    else:
        rep = anyio.run(lambda: server.bb_sync(args.courses or None, 0))
        last = None
        while rep.get("running"):
            if rep.get("progress") != last:
                print(rep.get("progress"), flush=True)
                last = rep.get("progress")
            import time
            time.sleep(1)
            rep = anyio.run(server.bb_sync_status)
        rep = rep.get("report") or rep
    print(json.dumps(rep, indent=1))
    sys.exit(2 if rep.get("login_required") else 1 if rep.get("error") or rep.get("ok") is False else 0)


if __name__ == "__main__":
    main()
