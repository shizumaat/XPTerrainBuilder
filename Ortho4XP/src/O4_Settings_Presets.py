"""Settings presets: the three starting points a new user picks from (#822).

**Recommended**, **Sharper airports** and **Light on disk** each write the
SAME fixed set of keys (:data:`PRESET_KEYS`) with fixed values.  The Mac app
mirrors :data:`PRESETS` row for row in
``Sources/XPTerrainBuilder/SettingsPresets.swift``;
``tests/test_settings_presets.py`` fails when the two differ, when
Recommended stops equalling the shipped defaults, or when a cost line's
figures stop matching their derivation (``docs/presets.md``).

Every key is an existing one: four engine config keys from
``O4_Cfg_Vars`` (written to the GLOBAL config, the defaults for new tiles)
and :data:`ZOOM_PREF`, the build-zoom preference the Build pane already
stores (Qt ``prefs["zl"]``, Mac ``@AppStorage("OrthoZoomLevel")``).  A
preset never changes a key's name or its stored value format.

Values are stored as the cfg literal ``O4_Settings_Model.coerce`` produces,
so a preset compares with the stored config through
``O4_Settings_Model.values_equivalent``.  When the current values match no
preset, the window shows :data:`CUSTOM_TITLE`.
"""

from __future__ import annotations

from dataclasses import dataclass

import O4_Cfg_Vars
import O4_Settings_Model as SM

__all__ = [
    "Preset", "PRESETS", "PRESET_KEYS", "ZOOM_PREF", "CUSTOM_TITLE",
    "SECTION_TITLE", "SECTION_NOTE", "SHARPER_AIRPORTS_EXTRA_GB",
    "RELATIVE_BUILD_TIME", "preset", "cfg_values", "zoom_value",
    "default_zoom", "current_values", "matching_preset", "status_text",
]

#: The Build pane's zoom preference (Qt ``prefs["zl"]``; the Mac app keeps
#: the same value under ``@AppStorage("OrthoZoomLevel")``).
ZOOM_PREF = "zl"

#: The keys every preset writes, in display order.
PRESET_KEYS = (
    ZOOM_PREF,
    "cover_airports_with_highres",
    "cover_zl",
    "cover_extent",
    "cleaning_level",
)

#: The words around the cards (SettingsPresets.swift uses the same ones).
SECTION_TITLE = "Start from"
SECTION_NOTE = ("Sets the defaults for new tiles. "
                "Settings you change afterwards show as Custom.")
CUSTOM_TITLE = "Custom"


@dataclass(frozen=True)
class Preset:
    """One card: its key, title, one-line summary, cost line and values."""

    key: str
    title: str
    summary: str
    cost: str
    values: tuple  # ((name, cfg literal), ...) in PRESET_KEYS order

    def as_dict(self) -> dict:
        return dict(self.values)


# The cost lines are DERIVED, never measured here: the imagery texture bytes
# of one 1°x1° tile at the preset's detail level, for tiles between 60°S and
# 60°N (docs/presets.md gives the formula; the twin recomputes the figures).
PRESETS = (
    Preset(
        "recommended", "Recommended",
        "The settings the app ships with: Standard detail everywhere.",
        "About 1.6–3.1 GB of imagery per tile.",
        (("zl", "16"), ("cover_airports_with_highres", "False"),
         ("cover_zl", "18"), ("cover_extent", "1.0"),
         ("cleaning_level", "1")),
    ),
    Preset(
        "sharper_airports", "Sharper airports",
        "Standard detail, and Very sharp imagery on and around every airport.",
        "About 1.6–3.1 GB per tile, plus the sharper airports.",
        (("zl", "16"), ("cover_airports_with_highres", "True"),
         ("cover_zl", "18"), ("cover_extent", "1.0"),
         ("cleaning_level", "1")),
    ),
    Preset(
        "light_on_disk", "Light on disk",
        "Light detail, and fewer build files kept: a rebuild starts over.",
        "About 0.4–0.8 GB of imagery per tile, a quarter of Recommended.",
        (("zl", "15"), ("cover_airports_with_highres", "False"),
         ("cover_zl", "18"), ("cover_extent", "1.0"),
         ("cleaning_level", "2")),
    ),
)

# MEASURED BY THE MASTER (no corpus in the lane that wrote this table).
#: Extra imagery GB per tile that Sharper airports adds; it depends on how
#: many airports a tile holds, so it is a measured range, e.g. (0.1, 0.5).
SHARPER_AIRPORTS_EXTRA_GB = None
#: Whole-tile build time relative to Recommended, per preset key, e.g.
#: {"recommended": 1.0, "sharper_airports": 1.1, "light_on_disk": 0.6}.
RELATIVE_BUILD_TIME: dict = {}


def preset(key: str) -> Preset:
    for entry in PRESETS:
        if entry.key == key:
            return entry
    raise KeyError(key)


def cfg_values(entry: Preset) -> dict:
    """The engine config part of a preset (everything but the zoom)."""
    return {name: value for name, value in entry.values if name != ZOOM_PREF}


def zoom_value(entry: Preset) -> int:
    return int(entry.as_dict()[ZOOM_PREF])


def default_zoom() -> int:
    """The shipped build zoom: the registry's ``default_zl``."""
    return int(O4_Cfg_Vars.cfg_vars["default_zl"]["default"])


def current_values(global_values: dict, zoom) -> dict:
    """The preset keys' current values: the global effective config values
    (``global_values``, registry defaults where absent) plus the zoom."""
    current = {ZOOM_PREF: str(zoom)}
    for name in PRESET_KEYS[1:]:
        if name in global_values:
            current[name] = str(global_values[name])
        else:
            current[name] = SM.global_effective_value(name, {})
    return current


def _same(name: str, first: str, second: str) -> bool:
    if name == ZOOM_PREF:
        try:
            return int(float(first)) == int(float(second))
        except (TypeError, ValueError):
            return False
    return SM.values_equivalent(name, str(first), str(second))


def matching_preset(current: dict) -> Preset | None:
    """The preset whose every key equals ``current``, else ``None``
    (the window then shows Custom)."""
    for entry in PRESETS:
        if all(_same(name, current.get(name, ""), value)
               for name, value in entry.values):
            return entry
    return None


def status_text(current: dict) -> str:
    """``"Current: <title>"`` or ``"Current: Custom"``."""
    entry = matching_preset(current)
    return "Current: %s" % (entry.title if entry else CUSTOM_TITLE)
