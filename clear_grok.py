import os
import shutil
import sys

from common.config import get_config, platform_config, ROOT
from common.crypto_utils import load_cookies
from common.browser import start_playwright, launch_browser, new_context, shutdown
from common.locator_loader import load_locators
from common.actions import click_with_fallback, scroll_down
from common.screenshot import capture_error_screenshot
from common.waits import sleep_random
from common.locator_correction import reconcile_startup


PLATFORM = "grok"
GROK_COOKIES_FILE = "grok_cookies/grok_cookies.json.encrypted"
TEMP_DIR = ROOT / "temp"


def run():
    cfg = get_config()
    pc = platform_config(PLATFORM)
    scroll_presses = pc.get("scroll_down_presses", 15)

    reconcile_startup(PLATFORM, "locators/grok_locators.txt")

    waits = cfg["waits"]
    decrypt_key = os.getenv(cfg["env"]["decrypt_key"])
    if not decrypt_key:
        raise RuntimeError(f"{cfg['env']['decrypt_key']} missing")

    TEMP_DIR.mkdir(exist_ok=True)

    cookies = load_cookies(ROOT / GROK_COOKIES_FILE, decrypt_key, cfg["pbkdf2_iterations"])
    print(f"[OK] Total cookies loaded: {len(cookies)}", flush=True)

    browser = None
    pw_cm = None
    page = None
    locator_failed = False

    try:
        pw, pw_cm = start_playwright()
        browser = launch_browser(pw, pc)

        context = new_context(browser, pc)

        print("[STEP] Adding cookies to browser context...", flush=True)
        context.add_cookies(cookies)

        page = context.new_page()
        print("[OK] Cookies added successfully", flush=True)

        loc = load_locators("locators/grok_locators.txt", page)

        print("[STEP] Opening Grok...", flush=True)
        page.goto("https://grok.com/", wait_until="domcontentloaded")
        print("[OK] Grok opened with cookies (Logged In)", flush=True)

        print(f"[INFO] Waiting {waits['random_min_seconds']}-{waits['random_max_seconds']}s on homepage...", flush=True)
        sleep_random(waits["random_min_seconds"], waits["random_max_seconds"])

        print("[STEP] Navigating to Grok data page...", flush=True)
        page.goto("https://grok.com/?_s=data", wait_until="domcontentloaded")

        print(f"[INFO] Waiting {waits['random_min_seconds']}-{waits['random_max_seconds']}s on data page...", flush=True)
        sleep_random(waits["random_min_seconds"], waits["random_max_seconds"])

        print("[STEP] Focusing settings scroll area via 'Personalization' heading...", flush=True)
        if not click_with_fallback(page, loc, "personalization_heading"):
            locator_failed = True
            return

        print(f"[STEP] Scrolling down via Down arrow key ({scroll_presses} presses max)...", flush=True)
        stop_locator = loc.chain("delete_all_conversations_button")[0]
        scroll_down(page, times=scroll_presses, stop_locator=stop_locator)
        print("[OK] Scrolled down to reveal the delete button", flush=True)

        print("[STEP] Clicking 'Delete All Conversations'...", flush=True)
        if not click_with_fallback(page, loc, "delete_all_conversations_button"):
            locator_failed = True
            return

        print(f"[INFO] Waiting {waits['random_min_seconds']}-{waits['random_max_seconds']}s after first click...", flush=True)
        sleep_random(waits["random_min_seconds"], waits["random_max_seconds"])

        print("[STEP] Clicking 'Are you sure?' button...", flush=True)
        if not click_with_fallback(page, loc, "confirm_delete_conversations_button"):
            locator_failed = True
            return

        print(f"[INFO] Waiting {waits['random_min_seconds']}-{waits['random_max_seconds']}s after second click...", flush=True)
        sleep_random(waits["random_min_seconds"], waits["random_max_seconds"])

        print(f"[INFO] Final wait {waits['random_min_seconds']}-{waits['random_max_seconds']}s before closing the browser...", flush=True)
        sleep_random(waits["random_min_seconds"], waits["random_max_seconds"])

    except Exception as e:
        print("[ERROR]", e, flush=True)
        locator_failed = True

    finally:
        if locator_failed and page:
            capture_error_screenshot(page, cfg)

        shutdown(pw_cm, browser)

        try:
            if TEMP_DIR.exists():
                shutil.rmtree(TEMP_DIR)
            TEMP_DIR.mkdir(exist_ok=True)
            print("[CLEANUP] Temp cleared", flush=True)
        except Exception as e:
            print("[CLEANUP ERROR]", e, flush=True)

        print("[DONE] Script finished", flush=True)

        if locator_failed:
            print("[EXIT] Terminating process with exit code 1 due to missing locator.", flush=True)
            sys.exit(1)


if __name__ == "__main__":
    run()