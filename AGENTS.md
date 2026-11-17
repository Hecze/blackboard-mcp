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

## Start here (any agent / harness)

1. `powershell -ExecutionPolicy Bypass -File scripts\env\doctor.ps1` — checks the Blackboard session, SQL Server,
   yEd, PDF tools and desktop automation, and prints the fix for anything missing (`scripts\env\probe.ps1 -Json`
   gives the raw machine facts: real CPU architecture, Windows language, installed programs).
2. The Blackboard tools are an MCP stdio server (`.venv\Scripts\blackboard-mcp.exe serve`; how to register it in each
   client: `README.md`). Without MCP, call them from Python: `asyncio.run(blackboard_mcp.server.bb_<tool>(...))`.
3. Skills (task playbooks) live in **`skills/<name>/SKILL.md`** — plain Markdown, read them directly if your harness
   doesn't load skills. `.claude/skills/` is a generated mirror: edit `skills/`, then `python scripts/sync_skills.py`.

## Working on an evaluation (T1, T2, final exam, project…)

Follow **[`skills/obtener-contexto-evaluacion/SKILL.md`](skills/obtener-contexto-evaluacion/SKILL.md)**: it finds the
evaluation, its files (including exam statements) and settings, pulls the whole course (`bb_pull_course`), reads the
syllabus, transcribes and analyses every recorded class (`bb_recordings`/`bb_transcript`, one class at a time or in
parallel), checks announcements, settles the scope and writes a sourced dossier in
`estudio/<CODE>-<evaluation>/EXPEDIENTE.md`. Then do whatever the user asked with it, respecting the teacher's rules
recorded there (e.g. AI forbidden in that evaluation). Never submit, save or start attempts in Blackboard.

## Desktop apps and documents (SQL Server/SSMS, yEd, Word…)

Follow **[`skills/preparar-entorno-escritorio/SKILL.md`](skills/preparar-entorno-escritorio/SKILL.md)** and its scripts in
`scripts\env\`. Use the tool the user asked for (yEd means yEd, not a substitute). Never hand-roll SendKeys,
coordinate clicks or a persistent admin broker; anything that needs UAC is run by the student. Windows x86_64 and
ARM64 (verified ARM64 notes at the end of the skill; on ARM64 yEd runs via the "yEd (ARM64)" shortcut / native JDK).

### Before delivering anything (Word/PDF, SQL, diagrams)

Follow **[`skills/entregables-sin-huella/SKILL.md`](skills/entregables-sin-huella/SKILL.md)**: the deliverable must
read as the student's own work and be defensible in the viva.
- Prose: first person, no defining the concept being evaluated, no citing the assignment instructions or the rubric,
  no "en conclusión / a continuación", no closing that repeats the tables.
- SQL: no decorative header, no per-column comments, no `IF OBJECT_ID … DROP` in every table, no `dbo.` everywhere,
  no systematic `CONSTRAINT` prefixes. Keep only what the statement asks for (PK, FK, NULL/NOT NULL, types, `GO`).
- Metadata: `python scripts\limpiar_metadatos.py archivo.docx --autor "<alumno>" --titulo "<T1 …>"` (and the same for
  the PDF). Never ship `python-docx`, the teacher's name as `lastModifiedBy`, or a borrowed document title.
- Never fake authorship, signatures or screenshots; if the course forbids AI, say so first.


### SQL Server without elevation (privilege left on this machine)

To let agents use `sqlcmd`/`pyodbc` as the student's Windows user, a SQL login was created for that user:
`hecze-laptop\hecto` is **sysadmin** on the local `MSSQLSERVER` (created by an earlier agent session, Nov 2026).
- Check: `scripts\env\sql-login.ps1 -Status`
- Narrower alternative: `scripts\env\sql-login.ps1 -Grant -Role dbcreator` (elevated)
- Cleanup when no longer needed: `scripts\env\sql-login.ps1 -Revoke` (elevated)
Record any new lasting privilege like this here.

## How the session stays alive

- Sign-in uses a dedicated Chrome profile at `~/.blackboard-mcp/browser-profile` (Microsoft "stay signed in").
- `blackboard-mcp refresh` renews the session silently (headless). Cibertec hides its SSO button behind
  "Ver opciones", so `auth.py` follows the `/auth-saml/saml/login` link directly.
- Windows scheduled task **"Blackboard keep-alive"** (installed by `scripts/install-keepalive.ps1`) runs
  `scripts/keepalive.ps1` at sign-in and every 4 hours; on failure it shows a Windows popup and logs to
  `~/.blackboard-mcp/keepalive.log`.
- Settings: `~/.blackboard-mcp/config.json` (`base_url`, `sso_button`).
- Exam alarms: scheduled task **"Blackboard alarmas"** (`scripts/install-alarms.ps1`) runs `blackboard-mcp alarms`
  every 15 min; snoozes are stored in `~/.blackboard-mcp/alarms.json`. An alarm only stops when Blackboard shows the
  evaluation submitted/graded — never mark it done or edit that file to silence it.
  The alarm has two buttons: **Hacer con OpenCode** (left; `bbexam://` → `scripts/abrir-examen-opencode.ps1`, which
  creates a session in this repo through the local OpenCode API and sends the "dossier + solve it" prompt) and
  **Posponer** (right). The protocol is registered in HKCU by `alarms.register_app()`; nothing to install.

## Working on the code

- Python venv in `.venv` (on ARM64, `pip install --only-binary=:all: cryptography` first). Tests:
  `.venv\Scripts\python -m pytest -q` (offline). Keep LF line endings. `main` is this fork's branch; `upstream` is
  Mattlo0546/blackboard-mcp.
- Tools, scripts and where files live: `README.md` (single source; don't repeat them here).
- MCP results go out once, as compact JSON without empty fields (`server.tool` decorator); the Python functions
  still return dicts. Prefer adding optional parameters (like `links=True`) over always-on verbose fields.
- Recorded classes: Cibertec runs live lessons in **Class** (cibertec.class.com, Zoom underneath), not Collaborate.
  `classcom.py` uses Zoom's `audio_transcript.vtt` (Class's live captions are a weak fallback) and gets the Class
  `user_uuid` from the Class web app's localStorage after Microsoft SSO (`~/.blackboard-mcp/class.json`).
  Transcripts never drop or summarise content.
- Teachers also post class scripts and diagrams in **announcements** — `bb_pull_course` saves them.
