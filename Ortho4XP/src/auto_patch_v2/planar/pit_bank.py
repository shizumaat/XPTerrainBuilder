"""A WALLED PIT'S OPEN EDGE TAKES A BANK (#1949 R3; spec
``sim-review/1949-R2.md`` §3; owner RULINGS 2026-11-16l: "retaining walls
should pretty much never be perfectly flush at the top ... plan for about a
1m of wall to rise above the high side ground").

Where a walled pit's wall stands lower than the ground behind it, the pit
states its rim on that OPEN EDGE (``airport/floor_rim.open_edge_tops``,
``ObjectFloor.rim_banks``): ``retaining_parapet_m`` under the wall's top,
eased from the DEM at the run's ends.  The ground behind must come down to
it, so each run of those rim samples mints ``graded_strip`` pieces under
``model/planar.PIT_BANK_PREFIX`` (a zone region's family, no zone class --
the form of ``planar/agp_ground``):

* ``pit_bank:<floor>:<run>#k`` -- outside the floor's void band (its outer
  ring is the bank's CREST, the rim vertices ``constraints/object_floor``
  pins), ``planar/bank_cut.bank_width`` of the run's largest rise (DEM over
  the crest) wide, its TOE pinned on the DEM (``constraints/fill_bank``).

Inside a gore both arms are crest and no toe is left: the solve grades the
island between them.  Each piece welds to the zone bands, yields to the
airside cells, and stands off every other cell, road ribbon and keep-out --
the pit's own cells and keep-out excepted (the bank meets them); a bank a
road ribbon cuts short is listed ``pit_bank_clipped`` with its grade.  No
airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
import shapely.prepared
from shapely.geometry import LineString, Point

from ..model.planar import PIT_BANK_PREFIX
from .bank_cut import bank_width, knives, pieces
from .stack_ground import _areal

__all__ = ["pit_bank_pieces", "banked_floors"]


def banked_floors(floors: _t.Sequence) -> list:
    """The floors that own their ground and state open-edge rims."""
    from ..airport.object_floor import owns_ground
    return [f for f in floors if getattr(f, "rim_banks", False) and f.rim_tops
            and owns_ground(f)]


def _runs(T: np.ndarray, step: float) -> list[np.ndarray]:
    """``T``'s rows (rim samples in ring order) split where two neighbours
    stand more than one and a half samples apart; the last run joins the
    first across the ring's start."""
    if not len(T):
        return []
    gap = np.hypot(*np.diff(T[:, :2], axis=0).T) > 1.5 * step
    runs = np.split(np.arange(len(T)), np.flatnonzero(gap) + 1)
    if len(runs) > 1 and np.hypot(*(T[0, :2] - T[-1, :2])) <= 1.5 * step:
        runs = [np.concatenate([runs[-1], runs[0]]), *runs[1:-1]]
    return runs


def pit_bank_pieces(floors: _t.Sequence, airport, taken: _t.Sequence, apart: _t.Sequence,
                    cut_m: float, hairline_m: float, vertex_m: float, law, airside=(),
                    ribbons: _t.Sequence = (), notes: "list | None" = None
                    ) -> list[tuple[str, _t.Any]]:
    """``(ref, polygon)`` per pit-bank piece (module doc): ``taken`` the
    zone bands (welded), ``apart`` every other cell / ribbon / keep-out
    (stood off by ``cut_m``), ``airside`` the airside cells, ``ribbons``
    the road ribbons (a bank they cut is listed); any of them inside a
    banked floor's void band is the pit's own and is met, not stood off."""
    from ..airport.dem import dem_z_many
    banked = banked_floors(floors)
    if not banked:
        return []
    ob = law.tables.structures.tunnel.object
    band, step = 0.5 * float(ob.wall_face_max_thickness_m), float(ob.wall_sample_m)
    outer = {f.id: f.footprint.buffer(band, join_style="mitre") for f in banked}
    own = shapely.union_all(list(outer.values()))
    mine = shapely.prepared.prep(own)

    def _not_own(gs) -> list:
        # inside a banked pit's void band everything is the pit's own (its
        # trench faces are airside; its keep-out, a frame's claim) and the
        # bank meets it; only what stands outside the band is stood off
        out = []
        for g in gs:
            if g is None or g.is_empty or not mine.intersects(g):
                out.append(g)
            elif not (rest := _areal(g.difference(own))).is_empty:
                out.append(rest)
        return out
    plan = []
    for f in banked:
        T = np.asarray(f.rim_tops, float)
        dem = getattr(airport, "dem", None)
        g = dem_z_many(dem, T[:, 0], T[:, 1]) if dem is not None else np.full(len(T), np.nan)
        crest = f.zero_z + T[:, 2]
        for k, r in enumerate(_runs(T, step)):
            rise = np.nanmax(g[r] - crest[r]) if np.isfinite(g[r]).any() else 0.0
            w = bank_width(max(0.0, float(rise)), law)
            axis = LineString(T[r, :2]) if len(r) > 1 else Point(T[r[0], :2])
            plan.append((f"{PIT_BANK_PREFIX}{f.id}:{k}", axis, w, float(rise)))
    reach = shapely.union_all([a.buffer(w) for _r, a, w, _z in plan])
    knife, rib = knives(reach, _not_own(taken), _not_own(apart), _not_own(airside),
                        _not_own(ribbons), cut_m, law)
    out: list[tuple[str, _t.Any]] = []
    claimed = own
    for base, axis, w, rise in plan:
        # round at the run's ends: the bank wraps a convex corner (a gore's
        # nose) and meets the rim just past the run, which eases to the DEM
        bank = axis.buffer(w, cap_style="round", join_style="mitre",
                           mitre_limit=2.0).difference(claimed)
        bank = _areal(bank)
        if bank.is_empty:
            continue
        claimed = claimed.union(bank)
        if notes is not None and not rib.is_empty and bank.intersects(rib):
            gap = float(axis.distance(rib))
            if gap < w:
                notes.append(f"pit_bank_clipped: {base} {gap:.1f} m wide against {w:.1f} m "
                             f"(rise {rise:.2f} m, grade {rise / max(gap, 0.1):.2f})")
        out.extend((f"{base}#{j}", q) for j, q in enumerate(pieces(bank, knife, hairline_m,
                                                                    vertex_m)))
    return out
