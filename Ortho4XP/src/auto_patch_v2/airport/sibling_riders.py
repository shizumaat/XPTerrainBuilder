"""A SIBLING PACK'S ROWS ON THE AIRPORT'S RE-SEATED DECKS MOVE WITH THEM
(issue #1252; owner 2026-10-22: "every other pack that is placing objects
... inside the airport area must be processed and reseated as well").

An airport can ship its parked cars in a pack of their own
(``KDFW_1_Parked_Cars``: 14,725 library cars on the ground, 218 more
``OBJECT_MSL`` on the garage decks of the airport pack).  The airport
pack's garages are re-seated by the placement plan; the cars on their
decks are not, and float or sink by the garage's move.

THE PACKS: enabled, not the serving pack, no apt.dat, a DSF for the tile,
and NO object of their own (``pack_local.tile_candidates`` less
``pack_local.ships_objects``: a pack that
ships objects inside the airport is a companion, re-seated by its own
plan — RULINGS 2026-10-28p (5)); and a DSF that places an object from an
elevation pool at all (``dsf_commands.places_elevated_objects``, read off
the command stream without a dump, ~1 s for 20 packs).

THE ROWS, all ``OBJECT_MSL`` (an on-ground row already follows the new
mesh, an ``OBJECT_AGL`` row is kept as authored, 14g (1)):

* standing on a re-seated frame's deck (``frame_riders.rider_seats``):
  written ``OBJECT_MSL`` at its authored height plus the frame's
  displacement;
* inside the airport boundary (apt.dat row 130 of the airport pack, else
  the hull of its pavements) and over NO object of the airport pack
  (``frame_riders.over_objects``): converted to on-ground, seated on the
  new ground like the airport pack's own rows under 11d (owner
  2026-11-04: "If cars (or other objects) from a secondary pack are not
  on top of/overlap with any other objects, then they should be seated
  on the new ground");
* anything else (over an object it does not stand on, or outside the
  boundary — an overlay's VFR object) stays as authored (28p (5)).

The write is the airport pack's own (``placement_write.apply_plan``: the
pristine DSF kept once as ``.anchor_bak``, the edit verified against the
re-dump, the record beside it), so a stopped build, an unpatched airport
and a rerun treat the sibling exactly as they treat the airport pack.
"""
from __future__ import annotations

import os
import typing as _t

from ..model.placement import Conversion, PlacementPlan, Provenance

__all__ = ["RIDER_KEY", "airport_region", "candidates", "sibling_plan"]

#: the plan JSON key of the ``k``-th sibling written for ``icao``
#: (``o4_v2_placement_<ICAO>~riders<k>.json``)
RIDER_KEY = "{icao}~riders{k}"


def _places_elevated(dsf_path: str) -> bool:
    """Does the DSF place any object from an elevation pool?  A file that
    cannot be read this way is read (``True``): the dump decides."""
    from O4_DSF_Header import dsf_bytes

    from .dsf_commands import places_elevated_objects
    verdict = places_elevated_objects(dsf_bytes(dsf_path))
    return verdict is not False


def candidates(main_root: str, lat: int, lon: int) -> list[str]:
    """The sibling packs of ``main_root`` on the tile (module doc)."""
    from . import dsf as _dsf
    from .dsf_write import pristine_dsf_path
    from .pack_local import ships_objects, tile_candidates
    return [r for r in tile_candidates(main_root, lat, lon) if not ships_objects(r)
            and _places_elevated(pristine_dsf_path(_dsf.dsf_path_in_pack(r, lat, lon)))]


def airport_region(pack_root: str, icao: str) -> _t.Any:
    """The airport's boundary as a ``(lon, lat)`` shapely geometry: the
    exteriors of its apt.dat row 130 in the airport pack, else the convex
    hull of its pavements; ``None`` with neither."""
    from shapely.geometry import MultiPoint, Polygon
    from shapely.ops import unary_union

    from .apt_dat import parse_airport_block, read_airport_block
    block = read_airport_block(os.path.join(pack_root, "Earth nav data", "apt.dat"),
                               icao)
    if not block:
        return None
    apt = parse_airport_block(block)
    rings = [b.rings[0] for b in apt.boundaries if b.rings and len(b.rings[0]) >= 3]
    if rings:
        return unary_union([Polygon(r).buffer(0) for r in rings])
    pts = [p for pv in apt.pavements for ring in pv.rings[:1] for p in ring]
    return MultiPoint(pts).convex_hull if len(pts) >= 3 else None


def sibling_plan(main: PlacementPlan, frames: _t.Sequence[_t.Any], root: str,
                 dump: _t.Any, dsf_path: str, contact_m: float,
                 region: _t.Any = None,
                 over: "_t.Callable[[float, float], bool] | None" = None
                 ) -> PlacementPlan:
    """The sibling's plan (module doc): its deck riders' row seats, and —
    with a ``region`` and an ``over`` test — the on-ground conversions of
    its free ``OBJECT_MSL`` rows inside the airport."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    from ..model.placement import KIND_MSL
    from .frame_riders import rider_seats
    rows = list(getattr(dump, "placements", ()) or ())
    counts: dict[str, int] = {}
    seats = rider_seats(rows, range(len(rows)), frames, contact_m, counts)
    ridden = {m.index for m in seats}
    conversions = []
    if region is not None and over is not None:
        inside = prep(region)
        for i, p in enumerate(rows):
            if (p.kind == KIND_MSL and i not in ridden
                    and inside.contains(Point(float(p.lon), float(p.lat)))
                    and not over(float(p.lat), float(p.lon))):
                conversions.append(Conversion(i, p.def_path, p.lon, p.lat,
                                              p.heading_deg, p.kind,
                                              0.0 if p.elevation is None
                                              else float(p.elevation)))
    counts["msl_seats"] = len(seats)
    counts["free_rows_on_ground"] = len(conversions)
    return PlacementPlan(
        icao=main.icao, pack_name=os.path.basename(os.path.normpath(root)),
        pack_root=root, dsf_path=dsf_path,
        dsf_backup_path=dsf_path + ".anchor_bak",
        provenance=Provenance("", main.provenance.engine_version,
                              main.provenance.law_digest, counts),
        conversions=tuple(conversions), splits=(), kept=(), msl_seats=seats)
