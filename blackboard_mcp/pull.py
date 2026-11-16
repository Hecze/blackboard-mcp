"""Download *everything* a course offers, keeping Blackboard's folder structure:
every file in every folder, files inside Ultra assessments (rubrics, statements), files and class scripts the
teacher posted in announcements, and documents behind SharePoint/OneDrive links (syllabus, manuals), which
need the student's Microsoft sign-in (taken from the Blackboard browser profile).

Result: <download_dir>/<course>/Todo/<folder>/<file>, announcements under Todo/ANUNCIOS, and an index
(Todo/manifest.json) with every item's folder trail, type, text, links and local files.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .bb import Blackboard, Course, body_links, handler_id, html_to_text
from .config import Settings
from .sync import safe

SHAREPOINT = re.compile(r"https://[a-z0-9-]+\.sharepoint\.com/", re.I)


def course_root(settings: Settings, course: Course) -> Path:
    return settings.download_dir / safe(course.short_name(), 60) / "Todo"


def pull_course(settings: Settings, bb: Blackboard, course: Course, progress=lambda m: None) -> dict:
    root = course_root(settings, course)
    root.mkdir(parents=True, exist_ok=True)
    manifest, downloaded, existing, errors, sharepoint = [], 0, 0, [], []

    def fetch(url: str, dest: Path) -> str:
        nonlocal downloaded, existing
        if dest.exists():
            existing += 1
            return str(dest)
        try:
            bb.download(url, dest)
            downloaded += 1
            return str(dest)
        except Exception as e:  # noqa: BLE001 - recorded in the report
            errors.append(f"{dest.name}: {e}")
            return f"ERROR {dest.name}: {e}"

    for trail, item in bb.walk(course.id):
        folder = root.joinpath(*[safe(t, 60) for t in trail])
        kind = handler_id(item)
        ext_url = (item.get("contentHandler") or {}).get("url")
        entry = {"trail": list(trail), "id": item["id"], "title": item.get("title"), "type": kind,
                 "text": html_to_text(item.get("body") or item.get("description"))[:3000],
                 "links": [ln["url"] for ln in body_links(item.get("body"), settings.base_url) if not ln["blackboard_file"]]
                 + ([ext_url] if ext_url else []),
                 "files": []}
        progress(" / ".join(trail + (item.get("title") or "",)))
        for f in bb.item_files(course.id, item):
            entry["files"].append(fetch(f["url"], folder / safe(f["name"], 120)))
        if ext_url and SHAREPOINT.match(ext_url):
            sharepoint.append((entry, ext_url, folder / safe(item.get("title") or "documento", 100)))
        manifest.append(entry)

    # Announcements: teachers post class scripts (LAB 5-11…) and diagrams there, not in the content area.
    ann_dir = root / "ANUNCIOS"
    for a in sorted(bb.announcements(course.id), key=lambda a: a.get("created") or ""):
        day = (a.get("created") or "")[:10]
        text = html_to_text(a.get("body"))
        files = [ln for ln in body_links(a.get("body"), settings.base_url) if ln["blackboard_file"]]
        entry = {"trail": ["ANUNCIOS"], "id": a.get("id"), "title": a.get("title"), "type": "announcement",
                 "date": day, "text": text[:3000],
                 "links": [ln["url"] for ln in body_links(a.get("body"), settings.base_url) if not ln["blackboard_file"]],
                 "files": []}
        if text.strip():
            p = ann_dir / safe(f"{day} {a.get('title') or 'anuncio'}.txt", 120)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            entry["files"].append(str(p))
        for ln in files:
            entry["files"].append(fetch(ln["url"], ann_dir / safe(f"{day} {ln['text']}", 120)))
        manifest.append(entry)

    if sharepoint:
        progress("Documentos de SharePoint (sílabo, manuales)…")
        for entry, path in zip((s[0] for s in sharepoint), download_sharepoint(settings, [(u, d) for _, u, d in sharepoint])):
            entry["files"].append(path)
            if path.startswith("ERROR"):
                errors.append(path)
            elif path:
                downloaded += 1

    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"course": course.short_name(), "folder": str(root), "manifest": str(root / "manifest.json"),
            "items": len(manifest), "downloaded": downloaded, "already_had": existing,
            "errors": list(dict.fromkeys(errors))[:20]}


def download_sharepoint(settings: Settings, links: list[tuple[str, Path]]) -> list[str]:
    """Download SharePoint/OneDrive share links (…?download=1) with the signed-in browser profile."""
    from playwright.sync_api import sync_playwright

    from .auth import _launch
    out = []
    with sync_playwright() as pw:
        ctx = _launch(pw, settings, True)
        try:
            for url, dest in links:
                done = [p for p in dest.parent.glob(dest.name + ".*")] if dest.parent.exists() else []
                if done:
                    out.append(str(done[0]))
                    continue
                try:
                    r = ctx.request.get(url + ("&" if "?" in url else "?") + "download=1", timeout=180000)
                    ctype = r.headers.get("content-type", "")
                    if not r.ok or "html" in ctype:
                        out.append(f"ERROR {dest.name}: SharePoint {r.status}")
                        continue
                    ext = {"pdf": ".pdf", "word": ".docx", "sheet": ".xlsx", "presentation": ".pptx"}
                    suffix = next((v for k, v in ext.items() if k in ctype), ".bin")
                    target = dest.with_name(dest.name + suffix)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(r.body())
                    out.append(str(target))
                except Exception as e:  # noqa: BLE001
                    out.append(f"ERROR {dest.name}: {e}")
        finally:
            ctx.close()
    return out
