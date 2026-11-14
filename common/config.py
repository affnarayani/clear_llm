import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv()

_CONFIG_CACHE = None


def get_config():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        config_path = ROOT / "json" / "config.json"
        with config_path.open("r", encoding="utf-8") as f:
            _CONFIG_CACHE = json.load(f)
    return _CONFIG_CACHE


def platform_config(platform):
    cfg = get_config()
    merged = dict(cfg)
    merged.update(cfg.get("platforms", {}).get(platform, {}))
    return merged