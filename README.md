# blackboard-mcp (fork para Cibertec, Windows)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)

Fork de [Mattlo0546/blackboard-mcp](https://github.com/Mattlo0546/blackboard-mcp) adaptado a un estudiante de
**Cibertec** (`https://cibertec.blackboard.com`, Blackboard Ultra) en **Windows (x86_64 y ARM64)**. Da a un
agente de IA acceso **de solo lectura** a todo lo del curso:
- evaluaciones, su estado y sus archivos (rúbricas y enunciados);
- el material completo del curso, los anuncios y los documentos de SharePoint;
- las **clases grabadas** (Class / Zoom) como transcripciones que separan al profesor de los alumnos.

Funciona con **cualquier cliente o harness** que hable MCP por stdio: Claude Code o Desktop, Codex, OpenCode,
Cursor, VS Code… Si tu agente no usa MCP, cada herramienta también es una función de Python.

> **Para agentes:** empieza por [`AGENTS.md`](AGENTS.md). Las skills están en [`skills/`](skills/).

## Instalación (Windows)

```powershell
git clone https://github.com/Hecze/blackboard-mcp.git; cd blackboard-mcp
python -m venv .venv
.venv\Scripts\pip install --only-binary=:all: cryptography   # en ARM64, para no compilarla
.venv\Scripts\pip install -e .
```

Configuración en `%USERPROFILE%\.blackboard-mcp\config.json`:
```json
{
  "base_url": "https://cibertec.blackboard.com",
  "sso_button": "SAML Docentes y Estudiantes",
  "class_web": "https://cibertec.class.com"
}
```
- `base_url`: la dirección de tu Blackboard.
- `sso_button`: el texto del botón de inicio de sesión. Opcional.
- `class_web`: el sitio de Class de tu institución, para las grabaciones. Opcional.

Las variables `BB_BASE_URL`, `BB_SSO_BUTTON` y `BB_CLASS_WEB` tienen prioridad sobre el archivo.

Alarmas de exámenes (opcional, mismo archivo): `"alarm_days": 7` (cuántos días antes empiezan a sonar),
`"alarm_include"` y `"alarm_exclude"` (expresiones regulares sobre el título; por defecto suenan T1/T2/T3, EF,
examen, sustitutorio, parcial y final, y no los cuestionarios ni la asistencia). Es una **notificación de alarma nativa de Windows** (se queda en pantalla, sonido de alarma en bucle) con dos botones: **Hacer con OpenCode** (abre una pestaña nueva y deja el prompt del examen escrito en el input, sin enviarlo: tú decides cuándo darle Enter) y **Posponer** (2 h, o menos para que el último aviso llegue al menos 1 h antes del vencimiento; en esa última hora suena cada 15 min).

Inicio de sesión (una vez; **el estudiante escribe su contraseña en la ventana que se abre**, el agente nunca):
```powershell
.venv\Scripts\blackboard-mcp.exe login
```
Mantener la sesión viva (tarea programada cada 4 h, sin permisos de administrador):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-keepalive.ps1
```
Comprobar todo:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\env\doctor.ps1
```

## Registrar el servidor en tu cliente

Es un servidor MCP **stdio**. El comando es `<repo>\.venv\Scripts\blackboard-mcp.exe` con el argumento `serve`.
Usa la ruta absoluta y sigue la documentación de tu cliente:

| Cliente | Configuración |
|---|---|
| Claude Code | `claude mcp add --scope user blackboard -- C:\ruta\blackboard-mcp\.venv\Scripts\blackboard-mcp.exe serve` |
| Claude Desktop, Cursor, VS Code y otros con `mcpServers` | `{"mcpServers": {"blackboard": {"command": "C:\\ruta\\blackboard-mcp\\.venv\\Scripts\\blackboard-mcp.exe", "args": ["serve"]}}}` |
| OpenCode (`opencode.json`) | `{"mcp": {"blackboard": {"type": "local", "command": ["C:\\ruta\\blackboard-mcp\\.venv\\Scripts\\blackboard-mcp.exe", "serve"]}}}` |
| Codex CLI (`~/.codex/config.toml`) | `[mcp_servers.blackboard]`, `command = 'C:\ruta\blackboard-mcp\.venv\Scripts\blackboard-mcp.exe'`, `args = ["serve"]` |

**Sin MCP**, desde Python:
```powershell
.venv\Scripts\python -c "import asyncio; from blackboard_mcp import server; print(asyncio.run(server.bb_evaluations('GDAT5373')))"
```

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `bb_login` / `bb_status` | Iniciar sesión (prueba primero renovarla en silencio) y ver la cuenta, la carpeta de descargas y el estado de la sesión |
| `bb_courses` | Cursos actuales (`include_all` para todos) |
| `bb_evaluations` | Todas las evaluaciones de un curso (o de todos): fecha límite, tu estado (pendiente / enviada / calificada / vencida), nota, comentario, instrucciones y **archivos del profesor**, incluido el enunciado de exámenes como la T1 |
| `bb_download` | Baja los archivos de un elemento o evaluación |
| `bb_pull_course` | Baja **todo** el curso con sus carpetas, más anuncios, documentos de SharePoint (sílabo, manuales) y un `manifest.json` |
| `bb_browse` | Contenido de un curso o carpeta |
| `bb_upcoming` | Próximas fechas de entrega |
| `bb_announcements` | Anuncios recientes |
| `bb_recordings` | Clases grabadas en Class (salas TEO y LAB) |
| `bb_transcript` | Transcripciones en Markdown: **🎓 PROFESOR** vs **🙋 Alumno: nombre**, con el minuto y el chat de clase |
| `bb_sync` / `bb_sync_status` / `bb_set_courses` | Sincronizar los PDF de los cursos (del proyecto original) |

Todo es **de solo lectura**: nunca entrega, guarda ni crea intentos en Blackboard.

## Dónde quedan las cosas

| Qué | Dónde |
|---|---|
| Descargas | `%USERPROFILE%\BlackboardFiles\<curso>\Todo\` (curso completo), `…\Downloads\`, `…\Grabaciones\` |
| Sesión y configuración | `%USERPROFILE%\.blackboard-mcp\`: **privado**, nunca lo subas (`cookies.json`, `class.json`, `browser-profile\`) |
| Apuntes y expedientes | `estudio\` en el repo (en `.gitignore`) |

## Skills (instrucciones para agentes)

Las fuentes están en [`skills/`](skills/): Markdown con frontmatter YAML, legibles por cualquier agente.
`python scripts/sync_skills.py` las copia a las carpetas que algunos harnesses leen solos (`.claude/skills/`).

- [`obtener-contexto-evaluacion`](skills/obtener-contexto-evaluacion/SKILL.md): reúne todo sobre una evaluación
  (fecha real, reglas, enunciado, rúbrica, sílabo, material, anuncios, lo que dijo el profesor en clase) en un
  expediente con fuentes.
- [`preparar-entorno-escritorio`](skills/preparar-entorno-escritorio/SKILL.md): deja listo el PC para programas de
  escritorio (SQL Server, SSMS, yEd, Word) con scripts de `scripts\env\` y MCP que ya existen. Incluye las notas
  verificadas de ARM64.

## Scripts

| Script | Para qué |
|---|---|
| `scripts\env\probe.ps1 [-Json]` | Describe el PC (arquitectura real, idioma, lo instalado) |
| `scripts\env\doctor.ps1` | Revisa todo y dice cómo arreglar lo que falta |
| `scripts\env\install-sqlserver.ps1`, `install-ssms.ps1` | SQL Server y SSMS con winget (el estudiante aprueba UAC) |
| `scripts\env\sql-login.ps1 -Status/-Grant/-Revoke` | Usar SQL Server sin elevación, o deshacerlo |
| `scripts\env\install-yed-arm64.ps1` | yEd en ARM64 (JDK ARM64 + accesos directos) |
| `scripts\pdf2png.py` | PDF a PNG |
| `scripts\install-keepalive.ps1` | Tarea que renueva la sesión de Blackboard |
| `scripts\install-alarms.ps1` | Tarea **"Blackboard alarmas"**: cada 15 min revisa tus exámenes (T1, T2, T3, EF, sustitutorio, parcial…) y muestra una alarma nativa de Windows que solo se pospone, no se apaga, hasta que Blackboard los marque como enviados. Prueba: `blackboard-mcp alarms --demo` |
| `scripts\sync_skills.py` | Copia `skills/` a las carpetas de cada harness |

## Desarrollo

```powershell
.venv\Scripts\python -m pytest -q        # pruebas sin conexión
python scripts/sync_skills.py --check    # las copias de las skills están al día
```
Licencia MIT. Basado en el trabajo de [Mattlo0546](https://github.com/Mattlo0546/blackboard-mcp), que lo publicó
para universidades del Reino Unido (macOS y SlideMate). Este fork no está afiliado con Anthology, Blackboard,
Class Technologies ni Cibertec.
