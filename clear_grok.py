import os
import json
import time
import base64
import random
import shutil
import requests
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


# =========================
# CONFIG
# =========================
HEADLESS = True

GROK_COOKIES_FILE = "cookies_grok/grok_cookies.json.encrypted"

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

PBKDF2_ITERATIONS = 200_000

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


# =========================
# ENV
# =========================
load_dotenv()

DECRYPT_KEY = os.getenv("DECRYPT_KEY")

if not DECRYPT_KEY:
    raise RuntimeError("DECRYPT_KEY missing")


# =========================
# CRYPTO
# =========================
def _derive_key(password: bytes, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password)


def _decrypt_payload(payload: Dict[str, Any], password: str) -> bytes:
    salt = base64.b64decode(payload["s"])
    nonce = base64.b64decode(payload["n"])
    ciphertext = base64.b64decode(payload["ct"])

    key = _derive_key(password.encode("utf-8"), salt)
    aesgcm = AESGCM(key)

    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise RuntimeError("❌ Decryption failed (InvalidTag)")


def load_cookies(file_path: Path) -> List[Dict[str, Any]]:
    print("[STEP] Loading cookies...", flush=True)

    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    plaintext = _decrypt_payload(payload, DECRYPT_KEY)
    cookies = json.loads(plaintext.decode("utf-8"))

    # cookies ko normalize aur sanitize karne ke liye
    for c in cookies:
        # 1. SameSite handle karne ke liye
        if "sameSite" in c:
            val = str(c["sameSite"]).lower()

            if val in ["no_restriction", "none", "unspecified", "null"]:
                c["sameSite"] = "None"
            elif val == "lax":
                c["sameSite"] = "Lax"
            elif val == "strict":
                c["sameSite"] = "Strict"
            else:
                c["sameSite"] = "Lax"

        # 2. partitionKey Fix: Object ko String mein badalne ya remove karne ke liye
        if "partitionKey" in c:
            p_key = c["partitionKey"]
            if isinstance(p_key, dict):
                # Agar dict ke andar topLevelSite string hai, toh use nikal lo
                if "topLevelSite" in p_key and isinstance(p_key["topLevelSite"], str):
                    c["partitionKey"] = p_key["topLevelSite"]
                else:
                    del c["partitionKey"]
            elif not isinstance(p_key, str):
                # Agar string ya dict dono nahi hai, toh remove kar do
                del c["partitionKey"]

    print("[OK] Cookies loaded and sanitized", flush=True)
    return cookies


# =========================
# MAIN
# =========================
def run():
    print("[START] Script started", flush=True)

    cookies = load_cookies(Path(GROK_COOKIES_FILE))

    print(f"[OK] Total cookies loaded: {len(cookies)}", flush=True)

    # =========================
    # STEALTH SETUP
    # =========================
    stealth = Stealth()

    pw_cm = stealth.use_sync(sync_playwright())

    pw = pw_cm.__enter__()

    try:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(
            no_viewport=True,
            user_agent=USER_AGENT
        )

        print("[STEP] Adding cookies to browser context...", flush=True)

        context.add_cookies(cookies)

        page = context.new_page()

        print("[OK] Cookies added successfully", flush=True)

        print("[STEP] Opening Grok...", flush=True)

        page.goto(
            "https://grok.com/",
            wait_until="domcontentloaded"
        )

        print("[OK] Grok opened with cookies (Logged In)", flush=True)

        # 1. Wait after opening Grok homepage
        initial_delay = random.randint(15, 30)
        print(f"[INFO] Waiting for {initial_delay} seconds on homepage...", flush=True)
        time.sleep(initial_delay)

        # 2. Navigating to the data management page
        print("[STEP] Navigating to Grok data page...", flush=True)
        page.goto("https://grok.com/?_s=data", wait_until="domcontentloaded")
        
        delay1 = random.randint(15, 30)
        print(f"[INFO] Waiting for {delay1} seconds on data page...", flush=True)
        time.sleep(delay1)

        # 3. Scrolling specific Settings locator to view (Syntax Fixed)
        print("[STEP] Scrolling to Settings section to find the button...", flush=True)
        try:
            settings_section = page.get_by_label('Settings', exact=True).locator('div').filter(has_text='Improve the ModelBy allowing').nth(1)
            settings_section.scroll_into_view_if_needed()
            print("[OK] Scrolled to target Settings view", flush=True)
        except Exception as scroll_err:
            print(f"[WARNING] Could not scroll to settings section: {scroll_err}", flush=True)

        # 4. First click on 'Delete All Conversations' (Syntax Fixed)
        print("[STEP] Clicking 'Delete All Conversations' for the first time...", flush=True)
        page.get_by_role('button', name='Delete All Conversations').click()
        
        delay2 = random.randint(15, 30)
        print(f"[INFO] Waiting for {delay2} seconds after first click...", flush=True)
        time.sleep(delay2)

        # 5. Second click on 'Delete All Conversations' (Confirmation - Syntax Fixed)
        print("[STEP] Clicking 'Delete All Conversations' for the second time...", flush=True)
        page.get_by_role('button', name='Delete All Conversations').click()
        
        delay3 = random.randint(15, 30)
        print(f"[INFO] Waiting for {delay3} seconds after second click...", flush=True)
        time.sleep(delay3)

        # 6. Final random wait before closing
        final_delay = random.randint(15, 30)
        print(f"[INFO] Final wait for {final_delay} seconds before closing the browser...", flush=True)
        time.sleep(final_delay)

    except Exception as e:
        print("[ERROR]", e, flush=True)

    finally:
        try:
            browser.close()
        except:
            pass

        try:
            if TEMP_DIR.exists():
                shutil.rmtree(TEMP_DIR)

            TEMP_DIR.mkdir(exist_ok=True)
            print("[CLEANUP] Temp cleared", flush=True)
        except Exception as e:
            print("[CLEANUP ERROR]", e, flush=True)

        try:
            pw_cm.__exit__(None, None, None)
        except:
            pass

        print("[DONE] Script finished", flush=True)


if __name__ == "__main__":
    run()