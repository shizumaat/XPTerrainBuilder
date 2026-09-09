"""THE WALL CORRIDORS (RULINGS 2026-09-08m / 08n LAW C; spec ``docs/specs/
auto-patch-v2/othh-terminal-ramps-spec.md`` §6; law ``structures.toml
[cutout.wall_corridor]``): the pack models the terminal's road underpass,
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

THE READING, per ANCHOR FAMILY (``deck_signature.family_key``):

1. BANDS — a genuine component whose every triangle is vertical (``|n_y|
   < tunnel.object.plate_normal_y_min``), reaching ``min_wall_depth_m``
   under the local ground and up to within ``basin.contact_band_m`` of
   it, is a WALL BAND: its plan footprint is the union of its faces' plan
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
   so a 78 m quad still states its bottom everywhere).  LEVEL (the
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

Nothing numeric lives here but geometric epsilons; every law value is a
table argument.
"""
from __future__ import annotations

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
from . import obj8 as _obj8
from .deck_signature import family_key
from .tunnel_walls import Station, WallLines, midline, read_wall_lines, stations_along

__all__ = ["WallBand", "WallCorridorRecord", "WallCorridorStats", "read_wall_corridors",
           "ID_PREFIX", "CLASS_LEVEL", "CLASS_BAY", "CLASS_GARAGE"]

ID_PREFIX = "wall-corridor"
CLASS_LEVEL, CLASS_BAY, CLASS_GARAGE = "level", "bay", "garage_ramp"
#: A face's plan segment shorter than this is a point (a degenerate face).
_MIN_SEG_M = 0.02
#: A single SHEET (no plan thickness) is represented this wide so the ring
#: walker (``shapely.simplify`` at 0.01 m inside ``read_wall_lines``) keeps
#: it; its MEASURED thickness stays 0 (the rim law floors at the spacing).
_SHEET_BAND_M = 0.05
#: Face edges are densified this fine, and the bottom profile reads the
#: lowest sample within this of a station (a descending bottom is read
#: at most this far downhill: 0.5 m × the grade).
_DENSIFY_M = 0.5
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


@_dc.dataclass(frozen=True)
class WallBand:
    """One kerb-wall band in the airport frame: its plan polygon (a thin
    rectangle), measured plan thickness (0 for a sheet), axis (a
    ``LineString`` along its length), bearing (0..180°), and its faces'
    vertices as ``(x, y, z_rendered)`` rows (edges densified)."""

    owner: str
    resource: str
    comp: int
    poly: Polygon
    thickness_m: float
    axis: LineString
    length_m: float
    bearing_deg: float
    pts: np.ndarray
    top_z: float
    bottom_z: float


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
    read_s: float = 0.0


# ── bands ────────────────────────────────────────────────────────────────

def _tri_normals_y(v: np.ndarray, tris: np.ndarray) -> np.ndarray:
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    nrm = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(nrm, axis=1)
    ny = np.zeros(tris.shape[0])
    ok = ln > 1e-12
    ny[ok] = np.abs(nrm[ok, 1] / ln[ok])
    return ny


def _plan_segments(v: np.ndarray, tris: np.ndarray, mat: _t.Sequence[float]
                   ) -> list[LineString]:
    """The plan segment of each (vertical) triangle in the frame: the
    farthest pair of its three plan points."""
    return [seg for seg, _k in _plan_segments_indexed(v, tris, mat)]


def _plan_segments_indexed(v: np.ndarray, tris: np.ndarray, mat: _t.Sequence[float]
                           ) -> list[tuple[LineString, int]]:
    """:func:`_plan_segments` with each segment's triangle row."""
    a, b, d, e, xoff, yoff = mat
    pts = v[tris][:, :, [0, 2]]
    xs = a * pts[:, :, 0] + b * pts[:, :, 1] + xoff
    ys = d * pts[:, :, 0] + e * pts[:, :, 1] + yoff
    out = []
    for k in range(tris.shape[0]):
        P = [(float(xs[k, i]), float(ys[k, i])) for i in range(3)]
        best = max(((math.dist(P[i], P[j]), i, j) for i in range(3) for j in range(i + 1, 3)),
                   key=lambda t: t[0])
        if best[0] >= _MIN_SEG_M:
            out.append((LineString([P[best[1]], P[best[2]]]), k))
    return out


def _bearing(seg: LineString) -> float:
    (x0, y0), (x1, y1) = seg.coords[0], seg.coords[-1]
    return (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360.0) % 180.0


def _angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _straight_runs(segs: list[tuple[LineString, int]], parallel_deg: float, t_max: float
                   ) -> list[list[int]]:
    """A vertical component split into STRAIGHT RUNS: its plan segments
    clustered by bearing (within ``parallel_deg``) and, within a bearing,
    by proximity (segments closer than a wall's plan thickness ``t_max``
    are one wall: its two faces and their joins) — a welded U-shaped
    kerb yields its two side walls and its end wall apart.  Each run is
    a list of indices into ``segs``."""
    clusters: list[tuple[float, list[int]]] = []
    for k, (seg, _t) in enumerate(segs):
        b = _bearing(seg)
        for cl in clusters:
            if _angle_diff(b, cl[0]) <= parallel_deg:
                cl[1].append(k)
                break
        else:
            clusters.append((b, [k]))
    runs: list[list[int]] = []
    for _b, idx in clusters:
        merged = unary_union([segs[k][0].buffer(t_max / 2.0, cap_style="flat", **_MITRE)
                              for k in idx])
        for part in shapely.get_parts(merged):
            members = [k for k in idx if segs[k][0].intersects(part)]
            if members:
                runs.append(members)
    return runs


def _plan_polys(v: np.ndarray, tris: np.ndarray, mat: _t.Sequence[float]) -> list[Polygon]:
    """The valid plan polygons of ``tris`` in the frame."""
    if tris.shape[0] == 0:
        return []
    a, b, d, e, xoff, yoff = mat
    pts = v[tris][:, :, [0, 2]]
    xs = a * pts[:, :, 0] + b * pts[:, :, 1] + xoff
    ys = d * pts[:, :, 0] + e * pts[:, :, 1] + yoff
    polys = shapely.polygons(np.stack([xs, ys], axis=2))
    ok = shapely.is_valid(polys) & (shapely.area(polys) > 1e-9)
    return [p for p, k in zip(polys, ok.tolist()) if k]


def _densified(v: np.ndarray, tris: np.ndarray, mat: _t.Sequence[float], base: float
               ) -> np.ndarray:
    """``(x, y, z_rendered)`` rows: every triangle edge densified every
    ``_DENSIFY_M`` in the frame."""
    a, b, d, e, xoff, yoff = mat
    rows = []
    for t in tris.tolist():
        for i in range(3):
            p, q = v[t[i]], v[t[(i + 1) % 3]]
            L = float(np.linalg.norm(q - p))
            n = max(1, int(math.ceil(L / _DENSIFY_M)))
            for k in range(n + 1):
                f = k / n
                x, y, z = (p + (q - p) * f).tolist()
                rows.append((a * x + b * z + xoff, d * x + e * z + yoff, base + y))
    return np.asarray(rows, dtype=float).reshape(-1, 3)


def _band_polygon(segs: list[LineString]) -> tuple[Polygon | None, float]:
    """The band's plan polygon and measured thickness from a straight
    run's face segments: the run's minimum rotated rectangle (a wall's
    two faces and their joins: OTHH 77.8 × 0.54 m), or — a single sheet
    with no plan extent across — the line widened to ``_SHEET_BAND_M``
    (thickness 0)."""
    if not segs:
        return None, 0.0
    lines = unary_union(segs)
    rect = lines.minimum_rotated_rectangle
    if rect.geom_type == "Polygon" and rect.area > _MIN_SEG_M * _SHEET_BAND_M:
        L, W = _rect_sides(rect)
        if W >= _SHEET_BAND_M:
            return rect, W
    poly = lines.buffer(_SHEET_BAND_M / 2.0, cap_style="flat", **_MITRE)
    if poly.geom_type != "Polygon":
        poly = max((g for g in shapely.get_parts(poly) if g.geom_type == "Polygon"),
                   key=lambda g: g.area, default=None)
    return poly, 0.0


def _rect_sides(poly: Polygon) -> tuple[float, float]:
    rect = poly.minimum_rotated_rectangle
    c = list(rect.exterior.coords)[:4]
    if len(c) < 4:
        return 0.0, 0.0
    lens = [math.dist(c[i], c[(i + 1) % 4]) for i in range(4)]
    return max(lens), min(lens)


def _rect_axis(poly: Polygon) -> tuple[LineString, float, float] | None:
    """``(axis midline, length, bearing 0..180)`` of the plan rectangle."""
    rect = poly.minimum_rotated_rectangle
    if rect.geom_type != "Polygon":
        return None
    c = list(rect.exterior.coords)[:4]
    if len(c) < 4:
        return None
    lens = [math.dist(c[i], c[(i + 1) % 4]) for i in range(4)]
    li = max(range(4), key=lambda i: lens[i])
    p, q = c[li], c[(li + 1) % 4]
    r, s_ = c[(li + 3) % 4], c[(li + 2) % 4]
    a = ((p[0] + r[0]) / 2.0, (p[1] + r[1]) / 2.0)
    b = ((q[0] + s_[0]) / 2.0, (q[1] + s_[1]) / 2.0)
    brg = (math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) + 360.0) % 180.0
    return LineString([a, b]), float(lens[li]), float(brg)


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
    base = o.anchor_z + o.agl_m
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    v = g.vertices
    bands: list[WallBand] = []
    verticals: list[tuple[int, np.ndarray]] = []
    for ci, comp in enumerate(cache.genuine(o.resolved)):
        cx, cy = _obj8._to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        plane_ground = local - base
        if comp.min_y > plane_ground - wc.min_wall_depth_m:
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
            caps = _plan_polys(v, comp.tris[~vert], mat)
            if caps:
                cap_u = unary_union(caps)
                if cap_u.area > 1e-9:
                    _L, Wc = _rect_sides(cap_u.minimum_rotated_rectangle)
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

def _merge_walls(bands: list[WallBand], parallel_deg: float, t_max: float, gap_m: float
                 ) -> list[WallBand]:
    """Rule 1's family merge: parallel bands within ``t_max`` of each
    other laterally and ``gap_m`` along the axis are ONE wall — the
    union's plan rectangle, the samples concatenated."""
    n = len(bands)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            A, B = bands[i], bands[j]
            if _angle_diff(A.bearing_deg, B.bearing_deg) > parallel_deg:
                continue
            brg = math.radians(A.bearing_deg)
            u = (math.sin(brg), math.cos(brg))
            nrm = (-u[1], u[0])
            ca, cb = A.poly.centroid, B.poly.centroid
            lateral = abs((cb.x - ca.x) * nrm[0] + (cb.y - ca.y) * nrm[1])
            if lateral > t_max:
                continue
            lo, hi, ov = _overlap_along(u, A, B)
            if ov < -gap_m:
                continue
            parent[find(i)] = find(j)
    groups: dict[int, list[WallBand]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(bands[i])
    out: list[WallBand] = []
    for members in groups.values():
        if len(members) == 1:
            out.append(members[0])
            continue
        members.sort(key=lambda b: -b.length_m)
        first = members[0]
        rect = unary_union([b.poly for b in members]).minimum_rotated_rectangle
        if rect.geom_type != "Polygon":
            out.append(first)
            continue
        L, W = _rect_sides(rect)
        ra = _rect_axis(rect)
        if ra is None:
            out.append(first)
            continue
        axis, length, brg = ra
        pts = np.concatenate([b.pts for b in members])
        out.append(WallBand(first.owner, first.resource, first.comp, rect, float(W), axis,
                            length, brg, pts, float(pts[:, 2].max()), float(pts[:, 2].min())))
    return out


def _overlap_along(u: XY, a: WallBand, b: WallBand) -> tuple[float, float, float]:
    """The bands' extents projected on direction ``u``: ``(lo, hi,
    overlap)`` of their intersection."""
    def span(band: WallBand) -> tuple[float, float]:
        ps = [(x * u[0] + y * u[1]) for x, y in band.poly.exterior.coords]
        return min(ps), max(ps)
    a0, a1 = span(a)
    b0, b1 = span(b)
    lo, hi = max(a0, b0), min(a1, b1)
    return lo, hi, hi - lo


def _floor_profile(bands: _t.Sequence[WallBand], axis_ln: LineString, ss: _t.Sequence[float],
                   window: float) -> list[float | None]:
    """Rule 3: the lowest rendered vertex of the bands' faces within
    ``±window`` of each station along the axis (``None`` where none)."""
    pts = np.concatenate([b.pts for b in bands])
    s_of = np.asarray([axis_ln.project(Point(x, y)) for x, y in pts[:, :2].tolist()])
    out: list[float | None] = []
    for s in ss:
        sel = np.abs(s_of - s) <= window
        out.append(float(pts[sel, 2].min()) if sel.any() else None)
    # fill the gaps from the neighbours
    for i, z in enumerate(out):
        if z is None:
            left = next((out[j] for j in range(i - 1, -1, -1) if out[j] is not None), None)
            right = next((out[j] for j in range(i + 1, len(out)) if out[j] is not None), None)
            out[i] = left if right is None else (right if left is None else (left + right) / 2.0)
    return out


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
              trench: Polygon, floor_max: float, normal_min: float, grid: float
              ) -> float | None:
    """Rule 5: the lowest rendered near-horizontal family face OVER the
    trench (a plan overlap of a grid cell at least, inside the trench
    shrunk by the identity spacing — the kerbs' own top caps touch the
    inner-face line and are not a ceiling) above its floor, minus the
    floor (``None`` = open air)."""
    lowest: float | None = None
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
        base = o.anchor_z + o.agl_m
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
    return None if lowest is None else lowest - floor_max


def read_wall_corridors(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                        cache: _obj8.ResourceCache, law: Law
                        ) -> tuple[list[WallCorridorRecord], WallCorridorStats]:
    """Every wall corridor the pack's kerb-wall families state (module
    doc); the stats name every refusal."""
    t0 = time.perf_counter()
    stats = WallCorridorStats()
    wc = law.tables.structures.cutout.wall_corridor
    ob = law.tables.structures.tunnel.object
    bl = law.tables.structures.basin
    co = law.tables.structures.cutout
    grid = law.tables.emit.identity.min_distinct_spacing_m
    dem_z = airport.dem.z
    to_ll = airport.frame.transformers()[1]
    fams: dict[tuple, list[_obj8.PlacedObject]] = {}
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
        by_id = {o.id: o for o in members}
        for o in members:
            bs, verts = _bands_of(o, cache, dem_z, law)
            bands.extend(bs)
            if verts:
                g = cache.geometry(o.resolved)
                mat = _obj8.placement_affine(o.xy, o.heading_deg)
                comps = cache.genuine(o.resolved)
                for ci, mask in verts:
                    faces.extend(_plan_segments(g.vertices, comps[ci].tris[mask], mat))
        if len(bands) < 2:
            continue
        bands = _merge_walls(bands, wc.parallel_max_deg, ob.wall_face_max_thickness_m,
                             wc.merge_gap_m)
        stats.families += 1
        stats.bands += len(bands)
        face_tree = STRtree(faces) if faces else None
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
                floors = _floor_profile((A, B), axis_ln, orig_s, _DENSIFY_M)
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
                if max(depths) < wc.min_wall_depth_m:
                    stats.refused.append(f"{name} at {site}: the wall bottom reaches only "
                                         f"{max(depths):.2f} m under the ground (< min_wall_depth_m "
                                         f"{wc.min_wall_depth_m})")
                    continue
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
                closed = [c >= wc.end_cap_cover_min for c in covers]
                width = 2.0 * sum((s.half_l + s.half_r) / 2.0 for s in sts) / len(sts)
                thick = sum((s.thick_l + s.thick_r) / 2.0 for s in sts) / len(sts)
                trench0 = _trench(axis, sts)
                # RULE 5: headroom over the trench
                headroom = _headroom(members, cache, trench0, zmax, ob.plate_normal_y_min, grid)
                if headroom is not None and headroom < wc.min_headroom_m:
                    stats.refused.append(f"{name} at {site}: headroom {headroom:.2f} m over the floor "
                                         f"(< min_headroom_m {wc.min_headroom_m}): a covered slot, "
                                         f"not a corridor")
                    continue
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
                                        f"authored; the deep end closed by the garage",)))
                elif closed[0] and closed[1]:
                    stats.refused.append(f"{name} at {site}: closed at both ends (covers "
                                         f"{covers[0]:.0%} / {covers[1]:.0%}): no mouth — a sunken "
                                         f"yard between four kerbs, not a corridor")
                    continue
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
                                        f"({covers[m]:.0%} covered), a ramp beyond the open end",)))
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
                                            f"midpoint, a ramp beyond its end",)))
                for r in recs:
                    out.append(r)
                    stats.by_class[r.cls] = stats.by_class.get(r.cls, 0) + 1
                stats.corridors += 1 if recs else 0
    out.sort(key=lambda r: r.id)
    stats.read_s = time.perf_counter() - t0
    return out, stats
