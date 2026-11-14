import os
import sys

from common.config import get_config, platform_config, ROOT
from common.crypto_utils import load_cookies
from common.browser import start_playwright, launch_browser, new_context, shutdown
from common.locator_loader import load_locators
from common.actions import click_with_fallback
from common.screenshot import capture_error_screenshot
from common.waits import sleep_random
from common.locator_correction import reconcile_startup


PLATFORM = "chatgpt"


def run():
    cfg = get_config()
    pc = platform_config(PLATFORM)

    reconcile_startup(PLATFORM, "locators/chatgpt_locators.txt")

    waits = cfg["waits"]
    decrypt_key = os.getenv(cfg["env"]["decrypt_key"])
    if not decrypt_key:
        print(f"{cfg['env']['decrypt_key']} missing in environment variables.", flush=True)
        sys.exit(1)

    cookies_dir = ROOT / cfg["cookie_dirs"][PLATFORM]
    encrypted_files = list(cookies_dir.glob("*.encrypted"))
    if not encrypted_files:
        print(f"No .encrypted cookie files found in '{cookies_dir}' folder", flush=True)
        sys.exit(1)

    print(f"[OK] Found {len(encrypted_files)} cookie file(s) to process.", flush=True)
    print("[START] Script started", flush=True)

    for index, cookie_file in enumerate(encrypted_files, start=1):
        print("\n" + "=" * 50, flush=True)
        print(f"[PROCESS] Processing file {index}/{len(encrypted_files)}: {cookie_file.name}", flush=True)
        print("=" * 50, flush=True)

        browser = None
        pw_cm = None
        page = None

        try:
            cookies = load_cookies(cookie_file, decrypt_key, cfg["pbkdf2_iterations"])
            print(f"[OK] Total cookies loaded: {len(cookies)}", flush=True)

            pw, pw_cm = start_playwright()
            browser = launch_browser(pw, pc)

            context = new_context(browser, pc)
            context.grant_permissions(["clipboard-read", "clipboard-write"])

            print("[STEP] Adding cookies to browser context...", flush=True)
            context.add_cookies(cookies)

            page = context.new_page()
            print("[OK] Cookies added successfully", flush=True)

            loc = load_locators("locators/chatgpt_locators.txt", page)

            print("[STEP] Opening ChatGPT Main URL (Logging in via cookies)...", flush=True)
            page.goto("https://chatgpt.com/", wait_until="domcontentloaded")
            print("[OK] URL opened and Login completed via session cookies", flush=True)

            print("[STEP] Navigating directly to Data controls settings...", flush=True)
            page.goto("https://chatgpt.com/settings/data-controls", wait_until="domcontentloaded")
            print("[OK] Data controls URL loaded", flush=True)

            print(f"[STEP] Waiting {waits['random_min_seconds']}-{waits['random_max_seconds']}s...", flush=True)
            sleep_random(waits["random_min_seconds"], waits["random_max_seconds"])

            print("[STEP] Clicking first 'Delete all' button...", flush=True)
            click_with_fallback(page, loc, "delete_all_chat_history_button")
            print("[OK] First 'Delete all' clicked", flush=True)

            print(f"[STEP] Waiting {waits['short_random_min_seconds']}-{waits['short_random_max_seconds']}s before confirmation...", flush=True)
            sleep_random(waits["short_random_min_seconds"], waits["short_random_max_seconds"])

            print("[STEP] Clicking confirmation 'Delete all' button...", flush=True)
            click_with_fallback(page, loc, "confirm_delete_all_button")
            print("[OK] Confirmation 'Delete all' clicked successfully", flush=True)

            print(f"[STEP] Waiting {waits['random_min_seconds']}-{waits['random_max_seconds']}s before browser exit...", flush=True)
            sleep_random(waits["random_min_seconds"], waits["random_max_seconds"])

        except SystemExit:
            raise
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Operation failed for {cookie_file.name}: {e}", flush=True)
            print("[STEP] Executing emergency browser teardown and exiting program via sys.exit(1)...", flush=True)

            if page:
                capture_error_screenshot(page, cfg)

            sys.exit(1)

        finally:
            if browser or pw_cm:
                print(f"[STEP] Exiting browser and cleaning context for {cookie_file.name}...", flush=True)
                shutdown(pw_cm, browser)

    print("\n[DONE] All cookie files processed successfully.", flush=True)


if __name__ == "__main__":
    run()