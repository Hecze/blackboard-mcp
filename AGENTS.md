# AGENTS.md

Fork of [blackboard-mcp](https://github.com/Mattlo0546/blackboard-mcp) used by a Cibertec student
(Ingeniería de Ciencia de Datos e IA) to give the AI full read access to their Blackboard:
`https://cibertec.blackboard.com` (Ultra). Talk to the student in Spanish.

## 🚨 CRITICAL: Blackboard session lost → warn the student IMMEDIATELY

Losing the Blackboard session is the most important thing that can go wrong here: without it the AI
can't see exams, deadlines or the teacher's files, and the student could miss an evaluation.

Treat the session as lost when ANY of these happens:

- A `bb_*` tool returns `login_required: true` (or `critical: true`).
- `~/.blackboard-mcp/session-health.json` has `"ok": false`.
- The MCP server's instructions start with `CRITICAL:`.
- The last line of `~/.blackboard-mcp/keepalive.log` has `exit=` other than `0`.

When it happens:

1. **Stop and tell the student at once**, as the first thing in your reply, before any other work or
   answer, clearly and prominently — e.g. start with `🚨 **CRÍTICO: tu sesión de Blackboard se cerró.**`
   Never hide it, defer it, or only mention it at the end.
2. Say what it means (you can't see their evaluations right now) and what's needed: signing in again once.
3. Offer to run `bb_login` (or `.venv\Scripts\blackboard-mcp.exe login` from a terminal tab the student can
   see — a background shell's window doesn't appear on their screen). The student types their own password
   in that window. **Never ask for, store, or type the student's password.**
4. After they sign in, check that `.venv\Scripts\blackboard-mcp.exe refresh` exits 0, and confirm it.

When starting work in this repo, glance at `session-health.json` first and apply the above if it isn't ok.

## Working on an evaluation (T1, T2, final exam, project…)

Gather its full context with the project skill **`obtener-contexto-evaluacion`**
([.claude/skills/obtener-contexto-evaluacion/SKILL.md](.claude/skills/obtener-contexto-evaluacion/SKILL.md)): it finds the evaluation,
its files and settings, pulls the whole course (`bb_pull_course`), reads the syllabus, transcribes and analyses every
recorded class (`bb_recordings`/`bb_transcript`, one subagent per class), checks announcements, settles the scope and
writes a sourced dossier in `estudio/<CODE>-<evaluation>/EXPEDIENTE.md`. Then do whatever the user asked with it,
respecting the teacher's rules recorded there (e.g. AI forbidden in that evaluation).

## How the session stays alive

- Sign-in uses a dedicated Chrome profile at `~/.blackboard-mcp/browser-profile` (Microsoft "stay signed in").
- `blackboard-mcp refresh` renews the session silently (headless). Cibertec hides its SSO button behind
  "Ver opciones", so `auth.py` follows the `/auth-saml/saml/login` link directly.
- Windows scheduled task **"Blackboard keep-alive"** (installed by `scripts/install-keepalive.ps1`) runs
  `scripts/keepalive.ps1` at sign-in and every 4 hours; on failure it shows a Windows popup and logs to
  `~/.blackboard-mcp/keepalive.log`.
- Settings: `~/.blackboard-mcp/config.json` (`base_url`, `sso_button`).

## Working on the code

- Python venv in `.venv` (Windows ARM64; if `cryptography` fails to build, install it with
  `pip install --only-binary=:all: cryptography`).
- Tests: `.venv\Scripts\python -m pytest -q` (offline, no account needed).
- Keep files LF line endings. Work on a branch; `main` tracks upstream (`git remote upstream`).
- Recorded classes: Cibertec runs live lessons in **Class** (cibertec.class.com, Zoom underneath), not
  Collaborate. `bb_recordings` lists them, `bb_transcript` saves Markdown transcripts under
  `<download_dir>/Grabaciones/<class>/` using Zoom's `audio_transcript.vtt` (good Spanish, speaker names;
  Class's own live captions are much worse and are only a fallback). `classcom.py` gets the Class
  `user_uuid` from the Class web app's localStorage after Microsoft SSO and keeps it in `~/.blackboard-mcp/class.json`.
- Teachers also post class scripts and diagrams in **announcements** — check them, not only course content.
- Main tools: `bb_evaluations` (each evaluation's due date, the student's status, score, feedback,
  instructions and the teacher's attached files such as rubrics), `bb_upcoming`, `bb_browse`,
  `bb_download`, `bb_pull_course` (whole course incl. announcements and SharePoint docs), `bb_announcements`, `bb_sync`.
