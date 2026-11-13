"""THE PACK-LOCAL OBJECT WITNESS: which placements of a pack's DSF are the
pack's OWN objects inside an airport — a ``.obj`` file the pack itself
ships, resolved inside its own folder.  An overlay that places only library
objects (``lib/...`` and other virtual paths another pack exports) owns
none.  Read by ``airport/companion`` (owner RULINGS 2026-10-28p (5)) and
``airport/object_pack`` (#1630): one witness, two rules.  The packs it is
asked of are :func:`tile_candidates` (``companion`` and ``sibling_riders``,
#1252).
"""
from __future__ import annotations

import os
import typing as _t

__all__ = ["ships_objects", "admitted", "tile_candidates"]


def _inside(path: str, root: str) -> bool:
    real = os.path.realpath(root)
    try:
        return os.path.commonpath([os.path.realpath(path), real]) == real
    except ValueError:
        return False


def ships_objects(root: str) -> bool:
    """Does the pack ship any ``.obj`` of its own (outside its DSFs)?  The
    cheap gate before a DSF is dumped: an overlay that places only
    library objects ships none and is never dumped."""
    for here, dirs, files in os.walk(root):
        if os.path.basename(here) == "Earth nav data":
            dirs[:] = []
            continue
        if any(f.lower().endswith(".obj") for f in files):
            return True
    return False


def admitted(dump, root: str, inside: _t.Callable[[float, float], bool],
             also: _t.Callable[[str, _t.Any], bool] | None = None
             ) -> list[tuple[int, _t.Any]]:
    """The rows of ``dump`` a pack owns at an airport: ``.obj`` placements whose
    resource is a file ``root`` ships and whose anchor ``(lon, lat)`` is
    ``inside`` the airport — or, failing that, for which ``also(path, row)``
    holds (#2063: a body authored far from its anchor)."""
    rows = []
    for i, pl in enumerate(dump.placements):
        if not pl.def_path.lower().endswith(".obj"):
            continue
        path = os.path.join(root, pl.def_path)
        if not (os.path.isfile(path) and _inside(path, root)):
            continue
        if inside(pl.lon, pl.lat) or (also is not None and also(path, pl)):
            rows.append((i, pl))
    return rows


def tile_candidates(main_root: str, lat: int, lon: int,
                    icao: str = "") -> list[str]:
    """The Custom Scenery packs beside ``main_root`` that could carry the
    airport's objects: enabled, not the serving pack, a DSF for the tile,
    and no apt.dat (a pack with one is an airport of its own).  In
    folder-name order.

    ``icao`` (#2063): a pack whose apt.dat defines OTHER airports only is
    a candidate too — the Seattle pack (apt.dat: KSEA) places parked aircraft
    of its own on KRNT's aprons, which KRNT's own pack serves; a pack
    whose apt.dat defines ``icao`` itself is a rival pack of the same
    airport and never is.  Which of its rows are this airport's, and not
    its own airports', is ``object_window.own_claim``'s question."""
    import O4_Scenery_Packs as _SP

    from .apt_dat import file_has_airport
    from .dsf import dsf_path_in_pack
    scenery = os.path.dirname(os.path.normpath(main_root))
    if os.path.basename(scenery) != "Custom Scenery" or not os.path.isdir(scenery):
        return []
    main = os.path.realpath(main_root)
    out = []
    for name in sorted(os.listdir(scenery)):
        root = os.path.join(scenery, name)
        if not os.path.isdir(root) or os.path.realpath(root) == main:
            continue
        apt = os.path.join(root, "Earth nav data", "apt.dat")
        if os.path.isfile(apt) and (not icao or file_has_airport(apt, icao)):
            continue
        if not os.path.isfile(dsf_path_in_pack(root, lat, lon)):
            continue
        if _SP.pack_enabled(root):
            out.append(root)
    return out
