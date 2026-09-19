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
import time
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from . import frame_entry as _fe
from . import obj8 as _obj8
from .below_zero import read_below_zero, read_wall_height
from .wall_corridor_probe import (ROAD_ROLES, MouthRoad, _floor_road, _floor_slab,
                                  _RoadLevels, mouth_roads)
from .wall_geometry import (WallBand, _DENSIFY_M, _seat_base, _MITRE, _MIN_SEG_M, _SHEET_BAND_M, _angle_diff, _band_polygon,
                            _bearing, _densified, _merge_walls, _overlap_along,
                            _plan_polys, _plan_segments, _plan_segments_indexed,
                            _rect_axis, _rect_sides, _straight_runs, _tri_normals_y)
from .deck_signature import family_key
from .tunnel_walls import Station, WallLines, midline, read_wall_lines, stations_along

__all__ = ["WallBand", "WallCorridorRecord", "WallCorridorStats", "read_wall_corridors",
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
        if comp.max_y < plane_ground - bl.contact_band_m:
            continue                    # buried: never reaches the ground
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


def read_wall_corridors(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                        cache: _obj8.ResourceCache, law: Law, classification: _t.Any = None,
                        measure: bool = False
                        ) -> tuple[list[WallCorridorRecord], WallCorridorStats]:
    """Every wall corridor the pack's kerb-wall families state (module
    doc); the stats name every refusal and, per CANDIDATE, each of the
    three admission clauses with its witness (``stats.admission``).
    ``classification``, when given, adds the patch's own road ribbons to
    the mouth-road test (10w (b)); without it only the OSM ways are
    read.  ``measure`` (the ``--stage structures`` replay alone) adds the
    RULINGS 2026-09-10ab reading of the two round-4 discriminators per
    candidate (``stats.floor_probe``) — a measurement, never a gate, and
    never a cost in a build."""
    t0 = time.perf_counter()
    stats = WallCorridorStats()
    wc = law.tables.structures.cutout.wall_corridor
    ob = law.tables.structures.tunnel.object
    bl = law.tables.structures.basin
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    dem_z = airport.dem.z
    to_ll = airport.frame.transformers()[1]
    # RULINGS 2026-09-10ad: (b'') is DELETED (refuted in 10z/10ab); the
    # roads survive as the round-4 PROBE's reading alone (``measure``)
    roads = mouth_roads(airport, classification) if measure else []
    road_tree = STRtree([r.geom for r in roads]) if roads else None
    # RULINGS 2026-09-10ab (i): the LEVEL reader for a mouth road (the
    # replay's measurement only)
    levels = _RoadLevels(airport, law) if measure else None
    #: the per-placement below-zero walk, memoised across candidates
    bz_store: dict = {}
    fams: dict[tuple, list[_obj8.PlacedObject]] = {}
    # MEASURED ORDER-DEPENDENT AND NOT FIXED HERE (lane v2othhdet, dry
    # OTHH pair): this intake's order decides the family members' order,
    # which decides which band of a pair is A (and so which RESOURCE
    # names the corridor) and which pairs are admitted at all.  Sorting
    # it by ``object_cut.placement_key`` moved OTHH's reading
    # 73 -> 75 wall corridors (Bridge_02 ids replacing Bridge_06 ids at
    # the same sites, ``OTHH_Terminal_Parking_006@0`` admitted,
    # ``..._VCN_004@0/a,b,@2/a,b,@3`` gone) — a GEOMETRY change, not a
    # relabelling, and neither order is more right than the other until
    # the band-pair choice is ruled.  Reported, not attempted: the sorted
    # intake is arbitrary in exactly the way the DSF order is.
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        stats.placements += 1
        vmin = cache.y_range(o.resolved)[0]
        if vmin == math.inf or vmin > -wc.min_wall_depth_m:
            continue
        fams.setdefault(family_key(o), []).append(o)
    out: list[WallCorridorRecord] = []
    k_by_res: dict[str, int] = {}
    for fk, members in sorted(fams.items(), key=lambda kv: kv[0]):
        bands: list[WallBand] = []
        faces: list[LineString] = []
        faces_low: list[LineString] = []
        by_id = {o.id: o for o in members}
        for o in members:
            bs, verts = _bands_of(o, cache, dem_z, law)
            bands.extend(bs)
            if verts:
                g = cache.geometry(o.resolved)
                mat = _obj8.placement_affine(o.xy, o.heading_deg)
                comps = cache.genuine(o.resolved)
                for ci, mask in verts:
                    rows = comps[ci].tris[mask]
                    faces.extend(_plan_segments(g.vertices, rows, mat))
                    # RULINGS 2026-09-10af: the BELOW-ZERO faces alone — a
                    # foundation skirt CLOSES its pair's ends with more of
                    # itself (the building's other two sides are skirted
                    # too); a corridor's trench OPENS at its mouth.  The
                    # 08n end-cap test reads EVERY vertical face, so a wall
                    # standing over a trench closes an end that is open
                    # below the ground.
                    low = (g.vertices[rows][:, :, 1].min(axis=1) <= -wc.min_wall_depth_m
                           if measure else np.zeros(rows.shape[0], dtype=bool))
                    if low.any():
                        faces_low.extend(_plan_segments(g.vertices, rows[low], mat))
        if len(bands) < 2:
            continue
        bands = _merge_walls(bands, wc.parallel_max_deg, ob.wall_face_max_thickness_m,
                             wc.merge_gap_m)
        stats.families += 1
        stats.bands += len(bands)
        face_tree = STRtree(faces) if faces else None
        low_tree = STRtree(faces_low) if faces_low else None
        fam_name = f"{fk[0]:.3f},{fk[1]:.3f},{fk[2]:.3f}"
        # RULE 2: the pairs
        for i in range(len(bands)):
            for j in range(i + 1, len(bands)):
                A, B = bands[i], bands[j]
                dd = abs(A.bearing_deg - B.bearing_deg)
                dd = min(dd, 180.0 - dd)
                if dd > wc.parallel_max_deg:
                    continue
                gap = A.poly.distance(B.poly)
                if not (wc.min_width_m <= gap <= wc.max_width_m):
                    continue
                brg = math.radians(A.bearing_deg)
                u = (math.sin(brg), math.cos(brg))
                lo, hi, ov = _overlap_along(u, A, B)
                if ov < wc.min_wall_length_m:
                    continue
                between = unary_union([A.poly, B.poly]).convex_hull.difference(
                    unary_union([A.poly.buffer(grid), B.poly.buffer(grid)]))
                third = False
                for k, C in enumerate(bands):
                    if k in (i, j) or not C.poly.intersects(between):
                        continue
                    _l, _h, ov3 = _overlap_along(u, A, C)
                    if C.poly.intersection(between).area > 1e-6 and ov3 >= wc.min_wall_length_m:
                        third = True
                        break
                if third:
                    continue
                stats.pairs += 1
                o0 = by_id[A.owner]
                name = os.path.basename(A.resource)
                la, lo_ = to_ll(*A.poly.centroid.coords[0])
                site = f"{la:.6f},{lo_:.6f}"
                # THE AFFORDANCE GATE (RULINGS 2026-09-10ap, closing
                # 10ac-1 as (B)): LAW C — kerb-wall corridors AND garage
                # ramps — is an AIRPORT-LEVEL affordance a pack earns by
                # a sim read (``law/airports.toml``, on at OTHH alone).
                # Checked FIRST, before (a): no geometry of this pair is
                # read where the law is off, and every candidate says so.
                #
                # §33 (6) A's RETIREMENT OF THIS KEY IS REFUTED (lane
                # `v2objcut`, 2026-09-15, one dry VHHH replay).  The
                # crested-wall signature — solids under the object's own
                # zero WITH a crest plate ``plate_min_height_m`` above it
                # — admits an ordinary BUILDING, because a building has a
                # roof: at VHHH it took wall corridors 0 -> 116 (bay 28,
                # level 88), every one of them inside ``CITY2.obj``, a
                # city-block object off the field whose foundation walls
                # descend 6.4-8.5 m.  No depth threshold repairs it:
                # OTHH's own admitted bays are 1.35 m deep.  This is the
                # 10ap finding at a THIRD airport, so the honest switch
                # stands and §33 (6) A is an intent question for the
                # owner, not a mechanism.
                if not law.affordances.kerb_wall_corridors:
                    stats.admission.append(
                        f"candidate {name} bands {A.comp}/{B.comp} at {site}: "
                        f"law off for {law.icao or '(no airport)'}")
                    continue
                plate = unary_union([A.poly, B.poly])
                walls = read_wall_lines(plate, law)
                if isinstance(walls, str):
                    stats.refused.append(f"{name} at {site}: the pair {A.comp}/{B.comp} is not "
                                         f"two readable bands ({walls})")
                    continue
                if walls.kind != "II":
                    stats.refused.append(f"{name} at {site}: the pair {A.comp}/{B.comp} reads as "
                                         f"{walls.kind}, not two bands")
                    continue
                axis = midline(walls, ob.wall_sample_m)
                sts = stations_along(axis, walls, ob.wall_sample_m, grid)
                if len(sts) < 2:
                    stats.refused.append(f"{name} at {site}: the inner faces leave no station")
                    continue
                axis_ln = LineString(axis)
                orig_s = [st.s for st in sts]
                floors, floors_y = _floor_profile((A, B), axis_ln, orig_s, _DENSIFY_M)
                # RULINGS 2026-09-10ad: ONE SEAT PER CORRIDOR.  The pair is
                # one body (its kerbs and the deck over them weld) and the
                # rebake seats a body on the ground under it, so the floor
                # is the AUTHORED wall bottom under the ground at the
                # corridor's own plan centroid — not each band's own
                # reading (the two kerbs of a corridor on sloping ground
                # would seat centimetres apart) and never the pack's
                # anchor plane.
                seat_z = _seat_base(o0, plate.centroid.coords[0], dem_z)
                floors = [seat_z + y for y in floors_y]
                grounds = [float(dem_z(*axis_ln.interpolate(s).coords[0])) for s in orig_s]
                if any(math.isnan(z) for z in grounds):
                    stats.refused.append(f"{name} at {site}: no DEM along the corridor")
                    continue
                # RULE 3: level or descending
                zmin, zmax = min(floors), max(floors)
                depths = [g - z for g, z in zip(grounds, floors)]
                grades = [abs(floors[k + 1] - floors[k]) / max(orig_s[k + 1] - orig_s[k], 1e-9)
                          for k in range(len(floors) - 1)]
                max_grade = max(grades) if grades else 0.0
                if max_grade > wc.max_authored_grade:
                    stats.refused.append(f"{name} at {site}: the wall bottom runs at "
                                         f"{100.0 * max_grade:.1f} % between stations (> "
                                         f"max_authored_grade {100.0 * wc.max_authored_grade:.0f} %)")
                    continue
                # RULINGS 2026-09-10u: the corridor is admitted on AUTHORED
                # depth — the wall bottom under the OBJECT'S OWN local zero
                # at some station.  ``depths`` (against the DEM) stays the
                # MEASUREMENT of an admitted corridor (the mouth at grade,
                # the notes, ``depth_m``), never the admission.
                authored_depths = [-y for y in floors_y]
                head = f"candidate {name} bands {A.comp}/{B.comp} at {site}"
                if max(authored_depths) < wc.min_wall_depth_m:
                    msg = (f"{name} at {site}: the wall bottom is authored at y "
                           f"{min(floors_y):+.2f} at its deepest station — never "
                           f"min_wall_depth_m {wc.min_wall_depth_m} under the "
                           f"object's own zero (10u)")
                    stats.refused.append(msg)
                    stats.admission.append(
                        f"{head}: (a) REFUSED — deepest authored y {min(floors_y):+.2f} m, "
                        f"never {wc.min_wall_depth_m} m under the object's zero; (b'') not read")
                    continue
                clause_a = (f"(a) admitted — wall bottom authored {max(authored_depths):.2f} m "
                            f"under the object's zero")
                # RULINGS 2026-09-10af — (d) THE NARROW-CUT TEST: a
                # corridor is a road-width cut in a building that is
                # otherwise above its own zero; a placement whose whole
                # bottom stands below zero is FOUNDATIONS (the author's
                # slope affordance) and is left to its seat.
                bz = (read_below_zero([by_id[A.owner], by_id[B.owner]], cache,
                                      wc.min_wall_depth_m, plate.centroid.coords[0],
                                      ob.wall_face_max_thickness_m, store=bz_store)
                      if measure else None)
                cut_w, foot_w = (0.0, 0.0) if bz is None else bz.widths(u)
                frac = 0.0 if bz is None else bz.fraction
                # RULINGS 2026-09-10ao — THE WALL'S HEIGHT ABOVE THE
                # OBJECT'S ZERO: a kerb wall rises from its floor to the
                # deck it carries and no further; a cargo shed's
                # foundation sheet is the bottom of a BUILDING wall that
                # rises to a roof.  Read per band, in the object's own
                # authored frame (never the terrain).
                ha = (read_wall_height(by_id[A.owner], cache, A.comp, grid,
                                       ob.wall_face_max_thickness_m, store=bz_store)
                      if measure else None)
                hb = (read_wall_height(by_id[B.owner], cache, B.comp, grid,
                                       ob.wall_face_max_thickness_m, store=bz_store)
                      if measure else None)
                h_own = max([h.own_m for h in (ha, hb) if h is not None] or [0.0])
                h_step = max([h.step_m for h in (ha, hb) if h is not None] or [0.0])
                h_conn = max([h.connected_m for h in (ha, hb) if h is not None] or [0.0])
                h_conn_min = min([h.connected_m for h in (ha, hb) if h is not None] or [0.0])
                nc_row: dict | None = None
                if measure:
                    nc_row = {"airport": airport.icao, "resource": name,
                              "bands": f"{A.comp}/{B.comp}", "site": site,
                              "spacing_m": round(gap, 2),
                              "width_m": None, "perimeter_m": 0.0 if bz is None
                              else round(bz.perimeter_m, 1),
                              "below_perimeter_m": 0.0 if bz is None
                              else round(bz.below_perimeter_m, 1),
                              "fraction": round(frac, 3),
                              "fraction_total": 0.0 if bz is None
                              else round(bz.fraction_total, 3),
                              "total_perimeter_m": 0.0 if bz is None
                              else round(bz.total_perimeter_m, 1),
                              "total_below_perimeter_m": 0.0 if bz is None
                              else round(bz.total_below_perimeter_m, 1),
                              "cut_width_m": round(cut_w, 1),
                              "footprint_width_m": round(foot_w, 1),
                              "width_ratio": round(cut_w / foot_w, 3) if foot_w > 0 else None,
                              "site_area_m2": 0.0 if bz is None
                              else round(bz.site_area_m2, 1),
                              "site_thickness_m": 0.0 if bz is None
                              else round(bz.site_thickness_m, 2),
                              "axis_inside_frac": 0.0 if bz is None else round(
                                  axis_ln.intersection(bz.footprint).length
                                  / max(axis_ln.length, 1e-9), 3),
                              "end_cover": [0.0, 0.0], "end_cover_below": [0.0, 0.0],
                              # RULINGS 2026-09-10ao — the wall's height
                              # above the object's zero, per band and for
                              # the wall connected above it
                              "wall_own_m": round(h_own, 2),
                              "wall_step_m": round(h_step, 2),
                              "wall_connected_m": round(h_conn, 2),
                              "wall_connected_min_m": round(h_conn_min, 2),
                              "wall_a_m": None if ha is None else round(ha.connected_m, 2),
                              "wall_b_m": None if hb is None else round(hb.connected_m, 2),
                              "wall_witness": (("A: " + ha.witness) if ha else "")
                                              + (("; B: " + hb.witness) if hb else ""),
                              "admitted": False}
                    stats.narrow_cut.append(nc_row)
                descending = (zmax - zmin) >= wc.min_wall_depth_m
                # RULE 4: the ends
                def end_line(k: int) -> tuple[XY, XY]:
                    p = axis[0] if k == 0 else axis[-1]
                    q = axis[1] if k == 0 else axis[-2]
                    ux, uy = p[0] - q[0], p[1] - q[1]
                    L = math.hypot(ux, uy) or 1.0
                    nx, ny_ = -uy / L, ux / L
                    st = sts[0] if k == 0 else sts[-1]
                    return ((p[0] + nx * st.half_l, p[1] + ny_ * st.half_l),
                            (p[0] - nx * st.half_r, p[1] - ny_ * st.half_r))
                covers = [_end_cover(end_line(k), faces, face_tree, ob.end_cap_open_m)
                          for k in (0, 1)]
                covers_low = [_end_cover(end_line(k), faces_low, low_tree,
                                         ob.end_cap_open_m) for k in (0, 1)] \
                    if measure else [0.0, 0.0]
                closed = [c >= wc.end_cap_cover_min for c in covers]
                width = 2.0 * sum((s.half_l + s.half_r) / 2.0 for s in sts) / len(sts)
                thick = sum((s.thick_l + s.thick_r) / 2.0 for s in sts) / len(sts)
                if nc_row is not None:
                    nc_row["width_m"] = round(width, 2)
                    nc_row["end_cover"] = [round(covers[0], 3), round(covers[1], 3)]
                    nc_row["end_cover_below"] = [round(covers_low[0], 3),
                                                 round(covers_low[1], 3)]
                trench0 = _trench(axis, sts)
                # THE MOUTHS: the open ends (a garage's shallow end).  A
                # pair closed at BOTH ends is a sunken yard, not a corridor.
                # (RULINGS 2026-09-10ad: the 10z (b'') groundside-mouth
                # clause is DELETED — it separated nothing, 10ab.)
                if descending:
                    deep0 = 0 if floors[0] <= floors[-1] else 1
                    mouth_ks = [1 - deep0]
                else:
                    mouth_ks = [k for k in (0, 1) if not closed[k]]
                if not mouth_ks:
                    msg = (f"{name} at {site}: closed at both ends (covers {covers[0]:.0%} / "
                           f"{covers[1]:.0%}): no mouth — a sunken yard between four kerbs, not "
                           f"a corridor")
                    stats.refused.append(msg)
                    stats.admission.append(f"{head}: {clause_a}; REFUSED — no mouth (both "
                                           f"ends closed)")
                    continue
                # RULINGS 2026-09-10ab: the two discriminators MEASURED —
                # the REPLAY's instrument (``--stage structures``), never
                # a gate and never a build cost: neither separates LEMD
                # from OTHH (spec §12c), so nothing reads them in law.
                if measure:
                    mouth_pts = [(k, axis[0] if k == 0 else axis[-1],
                                  floors[0] if k == 0 else floors[-1]) for k in mouth_ks]
                    fr = _floor_road(mouth_pts, roads, road_tree,
                                     wc.corridor_road_level_m, levels)
                    slab_cover, slab_w = _floor_slab(
                        members, cache, trench0, axis_ln, orig_s, floors,
                        wc.corridor_floor_slab_max_thickness_m,
                        wc.corridor_floor_slab_tol_m, ob.plate_normal_y_min, dem_z)
                    corridor_len = float(orig_s[-1] - orig_s[0])
                    stats.floor_probe.append({
                        "airport": airport.icao, "candidate": head,
                        "resource": name, "bands": f"{A.comp}/{B.comp}", "site": site,
                        "length_m": round(corridor_len, 1),
                        "floor_min_z": round(zmin, 2), "floor_max_z": round(zmax, 2),
                        "mouth_floor_z": None if fr is None else round(fr.floor_z, 2),
                        "road_level_z": None if fr is None else round(fr.level_z, 2),
                        "road_dist_m": None if fr is None else round(fr.distance_m, 1),
                        "delta_m": None if fr is None else round(fr.delta_m, 2),
                        "road_source": "" if fr is None else fr.source,
                        "road_witness": "" if fr is None else fr.witness,
                        "within_tol": bool(fr is not None and abs(fr.delta_m)
                                           <= wc.corridor_floor_road_tol_m),
                        "ramp_reachable": bool(fr is not None and abs(fr.delta_m)
                                               <= wc.max_ramp_grade * max(corridor_len, 1e-9)),
                        "slab_cover": round(slab_cover, 3),
                        "slab": bool(slab_cover >= wc.corridor_floor_slab_cover_min),
                        "slab_witness": slab_w,
                    })
                # RULE 5: headroom over the trench (a MEASUREMENT plus the
                # covered-slot gate; OPEN AIR PASSES — 10z deleted the deck
                # clause: seven OTHH corridors carry no plate of their own).
                headroom, deck_w, plate_plan = _headroom(members, cache, trench0, zmax,
                                                         ob.plate_normal_y_min, grid, dem_z)
                if headroom is not None and headroom < wc.min_headroom_m:
                    msg = (f"{name} at {site}: headroom {headroom:.2f} m over the floor "
                           f"(< min_headroom_m {wc.min_headroom_m}): a covered slot, "
                           f"not a corridor")
                    stats.refused.append(msg)
                    stats.admission.append(f"{head}: {clause_a}; headroom "
                                           f"{headroom:.2f} m REFUSED under min_headroom_m "
                                           f"{wc.min_headroom_m} ({deck_w})")
                    continue
                if nc_row is not None:
                    nc_row["admitted"] = True
                stats.admission.append(
                    f"{head}: {clause_a}; headroom "
                    + ("open air" if headroom is None else f"{headroom:.2f} m ({deck_w})")
                    + " -> ADMITTED")
                notes_common = (
                    f"bands {A.comp} ({A.thickness_m:.2f} m, {A.length_m:.1f} m) / {B.comp} "
                    f"({B.thickness_m:.2f} m, {B.length_m:.1f} m) of {name}, inner faces {gap:.2f} m "
                    f"apart, overlap {ov:.1f} m; wall bottom {zmin:.2f}..{zmax:.2f} (ground "
                    f"{min(grounds):.2f}..{max(grounds):.2f}), max authored grade "
                    f"{100.0 * max_grade:.1f} %; ends cover {covers[0]:.0%}/{covers[1]:.0%}; headroom "
                    f"{'open air' if headroom is None else f'{headroom:.2f} m'}",)
                k_res = k_by_res.get(A.resource, 0)
                k_by_res[A.resource] = k_res + 1
                base_id = f"{ID_PREFIX}:{name}@{k_res}"
                objects_ids = tuple(sorted({A.owner, B.owner}))
                anchor = (o0.xy, float(o0.anchor_z), float(o0.agl_m))
                overlap = co.floor_overlap_m
                recs: list[WallCorridorRecord] = []
                if descending:
                    # the deep end is the mouth (closed by the garage), the
                    # shallow end must meet the ground
                    deep = 0 if floors[0] <= floors[-1] else 1
                    shallow_depth = depths[-1] if deep == 0 else depths[0]
                    if shallow_depth > bl.contact_band_m:
                        stats.refused.append(f"{name} at {site}: the wall bottom descends "
                                             f"{zmax - zmin:.2f} m but its shallow end lies "
                                             f"{shallow_depth:.2f} m under the ground (> contact_band_m "
                                             f"{bl.contact_band_m}): no mouth at grade")
                        continue
                    s_a, s_b = (orig_s[0], orig_s[-1]) if deep == 0 else (orig_s[-1], orig_s[0])
                    ax2, st2, fl2, gr2 = _slice(axis_ln, sts, floors, s_a, s_b, overlap, 0.0,
                                                ob.wall_sample_m, dem_z)
                    t_end = walls.end_thickness_m[deep] or thick
                    recs.append(WallCorridorRecord(
                        base_id, A.resource, objects_ids, fam_name, CLASS_GARAGE, tuple(ax2),
                        tuple(st2), tuple(fl2), tuple(gr2), float(st2[-1].s), width, True, False,
                        t_end, 0.0, plate, _trench(ax2, st2), unary_union([plate, trench0]),
                        *anchor, headroom, max_grade, "",
                        notes_common + (f"garage ramp (2026-09-08n): the wall bottom descends "
                                        f"{zmax - zmin:.2f} m from the grade end to the garage, cut as "
                                        f"authored; the deep end closed by the garage",),
                        plate_plan=plate_plan))
                elif closed[0] or closed[1]:
                    m = 0 if closed[0] else 1
                    s_a, s_b = (orig_s[0], orig_s[-1]) if m == 0 else (orig_s[-1], orig_s[0])
                    ax2, st2, fl2, gr2 = _slice(axis_ln, sts, floors, s_a, s_b, overlap, 0.0,
                                                ob.wall_sample_m, dem_z)
                    recs.append(WallCorridorRecord(
                        base_id, A.resource, objects_ids, fam_name, CLASS_BAY, tuple(ax2),
                        tuple(st2), tuple(fl2), tuple(gr2), float(st2[-1].s), width, True, False,
                        thick, 0.0, plate, _trench(ax2, st2), unary_union([plate, trench0]),
                        *anchor, headroom, max_grade, "",
                        notes_common + (f"closed bay: end {m} closed by a family face "
                                        f"({covers[m]:.0%} covered), a ramp beyond the open end",),
                        plate_plan=plate_plan))
                else:
                    # two capless halves meeting at the midpoint, each
                    # climbing beyond its own end
                    s_mid = (orig_s[0] + orig_s[-1]) / 2.0
                    for tag, s_b in (("a", orig_s[0]), ("b", orig_s[-1])):
                        ax2, st2, fl2, gr2 = _slice(axis_ln, sts, floors, s_mid, s_b, 0.0, 0.0,
                                                    ob.wall_sample_m, dem_z)
                        if len(ax2) < 2:
                            continue
                        other = f"{base_id}/{'b' if tag == 'a' else 'a'}"
                        recs.append(WallCorridorRecord(
                            f"{base_id}/{tag}", A.resource, objects_ids, fam_name, CLASS_LEVEL,
                            tuple(ax2), tuple(st2), tuple(fl2), tuple(gr2), float(st2[-1].s), width,
                            False, False, 0.0, 0.0, plate, _trench(ax2, st2),
                            unary_union([plate, trench0]), *anchor, headroom, max_grade, other,
                            notes_common + (f"level corridor open at both ends: half {tag} from the "
                                            f"midpoint, a ramp beyond its end",),
                            plate_plan=plate_plan))
                for r in recs:
                    out.append(r)
                    stats.by_class[r.cls] = stats.by_class.get(r.cls, 0) + 1
                stats.corridors += 1 if recs else 0
    out.sort(key=lambda r: r.id)
    stats.read_s = time.perf_counter() - t0
    return out, stats
