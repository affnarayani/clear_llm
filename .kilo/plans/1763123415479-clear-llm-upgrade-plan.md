# Clear_LLM Upgrade Plan

## Goal
Upgrade the 2-script automation (`clear_gpt.py`, `clear_grok.py`) so that:
- Every Playwright locator is externalized to a per-platform editable `.txt` file (single source of truth).
- Every locator has a **Gemini Vision fallback** (`gemini-3.5-flash-lite`) that clicks by coordinates when the text locator fails.
- Shared config lives in `/json/config.json`; shared code lives in `/common`.
- Error screenshots go to `/error/error_screenshot.png`.
- Onlyfiles is the only upload service (IMGBBB fully removed).
- GitHub workflows install from `requirements.txt`, pass `GEMINI_API_KEY`, and keep Cloudflare + screenshot logic intact.
- All code/comments are English; no secrets leak.

## Scope notes (what does NOT apply)
- No Claude / KDP / Gumroad code exists -> no `claude_locators.txt`, `kdp_cookies`, `gumroad_cookies`.
- No `_v{i}` outdated files exist -> nothing to delete.
- No plain data `.json` files exist. Encrypted cookie stores (`*.json.encrypted`) stay in their cookie folders (they are cookie data, not config). Only the new `config.json` goes to `/json`.

---

## Target file tree
```
/common/
  __init__.py
  config.py          # load_config() -> dict, resolves repo paths
  crypto_utils.py    # derive_key, decrypt_payload, load_cookies (deduped)
  onlyfiles.py       # upload_screenshot(path) -> url|None
  locator_loader.py  # load_locators(txt_path, page) -> Locators (exec-load)
  gemini_vision.py   # gemini_click(page, description), _find_coords(...)
/locators/
  chatgpt_locators.txt
  grok_locators.txt
/json/
  config.json
/error/
  .gitkeep
clear_gpt.py          # refactored, thin
clear_grok.py         # refactored, thin
encrypt.py            # import crypto from common
requirements.txt      # + google-genai
.env                  # + GEMINI_API_KEY, - IMGBBB_API_KEY
```

---

## 1. `/json/config.json` (all shared config)
```json
{
  "headless": true,
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  "pbkdf2_iterations": 200000,
  "waits": {
    "absolute_seconds": 5,
    "random_min_seconds": 15,
    "random_max_seconds": 30,
    "short_random_min_seconds": 6,
    "short_random_max_seconds": 12
  },
  "screenshot": { "dir": "error", "filename": "error_screenshot.png", "full_page": true },
  "onlyfiles": { "upload_url": "https://api.onlyfiles.com/v1/upload", "expire_seconds": 172800, "enabled": true },
  "gemini": { "api_key_env": "GEMINI_API_KEY", "model": "gemini-3.5-flash-lite" },
  "env": { "decrypt_key": "DECRYPT_KEY" },
  "cookie_dirs": { "chatgpt": "chatgpt_cookies", "grok": "grok_cookies" },
  "platforms": {
    "chatgpt": {
      "viewport": { "width": 1920, "height": 1080 },
      "launch_args": ["--start-maximized", "--window-size=1920,1080", "--disable-blink-features=AutomationControlled"]
    },
    "grok": {
      "no_viewport": true,
      "launch_args": ["--start-maximized", "--disable-blink-features=AutomationControlled"]
    }
  }
}
```
`common/config.py` loads this once, exposes `get_config()` and `platform_config(name)` (merges shared defaults with per-platform overrides).

---

## 2. `/locators/*.txt` (single source of truth)
Format per line: `<descriptive_name> = <exact playwright expr>   # vision: <description used by Gemini>`
- `common/locator_loader.py` reads the file **after** `page` exists, execs each line in a namespace containing `page` and `re`, and returns a `Locators` object exposing:
  - attribute access -> live Playwright Locator (`loc.delete_all_chat_history_button`)
  - `loc.vision("name")` -> the `# vision:` description string
  - `loc.raw("name")` -> the exact expression text (for logging)

`chatgpt_locators.txt`:
```
# ChatGPT locators. Edit expressions here; Python loads them verbatim.
delete_all_chat_history_button = page.get_by_role("button", name="Delete all")   # vision: the "Delete all" button on the Data controls settings page
confirm_delete_all_button = page.get_by_role("button", name="Delete all")   # vision: the confirmation "Delete all" button inside the delete-confirmation dialog
```

`grok_locators.txt`:
```
# Grok locators. Edit expressions here; Python loads them verbatim.
data_controls_settings_section = page.get_by_text('Data ControlsImprove the')   # vision: the "Data Controls" settings section heading on the Grok data page
delete_all_conversations_button = page.locator('div').filter(has_text=re.compile(r'^Delete All ConversationsDelete all of your conversation data\.Delete$')).get_by_role('button')   # vision: the "Delete All Conversations" button in the data controls section
confirm_delete_conversations_button = page.get_by_role('button', name='Are you sure?')   # vision: the "Are you sure?" confirmation button in the delete dialog
```
- No locator is used directly in any `.py`; both scripts call `load_locators(...)`.

---

## 3. Gemini Vision fallback (`/common/gemini_vision.py`)
- SDK: `google-genai` (`from google import genai`, `from google.genai import types`), model `gemini-3.5-flash-lite`, key from `GEMINI_API_KEY` env.
- `gemini_click(page, description)`:
  1. `page.screenshot()` -> PNG bytes.
  2. Prompt Gemini: return strict JSON `{"found": bool, "x": int, "y": int}` for the described element's click point (pixel center) in the screenshot.
  3. On `found`, `page.mouse.click(x, y)`; return True. On failure/exception, log and return False.
- `click_with_fallback(page, locators, name, timeout_ms)`:
  1. Try `loc = locators.attr(name); loc.wait_for(state="visible", timeout=timeout_ms); loc.click()`.
  2. On any exception -> `gemini_click(page, locators.vision(name))`.
- Every action in both scripts goes through `click_with_fallback`. If fallback also fails, existing error path runs (screenshot + exit 1).

---

## 4. `/common` extraction (full)
- `crypto_utils.py`: `derive_key`, `decrypt_payload`, `load_cookies` (single implementation; sameSite/partitionKey normalization merged).
- `onlyfiles.py`: `upload_screenshot(path)` using `config.onlyfiles` (48h expire). Only upload service; IMGBBB gone.
- `config.py`, `locator_loader.py`, `gemini_vision.py` as above.
- `encrypt.py` imports `derive_key`-equivalent from `common.crypto_utils` (keep behavior: encrypt `cookies.json` -> `cookies.json.encrypted`, delete plaintext).

---

## 5. Script refactors
`clear_gpt.py`:
- Import config/common helpers. Read `HEADLESS`, UA, waits, viewport, launch_args from config.
- Cookie dir = `chatgpt_cookies` (renamed). Glob `*.encrypted`.
- `loc = load_locators("locators/chatgpt_locators.txt", page)` after page creation.
- Replace direct locators with `click_with_fallback(...)`.
- Error path: screenshot to `error/error_screenshot.png` (mkdir `error`), replace if exists, then `upload_screenshot`.

`clear_grok.py`:
- Same pattern; cookie file = `grok_cookies/grok_cookies.json.encrypted` (renamed folder).
- Use `locators/grok_locators.txt`; `click_with_fallback` for all clicks; keep `scroll_into_view_if_needed` on the settings section (also fallback-guarded).
- Convert all Hinglish comments to English.

---

## 6. Requirements & env
- `requirements.txt`: add `google-genai` (keep cryptography, python-dotenv, requests, playwright, playwright-stealth). Recommend pinning versions.
- `.env`: add `GEMINI_API_KEY=<your-gemini-api-key>`; remove `IMGBBB_API_KEY`.
- `.gitignore`: add `__pycache__/`, `*.pyc`, `/error/` (keep dir via `.gitkeep` if desired), keep `.env`, `/temp/`.

---

## 7. GitHub workflows
- `1a_clear_gpt.yml`:
  - Remove `IMGBBB_API_KEY` env; add `GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}`.
  - Screenshot artifact path -> `error/error_screenshot.png`.
  - Keep Cloudflare WARP, `pip install -r requirements.txt`, `playwright install chromium`.
  - Translate the Hinglish comment to English.
- `2a_clear_grok.yml`: same env swap + `error/error_screenshot.png`; keep Cloudflare.
- `0a_retry.yml`, `0b_clear_history.yml`: pure `gh` API, no project files/locators -> leave intact (verify no folder/file refs).
- Ensure checkout includes `common/`, `locators/`, `json/` (default checkout already does).
- Add repo secret `GEMINI_API_KEY` (user must set in GitHub Settings -> Secrets).

---

## 8. Cookie folder rename (git mv)
- `cookies_gpt/`  -> `chatgpt_cookies/`
- `cookies_grok/` -> `grok_cookies/`
- Update all Python + workflow references.

---

## 9. Secret-leak audit (final step)
- `.env` is gitignored and NOT tracked -> good. Confirm `git ls-files` shows no `.env`.
- Remove `IMGBBB_API_KEY` from `.env` and both workflows (done above).
- `__pycache__/*.pyc` are currently committed -> `git rm -r --cached __pycache__` and add to `.gitignore`.
- No secrets hardcoded in `.py`.
- Note: `.env` holds live `DECRYPT_KEY` and now `GEMINI_API_KEY` in plaintext; since the Gemini key was shared in chat, recommend rotating it in Google AI Studio after wiring.
- Verify final `git grep` for the API key / IMGBBB returns nothing tracked.

---

## Validation
- `python -c "import ast; ast.parse(open(f).read())"` on all `.py` (syntax).
- Dry-run locator loader on a sample to confirm attribute + vision parsing.
- Confirm no direct `page.get_by_*`/`page.locator` remains in `clear_*.py` (grep).
- Confirm `error/` screenshot path logic and onlyfiles call.
- `git grep -n "IMGBBB\|AQ.Ab8RN6"` -> no matches in tracked files.

## Open items requiring user action
- Set `GEMINI_API_KEY` as a GitHub Actions repository secret.
- Rotate the Gemini key if it should not remain in chat history.