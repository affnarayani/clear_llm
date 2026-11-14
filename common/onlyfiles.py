import requests

from .config import get_config


def upload_screenshot(screenshot_path, cfg=None):
    if cfg is None:
        cfg = get_config()

    onlyfiles = cfg["onlyfiles"]
    if not onlyfiles.get("enabled", True):
        return None

    with open(screenshot_path, "rb") as file:
        response = requests.post(
            onlyfiles["upload_url"],
            files={"file": file},
            data={"expire": onlyfiles["expire_seconds"]},
        )

    if response.status_code == 200:
        res_data = response.json()
        if res_data.get("status"):
            direct_url = res_data["data"]["file"]["url"]["full"]
            print(f"[OK] Screenshot uploaded (expires in 48h): {direct_url}", flush=True)
            return direct_url
        error_msg = res_data.get("error", {}).get("message", "Unknown error")
        print(f"[WARNING] Upload failed: {error_msg}", flush=True)
        return None

    print(f"[WARNING] Upload failed: {response.status_code}", flush=True)
    return None