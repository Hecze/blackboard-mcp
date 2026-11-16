# ARM64 (Windows on ARM) — notas verificadas

Probado el 16/11/2026 en Windows 11 Home ARM64 (26200), con Windows en español. ✅ = verificado en ese PC,
⚠️ = sin verificar.

| Herramienta | Estado | Cómo |
|---|---|---|
| **yEd 3.25.1** | ✅ con Java ARM64 | `yEd.exe` usa su `jre\` **x64** emulado y se cerraba (`RADAR_PRE_LEAK_64`). `scripts\env\install-yed-arm64.ps1` instala Microsoft OpenJDK 21 ARM64 (zip portátil, sin admin) en `~\tools\jdk-21-arm64` y crea accesos directos **"yEd (ARM64)"** que ejecutan `javaw -jar yed.jar`. Probado: la ventana se abre y queda estable. No uses el acceso directo original. |
| **SQL Server 2025 + SSMS 22** | ✅ x64 emulado | El servicio corre emulado y responde a `sqlcmd`. Instalador: medio **en-US** (ver paso 3). Hay drivers ODBC 18 **ARM64** nativos. |
| **PyMuPDF** | ✅ solo `==1.28.2` | `pip install "pymupdf==1.28.2"` (binario `cp310-abi3-win_arm64`). Sin versión, pip toma la 2.1 y falla al compilar. |
| **pypdfium2** | ✅ | 5.15.2, binario ARM64. |
| **Pillow, uv** | ✅ | Binarios ARM64 (`pip install pillow uv`). |
| **Mermaid CLI** | ✅ con Edge | El Chrome que baja Puppeteer es x64; usa Edge (ARM64 nativo): `PUPPETEER_SKIP_DOWNLOAD=1 npm i @mermaid-js/mermaid-cli` y `mmdc -p pptr.json …` con `{"executablePath": "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"}`. **Solo si no se pidió yEd.** |
| **Graphviz** | ⚠️ solo x64 | winget no tiene instalador arm64 de `Graphviz.Graphviz`; debería correr emulado. |
| **Windows-MCP** | ⚠️ sin verificar | Necesita Python 3.14 (`uv python install 3.14` baja la versión ARM64). Pendiente probarlo en ARM64. |
| **Java Access Bridge con yEd** | ⚠️ sin verificar | `jabswitch -enable` del JDK ARM64. |

Reglas en ARM64:
- Antes de instalar algo, comprueba si hay versión ARM64: `winget show --id <ID> --architecture arm64`. "No
  applicable installer" significa que solo hay x64, que correrá emulado.
- En apps Java, el problema suele ser **el JRE x64 incluido**, no la app: ejecuta el `.jar` con un JDK ARM64.
- Para automatizar el navegador, Edge es ARM64 nativo; el Chrome de Puppeteer o Playwright es x64.
- Paquetes de Python: si pip intenta compilar, busca la última versión con binario `win_arm64`
  (`pip download <pkg>==<versión> --only-binary=:all:`) y fíjala.
