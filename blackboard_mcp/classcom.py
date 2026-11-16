"""Class (class.com) — the virtual classroom some schools run their live Zoom/Teams lessons through, launched
from Blackboard ("Launch Class"). Its recordings come with Zoom's transcript, where every line carries the
speaker's name, plus the session chat. This module lists a student's classes and recordings and turns a
recording into a readable transcript that tells the teacher apart from the students.

Auth: Class's API identifies the student by a `user_uuid` header. We get it once by signing in to Class with
the same browser profile Blackboard uses (Microsoft SSO), and keep it in ~/.blackboard-mcp/class.json.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .config import Settings

# Lines of the transcript that are the computer's audio the teacher shared (videos, music), not speech.
SHARED_AUDIO = re.compile(r"^Audio shared by ", re.I)
CUE_TIME = re.compile(r"(\d+):(\d\d):(\d\d)\.(\d+)\s*-->\s*(\d+):(\d\d):(\d\d)\.(\d+)")


class ClassLoginRequired(RuntimeError):
    pass


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


class ClassClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.s = settings
        self.state_path = settings.home / "class.json"
        self.state = self._load()
        self._transport = transport

    # -- state / auth -------------------------------------------------------
    def _load(self) -> dict:
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=1))
        try:
            self.state_path.chmod(0o600)
        except OSError:
            pass

    @property
    def web(self) -> str:
        return (self.state.get("web") or self.s.class_web or "").rstrip("/")

    @property
    def api(self) -> str:
        if not self.state.get("api"):
            if not self.web:
                raise ClassLoginRequired("No Class address set (class_web in ~/.blackboard-mcp/config.json, "
                                         "e.g. https://yourschool.class.com).")
            self.state["api"] = httpx.get(self.web + "/env.json", timeout=30).json()["api"]
            self._save()
        return self.state["api"].rstrip("/")

    def login(self, headless: bool = True, timeout_s: int = 90) -> dict:
        """Sign in to Class through Microsoft SSO in the Blackboard browser profile and keep the user_uuid."""
        from playwright.sync_api import sync_playwright

        from .auth import _launch
        found: dict = {}
        with sync_playwright() as pw:
            ctx = _launch(pw, self.s, headless)
            try:
                ctx.on("request", lambda r: found.setdefault("uuid", r.headers.get("user_uuid"))
                       if r.headers.get("user_uuid") else None)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(self.web + "/teams", wait_until="domcontentloaded", timeout=60000)
                deadline = datetime.now() + timedelta(seconds=timeout_s)
                while not found.get("uuid") and datetime.now() < deadline:
                    for text in ("Iniciar sesión con Microsoft", "Sign in with Microsoft", "Microsoft",
                                 "Iniciar sesión", "Sign in", "Log in"):
                        try:
                            btn = page.get_by_text(text, exact=False).first
                            if btn.count() and btn.is_visible():
                                btn.click(timeout=3000)
                                page.wait_for_timeout(4000)
                                break
                        except Exception:
                            pass
                    page.wait_for_timeout(2000)
                    try:   # the Class web app keeps the signed-in user's uuid in localStorage
                        uid = page.evaluate("() => localStorage.getItem('user_uuid')")
                        if uid:
                            found["uuid"] = uid
                    except Exception:
                        pass
                    if found.get("uuid"):
                        break
                    if "/teams" not in page.url and self.web in page.url:
                        page.goto(self.web + "/teams", wait_until="domcontentloaded", timeout=60000)
            finally:
                ctx.close()
        if not found.get("uuid"):
            raise ClassLoginRequired("Couldn't sign in to Class. Sign in to Blackboard again (bb_login) and retry.")
        self.state["user_uuid"] = found["uuid"]
        self._save()
        return {"ok": True}

    def _call(self, method: str, path: str, *, retry: bool = True, **kw):
        if not self.state.get("user_uuid"):
            self.login()
        uid = self.state["user_uuid"]
        with httpx.Client(transport=self._transport, timeout=httpx.Timeout(30, read=180)) as c:
            r = c.request(method, self.api + path, headers={"user_uuid": uid, "x-class-user-uuid": uid}, **kw)
        if r.status_code in (401, 403) and retry:
            self.state.pop("user_uuid", None)
            self.login()
            return self._call(method, path, retry=False, **kw)
        if r.status_code in (401, 403):
            raise ClassLoginRequired(f"Class refused the request ({r.status_code}).")
        r.raise_for_status()
        return r.json()

    # -- data ---------------------------------------------------------------
    def classes(self) -> list[dict]:
        """Every Class class the student is in (e.g. "Base de Datos_Lopez Lopez, Jaime TEO" and its LAB)."""
        out, seen = [], set()
        for c in self._call("GET", "/api/zoom/get_user_classes"):
            if c.get("class_uuid") in seen:
                continue
            seen.add(c["class_uuid"])
            out.append({"class_uuid": c["class_uuid"], "class_name": c.get("class_name"),
                        "teacher": c.get("teacher_name"), "provider": c.get("meeting_provider")})
        return out

    def classes_for(self, course_name: str) -> list[dict]:
        """Classes whose name matches a Blackboard course ("GDAT5373 BASE DE DATOS" ~ "Base de Datos_… TEO")."""
        q = _norm(re.sub(r"^[A-Z]{2,5}\d{3,5}\s+", "", course_name.strip()))
        cs = self.classes()
        hits = [c for c in cs if _norm(c["class_name"].split("_")[0]) == q] or \
               [c for c in cs if q and (q in _norm(c["class_name"]) or _norm(c["class_name"].split("_")[0]) in q)]
        return hits

    def school_uuid(self) -> str:
        if not self.state.get("school_uuid"):
            self.state["school_uuid"] = self._call("GET", "/api/zoom/get_school_info")["school_uuid"]
            self._save()
        return self.state["school_uuid"]

    def recordings(self, class_uuid: str) -> list[dict]:
        data = self._call("GET", f"/recording/v1/schools/{self.school_uuid()}/class/{class_uuid}/recordings")
        return sorted(data.get("recordings", []), key=lambda r: r.get("when") or "")

    def session(self, class_uuid: str, recording_id: str) -> dict:
        """Everything the recording player loads: transcript, chat, participants, media/VTT links."""
        return self._call("POST", f"/meeting/{class_uuid}/v1_join_async_meeting", json={"recordingUuid": recording_id})

    # -- transcript ---------------------------------------------------------
    def transcript(self, class_uuid: str, recording_id: str, class_name: str = "", teacher_hint: str = "") -> dict:
        d = self.session(class_uuid, recording_id)
        rec = d.get("recordingData") or {}
        start = datetime.fromisoformat((rec.get("when") or "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
        hosts = {z.get("user_name") for z in (d.get("zoomStates") or {}).values() if z.get("is_host")}
        teacher = _pick_teacher(hosts, teacher_hint, d)

        source, lines = "zoom", []
        vtt_url = next((a["url"] for a in rec.get("artifactsComplete") or [] if a.get("contents") == "audio_transcript"), None)
        if vtt_url:
            lines = parse_vtt(httpx.get(vtt_url, timeout=180).text)
        if not lines:   # fall back to Class's own live captions (weaker: often mixes Spanish and English)
            source = "class"
            for t in rec.get("transcripts") or []:
                dt = t.get("data") or {}
                off = (dt.get("start_time") or t.get("timestamp") or 0) / 1000 - start.timestamp()
                lines.append({"t": off, "end": off + 3, "speaker": dt.get("user_name") or "?", "text": t.get("content") or ""})
        chats = []
        for c in d.get("chats") or []:
            if c.get("type") != "public":
                continue
            frm = ((c.get("data") or {}).get("from") or {}).get("name") or "?"
            chats.append({"t": c.get("timestamp", 0) / 1000 - start.timestamp(), "speaker": frm,
                          "text": (c.get("data") or {}).get("content") or "", "chat": True})
        return {"class_name": class_name or d.get("meetingTopic"), "recording_id": recording_id, "start": start,
                "duration_s": rec.get("duration"), "teacher": teacher, "source": source,
                "participants": len(d.get("students") or []), "lines": lines, "chats": chats}


def _pick_teacher(hosts: set, hint: str, d: dict) -> str | None:
    hint_words = set(_norm(hint).split())
    for h in hosts:
        if hint_words and hint_words & set(_norm(h).split()):
            return h
    if hosts:
        return sorted(hosts)[0]
    m = re.search(r"_(.+?),\s*(\S+)", d.get("meetingTopic") or "")   # "Base de Datos_Lopez Lopez, Jaime TEO"
    return f"{m.group(2)} {m.group(1)}".upper() if m else None


def parse_vtt(vtt: str) -> list[dict]:
    """Zoom transcript VTT → [{t, end, speaker, text}] (seconds from the recording start), dropping shared audio."""
    out = []
    for block in re.split(r"\n\s*\n", vtt.replace("\r", "")):
        m = CUE_TIME.search(block)
        if not m:
            continue
        g = list(map(int, m.groups()))
        t = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        text = " ".join(block[m.end():].strip().splitlines()).strip()
        speaker, _, said = text.partition(": ")
        if not said or len(speaker) > 80:
            speaker, said = "?", text
        if SHARED_AUDIO.match(speaker) or not said.strip():
            continue
        out.append({"t": t, "end": end, "speaker": speaker.strip(), "text": said.strip()})
    return out


def _aliases(names: list[str]) -> dict[str, str]:
    """Short, unique names for the legend: first given name, then + first surname / initial if two clash."""
    words = {n: n.title().split() for n in names}
    alias = {n: (w[0] if w else n) for n, w in words.items()}
    for level in (2, 3):
        clash = {a for a in alias.values() if list(alias.values()).count(a) > 1}
        for n in names:
            if alias[n] in clash and len(words[n]) >= level:
                alias[n] = " ".join(words[n][:1] + words[n][level - 1:level])   # "Juan Novoa", "Juan Perez"
    return alias


def to_markdown(tr: dict, tz_offset_h: int = -5) -> str:
    """Readable, compact transcript. Nothing is summarised or dropped: every spoken line and every chat message is
    kept (any passing remark may matter). Speakers are 🎓 (the teacher) or 🙋 + a short name, expanded once in the
    legend; consecutive lines of one speaker are merged into a paragraph; the public chat is interleaved."""
    teacher = tr.get("teacher")
    tn = set(_norm(teacher).split()) if teacher else set()

    def is_teacher(name: str) -> bool:
        return bool(teacher) and (name == teacher or (len(tn) > 0 and len(tn & set(_norm(name).split())) >= 2))

    people = sorted({x["speaker"] for x in tr["lines"] + tr["chats"] if x["speaker"] != "?" and not is_teacher(x["speaker"])})
    alias = _aliases(people)

    def who(name: str) -> str:
        if is_teacher(name):
            return "🎓"
        return f"🙋 {alias[name]}" if name in alias else "❔"

    items = sorted(tr["lines"] + tr["chats"], key=lambda x: x["t"])
    local = tr["start"].astimezone(timezone(timedelta(hours=tz_offset_h)))
    spoke = {x["speaker"] for x in tr["lines"]}
    head = [
        f"# {tr['class_name']} — {local:%d/%m/%Y %H:%M}",
        "",
        f"Duración {_hms(tr.get('duration_s') or 0)} · {tr.get('participants')} asistentes · transcripción "
        f"{'de Zoom (con hablantes)' if tr['source'] == 'zoom' else 'de subtítulos en vivo de Class (calidad baja)'}, "
        "automática: puede tener palabras mal reconocidas. [hh:mm:ss] = minuto de la grabación · 💬 = chat.",
        "",
        f"- 🎓 = profesor {(teacher or '?').title()}",
        *[f"- 🙋 {alias[n]} = {n.title()}{'' if n in spoke else ' (solo chat)'}" for n in people],
        "",
        "---",
        "",
    ]
    body, cur, buf, t0, last_end = [], None, [], 0.0, 0.0

    def flush():
        if buf:
            body.append(f"**[{_hms(t0)}] {who(cur)}:** {' '.join(buf)}\n")

    for x in items:
        if x.get("chat"):
            flush()
            buf, cur = [], None
            body.append(f"> 💬 [{_hms(x['t'])}] {who(x['speaker'])}: {x['text']}\n")
            continue
        if x["speaker"] == cur and x["t"] - last_end < 25 and len(" ".join(buf)) < 1200:
            buf.append(x["text"])
        else:
            flush()
            cur, buf, t0 = x["speaker"], [x["text"]], x["t"]
        last_end = x.get("end", x["t"])
    flush()
    return "\n".join(head + body)
