"""THE GENERATED STRUCTURES A PACKAGE CARRIES (#2140): each airport's
generated taxiway decks and road bridges (spec ``docs/specs/2123.md``) as
the portable record of ``auto_patch_v2.airport.generated_record`` -- the
deck OBJ8 files and their texture, their placement rows (the pack DSF's
``OBJECT_MSL`` rows), the road chains, the regions cut from the pack's
pages and apt.dat, the faked-cut placements hidden, and X-Plane's own art
as REFERENCES (never the files).

At save, the record is made from the airport's graded surface (its
``provenance.generated``) through the same ``generated_pack.recipe`` the
object stage runs, against the airport's pack and the X-Plane install the
tile's build reads.  It rides as the member ``generated/<tile>/<ICAO>.json``
and installs into the tile's patch folder as ``o4_generated_<ICAO>.json``,
where the receiving object stage uses it in place of the generator when its
own solve published the same structures (``generated_record.
installed_recipe``).  An airport with no generated structure, or one whose
record cannot be made (no graded surface, art outside the install), carries
none; a package is never refused for it.
"""
from __future__ import annotations

import json
import os

import O4_File_Names as FNAMES

__all__ = ["PREFIX", "members", "destination"]

#: The first folder of a generated-structure member.
PREFIX = "generated"


def _member_name(tile_key: str, icao: str) -> str:
    """``generated/<tile>/<ICAO>.json``."""
    return "%s/%s/%s.json" % (PREFIX, tile_key, str(icao).upper())


def _record(tile, icao: str) -> "tuple[dict, str] | None":
    """``(record, graded surface path)`` of ``icao`` in ``tile``, or
    ``None`` (module doc)."""
    from auto_patch.agp_reader import resolve_library_path
    from auto_patch_v2.airport import apt_flatten as _af
    from auto_patch_v2.airport import generated_pack as _gen
    from auto_patch_v2.airport import generated_record as _rec
    from auto_patch_v2.airport.deck_skin import install_root
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.rebake import graded_surface_path

    from . import key as _key
    path = graded_surface_path(FNAMES.patch_dir(tile.lat, tile.lon), icao)
    try:
        with open(path, encoding="utf-8") as fh:
            pub = (json.load(fh).get("provenance") or {}).get("generated") or {}
    except (OSError, ValueError):
        return None
    if not (pub.get("decks") or pub.get("road_bridges")):
        return None
    root = _key.pack_root(tile, icao)
    apt = _af.apt_dat_of(root) if root else ""
    rec = _gen.recipe(pub, apt, icao, Law.for_airport(icao),
                      resolve_library=resolve_library_path)
    doc = _rec.to_record(rec, pub, icao, install_root(apt))
    return (doc, path) if doc else None


def members(tile, airports) -> list:
    """``[(member name, bytes, mtime_ns)]``: the record of each airport of
    ``airports`` the tile generated structures for (module doc)."""
    import O4_UI_Utils as UI
    key = FNAMES.short_latlon(tile.lat, tile.lon)
    out = []
    for icao in sorted({str(a).upper() for a in airports or ()}):
        try:
            got = _record(tile, icao)
        except Exception as exc:                 # never fails the package
            UI.vprint(1, "  [package] %s: its generated decks / road bridges were "
                         "not recorded (%s)" % (icao, exc))
            continue
        if got is None:
            continue
        doc, source = got
        data = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")
        out.append((_member_name(key, icao), data, os.stat(source).st_mtime_ns))
    return out


def destination(parts) -> str:
    """Where the member split as ``parts`` (``["generated", tile,
    "ICAO.json"]``) lands: the installed record in the tile's patch folder.

    :raises ValueError: not a generated-structure member."""
    from auto_patch_v2.airport.generated_record import installed_path
    tile = FNAMES.parse_tile_key(parts[1]) if len(parts) == 3 else None
    icao = parts[2][: -len(".json")] if len(parts) == 3 and parts[2].endswith(".json") else ""
    if parts[0] != PREFIX or tile is None or not icao.isalnum():
        raise ValueError("package member %r is not a generated-structure record"
                         % "/".join(parts))
    return installed_path(FNAMES.patch_dir(*tile), icao)
