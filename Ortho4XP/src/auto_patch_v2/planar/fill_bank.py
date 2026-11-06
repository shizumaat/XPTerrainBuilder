"""THE FILL BANK: THE OLD-DEM FILL'S GROUND IS GRADED GROUND OF ITS OWN
(owner RULINGS 2026-11-06a (2), 2026-11-06b (4); #1915; spec
``docs/specs/old-dem-fill-spec.md`` §2 (3)).

Where the DEM is older than the airport, ``airport/old_dem_fill`` wraps the
airport's sampler in the fill: the embankment from the runway band's crest
and from each road terrace down to the DEM.  The zones stop at the crest
(the terrain edge and the end area read the built ground), so the bank
between the crest and the toe is left to nobody — and the core mesh, which
reads the raw DEM, would hang the strip's ring over the old valley.  So the
fill's FOOTPRINT is graded ground: one ``graded_strip`` piece per part of it
no other region holds, its ref under ``model/planar.FILL_BANK_PREFIX`` (a zone
region's family, no zone class — the zone law binds no foot to it, and the
census's adjacent-ground step, which prices a ring steeper than 1:3, does
not read the fill's own steep embankment).  Its vertices carry the ground
datum at the fill's level (the sampler's), its toe lies on the DEM, so the
patch meets the mesh there.

Each piece welds to the zone bands (their ring is the crest) and stands off
every cell, road ribbon and structure keep-out by the zones' groundside
stand-off, as a wall slope does (``planar/wall_slope``): a road's level is
its own law, and the road is held on its terrace by the same sampler.  The
water is never filled.  No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import shapely

from ..airport.old_dem_fill import fill_model_of
from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..model.planar import FILL_BANK_PREFIX

__all__ = ["fill_bank_pieces"]


def fill_bank_pieces(airport, taken: _t.Sequence, apart: _t.Sequence, cut_m: float,
                     hairline_m: float, vertex_m: float, water=None
                     ) -> list[tuple[str, _t.Any]]:
    """``(ref, polygon)`` per fill-bank piece (module docstring): the fill's
    footprint less ``taken`` (the zone bands, welded), less every polygon of
    ``apart`` grown by ``cut_m`` and less ``water``; each ring carries a
    vertex at least every ``vertex_m`` so the ground follows the fill
    between them.  ``[]`` without a fill."""
    model = fill_model_of(airport)
    if model is None or model.footprint is None or model.footprint.is_empty:
        return []
    zones = [g for g in taken if g is not None and not g.is_empty]
    cells = [g.buffer(cut_m, join_style="mitre", mitre_limit=2.0)
             for g in apart if g is not None and not g.is_empty]
    if water is not None and not water.is_empty:
        cells.append(water)
    g = fixed_difference(model.footprint, canonical_union(zones + cells))
    out: list[tuple[str, _t.Any]] = []
    for part in shapely.get_parts(g):
        if part.geom_type != "Polygon" or part.area < 1.0 or is_hairline(part, hairline_m):
            continue
        out.append((f"{FILL_BANK_PREFIX}{len(out)}", shapely.segmentize(part, vertex_m)))
    return out
