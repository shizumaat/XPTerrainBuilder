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
   cut it.  A taxi face never hosts (clause 1).  The host's own EDGE,
   clear of the mouth's cap, still stops the ramp (#1028 Q32: a ramp never
   crosses a pavement edge).

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

A SLID MOUTH CONTINUES THE ROAD'S OWN PROFILE (owner, issue #1028: "a
mouth that slides is placed where the road's own geometry reaches grade,
not just at the first point past the pavement").  The road leaves the
bore at the MAPPED portal's floor (its DEM less ``mouth_depth_m``, the
§33 (3) crest cap applied) and climbs along the approach at the design
``ramp_grade`` (:func:`road_profile`) — held at the bore's depth under
any pavement it passes beneath (a road under a taxiway keeps its cover).
The slid mouth's floor is that profile at the mouth — never a
fresh ``mouth_depth_m`` under the ground there, which dug a full-depth
trench where the road had already come up (measured EDDF: a motorway at
grade 104.5 m beyond the plateau's edge given a 7.5 m trench and a 168 m
ramp back up).  Where the profile REACHES GRADE before the mouth stands
clear of the pavement, the road surfaces under that pavement: no open
ramp stands beyond it and none is built — the DEM carries the road.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union
from shapely.strtree import STRtree

from ..airport.dem import dem_z_at
from ..law import Law
from ..law.tables import is_structure_role, is_value_role, role_family, role_side
from ..model.frame import rotated_rectangle

__all__ = ["mouth_stops", "clear_mouth", "mouth_at_pavement", "road_profile"]

#: Passes of the slide (each re-reads the stops from the new mouth).
_SLIDE_PASSES = 4
#: The road profile's sampling step along the approach (m): the ground's
#: fall at a plateau's edge is a few metres long.
_PROFILE_STEP_M = 1.0


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
    # the mouth's own end (its cap behind the mouth line, the first metres of
    # ramp): a host's edge there is where the ramp enters it, never a stop
    lead = min(axis.length, 2.0 * (half + rim_off))
    mouth_end = _extend_back(substring(axis, 0.0, lead), 2.0 * rim_off).buffer(
        half + 2.0 * rim_off + grid, cap_style="flat") if lead > 0.0 else mp.buffer(half + rim_off)
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
            # clause 3: the ramp's host — cut, but never crossed out of
            # (owner #1028 Q32: "never cross a pavement edge"): its edge,
            # clear of the mouth's own cap, stops the ramp's top
            edge = None if _own_road(axis, p, half + rim_off, grid) else \
                p.exterior.buffer(grid).difference(mouth_end)
            if edge is not None and not edge.is_empty:   # (the ramp's own road IS it)
                out.append((edge, f"{c.ref}#edge"))
            continue
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
    width = _narrow_width(poly)
    return width <= 2.0 * reach + grid and _runs_along(axis, poly, width, grid)


def _narrow_width(poly: Polygon) -> float:
    """The polygon's width: its rotated rectangle's short side (inf for a
    degenerate one)."""
    cs = list(rotated_rectangle(poly).exterior.coords)[:-1]
    if len(cs) < 4:
        return math.inf
    return min(math.dist(cs[i], cs[(i + 1) % 4]) for i in range(4))


def _runs_along(axis: LineString, poly: Polygon, width: float, grid: float) -> bool:
    """The axis runs ALONG ``poly`` — inside it for longer than it is wide:
    a ribbon the road follows, never one it passes under."""
    return axis.intersection(poly).length > width + grid


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


def road_profile(airport, law: Law, axis: LineString, portal: tuple[float, float],
                 inward: tuple[float, float], rim_off: float, spacing: float,
                 cover: _t.Sequence[Polygon] = ()):
    """THE ROAD'S OWN PROFILE out of a MAPPED portal (#1028; module doc):
    ``(z_p, s_g, floor_at)`` or ``None`` where the DEM carries no portal.

    ``z_p`` is the floor at the portal: the DEM at the rim's cap centre
    (``rim_off`` in front of the mouth line, as the build's datum reads
    it), crest-capped at the approach's ground + ``mouth_depth_m`` as §33
    (3) caps it, less ``mouth_depth_m``.  Out along ``axis`` the road
    climbs from it at ``ramp_grade`` — but WHERE THE AXIS PASSES UNDER
    PAVEMENT (``cover``, the stops the mouth slid out of, save a ribbon the
    axis runs along: the road's own paving) it keeps the
    bore's depth under that pavement's ground (the floor never rises above
    ``DEM − mouth_depth_m`` there): the slide never thins the cover over
    a road passing under a taxiway.  ``floor_at(s)`` is that profile;
    ``s_g`` the first station, out from under the pavement, where the
    ground has come down to it (``None`` within the slide cap plus the
    longest ramp)."""
    from .structure_approach import approach_ground
    tn = law.tables.structures.tunnel
    z = dem_z_at(airport, (portal[0] + inward[0] * rim_off, portal[1] + inward[1] * rim_off))
    if math.isnan(z):
        return None

    def fn(s: float) -> tuple[float, float]:
        q = axis.interpolate(min(s, axis.length))
        return (q.x, q.y)
    ground = approach_ground(airport, fn, tn.mouth_depth_m, spacing)
    if not math.isnan(ground):
        z = min(z, ground + tn.mouth_depth_m)          # §33 (3): an overbridge is no cover
    z_p = z - tn.mouth_depth_m
    # a ribbon the road runs ALONG is the road's own paving, never its cover
    cover = [p for p in cover if not _runs_along(axis, p, _narrow_width(p), _PROFILE_STEP_M)]
    tree = STRtree(cover) if cover else None
    step = min(spacing, _PROFILE_STEP_M)
    lim = min(axis.length, tn.mouth_slide_max_m + tn.max_ramp_length_m)
    floors, s_g, f, s = [z_p], None, z_p, step
    while s <= lim + 1e-9:
        q = Point(fn(s))
        d = dem_z_at(airport, (q.x, q.y))
        f += tn.ramp_grade * step
        under = tree is not None and len(tree.query(q, predicate="within")) > 0
        if under and not math.isnan(d):
            f = min(f, d - tn.mouth_depth_m)
        floors.append(f)
        if s_g is None and not under and not math.isnan(d) and d <= f:
            s_g = s
        s += step

    def floor_at(s: float) -> float:
        k = min(len(floors) - 1, max(0, int(round(s / step))))
        return floors[k]
    return z_p, s_g, floor_at


def mouth_at_pavement(group, axis: LineString, cells, polys, pads, law: Law,
                      cut_roles: _t.Collection[str], half: float, rim_off: float, gap: float,
                      spacing: float, grid: float, decked: _t.Sequence[Polygon],
                      airport=None, crossing: _t.Sequence[tuple[Polygon, str]] = ()):
    """THE ONE CALL ``structures.build_structures`` makes for a MAPPED
    bore's group: ``(axis, mouth, stops, tree, note, floor_z)`` with the
    axis starting at the mouth that stands clear of the pavement (the
    module doc); ``axis`` is ``None`` and ``note`` the refusal when no
    mouth on the approach does, or when the road reaches grade under the
    pavement.  ``floor_z`` is a SLID mouth's floor on the road's own
    profile, held under the pavement it slid out of (:func:`road_profile`;
    ``None`` for a mouth that did not slide, or without ``airport``): the
    caller's datum is never deeper.  ``decked`` are the corridor's own deck
    polygons (read on the mapped approach).  ``crossing`` are the mapped
    roads through the corridor (``structure_approach.crossing_roads``, #1028):
    stops like the pavement's — a road over the bore slides the mouth out of
    it, one across the approach trims the ramp's top.  ``stops`` / ``tree`` carry the building ``pads`` too
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
    total, refs, cover = 0.0, [], []
    for _pass in range(_SLIDE_PASSES):
        here = substring(axis, total, axis.length)
        mouth = here.coords[0] if total > 0.0 else group.mouth
        stops = mouth_stops(cells, polys, law, cut_roles, here, mouth, half, rim_off, decked,
                            grid) + list(crossing)
        s0, ref = clear_mouth(here, stops, half, rim_off, gap, spacing, grid,
                              lambda s, _t=total: ring_of(_t + s),
                              law.tables.structures.tunnel.mouth_slide_max_m - total)
        cover.extend(p for p, _r in stops)
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
            f"(#971: a mouth stops at the pavement, never cuts it)"), None
    if total <= 0.0:
        return axis, group.mouth, stops, tree, "", None
    at = ", ".join(dict.fromkeys(refs))
    prof = None if airport is None else road_profile(airport, law, axis, group.mouth,
                                                     group.inward, rim_off, spacing, cover)
    floor = None
    if prof is not None:
        z_p, s_g, floor_at = prof
        floor = floor_at(total)
        q = substring(axis, total, axis.length).coords[0]
        here = dem_z_at(airport, (q[0] + group.inward[0] * rim_off,
                                  q[1] + group.inward[1] * rim_off))
        if not math.isnan(here) and floor >= here:
            s_g = min(total, s_g if s_g is not None else total)   # surfaced at the mouth's cap
        if s_g is not None and s_g <= total + grid:
            return None, None, stops, tree, (
                f"the road reaches grade {s_g:.0f} m out along its approach (floor {z_p:.2f} at "
                f"the mapped portal, climbing at the design grade), before its mouth stands clear "
                f"of pavement {at} at {total:.1f} m: it surfaces under the pavement and no open "
                f"ramp stands beyond it (#1028)"), None
    new = substring(axis, total, axis.length)
    p = new.coords[0]
    return new, (p[0], p[1]), stops, tree, (
        f"mouth stops at pavement {at}: {total:.1f} m out along the approach from the mapped "
        f"portal (#971; the stretch between is covered bore"
        + ("" if floor is None else f", climbing on the road's own profile to floor {floor:.2f} "
           f"at the mouth, #1028") + ")"), floor
