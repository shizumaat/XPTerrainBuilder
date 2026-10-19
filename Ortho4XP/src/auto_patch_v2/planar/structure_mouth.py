"""A TUNNEL MOUTH STOPS AT THE PAVEMENT (owner 2026-10-19, issue #971) —
what ONE mapped bore's corridor must stand clear of, and where its mouth
stands so that it does.

The owner's rule, verbatim: "Tunnel mouths should always stop at the
pavement (or object if one is provided) when approach a road or taxiway,
never cut into the pavement.  The exception would be for tunnels entirely
within pavement in the airside areas, as they clearly need to cut
pavement, however they too should never cross a taxiway edge, the full
taxiway width must always stay graded unless we're fully cutting it out
for an object with a hard deck top."

Read as four clauses over the pavement faces near a MAPPED bore's mouth
(a pack-stated corridor — a wall object, a plate, a wall corridor — IS the
object the rule names, and keeps its building-pad stops alone):

1. **A taxiway face is never cut.**  Every taxi-family face stops the
   corridor, the one the mouth stands on included — §34 (12) (3)'s "the
   portal's own pavement" exemption no longer reaches it.  The corridor's
   own DECK (an underpass, §34 (5)) is not a cut and stays exempt.
2. **Pavement over the bore is not cut either.**  A road or apron face
   over the bore, and an apron the mouth stands on, stops the corridor:
   the mouth stops at its edge (since clause 4 every road but the ramp's
   own is a stop, so the road half of this clause needs no test of its
   own).  Every other airside face stops the corridor as §34 (12) (3)
   always had it.
3. **Unless the tunnel lies within it.**  A road or apron face the axis
   runs INSIDE from the mouth for at least the shortest lawful ramp
   (``mouth_depth_m / ramp_max_grade``) HOSTS the ramp — the tunnel is
   "entirely within pavement" — and is cut, as 08-07 ruling 4 has always
   cut it.  A taxi face never hosts (clause 1).

4. **Nor the road or lot it runs beside** (owner RULINGS 2026-10-19o):
   every other road or parking face stops the corridor too, save the
   ramp's OWN road — a ribbon no wider than the corridor that the axis
   runs along (:func:`_own_road`), which the ramp is.  Clause 3 still comes first.

THE MOUTH STOPS AT THE EDGE, IT IS NOT REFUSED.  :func:`clear_mouth`
slides the mouth outward along the approach until the corridor's mouth
end (its rim cap and first spacing of ramp) stands ``wall_gap_m`` clear of
every stop, at most ``[tunnel] mouth_slide_max_m``; the stretch between
the mapped portal and the new mouth is
covered bore — it emits nothing and the pavement over it keeps its own
surface.  Beyond the mouth the station-truncation loop of
``structures.build_structures`` stops the ramp's TOP at the same set.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_structure_role, is_value_role, role_family, role_side
from ..model.frame import rotated_rectangle

__all__ = ["mouth_stops", "clear_mouth", "mouth_at_pavement"]

#: Passes of the slide (each re-reads the stops from the new mouth).
_SLIDE_PASSES = 4


def _host_run_m(axis: LineString, poly: Polygon, grid: float) -> float:
    """How far the axis runs INSIDE ``poly`` from the mouth (s = 0),
    contiguously, sampled every identity step."""
    near = poly.buffer(grid)
    s = 0.0
    while s <= axis.length and near.contains(axis.interpolate(s)):
        s += grid
    return s


def mouth_stops(cells, polys, law: Law, cut_roles: _t.Collection[str], axis: LineString,
                mouth: tuple[float, float], half: float, rim_off: float,
                decked: _t.Sequence[Polygon], grid: float) -> list[tuple[Polygon, str]]:
    """The pavement faces ONE mapped bore's corridor stops short of, as
    ``[(polygon, ref)]`` for ``structure_geometry.pad_hit`` (the module
    doc's four clauses; since clause 4 a road over the bore (clause 2) is
    a stop as every road but the ramp's own is).  ``cut_roles`` is §34
    (12) (3)'s airside set (``structure_service.airside_cut_roles``),
    ``decked`` the corridor's own deck polygons."""
    tn = law.tables.structures.tunnel
    keep = unary_union(list(decked)).buffer(grid) if decked else None
    min_run = tn.mouth_depth_m / tn.ramp_max_grade
    mp = Point(mouth)
    out: list[tuple[Polygon, str]] = []
    for p, c in zip(polys, cells):
        if c.kind == "structure" or c.role == "building" or not is_value_role(law, c.role) \
                or is_structure_role(law, c.role):
            continue
        if keep is not None and p.within(keep):
            continue                                  # its own deck (§34 (5))
        if role_family(law, c.role) == "taxi":
            out.append((p, c.ref))                    # clause 1
            continue
        airside = role_side(law, c.role) == "airside"
        at_mouth = p.distance(mp) <= grid
        if airside and not at_mouth:
            if c.role in cut_roles:
                out.append((p, c.ref))                # §34 (12) (3), unchanged
            continue
        if at_mouth and _host_run_m(axis, p, grid) >= min_run:
            continue                                  # clause 3: the ramp's host
        if not airside and _own_road(axis, p, half + rim_off, grid):
            continue                                  # clause 4: the ramp's own road
        out.append((p, c.ref))                        # clauses 2 and 4
    return out


def _own_road(axis: LineString, poly: Polygon, reach: float, grid: float) -> bool:
    """CLAUSE 4's test: ``poly`` is the road the ramp IS — a ribbon no
    wider than the corridor (``2 * reach``, its rim to rim) that the axis
    runs ALONG, inside it for longer than the ribbon is wide.  A road the
    axis crosses, or a lot / pack road polygon wider than the corridor, is
    pavement the ramp runs beside or through, and stops it."""
    mrr = rotated_rectangle(poly)
    cs = list(mrr.exterior.coords)[:-1]
    if len(cs) < 4:
        return False
    width = min(math.dist(cs[i], cs[(i + 1) % 4]) for i in range(4))
    return width <= 2.0 * reach + grid and axis.intersection(poly).length > width + grid


def clear_mouth(axis: LineString, stops: list[tuple[Polygon, str]], half: float,
                rim_off: float, gap: float, spacing: float, grid: float,
                ring_of: _t.Callable[[float], "Polygon | None"],
                max_slide: float = math.inf) -> tuple[float, str]:
    """``(s0, ref)``: the least station ``s0`` along ``axis`` at which the
    corridor's mouth end — its real ring over the first ``spacing``,
    ``ring_of(s0)`` — stands ``gap`` clear of every stop; ``ref`` the stop
    it slid out of (``""`` when the mapped mouth already stands clear).

    THE MOUTH SLIDES AT MOST ``max_slide`` (``[tunnel] mouth_slide_max_m``):
    past it ``s0`` is NaN with ``ref`` naming the stop still in the way.
    (Round 1 refused at the first stop the portal did not touch; owner
    RULINGS 2026-10-19o's roads beside the ramp made that refuse bores
    whose mouths stand among side roads, so the bound is a length.)
    The rectangle ``half + rim_off`` either side of the axis, ``rim_off``
    behind the mouth line, is a necessary test (the real ring is never
    narrower) and keeps the ring builder off every station it fails."""
    if not stops:
        return 0.0, ""
    tree = STRtree([p for p, _r in stops])

    def hits(probe) -> list[str]:
        return [stops[int(j)][1] for j in tree.query(probe.buffer(gap), predicate="intersects")
                if stops[int(j)][0].distance(probe) < gap - 1e-9]

    def box(s: float):
        seg = substring(axis, max(0.0, s - rim_off), min(axis.length, s + spacing))
        if s < rim_off:
            seg = _extend_back(seg, rim_off - s)     # the cap stands behind s = 0
        return seg.buffer(half + rim_off, cap_style="flat")

    ring0 = ring_of(0.0)
    at_portal = set(hits(ring0 if ring0 is not None else box(0.0)))
    if not at_portal:
        return 0.0, ""
    first = sorted(at_portal)[0]
    s = grid
    while s < axis.length - spacing:
        got = hits(box(s))
        if not got:
            ring = ring_of(s)
            got = hits(ring) if ring is not None else []
            if not got:
                return s, first
        if s > max_slide:
            return math.nan, got[0]
        s += grid
    return math.nan, first


def _extend_back(seg: LineString, by: float) -> LineString:
    """``seg`` with its first point pushed ``by`` back along its first edge."""
    (x0, y0), (x1, y1) = seg.coords[0], seg.coords[1]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    head = (x0 - (x1 - x0) / L * by, y0 - (y1 - y0) / L * by)
    return LineString([head, *seg.coords])


def mouth_at_pavement(group, axis: LineString, cells, polys, pads, law: Law,
                      cut_roles: _t.Collection[str], half: float, rim_off: float, gap: float,
                      spacing: float, grid: float, decked: _t.Sequence[Polygon]):
    """THE ONE CALL ``structures.build_structures`` makes for a MAPPED
    bore's group: ``(axis, mouth, stops, tree, note)`` with the axis
    starting at the mouth that stands clear of the pavement (the module
    doc); ``axis`` is ``None`` and ``note`` the refusal when no mouth on
    the approach does.  ``decked`` are the corridor's own deck polygons
    (read on the mapped approach).  ``stops`` / ``tree`` carry the building ``pads`` too
    (``ramp_crosses_pad``: a pad stops the ramp's top but never slides
    the mouth).

    A bore the aeroway bridge STATED (§34 (5), ``structure_underpass``) is
    governed too: its clip put the mouth INSIDE the taxi cell so the rim
    landed on it, and that is the cut into the taxiway the owner's rule
    forbids ("the full taxiway width must always stay graded") — the
    newer word; the mouth slides to the taxiway's edge like any other."""
    from .structure_approach import pavement_half_widths
    from .structure_geometry import ring_for
    def ring_of(s0: float):
        ln = substring(axis, s0, axis.length)

        def fn(s: float, _ln=ln):
            q = _ln.interpolate(min(s, _ln.length))
            return (q.x, q.y)
        ss = [0.0, min(spacing, ln.length)]
        # the WIDER of the lanes and a pavement trace, side by side, and the
        # edges snapped AWAY from the axis (``half_fn`` given): which stations
        # the built ramp's trace reads depends on its whole station set, so
        # the probe never stands narrower than the ring built from either
        hw, _refs = pavement_half_widths(fn, ss, cells, polys, law, half)

        def half_fn(s: float, _hw=hw) -> tuple[float, float]:
            a, b = _hw.get(s, (half, half))
            return (max(half, a), max(half, b))
        geom = ring_for(None, fn, ss, half, rim_off, group.inward, grid, group, half_fn)
        return None if geom is None else geom.outer

    # the stops are re-read from each new mouth (an apron the new mouth
    # stands in, a host that starts there) and the slide repeats until the
    # mouth stands clear of them too
    total, refs = 0.0, []
    for _pass in range(_SLIDE_PASSES):
        here = substring(axis, total, axis.length)
        mouth = here.coords[0] if total > 0.0 else group.mouth
        stops = mouth_stops(cells, polys, law, cut_roles, here, mouth, half, rim_off, decked,
                            grid)
        s0, ref = clear_mouth(here, stops, half, rim_off, gap, spacing, grid,
                              lambda s, _t=total: ring_of(_t + s),
                              law.tables.structures.tunnel.mouth_slide_max_m - total)
        if math.isnan(s0) or s0 <= 0.0:
            break
        total += s0
        refs.append(ref)
    stops = list(pads) + stops
    tree = STRtree([p for p, _r in stops]) if stops else None
    if math.isnan(s0) or s0 > 0.0:
        return None, None, stops, tree, (
            f"the mouth cannot stand clear of pavement {ref} within "
            f"{law.tables.structures.tunnel.mouth_slide_max_m:.0f} m of its mapped portal "
            f"(#971: a mouth stops at the pavement, never cuts it)")
    if total <= 0.0:
        return axis, group.mouth, stops, tree, ""
    new = substring(axis, total, axis.length)
    p = new.coords[0]
    return new, (p[0], p[1]), stops, tree, (
        f"mouth stops at pavement {', '.join(dict.fromkeys(refs))}: {total:.1f} m out along "
        f"the approach from the mapped portal (#971; the stretch between is covered bore)")
