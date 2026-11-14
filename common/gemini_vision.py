import json
import os

from google import genai
from google.genai import types

from .config import get_config
from . import locator_correction

_client = None


def _get_client():
    global _client
    if _client is None:
        cfg = get_config()
        api_key_env = cfg.get("gemini", {}).get("api_key_env", "GEMINI_API_KEY")
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"{api_key_env} missing in environment variables.")
        _client = genai.Client(api_key=api_key)
    return _client


def _build_config():
    try:
        return types.GenerateContentConfig(
            temperature=0.0,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ),
        )
    except Exception:
        return types.GenerateContentConfig(temperature=0.0)


def _parse_json(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"found": False}
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return {"found": False}


def normalize_suggested(raw):
    """Wrap a raw CSS selector in page.locator(...). Skip selectors starting with '#'."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.startswith("#"):
        return None
    if s.startswith("page."):
        return s
    return "page.locator(" + json.dumps(s) + ")"


def gemini_locate(page, description):
    cfg = get_config()
    model = cfg.get("gemini", {}).get("model", "gemini-3.5-flash-lite")

    image_bytes = page.screenshot(full_page=False)
    client = _get_client()

    prompt = (
        "You are a UI automation assistant. Analyze this screenshot of a web page "
        f"and locate the UI element described as: '{description}'. "
        "Return ONLY a JSON object with this exact shape: "
        '{"found": true or false, "x": <integer>, "y": <integer>, '
        '"suggested_locator": "<raw CSS selector or empty string>"}. '
        "x and y are the pixel coordinates of the CENTER of the element, "
        "measured from the top-left corner of the image. "
        "suggested_locator must be a raw CSS selector string for that element "
        '(for example: button[type="submit"] or [data-testid="email-input"]). '
        'If the element is not visible, return {"found": false, "x": 0, "y": 0, "suggested_locator": ""}.'
    )

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            prompt,
        ],
        config=_build_config(),
    )

    return _parse_json(response.text or "")


def gemini_click_and_record(page, platform, name, broke_locator, description):
    data = gemini_locate(page, description)

    clicked = False
    if data.get("found") and "x" in data and "y" in data:
        try:
            x = int(data["x"])
            y = int(data["y"])
            print(f"[GEMINI] Clicking at ({x}, {y}) for '{description}'", flush=True)
            page.mouse.click(x, y)
            clicked = True
        except (TypeError, ValueError):
            print(f"[GEMINI] Invalid coordinates returned: {data}", flush=True)

    suggested_full = normalize_suggested(data.get("suggested_locator"))
    if suggested_full:
        print(f"[GEMINI] Suggested locator for '{name}': {suggested_full}", flush=True)
        locator_correction.record_break(platform, name, broke_locator, suggested_full)
    elif not clicked:
        print(f"[GEMINI] Element not found by vision: '{description}'", flush=True)

    return clicked