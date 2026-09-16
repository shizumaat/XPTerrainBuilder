"""THE RAMP / RIM GEOMETRY of a tunnel structure (M4; split out of
``planar/structures.py`` for lane v2tunnelobj so that file stays under
its line budget).

THE MODEL (RULINGS 2026-09-06b (1), 2026-09-08a; law ``structures.toml
[cutout]``, ``emit_wall_band = false``): one corridor = a RAMP polygon (the
trench floor — for an object corridor the walls' inner faces ⊕
``floor_overlap_m``, for an OSM bore the carriageway), and an at-grade RIM
ring standing ``rim_off`` outside the ramp edge by station — for an object
corridor :func:`rim_standoff` of the wall's own measured thickness (the
rim INSIDE the outer face by ``rim_inset_fraction`` of it, never closer
to the floor ring than the identity spacing), for an OSM bore
``wall_gap_m + wall_band_width_m``.
The rim closes across the mouth (s = 0) by an END CAP and, for a corridor
closed at both ends, across the far end too.  The region between ramp
and rim is the VOID: a planar face (role ``retaining_wall``, never
emitted as a surface) whose exterior IS the rim and whose hole IS the
ramp, so the rim is noded with the ground it cuts and the mesh
triangulates the wall between floor and rim.  Nothing stands between the
ramp edge and the rim; no crest band exists (the 09-01c band is retired).

Every vertex is born ON the identity grid; the rim is snapped AWAY from
the ramp (``snap_out``) and pushed out by grid steps until it clears the
ramp by ``rim_off`` everywhere — the gap is the law, never welded.

``capped=False`` leaves s = 0 open (an open+open corridor is two capless
halves meeting at its midpoint); ``far_capped=True`` closes the far end
(the void is an O with the ramp in its hole).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..model.frame import XY

if _t.TYPE_CHECKING:                      # annotations only (PEP 563 is on)
    from ..law import Law
    from ..model.structures import Tunnel


def pad_hit(outer: Polygon, pads: list[tuple[Polygon, str]], tree: STRtree | None,
            gap: float, exclude: _t.Collection[str] = ()) -> str | None:
    """The ref of a building pad (or, for a door ramp, any governed cell
    not among its host ``exclude`` refs) the footprint touches (closer
    than the gap), or ``None``.

    ONE implementation (lane v2planfix): ``planar/structures`` and
    ``planar/wall_corridor_ramps`` both ask this question, and carried
    byte-equal private copies of it.  It lives here because ``structures``
    imports ``wall_corridor_ramps`` — the shared home has to be upstream
    of both."""
    if tree is None:
        return None
    for j in tree.query(outer.buffer(gap), predicate="intersects"):
        p, ref = pads[int(j)]
        if ref in exclude:
            continue
        if p.distance(outer) < gap - 1e-9:
            return ref
    return None


def _unit(a: XY, b: XY) -> XY:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)

__all__ = ["RampGeometry", "geometry", "normals", "offset_line", "snap", "snap_out",
           "rim_standoff", "corner_distance", "beyond_strip",
           "design_points", "collapse_stations", "collapse_for_ramp", "ramp_targets", "covered_start", "reseat_expect"]


def rim_standoff(thickness_m: float, cutout, spacing_m: float) -> tuple[float, float]:
    """RULINGS 2026-09-08a (spec ``othh-read-20260906-spec.md`` §1a): the
    at-grade rim of a below-grade object's trench — ``(inset_m,
    standoff_m)`` for a wall (or basin shell) of MEASURED plan thickness
    ``thickness_m``.  ``inset_m`` is how far INSIDE the wall's outer face
    the rim stands (``cutout.rim_inset_fraction × t``: the terrain drop
    happens within the wall's thickness, hidden by the object);
    ``standoff_m`` is the rim's plan distance from the floor ring (the
    inner face ⊕ ``cutout.floor_overlap_m``) = the width of the mesh
    wall band: ``t − overlap − inset``, floored at ``spacing_m``
    (``emit.identity.min_distinct_spacing_m``) — a rim vertex is never
    closer to the floor ring than two distinct vertices may be.  Where
    the floor binds (``t < overlap + spacing``, a thin shell) the rim
    stands ``overlap + spacing`` outside the inner face: at the outer
    face of a 0.8 m wall, outside it for thinner ones.  One law for
    tunnel walls and basins (06b)."""
    t = max(float(thickness_m), 0.0)
    inset = cutout.rim_inset_fraction * t
    standoff = max(t - cutout.floor_overlap_m - inset, spacing_m)
    return inset, standoff


@_dc.dataclass(frozen=True)
class RampGeometry:
    """The stations' axis points and normals, the ramp's left / right
    edges, the ramp, the VOID (a Polygon with the ramp as its hole, or a
    MultiPolygon of two side pieces when capless), the outer footprint
    (= the rim ring), and the rim's cap points (``[left, centre,
    right]``; empty when capless) and far cap's (``[right, centre,
    left]``; empty unless far-capped).  ``left_rim`` / ``right_rim`` are
    the rim by station (the object's plate stations)."""

    axis: list[XY]
    normals: list[XY]
    left: list[XY]
    right: list[XY]
    ramp: Polygon
    wall: Polygon | MultiPolygon
    outer: Polygon
    cap_in: list[XY]
    cap_out: list[XY]
    far_in: list[XY]
    far_out: list[XY]
    left_rim: list[XY] = _dc.field(default_factory=list)
    right_rim: list[XY] = _dc.field(default_factory=list)


def normals(axis: _t.Sequence[XY]) -> list[XY]:
    """Left-hand unit normal per axis point (averaged at joints)."""
    n = len(axis)
    out: list[XY] = []
    for i in range(n):
        a = axis[max(0, i - 1)]
        b = axis[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        out.append((-dy / L, dx / L))
    return out


def offset_line(axis: _t.Sequence[XY], nrm: _t.Sequence[XY], off: float) -> list[XY]:
    return [(p[0] + nv[0] * off, p[1] + nv[1] * off) for p, nv in zip(axis, nrm)]


def snap(p: XY, grid: float) -> XY:
    """The nearest identity-grid point."""
    return (round(p[0] / grid) * grid, round(p[1] / grid) * grid)


def snap_out(p: XY, origin: XY, grid: float) -> XY:
    """``p`` snapped to the identity grid AWAY from ``origin`` on both
    axes, so a designed stand-off survives the arrangement's
    snap-rounding (09-01e "never ON a weld tolerance": two points 0.85 m
    apart both round to ONE 0.5 m grid point — measured OTHH, the ramp's
    mouth corner and the cap's corner merged into vertex 14058, an IIS
    of its two pins)."""
    out = []
    for c, o in zip(p, origin):
        k = c / grid
        if c > o + 1e-9:
            out.append(math.ceil(k - 1e-9) * grid)
        elif c < o - 1e-9:
            out.append(math.floor(k + 1e-9) * grid)
        else:
            out.append(round(k) * grid)
    return (out[0], out[1])


def _offset_out(axis: _t.Sequence[XY], nrm: _t.Sequence[XY], off: "float | _t.Sequence[float]",
                base: _t.Sequence[XY], grid: float) -> list[XY]:
    """``axis`` offset by ``off`` along ``nrm`` (one value, or one per
    point), each point snapped away from its ``base`` point."""
    offs = [off] * len(axis) if isinstance(off, (int, float)) else list(off)
    return [snap_out((p[0] + nv[0] * o, p[1] + nv[1] * o), b, grid)
            for p, nv, b, o in zip(axis, nrm, base, offs)]


def _clear(p: XY, direction: XY, ramp: Polygon, gap: float, grid: float) -> XY:
    """``p`` moved along ``direction`` by grid steps (snapped away from
    where it came from) until it stands ≥ ``gap`` off the ramp."""
    L = math.hypot(direction[0], direction[1]) or 1.0
    ux, uy = direction[0] / L, direction[1] / L
    q = p
    for _k in range(6):
        if ramp.distance(Point(q)) >= gap - 1e-9:
            return q
        q = snap_out((q[0] + ux * grid, q[1] + uy * grid), q, grid)
    return q


def _cap(m: XY, lin: XY, rin: XY, d: XY, nv: XY, ramp: Polygon, off: float, grid: float
         ) -> list[XY]:
    """The rim's end cap across the axis point ``m`` in direction ``d``
    (away from the ramp): ``[+nv corner, centre, −nv corner]``, each
    ``off`` beyond the ramp's end edge and cleared off the ramp by it."""
    dirs = [(d[0] + nv[0], d[1] + nv[1]), d, (d[0] - nv[0], d[1] - nv[1])]
    return [_clear(snap_out((lin[0] + dirs[0][0] * off, lin[1] + dirs[0][1] * off), lin, grid),
                   dirs[0], ramp, off, grid),
            _clear(snap_out((m[0] + d[0] * off, m[1] + d[1] * off), m, grid), d, ramp, off, grid),
            _clear(snap_out((rin[0] + dirs[2][0] * off, rin[1] + dirs[2][1] * off), rin, grid),
                   dirs[2], ramp, off, grid)]


def design_points(axis_fn, ss: _t.Sequence[float], half: float, rim_off: float,
                  half_fn=None, rim_fn=None) -> list[tuple[XY, ...]]:
    """The UNSNAPPED design points of every station — ``(axis, left,
    right, left rim, right rim)`` — i.e. what :func:`_geometry_at` then
    snaps to the identity grid.  The collapse of §34 (7) is judged on
    these, never on the snapped ring: the snap is precisely the 0.27–0.49 m
    stagger the owner read as a zig-zag."""
    axis = [axis_fn(s) for s in ss]
    nrm = normals(axis)
    out: list[tuple[XY, ...]] = []
    for p, nv, s in zip(axis, nrm, ss):
        hl, hr = half_fn(s) if half_fn is not None else (half, half)
        rl, rr = rim_fn(s) if rim_fn is not None else (rim_off, rim_off)
        lp = (p[0] + nv[0] * hl, p[1] + nv[1] * hl)
        rp = (p[0] - nv[0] * hr, p[1] - nv[1] * hr)
        out.append((p, lp, rp,
                    (lp[0] + nv[0] * rl, lp[1] + nv[1] * rl),
                    (rp[0] - nv[0] * rr, rp[1] - nv[1] * rr)))
    return out


def _on_chord(pts: list[tuple[XY, ...]], zs: list[float], i: int, j: int,
              lateral_m: float, z_m: float) -> bool:
    """Every station strictly between ``i`` and ``j`` stands within
    ``lateral_m`` of the chord ``i``–``j`` in EVERY design point (axis,
    both floor edges, both rim lines) and within ``z_m`` of the straight
    line between their design elevations."""
    for k in range(i + 1, j):
        f = (k - i) / (j - i)
        if abs(zs[k] - (zs[i] + (zs[j] - zs[i]) * f)) > z_m:
            return False
        for c in range(len(pts[k])):
            a, b, p = pts[i][c], pts[j][c], pts[k][c]
            seg = LineString([a, b]) if a != b else Point(a)
            if seg.distance(Point(p)) > lateral_m:
                return False
    return True


def collapse_stations(ss: _t.Sequence[float], pts: list[tuple[XY, ...]], zs: list[float],
                      lateral_m: float, z_m: float,
                      protect: _t.Collection[float] = ()) -> list[float]:
    """A RAMP CORRIDOR CARRIES A CROSS-CHORD ONLY WHERE THE ROUTE BENDS OR
    THE PROFILE BREAKS (spec §34 (7), owner RULINGS 2026-09-14n item 2 /
    2026-09-14p).  Stations at ``station_m`` are the SAMPLING of the
    profile, not the emitted shape: once the profile is solved, a run of
    consecutive stations that adds nothing to either — every interior
    station within ``lateral_m`` (``emit.identity.min_distinct_spacing_m``)
    of the chord between the surviving ends and within ``z_m`` (the
    materiality floor) of the straight profile between them — COLLAPSES
    to that chord.  A straight constant-grade run then emits its two end
    chords and nothing between; a landing-to-climb transition keeps its
    chord because the profile breaks there.  The 0.5 m identity
    ``snap_out`` has nothing left between the ends to stagger (OTHH's
    40- and 29-node ramps: one grid quantum of lateral offset per 2 m
    station, on a straight route)."""
    n = len(ss)
    if n <= 2:
        return list(ss)
    # the knees the caller KNOWS (the mouth, where the climb starts, the
    # wall end, the pinned top) are never collapsed through: a run is only
    # ever collapsed between two of them
    kept = sorted({k for k in range(n)
                   if any(abs(ss[k] - p) <= 1e-6 for p in protect)} | {0, n - 1})
    out = [ss[0]]
    i = 0
    while i < n - 1:
        limit = next(k for k in kept if k > i)
        j = limit
        while j > i + 1 and not _on_chord(pts, zs, i, j, lateral_m, z_m):
            j -= 1
        out.append(ss[j])
        i = j
    return out


def reseat_expect(c, mouth_z: float, grade: float, s_top: float, airport: Airport
                   ) -> tuple[float, ...]:
    """The re-seat the DESIGN implies for the corridor's placement(s)
    (05n-4): ``ground(anchor) − (floor at the anchor's station + agl +
    plate)`` — the post-mesh seat measures the real one."""
    ln = LineString(c.axis)
    s = ln.project(Point(c.anchor_xy))
    floor = min(mouth_z + grade * min(s, s_top), c.anchor_dem_z) if grade > 0 else mouth_z
    return (round(c.anchor_dem_z - (floor + c.agl_m + c.plate_y), 3),)


def covered_start(axis_fn, hull_s: float, plate, step: float) -> float | None:
    """THE CORRIDOR'S COVERED START (spec §34 (9) (5) as CORRECTED by owner
    RULINGS 2026-09-14be): the last station, walking out from the mouth,
    at which the axis still stands under the COVERING PLATE — the
    roof/deck component that gives the corridor its headroom
    (``airport/wall_corridors._headroom``'s witness plate, published as
    ``WallCorridorRecord.plate_plan``).  ``None`` when the corridor carries
    no cover, or when the cover reaches the wall end (nothing protrudes).

    14at read the BUILDING PAD instead and the owner still saw full depth
    at the outer end of the retaining walls: the pad polygon is not the
    building's wall face — at OTHH's east mouth it stands only 2.4 m
    inside the wall end where the cover stands farther in still.  The
    corridor is a trench only where it is COVERED; everything from the
    ramp's top down to the plate edge — the protruding retaining-wall
    bands included — is RAMP."""
    if plate is None or getattr(plate, "is_empty", True):
        return None
    inside = None
    s = 0.0
    while s <= hull_s + 1e-9:
        if plate.covers(Point(axis_fn(s))):
            inside = s
        elif inside is not None:
            break
        s += step
    return None if inside is None or inside >= hull_s - 1e-6 else inside


def ramp_targets(tunnels: _t.Sequence[Tunnel], law: Law, faces: dict, edges: list,
                 vxy: list[XY], dem_z: _t.Sequence[float]) -> dict[int, float]:
    """THE RAMP'S OBJECTIVE TARGET IS ITS OWN DESIGN, not the DEM: vertex
    id -> the designed profile value ``clamp(DEM, mouth_z − g·Δs, mouth_z
    + g·Δs)`` (``Δs`` from where the climb starts; ``g`` the tunnel's
    ``design_grade`` — ``min(ramp_max_grade, depth / wall length)`` for an
    object corridor, 05n-1 — else ``ramp_max_grade``) for every
    ``tunnel_ramp`` ring vertex.  With the DEM as target the ramp's pull levered the
    apron sharing its end cap 0.49 m up through the mouth datum
    (measured on the M4 twin) — groundside pulling airside; at its
    design the ramp has nothing to pull with."""
    if not tunnels:
        return {}
    from ..model.structures import profile_z
    g = law.tables.structures.tunnel.ramp_max_grade
    axes = {tn.id: LineString(tn.axis) for tn in tunnels}
    out: dict[int, float] = {}
    for fid, face in faces.items():
        if face.role not in ("tunnel_ramp", "door_ramp", "wall_corridor_ramp", "garage_ramp"):
            continue
        ids = {edges[e].a for e in face.ring} | {edges[e].b for e in face.ring}
        cx = sum(vxy[v][0] for v in ids) / len(ids)
        cy = sum(vxy[v][1] for v in ids) / len(ids)
        tid = min(axes, key=lambda k: axes[k].distance(Point(cx, cy)))
        tn = tunnels[[t.id for t in tunnels].index(tid)]
        gt = tn.design_grade if tn.design_grade > 0.0 else g
        for v in ids:
            s = axes[tid].project(Point(vxy[v]))
            if tn.profile:
                # a sunken road (09-08b/c Law B): the plate's own floor
                out[v] = profile_z(tn.profile, min(s, tn.top_s))
                continue
            reach = gt * max(0.0, s - tn.climb_from_s)
            if tn.source in ("object", "door") and s <= tn.wall_length_m + 1e-6:
                # INSIDE THE WALLS the design line itself (05n-1; the DEM
                # there is not the ground — 2026-09-06f: a cutting the DEM
                # carries would pull the ramp under its own design)
                out[v] = tn.mouth_z + gt * max(0.0, min(s, tn.top_s) - tn.climb_from_s)
                continue
            d = float(dem_z[v])
            if math.isnan(d):
                continue
            out[v] = max(tn.mouth_z - reach, min(tn.mouth_z + reach, d))
    return out


def collapse_for_ramp(axis_fn, ss: _t.Sequence[float], half: float, rim_off: float,
                      half_fn, g, *, climb_from: float, s_top: float, mouth_z: float,
                      design_grade: float, top_pinned: bool, wall_kind: bool,
                      dem_z, grid: float, z_tol: float) -> list[float]:
    """:func:`collapse_stations` over ONE ramp group (§34 (7)).

    The design elevation per station is read exactly as the halves that
    PUBLISH it do: the floor profile inside the walls
    (``wall_corridor_profile`` / Law B's pins, which carry the RECORD's own
    stations and the collapse never touches), the constant-grade design
    line beyond the knee (the wall end for a Law C corridor, or its MOVED
    mouth under §34 (8); where the climb starts otherwise), and the top at
    the GROUND where the generator
    pins it there — the profile BREAKS at that pin, so the collapse has to
    see it.  The knees are protected: no run is ever collapsed through the
    mouth, the start of the climb, the wall end or the top."""
    from ..model.structures import profile_z
    profile = tuple(g.profile)
    knee = (min(g.hull_s, climb_from) if wall_kind else climb_from) if g.climbs \
        else (profile[-1][0] if profile else climb_from)

    def z_at(s: float) -> float:
        if not (g.climbs and s > knee + 1e-9):
            return profile_z(profile, s) if profile else mouth_z
        return (profile[-1][1] if profile else mouth_z) + design_grade * (s - knee)
    zs = [z_at(s) for s in ss]
    if g.climbs and top_pinned:
        z_top = float(dem_z(*axis_fn(s_top)))
        if not math.isnan(z_top):
            zs[-1] = z_top
    return collapse_stations(ss, design_points(axis_fn, ss, half, rim_off, half_fn, g.rim_fn),
                             zs, grid, z_tol, protect=(climb_from, knee, g.hull_s, s_top))


def _geometry_at(axis_fn, ss: list[float], half: float, rim_off: float, inward: XY,
                 grid: float, capped: bool, far_capped: bool, half_fn=None, rim_fn=None,
                 cap_off: float | None = None, far_off: float | None = None
                 ) -> RampGeometry | None:
    """The ramp, the void and the rim for stations ``ss`` (see the module
    doc).  ``None`` when a bend tighter than the offsets folds a ring
    over itself (a buffer would repair it with off-grid vertices — the
    merge class).  ``half_fn(s) -> (left, right)`` / ``rim_fn(s) ->
    (left, right)`` give a corridor whose ramp edges and rim stand-offs
    vary by station (a wall object's inner faces and its walls'
    thickness); ``cap_off`` / ``far_off`` the end caps' stand-off (an
    object's end wall)."""
    axis = [axis_fn(s) for s in ss]
    nrm = normals(axis)
    hl = [half_fn(s)[0] for s in ss] if half_fn is not None else [half] * len(ss)
    hr = [half_fn(s)[1] for s in ss] if half_fn is not None else [half] * len(ss)
    rl = [rim_fn(s)[0] for s in ss] if rim_fn is not None else [rim_off] * len(ss)
    rr = [rim_fn(s)[1] for s in ss] if rim_fn is not None else [rim_off] * len(ss)
    # an object corridor's floor edges (``half_fn``: inner face + overlap)
    # snap AWAY from the axis — the overlap is a stand-off, never rounded
    # under; an OSM bore's carriageway snaps nearest
    if half_fn is not None:
        left = [snap_out((p[0] + nv[0] * h, p[1] + nv[1] * h), p, grid)
                for p, nv, h in zip(axis, nrm, hl)]
        right = [snap_out((p[0] - nv[0] * h, p[1] - nv[1] * h), p, grid)
                 for p, nv, h in zip(axis, nrm, hr)]
    else:
        left = [snap((p[0] + nv[0] * h, p[1] + nv[1] * h), grid) for p, nv, h in zip(axis, nrm, hl)]
        right = [snap((p[0] - nv[0] * h, p[1] - nv[1] * h), grid) for p, nv, h in zip(axis, nrm, hr)]
    ramp = Polygon(left + list(reversed(right)))
    if not ramp.is_valid or ramp.area < 1.0:
        return None
    # the rim: offset, snapped away, then PUSHED out by grid steps until
    # each point clears the ramp by its stand-off (a component-wise
    # outward snap can shorten a diagonal offset's projection; the law is
    # the plan distance to the ramp)
    left_rim = [_clear(p, d, ramp, o, grid) for p, d, o in
                zip(_offset_out(left, nrm, rl, left, grid), nrm, rl)]
    right_rim = [_clear(p, (-d[0], -d[1]), ramp, o, grid) for p, d, o in
                 zip(_offset_out(right, nrm, [-r for r in rr], right, grid), nrm, rr)]
    cap_out: list[XY] = []
    far_out: list[XY] = []
    if capped:
        # the cap: left corner, CENTRE (the mouth wall node, 09-03b), right corner
        cap_out = _cap(axis[0], left[0], right[0], inward, nrm[0], ramp,
                       cap_off if cap_off is not None else rim_off, grid)
    if far_capped:
        a, b = axis[-2], axis[-1]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        outward = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        # in ring order after the right rim's top: right corner, centre, left corner
        far_out = _cap(axis[-1], right[-1], left[-1], outward, (-nrm[-1][0], -nrm[-1][1]),
                       ramp, far_off if far_off is not None else rim_off, grid)
    outer_ring = list(reversed(left_rim)) + cap_out + right_rim + far_out
    if not capped and not far_capped:
        # capless: two side pieces — the rim is two lines, the void the
        # two strips between them and the ramp
        wall: Polygon | MultiPolygon = MultiPolygon([
            Polygon(list(left) + list(reversed(left_rim))),
            Polygon(list(right) + list(reversed(right_rim)))])
        outer = Polygon(list(reversed(left_rim)) + list(right_rim))
    else:
        outer = Polygon(outer_ring)
        if not outer.is_valid:
            return None
        wall = outer.difference(ramp)
        if wall.geom_type == "MultiPolygon":
            parts = [g for g in wall.geoms if g.area > 1e-6]
            wall = parts[0] if len(parts) == 1 else MultiPolygon(parts)
    if not wall.is_valid or not outer.is_valid or wall.is_empty:
        return None
    return RampGeometry(axis, nrm, left, right, ramp, wall, outer, [], cap_out, [], far_out,
                        left_rim, right_rim)


#: §33 (6) B: the id prefix ``airport/tunnel_objects.shell_corridor`` mints
#: for a signature-B corridor.  An id literal, flagged for ``blast.py``.
OBJECT_CUT_PREFIX = "object-cut:"

#: §33 (6) B AMENDED: a walled floor ring under this fraction of the
#: object's own trench is not a trench with walls, it is a shell whose
#: walls eat it — the corridor is refused by name instead.
_MIN_WALLED_FRACTION = 0.25


def seed_wall_stations(ss: list[float], c, grid: float) -> list[float]:
    """§33 (6) C2' A BAND IS A POLYLINE (RULINGS 2026-09-15x): where the
    pack's wall CURVES, the station set keeps the WALL'S OWN vertices.

    ``emit.chords.station_spacing_m`` is 12 m, and a 12-24 m chord across
    a curved inner face cuts the corner — measured LEMD `Bridge4.obj`
    (owner 15e item 6): the emitted ramp stood 0.46-4.09 m off the
    corridor's own inner faces (4 vertices over 0.75 m) and the rim
    0.51-11.53 m (21 over), on a corridor whose record carries 63
    stations at 2 m.

    ONLY THE STATIONS THAT CARRY THE CURVE ARE SEEDED — a corridor
    station is added when an inner-face point there stands more than
    ``grid`` (``emit.identity.min_distinct_spacing_m``, §34 (7)'s own
    lateral floor) off the chord between the surviving stations either
    side of it.  Seeding them ALL was measured and withdrawn: it moved
    nine STRAIGHT OTHH object corridors (and one's ramp top 240 -> 246 m)
    for nothing, because the denser set also re-steps the clip loop."""
    S = [float(st.s) for st in (getattr(c, "stations", ()) or ())] if c is not None else []
    if len(S) < 3 or not ss:
        return ss
    try:
        left, right = c.stations_inner()
    except Exception:                                      # pragma: no cover
        return ss
    if len(left) != len(S) or len(right) != len(S):
        return ss
    base = sorted(ss)
    keep = set(base)

    def at(chain, s: float) -> XY:
        k = min(range(len(S)), key=lambda i: abs(S[i] - s))
        return chain[k]

    for i, s in enumerate(S):
        if any(abs(s - t) <= 1e-9 for t in base):
            continue
        lo = max((t for t in base if t <= s), default=None)
        hi = min((t for t in base if t >= s), default=None)
        if lo is None or hi is None or hi - lo <= 1e-9:
            continue
        for chain in (left, right):
            a, b, p = at(chain, lo), at(chain, hi), chain[i]
            if a == b:
                continue
            if LineString([a, b]).distance(Point(p)) > grid:
                keep.add(s)
                break
    return sorted(keep)


def ring_for(c, axis_fn, ss: list[float], half: float, rim_off: float, inward: XY,
             grid: float, g, half_fn=None) -> "RampGeometry | None":
    """The corridor's ring: the OBJECT'S OWN TRENCH POLYGON for a
    signature-B object cut (§33 (6) B — see
    :func:`geometry_from_trench`), else :func:`geometry`'s axis offset."""
    if c is not None and str(getattr(c, "id", "")).startswith(OBJECT_CUT_PREFIX):
        # §33 (6) B AMENDED: the WALL's own width, by the law the axis
        # offset already applies per station (``object_corridor.rim_fn``
        # = :func:`rim_standoff` of the wall's MEASURED thickness); the
        # narrowest station's is the one the whole ring must clear.
        want = rim_off
        if g is not None and getattr(g, "rim_fn", None) is not None and ss:
            want = min(min(g.rim_fn(s)) for s in ss)
        gm = geometry_from_trench(axis_fn, ss, half, want, grid,
                                  c.trench, c.footprint, half_fn)
        if gm is not None:
            return gm
    return geometry(axis_fn, ss, half, rim_off, inward, grid, g.capped, g.far_capped,
                    half_fn, g.rim_fn, g.cap_off, g.far_off)


def geometry_from_trench(axis_fn, ss: list[float], half: float, standoff: float, grid: float,
                         trench, footprint, half_fn=None) -> "RampGeometry | None":
    """§33 (6) B: THE RING IS THE OBJECT'S OWN TRENCH POLYGON (owner
    RULINGS 2026-09-15g; Fable / RULINGS 2026-09-15x), not an axis offset.

    :func:`_geometry_at` builds a corridor's ramp by offsetting its AXIS
    by the half widths.  That folds on a HAIRPIN and the whole corridor
    is refused — measured at VHHH, where `tunnel5_done` (the owner's site
    22.3038632, 113.9088362: a 413 m U-turn ramp) and `TUNNEL2_DONE` (a
    1,110 m multi-portal shell) were both lost that way, their readings
    correct (floor 1.30 against the authored 1.31, trench 9,290 m²).  A
    shell STATES its trench: the plan union of its non-vertical faces,
    bounded by its own per-band wall line.  So the ramp face IS that
    polygon and the rim ring IS the object's footprint — no offset, no
    fold, and the cut cannot leave the object by construction.

    The per-station ``axis`` / ``left`` / ``right`` arrays are still the
    offsets: the profile is pinned per station and the mouth strip reads
    the first pair, and a folded RING never made those numbers wrong.

    §33 (6) B AMENDED — A SHELL'S TRENCH IS WALLED (Fable 2026-09-15;
    RULINGS 2026-09-15bh; lane ``v2vhhhctl``'s matched VHHH pair).  The
    ramp = the trench and the rim = the footprint left NOTHING BETWEEN
    THEM where the shell's wall faces do not stand on the ring — its
    portals, and every run the reader reads as open: ``outer.difference
    (ramp)`` is then a sliver of zero width, the floor ring IS the
    surrounding surface's ring, and ``constraints/structures.on_floor``
    gives the AIRSIDE vertices standing on it the FLOOR row.  Measured on
    the 1.0.341 VHHH products: the void ring at 22.30772,113.92337
    (``tunnel_wall`` way −11372, 11 nodes) spanning 0.78 … 7.32 m, nine
    airside vertices on a ``tunnel_ramp`` ring (three at TUNNEL2's
    authored floor 0.78), and 1,362 of 3,815 airside vertices within
    200 m of the five shells pulled up to 6.46 m under the control.

    So the FLOOR RING IS INSIDE THE RIM BY THE WALL'S THICKNESS: the
    trench ∩ the footprint eroded by ``standoff`` (the corridor's own
    :func:`rim_standoff` of its walls' measured thickness — the value the
    axis-offset path applies per station).  Where the object's walls are
    already thicker than the stand-off the floor ring is the object's own
    inner face, untouched; where they are thinner, or absent, the law's
    stand-off makes the wall.  A vertex can only move INWARD, so
    ``object_cut_offset`` can only fall.  The RIM RING is published as
    ``left_rim`` (``right_rim`` empty), so the corridor's ``wall_path`` is
    the closed rim ring itself — a basin's already is — and not the
    axis-offset lines, which on a hairpin run across the trench."""
    axis = [axis_fn(s) for s in ss]
    if len(axis) < 2:
        return None
    nrm = normals(axis)
    hl = [half_fn(s)[0] for s in ss] if half_fn is not None else [half] * len(ss)
    hr = [half_fn(s)[1] for s in ss] if half_fn is not None else [half] * len(ss)
    left = [snap_out((p[0] + nv[0] * h, p[1] + nv[1] * h), p, grid)
            for p, nv, h in zip(axis, nrm, hl)]
    right = [snap_out((p[0] - nv[0] * h, p[1] - nv[1] * h), p, grid)
             for p, nv, h in zip(axis, nrm, hr)]
    ramp = _one_polygon(trench)
    outer = _one_polygon(footprint)
    if ramp is None or outer is None:
        return None
    if not outer.contains(ramp):
        outer = _one_polygon(unary_union([outer, ramp]))
        if outer is None:
            return None
    if standoff > 0.0:
        # THE GAP IS NEVER ON A WELD TOLERANCE (09-01e, this file's own
        # law): the arrangement snap-rounds to ``grid``, and two points
        # 0.85 m apart have been measured rounding to ONE 0.5 m grid
        # point.  Neither of these rings is snapped — they are the
        # OBJECT'S own vertices — so each can move up to half a grid
        # diagonal toward the other, and the stand-off is widened by one
        # grid step to keep the rings at least the identity spacing apart
        # after the round.
        inside = _one_polygon(outer.buffer(-(standoff + grid), join_style="mitre"))
        if inside is None:
            return None
        walled = _one_polygon(ramp.intersection(inside))
        if walled is None or walled.area < ramp.area * _MIN_WALLED_FRACTION:
            # the object leaves no room for its own walls: refused by
            # name upstream rather than emitted as a wall-less trench
            return None
        ramp = walled
    wall = outer.difference(ramp)
    if wall.is_empty:
        return None
    return RampGeometry(axis, nrm, left, right, ramp, wall, outer, [], [], [], [],
                        list(outer.exterior.coords), [])


def _one_polygon(geom):
    """One valid Polygon, or ``None`` — the same repair the object reader
    makes (``airport/object_cut.valid_polygon``), never a second
    spelling."""
    from ..airport import object_cut as _oc
    return _oc.largest_polygon(geom)


def geometry(axis_fn, ss: list[float], half: float, rim_off: float, inward: XY,
             grid: float, capped: bool = True, far_capped: bool = False, half_fn=None,
             rim_fn=None, cap_off: float | None = None, far_off: float | None = None
             ) -> RampGeometry | None:
    """:func:`_geometry_at` with the stand-off widened by grid steps (at
    most three) until the ramp and the rim clear each other by the law's
    stand-off everywhere — the snapped rings are jagged by up to half a
    grid step, so an edge can stand closer than its vertices do.  THE
    GAP IS THE LAW: a bend that cannot be cleared this way is refused,
    never welded."""
    for k in range(4):
        extra = k * grid
        rf = (lambda s, _f=rim_fn, _e=extra: (_f(s)[0] + _e, _f(s)[1] + _e)) \
            if rim_fn is not None else None
        g = _geometry_at(axis_fn, ss, half, rim_off + extra, inward, grid, capped, far_capped,
                         half_fn, rf, None if cap_off is None else cap_off + extra,
                         None if far_off is None else far_off + extra)
        if g is None:
            return None
        side_want = rim_off if rim_fn is None else min(min(rim_fn(s)) for s in ss)
        lines = [(LineString(g.left_rim), side_want), (LineString(g.right_rim), side_want)]
        if g.cap_out:
            lines.append((LineString(g.cap_out), cap_off if cap_off is not None else rim_off))
        if g.far_out:
            lines.append((LineString(g.far_out), far_off if far_off is not None else rim_off))
        edge = g.ramp.exterior
        if all(edge.distance(ln) >= want - 1e-6 for ln, want in lines):
            return g
    return None


def corner_distance(axis_fn, s0: float, s1: float, half_fn, half: float) -> float:
    """The least direct distance between the ramp's edge corners at
    station ``s0`` and at ``s1`` (left and right, the half-widths from
    ``half_fn`` or ``half``) — the shortest ring pair the within-shape
    law prices between the two lines."""
    def corners(s: float) -> list[XY]:
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        ux, uy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ux, uy) or 1.0
        n = (-uy / L, ux / L)
        hl, hr = half_fn(s) if half_fn is not None else (half, half)
        return [(p[0] + n[0] * hl, p[1] + n[1] * hl), (p[0] - n[0] * hr, p[1] - n[1] * hr)]
    return min(math.hypot(q[0] - r[0], q[1] - r[1]) for q in corners(s0) for r in corners(s1))


def beyond_strip(axis_fn, s_end: float, length: float) -> Polygon:
    """The half-plane strip BEYOND the axis station ``s_end`` (an object
    corridor's open end line): ``length`` long along the axis, as wide."""
    a, b = axis_fn(max(0.0, s_end - 1.0)), axis_fn(s_end)
    ux, uy = _unit(a, b)
    nx, ny = -uy, ux
    e = axis_fn(s_end)
    return Polygon([(e[0] + nx * length, e[1] + ny * length),
                    (e[0] - nx * length, e[1] - ny * length),
                    (e[0] - nx * length + ux * length, e[1] - ny * length + uy * length),
                    (e[0] + nx * length + ux * length, e[1] + ny * length + uy * length)])
