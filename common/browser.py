from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


def start_playwright():
    stealth = Stealth()
    pw_cm = stealth.use_sync(sync_playwright())
    pw = pw_cm.__enter__()
    return pw, pw_cm


def launch_browser(pw, platform_cfg):
    return pw.chromium.launch(
        headless=platform_cfg["headless"],
        args=platform_cfg["launch_args"],
    )


def new_context(browser, platform_cfg):
    ctx_kwargs = {"user_agent": platform_cfg["user_agent"]}
    if platform_cfg.get("no_viewport"):
        ctx_kwargs["no_viewport"] = True
    else:
        ctx_kwargs["viewport"] = platform_cfg["viewport"]
    return browser.new_context(**ctx_kwargs)


def shutdown(pw_cm, browser):
    if browser:
        try:
            browser.close()
        except Exception:
            pass
    if pw_cm:
        try:
            pw_cm.__exit__(None, None, None)
        except Exception:
            pass