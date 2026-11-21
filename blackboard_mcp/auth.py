"""Signing in to Blackboard.

Most universities put Blackboard behind single sign-on with MFA, so there is
no password we can post from a script. Instead we open a real browser window
(your installed Chrome, with its own dedicated profile), you sign in once, and we
keep the resulting session cookies. The same browser profile remembers the SSO
"stay signed in" state, so later refreshes can usually happen invisibly.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import Settings

SESSION_COOKIES = ("BbRouter", "JSESSIONID", "AWSELB", "AWSELBCORS", "BbClientCalenderTimeZone")
# Some Blackboard landing pages don't redirect to single sign-on by themselves; one of these buttons starts it.
# (Bristol: "Staff and student login".) Clicking it lets the silent refresh work with no window.
SSO_BUTTONS = ("Staff and student login", "Student and staff login", "Student login", "Single sign-on",
               "Single Sign On", "Institutional login", "University login", "Sign in with", "Log in with SSO")
# Headless Chrome advertises "HeadlessChrome", which identity providers may treat differently.
DESKTOP_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/154.0.0.0 Safari/537.36")


class LoginRequired(RuntimeError):
    """Raised when there is no usable Blackboard session."""

    def __init__(self, msg: str = ""):
        super().__init__(
            msg
            or "Not signed in to Blackboard (or the session expired). "
            "Run the `bb_login` tool (or `blackboard-mcp login` in a terminal) "
            "and complete the university sign-in in the window that opens."
        )


def load_cookies(settings: Settings) -> dict[str, str]:
    p = settings.cookies_path
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}
    return {c["name"]: c["value"] for c in data.get("cookies", [])}


def save_cookies(settings: Settings, cookies: list[dict]) -> None:
    p = settings.cookies_path
    p.write_text(json.dumps({"saved": time.time(), "cookies": cookies}, indent=1))
    p.chmod(0o600)


def health_path(settings: Settings) -> Path:
    return settings.home / "session-health.json"


def write_health(settings: Settings, ok: bool, message: str = "") -> None:
    """Record whether the last sign-in / silent refresh worked, so the MCP server and the scheduled
    keep-alive can tell the student straight away when the session is lost."""
    try:
        health_path(settings).write_text(json.dumps(
            {"ok": ok, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "message": message}, indent=1))
    except OSError:
        pass


def read_health(settings: Settings) -> dict | None:
    try:
        return json.loads(health_path(settings).read_text())
    except (OSError, ValueError):
        return None


def _host(settings: Settings) -> str:
    from urllib.parse import urlparse
    return urlparse(settings.base_url).hostname or ""


def _launch(pw, settings: Settings, headless: bool):
    settings.profile_dir.mkdir(parents=True, exist_ok=True)
    kwargs = dict(user_data_dir=str(settings.profile_dir), headless=headless,
                  viewport={"width": 1100, "height": 800})
    if headless:
        kwargs["user_agent"] = DESKTOP_UA
    if settings.browser_channel:
        try:
            return pw.chromium.launch_persistent_context(channel=settings.browser_channel, **kwargs)
        except Exception:
            pass  # Chrome not installed -> fall back to Playwright's Chromium
    return pw.chromium.launch_persistent_context(**kwargs)


def blackboard_reachable(settings: Settings, timeout: float = 15) -> bool:
    """Can this machine reach the Blackboard server at all? Any HTTP answer counts; a connect error or timeout
    means a network problem (Wi-Fi not reaching AWS, Blackboard down), which is not a lost session."""
    import httpx
    try:
        httpx.get(settings.base_url + "/", timeout=timeout, follow_redirects=False)
        return True
    except httpx.TransportError:
        return False


def browser_login(settings: Settings, *, headless: bool = False, timeout_s: int = 300) -> dict:
    res = _browser_login(settings, headless=headless, timeout_s=timeout_s)
    write_health(settings, bool(res.get("ok")),
                 "" if res.get("ok") else ("silent refresh failed: " if headless else "") + str(res.get("reason")))
    return res


def _browser_login(settings: Settings, *, headless: bool = False, timeout_s: int = 300) -> dict:
    """Open Blackboard in a browser and wait until we land in Ultra, signed in.

    headless=True is the silent refresh: it only succeeds if the SSO session in
    the saved browser profile is still valid.
    """
    from playwright.sync_api import sync_playwright

    if not settings.base_url:
        return {"ok": False, "reason": "Set your Blackboard address first (BB_BASE_URL, e.g. https://learn.example.ac.uk)."}
    host = _host(settings)
    deadline = time.time() + (45 if headless else timeout_s)
    with sync_playwright() as pw:
        ctx = _launch(pw, settings, headless)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(settings.base_url + "/ultra/", wait_until="domcontentloaded")
            if not headless:
                try:
                    page.bring_to_front()
                except Exception:
                    pass
            clicked_sso = False
            while time.time() < deadline:
                url = page.url
                on_bb = host in url and "/ultra" in url and "login" not in url.lower()
                if not clicked_sso and host in url and "/ultra" not in url:
                    # On the landing page: start SSO. With a valid "stay signed in" cookie in the
                    # profile, Microsoft signs us straight back in without MFA.
                    # Many sites (e.g. Cibertec) hide the SAML button behind "Ver opciones", so a click would
                    # wait for a visible element and stall: follow the SAML login link directly when there is one.
                    try:
                        saml = page.eval_on_selector("a[href*='/auth-saml/saml/login']", "a => a.href")
                    except Exception:
                        saml = None
                    if saml:
                        page.goto(saml, wait_until="domcontentloaded")
                        clicked_sso = True
                        continue
                    for text in ((settings.sso_button,) if settings.sso_button else ()) + SSO_BUTTONS:
                        try:
                            btn = page.get_by_text(text, exact=False)
                            if btn.count():
                                btn.first.click(timeout=3000)
                                clicked_sso = True
                                break
                        except Exception:
                            pass
                cookies = [c for c in ctx.cookies() if host.endswith(c["domain"].lstrip("."))]
                names = {c["name"] for c in cookies}
                if on_bb and "BbRouter" in names:
                    # Confirm with the API from inside the browser session.
                    try:
                        resp = page.request.get(settings.base_url + "/learn/api/public/v1/users/me")
                        if resp.ok:
                            me = resp.json()
                            save_cookies(settings, cookies)
                            return {"ok": True, "user": me.get("userName"),
                                    "name": (me.get("name") or {}).get("given")}
                    except Exception:
                        pass
                page.wait_for_timeout(1000)
            return {"ok": False, "reason": "timed out waiting for sign-in"}
        finally:
            ctx.close()


def refresh_silently(settings: Settings) -> bool:
    try:
        return bool(browser_login(settings, headless=True).get("ok"))
    except Exception as e:  # noqa: BLE001
        write_health(settings, False, f"silent refresh crashed: {type(e).__name__}: {e}")
        return False
