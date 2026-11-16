"""Render PDF pages to PNG. Uses PyMuPDF, falls back to pypdfium2 (both have native Windows ARM64 wheels:
pin pymupdf==1.28.2 — 2.x has no win_arm64 wheel and pip tries to compile it).

  python scripts/pdf2png.py file.pdf [out_dir] [--dpi 150] [--pages 1,3-5]
Prints the PNG paths, one per line.
"""
import argparse
import sys
from pathlib import Path


def page_list(spec: str | None, count: int) -> list[int]:
    if not spec:
        return list(range(count))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += range(int(a) - 1, int(b or a))
    return [p for p in out if 0 <= p < count]


def render(pdf: Path, out: Path, dpi: int, pages: str | None) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    done = []
    try:
        import pymupdf
        doc = pymupdf.open(pdf)
        for i in page_list(pages, doc.page_count):
            dest = out / f"{pdf.stem}-p{i + 1:03d}.png"
            doc[i].get_pixmap(dpi=dpi).save(dest)
            done.append(dest)
        return done
    except ImportError:
        pass
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    for i in page_list(pages, len(doc)):
        dest = out / f"{pdf.stem}-p{i + 1:03d}.png"
        doc[i].render(scale=dpi / 72).to_pil().save(dest)
        done.append(dest)
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("out", type=Path, nargs="?")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--pages")
    a = ap.parse_args()
    try:
        for p in render(a.pdf, a.out or a.pdf.with_suffix(""), a.dpi, a.pages):
            print(p)
    except ImportError:
        sys.exit('Install one of: pip install "pymupdf==1.28.2"  |  pip install pypdfium2')
