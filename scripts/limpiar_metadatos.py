"""Normaliza los metadatos de un .docx o .pdf para que queden a nombre del alumno.

Uso:
    python scripts/limpiar_metadatos.py archivo.docx --autor "Nombre Apellido" --titulo "T1 - MCUN"
    python scripts/limpiar_metadatos.py archivo.pdf  --autor "Nombre Apellido" --titulo "T1 - MCUN"

- .docx: reescribe docProps/core.xml (creator, lastModifiedBy, title) y docProps/app.xml (Company, TotalTime)
  sin tocar el contenido. No necesita Word.
- .pdf: reescribe /Title y /Author del Info y el XMP (requiere pypdf).

No inventa autoría: solo deja los metadatos coherentes con el alumno que entrega.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path


def limpiar_docx(path: Path, autor: str, titulo: str | None, empresa: str | None) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                txt = data.decode("utf-8")
                txt = re.sub(r"<dc:creator>.*?</dc:creator>", f"<dc:creator>{autor}</dc:creator>", txt, flags=re.S)
                txt = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>",
                             f"<cp:lastModifiedBy>{autor}</cp:lastModifiedBy>", txt, flags=re.S)
                if titulo:
                    if "<dc:title>" in txt:
                        txt = re.sub(r"<dc:title>.*?</dc:title>", f"<dc:title>{titulo}</dc:title>", txt, flags=re.S)
                    else:
                        txt = txt.replace("</cp:coreProperties>",
                                          f"<dc:title>{titulo}</dc:title></cp:coreProperties>")
                data = txt.encode("utf-8")
            elif item.filename == "docProps/app.xml":
                txt = data.decode("utf-8")
                if empresa:
                    txt = re.sub(r"<Company>.*?</Company>", f"<Company>{empresa}</Company>", txt, flags=re.S)
                txt = re.sub(r"<TotalTime>.*?</TotalTime>", "<TotalTime>0</TotalTime>", txt, flags=re.S)
                data = txt.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(str(tmp), str(path))
    print(f"docx actualizado: {path}")


def limpiar_pdf(path: Path, autor: str, titulo: str | None) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        sys.exit("Falta pypdf: pip install pypdf")

    r = PdfReader(str(path))
    w = PdfWriter()
    for pg in r.pages:
        w.add_page(pg)
    meta = dict(r.metadata or {})
    meta["/Author"] = autor
    if titulo:
        meta["/Title"] = titulo
    meta.pop("/Creator", None)      # deja solo el Producer de la app que genero el PDF
    w.add_metadata(meta)
    out = path.with_suffix(".tmp.pdf")
    with open(out, "wb") as f:
        w.write(f)
    shutil.move(str(out), str(path))
    print(f"pdf actualizado: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Normaliza autor/titulo de un .docx o .pdf")
    ap.add_argument("archivo")
    ap.add_argument("--autor", required=True, help="nombre del alumno")
    ap.add_argument("--titulo", default=None)
    ap.add_argument("--empresa", default=None, help="solo .docx (app.xml Company)")
    a = ap.parse_args()

    p = Path(a.archivo)
    if not p.exists():
        sys.exit(f"No existe: {p}")
    if p.suffix.lower() == ".docx":
        limpiar_docx(p, a.autor, a.titulo, a.empresa)
    elif p.suffix.lower() == ".pdf":
        limpiar_pdf(p, a.autor, a.titulo)
    else:
        sys.exit("Solo .docx o .pdf")


if __name__ == "__main__":
    main()
