---
name: preparar-entorno-escritorio
description: >-
  Deja listo un PC Windows (x86_64 o ARM64) para que un agente trabaje con las aplicaciones de escritorio de los cursos (SQL Server + SSMS, yEd, Word/.docx, diagramas, PDF) usando los scripts de este repo y herramientas que ya existen (MCP de automatización de Windows por árbol de accesibilidad, MCP de Word, render de PDF) en vez de automatización hecha a mano (SendKeys, clics por coordenadas, brokers de administrador). Úsala antes de cualquier tarea que necesite programas de escritorio o editar documentos.
---

# preparar-entorno-escritorio

Cómo **obtener, instalar y comprobar** lo que un agente necesita para trabajar con programas de escritorio en
Windows 10/11, **x86_64 y ARM64**. Sirve para cualquier agente o harness: todo lo que aquí se pide son
comandos de PowerShell o Python y servidores MCP estándar (stdio).

Nace de un intento real en el que el agente lo armó todo a mano: SendKeys que acabaron escribiendo en otra
ventana, clics por coordenadas fallidos, capturas con offset, un broker de administrador hecho en casa e
instaladores sin progreso. Casi todo eso ya existe hecho y mejor.

Habla con el estudiante en español. **Instalar software y conceder permisos siempre lo confirma él.**

Scripts del repo (rutas relativas a la raíz; se ejecutan con
`powershell -ExecutionPolicy Bypass -File <script>`):

| Script | Qué hace | ¿Admin? |
|---|---|---|
| `scripts\env\probe.ps1 [-Json]` | Describe el PC: arquitectura **real** del CPU y la del proceso (si difieren, la shell corre emulada), idioma de Windows, runtimes y programas del curso ya instalados | No |
| `scripts\env\doctor.ps1` | Revisa todo lo que usa el repo (Blackboard, SQL Server, yEd, PDF, Windows-MCP) y da el comando que arregla cada falta. Sale con 1 si falta algo obligatorio | No |
| `scripts\env\install-sqlserver.ps1 [-Version 2025] [-Edition Developer] [-Locale en-US]` | SQL Server con winget | **Sí** (lo ejecuta el estudiante) |
| `scripts\env\install-ssms.ps1 [-Version 22]` | SSMS con winget | Lo que pida el instalador |
| `scripts\env\sql-login.ps1 -Status / -Grant [-Role dbcreator] / -Revoke` | Permite a tu usuario de Windows usar SQL Server **sin elevación** (`sqlcmd`, `pyodbc`), o lo deshace | `-Grant` y `-Revoke`: sí |
| `scripts\env\install-yed-arm64.ps1` | yEd en ARM64: JDK ARM64 portátil + accesos directos "yEd (ARM64)" | No |
| `python scripts\pdf2png.py archivo.pdf [salida] [--dpi 150] [--pages 1,3-5]` | Páginas de PDF a PNG (PyMuPDF, o pypdfium2 si no está) | No |

---

## 0. Reglas

**Seguridad**
- **El agente nunca obtiene permisos de administrador permanentes.** Nada de "PowerShell elevado que ejecuta lo
  que aparezca en una carpeta": cualquier programa que escriba ahí se ejecuta como administrador. Lo que pida
  UAC lo **ejecuta el estudiante** (el agente le da el comando exacto, en general uno de los scripts de arriba).
- Para usar SQL Server sin elevación, usa `sql-login.ps1 -Grant` (una vez, como administrador). Es un privilegio
  que **queda en la máquina**: anótalo, prefiere `-Role dbcreator` si alcanza, y usa `-Revoke` cuando ya no haga falta.
- **Una sesión de Windows dedicada al agente** (otro usuario local o una VM), no el escritorio donde trabaja el
  estudiante. Así el teclado y los clics nunca caen en su ventana.
- Los MCP de escritorio tienen **acceso total al sistema**: restringe sus herramientas y desactiva la telemetría
  (paso 2).
- En Blackboard la IA **nunca envía, guarda ni crea intentos** (ver `obtener-contexto-evaluacion`) y respeta las
  reglas del profesor sobre el uso de IA en cada evaluación.

**Fidelidad a la herramienta pedida**
- **Si el usuario o el curso piden una herramienta concreta (yEd, SSMS, Word…), se usa esa herramienta.** No se
  sustituye por algo parecido (Mermaid o Graphviz en lugar de yEd, LibreOffice en lugar de Word, un script en
  lugar de SSMS), aunque sea más fácil de automatizar.
- Esta guía documenta **todas las formas conocidas** de hacer funcionar y automatizar cada herramienta. Si
  ninguna funciona, se dice qué falla y se pregunta. No se cambia de herramienta por iniciativa propia.
- Las herramientas "sin interfaz" (paso 5.2) son para cuando **no** se pidió una herramienta concreta.

## 1. Sondeo y diagnóstico (siempre lo primero)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\env\probe.ps1 -Json
powershell -ExecutionPolicy Bypass -File scripts\env\doctor.ps1
```
- Fíjate en `arch` (la máquina) y `process_arch` (la shell). En un PC ARM64 una shell x64 emulada informa
  `PROCESSOR_ARCHITECTURE=AMD64`, así que no uses esa variable para decidir.
- `ui_culture` es el idioma de Windows, y afecta al instalador de SQL Server (paso 3).
- No instales ni descargues lo que `installed` ya muestra.
- `doctor` dice qué falta y con qué comando se arregla. Vuelve a ejecutarlo al final para confirmar.

## 2. Automatización del escritorio: Windows-MCP

**[CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)** (MIT, PyPI `windows-mcp`) lee el
**árbol de accesibilidad (UI Automation)** de las ventanas, incluidas las de fondo, y busca controles por nombre.
Herramientas: Click, Type, Scroll, Shortcut, Wait/WaitFor, Screenshot, Snapshot, App, Process, Clipboard,
FileSystem, PowerShell, Registry…

Requisitos: **Python 3.14+** y **uv**. `doctor` lo comprueba; si falta, `pip install uv` y luego
`uv python install 3.14`.

Es un servidor MCP **stdio** estándar:
- comando `uvx`;
- argumentos `windows-mcp serve`, más restricciones, por ejemplo `--exclude-tools PowerShell,Registry`;
- variable de entorno `ANONYMIZED_TELEMETRY=false`.

Cómo registrarlo en Claude Code o Desktop, Cursor, VS Code, OpenCode o Codex: **[reference/clientes-mcp.md](reference/clientes-mcp.md)**.

Cómo usarlo bien:
- **Primero `Snapshot`** (el árbol de la ventana) y después **clic por nombre**. Las coordenadas solo como último
  recurso.
- Usa **`WaitFor`** en lugar de esperas fijas.
- Las apps **Java/Swing (como yEd)** casi no exponen UI Automation: ver el paso 5.1.

Alternativas (sin verificar a fondo):
- [felenko/WindowsOSMCP](https://github.com/felenko/WindowsOSMCP): `click_element` por nombre o ID;
- [locomorange/uiautomation-mcp](https://github.com/locomorange/uiautomation-mcp): .NET;
- FlaUI-MCP (.NET 8);
- servidores basados en **pywinauto**: actúan sin mover el cursor ni robar el foco.

Si tu harness trae su propio control del escritorio (computer use) o un navegador, puedes usarlo. Para páginas
web, mejor un navegador automatizado que el escritorio.

## 3. Programas del curso: SQL Server y SSMS

- **SQL Server** (el estudiante ejecuta, como administrador):
  `scripts\env\install-sqlserver.ps1 -Version 2025 -Edition Developer`
  - IDs de winget verificados: `Microsoft.SQLServer.2025.Developer`, `.2025.Express`, `.2022.Developer`,
    `.2022.Express`.
  - **Idioma del medio**: con Windows en **es-ES**, el medio es-ES falló con un diálogo de "mismatch de idioma" y
    el **inglés (ENU) funcionó**. El script usa `--locale en-US` por defecto. Si aparece ese diálogo, ve directo
    al medio ENU; no reintentes con el del idioma de Windows.
  - El profesor del curso usa SQL Server 2022 Developer. 2025 también sirve para los ejercicios.
- **SSMS**: `scripts\env\install-ssms.ps1` (`Microsoft.SQLServerManagementStudio.22`). Si dice "no se puede
  ejecutar si la instalación está en curso", hay un `setup.exe` colgado: el estudiante lo cierra desde el
  Administrador de tareas.
- **Usar SQL Server sin elevación**: `scripts\env\sql-login.ps1 -Grant` (una vez, como administrador) y luego
  `-Status`. Así el agente puede usar `sqlcmd -S localhost -E -C -Q "..."` o `pyodbc` con su usuario de Windows.
- **T-SQL sin interfaz**: `sqlcmd` o Python con `pyodbc` (driver "ODBC Driver 18 for SQL Server"). SSMS solo
  cuando hace falta la interfaz o una captura de SSMS.
- Para otros programas: busca el ID con `winget search "<nombre>"` (no lo adivines) e instala con
  `--log "$env:TEMP\winget-<ID>.log"`, en una terminal visible.

## 4. Documentos Word (.docx)

Si se pide Word o un `.docx`, se trabaja sobre el `.docx`. Qué MCP usar, cómo insertar sin romper el formato
y cómo previsualizarlo: **[reference/word.md](reference/word.md)**.

## 5. Diagramas y PDF

### 5.1 yEd (cuando se pide yEd; es lo que usa el curso de Base de Datos)

Instalación: `winget search yEd` o el instalador de yWorks. Queda en `C:\Users\<usuario>\yEd\` con `yEd.exe`,
`yed.jar` y un Java propio en `jre\`. **En ARM64**, ejecuta `scripts\env\install-yed-arm64.ps1` (ver ARM64).

Todas las formas de trabajar con yEd:
1. **Interfaz de yEd**: dibujar y luego *File → Export* a PNG, JPG o SVG.
2. **Generar o editar el `.graphml`** (XML) con código y **abrirlo en yEd**: `java -jar yed.jar archivo.graphml`,
   o `yEd.exe archivo.graphml` en x86_64. El `.graphml` también es lo que suele entregarse. Los del profesor
   (`Todo\ANUNCIOS\*.graphml`) sirven de plantilla para el estilo.
3. **Automatizar la interfaz** (Swing: UI Automation no ve sus controles):
   - **atajos de teclado** dirigidos a la ventana de yEd, con su título verificado (Windows-MCP
     `Shortcut`/`Type`);
   - **Java Access Bridge**: `jabswitch -enable` (viene con el JDK) expone Swing a las herramientas de
     accesibilidad. Bibliotecas Python: `pyjab`, `JABWrapper`. **Sin verificar con yEd.**
   - capturas (`Snapshot`/`Screenshot`) para comprobar cada paso.
4. yEd **no** tiene exportación por línea de comandos. No inventes una.

### 5.2 Otras herramientas de diagramas (solo si no se pidió una concreta)

- **Graphviz** (`winget search Graphviz`): `dot -Tpng diagrama.dot -o diagrama.png`.
- **Mermaid CLI**: `npm install -g @mermaid-js/mermaid-cli`, luego `mmdc -i diagrama.mmd -o diagrama.png`.

### 5.3 PDF → imagen

`python scripts\pdf2png.py archivo.pdf [carpeta] --dpi 150 --pages 1-3`. Necesita **`pymupdf==1.28.2`** o
`pypdfium2`. No instales `pymupdf` sin versión: en ARM64 pip elige la 2.x, que no tiene binario `win_arm64`, e
intenta compilarla y falla.

## 6. Capturas

- Con Windows-MCP: `Screenshot` o `Snapshot` de la ventana (sin `CopyFromScreen` con offsets ni `PrintWindow`).
- Recortar o redimensionar: `Pillow`.

## 7. Checklist final

- [ ] `probe.ps1` hecho (arquitectura real, idioma, lo ya instalado).
- [ ] `doctor.ps1` sin `FALTA`.
- [ ] Los MCP que se usen (Windows-MCP, Word) registrados y **conectados** en el cliente.
- [ ] Herramientas peligrosas excluidas y telemetría desactivada.
- [ ] Lo que pidió UAC lo ejecutó el estudiante. Privilegios que quedan (como el login de `sql-login.ps1`)
      anotados.
- [ ] Sesión de Windows dedicada al agente, y nada con permisos de administrador permanentes.

## ARM64

Si `probe.ps1` dice `"arch": "ARM64"`, lee **[reference/arm64.md](reference/arm64.md)**: qué funciona, qué corre emulado y
cómo (yEd con JDK ARM64, PyMuPDF `==1.28.2`, Mermaid con Edge, SQL Server x64 emulado).
