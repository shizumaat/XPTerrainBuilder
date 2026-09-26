"""THE WALL-BAND PLAN GEOMETRY (Law C rule 1, ``wall_corridors``): the
triangle-level readings a kerb wall's band is built from — plan segments
and polygons, straight runs, the band rectangle and its axis, the
densified face samples — and the family MERGE of parallel bands into one
wall.  Split out of ``wall_corridors`` under the 1,000-line law
(``tests/auto_patch_v2/test_model.py``); no law value lives here, only
geometric epsilons.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

import dataclasses as _dc

from . import bulk_geos as _bulk
from . import frame_entry as _fe
from ..model.frame import XY, rotated_rectangle
from . import obj8 as _obj8

#: A face's plan segment shorter than this is a point (a degenerate face).
_MIN_SEG_M = 0.02
#: A single SHEET (no plan thickness) is represented this wide so the ring
#: walker keeps it; its MEASURED thickness stays 0.
_SHEET_BAND_M = 0.05
_MITRE = dict(join_style="mitre", mitre_limit=2.0)
#: Face edges are densified this fine (the bottom profile reads the lowest
#: sample within this of a station).
_DENSIFY_M = 0.5


@_dc.dataclass(frozen=True)
class WallBand:
    """One kerb-wall band in the airport frame: its plan polygon (a thin
    rectangle), measured plan thickness (0 for a sheet), axis (a
    ``LineString`` along its length), bearing (0..180°), and its faces'
    vertices as ``(x, y, z_rendered, y_authored)`` rows (edges densified;
    the fourth column is the sample's height in the OBJECT's own frame —
    RULINGS 2026-09-10u, depth is read there, never against the terrain
    under a placement whose anchor plane may sit under it)."""

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
        merged = _fe.union([segs[k][0].buffer(t_max / 2.0, cap_style="flat", **_MITRE)
                            for k in idx], "wall_geometry.runs")
        parts = shapely.get_parts(merged)
        # §B.3 (#28): ONE envelope query + the same GEOS predicate over the
        # candidates, instead of |idx| x |parts| scalar ``intersects``;
        # runs come out per part in part order, members in ``idx`` order
        qi, pi = _bulk.intersecting_pairs([segs[k][0] for k in idx], parts)
        if qi.size == 0:
            continue
        cut = np.nonzero(np.diff(pi))[0] + 1
        for grp in np.split(qi, cut):
            runs.append([idx[q] for q in grp.tolist()])
    return runs


def _plan_polys(v: np.ndarray, tris: np.ndarray, mat: _t.Sequence[float],
                q: float = 0.0) -> list[Polygon]:
    """The valid plan polygons of ``tris`` in the frame.

    §51 (4) row 12 (TNCM).  The triangles are built STRAIGHT IN THE FRAME
    from a numpy affine, so they never pass through ``frame_entry.enter``
    — but they are placed pack geometry all the same, and §51 (2) (b)
    applies to them: the coordinates are snapped to ``q`` with the SAME
    ``rint(c / q) * q`` arithmetic before the rings are built, so the
    three platforms hold identical doubles here too.  The vectorised
    valid-and-area filter stays; its floor is the derived one grid cell.
    """
    if tris.shape[0] == 0:
        return []
    a, b, d, e, xoff, yoff = mat
    pts = v[tris][:, :, [0, 2]]
    xs = a * pts[:, :, 0] + b * pts[:, :, 1] + xoff
    ys = d * pts[:, :, 0] + e * pts[:, :, 1] + yoff
    if q > 0.0:
        xs = np.rint(xs / q) * q
        ys = np.rint(ys / q) * q
    polys = shapely.polygons(np.stack([xs, ys], axis=2))
    floor = q * q if q > 0.0 else 1e-9
    ok = shapely.is_valid(polys) & (shapely.area(polys) > floor)
    return [p for p, k in zip(polys, ok.tolist()) if k]


def _densified(v: np.ndarray, tris: np.ndarray, mat: _t.Sequence[float], base: float
               ) -> np.ndarray:
    """``(x, y, z_rendered, y_authored)`` rows: every triangle edge
    densified every ``_DENSIFY_M`` in the frame.  The fourth column is
    the sample's height in the OBJECT's own frame (``z_rendered - base``,
    RULINGS 2026-09-10u), carried per row so a merged band spanning two
    placements still states each sample's authored height."""
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
                rows.append((a * x + b * z + xoff, d * x + e * z + yoff, base + y, y))
    return np.asarray(rows, dtype=float).reshape(-1, 4)


def _band_polygon(segs: list[LineString]) -> tuple[Polygon | None, float]:
    """The band's plan polygon and measured thickness from a straight
    run's face segments: the run's minimum rotated rectangle (a wall's
    two faces and their joins: OTHH 77.8 × 0.54 m), or — a single sheet
    with no plan extent across — the line widened to ``_SHEET_BAND_M``
    (thickness 0)."""
    if not segs:
        return None, 0.0
    lines = unary_union(segs)
    rect = rotated_rectangle(lines)
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
    rect = rotated_rectangle(poly)
    c = list(rect.exterior.coords)[:4]
    if len(c) < 4:
        return 0.0, 0.0
    lens = [math.dist(c[i], c[(i + 1) % 4]) for i in range(4)]
    return max(lens), min(lens)


def _rect_axis(poly: Polygon) -> tuple[LineString, float, float] | None:
    """``(axis midline, length, bearing 0..180)`` of the plan rectangle."""
    rect = rotated_rectangle(poly)
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
        rect = rotated_rectangle(_fe.union([b.poly for b in members], "wall_geometry.bands"))
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


# ── the SEATED frame (RULINGS 2026-09-10ad) ──────────────────────────────

def _seat_base(o: _obj8.PlacedObject, xy: XY, dem_z) -> float:
    """The object's y = 0 plane in the SEATED frame at ``xy``: the rebake
    puts an object's zero on the LOCAL GROUND (09af-1, ``emit/rebake``'s
    ``base = anchor ground + agl``), so a component renders at ``dem(its
    own plan centroid) + agl + authored y``.  Law C reads depth THERE and
    never against ``anchor_z`` — a shared-datum pack (Aerosoft LEMD) puts
    ONE anchor at 596 m under components up to 4 km away where the terrain
    stands at 605, and every wall then reads 8-10 m "below ground", with a
    160-200 m ramp for a 2.6 m door (RULINGS 2026-09-10ad).  The pack's
    own anchor is the fallback where the DEM states nothing."""
    local = float(dem_z(xy[0], xy[1]))
    if math.isnan(local):
        return float(o.anchor_z + o.agl_m)
    return local + float(o.agl_m)
