"""THE OBJECT PACK OF AN AIRPORT NO CUSTOM apt.dat DEFINES (#1630).

THE DEFECT (KPAE, the owner's sim read 2026-10-29).  The Seattle pack
``c_USA - 100_airport - KSEA Seattle Airports XP (DD)`` places 1,034
objects at KPAE in its ``+47-123`` DSF and excludes the stock ones there,
but its apt.dat defines only KSEA.  ``apt_dat.find_apt_dat`` found no
Custom Scenery apt.dat carrying KPAE, so the pack was Global Airports: the
patch read and seated Global's 1,523 stock placements, and the pack's own
objects — the ones X-Plane draws — were never read and floated.

THE RULE.  When the airport's block is Global Airports', an ENABLED Custom
Scenery pack that X-Plane draws ABOVE Global Airports
(``O4_Scenery_Packs.names_above_global_airports``) and whose DSF for the
airport's tile places at least one PACK-LOCAL object inside the airport's
boundary is the airport's OBJECT PACK — whether or not its apt.dat defines
the airport.  The first such pack in priority order wins.  The airport's
apt.dat block stays Global's (nothing else defines it); the DSF, the
objects, the pads and the seats are the object pack's.  ``pack.select_pack``
builds the selection — the ONE derivation site; this module only decides.

THE WITNESS IS THE COMPANION'S (``pack_local.admitted``): a ``.obj`` the
pack itself ships, anchored inside apt.dat row 130 (else the airport's
runways and pavements).  An overlay placing only library objects
(simHeaven, AEP, Ortho4XP overlays) is never an object pack.

THE DUMP IS MADE BEFORE THE BUILD, never here: :func:`candidates` names the
packs whose pristine DSF the pre-build refresh dumps
(``engine_v2.fresh_pack_dump``); :func:`find` reads only dumps already in
the mod cache, and a candidate without one is not chosen.
"""
from __future__ import annotations

import functools
import math
import os
import typing as _t

from . import apt_dat as _apt
from . import dsf as _dsf

__all__ = ["candidates", "find", "region_of"]


def candidates(xplane_root: str, lat: int, lon: int) -> list[str]:
    """The pack folders that could be an object pack for tile
    ``(lat, lon)``, highest priority first: enabled, drawn above Global
    Airports, a DSF for the tile, and objects of their own."""
    import O4_Scenery_Packs as _SP
    from .pack_local import ships_objects
    scenery = os.path.join(xplane_root, "Custom Scenery")
    if not os.path.isdir(scenery):
        return []
    out = []
    for name in _SP.names_above_global_airports(scenery):
        root = os.path.join(scenery, name)
        if os.path.isfile(_dsf.dsf_path_in_pack(root, lat, lon)) \
                and ships_objects(root):
            out.append(root)
    return out


def region_of(block: _t.Sequence[str], icao: str):
    """``(region, to_xy)``: the airport's boundary (row 130), else the
    union of its runways and pavements, in a metre frame at its reference
    point; ``(None, None)`` when the block carries neither."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from ..model.frame import Frame
    apt = _apt.parse_airport_block(list(block))
    to_xy = Frame(icao, apt.reference_point(), 9).transformers()[0]
    rings = [[to_xy(lo, la) for lo, la in b.rings[0]] for b in apt.boundaries if b.rings]
    if not rings:
        rings = [[to_xy(lo, la) for lo, la in p.rings[0]] for p in apt.pavements if p.rings]
        rings += [_runway_rect(rw, to_xy) for rw in apt.runways]
    parts = []
    for ring in rings:
        if len(ring) >= 3:
            poly = Polygon(ring)
            parts.append(poly if poly.is_valid else poly.buffer(0))
    if not parts:
        return None, None
    return unary_union(parts), to_xy


def _runway_rect(rw, to_xy) -> list[tuple[float, float]]:
    """A runway's rectangle in metres: its two ends ± half its width."""
    (ax, ay), (bx, by) = (to_xy(e[2], e[1]) for e in rw.ends)
    L = math.hypot(bx - ax, by - ay) or 1.0
    w = float(rw.width_m or 60.0) / 2.0
    nx, ny = -(by - ay) / L * w, (bx - ax) / L * w
    return [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]


def find(xplane_root: str, icao: str, apt_dat_path: str,
         mod_cache_root: str | None = None) -> str | None:
    """The airport's object pack folder (module doc), or ``None``.
    ``apt_dat_path`` is the Global Airports file serving ``icao``."""
    if mod_cache_root is None:
        import O4_File_Names as FNAMES
        mod_cache_root = FNAMES.airport_mod_cache_root()
    if not mod_cache_root or not apt_dat_path:
        return None
    block = _apt.read_airport_block(apt_dat_path, icao)
    if not block:
        return None
    lat0, lon0 = _apt.parse_airport_block(block).reference_point()
    lat, lon = math.floor(lat0), math.floor(lon0)
    dumps = []
    for root in candidates(xplane_root, lat, lon):
        dump = pristine_dump(mod_cache_root, root, lat, lon)
        if dump:
            dumps.append((root, dump, os.path.getmtime(dump)))
    if not dumps:
        return None
    return _first_placing(icao.upper(), tuple(block), tuple(dumps))


def pristine_dump(mod_cache_root: str, root: str, lat: int, lon: int) -> str | None:
    """The mod-cache text dump of ``root``'s PRISTINE tile DSF, or ``None``."""
    from .backup_state import classify_dsf      # dsf_write.pristine_dsf_path's rule
    pristine = classify_dsf(_dsf.dsf_path_in_pack(root, lat, lon)).read_path
    return _dsf.find_text_dump(mod_cache_root, os.path.basename(root), lat, lon,
                               dsf_path=pristine)


@functools.lru_cache(maxsize=64)
def _first_placing(icao: str, block: tuple[str, ...],
                   dumps: tuple[tuple[str, str, float], ...]) -> str | None:
    """The first ``root`` of ``dumps`` (``(root, dump, mtime)``) placing a
    pack-local object inside the airport; memoised on the dumps' mtimes."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    from .pack_local import admitted
    region, to_xy = region_of(block, icao)
    if region is None:
        return None
    region_p = prep(region)

    def inside(lo: float, la: float) -> bool:
        return region_p.contains(Point(*to_xy(lo, la)))

    for root, dump, _mtime in dumps:
        if admitted(_dsf.read_dump(dump, lambda _p: False), root, inside):
            return root
    return None
