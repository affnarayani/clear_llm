import json
from pathlib import Path

from .config import ROOT, get_config
from .locator_loader import iter_locator_lines, split_assignment, split_vision

JSON_PATH = ROOT / "locators" / "changed_locators.json"


def txt_path_for(platform):
    return ROOT / "locators" / f"{platform}_locators.txt"


def load_entries():
    if not JSON_PATH.exists():
        return []
    try:
        with JSON_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_entries(entries):
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def find_entry(platform, name):
    for e in load_entries():
        if e.get("platform") == platform and e.get("name") == name:
            return e
    return None


def record_break(platform, name, broke_locator, suggested_locator):
    entries = load_entries()
    for e in entries:
        if e.get("platform") == platform and e.get("name") == name:
            e["broke_locator"] = broke_locator
            e["suggested_locator"] = suggested_locator
            save_entries(entries)
            return
    entries.append({
        "platform": platform,
        "name": name,
        "broke_locator": broke_locator,
        "suggested_locator": suggested_locator,
    })
    save_entries(entries)


def remove_entry(platform, name):
    entries = load_entries()
    new = [e for e in entries if not (e.get("platform") == platform and e.get("name") == name)]
    if len(new) != len(entries):
        save_entries(new)
        return True
    return False


def _txt_expressions(path):
    exprs = set()
    path = Path(path)
    if not path.exists():
        return exprs
    for _name, expr, _v in iter_locator_lines(path):
        exprs.add(expr)
    return exprs


def is_in_txt(path, expr):
    return expr in _txt_expressions(path)


def first_rhs(path, name):
    for n, expr, _v in iter_locator_lines(path):
        if n == name:
            return expr
    return None


def append_fallback(path, name, suggested_expr):
    path = Path(path)
    if not path.exists():
        return False

    lines = path.read_text(encoding="utf-8").splitlines()

    name_idxs = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            n, expr = split_assignment(split_vision(s)[0])
        except ValueError:
            continue
        if n == name:
            if expr == suggested_expr:
                return False
            name_idxs.append(i)

    if not name_idxs:
        return False

    insert_at = name_idxs[-1] + 1
    lines.insert(insert_at, f"{name} = {suggested_expr}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def reconcile_startup(platform, txt_path=None):
    cfg = get_config()
    auto = bool(cfg.get("auto_correct_locator", True))

    path = Path(txt_path) if txt_path else txt_path_for(platform)
    if not path.is_absolute():
        path = ROOT / path

    entries = load_entries()
    if not entries:
        return

    remaining = []
    changed = False

    for e in entries:
        if e.get("platform") != platform:
            remaining.append(e)
            continue

        suggested = e.get("suggested_locator")
        name = e.get("name")

        if auto:
            if suggested and name and not is_in_txt(path, suggested):
                append_fallback(path, name, suggested)
            changed = True
        else:
            if suggested and is_in_txt(path, suggested):
                changed = True
            else:
                remaining.append(e)

    if changed:
        save_entries(remaining)


def reconcile_after_success(platform, name, is_primary):
    entry = find_entry(platform, name)
    if not entry:
        return

    path = txt_path_for(platform)

    suggested = entry.get("suggested_locator")
    if suggested and is_in_txt(path, suggested):
        remove_entry(platform, name)
        return

    if is_primary:
        primary_raw = first_rhs(path, name)
        if primary_raw and entry.get("broke_locator") == primary_raw:
            remove_entry(platform, name)