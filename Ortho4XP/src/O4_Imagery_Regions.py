"""Imagery on demand, region by region (RULINGS 2026-11-10e (3)).

The user turns on demand on for whole regions — simHeaven's six X-World
regions ("Use the same regions that simheaven uses") — so a user tight on
space keeps placeholders only where they fly.  A tile outside the chosen
regions builds full imagery, as with on demand off.

* :data:`REGIONS` — ``(code, label)`` in Settings order.
* :func:`setting_name` — the app setting of one region
  (``imagery_on_demand_<code>``, a bool, on by default).
* :func:`region_of` — a 1° tile's region, read from the generated
  :mod:`O4_Imagery_Regions_Table` (``tools/gen_imagery_regions.py`` names
  the source).
* :func:`tile_on_demand` — the per-tile decision the placeholder mode
  reads: its region's switch.
* :func:`default_settings` — the switches a first run sets: the regions
  holding the user's built tiles, every region when there are none.
"""

from __future__ import annotations

import bisect

import O4_Imagery_Regions_Table as TABLE

__all__ = ["REGIONS", "SETTING_PREFIX", "default_settings", "region_of",
           "setting_name", "tile_on_demand"]

#: simHeaven's X-World regions, (code, label), in Settings order.
REGIONS = (
    ("europe", "Europe"),
    ("america", "America"),
    ("asia", "Asia"),
    ("africa", "Africa"),
    ("australia_oceania", "Australia-Oceania"),
    ("antarctica", "Antarctica"),
)
#: A region's setting is this prefix and its code.
SETTING_PREFIX = "imagery_on_demand_"

#: lat -> ([lon_from, ...], [code, ...]), parsed once from the table.
_RUNS = {
    lat: tuple(map(list, zip(*((int(lon), TABLE.REGIONS[letter])
                               for lon, letter in (run.split(":")
                                                   for run in row.split())),
                             strict=True)))
    for lat, row in TABLE.ROWS.items()
}


def setting_name(code: str) -> str:
    """The app setting that turns on demand on in region ``code``."""
    return SETTING_PREFIX + code


def region_of(lat: int, lon: int) -> str:
    """The region code of the 1° tile whose south-west corner is
    (``lat``, ``lon``); longitudes wrap, latitudes clamp."""
    lat = min(89, max(-90, int(lat)))
    lon = (int(lon) + 180) % 360 - 180
    starts, codes = _RUNS[lat]
    return codes[bisect.bisect_right(starts, lon) - 1]


def tile_on_demand(tile) -> bool:
    """Whether ``tile``'s region has on demand on: its region's setting
    as the tile carries it (on when the tile carries none)."""
    name = setting_name(region_of(tile.lat, tile.lon))
    return bool(getattr(tile, name, True))


def default_settings(tiles) -> dict:
    """``{setting: bool}`` for every region: on where one of ``tiles``
    (``(lat, lon)`` pairs, the user's built tiles) lies, or everywhere
    when ``tiles`` is empty."""
    held = {region_of(lat, lon) for lat, lon in tiles}
    return {setting_name(code): (not held or code in held)
            for code, _label in REGIONS}
