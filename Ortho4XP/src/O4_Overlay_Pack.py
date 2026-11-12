"""The app's overlay pack, ``yXPTerrainBuilder Overlays`` (#2021, RULINGS
2026-11-12e).

A FULL tile replaces X-Plane's base mesh for its square, and with it the
default scenery's roads, forests and buildings, which live in that same
DSF.  Every full tile the app builds or adopts therefore gets an overlay
DSF of that default content (``O4_Overlay_Utils.auto_overlay``), filed in
ONE Custom Scenery pack::

    <Custom Scenery>/yXPTerrainBuilder Overlays/Earth nav data/+50-070/+53-063.dsf

-- unless other installed scenery already supplies that content for the
tile (:func:`covering_pack`).  The pack is a real folder carrying
:data:`MARKER` (never a link), and its ``scenery_packs.ini`` row sits
directly above the World pack's, which stays the last row
(:func:`ini_install`; owner 2026-11-12T14:53Z).

Standard library plus ``O4_DSF_Header``, ``O4_Scenery_Packs`` and
``O4_World_Pack`` (all stdlib-only).  No pack of anyone else is named here.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

import O4_DSF_Header as DSFH
import O4_Scenery_Packs as SP
import O4_World_Pack as WP

__all__ = ["PACK_NAME", "MARKER", "dsf_path", "covering_pack", "has_row",
           "ini_install", "install"]

PACK_NAME = "yXPTerrainBuilder Overlays"
#: Written into the pack's root by :func:`install`: the app manages it.
MARKER = "XPTerrainBuilder_overlays.json"
#: Exclusion boxes are given in degrees; this much short of the tile's
#: edge still counts as the whole tile.
_EDGE_TOLERANCE_DEG = 1e-6


def dsf_path(scenery_dir: str, lat: int, lon: int) -> str:
    """Where the pack's overlay DSF of a tile lives."""
    return os.path.join(scenery_dir, PACK_NAME, WP.dsf_relpath(lat, lon))


def _network_excluded(pairs, lat: int, lon: int) -> bool:
    """Does a ``sim/exclude_net`` among DSF header ``pairs`` cover the
    whole tile (box ``west/south/east/north``)?

    A pack that replaces the default scenery of a tile -- its own roads,
    with buildings and forests along them -- excludes X-Plane's default
    road network over the whole tile.  A pack that adds an airport or a
    landmark excludes a few small boxes; one that replaces only the
    forests excludes forests (``sim/exclude_for``), and the tile still
    needs its roads and buildings."""
    for name, value in pairs:
        if name != "sim/exclude_net":
            continue
        try:
            west, south, east, north = (float(v) for v in value.split("/"))
        except ValueError:
            continue
        if (west <= lon + _EDGE_TOLERANCE_DEG
                and south <= lat + _EDGE_TOLERANCE_DEG
                and east >= lon + 1 - _EDGE_TOLERANCE_DEG
                and north >= lat + 1 - _EDGE_TOLERANCE_DEG):
            return True
    return False


def _why_covering(pairs, lat: int, lon: int,
                  default_agent: Optional[str]) -> Optional[str]:
    props = dict(pairs)
    if props.get("sim/overlay") != "1":
        return None
    if _network_excluded(pairs, lat, lon):
        return "replaces the default road network over the whole tile"
    if default_agent and props.get("sim/creation_agent") == default_agent:
        return "already holds the default scenery's roads, forests and buildings"
    return None


def covering_pack(scenery_dir: str, lat: int, lon: int,
                  default_agent: Optional[str] = None
                  ) -> Optional[tuple]:
    """``(pack, why)`` of the first enabled Custom Scenery pack, other
    than this one and the World pack, whose overlay DSF of the tile
    supplies the default scenery's roads, forests and buildings itself;
    ``None`` when no pack does.

    An overlay DSF of the tile (``sim/overlay 1``) covers it when

    * it excludes the default road network over the whole tile
      (:func:`_network_excluded`: the pack replaces the default
      content there), or
    * its ``sim/creation_agent`` is ``default_agent`` -- the agent of
      X-Plane's own DSF of the tile: it is that DSF's content, extracted
      (an overlay folder an earlier Ortho4XP wrote).

    An airport or landmark overlay does neither and covers nothing: the
    tile still gets its overlay.  A pack disabled in ``scenery_packs.ini``
    is not read.  One ``stat`` per pack; only a DSF that exists has its
    header read."""
    if not scenery_dir or not os.path.isdir(scenery_dir):
        return None
    disabled = SP.disabled_pack_names(scenery_dir)
    relative = WP.dsf_relpath(lat, lon)
    for entry in sorted(os.listdir(scenery_dir)):
        if entry in (PACK_NAME, WP.PACK_NAME) or entry in disabled:
            continue
        dsf = os.path.join(scenery_dir, entry, relative)
        if not os.path.isfile(dsf):
            continue
        why = _why_covering(DSFH.dsf_property_pairs(dsf) or [], lat, lon,
                            default_agent)
        if why:
            return entry, why
    return None


def _is_row(line: str, name: str) -> bool:
    return line.strip().rstrip("/").endswith("Custom Scenery/" + name)


def has_row(lines) -> bool:
    """Does ``scenery_packs.ini`` (its ``lines``) have the pack's row?"""
    return any(_is_row(line, PACK_NAME) for line in lines)


def ini_install(lines: list) -> bool:
    """File the pack's row into ``scenery_packs.ini`` lines (edited in
    place) directly ABOVE the World pack's row, the last row; at the end
    when the ini has no World row.  A row already there is enabled and
    moved.  ``False`` when a row was already there."""
    had = [i for i, line in enumerate(lines) if _is_row(line, PACK_NAME)]
    for i in reversed(had):
        del lines[i]
    world = [i for i, line in enumerate(lines) if _is_row(line, WP.PACK_NAME)]
    if world:
        lines.insert(world[0], "SCENERY_PACK Custom Scenery/%s/" % PACK_NAME)
    else:
        SP.insert_new_packs(lines, [PACK_NAME], lambda name: "bottom"
                            if name == PACK_NAME else None)
    return not had


def install(scenery_dir: str) -> dict:
    """Make the pack in Custom Scenery folder ``scenery_dir`` -- a real
    folder with :data:`MARKER` -- and file its ini row (:func:`ini_install`;
    the ini is rewritten only when the row was missing or out of place).
    ``ValueError`` when the name is taken by a link or a file: the pack is
    never a link.  ``{"pack", "ini_added"}``."""
    pack = os.path.join(scenery_dir, PACK_NAME)
    if os.path.islink(pack) or (os.path.exists(pack)
                                and not os.path.isdir(pack)):
        raise ValueError(f"{pack} is a link or a file, not a folder: the "
                         "overlay pack is never a link.")
    os.makedirs(os.path.join(pack, "Earth nav data"), exist_ok=True)
    marker = os.path.join(pack, MARKER)
    if not os.path.isfile(marker):
        with open(marker, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"version": 1, "installed_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, handle)
    ini = os.path.join(scenery_dir, SP.INI_FILENAME)
    lines, newline = SP.read_ini_lines(ini, missing_ok=True)
    before = list(lines)
    added = ini_install(lines)
    if lines != before:
        SP.write_ini_lines(ini, lines, newline)
    return {"pack": pack, "ini_added": added}
