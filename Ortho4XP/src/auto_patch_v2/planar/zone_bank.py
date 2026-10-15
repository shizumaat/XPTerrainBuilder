"""THE ZONE BANK — where a graded zone meets raw terrain it ties in on a
1:3 bank (owner RULINGS 2026-10-15c (3) "1:3 bank").

The zone faces are LAW surfaces (the lip, the band, the end corridor) with
no DEM term, and their outer ring is the patch edge: beyond it the mesh is
the DEM.  Where the band stands over or under that DEM the edge was a bare
step (lawful since 2026-08-01) — at KBJC 12L a 7.2 m wall in 5 m.  The
owner's law: a fill or cut over ``adjacent_ground.bank_foot_tol_m`` ties
in on ``emit.design.bank_slope`` instead; under it the step stays.

The bank must be IN THE MAP before the solve sets the band's level, so its
width is ESTIMATED here from the DEM (master's ruling on the spec's Q2 (a)):
along each zone's outer ring, at a station every ``_STEP_M``,

    Δ̂ = clamp(DEM(p), z_e − f_max(d), z_e − f_min(d)) − DEM(p)

with ``z_e`` the DEM at the nearest pavement point, ``d`` the distance to
it and ``f`` the zone class's own corridor (``tables.zone_bounds``): the
band, pulled to its DEM inside its corridor, stands at the clamp.  The
pavement stands off its DEM by up to a metre or two, which the estimate
cannot see, so a station whose estimate is over the tolerance banks
``(|Δ̂| +
adjacent_ground.bank_estimate_margin_m) / bank_slope`` wide (``bank_min_width_m``
at least, ``adjacent_ground.bank_cap_width_m`` at most; a capped station
is COUNTED in the report).  The solve places the toe inside it
(``constraints/zone_bank``: the 1:3 cone from the zone ring, the DEM pull
on the bank's ground).

No bank is minted where the region was ENDED by the terrain edge (10b/10c:
"beyond the edge there is no bank" — the DEM's own slope is the bank), on
the coast, or on ground any other region already claims.  The bank face is
``graded_strip`` under the ref ``zone_bank:<zone ref>`` — never an
``adjacent_ground:`` ref, so no zone class and no zone-ref reader takes it
for a band."""
from __future__ import annotations

import dataclasses as _dc
import math

import shapely
from shapely.geometry import LineString, Point, Polygon  # noqa: F401
from shapely.ops import nearest_points, unary_union

from ..law import Law
from ..law.tables import snap_margin_m, zone_bounds
from ..model.planar import ZONE_BANK_REF_PREFIX, is_zone_bank_ref  # noqa: F401

__all__ = ["BANK_REF_PREFIX", "BankReport", "LAST", "zone_banks", "is_zone_bank_ref"]

#: The bank face's ref prefix (``zone_bank:<zone ref>``; ``model.planar``).
BANK_REF_PREFIX = ZONE_BANK_REF_PREFIX
#: The station spacing along a zone's outer ring (m) — the width estimate's
#: sampling, not a law value.
_STEP_M = 10.0


#: The last call's report (the build log prints it; lanes read it).
LAST: list = []


@_dc.dataclass
class BankReport:
    """What the bank minted, for the build log and the lane measurements."""

    banks: int = 0
    area_m2: float = 0.0
    stations: int = 0
    banked: int = 0
    capped: int = 0
    max_step_m: float = 0.0

    def line(self) -> str:
        return (f"zone banks (15c (3)): {self.banks} bank(s), {self.area_m2:.0f} m2, "
                f"{self.banked}/{self.stations} ring station(s) banked, "
                f"{self.capped} at the cap, estimated step max {self.max_step_m:.2f} m")


def _estimate(p: Point, pavement, dem, law: Law, role: str, cn, cl) -> float:
    """Δ̂ at ring point ``p`` (module docstring); 0.0 off the DEM."""
    foot = nearest_points(pavement, p)[0]
    d = foot.distance(p)
    try:
        z_dem = float(dem.z(p.x, p.y))
        z_e = float(dem.z(foot.x, foot.y))
    except Exception:                                    # pragma: no cover
        return 0.0
    if not (math.isfinite(z_dem) and math.isfinite(z_e)):
        return 0.0
    # the corridor accumulated over the TRUE distance (``half_m=d``): an end
    # band's ring stands far past the lateral half-width, and its fall is
    # read on the same slopes there (an estimate; the solve places the toe)
    lo, hi = zone_bounds(law, role, d, cn, cl, half_m=max(d, 0.0))
    lo = -1e9 if lo is None else lo
    hi = 1e9 if hi is None else hi
    z_band = min(max(z_dem, z_e + lo), z_e + hi)
    return z_band - z_dem


def _minus(a, b):
    """``a − b``, robust: GEOS refuses some near-degenerate overlays (a
    coastline-trimmed zone, measured on the VMMC twin); the two are then
    reduced to their polygonal parts and differenced on the identity grid,
    and where even that fails no bank is minted there (never a wrong one)."""
    try:
        return a.difference(b)
    except shapely.errors.GEOSException:
        pass

    def poly(g):
        parts = [q for q in shapely.get_parts(shapely.make_valid(g))
                 if q.geom_type in ("Polygon", "MultiPolygon")]
        return unary_union(parts) if parts else Polygon()
    try:
        return shapely.difference(poly(a), poly(b), grid_size=1e-3)
    except shapely.errors.GEOSException:
        return Polygon()


def zone_banks(zones: list, claimed, pavement_by_class: dict, dem, law: Law,
               report: BankReport | None = None,
               cells_claimed=None) -> list[tuple[str, Polygon, object]]:
    """``[(bank ref, polygon, zone region)]`` — one bank per zone region
    that needs one (module docstring).  ``claimed`` is every region the
    bank may not take (cells with their stand-offs, every zone, keep-outs,
    water); ``cells_claimed`` the same WITHOUT the zones (what a zone's
    ring may abut besides another zone); ``pavement_by_class`` maps a zone's ``(family, code_number,
    code_letter)`` to its pavement union (the ``z_e`` foot)."""
    if report is None:
        report = BankReport()
    if cells_claimed is None:
        cells_claimed = claimed
    LAST.clear()
    LAST.append(report)
    if dem is None or not zones:
        return []
    slope = float(law.tables.emit.design.bank_slope)
    ag = law.tables.zones.adjacent_ground
    tol, cap = float(ag.bank_foot_tol_m), float(ag.bank_cap_width_m)
    margin = float(ag.bank_estimate_margin_m)
    wmin = float(law.tables.emit.design.bank_min_width_m)
    if slope <= 0.0 or cap <= 0.0:
        return []
    snap = snap_margin_m(law)
    out: list[tuple[str, Polygon, object]] = []
    taken = claimed
    from shapely.strtree import STRtree
    tree = STRtree([z.polygon for z in zones])
    for z in zones:
        if z.quay or z.natural_shore or z.polygon.is_empty:
            continue
        pav = pavement_by_class.get((z.family, z.code_number, z.code_letter))
        if pav is None or pav.is_empty:
            continue
        role = "runway" if z.family == "runway" else "junction"
        # the FREE ring: the region's exterior where no other region abuts
        # it and no terrain edge ended it
        ends = unary_union(list(z.edge_lines)).buffer(snap) if z.edge_lines else None
        # what abuts it: the other zones, and every cell / keep-out / water
        # (``cells_claimed``) — read near this zone only
        near = z.polygon.buffer(2.0 * snap)
        others = [zones[i].polygon for i in tree.query(near)
                  if zones[i] is not z and zones[i].polygon.intersects(near)]
        others.append(cells_claimed.intersection(near))
        free = z.polygon.exterior.difference(unary_union(others).buffer(snap))
        if ends is not None:
            free = free.difference(ends)
        pieces = []
        for ln in shapely.get_parts(free):
            if ln.geom_type != "LineString" or ln.length < snap:
                continue
            n = max(1, int(math.ceil(ln.length / _STEP_M)))
            for k in range(n):
                a = ln.interpolate(k / n, normalized=True)
                b = ln.interpolate((k + 1) / n, normalized=True)
                mid = ln.interpolate((k + 0.5) / n, normalized=True)
                step = abs(_estimate(mid, pav, dem, law, role, z.code_number, z.code_letter))
                if report is not None:
                    report.stations += 1
                    report.max_step_m = max(report.max_step_m, step)
                if step <= tol:
                    continue            # under the foot tolerance the step stays
                w = (step + margin) / slope
                if w > cap and report is not None:
                    report.capped += 1
                w = min(max(w, wmin), cap)
                if report is not None:
                    report.banked += 1
                pieces.append(LineString([a, b]).buffer(w, cap_style="round"))
        if not pieces:
            continue
        bank = _minus(_minus(unary_union(pieces), taken), z.polygon)
        # OPENED and simplified: the union of the station buffers leaves
        # slivers and near-parallel spurs the census reads as hairlines
        # (measured KBJC replay: 741 bank|bank hairline pairs); what is
        # narrower than the narrowest bank is no bank
        o = 0.5 * wmin
        bank = _minus(_minus(bank.buffer(-o, join_style="mitre").buffer(o, join_style="mitre")
                             .simplify(snap), taken), z.polygon)
        parts = [g for g in shapely.get_parts(bank)
                 if g.geom_type == "Polygon" and g.area >= 1.0
                 and g.distance(z.polygon) <= snap]
        if not parts:
            continue
        geom = unary_union(parts)
        taken = unary_union([taken, geom])
        for k, g in enumerate(shapely.get_parts(geom)):
            if g.geom_type != "Polygon" or g.area < 1.0:
                continue
            out.append((f"{BANK_REF_PREFIX}{z.ref}#{k}", g, z))
            report.banks += 1
            report.area_m2 += float(g.area)
    print("    [planar] " + report.line())
    return out
