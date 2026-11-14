from .config import ROOT, get_config
from .onlyfiles import upload_screenshot


def capture_error_screenshot(page, cfg=None):
    if cfg is None:
        cfg = get_config()

    shot_cfg = cfg["screenshot"]
    error_dir = ROOT / shot_cfg["dir"]
    error_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = error_dir / shot_cfg["filename"]

    try:
        page.screenshot(
            path=str(screenshot_path),
            full_page=shot_cfg.get("full_page", True),
        )
        print(f"[OK] Error screenshot captured: {screenshot_path}", flush=True)
        upload_screenshot(str(screenshot_path), cfg)
        return screenshot_path
    except Exception as screenshot_err:
        print(f"[WARNING] Could not capture or upload screenshot: {screenshot_err}", flush=True)
        return None