from __future__ import annotations

from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Page, BrowserContext
from .errors import E, die
from .display import has_display

import asyncio
import sys
import os
import json
import time
from urllib.request import urlopen
from urllib.error import URLError


# ---------------------------------------------------------------------------
# Configuration & Detection
# ---------------------------------------------------------------------------

def _get_cdp_url() -> str | None:
    """
    Return the CDP URL (ws://127.0.0.1:PORT/devtools/browser/<id>) if the user
    has exported AI_CLI_BRIDGE_CDP_URL. When present, we attach to an *external*
    headed browser instead of launching our own.
    """
    return os.environ.get("AI_CLI_BRIDGE_CDP_URL")


async def _ensure_cdp_browser(cfg) -> str | None:
    """
    Best-effort autostart for a CDP-enabled headed browser (Flatpak Ungoogled Chromium).
    Triggered only if:
      - AI_CLI_BRIDGE_CDP_URL is not set AND
      - config["cdp"]["enable_autostart"] is true

    Launches the browser with:
      --remote-debugging-address=127.0.0.1
      --remote-debugging-port=<port>
      --user-data-dir=<profile>
      --no-first-run --new-window
      <startup_urls...>

    Then polls http://127.0.0.1:<port>/json/version for webSocketDebuggerUrl.
    If obtained, sets AI_CLI_BRIDGE_CDP_URL and returns the ws URL.

    Returns None on failure without aborting (the caller may still proceed in non-CDP mode).
    """
    cdp = (cfg or {}).get("cdp") or {}
    if not cdp.get("enable_autostart"):
        return None

    port = int(cdp.get("port", 9222))
    wait_seconds = int(cdp.get("wait_seconds", 12))
    flatpak_id = cdp.get("flatpak_id", "io.github.ungoogled_software.ungoogled_chromium")
    user_data_dir = os.path.expanduser(cdp.get("user_data_dir", "~/.ai_cli_bridge/data/profiles/claude_cdp"))
    startup_urls = cdp.get("startup_urls") or ["https://claude.ai/chat"]

    cmd = [
        "flatpak", "run", flatpak_id,
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run", "--new-window",
        *startup_urls,
    ]

    try:
        # Fire-and-forget; do not await completion of the GUI app
        await asyncio.create_subprocess_exec(*cmd)
    except Exception as e:
        print(f"[AI-CLI-BRIDGE] CDP autostart failed to launch: {e}", file=sys.stderr)
        return None

    ws_url = None
    deadline = time.time() + wait_seconds
    version_url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < deadline and not ws_url:
        try:
            with urlopen(version_url, timeout=1.0) as r:
                data = json.load(r)
                ws_url = data.get("webSocketDebuggerUrl")
                if ws_url:
                    break
        except URLError:
            pass
        except Exception:
            pass
        await asyncio.sleep(0.25)

    if ws_url:
        os.environ["AI_CLI_BRIDGE_CDP_URL"] = ws_url
        print(f"[AI-CLI-BRIDGE] CDP ready: {ws_url}", file=sys.stderr)
        return ws_url

    print("[AI-CLI-BRIDGE] CDP autostart did not become ready in time.", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Challenge detection & readiness checks
# ---------------------------------------------------------------------------

CHALLENGE_LOCATORS = [
    # Generic
    "iframe[title*='challenge']",
    "iframe[src*='challenge']",
    "[data-testid*='challenge']",
    "text=/verify you are human/i",
    "text=/are you a human/i",
    "div:has-text('Verify you are human')",

    # Cloudflare Turnstile
    "iframe[src*='challenges.cloudflare.com']",
    ".cf-challenge",
    ".cf-turnstile",
    "div[aria-label*='challenge']",

    # Arkose / FunCaptcha
    "iframe[src*='funcaptcha.com']",
    "iframe[src*='arkoselabs.com']",
]


async def _any_visible(page: Page, selectors: list[str]) -> str | None:
    """Return the first selector that is currently visible, else None."""
    for sel in selectors:
        if not sel:
            continue
        try:
            if await page.locator(sel).first.is_visible():
                return sel
        except Exception:
            pass
    return None


async def _check_auth_readiness(page: Page, cfg, timeout: int = 10) -> tuple[bool, str]:
    """
    Verify auth readiness per spec Section 5:
      1) input_box present & enabled
      2) login_form absent
      3) error_indicator absent
    """
    selectors = cfg.get("selectors", {}) or {}
    input_box = selectors.get("input_box")
    login_form = selectors.get("login_form")
    error_indicator = selectors.get("error_indicator")

    try:
        # 1) input_box present & enabled
        if input_box:
            locator = page.locator(input_box).first
            await locator.wait_for(state="visible", timeout=timeout * 1000)
            if not await locator.is_enabled():
                return False, "Input box not enabled"

        # 2) login_form absent
        if login_form and await _any_visible(page, [login_form]):
            return False, "Login form still visible"

        # 3) error_indicator absent
        if error_indicator and await _any_visible(page, [error_indicator]):
            return False, "Error indicator present"

        return True, "Auth ready"

    except Exception as e:
        return False, f"Auth check failed: {e}"


async def wait_for_challenge_clear(page: Page, timeout: int = 120) -> bool:
    """
    Detect a human-verification challenge and wait until it disappears.
    Returns True if a challenge was detected and later cleared; False if none found.
    Raises E.E002 if it doesn't clear within `timeout`.
    """
    sel = await _any_visible(page, CHALLENGE_LOCATORS)
    if not sel:
        return False

    print(
        f"[AI-CLI-BRIDGE] Human verification detected ({sel}) — waiting up to {timeout}s...",
        file=sys.stderr,
    )
    try:
        await page.wait_for_selector(sel, state="hidden", timeout=timeout * 1000)
        print("[AI-CLI-BRIDGE] Challenge cleared.", file=sys.stderr)
        return True
    except asyncio.TimeoutError:
        die(E.E002, f"Challenge not cleared after {timeout}s. Please complete verification and retry.")


# ---------------------------------------------------------------------------
# Fingerprint softening (heads-only, gentle)
# ---------------------------------------------------------------------------

SOFTEN_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--password-store=basic",
    "--use-mock-keychain",
]

REALISTIC_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

STEALTH_INIT_JS = """
// 1) navigator.webdriver → undefined
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2) plugins & languages look normal
try {
  Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
  Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3] });
} catch (e) {}

// 3) Permissions.query spoof (common probe)
const _query = (navigator.permissions && navigator.permissions.query)
  ? navigator.permissions.query.bind(navigator.permissions)
  : null;
if (_query) {
  navigator.permissions.query = (params) => {
    if (params && params.name === 'notifications') {
      return Promise.resolve({ state: Notification.permission });
    }
    return _query(params);
  };
}

// 4) WebGL vendor/renderer echo (plausible AMD on Linux)
(function() {
  const VENDOR  = "AMD";
  const RENDERER = "AMD Radeon 680M (RADV NAVI3X)";

  function patch(getParameter) {
    return function(pname) {
      const gl = this;
      try {
        const dbg = gl.getExtension && (gl.getExtension('WEBGL_debug_renderer_info')
                 || gl.getExtension('MOZ_WEBGL_debug_renderer_info')
                 || gl.getExtension('WEBKIT_WEBGL_debug_renderer_info'));
        if (dbg) {
          const UNMASKED_VENDOR = dbg.UNMASKED_VENDOR_WEBGL;
          const UNMASKED_RENDERER = dbg.UNMASKED_RENDERER_WEBGL;
          if (pname === UNMASKED_VENDOR)   return VENDOR;
          if (pname === UNMASKED_RENDERER) return RENDERER;
        }
      } catch (e) {}
      return getParameter.apply(this, arguments);
    };
  }

  try {
    const p1 = (typeof WebGLRenderingContext !== 'undefined') && WebGLRenderingContext.prototype;
    if (p1 && p1.getParameter) {
      const orig = p1.getParameter;
      Object.defineProperty(p1, 'getParameter', { value: patch(orig) });
    }
  } catch (_) {}

  try {
    const p2 = (typeof WebGL2RenderingContext !== 'undefined') && WebGL2RenderingContext.prototype;
    if (p2 && p2.getParameter) {
      const orig = p2.getParameter;
      Object.defineProperty(p2, 'getParameter', { value: patch(orig) });
    }
  } catch (_) {}
})();
"""


# ---------------------------------------------------------------------------
# Main: launch/attach browser and ensure readiness
# ---------------------------------------------------------------------------

@asynccontextmanager
async def launch_browser(cfg):
    """
    Launch (or attach to) a headed Chromium context per V1.3.1 spec.

    Modes:
      - CDP mode (preferred): if AI_CLI_BRIDGE_CDP_URL is present OR config.cdp.enable_autostart is true,
        attach to user's *external* browser (Flatpak Ungoogled Chromium).
      - Fallback mode: launch Playwright's persistent context (headed).

    Navigation policy:
      - Prefer an existing Claude tab (CDP mode).
      - Only navigate if not already on the desired origin/path.
      - Perform human-challenge wait only if a challenge is actually present.
      - Verify auth readiness (input present & enabled, no login form, no error indicator).
    """
    if not has_display():
        die(E.E001, "No display available. AI-CLI-Bridge cannot run headless.")

    playwright = None
    browser: BrowserContext | None = None

    try:
        playwright = await async_playwright().start()

        # CDP autostart (if env not set) — frictionless startup
        cdp_url = _get_cdp_url() or await _ensure_cdp_browser(cfg)

        if cdp_url:
            # ----- External Browser (CDP) Mode: attach to headed browser -----
            try:
                remote = await playwright.chromium.connect_over_cdp(cdp_url)
            except Exception as e:
                await playwright.stop()
                die(E.E002, f"CDP connect failed: {e}. Ensure remote debugging is enabled.")
            # Adopt an existing page or create a new one
            try:
                contexts = getattr(remote, "contexts", []) or []
                pages = contexts[0].pages if contexts else []
                page: Page = pages[0] if pages else await contexts[0].new_page()
            except Exception:
                page = await remote.new_page()
            browser = remote  # maintain variable naming consistency

        else:
            # ----- Default Mode: Playwright-bundled Chromium (persistent, headed) -----
            browser = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(cfg["_profile_dir"]),
                headless=False,                 # headed-only per spec
                args=SOFTEN_ARGS,               # reduce common automation markers
                user_agent=REALISTIC_UA,        # align navigator.userAgent
                locale="en-US",
            )
            # Inject stealth fixes for all pages in this persistent context
            await browser.add_init_script(STEALTH_INIT_JS)
            # Conservative, realistic UA + CH (Linux + Chromium 129)
            await browser.set_extra_http_headers({
                "User-Agent": REALISTIC_UA,
                "sec-ch-ua": "\"Chromium\";v=\"129\", \"Not=A?Brand\";v=\"24\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Linux\"",
            })
            page = browser.pages[0] if browser.pages else await browser.new_page()

        # ------------------------
        # Tab selection / navigation
        # ------------------------
        target_url = cfg.get("_conversation_url") or cfg.get("base_url", "https://claude.ai")

        # In CDP mode, prefer an already-open Claude tab if present
        try:
            from urllib.parse import urlparse
            def _host(u: str):
                try:
                    pu = urlparse(u or "")
                    return (pu.scheme or "", pu.hostname or "", pu.port or -1)
                except Exception:
                    return ("", "", -1)

            if _get_cdp_url():
                pages = []
                try:
                    contexts = getattr(browser, "contexts", []) or []
                    for ctx in contexts:
                        pages.extend(getattr(ctx, "pages", []) or [])
                except Exception:
                    pass
                for p in pages:
                    u = getattr(p, "url", "") or ""
                    sch, host, port = _host(u)
                    if sch == "https" and host == "claude.ai":
                        page = p
                        break
        except Exception:
            pass

        # Only navigate if we're not already on the desired origin/path
        def _same_origin(u: str, v: str) -> bool:
            try:
                from urllib.parse import urlparse
                pu, pv = urlparse(u), urlparse(v)
                return (pu.scheme, pu.hostname, pu.port or -1) == (pv.scheme, pv.hostname, pv.port or -1)
            except Exception:
                return False

        try:
            cur = page.url
        except Exception:
            cur = ""

        should_navigate = True
        if cur and target_url:
            # If on same origin and already a Claude route, avoid a reload (reduces CAPTCHA risk)
            if _same_origin(cur, target_url) and cur.startswith("https://claude.ai/"):
                should_navigate = False

        if should_navigate:
            await page.goto(target_url, timeout=cfg["timeouts"]["page_load"] * 1000)

        # Gentle motion/scroll to add human-like entropy (no clicks/typing)
        try:
            await page.wait_for_timeout(800)
            vw = await page.evaluate("() => window.innerWidth")
            vh = await page.evaluate("() => window.innerHeight")
            await page.mouse.move(int(vw * 0.3), int(vh * 0.5), steps=8)
            await page.wait_for_timeout(140)
            await page.mouse.move(int(vw * 0.6), int(vh * 0.3), steps=10)
            await page.wait_for_timeout(200)
            await page.mouse.wheel(delta_y=200)
        except Exception:
            pass

        # Human-verification challenge handling (only if present)
        challenge_timeout = cfg["timeouts"].get("response_wait", 120)
        await wait_for_challenge_clear(page, timeout=challenge_timeout)

        # Auth readiness (per spec §5)
        ready, message = await _check_auth_readiness(page, cfg, timeout=cfg["timeouts"]["page_load"])
        if not ready:
            # Soft retry once if a challenge element is still present
            try:
                if await _any_visible(page, CHALLENGE_LOCATORS):
                    await page.wait_for_timeout(15000)
                    ready, message = await _check_auth_readiness(page, cfg, timeout=cfg["timeouts"]["page_load"])
            except Exception:
                pass

        if not ready:
            die(E.E002, f"Auth not ready: {message}. Open the page and complete login, then retry.")

    except Exception as e:
        # Teardown on error
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright:
            try:
                await playwright.stop()
            except Exception:
                pass
        if isinstance(e, SystemExit):
            raise
        die(E.E002, f"Browser launch failed: {e}")

    try:
        # Yield the ready page to callers (open/send/etc.)
        yield page
    finally:
        # Graceful shutdown:
        # - CDP mode: DO NOT close the external browser; leave tabs intact.
        # - Persistent mode: close our browser context.
        try:
            if _get_cdp_url():
                # leave external browser running; nothing to do
                pass
            else:
                await browser.close()
        except Exception:
            pass
        try:
            await playwright.stop()
        except Exception:
            pass

