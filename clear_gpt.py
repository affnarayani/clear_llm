import os
import sys
import json
import time
import base64
import random
import shutil
import requests
import re
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

COOKIES_DIR = Path("cookies_gpt")
encrypted_files = list(COOKIES_DIR.glob("*.encrypted"))

if not encrypted_files:
    print("No .encrypted cookie files found in 'cookies_gpt/' folder", flush=True)
    sys.exit(1)

print(f"[OK] Found {len(encrypted_files)} cookie file(s) to process.", flush=True)

PBKDF2_ITERATIONS = 200_000

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


# =========================
# ENV
# =========================
load_dotenv()

DECRYPT_KEY = os.getenv("DECRYPT_KEY")

if not DECRYPT_KEY:
    print("DECRYPT_KEY missing in environment variables.", flush=True)
    sys.exit(1)


# =========================
# RANDOM WAIT
# =========================
def custom_random_wait(min_sec, max_sec):
    seconds = random.uniform(min_sec, max_sec)
    print(f"[WAIT] Sleeping for {seconds:.2f} seconds...", flush=True)
    time.sleep(seconds)


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
        print("Decryption failed (InvalidTag)", flush=True)
        sys.exit(1)


def load_cookies(file_path: Path) -> List[Dict[str, Any]]:
    print(f"[STEP] Loading cookies from {file_path.name}...", flush=True)

    try:
        with file_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        plaintext = _decrypt_payload(payload, DECRYPT_KEY)
        cookies = json.loads(plaintext.decode("utf-8"))

        # normalize SameSite and PartitionKey
        for c in cookies:
            if "partitionKey" in c and isinstance(c["partitionKey"], dict):
                if "topLevelSite" in c["partitionKey"]:
                    c["partitionKey"] = str(c["partitionKey"]["topLevelSite"])
                else:
                    del c["partitionKey"]

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

        print("[OK] Cookies loaded", flush=True)
        return cookies
    except Exception as crypto_err:
        print(f"[CRITICAL CRYPTO ERROR]: File {file_path.name} parse/decrypt failed: {crypto_err}", flush=True)
        sys.exit(1)

def upload_to_onlyfiles(screenshot_path):
    url = "https://api.onlyfiles.com/v1/upload"
    expire_seconds = 172800  # 48 hours

    with open(screenshot_path, "rb") as file:
        response = requests.post(url, files={"file": file}, data={"expire": expire_seconds})

    if response.status_code == 200:
        res_data = response.json()
        if res_data.get("status"):
            direct_url = res_data["data"]["file"]["url"]["full"]
            print(f"👉 DIRECT LINK (Expires in 48 Hours): {direct_url}")
            return direct_url
        else:
            error_msg = res_data.get("error", {}).get("message", "Unknown error")
            print(f"[WARNING] Upload Failed: {error_msg}")
            return None
    else:
        print(f"[WARNING] Upload Failed: {response.status_code}")
        return None

# =========================
# MAIN
# =========================
def run():
    print("[START] Script started", flush=True)

    # LOOP: Iterating through each encrypted cookie file in the directory
    for index, cookie_file in enumerate(encrypted_files, start=1):
        print("\n" + "="*50, flush=True)
        print(f"[PROCESS] Processing file {index}/{len(encrypted_files)}: {cookie_file.name}", flush=True)
        print("="*50, flush=True)

        browser = None
        pw_cm = None

        try:
            cookies = load_cookies(cookie_file)
            print(f"[OK] Total cookies loaded: {len(cookies)}", flush=True)

            # =========================
            # STEALTH SETUP
            # =========================
            stealth = Stealth()
            pw_cm = stealth.use_sync(sync_playwright())
            pw = pw_cm.__enter__()

            browser = pw.chromium.launch(
                headless=HEADLESS,
                args=[
                    "--start-maximized",
                    "--window-size=1920,1080",
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=USER_AGENT
            )

            context.grant_permissions(["clipboard-read", "clipboard-write"])

            print("[STEP] Adding cookies to browser context...", flush=True)
            context.add_cookies(cookies)

            page = context.new_page()
            print("[OK] Cookies added successfully", flush=True)

            print("[STEP] Opening ChatGPT Main URL (Logging in via cookies)...", flush=True)
            page.goto(
                "https://chatgpt.com/",
                wait_until="domcontentloaded"
            )
            print("[OK] URL opened and Login completed via session cookies", flush=True)

            # ==================================================
            # UPDATED AUTOMATION FLOW
            # ==================================================

            print("[STEP] Navigating directly to Data controls settings...", flush=True)
            page.goto(
                "https://chatgpt.com/settings/data-controls",
                wait_until="domcontentloaded"
            )
            print("[OK] Data controls URL loaded", flush=True)

            # Wait random 15-30 seconds
            print("[STEP] Waiting 15-30s...", flush=True)
            custom_random_wait(15, 30)

            # Locate and click first 'Delete all' button
            print("[STEP] Clicking first 'Delete all' button...", flush=True)
            delete_all_btn = page.get_by_role("button", name="Delete all")
            delete_all_btn.wait_for(state="visible", timeout=30000)
            delete_all_btn.click()
            print("[OK] First 'Delete all' clicked", flush=True)

            # Wait random 6-12 seconds
            print("[STEP] Waiting 6-12s before confirmation...", flush=True)
            custom_random_wait(6, 12)

            # Again locate and click confirmation 'Delete all' button
            print("[STEP] Clicking confirmation 'Delete all' button...", flush=True)
            confirm_btn = page.get_by_role("button", name="Delete all")
            confirm_btn.wait_for(state="visible", timeout=30000)
            confirm_btn.click()
            print("[OK] Confirmation 'Delete all' clicked successfully", flush=True)

            # Post-action randomized wait interval (15-30s) before session destruction
            print("[STEP] Waiting 15-30s before browser exit...", flush=True)
            custom_random_wait(15, 30)

        except SystemExit:
            raise
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Operation failed for {cookie_file.name}: {e}", flush=True)
            print("[STEP] Executing emergency browser teardown and exiting program via sys.exit(1)...", flush=True)
            
            # CAPTURE SCREENSHOT ON ERROR
            if 'page' in locals() and page:
                try:
                    screenshot_path = "clear_gpt_error_screenshot.png"
                    page.screenshot(path=screenshot_path, full_page=True)
                    print(f"[OK] Error screenshot captured: {screenshot_path}", flush=True)
                    
                    upload_to_onlyfiles(screenshot_path)
                except Exception as screenshot_err:
                    print(f"[WARNING] Could not capture or upload screenshot: {screenshot_err}", flush=True)
            
            if browser:
                try:
                    browser.close()
                except:
                    pass
            if pw_cm:
                try:
                    pw_cm.__exit__(None, None, None)
                except:
                    pass
                    
            sys.exit(1)

        finally:
            if browser or pw_cm:
                print(f"[STEP] Exiting browser and cleaning context for {cookie_file.name}...", flush=True)
                if browser:
                    try:
                        browser.close()
                    except:
                        pass
                if pw_cm:
                    try:
                        pw_cm.__exit__(None, None, None)
                    except:
                        pass

    print("\n[DONE] All cookie files processed successfully.", flush=True)


if __name__ == "__main__":
    run()