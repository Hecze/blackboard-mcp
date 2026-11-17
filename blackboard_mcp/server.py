"""MCP server exposing a Blackboard Learn (Ultra) site to AI tools."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

import anyio
from mcp.server.fastmcp import FastMCP

from .auth import LoginRequired, browser_login, read_health, write_health
from .bb import Blackboard, body_links, course_labels, handler_id, html_to_text, parse_dt
from .config import load_settings
from .sync import Syncer, safe

_settings = load_settings()
_health = read_health(_settings)
_ALERT = (
    "CRITICAL: the student's Blackboard session is LOST (last check "
    f"{(_health or {}).get('checked_at')}: {(_health or {}).get('message')}). Tell the student IMMEDIATELY, before "
    "anything else, and ask them to sign in again with bb_login. "
) if _health and not _health.get("ok") else ""

# Each tool's own description says what it does; the server instructions only carry what applies to all of them.
mcp = FastMCP(
    "blackboard",
    instructions=_ALERT + (
        "Read-only tools for the student's Blackboard (Ultra) and recorded classes. Results are compact JSON: empty or "
        "null fields are omitted. If any tool returns login_required, that is CRITICAL: tell the student at once, "
        "prominently, and offer bb_login (it opens a browser window where the student signs in)."
    ),
)


def _compact(obj):
    """Drop None / "" / [] / {} recursively (keeps 0 and False: a 0 score is data)."""
    if isinstance(obj, dict):
        out = {k: _compact(v) for k, v in obj.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(obj, list):
        return [_compact(v) for v in obj]
    return obj


def tool(fn):
    """Register `fn` as an MCP tool whose result goes out ONCE, as compact JSON text without empty fields.

    FastMCP would otherwise send a dict twice (indented JSON text + structuredContent) and publish an output schema.
    The Python function itself keeps returning dicts, so it can still be called directly (tests, harnesses without MCP).
    """
    import functools
    import json

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return json.dumps(_compact(await fn(*args, **kwargs)), ensure_ascii=False, separators=(",", ":"), default=str)

    mcp.tool(structured_output=False)(wrapper)
    return fn

_job: dict = {"running": False}
_job_lock = threading.Lock()


def _bb() -> Blackboard:
    if not _settings.base_url:
        raise LoginRequired("No Blackboard address set. Set BB_BASE_URL to your university's Blackboard, "
                            "e.g. https://learn.example.ac.uk.")
    return Blackboard(_settings)


async def _run(fn, *args):
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args))
    except LoginRequired as e:
        write_health(_settings, False, str(e))
        return {"login_required": True, "critical": True,
                "message": "CRITICAL - Blackboard session lost, tell the student immediately. " + str(e)}
    except (ValueError, PermissionError) as e:
        return {"error": str(e)}


@tool
async def bb_login(timeout_seconds: int = 300) -> dict:
    """Sign in to Blackboard. Opens a Chrome window at the university sign-in page; the student completes it
    there (SSO + MFA). Tries a silent refresh first, so it often finishes without any window."""
    def go():
        res = browser_login(_settings, headless=True)
        if res.get("ok"):
            return dict(res, how="refreshed silently")
        return dict(browser_login(_settings, headless=False, timeout_s=timeout_seconds), how="interactive sign-in")
    return await _run(go)


@tool
async def bb_status() -> dict:
    """Which Blackboard and account this is, where files download to, and when the last sync ran."""
    def go():
        last = Syncer(_settings, _bb()).state.get("last_sync")
        me = _bb().me()
        return {"base_url": _settings.base_url, "signed_in_as": me.get("userName"),
                "name": (me.get("name") or {}).get("given"), "download_dir": str(_settings.download_dir),
                "last_sync": datetime.fromtimestamp(last).isoformat(timespec="minutes") if last else None,
                "session_health": read_health(_settings)}
    return await _run(go)


@tool
async def bb_courses(include_all: bool = False, links: bool = False) -> list[dict] | dict:
    """List current Blackboard courses (include_all=True: every course and organisation you're enrolled in).
    `links=True` adds each item's Blackboard URL (omitted by default to keep the answer short)."""
    def go():
        bb = _bb()
        syncer = Syncer(_settings, bb)
        current = syncer.courses()
        _, skipped = syncer.choose(current)
        why = {s["id"]: s["why"] for s in skipped}
        now_ids = {c.id for c in current}
        cs = bb.courses(include_organisations=True) if include_all else current
        return [{"id": c.id, "course_id": c.course_id, "code": c.code, "name": c.name,
                 "last_accessed": c.last_accessed, "url": c.url if links else None, "synced": c.id in now_ids and c.id not in why,
                 "why_not": why.get(c.id) or ("" if c.id in now_ids else "not this year's, or an organisation")}
                for c in cs]
    return await _run(go)


@tool
async def bb_set_courses(include: list[str] | None = None, exclude: list[str] | None = None) -> dict:
    """Choose which courses a full bb_sync pulls, overriding its guess. `include`: courses (id, code or name) to
    pull even though they look like an info site; `exclude`: ones to stop pulling. Saved for every later sync.
    Passing a course in one list removes it from the other."""
    def go():
        import json
        bb = _bb()
        syncer = Syncer(_settings, bb)
        prefs = syncer.prefs()
        inc, exc = set(prefs.get("include") or []), set(prefs.get("exclude") or [])
        everything = bb.courses(include_organisations=True)
        for q in include or []:
            cid = bb.find_course(q, everything).id
            inc.add(cid)
            exc.discard(cid)
        for q in exclude or []:
            cid = bb.find_course(q, everything).id
            exc.add(cid)
            inc.discard(cid)
        syncer.prefs_path.write_text(json.dumps({"include": sorted(inc), "exclude": sorted(exc)}, indent=1))
        return {"ok": True, "include": sorted(inc), "exclude": sorted(exc)}
    return await _run(go)


@tool
async def bb_browse(course: str, folder_id: str | None = None, links: bool = False) -> dict:
    """List the content in a course (or inside one folder): titles, types, text, links and grade columns.
    `course` can be a course code, part of its name, or its id.
    `links=True` adds each item's Blackboard URL (omitted by default to keep the answer short)."""
    def go():
        bb = _bb()
        c = bb.find_course(course)
        items = [{
            "id": it["id"], "title": it.get("title"), "type": handler_id(it),
            "has_children": it.get("hasChildren", False), "modified": it.get("modified"),
            "text": html_to_text(it.get("body") or it.get("description"))[:600],
            "links": [l["url"] for l in body_links(it.get("body"), _settings.base_url)][:10],
            "grade_column": (it.get("contentHandler") or {}).get("gradeColumnId"),
            "open_in_blackboard": bb.web_link(c, it) if links else None,
        } for it in bb.contents(c.id, folder_id)]
        return {"course": c.short_name(), "folder_id": folder_id, "items": items}
    return await _run(go)


@tool
async def bb_download(course: str, content_id: str) -> dict:
    """Download every file attached to (or embedded in) one content item. Returns the local paths."""
    def go():
        bb = _bb()
        c = bb.find_course(course)
        folder = _settings.download_dir / safe(c.short_name(), 60) / "Downloads"
        item = bb.get(f"/learn/api/public/v1/courses/{c.id}/contents/{content_id}")
        paths = []
        for f in bb.item_files(c.id, item):   # attachments, embedded files, Ultra assessment instructions
            dest = folder / safe(f["name"], 120)
            bb.download(f["url"], dest)
            paths.append(str(dest))
        return {"title": item.get("title"), "files": paths}
    return await _run(go)


@tool
async def bb_upcoming(days: int = 21) -> dict:
    """Due dates from Blackboard for the next `days` days (assignments, quizzes, Turnitin)."""
    def go():
        bb = _bb()
        now = datetime.now(timezone.utc)
        names = {c.id: c.short_name() for c in bb.courses(include_organisations=True)}
        items = [{"course": names.get(it.get("calendarId"), it.get("calendarName")), "title": it.get("title"),
                  "due": it.get("end") or it.get("start"), "details": html_to_text(it.get("description"))[:400]}
                 for it in bb.calendar_due(now - timedelta(days=1), now + timedelta(days=days))]
        items.sort(key=lambda i: i["due"] or "")
        return {"window_days": days, "items": items}
    return await _run(go)


@tool
async def bb_evaluations(course: str | None = None, only_open: bool = False, links: bool = False) -> dict:
    """Every evaluation (assignments, tests, exams) in one course, or in all current courses if none is given:
    due date, the student's own status (pending / draft / submitted / graded / overdue), score and feedback,
    the instructions and the files the teacher attached to it (rubrics, templates). Call bb_download with the
    course and `content_id` to download those files. only_open=True keeps just what still needs handing in.
    Results are grouped by course.
    `links=True` adds each item's Blackboard URL (omitted by default to keep the answer short)."""
    def go():
        bb = _bb()
        cs = [bb.find_course(course)] if course else Syncer(_settings, bb).courses()
        labels = course_labels(cs)
        by_course: dict[str, list] = {}
        counts: dict[str, int] = {}
        for c in cs:
            for e in bb.evaluations(c):
                if only_open and (e["kind"] != "submission" or e["status"] not in ("pending", "draft", "overdue")):
                    continue
                if not links:
                    e.pop("open_in_blackboard", None)
                by_course.setdefault(labels[c.id], []).append(e)
                counts[e["status"]] = counts.get(e["status"], 0) + 1
        for evs in by_course.values():   # bb.evaluations already sorts by due date
            evs.sort(key=lambda e: (e["due"] is None, e["due"] or ""))
        return {"counts": counts, "courses": by_course}
    return await _run(go)


@tool
async def bb_announcements(course: str | None = None, days: int = 14) -> dict:
    """Recent announcements for one course, or for all current courses if none is given."""
    def go():
        bb = _bb()
        cs = [bb.find_course(course)] if course else Syncer(_settings, bb).courses()
        since = datetime.now(timezone.utc) - timedelta(days=days)
        labels = course_labels(cs)
        by_course: dict[str, list] = {}
        for c in cs:
            anns = []
            for a in bb.announcements(c.id):
                when = parse_dt(a.get("created"))
                if when and when < since:
                    continue
                anns.append({"title": a.get("title"), "posted": a.get("created"),
                             "text": html_to_text(a.get("body"))[:1500]})
            if anns:
                by_course[labels[c.id]] = sorted(anns, key=lambda a: a["posted"] or "", reverse=True)
        return {"days": days, "courses": by_course}
    return await _run(go)


@tool
async def bb_pull_course(course: str) -> dict:
    """Download EVERYTHING in one course into <download folder>/<course>/Todo/, keeping Blackboard's folders:
    all files (slides, guides, SQL, xlsx…), files inside evaluations (rubrics, statements), files and class
    scripts posted in announcements (Todo/ANUNCIOS) and SharePoint documents such as the syllabus and manuals.
    Writes Todo/manifest.json, an index of every item. Files already downloaded are skipped. Takes a minute or two."""
    from .pull import pull_course

    def go():
        bb = _bb()
        return pull_course(_settings, bb, bb.find_course(course))
    return await _run(go)


def _class_client():
    from .classcom import ClassClient
    if not _settings.class_web:
        raise ValueError("Class isn't set up: add \"class_web\" (e.g. https://yourschool.class.com) to "
                         "~/.blackboard-mcp/config.json.")
    return ClassClient(_settings)


def _class_targets(cc, course: str | None) -> list[dict]:
    if not course:
        return cc.classes()
    try:
        name = _bb().find_course(course).name
    except (ValueError, PermissionError, LoginRequired):
        name = course
    hits = cc.classes_for(name)
    if not hits:
        raise ValueError(f"No Class classroom matches '{course}'. Classes: "
                         + "; ".join(c["class_name"] for c in cc.classes()))
    return hits


@tool
async def bb_recordings(course: str | None = None) -> dict:
    """Recorded live lessons (Class / Zoom) for one course — its TEO and LAB rooms — or for every class.
    Grouped by class room; each recording has a date, duration and status. Pass the room's class_uuid + a
    recording_id to bb_transcript."""
    from .classcom import ClassLoginRequired

    def go():
        cc = _class_client()
        classes = {}
        for c in _class_targets(cc, course):
            recs = [{"recording_id": r["recordingId"], "when": r.get("when"), "status": r.get("status"),
                     "duration": time.strftime("%H:%M:%S", time.gmtime(r.get("duration") or 0)),
                     "transcript_saved": _transcript_path(c["class_name"], r).exists()}
                    for r in cc.recordings(c["class_uuid"])]
            recs.sort(key=lambda r: r["when"] or "", reverse=True)
            classes[c["class_name"]] = {"class_uuid": c["class_uuid"], "teacher": c.get("teacher"), "recordings": recs}
        return {"classes": classes}
    try:
        return await _run(go)
    except ClassLoginRequired as e:
        return {"login_required": True, "critical": True, "message": str(e)}


def _transcript_path(class_name: str, rec: dict):
    when = (rec.get("when") or "")[:10]
    return _settings.download_dir / "Grabaciones" / safe(class_name or "Class", 80) / f"{when} {rec.get('recordingId', rec.get('recording_id', ''))[:8]}.md"


@tool
async def bb_transcript(course: str | None = None, class_uuid: str | None = None, recording_id: str | None = None,
                        refresh: bool = False) -> dict:
    """Save readable transcripts of recorded lessons as Markdown: who speaks (🎓 PROFESOR vs 🙋 Alumno by name,
    from Zoom's speaker labels), when, and the class chat in between. Give class_uuid + recording_id for one
    recording, or `course` to fetch every finished recording of that course not saved yet. Returns the file
    paths — read them to study what was taught."""
    from .classcom import ClassLoginRequired, to_markdown

    def go():
        cc = _class_client()
        if class_uuid and recording_id:
            targets = [(c, {"recordingId": recording_id}) for c in cc.classes() if c["class_uuid"] == class_uuid] \
                or [({"class_uuid": class_uuid, "class_name": "", "teacher": ""}, {"recordingId": recording_id})]
        else:
            targets = [(c, r) for c in _class_targets(cc, course) for r in cc.recordings(c["class_uuid"])
                       if r.get("status") == "AVAILABLE"]
        saved, skipped = [], []
        for c, r in targets:
            path = _transcript_path(c["class_name"], r)
            if path.exists() and not refresh and r.get("when"):
                skipped.append(str(path))
                continue
            tr = cc.transcript(c["class_uuid"], r["recordingId"], c.get("class_name", ""), c.get("teacher") or "")
            path = _transcript_path(tr["class_name"], {"when": tr["start"].isoformat(), "recordingId": r["recordingId"]})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(to_markdown(tr), encoding="utf-8")
            saved.append({"file": str(path), "teacher": tr["teacher"], "source": tr["source"],
                          "lines": len(tr["lines"]), "chat_messages": len(tr["chats"])})
        return {"saved": saved, "already_saved": skipped}
    try:
        return await _run(go)
    except ClassLoginRequired as e:
        return {"login_required": True, "critical": True, "message": str(e)}


def _sync_worker(courses):
    try:
        _job["report"] = Syncer(_settings, _bb(), lambda m: _job.update(progress=m)).run(courses or None)
    except LoginRequired as e:
        _job["report"] = {"login_required": True, "message": str(e)}
    except Exception as e:  # noqa: BLE001 - surfaced through bb_sync_status
        _job["report"] = {"error": f"{type(e).__name__}: {e}"}
    finally:
        _job["running"] = False


@tool
async def bb_sync(courses: list[str] | None = None, wait_seconds: int = 20) -> dict:
    """Download the PDFs (slides, readings, worksheets) from every current course, or just `courses`, into
    <download folder>/<course>/<week>/ (SlideMate's library if it's set up). Only new or changed files are
    fetched. Runs in the background: if it isn't done within wait_seconds, call bb_sync_status."""
    with _job_lock:
        if not _job.get("running"):
            _job.clear()
            _job.update(running=True, started_at=time.time(), progress="Finding your courses…", report=None)
            threading.Thread(target=_sync_worker, args=(courses,), daemon=True).start()
    deadline = time.time() + max(0, wait_seconds)
    while _job.get("running") and time.time() < deadline:
        await anyio.sleep(0.5)
    return await bb_sync_status()


@tool
async def bb_sync_status() -> dict:
    """Progress (while running) or the result of the most recent bb_sync."""
    if _job.get("running"):
        return {"running": True, "progress": _job.get("progress"),
                "elapsed_s": round(time.time() - _job.get("started_at", time.time()))}
    return {"running": False, "report": _job.get("report")}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
