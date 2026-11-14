import re
from pathlib import Path

from .config import ROOT

VISION_MARKER = "# vision:"


def split_vision(line):
    idx = line.find(VISION_MARKER)
    if idx == -1:
        return line.strip(), None
    expr_part = line[:idx].strip()
    desc = line[idx + len(VISION_MARKER):].strip()
    return expr_part, (desc or None)


def split_assignment(expr_part):
    if "=" not in expr_part:
        raise ValueError(f"Invalid locator line (missing '='): {expr_part!r}")
    name, expr = expr_part.split("=", 1)
    return name.strip(), expr.strip()


def iter_locator_lines(path):
    """Yield (name, expr, vision) for each locator line in the file, in order."""
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            expr_part, vision = split_vision(s)
            name, expr = split_assignment(expr_part)
            yield name, expr, vision


class Locators:
    def __init__(self, platform, chains, raw, vision):
        self._platform = platform
        self._chains = chains
        self._raw = raw
        self._vision = vision

    @property
    def platform(self):
        return self._platform

    def __getattr__(self, name):
        chains = self.__dict__["_chains"]
        if name in chains:
            return chains[name][0]
        raise AttributeError(name)

    def chain(self, name):
        return self._chains.get(name, [])

    def fallbacks(self, name):
        return self._chains.get(name, [])[1:]

    def vision(self, name):
        return self._vision.get(name, name.replace("_", " "))

    def raw(self, name):
        return self._raw.get(name)

    def names(self):
        return list(self._chains.keys())


def load_locators(txt_path, page, extra_namespace=None):
    path = Path(txt_path)
    if not path.is_absolute():
        path = ROOT / path

    platform = path.name.split("_locators")[0]

    namespace = {"page": page, "re": re}
    if extra_namespace:
        namespace.update(extra_namespace)

    chains = {}
    raw = {}
    vision = {}

    for name, expr, vdesc in iter_locator_lines(path):
        code = compile(f"{name} = {expr}", str(path), "exec")
        exec(code, namespace)

        locator = namespace[name]
        chains.setdefault(name, []).append(locator)

        if name not in raw:
            raw[name] = expr
        if vdesc and name not in vision:
            vision[name] = vdesc

    return Locators(platform, chains, raw, vision)