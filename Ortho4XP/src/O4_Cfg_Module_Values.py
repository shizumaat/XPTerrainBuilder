"""The app settings that live in OTHER modules' globals (a ``cfg_vars``
entry with a ``"module"`` alias, ``O4_Cfg_Vars``): where each alias
lives, and the values ``O4_Config_Utils`` assigned them.

``O4_Config_Utils`` used to import every owning module only to ``exec``
``"IMG.http_timeout=…"`` into it — five import edges that put the tile
pipeline (``O4_Tile_Utils``, ``O4_Vector_Map``, …) in the code closure of
every module that reads the config (#836).  Now the config records each
value here (:func:`assign`) and sets it on the owning module when that
module is loaded; a module loaded LATER takes its values from here as the
last statement of its own source (:func:`pull`) — the same end state as
before, when the config imported it first and assigned after.

STDLIB ONLY, imports no engine module: every owning module imports this
one.
"""
from __future__ import annotations

import importlib
import sys
import typing as _t

__all__ = ["MODULES", "assign", "pull", "holder"]

#: The ``"module"`` alias a ``cfg_vars`` entry names -> the module whose
#: global holds that setting.
MODULES: dict[str, str] = {
    "UI": "O4_UI_Utils",
    "OSM": "O4_OSM_Utils",
    "DEM": "O4_DEM_Utils",
    "TILE": "O4_Tile_Utils",
    "IMG": "O4_Imagery_Utils",
    "OVL": "O4_Overlay_Utils",
}

#: ``{module name: {setting: value}}`` as the config last assigned them.
_VALUES: dict[str, dict[str, _t.Any]] = {}


def assign(alias: str, var: str, value: _t.Any) -> None:
    """Record ``value`` for setting ``var`` of the module ``alias`` names,
    and set it on that module now when it is loaded."""
    name = MODULES[alias]
    _VALUES.setdefault(name, {})[var] = value
    module = sys.modules.get(name)
    if module is not None:
        setattr(module, var, value)


def pull(module_name: str, namespace: dict) -> None:
    """Give a module being imported (``__name__``, ``globals()``) the
    values the config already assigned it; none when the config has not
    run."""
    namespace.update(_VALUES.get(module_name, {}))


def holder(alias: str):
    """The module object ``alias`` names (imported on demand) — what
    ``getattr(O4_Config_Utils, alias)`` answered when the config imported
    it."""
    return importlib.import_module(MODULES[alias])
