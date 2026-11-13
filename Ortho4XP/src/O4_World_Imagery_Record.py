"""Which photo provider draws each tile of the World pack (#2018, spec
``docs/specs/auto-imagery-provider-spec-20261113.md`` §4).

The record of tile ``<tile>`` is ``<pack>/XPTerrainBuilder_imagery/<tile>.json``::

    {"provider": "FRorth", "zl": 16, "kind": "drape", "auto": true,
     "blend": {side: {"toward", "knots": [[t, b_r, b_g, b_b,
                                            gain_r, gain_g, gain_b], ...]}},
     "at": "..."}

(a first-round record's sides hold ``start``/``mid``/``end`` offsets;
``O4_Imagery_Provider_Blend.from_record`` reads both).

* :func:`write_staged` -- the drape writer puts it in the staging folder
  (``<staged>/XPTerrainBuilder_imagery.json``);
* :func:`carry` -- ``O4_World_Pack.swap_in`` carries it into the pack with
  the tile (one ``os.replace``; X-Plane never reads it);
* :func:`read` -- a tile's record; a tile with none (built before this,
  adopted, a full build) reads its provider and zoom from its DDS names
  (``<y>_<x>_<provider><zl>.dds``, :func:`from_textures`).

Standard library only, so it runs wherever ``O4_World_Pack`` does.  No
tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import json
import os
import re

__all__ = ["RECORD_DIR", "STAGED_NAME", "write_staged", "carry", "read",
           "from_folder"]

RECORD_DIR = "XPTerrainBuilder_imagery"
STAGED_NAME = "XPTerrainBuilder_imagery.json"
_DDS_RE = re.compile(r"^\d+_\d+_(.+?)(\d\d)\.dds$")


def _tile_name(lat: int, lon: int) -> str:
    return f"{int(lat):+03d}{int(lon):+04d}"


def record_path(pack: str, lat: int, lon: int) -> str:
    """Where the pack keeps tile (``lat``, ``lon``)'s record."""
    return os.path.join(pack, RECORD_DIR, _tile_name(lat, lon) + ".json")


def write_staged(staged: str, record: dict) -> str:
    """Write ``record`` into the staged tile folder; its path."""
    path = os.path.join(staged, STAGED_NAME)
    os.makedirs(staged, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, sort_keys=True)
    return path


def carry(staged: str, pack: str, lat: int, lon: int) -> bool:
    """Move the staged record (if any) to the pack's; True when moved."""
    src = os.path.join(staged, STAGED_NAME)
    if not os.path.isfile(src):
        return False
    dest = record_path(pack, lat, lon)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    partial = dest + ".partial"
    with contextlib.suppress(FileNotFoundError):
        os.remove(partial)
    with open(src, "rb") as handle, open(partial, "wb") as out:
        out.write(handle.read())
    os.replace(partial, dest)
    return True


def from_folder(folder: str) -> dict:
    """``{"provider", "zl", "derived": True}`` from the first DDS named
    ``<y>_<x>_<provider><zl>.dds`` in ``folder``; ``{}`` when there is
    none (also an adopted tile's own pack's ``textures``, #2048)."""
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                match = _DDS_RE.match(entry.name)
                if match:
                    return {"provider": match.group(1),
                            "zl": int(match.group(2)), "derived": True}
    except OSError:
        pass
    return {}


def from_textures(pack: str, lat: int, lon: int) -> dict:
    """:func:`from_folder` of the tile's textures folder in ``pack``."""
    return from_folder(os.path.join(pack, "textures", _tile_name(lat, lon)))


def read(pack: str, lat: int, lon: int) -> dict:
    """Tile (``lat``, ``lon``)'s record, else :func:`from_textures`."""
    try:
        with open(record_path(pack, lat, lon), encoding="utf-8") as handle:
            record = json.load(handle)
        if isinstance(record, dict) and record.get("provider"):
            return record
    except (OSError, ValueError):
        pass
    return from_textures(pack, lat, lon)
