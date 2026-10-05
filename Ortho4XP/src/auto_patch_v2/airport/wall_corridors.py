"""THE WALL CORRIDORS (RULINGS 2026-09-08m / 08n LAW C; spec ``docs/specs/
auto-patch-v2/othh-terminal-ramps-spec.md`` §6, §12g; law ``structures.toml
[cutout.wall_corridor]``, ``airports.toml``):

LAW C IS A PER-AIRPORT AFFORDANCE (RULINGS 2026-09-10ap, closing 10ac-1
as (B)): both classes here — kerb-wall corridors AND garage ramps — are
read only where ``law/airports.toml`` states ``kerb_wall_corridors =
true`` for the airport (OTHH alone today, on the owner's sim read).
After seven rounds no witness in the geometry or the map separated
OTHH's terminal kerb corridors from LEMD's cargo-dock foundations
(§12–§12f), so the key is an honest switch, not a mechanism, and it is
checked FIRST at the single admission site (before clause (a)), one
``stats.admission`` line per candidate.  Law A (door wells) and Law B
(sunken roads, basins) are unconditional everywhere.

The reading itself: the pack models the terminal's road underpass,
its loading bays and its garage entry ramps as KERB WALLS only — genuine
components of VERTICAL faces only, reaching under the ground, NO floor
at any depth (measured OTHH, scout ``othhunderpass``: ``Terminal_Base_
2_5`` comps 799/800, two 77.8 m bands y −1.888..+0.587, inner faces
9.84 m apart, a deck at +2.61 over 74 % of them; the loading bay
``Terminal_Base_2_1`` comps 3176/3179 + a ``Base_4`` end wall, 6.3 ×
9.75 m, 1.35 m deep).  Every floor-plate reader (basin, door, sunken
road, tunnel crest) sees nothing there, and ``obj8._bulk_polys`` drops
their zero-plan-area bands — this reader takes the vertical triangles
from ``Component.tris`` directly.

EVERY READING IS IN THE OBJECT'S SEATED FRAME (RULINGS 2026-09-10ad):
the rebake puts an object's zero on its LOCAL GROUND (09af-1), so a
component renders at ``dem(its own plan centroid) + agl + authored y``
(``_seat_base``) and its depth under the ground IS its authored depth.
Reading it against ``anchor_z`` instead gave a shared-datum pack
(Aerosoft LEMD: one anchor at 596 m for components 4 km away where the
terrain stands at 605) walls 8-10 m "below ground" and 160-200 m ramps
for doors authored 2.6 m down.

THE READING, per ANCHOR FAMILY (``deck_signature.family_key``):

1. BANDS — a genuine component whose every triangle is vertical (``|n_y|
   < tunnel.object.plate_normal_y_min``), AUTHORED ``min_wall_depth_m``
   below the OBJECT'S OWN local zero (RULINGS 2026-09-10u: never against
   the DEM under the pack's anchor plane) and reaching up to within
   ``basin.contact_band_m`` of the ground (in the seated frame: ``max_y
   >= -contact_band_m``), is a WALL BAND: its plan footprint is the union of its faces' plan
   segments (the loops filled; a single sheet is widened to a nominal
   band so the wall-line reader can walk its ring), its axis the minimum
   rotated rectangle's long side, its thickness the short side.  Bands
   of one family parallel within ``parallel_max_deg``, within a wall's
   plan thickness (``tunnel.object.wall_face_max_thickness_m``) of each
   other laterally and interrupted by at most ``merge_gap_m`` along the
   axis are ONE WALL (a kerb split at a crossing; a floor-to-deck panel
   standing inside its kerb: OTHH ``Terminal_Base_9_6`` in ``2_5``).
2. PAIRS — two bands of one family parallel within ``parallel_max_deg``,
   their inner faces ``min_width_m``..``max_width_m`` apart, overlapping
   ``min_wall_length_m`` along the axis, with no third band of the family
   between them, form a CORRIDOR: ``tunnel_walls.read_wall_lines`` reads
   the pair as kind "II" (the inner faces are the chains nearer the other
   band), ``midline`` / ``stations_along`` give the axis and the stations.
3. THE FLOOR — the walls' BOTTOM edge PER STATION (``mouth_depth =
   "wall_bottom"``, 08n): the lowest rendered vertex of the bands' faces
   within a station's window along the axis (every face edge densified,
   so a 78 m quad still states its bottom everywhere).  The corridor is
   ADMITTED on that bottom's AUTHORED height (10u) and the floor stands
   at it in the SEATED frame (10ad), so the ramp beyond a mouth climbs
   the AUTHORED depth.  LEVEL (the
   underpass, the bays: the bottom's range under ``min_wall_depth_m``)
   or DESCENDING (a garage ramp: the bottom runs from within the contact
   band of the ground down to the garage floor — cut AS AUTHORED; the
   ramp laws do not gate it; ``max_authored_grade`` refuses loudly).
4. THE ENDS — an end is CLOSED when family vertical faces within
   ``tunnel.object.end_cap_open_m`` of its line cover ``end_cap_cover_min``
   of it; else a MOUTH (``planar/wall_corridor_ramps.py`` ramps beyond it
   at ``ramp_grade``).  A descending corridor's deep end is closed by the
   garage whatever crosses it.  Classes: ``level`` open both ends (TWO
   capless halves meeting at the midpoint, each climbing beyond its own
   end), ``bay`` (one closed end), ``garage_ramp`` (descending); closed at
   both ends is refused by name (no mouth).
5. HEADROOM — the lowest near-horizontal family face over the trench
   stands ``min_headroom_m`` above the floor, else refused (replaces the
   basement cover gate: the deck above is the family's own roof and stays).
   Open air over the trench is NOT a refusal (RULINGS 2026-09-10z: seven
   OTHH corridors carry no deck plate of their own).
6. THE KERB (issue #12, Q-12): a band whose OWN component rises more than
   ``max_wall_height_m`` over the object's zero is a building / bridge wall's
   buried foot — foundations (10af); the pair is refused and the object keeps
   its seat.  (10ap refuted it on the OLD pack; the owner's new-pack read
   names two such corridors as tunnels "where none exist".)
(The 10w heading and deck clauses, 10z's groundside-mouth clause (b'')
and 10ao's terminals-only clause are all REFUTED and DELETED: no mouth test separates LEMD's cargo
foundations from OTHH's kerb corridors — RULINGS 2026-09-10ab / 10ad.)

The ``--stage structures`` replay additionally MEASURES, per candidate,
the two discriminators RULINGS 2026-09-10ab asked for — the mouth road's
LEVEL against the floor, and a FLOOR SLAB between the walls
(``read_wall_corridors(measure=True)``, ``stats.floor_probe``).  Neither
separates the two packs (spec §12c: the slab is 0 at BOTH; no level
tolerance keeps OTHH's 43 without keeping 15 of LEMD's), so neither
gates anything and a build never runs them.

Nothing numeric lives here but geometric epsilons; every law value is a
table argument.
"""
from __future__ import annotations

from ..model.frame import rotated_rectangle

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..model.frame import XY
from . import frame_entry as _fe
from . import obj8 as _obj8
from .wall_corridor_probe import ROAD_ROLES, MouthRoad, mouth_roads
from .wall_geometry import (WallBand, _DENSIFY_M, _seat_base, _MITRE, _MIN_SEG_M, _SHEET_BAND_M, _angle_diff, _band_polygon,
                            _densified, _plan_polys, _plan_segments_indexed,
                            _rect_axis, _rect_sides, _straight_runs, _tri_normals_y)
from .tunnel_walls import Station, WallLines

__all__ = ["WallBand", "WallCorridorRecord", "WallCorridorStats",
           "MouthRoad", "mouth_roads", "ROAD_ROLES",
           "ID_PREFIX", "CLASS_LEVEL", "CLASS_BAY", "CLASS_GARAGE"]

ID_PREFIX = "wall-corridor"
CLASS_LEVEL, CLASS_BAY, CLASS_GARAGE = "level", "bay", "garage_ramp"




@_dc.dataclass(frozen=True)
class WallCorridorRecord:
    """One wall corridor (or one half of a level open/open corridor) in
    the airport frame, s = 0 at the MOUTH end (the deep / closed end, or
    the midpoint for a half): the axis and stations (``tunnel_walls.
    Station``: inner faces and thickness per station), the floor per
    station (rendered z), the ground per station, the class, the ends."""

    id: str
    resource: str
    objects: tuple[str, ...]
    family: str
    cls: str
    axis: tuple[XY, ...]
    stations: tuple[Station, ...]
    floors: tuple[float, ...]
    grounds: tuple[float, ...]
    length_m: float
    width_m: float
    mouth_closed: bool
    far_closed: bool
    mouth_thickness_m: float
    far_thickness_m: float
    walls: Polygon
    trench: Polygon
    footprint: Polygon
    anchor_xy: XY
    anchor_dem_z: float
    agl_m: float
    headroom_m: float | None
    max_authored_grade: float
    sibling: str = ""
    notes: tuple[str, ...] = ()
    #: THE COVERING PLATE'S PLAN (spec §34 (9) (5) as corrected by owner
    #: RULINGS 2026-09-14be): the plan union of the witness plate's own
    #: near-horizontal faces — the roof/deck component that gives this
    #: corridor its ``headroom_m``.  ``None`` = open air, no cover.  Its
    #: edge along the axis is the corridor's FULL-DEPTH point; everything
    #: from the ramp's top down to it, the protruding retaining-wall
    #: bands included, is ramp.
    plate_plan: Polygon | None = None

    @property
    def floor_z(self) -> float:
        return self.floors[0]

    @property
    def mouth_dem_z(self) -> float:
        return self.grounds[0]

    @property
    def depth_m(self) -> float:
        return max(g - z for g, z in zip(self.grounds, self.floors))

    @property
    def profile(self) -> tuple[tuple[float, float], ...]:
        return tuple((st.s, z) for st, z in zip(self.stations, self.floors))

    @property
    def ends(self) -> str:
        a = "closed" if self.mouth_closed else "open"
        b = "closed" if self.far_closed else "open"
        return f"{a}/{b}"

    @property
    def ground_kind(self) -> str:
        return "closed" if self.far_closed else "open"

    @property
    def mouth_kind(self) -> str:
        return self.cls

    #: The fields ``planar/structures.build_structures`` reads off an
    #: object corridor and a wall corridor never has.
    plate_y: float = 0.0
    edge_wall: bool = False
    flat: bool = False
    floor_y: float | None = None


@_dc.dataclass
class WallCorridorStats:
    placements: int = 0
    families: int = 0
    bands: int = 0
    pairs: int = 0
    corridors: int = 0
    by_class: dict[str, int] = _dc.field(default_factory=dict)
    refused: list[str] = _dc.field(default_factory=list)
    #: One line per CANDIDATE corridor stating the admission -- (a)
    #: AUTHORED depth in the SEATED frame (10u, 10ad) -- with its witness
    #: or its refusal.
    admission: list[str] = _dc.field(default_factory=list)
    #: RULINGS 2026-09-10ab: one row per candidate reaching the mouth
    #: test — the two discriminators MEASURED (floor vs the mouth road's
    #: level; the floor slab), whatever the admission then says.
    floor_probe: list[dict] = _dc.field(default_factory=list)
    #: RULINGS 2026-09-10af: one row per candidate — the NARROW-CUT
    #: reading (the wall pair's spacing; the placement's below-zero
    #: perimeter fraction; the cut's width across the axis against the
    #: footprint's), whatever the admission then says.
    narrow_cut: list[dict] = _dc.field(default_factory=list)
    read_s: float = 0.0


def _bands_of(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, dem_z, law: Law
              ) -> tuple[list[WallBand], list[tuple[int, np.ndarray]]]:
    """Rule 1 for one placement: its wall bands, and — for the closure
    and headroom readings — every genuine component's index with its
    vertical-face mask (``(comp index, mask)``)."""
    wc = law.tables.structures.cutout.wall_corridor
    ob = law.tables.structures.tunnel.object
    bl = law.tables.structures.basin
    g = cache.geometry(o.resolved)
    if g is None:
        return [], []
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    v = g.vertices
    bands: list[WallBand] = []
    verticals: list[tuple[int, np.ndarray]] = []
    for ci, comp in enumerate(cache.genuine(o.resolved)):
        cx, cy = _obj8._to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        # RULINGS 2026-09-10ad: the SEATED frame — the component's own
        # local ground carries the object's zero, so the ground stands at
        # y = -agl in the object's frame (never ``dem - anchor_z``, which
        # is the pack's anchor plane against the terrain).
        base = _seat_base(o, (cx, cy), dem_z)
        plane_ground = -float(o.agl_m)
        # RULINGS 2026-09-10u — AUTHORED depth admits a band: its lowest
        # vertex stands at least min_wall_depth_m below the OBJECT'S OWN
        # local zero.  Rendered depth (dem_z - (anchor_z + agl)) admitted
        # every wall of a pack whose flat anchor plane sits metres under
        # the terrain (Aerosoft LEMD: 17 spurious corridors, nothing
        # authored below the origin); OTHH's accepted kerbs author theirs
        # at y -1.888..+0.587 and stay admitted.  The placement pre-screen
        # in read_wall_corridors reads the same frame.
        if comp.min_y > -wc.min_wall_depth_m:
            continue
        ny = _tri_normals_y(v, comp.tris)
        vert = ny < ob.plate_normal_y_min
        if vert.any():
            verticals.append((ci, vert))
        if not vert.any():
            continue
        if comp.max_y < plane_ground - bl.contact_band_m:
            continue                    # buried: never reaches the ground
        if not vert.all():
            # a kerb may carry a CAP or a chamfer (a strip no wider across
            # than a wall's plan thickness); a component whose non-vertical
            # faces span wider is a floor, a roof or a deck — not a band
            # (OTHH Terminal_Base_2_1 comps 3176/3179: 0.1 m2 of slivers)
            caps = _plan_polys(v, comp.tris[~vert], mat, cache.input_quantum_m)
            if caps:
                # §51 (4) row 12 / Law B (THE TNCM ABORT): every ``cap``
                # was already valid and GEOS still threw a side-location
                # conflict at (-557.635, 254.363) — validity at entry does
                # not make the exact overlay total, so the union ladders.
                cap_u = _fe.union(caps, "wall_corridors.caps")
                if cap_u.area > 1e-9:
                    _L, Wc = _rect_sides(rotated_rectangle(cap_u))
                    if Wc > ob.wall_face_max_thickness_m:
                        continue
        segs = _plan_segments_indexed(v, comp.tris[vert], mat)
        tri_rows = np.nonzero(vert)[0]
        for run in _straight_runs(segs, wc.parallel_max_deg, ob.wall_face_max_thickness_m):
            poly, thick = _band_polygon([segs[k][0] for k in run])
            if poly is None or poly.is_empty or poly.area <= 1e-9:
                continue
            ra = _rect_axis(poly)
            if ra is None:
                continue
            axis, length, brg = ra
            if length < wc.min_wall_length_m:
                continue                # a wall's end face, a return: never a band
            rows = comp.tris[tri_rows[sorted({segs[k][1] for k in run})]]
            pts = _densified(v, rows, mat, base)
            bands.append(WallBand(o.id, o.path, ci, poly, float(thick), axis, length, brg, pts,
                                  float(pts[:, 2].max()), float(pts[:, 2].min())))
    return bands, verticals


# ── pairs → corridors ────────────────────────────────────────────────────

def _floor_profile(bands: _t.Sequence[WallBand], axis_ln: LineString, ss: _t.Sequence[float],
                   window: float) -> tuple[list[float], list[float]]:
    """Rule 3: per station, the lowest RENDERED vertex of the bands'
    faces within ``±window`` of it along the axis, and that same sample's
    AUTHORED height (``y`` in the object's own frame, RULINGS
    2026-09-10u) — ``(floors, floors_y)``, gaps filled from the
    neighbours."""
    pts = np.concatenate([b.pts for b in bands])
    s_of = np.asarray([axis_ln.project(Point(x, y)) for x, y in pts[:, :2].tolist()])
    out: list[float | None] = []
    out_y: list[float | None] = []
    for s in ss:
        sel = np.abs(s_of - s) <= window
        if sel.any():
            rows = pts[sel]
            k = int(np.argmin(rows[:, 2]))
            out.append(float(rows[k, 2]))
            out_y.append(float(rows[:, 3].min()))
        else:
            out.append(None)
            out_y.append(None)
    # fill the gaps from the neighbours
    for col in (out, out_y):
        for i, z in enumerate(col):
            if z is None:
                left = next((col[j] for j in range(i - 1, -1, -1) if col[j] is not None), None)
                right = next((col[j] for j in range(i + 1, len(col)) if col[j] is not None), None)
                col[i] = left if right is None else (right if left is None else (left + right) / 2.0)
    return _t.cast(list[float], out), _t.cast(list[float], out_y)


def _end_cover(end: tuple[XY, XY], faces: list[LineString], tree: STRtree | None, tol: float
               ) -> float:
    """Rule 4: the share of the end line covered by family vertical faces
    standing within ``tol`` of it."""
    if tree is None:
        return 0.0
    a, b = end
    L = math.dist(a, b)
    if L < 1e-9:
        return 0.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    band = LineString([a, b]).buffer(tol, cap_style="flat")
    ivals: list[tuple[float, float]] = []
    for j in tree.query(band, predicate="intersects"):
        seg = faces[int(j)]
        x = seg.intersection(band)
        for part in shapely.get_parts(x):
            if part.is_empty or part.geom_type not in ("LineString", "Point"):
                continue
            ts = [((p[0] - a[0]) * ux + (p[1] - a[1]) * uy) for p in part.coords]
            lo, hi = max(0.0, min(ts)), min(L, max(ts))
            if hi > lo:
                ivals.append((lo, hi))
    ivals.sort()
    covered = 0.0
    cur: tuple[float, float] | None = None
    for lo, hi in ivals:
        if cur is None or lo > cur[1]:
            if cur is not None:
                covered += cur[1] - cur[0]
            cur = (lo, hi)
        else:
            cur = (cur[0], max(cur[1], hi))
    if cur is not None:
        covered += cur[1] - cur[0]
    return covered / L


def _interp_station(sts: _t.Sequence[Station], s: float) -> Station:
    lo = max((st for st in sts if st.s <= s + 1e-9), key=lambda st: st.s, default=sts[0])
    hi = min((st for st in sts if st.s >= s - 1e-9), key=lambda st: st.s, default=sts[-1])
    if hi.s - lo.s < 1e-9:
        return Station(s, lo.half_l, lo.half_r, lo.thick_l, lo.thick_r)
    f = (s - lo.s) / (hi.s - lo.s)
    g = lambda a, b: a + (b - a) * f     # noqa: E731
    return Station(s, g(lo.half_l, hi.half_l), g(lo.half_r, hi.half_r),
                   g(lo.thick_l, hi.thick_l), g(lo.thick_r, hi.thick_r))


def _slice(axis_ln: LineString, sts: _t.Sequence[Station], floors: _t.Sequence[float],
           s_a: float, s_b: float, ext_a: float, ext_b: float, sample: float, dem_z
           ) -> tuple[list[XY], list[Station], list[float], list[float]]:
    """The corridor re-based from ``s_a`` (the mouth, s = 0) toward
    ``s_b`` — either way along the axis — extended ``ext_a`` behind the
    mouth and ``ext_b`` beyond the far end (a closed end's floor overlap),
    stations every ``sample`` with the last ON the far end: axis points,
    stations (left / right swapped when travelling backwards), floors
    (the wall bottom interpolated over the original stations), grounds."""
    sign = 1.0 if s_b >= s_a else -1.0
    start = s_a - sign * ext_a
    end = s_b + sign * ext_b
    total = abs(end - start)
    ss = [sample * k for k in range(int(total // sample) + 1)]
    if total - ss[-1] > 1e-6:
        ss.append(total)
    orig_s = [st.s for st in sts]

    def floor_at(so: float) -> float:
        if so <= orig_s[0]:
            return floors[0]
        if so >= orig_s[-1]:
            return floors[-1]
        for k in range(len(orig_s) - 1):
            if orig_s[k] <= so <= orig_s[k + 1]:
                f = (so - orig_s[k]) / max(orig_s[k + 1] - orig_s[k], 1e-9)
                return floors[k] + (floors[k + 1] - floors[k]) * f
        return floors[-1]
    L = axis_ln.length
    out_axis: list[XY] = []
    out_st: list[Station] = []
    out_fl: list[float] = []
    out_gr: list[float] = []
    for s in ss:
        so = start + sign * s
        if so < 0.0 or so > L:
            e = axis_ln.interpolate(0.0 if so < 0.0 else L)
            q = axis_ln.interpolate(min(L, 1.0) if so < 0.0 else max(0.0, L - 1.0))
            ux, uy = e.x - q.x, e.y - q.y
            n = math.hypot(ux, uy) or 1.0
            d = (-so) if so < 0.0 else (so - L)
            p = (e.x + ux / n * d, e.y + uy / n * d)
        else:
            q = axis_ln.interpolate(so)
            p = (q.x, q.y)
        st = _interp_station(sts, so)
        if sign < 0:
            st = Station(s, st.half_r, st.half_l, st.thick_r, st.thick_l)
        else:
            st = Station(s, st.half_l, st.half_r, st.thick_l, st.thick_r)
        out_axis.append(p)
        out_st.append(st)
        out_fl.append(floor_at(so))
        gz = float(dem_z(p[0], p[1]))
        out_gr.append(gz)
    return out_axis, out_st, out_fl, out_gr


def _trench(axis: _t.Sequence[XY], sts: _t.Sequence[Station]) -> Polygon:
    """The region between the inner faces over the stations."""
    left: list[XY] = []
    right: list[XY] = []
    n = len(axis)
    for i, (p, st) in enumerate(zip(axis, sts)):
        a = axis[max(0, i - 1)]
        b = axis[min(n - 1, i + 1)]
        ux, uy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ux, uy) or 1.0
        nx, ny = -uy / L, ux / L
        left.append((p[0] + nx * st.half_l, p[1] + ny * st.half_l))
        right.append((p[0] - nx * st.half_r, p[1] - ny * st.half_r))
    poly = Polygon(left + list(reversed(right)))
    return poly if poly.is_valid else poly.buffer(0)


def _headroom(members: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
              trench: Polygon, floor_max: float, normal_min: float, grid: float, dem_z
              ) -> tuple[float | None, str, Polygon | None]:
    """Rule 5: the lowest rendered near-horizontal family face OVER the
    trench (a plan overlap of a grid cell at least, inside the trench
    shrunk by the identity spacing — the kerbs' own top caps touch the
    inner-face line and are not a ceiling) above its floor, minus the
    floor — and the WITNESS plate (RULINGS 2026-09-10w (c)): the placement
    and component that lowest face belongs to (``(None, "", None)`` = open
    air, no deck).

    THE WITNESS PLATE'S PLAN (spec §34 (9) (5) as corrected by owner
    RULINGS 2026-09-14be) is returned with it: the union in the airport
    frame of that component's own near-horizontal faces — UNCLIPPED by the
    trench, because the question it answers is where the cover ENDS.  The
    covering plate is what gives the corridor its headroom, so the plate
    whose edge is the corridor's full-depth point is this one, read here
    once and never re-derived downstream (``planar/structure_geometry.
    covered_start``)."""
    lowest: float | None = None
    witness = ""
    plate_polys = None
    inner = trench.buffer(-grid, **_MITRE)
    if inner.is_empty:
        inner = trench
    if inner.geom_type != "Polygon":
        inner = max((g for g in shapely.get_parts(inner) if g.geom_type == "Polygon"),
                    key=lambda g: g.area, default=trench)
    minx, miny, maxx, maxy = inner.bounds
    min_area = grid * grid
    for o in members:
        g = cache.geometry(o.resolved)
        if g is None:
            continue
        mat = _obj8.placement_affine(o.xy, o.heading_deg)
        v = g.vertices
        bounds = cache.component_bounds(o.resolved)
        comps = cache.components(o.resolved)
        for ci, comp in enumerate(comps):
            if ci >= bounds.shape[0]:
                break
            x0, x1, z0, z1 = bounds[ci].tolist()
            corners = [_obj8._to_frame(o.xy, o.heading_deg, x, z) for x in (x0, x1) for z in (z0, z1)]
            if max(c[0] for c in corners) < minx or min(c[0] for c in corners) > maxx \
                    or max(c[1] for c in corners) < miny or min(c[1] for c in corners) > maxy:
                continue
            # RULINGS 2026-09-10ad: the plate reads in the SAME seated
            # frame as the floor under it (a frame shift moves both, so
            # the headroom itself is unchanged by the seat)
            base = _seat_base(o, ((corners[0][0] + corners[3][0]) / 2.0,
                                  (corners[0][1] + corners[3][1]) / 2.0), dem_z)
            if base + comp.max_y <= floor_max:
                continue
            ny = _tri_normals_y(v, comp.tris)
            horiz = ny >= normal_min
            if not horiz.any():
                continue
            t = comp.tris[horiz]
            a, b, d, e, xoff, yoff = mat
            pts = v[t][:, :, [0, 2]]
            xs = a * pts[:, :, 0] + b * pts[:, :, 1] + xoff
            ys = d * pts[:, :, 0] + e * pts[:, :, 1] + yoff
            zs = base + v[t][:, :, 1].mean(axis=1)
            polys = shapely.polygons(np.stack([xs, ys], axis=2))
            hit = shapely.intersects(polys, inner) & shapely.is_valid(polys)
            for k in np.nonzero(hit)[0].tolist():
                z = float(zs[k])
                if z > floor_max + 1e-6 and (lowest is None or z < lowest) \
                        and polys[k].intersection(inner).area >= min_area:
                    lowest = z
                    witness = f"plate comp {ci} of {os.path.basename(o.path)} ({o.id})"
                    plate_polys = polys[shapely.is_valid(polys)]
    if lowest is None:
        return None, "", None
    plan = None
    if plate_polys is not None and len(plate_polys):
        plan = shapely.union_all(plate_polys)
        if plan.is_empty:
            plan = None
    return lowest - floor_max, witness, plan
