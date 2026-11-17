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


def test_alarms_ring_for_any_submission_but_only_big_ones_insist():
    from datetime import timedelta
    from blackboard_mcp.alarms import course_title, due_alarms, human_left, is_big, snooze_for, toast_xml
    for t in ("Examen T1", "T2", "EVALUACIÓN T1", "Examen Final", "EF", "Examen Sustitutorio", "Examen Certificado"):
        assert is_big(t), t
    for t in ("Minicuestionario N° 1 Parte 1", "Asistencia", "Cuestionario Tema 1", "Entregable al 50%"):
        assert not is_big(t), t
    ev = lambda title, status="pending", hours=20, kind="submission", col=None: {
        "title": title, "status": status, "kind": kind, "column_id": col or title,
        "due": (NOW + timedelta(hours=hours)).isoformat()}
    course = {"BD": [ev("Examen T1"), ev("Examen T2", status="submitted"), ev("T3", status="graded"),
                     ev("Examen Final", hours=24 * 30), ev("Examen Sustitutorio", hours=-1), ev("Minicuestionario N°2"),
                     ev("EF", status="draft", hours=3), ev("Asistencia", kind="grade_only")]}
    rang = due_alarms(course, NOW, {})
    # every pending submission rings, most urgent first; the "big" ones are flagged so they can insist
    assert [a["title"] for a in rang] == ["EF", "Examen T1", "Minicuestionario N°2"]
    assert [a["big"] for a in rang] == [True, True, False]
    # a snoozed big one is quiet for that time; a muted small one never comes back
    snoozed = {"Examen T1": {"snoozed_until": (NOW + timedelta(hours=1)).isoformat()}}
    assert [a["title"] for a in due_alarms(course, NOW, snoozed)] == ["EF", "Minicuestionario N°2"]
    muted = {"Minicuestionario N°2": {"muted": True}}
    assert [a["title"] for a in due_alarms(course, NOW, muted)] == ["EF", "Examen T1"]
    # one snooze: 1 h (lo que hace también cerrar con la X), shortened so the next ring is still >= 1 h before the
    # deadline; last hour every 15 min
    assert snooze_for(timedelta(days=2)) == timedelta(hours=1)
    assert snooze_for(timedelta(hours=3)) == timedelta(hours=1)
    assert snooze_for(timedelta(hours=1, minutes=30)) == timedelta(minutes=30)
    assert snooze_for(timedelta(minutes=50)) == timedelta(minutes=15)
    assert snooze_for(timedelta(minutes=5)) == timedelta(minutes=5)
    assert human_left(timedelta(hours=15, minutes=20)) == "15 h 20 min" and human_left(timedelta(days=2, hours=3)) == "2 d 3 h"
    assert course_title("GDAT5373 BASE DE DATOS [CIBERTEC.GDAT5373.2026]") == "Base de Datos"
    x = toast_xml("Examen T1", "Base de Datos", timedelta(hours=15, minutes=20), timedelta(hours=2))
    assert 'scenario="alarm"' in x and "Looping.Alarm" in x and x.count("<action ") == 1 and "Posponer 2 h" in x
    assert "<text>Examen T1 · Base de Datos</text><text>Quedan 15 h 20 min</text>" in x and "Vence" not in x

    # two buttons: "Hacer con OpenCode" (protocol, first = left) and the snooze/silence one
    from datetime import datetime, timezone
    from blackboard_mcp.alarms import PROTOCOL, exam_arg
    alarm = {"title": "Examen T1", "course": "GDAT5373 BASE DE DATOS",
             "due": datetime(2026, 11, 19, 12, tzinfo=timezone.utc), "left": timedelta(hours=15, minutes=20), "big": True}
    arg = exam_arg(alarm)
    assert arg.startswith(f"{PROTOCOL}://abrir?data=") and "Examen%20T1" in arg.replace("+", "%20")
    y = toast_xml("Examen T1", "Base de Datos", timedelta(hours=15, minutes=20), timedelta(hours=2), open_arg=arg)
    assert y.count("<action ") == 2
    assert y.index("Hacer con OpenCode") < y.index("Posponer")          # left to right
    assert f'activationType="protocol" arguments="{arg}"' in y.replace("&#x27;", "'")

    # small activity: the right button is a protocol action (so "cerrar con la X" NO silencia: vuelve en 1 h), and
    # the prompt sends us to Blackboard
    small = dict(alarm, title="Cuestionario Tema 3", big=False, url="https://x/outline", key="col_123")
    small_arg = exam_arg(small)
    assert "%22mode%22%3A%20%22blackboard%22" in small_arg
    from blackboard_mcp.alarms import mute_arg
    marg = mute_arg(small)
    assert "entendido?" in marg
    z = toast_xml("Cuestionario Tema 3", "Análisis y Diseño de Software", timedelta(hours=15), timedelta(hours=1),
                  open_arg=small_arg, big=False, mute=marg)
    assert "Entendido (no insistir)" in z and "Posponer" not in z and z.count("<action ") == 2
    assert f'activationType="protocol" arguments="{marg}"' in z.replace("&#x27;", "'")
    # sin mute (por si faltara), cae al botón de posponer (dismiss)
    z2 = toast_xml("Cuestionario Tema 3", "X", timedelta(hours=15), timedelta(hours=1), big=False)
    assert "Posponer 1 h" in z2 and z2.count("<action ") == 1
    assert "%22mode%22%3A%20%22repo%22" in arg     # T1 sigue yendo por el repo
    # el payload lleva el tag de la notificación: el handler lo usa para decirle al vigía qué botón se pulsó
    assert "%22tag%22%3A%20%22col_123%22" in small_arg and "%22tag%22%3A%20%22col_123%22" in marg


def test_alarms_are_shown_one_at_a_time():
    """Una sola notificación a la vez: la siguiente aparece al instante (X/Posponer/Entendido) o a los 10 min
    después de "Hacer con OpenCode"."""
    from blackboard_mcp.alarms import OPENCODE_PAUSE, ring_queue, toast_tag
    assert toast_tag("_4032653_1") == "_4032653_1"                  # el tag real de Blackboard se conserva
    assert toast_tag("a b/c·d") == "a_b_c_d" and len(toast_tag("x" * 200)) == 60

    queue_ = [{"title": "A"}, {"title": "B"}, {"title": "C"}]

    def player(outcomes):
        pending, shown = list(outcomes), []

        def show(a):
            shown.append(a["title"])
            return pending.pop(0)
        return show, shown

    # X, Posponer o Entendido → la siguiente entra al instante, sin esperas
    show, shown = player(["dismissed", "entendido", "dismissed"])
    slept = []
    assert ring_queue(queue_, show, sleep=slept.append) == ["dismissed", "entendido", "dismissed"]
    assert shown == ["A", "B", "C"] and slept == []

    # "Hacer con OpenCode" → 10 min antes de la siguiente (y no espera después de la última)
    show, shown = player(["opencode", "dismissed", "opencode"])
    slept = []
    assert ring_queue(queue_, show, sleep=slept.append) == ["opencode", "dismissed", "opencode"]
    assert slept == [OPENCODE_PAUSE.total_seconds()] == [600]
    assert OPENCODE_PAUSE.total_seconds() == 600




def test_snapshot_pierces_shadow_dom_and_keeps_hidden_radios():
    # Ultra pinta la evaluación con web components (shadow DOM) y los radios reales miden 0x0: si alguien
    # "simplifica" el snapshot, las opciones desaparecen y el agente no puede responder.
    from blackboard_mcp.navegador import _SNAP
    assert "shadowRoot" in _SNAP and "esOpcion" in _SNAP and "closest('label')" in _SNAP


def test_navegador_blocks_the_submit_button_and_spots_the_login_page():
    """Las actividades dentro de Blackboard se resuelven con `bb_*` sobre la sesión guardada; el envío es del alumno."""
    from blackboard_mcp.config import Settings
    from blackboard_mcp.navegador import ENVIAR, Navegador
    for t in ("Enviar", "enviar intento", "Entregar", " Guardar y enviar ", "Submit", "Finalizar intento"):
        assert ENVIAR.match(t), t
    for t in ("Guardar", "Guardar borrador", "Siguiente", "Iniciar intento", "Anterior", ""):
        assert not ENVIAR.match(t), t
    nav = Navegador(Settings(base_url="https://cibertec.blackboard.com"))
    assert not nav._login_required("https://cibertec.blackboard.com/ultra/courses/_1_1/outline")
    assert nav._login_required("https://login.microsoftonline.com/xyz/oauth2/authorize")
    assert nav._login_required("https://cibertec.blackboard.com/webapps/login/")   # sin /ultra: portal de acceso


def test_blackboard_mcp_exposes_the_navigator_tools():
    import asyncio

    from blackboard_mcp import server
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"bb_navegar", "bb_ver", "bb_clic", "bb_rellenar", "bb_elegir", "bb_marcar", "bb_tecla", "bb_atras",
            "bb_captura", "bb_cerrar_navegador"} <= names


def test_course_labels_unique_for_repeated_courses():
    from blackboard_mcp.bb import course_labels
    a = Course(id="_1", course_id="CIBERTEC.GDAT5373.202610202612", name="GDAT5373 BASE DE DATOS", code="GDAT5373")
    b = Course(id="_2", course_id="CIBERTEC.GDAT5373.202607202608", name="GDAT5373 BASE DE DATOS", code="GDAT5373")
    c = Course(id="_3", course_id="X", name="MATE5491 MATEMATICA II", code="MATE5491")
    lab = course_labels([a, b, c])
    assert lab["_3"] == "MATE5491 MATEMATICA II" and lab["_1"] != lab["_2"] and "202610202612" in lab["_1"]
