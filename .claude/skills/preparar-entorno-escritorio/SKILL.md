---
name: preparar-entorno-escritorio
description: >-
  Deja listo un PC Windows x86_64 para que un agente trabaje con aplicaciones de escritorio de los cursos (SQL Server + SSMS, yEd, Word/.docx, diagramas, PDF) usando herramientas que ya existen — MCP de automatización de Windows por árbol de accesibilidad, MCP de Word, renderizado de diagramas y PDF sin interfaz — en vez de scripts hechos a mano (SendKeys, clics por coordenadas, brokers con permisos de administrador). Úsala antes de cualquier tarea que necesite manejar programas de escritorio o editar documentos.
---

# preparar-entorno-escritorio

Guía para **obtener e instalar** las herramientas que un agente necesita para trabajar con programas de
escritorio en Windows. Plataforma objetivo: **Windows 10/11 x86_64**. ARM64 queda para después (ver al final).

Nace de un intento real en el que el agente lo armó todo a mano: SendKeys que acabaron escribiendo en otra
ventana, clics por coordenadas fallidos, capturas con offset, un broker de administrador hecho en casa e
instaladores sin progreso. Casi todo eso ya existe hecho y mejor. Esta skill dice qué usar.

Habla con el estudiante en español. **Instalar software y conceder permisos siempre lo confirma él.**

---

## 0. Reglas de seguridad (antes de instalar nada)

- **El agente nunca obtiene permisos de administrador permanentes.** Nada de "PowerShell elevado que ejecuta lo
  que aparezca en una carpeta": cualquier programa que escriba ahí se ejecuta como administrador. Si hay que
  instalar algo con UAC, **lo ejecuta el estudiante** (el agente le da el comando exacto), o se aprueba un UAC por
  instalación.
- **Una sesión de Windows dedicada al agente** (otro usuario local o una VM), no el escritorio donde trabaja el
  estudiante. Así el teclado y los clics nunca caen en su ventana.
- Los MCP de escritorio tienen **acceso total al sistema**. Restringe sus herramientas (paso 2) y desactiva la
  telemetría.
- En Blackboard la IA **nunca envía, guarda ni crea intentos** (ver `obtener-contexto-evaluacion`), y respeta las
  reglas del profesor sobre uso de IA en cada evaluación.

## 1. Sondeo del entorno (antes de elegir camino)

Antes de instalar o descargar nada, comprueba esto (en PowerShell):
```powershell
$env:PROCESSOR_ARCHITECTURE                 # AMD64 = x86_64 (esta guía); ARM64 = ver el final
[System.Globalization.CultureInfo]::CurrentUICulture.Name   # idioma de Windows (es-PE, en-US…)
(Get-CimInstance Win32_OperatingSystem).Caption
winget --version; python --version; uv --version; node --version
Get-Package | Where-Object Name -match 'SQL Server|Management Studio|yEd|Office|Word' | Select Name, Version
```
- **El idioma importa**: el instalador de SQL Server falla con un "mismatch de idioma" si la descarga no coincide
  con el idioma de Windows, y el error solo aparece en un diálogo. Elige la descarga según `CurrentUICulture`.
- No vuelvas a descargar lo que ya está instalado.

## 2. Automatización del escritorio: Windows-MCP

**[CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)** (MIT, PyPI `windows-mcp`). Lee el
**árbol de accesibilidad (UI Automation)** de las ventanas, incluidas las de fondo, y busca controles por nombre.
No necesita visión por computadora. Herramientas: Click, Type, Scroll, Shortcut, Wait/WaitFor, Screenshot,
Snapshot, App, Process, Clipboard, FileSystem, PowerShell, Registry…

Requisitos: Windows 10/11, **Python 3.14+** y **uv** (`pip install uv`).

```powershell
# Claude Code, para todos los proyectos:
claude mcp add --transport stdio --scope user windows-mcp -- uvx windows-mcp serve
claude mcp list            # debe aparecer conectado
```
- Restringe lo peligroso. Pasa banderas después de `serve`, por ejemplo `--exclude-tools PowerShell,Registry`,
  y define `ANONYMIZED_TELEMETRY=false` (con `-e` en `claude mcp add`).
- Si da "Connection closed", usa la ruta completa de `uvx.exe`.
- Claude Desktop (`claude_desktop_config.json`):
  `{"mcpServers": {"windows-mcp": {"command": "uvx", "args": ["windows-mcp", "serve"]}}}`.
  La versión de Microsoft Store necesita la ruta absoluta de `uvx.exe`.

Cómo usarlo bien:
- **Primero `Snapshot`** (el árbol de la ventana) y después **clic por nombre**. Las coordenadas solo como último
  recurso.
- Usa **`WaitFor`** en lugar de esperas fijas (`Start-Sleep`).
- Las apps **Java/Swing (como yEd)** casi no exponen UI Automation. Para ellas, evita la interfaz: genera el
  archivo (`.graphml`) y renderízalo sin interfaz (paso 5).

Alternativas, si Windows-MCP no encaja (sin verificar a fondo):
- [felenko/WindowsOSMCP](https://github.com/felenko/WindowsOSMCP): `click_element` por nombre o ID;
- [locomorange/uiautomation-mcp](https://github.com/locomorange/uiautomation-mcp): .NET;
- FlaUI-MCP (.NET 8, de Scott Hanselman);
- servidores basados en **pywinauto**: actúan sin mover el cursor ni robar el foco.

La **app de escritorio de Claude** también trae "computer use", con capturas, clics, teclado y permisos por app.
Para páginas web, usa el navegador integrado o Claude in Chrome en lugar de automatizar el escritorio.

## 3. Instalar programas: winget, con el estudiante aprobando

- Busca siempre el ID exacto. No lo adivines:
  ```powershell
  winget search "SQL Server"; winget search "Management Studio"; winget search yEd; winget search Graphviz
  ```
- Instala mostrando el progreso y guardando un registro:
  ```powershell
  winget install --id <ID> --exact --accept-package-agreements --accept-source-agreements --log "$env:TEMP\winget-<ID>.log"
  ```
  Ejecútalo en una **pestaña de terminal visible** (no en segundo plano) y sigue el registro. Lo que pida UAC lo
  aprueba el estudiante.
- **SQL Server 2022 Developer + SSMS** (curso de Base de Datos):
  - instálalo con el instalador oficial de Microsoft, en el **idioma de Windows** (paso 1); primero el motor y
    después SSMS;
  - si SSMS dice "no se puede ejecutar si la instalación está en curso", hay un `setup.exe` colgado. El estudiante
    lo cierra desde el Administrador de tareas (como administrador);
  - el profesor del curso usa SQL Server 2022 Developer + SSMS (ver las transcripciones del LAB 5/11).
- Para **ejecutar T-SQL** no hace falta la interfaz: `sqlcmd` (viene con SQL Server o como paquete aparte) o
  Python con `pyodbc`. Usa la interfaz solo cuando se necesite una captura de SSMS.

## 4. Documentos Word (.docx)

Por orden de preferencia (MCP de terceros: revisa el estado del repositorio antes de usarlos):
- **[docx-mcp](https://mcpservers.org/fr/servers/securityronin/docx-mcp)**: `uvx docx-mcp-server`. Control de
  cambios, comentarios, notas al pie, `insert_image`.
- **[MeterLong/MCP-Doc](https://playbooks.com/mcp/meterlong/mcp-doc)**: tablas (crear, combinar, editar celdas) e
  imágenes con tamaño.
- **[GongRzhe/Office-Word-MCP-Server](https://github.com/GongRzhe/Office-Word-MCP-Server)**: el más completo
  (`add_table`, `add_picture`, `convert_to_pdf`, insertar cerca de un texto…), pero está **archivado desde marzo
  de 2026**. Úsalo solo si los otros no alcanzan:
  `uvx --from office-word-mcp-server word_mcp_server`.
- Sin MCP: `python-docx` en un venv. Inserta **relativo a un texto ancla**, nunca por índice de párrafo.

**Vista previa visual** (para verificar que no se rompió el formato):
- Word instalado → `convert_to_pdf` (MCP) o Word por COM → PDF;
- PDF → PNG por página: paso 5;
- alternativa comercial con render directo a PNG: Aspose.Words MCP (requiere licencia).

## 5. Diagramas y PDF sin interfaz

- **Graphviz** (`winget search Graphviz`): `dot -Tpng diagrama.dot -o diagrama.png`.
- **Mermaid CLI**: `npm install -g @mermaid-js/mermaid-cli`, luego `mmdc -i diagrama.mmd -o diagrama.png`.
- **yEd / .graphml**: yEd no tiene render por línea de comandos. Genera el `.graphml` (XML) para entregar o editar
  en yEd y, para la imagen, convierte el mismo grafo a DOT o Mermaid. Si el curso exige el estilo de yEd (DER con
  rombos y pata de gallo), el estudiante exporta desde yEd.
- **PDF → PNG**: en x86_64, **PyMuPDF** (`pip install pymupdf`; `page.get_pixmap(dpi=150).save(...)`) o
  `pypdfium2`.

## 6. Capturas

- Con Windows-MCP: `Screenshot` o `Snapshot` de la ventana. Ya no hace falta `CopyFromScreen` con offsets ni
  `PrintWindow`.
- Recortar o redimensionar: `Pillow` en Python.

## 7. Checklist final

- [ ] Sondeo hecho (arquitectura, idioma, lo que ya está instalado).
- [ ] `claude mcp list` muestra `windows-mcp` (y el MCP de Word, si se usa) **conectados**.
- [ ] Herramientas peligrosas excluidas y telemetría desactivada.
- [ ] Programas instalados por el estudiante o aprobados por él, con el registro guardado.
- [ ] Sesión de Windows dedicada al agente.
- [ ] Nada corre con permisos de administrador permanentes.

## ARM64 (pendiente)

Ya se vio que en ARM64 yEd 3.25.1 se cae, PyMuPDF no tiene versión para ARM64 (falla la compilación) y SQL Server
x64 funciona bajo emulación. Cuando toque, se agregará aquí una sección con alternativas verificadas.
