"""The ``O4_`` gate table of ``auto_patch/config.py``, from source or as data.

``provenance.introspect_config_gates`` enumerates every env gate config.py
declares by parsing its SOURCE, so the inventory tracks the code with no
hand-kept list.  A frozen engine ships no ``.py``: the parse found nothing,
the ``o4_cfg`` digest recorded ``introspect:unavailable``, and a patch built
by the source engine (the Qt window run from a checkout) never matched one
built by the frozen engine (the Mac app), so every airport rebuilt when a
tile moved between them (#1321).

The freeze therefore writes the same parse as data —
``config_gates.json`` beside this module, ``{gate_name: in-source
default}`` — via :func:`write_freeze_gates`, called from both ``.spec``
files.  It is regenerated from source on every freeze and never committed or
hand-edited; ``tests/test_config_digest_frozen_parity.py`` holds the file to
a fresh source parse.

Stdlib only, no package-relative imports: the ``.spec`` files load this file
BY PATH (``runpy``) before PyInstaller runs.
"""
from __future__ import annotations

import json
import os
import re

__all__ = ["GATES_FILENAME", "parse_gate_defaults", "source_gate_defaults",
           "write_freeze_gates", "frozen_gate_defaults"]

GATES_FILENAME = "config_gates.json"

# Matches ``environ.get("O4_NAME", "default")`` regardless of the os alias
# (``_os`` / ``_os_early``) or an enclosing ``int(...)`` / ``float(...)`` cast.
# Only two-argument calls with a STRING default are captured; a bare
# ``environ.get("O4_X")`` (default None) is intentionally skipped.
_ENV_GATE_RE = re.compile(
    r"""environ\.get\(\s*["'](O4_[A-Za-z0-9_]+)["']\s*,\s*["']([^"']*)["']"""
)


def parse_gate_defaults(text: str) -> dict:
    """``{gate_name: in-source default}`` for config source ``text``."""
    defaults: dict = {}
    for match in _ENV_GATE_RE.finditer(text):
        # A gate can be referenced more than once; keep the first default seen
        # (they agree in practice) but never overwrite with a later duplicate.
        defaults.setdefault(match.group(1), match.group(2))
    return defaults


def source_gate_defaults(source_path: str) -> dict:
    """The parse of the config source at ``source_path``; ``{}`` when it
    cannot be read."""
    try:
        with open(source_path, "r", encoding="utf-8") as handle:
            return parse_gate_defaults(handle.read())
    except OSError:
        return {}


def write_freeze_gates(src_root: str, out_dir: str) -> str:
    """Parse ``src_root/auto_patch/config.py`` and write the table to
    ``out_dir/``:data:`GATES_FILENAME`; return that path.  RAISES
    ``SystemExit`` when the parse finds no gate: an engine frozen without
    the table would stamp ``introspect:unavailable`` and never reuse a
    patch built from source."""
    source = os.path.join(src_root, "auto_patch", "config.py")
    defaults = source_gate_defaults(source)
    if not defaults:
        raise SystemExit(
            f"ERROR: no O4_ gate parsed from {source!r} — refusing to freeze "
            "an engine whose patch config digest would not match the "
            "source engine's.")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, GATES_FILENAME)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(defaults, handle, indent=0, sort_keys=True)
        handle.write("\n")
    return path


def frozen_gate_defaults(directory: str | None = None) -> dict | None:
    """The table the freeze wrote beside this module (``directory/``
    :data:`GATES_FILENAME`), or ``None`` when it is absent or malformed (a
    checkout; an engine frozen by a spec that predates it)."""
    d = directory if directory is not None else os.path.dirname(
        os.path.abspath(__file__))
    try:
        with open(os.path.join(d, GATES_FILENAME), "r",
                  encoding="utf-8") as handle:
            table = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(table, dict) or not table or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in table.items()):
        return None
    return table
