"""Which settings a tile customizes, and what it would use otherwise (#1350).

A tile is CUSTOMIZED when its tile cfg (``Ortho4XP_+XX+YYY.cfg``) carries a
setting whose value differs from what the tile would inherit: the global
config file, else the registry default.  Both apps show this answer — the
map badge, the tile pane's "Custom settings" section — and neither computes
it: the Qt app calls :func:`tile_customizations` in process, the Mac app
through the engine's ``tile_customizations`` command.

The rule is the settings model's, never a second one: the tile cfg is read
through :func:`O4_Settings_Model.read_tile_raw` (an unstamped pre-1.0.352
file is retired exactly as the build would retire it), the inherited value
is :func:`O4_Settings_Model.global_effective_value`, and two values are one
when :func:`O4_Settings_Model.values_equivalent` says so (``25000`` and
``25000.0``, a legacy ``True`` for a mode setting).

NOT customizations: the imagery source, the zoom level and the zone list
(``O4_Settings_Model._TILE_PRESERVED``).  The Build box sets the first two
on every build; the zones are drawn on the map, not set in Settings.

``affects_output`` marks a setting the terrain steps read (the ground
shape, the airport grading, the water masks): changing it reruns those
steps.  The list is the step-reuse inputs (``O4_Step_Reuse``'s per-step
settings), not a hand-kept copy.  A texture-only setting is ``False``.

Nothing a build step imports may import this module: ``O4_Step_Reuse``
and ``O4_Settings_Model`` are in the auto-patch code closure, so they are
READ here, never edited for this feature (an edit there stales every
airport patch).
"""

from __future__ import annotations

import O4_Cfg_Vars
import O4_Settings_Model as SM
import O4_Step_Reuse

__all__ = ["tile_customizations", "customized_tiles", "display_value",
           "row_text", "row_tooltip", "GROUND_MARK"]


def display_value(name: str, value: str) -> str:
    """*value* as the settings window shows it: ``On``/``Off`` for a
    switch, the menu title for a labelled choice, else the value."""
    try:
        ok, normalized, _ = SM.coerce(name, value)
    except KeyError:
        return value
    if not ok:
        return value
    spec = O4_Cfg_Vars.cfg_vars.get(name) or {}
    if spec.get("type") is bool:
        return "On" if normalized == "True" else "Off"
    try:
        return SM.get_setting(name).label_for(normalized)
    except KeyError:
        return normalized


def _ground_settings() -> frozenset:
    """The tile settings any reusable step reads (vector, mesh, masks)."""
    tile_vars = set(O4_Cfg_Vars.list_tile_vars)
    return frozenset(
        name for step in O4_Step_Reuse.REUSABLE_STEPS
        for name in O4_Step_Reuse._step_settings(step) if name in tile_vars)


def _label(name: str) -> str:
    try:
        return SM.get_setting(name).label
    except KeyError:
        return name


def _working_dir(working_dir: str) -> str:
    """The tiles' folder as ``FNAMES.build_dir`` reads it: '' stays the
    default ``Tiles`` folder, a folder gets the trailing separator that
    means "one sub-folder per tile"."""
    if working_dir and not working_dir.endswith(("/", "\\")):
        return working_dir + "/"
    return working_dir or ""


def _rows(lat: int, lon: int, custom_build_dir: str,
          global_cfg: dict | None) -> list:
    tile_raw = SM.read_tile_raw(lat, lon, custom_build_dir) or {}
    if not tile_raw:
        return []
    if global_cfg is None:
        global_cfg = SM.read_global_raw()
    ground = _ground_settings()
    rows = []
    for name in O4_Cfg_Vars.list_tile_vars:
        if name in SM._TILE_PRESERVED or name not in tile_raw:
            continue
        tile_value = tile_raw[name]
        inherited = SM.global_effective_value(name, global_cfg)
        if SM.values_equivalent(name, tile_value, inherited):
            continue
        rows.append({
            "key": name,
            "label": _label(name),
            "tile_value": tile_value,
            "default_value": inherited,
            "tile_text": display_value(name, tile_value),
            "default_text": display_value(name, inherited),
            "affects_output": name in ground,
        })
    return rows


def tile_customizations(lat, lon, working_dir: str = "") -> dict:
    """The tile's customized settings, in registry order.

    :param working_dir: the folder holding the tile folders ('' = the
        default ``Tiles`` folder).
    :returns: ``{"lat", "lon", "customizations": [row, ...]}``, each row
        ``{key, label, tile_value, default_value, tile_text, default_text,
        affects_output}``; an empty list when the tile customizes nothing
        (or has no cfg at all).  ``default_value`` is what the tile would
        use without its override: the global config, else the default.
    """
    lat, lon = int(lat), int(lon)
    rows = _rows(lat, lon, _working_dir(working_dir), None)
    return {"lat": lat, "lon": lon, "customizations": rows}


def customized_tiles(tiles, working_dir: str = "") -> set:
    """The tiles of *tiles* (``(lat, lon)`` pairs) that customize at
    least one setting: the map badge set.  The global config is read once
    for the whole set."""
    custom_build_dir = _working_dir(working_dir)
    global_cfg = SM.read_global_raw()
    return {
        (int(lat), int(lon)) for (lat, lon) in tiles
        if _rows(int(lat), int(lon), custom_build_dir, global_cfg)
    }


#: Marks a row whose setting the terrain steps read (``affects_output``).
GROUND_MARK = "◆"


def row_text(row: dict) -> str:
    """One row as the tile pane lists it: ``Label: 5 (default 4)`` (a
    question label loses its question mark), with
    :data:`GROUND_MARK` in front of a setting that reshapes the terrain.
    ``BuildPane.swift`` (``customSettingText``) words it the same."""
    text = "%s: %s (default %s)" % (
        row["label"].rstrip("?"), row["tile_text"], row["default_text"])
    return GROUND_MARK + " " + text if row.get("affects_output") else text


def row_tooltip(row: dict) -> str:
    """The row's hover text: the cfg name, and what changing it reruns."""
    tip = row["key"]
    if row.get("affects_output"):
        tip += (" — changes the ground shape, airport grading or water: "
                "the terrain steps run again on the next build")
    return tip
