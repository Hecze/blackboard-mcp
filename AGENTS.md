# AGENTS.md

## REGLA FUNDAMENTAL: toda respuesta sale del material del curso

**Ninguna evaluación se contesta con conocimiento general.** Antes de responder una sola pregunta hay que traer el
material del curso desde Blackboard y responder **con ese material delante**:

**Permiso permanente:** cuando el alumno pide resolver una evaluación, autoriza implícitamente a **leer y descargar
cualquier cosa de Blackboard** (documentos, PDF/PPT, Storyline, infografías, grabaciones y transcripciones, el propio
cuestionario). No hace falta pedir permiso para abrir material ni para leer diapositivas o imágenes: es parte del
trabajo. Solo se pide permiso para cosas fuera de Blackboard o que toquen la máquina del alumno.

1. **Sílabo y guía** del curso (qué entra y qué no).
2. **Contenido del tema**: documentos Ultra (`body` de `/learn/api/public/v1/courses/{c}/contents/{id}`), PDFs/PPTs
   de `bbcswebdav`, presentaciones (Storyline/SCORM: `story.html` + `story_content/slide*.xml`), infografías y la
   clase grabada/transcripción (`bb_recordings` / `bb_transcript`).
3. Solo si el material no cubre la pregunta, se busca la fuente que el propio curso cita; **nunca se improvisa**.
4. Si aun así no hay base, se dice («esto no está en el material») en vez de arriesgar la nota.

Consecuencia práctica: un cuestionario de 5 preguntas se responde con el tema abierto al lado; si no se ha leído el
tema, **no se abre el intento**. Muchos admiten un solo intento: abrir sin material es quemar la nota.

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
  It rings for **any** pending submission with a date (`alarm_include`/`alarm_exclude` now only decide what counts as
  "big"). **Big** = T1/T2/T3/EF/sustitutorio/parcial/final: snooze + insist until submitted. **Everything else**
  (cuestionarios, simulaciones, entregables, tareas): rings **once** and is stored with `muted: true`, so it never
  comes back — that is the "Entendido (no insistir)" button.
  The alarm has two buttons: **Hacer con OpenCode** (left) and the snooze one (right). The left one fires `bbexam://` →
  `scripts/abrir-examen-opencode.ps1`, which opens a **new session tab** in the desktop app and leaves the exam prompt
  **written in the input, unsent** (the student presses Enter). It drives the UI on purpose: the API would send the
  message by itself. The payload carries `mode`: `repo` for T1/T2/EF (the statement is a .docx; work in the blackboard
  repo) and `blackboard` for every other activity (it is a form/quiz inside Blackboard: fill it page by page and
  **stop before "Enviar"** so the student verifies and submits). The protocol is registered in HKCU by
  `alarms.register_app()`; nothing to install.
  Alarms go **one at a time**, most urgent first (`alarms.ring_queue`), so several pending activities never stack up.
  The hand-over needs to know which button was pressed, and PowerShell cannot subscribe to WinRT events
  (`Register-ObjectEvent` refuses Windows Runtime objects): `show_toast(..., wait=True)` instead polls
  `ToastNotificationManager.History.GetHistory()` (the toast disappears when the student closes it with the X or
  "Posponer") and the marker file `%TEMP%\bbexam-boton.json`, which the protocol handler writes **before** touching the
  UI. Outcome: `opencode` → the next alarm waits `OPENCODE_PAUSE` (10 min, the student is busy); `dismissed` /
  `entendido` → next one right away; `timeout` (`WAIT_MAX`, 4 h) → the run ends. `alarms.lock` (msvcrt) keeps a single
  run in charge: the scheduled task fires every 15 min and a run can sit waiting for hours.
  Keep that script saved as **UTF-8 with BOM** — PowerShell 5.1 reads it as ANSI otherwise and the prompt comes out
  with `Â«` and `rÃºbrica`. `-DryRun` prints the prompt without touching the app.

## Activities that live inside Blackboard (`navegador.py`)

- Blackboard signs in through **Outlook SSO + MFA**. There is no password to store and nothing an agent can type:
  the session *is* the credential, and it lives in `~/.blackboard-mcp/browser-profile` + `cookies.json` (Chrome,
  refreshed by `bb_login` and the keep-alive task). **Never** ask the student for a password or put one in `.env`.
- The **app's browser has no session**: it is a different browser and lands on the access portal. That is not a bug
  and not a credentials problem — do not try to sign in there.
- `navegador.Navegador` launches the installed Chrome (`settings.browser_channel`) with
  `new_context(storage_state=cookies.json)`, so `bb_navegar` lands signed in. It owns Playwright in **its own thread**
  (the sync API cannot be shared across threads) and keeps the page between calls. Cookies are written back after
  each action, which also keeps the HTTP tools fresh.
- Tools: `bb_navegar` / `bb_ver` / `bb_clic` / `bb_rellenar` / `bb_elegir` / `bb_marcar` / `bb_tecla` / `bb_atras` /
  `bb_captura` / `bb_cerrar_navegador`. Refs (`data-bbt` attributes, `frame:ref` for iframes) expire when the page
  changes; always use the refs from the latest result.
- **`bb_clic` refuses the submit buttons** (`ENVIAR` regex: Enviar / Entregar / Submit / Finalizar intento…): the
  student reviews and presses it. Workflow in `skills/resolver-actividad-blackboard/SKILL.md`.
- "Iniciar intento" burns an attempt and starts the timer: cover that in the prompt/skill and wait for the student.
- Sessions that expire mid-way come back as `login_required` + `critical` from the snapshot; the tool writes it to
  `session-health.json` so the rest of the server reports it too.

### Barreras que ya costaron tiempo (no repetirlas)

Resueltas en `navegador.py` — si tocas el archivo, mantén estas cuatro o el cuestionario vuelve a romperse:

1. **Shadow DOM**: Ultra pinta la evaluación con web components y `document.querySelectorAll` no entra en los
   `shadowRoot`. Las opciones (`Verdadero`/`Falso`) no aparecían ni en el texto ni como `ref`. El snapshot recorre los
   shadow roots a mano y suma su `innerText`.
2. **Radios ocultos**: el `input[type=radio]` real mide 0×0 (se pinta la etiqueta). No se pueden filtrar por
   `visible()`; se incluyen siempre y el clic cae en su `<label>` (`el.labels[0]`/`closest('label')`).
3. **Pestaña nueva**: "Iniciar intento" y "Continuar intento" abren el reproductor en **otra pestaña**. Si el
   navegador se queda en la de atrás, el agente cree que el clic no hizo nada. `clic()` espera hasta 10 s a que
   aparezca una pestaña nueva y se pasa a ella.
4. **Refs caducadas**: Ultra re-renderiza y borra los `data-bbt`, así que una `ref` de hace dos llamadas puede no
   existir. `_resolver()` reintenta: relee la página y busca el elemento por su texto; si tampoco, dice «usa bb_ver».

Y estas son de operación:

- **Los servidores MCP no recargan código**: el proceso los tiene importados. Después de tocar `navegador.py` hay que
  reiniciar la app (o abrir sesión nueva). El cliente lanza **un proceso `blackboard-mcp serve` por sesión**, así que
  sin esto cada uno abría su propia ventana de Chrome. Ahora hay **un solo Chrome compartido por CDP**: el primero que
  llega lo lanza con `--remote-debugging-port=9333` (perfil propio en `~/.blackboard-mcp/chrome-cdp`, sólo 127.0.0.1) y
  los demás se cuelgan con `connect_over_cdp`; las cookies de `cookies.json` se inyectan al conectar.
  `bb_cerrar_navegador` cierra **tu pestaña**, no el navegador de los demás. `BB_CDP_PORT` cambia el puerto y
  `BB_CDP_OFF=1` vuelve al navegador propio (para depurar). Ojo: el perfil `chrome-cdp` es aparte del de `bb_login`;
  si Chrome no está en las rutas habituales, se cae al navegador propio.
- **El intento no se pierde al cerrar**: Blackboard guarda el borrador y "Continuar intento" lo retoma; el intento
  solo se consume al enviarlo o al agotarse el cronómetro (ahí se entrega solo). Cerrar el navegador a mitad es
  seguro — es lo que permite reiniciar tras corregir el código.
- **"Guardar y cerrar" y "Enviar" siguen deshabilitados hasta responder todo**, y el contador «N DE 10 PREGUNTAS
  RESTANTES» se actualiza en el siguiente render, no al instante: no son fallos, no hay que insistir.
- **El botón del pie queda tapado por el modal de confirmación**: al enviar sale «¿Desea enviar el examen?» con un
  `div.modal-backdrop` encima, así que el clic al botón del pie expira. Hay que pulsar el **Enviar del modal** (es el
  último del DOM): por eso `bb_enviar` se llama dos veces, una por cada uno.
- **Ultra pinta la pregunta en diferido**: recién navegado, el snapshot puede venir sin pregunta (sólo «Página 1 de
  10»). `abrir()` espera hasta 6 s a que exista un campo; si aun así sale vacío, `bb_ver` a los segundos.
- **Cada `abrir` navega la pestaña actual**, no abre otra: si el agente cambia de cuestionario, el intento anterior se
  queda sin pestaña (el borrador sigue en Blackboard). Para volver: "Continuar intento".
- **Enviar**: `bb_clic` se niega con «Enviar» siempre; `bb_enviar` existe para cuando el alumno lo autoriza
  explícitamente en la conversación. El envío deja el intento calificado en segundos.
- **Trabajos en equipo: no se tocan.** Ni abrir. Si el título o las instrucciones huelen a grupo («grupal», «en
  equipo», «avance de proyecto», «entregable», «integrantes»), se avisa al alumno y se para: no es un cuestionario
  individual, y resolverlo por él rompe la evaluación del grupo.
- **PS 5.1 `Set-Content -Encoding utf8` escribe BOM** y `json.loads` revienta con BOM: al pasar JSON entre procesos
  usar `[IO.File]::WriteAllText(..., UTF8Encoding($false))` o leer con `utf-8-sig`.

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
