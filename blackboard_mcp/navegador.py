"""Un navegador de verdad, con la sesión del alumno, para resolver actividades dentro de Blackboard.

El navegador de la app (y cualquier navegador "limpio") no sirve: Blackboard se entra por SSO de Outlook y ahí no hay
sesión. Este módulo abre Chromium con las cookies ya guardadas (`~/.blackboard-mcp/cookies.json`, las mismas que usa el
resto del servidor), así que entra directo, y le da al agente lo justo para trabajar dentro de un cuestionario:

    abrir(url) → leer la página (texto + elementos numerados) → clic / rellenar / elegir / marcar → ver → ...

Regla dura: **nunca pulsa el botón de enviar**. `clic()` se niega con los botones de envío; el último paso lo da el
alumno, que revisa antes. El navegador vive en su propio hilo (la API sincrónica de Playwright no se puede usar desde
varios hilos) y se reutiliza entre llamadas, de modo que la página se queda donde el agente la dejó.
"""
from __future__ import annotations

import queue
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .auth import DESKTOP_UA, LoginRequired, save_cookies
from .config import Settings

# Botones que envían la actividad. El agente no los toca: los pulsa el alumno cuando ya revisó todo.
ENVIAR = re.compile(r"^\s*(enviar|enviar intento|enviar actividad|entregar|entregar actividad|submit|submit attempt|"
                    r"guardar y enviar|guardar y entregar|finalizar|finalizar intento|terminar intento)\s*$", re.I)
NO_ENVIA = ("Bloqueado: ese botón ENVÍA la actividad y eso lo pulsas tú. Deja el formulario completo y avísale: "
            "«revisa y pulsa Enviar».")

# Elementos con los que se puede interactuar, con su texto (la etiqueta del radio, el valor del campo…).
_SNAP = r"""
([prefijo]) => {
  const visible = (el) => {
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  document.querySelectorAll('[data-bbt]').forEach((e) => e.removeAttribute('data-bbt'));
  const items = []; const seen = new Set();
  const nodos = document.querySelectorAll(
    "a[href], button, input, select, textarea, [role='button'], [role='radio'], [role='checkbox'], " +
    "[role='tab'], [role='link'], [role='menuitem'], [contenteditable='true']");
  nodos.forEach((el) => {
    if (!visible(el)) return;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (tag === 'input' && type === 'hidden') return;
    let texto = (el.innerText || el.value || '').trim().replace(/\s+/g, ' ');
    if (!texto && el.labels && el.labels.length) texto = (el.labels[0].innerText || '').trim().replace(/\s+/g, ' ');
    if (!texto) texto = (el.getAttribute('aria-label') || el.getAttribute('title') ||
                         el.getAttribute('placeholder') || el.getAttribute('name') || '').trim().replace(/\s+/g, ' ');
    const r = el.getBoundingClientRect();
    const clave = [tag, type, texto, Math.round(r.top), Math.round(r.left)].join('|');
    if (seen.has(clave)) return;
    seen.add(clave);
    const i = items.length;
    el.setAttribute('data-bbt', String(i));
    const o = { ref: prefijo + i, tipo: type ? tag + ':' + type : tag, texto: texto.slice(0, 160) };
    if ((type === 'radio' || type === 'checkbox') || tag === 'option') o.marcado = !!el.checked;
    if (tag === 'select') {
      o.opciones = Array.from(el.options).slice(0, 15).map((op) => op.text.trim().slice(0, 80));
      o.valor = el.selectedIndex >= 0 ? el.options[el.selectedIndex].text.trim() : '';
    }
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') o.deshabilitado = true;
    if (el.getAttribute('contenteditable') === 'true') o.editable = true;
    items.push(o);
  });
  const cuerpo = document.body ? document.body.innerText : '';
  return { items: items, texto: cuerpo.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim() };
}
"""


class Navegador:
    """Chromium con la sesión del alumno, en un hilo propio, reutilizado entre llamadas."""

    def __init__(self, settings: Settings):
        self.s = settings
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._arranque = threading.Lock()
        self._browser = None
        self._ctx = None
        self._page = None
        self._visible = True

    # --- hilo dueño de Playwright -------------------------------------------------------------------------------
    def _worker(self) -> None:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            while True:
                job = self._q.get()
                if job is None:
                    break
                fn, caja = job
                try:
                    caja["r"] = fn(pw)
                except BaseException as e:      # se re-lanza en el hilo que llamó
                    caja["e"] = e
                finally:
                    caja["d"].set()

    def _do(self, fn, timeout: float = 180):
        with self._arranque:
            if not self._thread or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._worker, daemon=True, name="bb-navegador")
                self._thread.start()
        caja: dict = {"d": threading.Event()}
        self._q.put((fn, caja))
        if not caja["d"].wait(timeout):
            raise TimeoutError("El navegador no respondió; ciérralo con bb_cerrar_navegador y vuelve a abrir.")
        if "e" in caja:
            raise caja["e"]
        return caja.get("r")

    # --- navegador -----------------------------------------------------------------------------------------------
    def _slots(self, pw, visible: bool):
        if self._page is not None and not self._page.is_closed():
            return self._page
        kwargs = {"viewport": {"width": 1280, "height": 900}}
        if not visible:
            kwargs["user_agent"] = DESKTOP_UA
        state = str(self.s.cookies_path) if self.s.cookies_path.exists() else None
        opciones = {"headless": not visible}
        self._browser = None
        if self.s.browser_channel:                 # el mismo Chrome que usa el inicio de sesión (config.json)
            try:
                self._browser = pw.chromium.launch(channel=self.s.browser_channel, **opciones)
            except Exception:
                self._browser = None
        if self._browser is None:
            self._browser = pw.chromium.launch(**opciones)
        self._ctx = self._browser.new_context(storage_state=state, **kwargs)
        self._page = self._ctx.new_page()
        self._visible = visible
        return self._page

    def _guardar_cookies(self) -> None:
        try:
            if self._ctx is not None:
                save_cookies(self.s, self._ctx.cookies())
        except Exception:
            pass

    def _host(self) -> str:
        return urlparse(self.s.base_url).hostname or ""

    def _login_required(self, url: str) -> bool:
        host = self._host()
        return bool(host) and not (host in (url or "") and "/ultra" in (url or ""))

    # --- acciones ------------------------------------------------------------------------------------------------
    def _snapshot(self, page) -> dict:
        textos, elementos = [], []
        frames = page.frames
        for i, f in enumerate(frames):
            prefijo = "" if i == 0 else f"{i}:"
            try:
                data = f.evaluate(_SNAP, [prefijo])
            except Exception:
                continue
            if data.get("texto"):
                textos.append(data["texto"])
            elementos.extend(data.get("items") or [])
        texto = "\n\n".join(textos)
        out = {"url": page.url, "titulo": (page.title() or "")[:160],
               "texto": texto[:8000], "elementos": elementos}
        if self._login_required(page.url):
            out["login_required"] = True
            out["critical"] = True
            out["message"] = ("CRITICAL - La sesión de Blackboard caducó: el navegador usa la sesión guardada del "
                              "alumno y aun así cayó en el portal de acceso. Dile que ejecute `blackboard-mcp login` "
                              "(SSO de Outlook + MFA) y no intentes entrar con contraseña.")
        return out

    def abrir(self, url: str, visible: bool = True) -> dict:
        def go(pw):
            page = self._slots(pw, visible)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            self._guardar_cookies()
            return self._snapshot(page)
        return self._do(go)

    def ver(self) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            return self._snapshot(page)
        return self._do(go)

    def _localizar(self, ref: str):
        """'3' o '1:3' → (frame, selector CSS del elemento)."""
        frame_idx, _, local = ref.partition(":")
        if local == "":
            local, frame_idx = frame_idx, "0"
        frame = self._page.frames[int(frame_idx)]
        return frame, f'[data-bbt="{local}"]'

    def _texto_de(self, frame, selector: str) -> str:
        try:
            return frame.eval_on_selector(selector, """el => ((el.innerText || el.value ||
                (el.labels && el.labels[0] ? el.labels[0].innerText : '') || el.getAttribute('aria-label') ||
                el.getAttribute('title') || '')).trim().replace(/\\s+/g, ' ')""")
        except Exception:
            return ""

    def clic(self, ref: str) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            frame, sel = self._localizar(ref)
            texto = self._texto_de(frame, sel)
            if ENVIAR.match(texto or ""):
                return {"bloqueado": True, "boton": texto, "message": NO_ENVIA}
            frame.click(sel, timeout=20000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                page.wait_for_timeout(800)
            self._guardar_cookies()
            return self._snapshot(page)
        return self._do(go)

    def rellenar(self, ref: str, texto: str) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            frame, sel = self._localizar(ref)
            frame.fill(sel, texto, timeout=20000)
            self._guardar_cookies()
            return self._snapshot(page)
        return self._do(go)

    def elegir(self, ref: str, opcion: str) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            frame, sel = self._localizar(ref)
            try:
                frame.select_option(sel, label=opcion, timeout=10000)
            except Exception:
                frame.select_option(sel, value=opcion, timeout=10000)
            return self._snapshot(page)
        return self._do(go)

    def marcar(self, ref: str, marcado: bool = True) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            frame, sel = self._localizar(ref)
            frame.set_checked(sel, marcado, timeout=20000)
            return self._snapshot(page)
        return self._do(go)

    def tecla(self, tecla: str) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            page.keyboard.press(tecla)
            page.wait_for_timeout(600)
            return self._snapshot(page)
        return self._do(go)

    def atras(self) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            page.go_back(wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            return self._snapshot(page)
        return self._do(go)

    def captura(self) -> dict:
        def go(pw):
            page = self._slots(pw, self._visible)
            carpeta = self.s.home / "capturas"
            carpeta.mkdir(parents=True, exist_ok=True)
            destino = carpeta / f"{datetime.now():%Y%m%d-%H%M%S}.png"
            page.screenshot(path=str(destino), full_page=False)
            return {"captura": str(destino), "url": page.url}
        return self._do(go)

    def cerrar(self) -> dict:
        def go(pw):
            self._guardar_cookies()
            try:
                if self._ctx is not None:
                    self._ctx.close()
                if self._browser is not None:
                    self._browser.close()
            finally:
                self._browser = self._ctx = self._page = None
            return {"ok": True, "cerrado": True}
        return self._do(go)
