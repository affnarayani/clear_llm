import time

from .gemini_vision import gemini_click_and_record
from .locator_correction import reconcile_after_success

POLL_INTERVAL = 0.2


def _first_visible(locators, timeout_ms):
    """Poll all locators in parallel; return (index, locator) of the first visible one."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while True:
        for i, locator in enumerate(locators):
            try:
                if locator.is_visible():
                    return i, locator
            except Exception:
                pass
        if time.monotonic() >= deadline:
            return None, None
        time.sleep(POLL_INTERVAL)


def scroll_down(page, times=15, delay=0.25, stop_locator=None):
    """Press ArrowDown up to `times` times to scroll the focused area.
    Stops early if `stop_locator` becomes visible."""
    pressed = 0
    for _ in range(times):
        page.keyboard.press("ArrowDown")
        pressed += 1
        time.sleep(delay)
        if stop_locator is not None:
            try:
                if stop_locator.is_visible():
                    break
            except Exception:
                pass
    print(f"[SCROLL] Pressed ArrowDown {pressed} time(s)", flush=True)
    return pressed


def click_with_fallback(page, loc, name, timeout_ms=30000):
    chain = loc.chain(name)
    if not chain:
        raise AttributeError(name)

    description = loc.vision(name)
    index, target = _first_visible(chain, timeout_ms)
    if target is not None:
        target.click()
        reconcile_after_success(loc.platform, name, is_primary=(index == 0))
        return True

    print(f"[FALLBACK] No locator visible for '{name}', trying Gemini vision...", flush=True)
    return gemini_click_and_record(page, loc.platform, name, loc.raw(name), description)


def ensure_visible_with_fallback(page, loc, name):
    chain = loc.chain(name)
    if not chain:
        raise AttributeError(name)

    description = loc.vision(name)
    for locator in chain:
        try:
            locator.scroll_into_view_if_needed()
            return True
        except Exception as exc:
            print(f"[FALLBACK] Scroll failed ({description}): {exc}", flush=True)

    print(f"[FALLBACK] Scroll locators failed for '{name}', trying Gemini vision...", flush=True)
    return gemini_click_and_record(page, loc.platform, name, loc.raw(name), description)