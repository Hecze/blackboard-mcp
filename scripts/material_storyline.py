"""Extrae el texto de TODAS las diapositivas de la presentación Storyline de un tema."""
import json
import pathlib
import re
import sys
from urllib.parse import urlparse

from blackboard_mcp.bb import Blackboard
from blackboard_mcp.config import load_settings

bb = Blackboard(load_settings())
COURSE = "_1471425_1"
SALIDA = pathlib.Path(r"C:\Users\hecto\AppData\Local\Temp\opencode\prng")
SALIDA.mkdir(exist_ok=True)


def url_de(cid):
    d = bb.get("/learn/api/public/v1/courses/%s/contents/%s" % (COURSE, cid))
    return (d.get("contentHandler") or {}).get("url") or ""


def bajar_js(base_path, nombre):
    url = base_path + "/html5/data/js/" + nombre
    r = bb._request("GET", url, stream=True)
    return r.read().decode("utf-8", errors="ignore")


def textos(obj, salida):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and len(v.strip()) > 2 and k.lower() in (
                    "text", "title", "caption", "alttext", "value", "content", "name"):
                salida.append(v.strip())
            else:
                textos(v, salida)
    elif isinstance(obj, list):
        for v in obj:
            textos(v, salida)


def tema(n, cid):
    url = url_de(cid)
    u = urlparse(url)
    base = u.path.rsplit("/", 1)[0]
    frame = bajar_js_otro(base, "/story_content/frame.xml")
    if not frame:
        print("tema %d: sin frame" % n)
        return
    enlaces = re.findall(r'<slidelink slideid="([^"]+)"[^>]*displaytext="([^"]*)"', frame)
    print("tema %2d: %d diapositivas" % (n, len(enlaces)))
    partes = []
    for sid, titulo in enlaces:
        corto = sid.rsplit(".", 1)[1]
        try:
            js = bajar_js(base, corto + ".js")
        except Exception:
            continue
        m = js.find("('slide', '")
        fin = js.rfind("');")
        if m < 0 or fin < m:
            continue
        crudo = js[m + len("('slide', '"):fin]
        # el JSON de Storyline trae comillas sin escapar: se extraen los textos con regex
        trozos = []
        for mm in re.finditer(r'"(?:text|title|caption|altText|name)":"((?:[^"\\]|\\.)*)"', crudo):
            try:
                trozos.append(json.loads('"%s"' % mm.group(1)))
            except Exception:
                trozos.append(mm.group(1))
        vistos, limpios = set(), []
        for t in trozos:
            t = re.sub(r"<[^>]+>", " ", t)
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) > 3 and t not in vistos:
                vistos.add(t)
                limpios.append(t)
        if limpios:
            partes.append("\n### %s\n%s" % (titulo, "\n".join(limpios)))
    destino = SALIDA / ("clase%02d.txt" % n)
    destino.write_text("\n".join(partes), encoding="utf-8")
    print("   -> %s (%d chars)" % (destino.name, destino.stat().st_size))


def bajar_js_otro(base, ruta):
    try:
        return bb._request("GET", base + ruta, stream=True).read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


LINKS = {4: "_34625403_1", 7: "_34625452_1", 8: "_34625458_1", 9: "_34625464_1",
         10: "_34625470_1", 11: "_34625452_1", 12: "_34625458_1"}

objetivo = int(sys.argv[1]) if len(sys.argv) > 1 else 4
tema(objetivo, LINKS[objetivo])
