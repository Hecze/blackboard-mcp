---
name: preparar-entorno-escritorio
description: >-
  Deja listo un PC Windows (x86_64 o ARM64) para que un agente trabaje con aplicaciones de escritorio de los cursos (SQL Server + SSMS, yEd, Word/.docx, diagramas, PDF) usando herramientas que ya existen — MCP de automatización de Windows por árbol de accesibilidad, MCP de Word, renderizado de diagramas y PDF sin interfaz — en vez de scripts hechos a mano (SendKeys, clics por coordenadas, brokers con permisos de administrador). Úsala antes de cualquier tarea que necesite manejar programas de escritorio o editar documentos.
---

# preparar-entorno-escritorio

Guía para **obtener e instalar** las herramientas que un agente necesita para trabajar con programas de
escritorio en Windows. Plataforma: **Windows 10/11 x86_64**, y **ARM64** con las particularidades verificadas al final.

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

## 0.1 Fidelidad a la herramienta pedida

- **Si el usuario o el curso piden una herramienta concreta (yEd, SSMS, Word…), se usa esa herramienta.** No se
  sustituye por "algo parecido" (Mermaid o Graphviz en lugar de yEd, LibreOffice en lugar de Word, un script en
  lugar de SSMS) aunque sea más fácil de automatizar.
- Esta guía documenta **todas las formas conocidas** de hacer funcionar y automatizar cada herramienta. Si ninguna
  funciona, se dice claramente qué falla y se pregunta al usuario. No se cambia de herramienta por iniciativa
  propia.
- Las herramientas "sin interfaz" del paso 5 son para cuando **no** se pidió una herramienta concreta.

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
- Las apps **Java/Swing (como yEd)** casi no exponen UI Automation. Para ellas, ver el paso 5.1 (yEd): atajos de
  teclado dirigidos a la ventana, Java Access Bridge, o editar el `.graphml` y abrirlo en yEd.

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

## 5. Diagramas y PDF

### 5.1 yEd (cuando se pide yEd, que es lo que usa el curso de Base de Datos)

Instalación: `winget search yEd` o el instalador de yWorks. Queda en `C:\Users\<usuario>\yEd\` con `yEd.exe`,
`yed.jar` y un Java propio en `jre\`.

Todas las formas de trabajar con yEd:
1. **Interfaz de yEd** (lo que hace el estudiante): dibujar y luego *File → Export* a PNG, JPG o SVG.
2. **Generar o editar el `.graphml`** (XML) con código y **abrirlo en yEd**: `yEd.exe archivo.graphml` o
   `java -jar yed.jar archivo.graphml`. Con *Layout* se reordena y luego se exporta desde yEd. El `.graphml`
   también es lo que suele entregarse. Los del profesor están en `Todo\ANUNCIOS\*.graphml` y sirven de plantilla
   para el estilo (formas, pata de gallo).
3. **Automatizar la interfaz de yEd**: es Swing, así que UI Automation no ve sus controles. Opciones:
   - **atajos de teclado** dirigidos a la ventana de yEd (Windows-MCP `Shortcut`/`Type` con la ventana enfocada y
     el título verificado), sin clics a ciegas;
   - **Java Access Bridge**: `jabswitch -enable` (viene con el JDK) expone los controles Swing a las herramientas
     de accesibilidad. Bibliotecas que lo usan desde Python: `pyjab`, `JABWrapper`. **Sin verificar con yEd.**
   - Capturas con `Snapshot`/`Screenshot` de Windows-MCP para comprobar cada paso.
4. yEd **no** tiene exportación por línea de comandos. No inventes una.

### 5.2 Otras herramientas de diagramas (solo si no se pidió una concreta)

- **Graphviz** (`winget search Graphviz`): `dot -Tpng diagrama.dot -o diagrama.png`.
- **Mermaid CLI**: `npm install -g @mermaid-js/mermaid-cli`, luego `mmdc -i diagrama.mmd -o diagrama.png`.

### 5.3 PDF → imagen

- **PyMuPDF**: `pip install pymupdf`, luego `pymupdf.open(p)[0].get_pixmap(dpi=150).save(...)`.
- **pypdfium2**: `pip install pypdfium2`, luego `pdfium.PdfDocument(p)[0].render(scale=2).to_pil().save(...)`.

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

## ARM64 (Windows on ARM)

Probado el 16/11/2026 en Windows 11 Home ARM64 (26200), con Windows en español. ✅ = verificado en ese PC,
⚠️ = sin verificar.

| Herramienta | Estado en ARM64 | Cómo |
|---|---|---|
| **yEd 3.25.1** | ✅ funciona **con Java ARM64** | `yEd.exe` usa su `jre\` **x64** emulado, y por eso se cerraba (`RADAR_PRE_LEAK_64`). Hay que lanzar `yed.jar` con un JDK **ARM64 nativo**: `"<jdk-arm64>\bin\java.exe" -jar C:\Users\<usuario>\yEd\yed.jar [archivo.graphml]`. Probado con Microsoft OpenJDK 21.0.13 aarch64: abrió la ventana "yEd" y siguió estable. JDK: `winget search Microsoft.OpenJDK` (instalador, pide UAC) o el zip portátil sin instalación `https://aka.ms/download-jdk/microsoft-jdk-21-windows-aarch64.zip` en `C:\Users\<usuario>\tools\`. Conviene un acceso directo "yEd (ARM64)" con ese comando. |
| **SQL Server 2025 + SSMS 22** | ✅ funciona (x64 emulado) | El servicio `MSSQLSERVER` corre emulado y responde. `sqlcmd -S localhost -E -C -Q "SELECT @@VERSION"` devolvió `SQL Server 2025 (RTM) 17.0.1000.7 (X64)`. **Descarga el instalador en el idioma de Windows** (es-ES): el mismatch de idioma hace fallar el instalador. Hay drivers ODBC 18 **ARM64** nativos. |
| **PyMuPDF** | ✅ funciona | `pip install pymupdf` instala la 1.28.2 con binario ARM64 (ya no hace falta compilarla). Renderizó el sílabo a PNG. |
| **pypdfium2** | ✅ funciona | 5.15.2, binario ARM64. Renderizó el sílabo a PNG. |
| **Pillow** | ✅ se instala | 13.0.0, binario ARM64. |
| **Mermaid CLI** | ✅ funciona con Edge | No descargues Chrome (es x64). Usa Edge, que es ARM64 nativo: `PUPPETEER_SKIP_DOWNLOAD=1 npm i @mermaid-js/mermaid-cli`, más un `pptr.json` con `{"executablePath": "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"}` y `mmdc -p pptr.json -i x.mmd -o x.png`. Generó un DER con pata de gallo. **Solo si no se pidió yEd.** |
| **Graphviz** | ⚠️ solo hay x64 | winget solo ofrece `Graphviz.Graphviz` win64 ("No applicable installer" para arm64). Debería correr emulado. |
| **Windows-MCP** | ⚠️ sin verificar | Necesita Python 3.14 (uv lo baja para ARM64: `uv python install 3.14`). En la prueba, el sistema de permisos del agente bloqueó ejecutarlo, porque da control total del escritorio. Lo instala el estudiante con el comando del paso 2 y luego se verifica con `claude mcp list`. |
| **uv** | ✅ se instala | `pip install uv` (0.13.8) con binario ARM64. |
| **Java Access Bridge con yEd** | ⚠️ sin verificar | `jabswitch -enable` del JDK ARM64. |

**Instalación permanente de yEd en ARM64 (hecha y probada en el PC del estudiante, sin permisos de administrador):**
```powershell
# 1. JDK ARM64 portátil en una carpeta del usuario
curl.exe -L -o $env:TEMP\jdk.zip https://aka.ms/download-jdk/microsoft-jdk-21-windows-aarch64.zip
Expand-Archive $env:TEMP\jdk.zip $env:TEMP\jdk; Move-Item (Get-ChildItem $env:TEMP\jdk -Directory)[0].FullName "$HOME\tools\jdk-21-arm64"
# 2. Accesos directos "yEd (ARM64)" en el menú Inicio y el Escritorio
$sh = New-Object -ComObject WScript.Shell
foreach ($t in "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\yEd (ARM64).lnk", "$([Environment]::GetFolderPath('Desktop'))\yEd (ARM64).lnk") {
  $l = $sh.CreateShortcut($t); $l.TargetPath = "$HOME\tools\jdk-21-arm64bin\javaw.exe"
  $l.Arguments = "-jar `"$HOME\yEd\yed.jar`""; $l.WorkingDirectory = "$HOME\yEd"; $l.IconLocation = "$HOME\yEd\yEd.exe,0"; $l.Save() }
```
Para abrir un archivo desde el agente: `& "$HOME\tools\jdk-21-arm64bin\javaw.exe" -jar "$HOME\yEd\yed.jar" archivo.graphml`.
El acceso directo original de yEd (con el Java x64) sigue existiendo: no lo uses en ARM64.

Reglas en ARM64:
- Antes de instalar algo, mira si existe la versión ARM64: `winget show --id <ID> --architecture arm64`. Si dice
  "No applicable installer", solo hay x64 y correrá emulado.
- En apps Java, el problema suele ser **el JRE x64 incluido**, no la app: prueba el `.jar` con un JDK ARM64.
- Para automatizar el navegador, Edge es ARM64 nativo. El Chrome que descargan Puppeteer o Playwright es x64.
