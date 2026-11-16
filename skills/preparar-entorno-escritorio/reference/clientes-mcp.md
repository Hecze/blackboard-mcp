# Registrar un servidor MCP stdio en cada cliente

Ejemplo: Windows-MCP (`uvx windows-mcp serve`). Para el servidor de Blackboard, igual con
`<repo>\.venv\Scripts\blackboard-mcp.exe serve` (ver `README.md`).

Regístralo en el cliente que uses. Ejemplos (sigue la documentación de tu cliente):
- **Claude Code**: `claude mcp add --transport stdio --scope user -e ANONYMIZED_TELEMETRY=false windows-mcp -- uvx windows-mcp serve --exclude-tools PowerShell,Registry`
- **Claude Desktop, Cursor y otros** con `mcpServers` en JSON:
  `{"mcpServers": {"windows-mcp": {"command": "uvx", "args": ["windows-mcp", "serve"], "env": {"ANONYMIZED_TELEMETRY": "false"}}}}`
- **OpenCode** (`opencode.json`):
  `{"mcp": {"windows-mcp": {"type": "local", "command": ["uvx", "windows-mcp", "serve"], "environment": {"ANONYMIZED_TELEMETRY": "false"}}}}`
- **Codex CLI** (`~/.codex/config.toml`):
  `[mcp_servers.windows-mcp]` con `command = "uvx"`, `args = ["windows-mcp", "serve"]` y
  `env = { ANONYMIZED_TELEMETRY = "false" }`.

Si el cliente no hereda el PATH (por ejemplo, la app de la Microsoft Store), usa la ruta absoluta de `uvx.exe`.
"Connection closed" suele significar justo eso.
