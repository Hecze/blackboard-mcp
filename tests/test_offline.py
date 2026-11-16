"""Offline tests: `uv run --with pytest pytest`. No Blackboard account or network needed."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
(TMP / "slidemate").mkdir()
(TMP / "slidemate" / "config.json").write_text(json.dumps({"library_roots": [str(TMP / "Slides")]}))
os.environ.update(BB_MCP_HOME=str(TMP / "home"), SLIDEMATE_DATA=str(TMP / "slidemate"), BB_BASE_URL="learn.example.ac.uk/ultra")
os.environ.pop("BB_DOWNLOAD_DIR", None)

from blackboard_mcp.bb import Course  # noqa: E402
from blackboard_mcp.config import load_settings  # noqa: E402
from blackboard_mcp.sync import Syncer, current_courses, parse_week  # noqa: E402

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def course(code, created, end=None):
    avail = {"available": "Yes", "duration": {"type": "DateRange", "end": end} if end else {"type": "Continuous"}}
    return Course(id=code, course_id=code, name=code, code=code, raw={"created": created, "availability": avail})


def test_settings():
    s = load_settings()
    assert s.base_url == "https://learn.example.ac.uk"
    assert s.download_dir == TMP / "Slides"  # SlideMate's library


def test_only_this_years_courses():
    cs = [course("NEW1", "2026-06-15T00:00:00Z"), course("NEW2", "2026-06-15T00:00:00Z"),
          course("OLD1", "2025-04-04T00:00:00Z"), course("ENDED", "2026-06-15T00:00:00Z", end="2026-01-01T00:00:00Z"),
          course("ENDS_LATER", "2024-01-01T00:00:00Z", end="2027-06-01T00:00:00Z")]
    assert [c.id for c in current_courses(cs, NOW)] == ["NEW1", "NEW2", "ENDS_LATER"]


def test_week_folders():
    assert parse_week("Week 3 - Sensing Mechanisms") == 3
    assert parse_week("Lecture 12 slides") == 12
    assert parse_week("Unit information") is None


class FakeBB:
    def __init__(self):
        self.downloads = []

    def walk(self, pk):
        yield (), {"id": "1", "title": "Week 1", "contentHandler": {"id": "resource/x-bb-folder"}}
        yield ("Week 1",), {"id": "2", "title": "Lecture 1 slides", "modified": "m1",
                            "contentHandler": {"id": "resource/x-bb-file"}}
        yield (), {"id": "3", "title": "Welcome to the unit", "modified": "m1"}
        yield ("Week 1",), {"id": "4", "title": "Unit poster", "modified": "m1"}

    def attachments(self, pk, cid):
        return [{"id": "a", "fileName": "Lecture 1.pdf"}, {"id": "b", "fileName": "recording.mp4"}] if cid == "2" else \
               [{"id": "d", "fileName": "a3.pdf"}] if cid == "4" else [{"id": "c", "fileName": "welcome.pdf"}]

    def attachment_url(self, pk, cid, aid):
        return f"/x/{cid}/{aid}"

    def download(self, url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF")
        self.downloads.append(url)


def test_sync_layout_skips_noise_and_repeats():
    s = load_settings()
    bb = FakeBB()
    rep = Syncer(s, bb).sync_course(course("ABC123", "2026-06-15T00:00:00Z"))
    assert rep["downloaded"] == 1 and bb.downloads == ["/x/2/a"]  # PDFs only; the welcome page and poster are skipped
    assert rep["not_study"] == 1
    assert (s.download_dir / "ABC123" / "Week 01" / "Lecture 1.pdf").exists()
    syncer = Syncer(s, bb)
    syncer.state["files"]["ABC123:2:a"] = "m1"
    assert syncer.sync_course(course("ABC123", "2026-06-15T00:00:00Z"))["downloaded"] == 0


def test_info_sites_are_skipped_unless_chosen():
    s = load_settings()
    syncer = Syncer(s, FakeBB())
    hub = Course(id="_9_1", course_id="FAC-HUB", name="Faculty of Engineering Student Hub", code=None)
    unit = Course(id="_5_1", course_id="COMS30030_2026", name="Machine Learning", code="COMS30030")
    keep, skipped = syncer.choose([hub, unit])
    assert [c.id for c in keep] == ["_5_1"] and skipped[0]["id"] == "_9_1"
    syncer.prefs_path.write_text(json.dumps({"include": ["_9_1"], "exclude": ["_5_1"]}))
    keep, skipped = syncer.choose([hub, unit])
    assert [c.id for c in keep] == ["_9_1"] and skipped == [{"id": "_5_1", "name": "Machine Learning", "why": "you turned it off"}]
    syncer.prefs_path.unlink()


def test_stdio_lists_tools_and_keeps_stdout_clean():
    p = subprocess.Popen([sys.executable, "-m", "blackboard_mcp.cli", "serve"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        def rpc(mid, method, params=None):
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n")
            p.stdin.flush()
            return json.loads(p.stdout.readline())
        rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
        p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        names = {t["name"] for t in rpc(2, "tools/list")["result"]["tools"]}
        assert {"bb_login", "bb_sync", "bb_sync_status", "bb_upcoming", "bb_announcements", "bb_set_courses",
                "bb_evaluations", "bb_recordings", "bb_transcript", "bb_pull_course"} <= names
    finally:
        p.kill()


def test_submission_status():
    from blackboard_mcp.bb import submission_status
    past, future = datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert submission_status(None, [], future, NOW) == "pending"
    assert submission_status(None, [], past, NOW) == "overdue"
    assert submission_status(None, [{"status": "InProgress"}], past, NOW) == "draft"
    assert submission_status(None, [{"status": "NeedsGrading"}], past, NOW) == "submitted"
    assert submission_status({"status": "NeedsGrading"}, [], past, NOW) == "submitted"
    assert submission_status({"status": "Graded", "score": 17}, [{"status": "Completed"}], past, NOW) == "graded"


def test_evaluations_from_api():
    import httpx
    from blackboard_mcp.bb import Blackboard

    api = "/learn/api/public"
    routes = {
        f"{api}/v1/users/me": {"id": "_u1", "userName": "alumno"},
        f"{api}/v2/courses/_c1/gradebook/columns": {"results": [
            {"id": "_g1", "name": "T1 - Informe", "contentId": "_x1", "grading": {"type": "Attempts", "due": "2026-10-10T04:59:00Z", "attemptsAllowed": 1}, "score": {"possible": 20}},
            {"id": "_g2", "name": "EF - Examen final", "grading": {"type": "Manual", "due": "2026-12-01T04:59:00Z"}},
            {"id": "_g3", "name": "Total", "grading": {"type": "Calculated"}},
        ]},
        f"{api}/v2/courses/_c1/gradebook/columns/_g1/attempts": {"results": [{"id": "_a1", "status": "NeedsGrading"}]},
        f"{api}/v2/courses/_c1/gradebook/columns/_g2/attempts": {"results": []},
        f"{api}/v2/courses/_c1/gradebook/columns/_g1/users/_u1": {"status": "NeedsGrading"},
        f"{api}/v1/courses/_c1/contents/_x1": {"id": "_x1", "title": "T1 - Informe",
                                               "body": "<p>Entregar en PDF.</p>"},
        f"{api}/v1/courses/_c1/contents/_x1/attachments": {"results": [{"id": "_f1", "fileName": "Rubrica T1.pdf"}]},
    }

    def handler(req):
        body = routes.get(req.url.path)
        return httpx.Response(200, json=body) if body is not None else httpx.Response(404, json={})

    bb = Blackboard(load_settings(), transport=httpx.MockTransport(handler), refresher=lambda s: True)
    bb._client.cookies.set("BbRouter", "x")
    evs = bb.evaluations(Course(id="_c1", course_id="C1", name="Curso", code=None, url="u"), now=NOW)
    assert [e["title"] for e in evs] == ["T1 - Informe", "EF - Examen final"]  # the calculated total is left out
    t1, ef = evs
    assert t1["status"] == "submitted" and t1["kind"] == "submission" and t1["teacher_files"] == ["Rubrica T1.pdf"]
    assert t1["instructions"] == "Entregar en PDF." and t1["content_id"] == "_x1"
    assert ef["status"] == "pending" and ef["kind"] == "grade_only"


def test_class_transcript_vtt_and_markdown():
    from blackboard_mcp.classcom import parse_vtt, to_markdown
    vtt = ("WEBVTT\n\n1\n00:12:55.250 --> 00:13:03.780\nJAIME FACTOR LOPEZ LOPEZ: Buenas tardes.\n\n"
           "2\n00:13:04.000 --> 00:13:06.000\nJAIME FACTOR LOPEZ LOPEZ: Empezamos.\n\n"
           "3\n00:13:07.000 --> 00:13:08.000\nAudio shared by JAIME FACTOR LOPEZ LOPEZ: y a y a\n\n"
           "4\n00:13:10.000 --> 00:13:12.000\nHEBERT ROBERTO SALVADOR CORDERO: Profesor, una consulta.\n")
    lines = parse_vtt(vtt)
    assert [l["speaker"] for l in lines] == ["JAIME FACTOR LOPEZ LOPEZ"] * 2 + ["HEBERT ROBERTO SALVADOR CORDERO"]
    assert lines[0]["t"] == 12 * 60 + 55.25
    md = to_markdown({"class_name": "BD TEO", "start": datetime(2026, 11, 9, 19, 19, tzinfo=timezone.utc),
                      "duration_s": 100, "teacher": "JAIME FACTOR LOPEZ LOPEZ", "source": "zoom", "participants": 3,
                      "lines": lines, "chats": [{"t": 789.0, "speaker": "OLVER", "text": "Hola", "chat": True}]})
    assert "**[00:12:55] 🎓:** Buenas tardes. Empezamos." in md
    assert "**[00:13:10] 🙋 Hebert:** Profesor, una consulta." in md and "y a y a" not in md
    assert "- 🎓 = profesor Jaime Factor Lopez Lopez" in md
    assert "- 🙋 Hebert = Hebert Roberto Salvador Cordero" in md and "- 🙋 Olver = Olver (solo chat)" in md
    assert "> 💬 [00:13:09] 🙋 Olver: Hola" in md
    assert "09/11/2026 14:19" in md   # Lima time


def test_class_matches_blackboard_course():
    from blackboard_mcp.classcom import ClassClient
    cc = ClassClient.__new__(ClassClient)
    cc.classes = lambda: [{"class_uuid": "a", "class_name": "Base de Datos_Lopez Lopez, Jaime TEO"},
                          {"class_uuid": "b", "class_name": "Base de Datos_Lopez Lopez, Jaime LAB"},
                          {"class_uuid": "c", "class_name": "ANALISIS Y DISEÑO DE SOFTWARE _ Julianne (LA)"}]
    assert [c["class_uuid"] for c in cc.classes_for("GDAT5373 BASE DE DATOS")] == ["a", "b"]
    assert [c["class_uuid"] for c in cc.classes_for("DCGS5365 ANALISIS Y DISEÑO DE SOFTWARE")] == ["c"]


REPO = Path(__file__).resolve().parent.parent


def test_skills_mirrors_in_sync_and_frontmatter_valid():
    import re
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_skills.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    for f in (REPO / "skills").glob("*/SKILL.md"):
        head = re.match(r"---\n(.*?)\n---\n", f.read_text(encoding="utf-8"), re.S).group(1)
        assert re.search(rf"^name: {re.escape(f.parent.name)}$", head, re.M), f
        # descriptions contain ': ' — they must be block scalars or YAML breaks (GitHub showed an error)
        assert re.search(r"^description: >-\n  \S", head, re.M), f


def test_docs_have_no_control_characters():
    files = [REPO / "AGENTS.md", REPO / "README.md", *(REPO / "skills").rglob("*.md"), *(REPO / "scripts").rglob("*.ps1")]
    for f in files:
        bad = [c for c in f.read_text(encoding="utf-8-sig") if ord(c) < 32 and c not in "\n\r"]  # tabs too: one was a mangled "\t"
        assert not bad, f"{f.name} has control characters (a mangled backslash?)"


def test_transcript_aliases_unique():
    from blackboard_mcp.classcom import _aliases
    a = _aliases(["JUAN JOSE NOVOA GUERRERO", "JUAN PEREZ LOPEZ", "OLVER EDGAR MONTALVO SABINO"])
    assert a["OLVER EDGAR MONTALVO SABINO"] == "Olver"
    assert len(set(a.values())) == 3 and a["JUAN PEREZ LOPEZ"] != a["JUAN JOSE NOVOA GUERRERO"]


def test_mcp_tool_output_is_compact_json_once():
    import asyncio
    from blackboard_mcp import server

    @server.tool
    async def _probe_tool() -> dict:
        """test only"""
        return {"a": None, "b": "", "c": [], "d": 0, "e": {"f": None, "g": False}, "h": "x"}

    r = asyncio.run(server.mcp.call_tool("_probe_tool", {}))
    blocks = r[0] if isinstance(r, tuple) else r
    assert [b.text for b in blocks] == ['{"d":0,"e":{"g":false},"h":"x"}']   # 0 and False kept, empties dropped
    assert not (isinstance(r, tuple) and r[1])                                # no duplicate structured copy
