"""Settings presets: the three starting points a new user picks from (#822).

**Light on disk**, **Balanced** and **Sharper airports** each write the
SAME fixed set of keys (:data:`PRESET_KEYS`) with fixed values.  The Mac app
mirrors :data:`PRESETS` row for row in
``Sources/XPTerrainBuilder/SettingsPresets.swift``;
``tests/test_settings_presets.py`` fails when the two differ, when
Balanced stops equalling the registry defaults, or when a cost line's
figures stop matching their derivation (``docs/presets.md``).

Every key is an existing one: three engine config keys from
``O4_Cfg_Vars`` (written to the GLOBAL config, the defaults for new tiles)
and :data:`ZOOM_PREF`, the build-zoom preference the Build pane already
stores (Qt ``prefs["zl"]``, Mac ``@AppStorage("OrthoZoomLevel")``).  A
preset never changes a key's name or its stored value format.

Values are stored as the cfg literal ``O4_Settings_Model.coerce`` produces,
so a preset compares with the stored config through
``O4_Settings_Model.values_equivalent``.  When the current values match no
preset, the window shows :data:`CUSTOM_TITLE`.  A new user starts from
:data:`DEFAULT_PRESET` (Sharper airports, #937): the first-run screens apply
it; the engine's own defaults stay Balanced, so builds outside the apps
(the harness, the CLI) are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

import O4_Cfg_Vars
import O4_Settings_Model as SM

__all__ = [
    "Preset", "PRESETS", "PRESET_KEYS", "DEFAULT_PRESET", "ZOOM_PREF",
    "CUSTOM_TITLE", "SECTION_TITLE", "SECTION_NOTE",
    "SHARPER_AIRPORTS_EXTRA_GB", "RELATIVE_BUILD_TIME", "preset",
    "default_preset", "unset_in", "cfg_values", "zoom_value",
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
        "light_on_disk", "Light on disk",
        "ZL15 everywhere: coarser imagery, smaller downloads.",
        "About 0.4–0.8 GB of imagery per tile, a quarter of Balanced.",
        (("zl", "15"), ("cover_airports_with_highres", "False"),
         ("cover_zl", "18"), ("cover_extent", "1.0")),
    ),
    Preset(
        "balanced", "Balanced",
        "The standard settings: ZL16 everywhere.",
        "About 1.6–3.1 GB of imagery per tile.",
        (("zl", "16"), ("cover_airports_with_highres", "False"),
         ("cover_zl", "18"), ("cover_extent", "1.0")),
    ),
    Preset(
        "sharper_airports", "Sharper airports",
        "ZL16, and ZL18 imagery on and around airports with ICAO codes.",
        "About 1.6–3.1 GB per tile, plus the sharper airports.",
        (("zl", "16"), ("cover_airports_with_highres", "ICAO"),
         ("cover_zl", "18"), ("cover_extent", "1.0")),
    ),
)

#: The preset a new user starts from (owner, #937): the first-run screens
#: apply it unless the global config already sets a preset key.
DEFAULT_PRESET = "sharper_airports"

# MEASURED BY THE MASTER (no corpus in the lane that wrote this table).
#: Extra imagery GB per tile that Sharper airports adds; it depends on how
#: many airports a tile holds, so it is a measured range, e.g. (0.1, 0.5).
SHARPER_AIRPORTS_EXTRA_GB = None
#: Whole-tile build time relative to Balanced, per preset key, e.g.
#: {"balanced": 1.0, "sharper_airports": 1.1, "light_on_disk": 0.6}.
RELATIVE_BUILD_TIME: dict = {}


def default_preset() -> Preset:
    return preset(DEFAULT_PRESET)


def unset_in(global_raw: dict) -> bool:
    """Whether the global config sets none of the preset keys, so a new
    user gets :data:`DEFAULT_PRESET` (the zoom is a preference, not cfg)."""
    return not any(name in global_raw for name in PRESET_KEYS[1:])


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
