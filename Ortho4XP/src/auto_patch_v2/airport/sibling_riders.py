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

THE ROWS: only an ``OBJECT_MSL`` row standing on a re-seated frame's deck
(``frame_riders.rider_seats``) is changed, and it is written ``OBJECT_MSL`` at its
authored height plus the frame's displacement.  Every other row of the
pack stays as authored — an overlay is left alone (28p (5)): its on-ground
rows already follow the new mesh, and an ``OBJECT_MSL`` row on the open
ground has no witness of the ground its author saw.

The write is the airport pack's own (``placement_write.apply_plan``: the
pristine DSF kept once as ``.anchor_bak``, the edit verified against the
re-dump, the record beside it), so a stopped build, an unpatched airport
and a rerun treat the sibling exactly as they treat the airport pack.
"""
from __future__ import annotations

import os
import typing as _t

from ..model.placement import PlacementPlan, Provenance

__all__ = ["RIDER_KEY", "candidates", "sibling_plan"]

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


def sibling_plan(main: PlacementPlan, frames: _t.Sequence[_t.Any], root: str,
                 dump: _t.Any, dsf_path: str, contact_m: float) -> PlacementPlan:
    """The sibling's plan: its deck riders' row seats and nothing else."""
    from .frame_riders import rider_seats
    rows = list(getattr(dump, "placements", ()) or ())
    counts: dict[str, int] = {}
    seats = rider_seats(rows, range(len(rows)), frames, contact_m, counts)
    counts["msl_seats"] = len(seats)
    return PlacementPlan(
        icao=main.icao, pack_name=os.path.basename(os.path.normpath(root)),
        pack_root=root, dsf_path=dsf_path,
        dsf_backup_path=dsf_path + ".anchor_bak",
        provenance=Provenance("", main.provenance.engine_version,
                              main.provenance.law_digest, counts),
        conversions=(), splits=(), kept=(), msl_seats=seats)
