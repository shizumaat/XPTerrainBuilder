"""Carry a changed registry default into global cfgs that stored the old one.

The engine writes EVERY default into the global cfg the first time it
runs (``O4_Config_Utils``), so raising a default in
:mod:`O4_Cfg_Vars` would never reach an existing user: their file holds
the old default as if they had chosen it.  This module rewrites such a
stored OLD default to the new one ONCE per file, and records that it
did in a sidecar register (``<cfg>.defaults``, one var name per line).
After that the var is never touched again in that file, so a value the
user sets by hand afterwards — the old default included — is kept.

A value that differs from the old default is the user's and is never
changed.  Tile cfgs are not migrated: they hold sparse overrides
(``O4_Settings_Model.write_tile``), i.e. values someone chose for that
tile.
"""

import os

import O4_Settings_Model as SETTINGS

#: var -> (old default as stored, new default).  Owner 2026-11-04:
#: masks_width 100 -> 500 to show the improved bathymetry and coastline.
CHANGED_DEFAULTS = {"masks_width": ("100", "500")}


def _register_path(cfg_path):
    return cfg_path + ".defaults"


def _read_register(cfg_path):
    try:
        with open(_register_path(cfg_path), encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except OSError:
        return set()


def migrate_changed_defaults(cfg_path):
    """Apply :data:`CHANGED_DEFAULTS` to the global cfg at *cfg_path*.

    :returns: INFO lines for the caller to print (possibly empty).
        Never raises: a cfg that cannot be rewritten keeps its value.
    """
    try:
        if not os.path.isfile(cfg_path):
            return []
        done = _read_register(cfg_path)
        pending = [v for v in CHANGED_DEFAULTS if v not in done]
        if not pending:
            return []
        data = SETTINGS._parse_cfg(cfg_path, strip_quotes=False)
        lines, changed = [], False
        for var in pending:
            old, new = CHANGED_DEFAULTS[var]
            if str(data.get(var, "")).strip() == old:
                data[var] = new
                changed = True
                lines.append("raised " + var + " from the old default "
                             + old + " to the new default " + new
                             + " in " + cfg_path)
        if changed:
            SETTINGS._write_atomic_with_backup(cfg_path, data)
        with open(_register_path(cfg_path), "a", encoding="utf-8",
                  newline="\n") as f:
            for var in pending:
                f.write(var + "\n")
        return lines
    except Exception:
        return []
