# Documentos Word (.docx)

Si se pide Word o un `.docx`, se trabaja sobre el `.docx`. MCP de terceros, por orden de preferencia (revisa el
estado de cada repositorio antes de usarlo):
- **[docx-mcp](https://mcpservers.org/fr/servers/securityronin/docx-mcp)**: comando `uvx docx-mcp-server`.
  Control de cambios, comentarios, notas al pie, `insert_image`.
- **[MeterLong/MCP-Doc](https://playbooks.com/mcp/meterlong/mcp-doc)**: tablas (crear, combinar, editar celdas) e
  imágenes con tamaño.
- **[GongRzhe/Office-Word-MCP-Server](https://github.com/GongRzhe/Office-Word-MCP-Server)**: el más completo
  (`add_table`, `add_picture`, `convert_to_pdf`, insertar cerca de un texto…), pero **archivado desde marzo de
  2026**. Comando: `uvx --from office-word-mcp-server word_mcp_server`.
- Sin MCP: `python-docx`. Inserta **relativo a un texto ancla**, nunca por índice de párrafo.

**Vista previa visual** (comprobar que no se rompió el formato): Word → PDF (`convert_to_pdf` o Word por COM) y
después `python scripts\pdf2png.py archivo.pdf`. La alternativa comercial es Aspose.Words MCP (licencia).
