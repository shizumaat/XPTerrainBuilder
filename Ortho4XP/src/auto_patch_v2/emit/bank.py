"""THE BANK at the patch boundary (owner RULINGS 2026-09-09e; spec
``auto-patch-v2/design-surface-spec.md`` §9).

§8.4 MEASURED that Ortho4XP's mesh does NOT blend from the patch boundary
to the DEM: it drapes the raw DEM right outside the constrained ring, so a
patch whose outer ring stands 16.6 m off the terrain builds a 16.8 m cliff
ONE TRIANGLE wide.  The owner's answer is a BANK.

    Outside every patch-boundary ring the patch emits a BANK FOOT ring ON
    THE DEM at plan distance ``d = max(bank_min_width_m, |z_ring −
    DEM(foot)| / bank_slope)`` along the outward normal; the foot's z IS
    the DEM there; the foot chain is smoothed along itself so the toe does
    not zigzag; where the foot would cross another patch ring it stops at
    that ring (the two rings share the bank).

THE BANK FACE IS AUTHORED (owner RULINGS 2026-09-09f-1).  09e left the
face to the mesh: ``O4_Vector_Map.include_patches`` polygonizes every closed
patch way and ``O4_Mesh_Utils.interpolate_free_interior_altitudes``
harmonically extends the two rings' authored altitudes across the annulus.
Spec §9.5 MEASURED what that gives — 17.55 m over 59 m on average, but ONE
triangle of 9.93 m over 8.9 m (111 %) against the patch ring, because the
extension is GRAPH-harmonic over whatever vertices Triangle4XP put in the
annulus, not metric-linear: with few free vertices the isolines crowd
against the shorter (inner) boundary.  The mesh will not interpolate a
straight bank it has no vertices for.

So the patch emits INTERMEDIATE RINGS every ``[design] bank_ring_spacing_m``
(10 m) of plan distance between the boundary ring and the foot, each
vertex's z LINEAR between the ring's design z and the foot's DEM z along the
outward normal — a foot 59 m out gets five, a foot at the 5 m minimum gets
none.  They carry the SAME ``o4_feature=bank_foot`` skip register as the
foot (:data:`BANK_KIND`), so every consumer that already ignores the foot —
``check_grade``'s role-less register, ``verify/frame.Patch.of``,
``tools/undulation`` — ignores them too, with no new register to add.
Outside the foot the mesh drapes the DEM, which the foot IS: continuous.

Every intermediate ring is a CLOSED way.  Where the bank is too narrow for
a level, the ring RUNS ALONG THE FOOT there — reusing the foot node's own
id, so nothing is duplicated and the two rings share that stretch of edge.
Closed is load-bearing and measured (spec §10.5): an OPEN chain enters
``include_patches`` as a DUMMY way, which is not in
``interp_alt_patch_polygons``, so the annulus outside it gets no INTERP_ALT
seed of its own while its segments still block Triangle4XP's regional
plague — the bank beyond level 1 reverted to the raw DEM and the transect
read 306 %, worse than the 111 % it was sent to fix.

THE BANK IS NOT A LAW SURFACE.  It carries no grade law of its own — it is
the terrain — so it is emitted role-less (``o4_feature=bank_foot``,
articulation geometry exactly as ``structure_rim``), the v1 census skips it
(``check_grade.ROLE_LESS_FEATURE_CLASSES``) and v2's own ``verify/frame.
Patch.of`` never builds a shape from it (it matches neither breakline
branch).  Spec §9.2 is the consumer table.

IT RUNS AFTER THE SOLVE, on the SOLUTION: no planar face, edge or vertex is
added, so no law row, no bending triangle and no zone membership changes.
The surface the rebake plan reads is the PRE-bank one (§9.2 A7).

Deviations recorded in spec §9.4: the second-difference smoothing is
applied to the foot's PLAN DISTANCE (its z is the DEM, not an unknown); a
foot ring straddling a tile seam becomes an open chain in each tile piece;
the ring is made valid by construction, which can move a foot vertex off
its own normal (its z is re-sampled there, so ``z = DEM`` still holds).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .surface import GradedSurface, SurfaceBreakline, SurfaceVertex

__all__ = ["BANK_KIND", "BankReport", "coverage_polygon", "foot_distances",
           "intermediate_offsets", "smooth_along", "with_bank"]

#: The breakline kind and the ``o4_feature`` value of a bank foot ring.
BANK_KIND = "bank_foot"

#: A hole in the patch coverage narrower than this many bank minimum widths
#: is not banked (there is no room for a foot inside it).  A geometric floor
#: of the construction, not a law value.
_MIN_HOLE_WIDTHS = 2.0
#: The miter factor is clamped here: at a spike the exact miter runs away.
_MITER_MAX = 3.0
#: Coordinate quantum (metres) of the ring-vertex identity join.
_SNAP = 1.0e-4


@_dc.dataclass
class BankReport:
    """What the bank pass built — the numbers the round quotes."""

    rings: int = 0
    ring_vertices: int = 0
    foot_vertices: int = 0
    face_rings: int = 0
    face_vertices: int = 0
    face_levels: int = 0
    repaired_rings: int = 0
    skipped_rings: int = 0
    mean_m: float = 0.0
    min_m: float = 0.0
    p95_m: float = 0.0
    max_m: float = 0.0
    max_slope: float = 0.0
    p95_slope: float = 0.0
    wall_s: float = 0.0

    def line(self, icao: str) -> str:
        return (f"[{icao}] bank (09e): {self.rings} rings banked "
                f"({self.ring_vertices} boundary vertices -> {self.foot_vertices} "
                f"foot nodes, {self.repaired_rings} repaired, {self.skipped_rings} "
                f"skipped), foot distance min {self.min_m:.1f} / mean "
                f"{self.mean_m:.1f} m / p95 "
                f"{self.p95_m:.1f} / max {self.max_m:.1f}, bank slope p95 "
                f"{self.p95_slope:.3f} / max {self.max_slope:.3f} "
                f"(law 0.33 = 1:3); FACE (09f-1) {self.face_rings} intermediate "
                f"chains / {self.face_vertices} vertices, deepest bank {self.face_levels} "
                f"level(s); {self.wall_s:.2f} s")


def coverage_polygon(planar: PlanarMap):
    """THE PATCH COVERAGE as ONE polygon in the frame: the union of EVERY
    planar face (the structure voids included — their rim is emitted as a
    constrained ring, so the ground inside them is patch geometry and takes
    no bank).  ``None`` when the map has no face."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = []
    for f in planar.faces.values():
        ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
        if len(ring) < 3:
            continue
        holes = [[planar.vertices[v].xy for v in planar.ring_vertices(h)]
                 for h in f.holes]
        p = Polygon(ring, [h for h in holes if len(h) >= 3])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    cov = unary_union(polys)
    return None if cov.is_empty else cov


def _outward_normals(pts: list[tuple[float, float]]
                     ) -> list[tuple[float, float]]:
    """The MITERED outward normal per vertex of a closed chain oriented so
    the patch material lies to the LEFT (shapely ``orient(sign=1)``: a CCW
    exterior, a CW hole) — the RIGHT normal points away from the patch in
    both cases."""
    n = len(pts)
    seg: list[tuple[float, float]] = []
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        seg.append((0.0, 0.0) if L <= 0.0 else (dy / L, -dx / L))
    out: list[tuple[float, float]] = []
    for i in range(n):
        px, py = seg[i - 1]
        nx, ny = seg[i]
        sx, sy = px + nx, py + ny
        L = math.hypot(sx, sy)
        if L <= 1.0e-9:
            out.append(seg[i] if (nx, ny) != (0.0, 0.0) else (px, py))
            continue
        miter = min(_MITER_MAX, 2.0 / L)
        out.append((sx / L * miter, sy / L * miter))
    return out


def _dem_many(dem, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Sample the production DEM at frame points (the zones' own sampler)."""
    many = getattr(dem, "z_many", None)
    if many is not None:
        return np.asarray(many(xs, ys), float)
    return np.asarray([dem.z(float(x), float(y)) for x, y in zip(xs, ys)], float)


def foot_distances(z_ring: np.ndarray, pts: np.ndarray, nrm: np.ndarray,
                   dem, slope: float, min_w: float,
                   rounds: int = 2) -> np.ndarray:
    """``d`` per boundary vertex: ``max(min_w, |z_ring − DEM(foot)| /
    slope)``, iterated because the foot's DEM depends on where the foot
    lands (the ruling's own fixed point; two rounds settle it)."""
    d = np.full(len(z_ring), float(min_w))
    for _ in range(max(1, rounds)):
        fx = pts[:, 0] + nrm[:, 0] * d
        fy = pts[:, 1] + nrm[:, 1] * d
        zf = _dem_many(dem, fx, fy)
        d = np.maximum(min_w, np.abs(z_ring - zf) / float(slope))
    return d


def intermediate_offsets(d: float, spacing: float) -> list[float]:
    """THE PLAN DISTANCES of the intermediate rings on a bank whose foot is
    ``d`` metres out (09f-1): one every ``spacing`` metres strictly inside
    the bank.  A foot at or inside one spacing gets NONE — a 5 m minimum
    bank has no room for a ring, and a foot exactly at 10 m already IS the
    ring.  ``d = 18.2, spacing = 10`` -> ``[10.0]``; ``d = 59`` -> five."""
    if spacing <= 0.0 or not d > spacing:
        return []
    n = int(math.ceil(d / spacing)) - 1
    return [spacing * (k + 1) for k in range(n)]


def smooth_along(d: np.ndarray, s: np.ndarray, w: float) -> np.ndarray:
    """THE TOE DOES NOT ZIGZAG (09e): the second-difference least squares
    along the CLOSED foot chain — minimise ``‖d − target‖² + w‖D²d‖²`` with
    ``D²`` the arc-length-scaled second difference at each station (the same
    operator ``[design] taxi_profile`` uses along a centreline).  ``s`` is
    the chord length from each station to the next."""
    import scipy.sparse as sp
    from scipy.sparse.linalg import spsolve
    n = len(d)
    if n < 3 or w <= 0.0:
        return d
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    r = 0
    for k in range(n):
        dp = float(s[k - 1])
        dn = float(s[k])
        if dp <= 1.0e-6 or dn <= 1.0e-6:
            continue
        sc = 0.5 * (dp + dn)
        for c, v in (((k + 1) % n, sc / dn), (k, -sc * (1.0 / dn + 1.0 / dp)),
                     ((k - 1) % n, sc / dp)):
            rows.append(r)
            cols.append(int(c))
            vals.append(float(v))
        r += 1
    if r == 0:
        return d
    D = sp.coo_matrix((vals, (rows, cols)), shape=(r, n)).tocsr()
    A = (sp.eye(n, format="csr") + float(w) * (D.T @ D)).tocsc()
    try:
        out = spsolve(A, d)
    except Exception:
        return d
    out = np.asarray(out, float).ravel()
    return out if np.all(np.isfinite(out)) else d


def _ray_limit(pts: np.ndarray, nrm: np.ndarray, d: np.ndarray, tree, segs,
               min_w: float) -> np.ndarray:
    """THE FOOT STOPS AT THE NEXT PATCH RING (09e: "the two rings share the
    bank"): ``d`` capped at the first crossing of the coverage boundary
    along the outward ray, never below ``min_w``."""
    from shapely.geometry import LineString
    out = d.copy()
    if tree is None:
        return out
    eps = _SNAP * 10.0
    for i in range(len(d)):
        px, py = float(pts[i, 0]), float(pts[i, 1])
        nx, ny = float(nrm[i, 0]), float(nrm[i, 1])
        L = math.hypot(nx, ny)
        if L <= 0.0:
            continue
        ray = LineString([(px + nx * eps, py + ny * eps),
                          (px + nx * out[i], py + ny * out[i])])
        best = None
        for j in tree.query(ray):
            g = segs[int(j)]
            if not ray.intersects(g):
                continue
            hit = ray.intersection(g)
            for q in getattr(hit, "geoms", [hit]):
                for cx, cy in getattr(q, "coords", []):
                    t = math.hypot(cx - px, cy - py)
                    if t > eps and (best is None or t < best):
                        best = t
        if best is not None:
            out[i] = max(min_w, best - eps)
    return out


def _foot_piece(pts: np.ndarray, nrm: np.ndarray, d: np.ndarray, host,
                exterior: bool):
    """THE BANK PIECE this chain contributes — the ground between the chain
    and its foot, as a polygon (``None`` when degenerate), and whether the
    raw offset had to be repaired (spec §9.4 deviation 3).  For an exterior
    chain that is the offset polygon itself; for a HOLE it is the hole
    minus the inward offset (the bank runs INTO the hole)."""
    from shapely.geometry import Polygon
    fx = pts[:, 0] + nrm[:, 0] * d
    fy = pts[:, 1] + nrm[:, 1] * d
    raw = Polygon(list(zip(fx.tolist(), fy.tolist())))
    repaired = False
    if not raw.is_valid or raw.is_empty:
        raw = raw.buffer(0)
        repaired = True
    cand = [g for g in getattr(raw, "geoms", [raw])
            if getattr(g, "geom_type", "") == "Polygon" and not g.is_empty]
    if exterior:
        if not cand:
            return None, True
        return max(cand, key=lambda g: g.area), repaired
    # a HOLE: the bank eats into it from its rim
    inner = max(cand, key=lambda g: g.area) if cand else None
    if inner is None or not host.contains(inner):
        return host, True
    piece = host.difference(inner)
    if piece.is_empty:
        return None, True
    return piece, repaired


def _push_off(ring: list, cov, min_w: float) -> list:
    """THE FOOT NEVER TOUCHES THE DESIGN SURFACE: a boundary vertex of the
    banked region that came to rest within half a bank width of the patch
    coverage is pushed back out to ``min_w`` along its own outward
    direction.  A foot node coincident with a design node would carry the
    DEM where the design ring carries the surface — the cliff again, at a
    single node."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    out = []
    for x, y in ring:
        p_ = Point(x, y)
        dist = cov.distance(p_)
        if dist >= 0.5 * min_w:
            out.append((x, y))
            continue
        q, _ = nearest_points(cov, p_)
        dx, dy = x - q.x, y - q.y
        L = math.hypot(dx, dy)
        if L <= 1.0e-9:
            out.append((x, y))
            continue
        out.append((q.x + dx / L * min_w, q.y + dy / L * min_w))
    return out


def _simple_rings(coords, reuse, ktree, rz, ztree, zsegs, zseg_z, ftree, zf,
                  inner, cov):
    """The level ring as ONE OR MORE SIMPLE polygons.  Valid as built, it is
    returned unchanged (every vertex keeps its identity, the foot's own ids
    included).  Self-intersecting, it is repaired through ``buffer(0)`` and
    each resulting exterior's vertices take the bank's own field: the design
    z where the nearest coverage point is, plus the nearest foot node's
    slope over the plan distance out.  Coordinate identity is what the mesh
    joins on (``O4_Vector_Map.insert_way(check=True)`` welds by coordinate),
    so a repaired vertex landing on a foot node costs nothing."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import nearest_points
    xy = [(c[0], c[1]) for c in coords]
    poly = Polygon(xy)
    if poly.is_valid and poly.area > 0.0:
        return [(coords, reuse)]
    fixed = poly.buffer(0)
    out = []
    for g in getattr(fixed, "geoms", [fixed]):
        if getattr(g, "geom_type", "") != "Polygon" or g.is_empty:
            continue
        for ring in [g.exterior, *g.interiors]:
            pts = list(ring.coords)[:-1]
            if len(pts) < 3:
                continue
            xyz = []
            for x, y in pts:
                q, _ = nearest_points(cov, Point(x, y))
                qx, qy = float(q.x), float(q.y)
                dq = math.hypot(x - qx, y - qy)
                zq = float("nan")
                if ztree is not None:
                    j = int(ztree.nearest(q))
                    gseg = zsegs[j]
                    L = gseg.length
                    t = (gseg.project(q) / L) if L > 1.0e-9 else 0.0
                    z0, z1 = zseg_z[j]
                    zq = z0 + (z1 - z0) * min(1.0, max(0.0, t))
                if not math.isfinite(zq) and ktree is not None:
                    zq = float(rz[int(ktree.query([qx, qy])[1]), 2])
                k = int(ftree.query([x, y])[1])
                dk = float(inner[k][3])
                frac = 1.0 if dk <= 1.0e-6 else min(1.0, dq / dk)
                xyz.append((x, y, zq + (float(zf[k]) - zq) * frac))
            out.append((xyz, [None] * len(xyz)))
    return out


def with_bank(surface: GradedSurface, planar: PlanarMap, law: Law,
              airport: Airport, report: BankReport | None = None
              ) -> GradedSurface:
    """The surface with its BANK FOOT rings appended (module docstring):
    new vertices (their z the DEM at the foot) and one CLOSED breakline of
    kind :data:`BANK_KIND` per banked boundary ring.  The input surface is
    returned unchanged when the airport has no coverage or no DEM."""
    import time
    from shapely.geometry import LineString, Point, Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import nearest_points, unary_union
    from shapely.strtree import STRtree
    t0 = time.perf_counter()
    rep = report if report is not None else BankReport()
    dem = getattr(airport, "dem", None)
    d_law = law.tables.emit.design
    cov = coverage_polygon(planar)
    if dem is None or cov is None:
        return surface
    z_of = {v.id: v.z for v in surface.vertices}
    xy_of = {v: vx.xy for v, vx in planar.vertices.items()}
    by_xy = {(round(x, 4), round(y, 4)): v for v, (x, y) in xy_of.items()
             if v in z_of}
    slope = float(d_law.bank_slope)
    min_w = float(d_law.bank_min_width_m)
    w_smooth = float(d_law.bank_foot_smooth)
    # the coverage boundary as segments — the ray limit's cutter set
    segs = []
    for poly in getattr(cov, "geoms", [cov]):
        for ring in [poly.exterior, *poly.interiors]:
            cs = list(ring.coords)
            segs.extend(LineString([cs[i], cs[i + 1]]) for i in range(len(cs) - 1))
    tree = STRtree(segs) if segs else None
    _to_ll = airport.frame.transformers()[1]
    next_id = max(z_of) + 1 if z_of else 0
    next_bl = max((b.id for b in surface.breaklines), default=-1) + 1
    new_v: list[SurfaceVertex] = []
    new_b: list[SurfaceBreakline] = []
    dists: list[float] = []
    slopes: list[float] = []
    chains: list[tuple[list, bool, object]] = []
    for poly in getattr(cov, "geoms", [cov]):
        poly = orient(poly, 1.0)
        chains.append((list(poly.exterior.coords)[:-1], True,
                       Polygon(poly.exterior)))
        for hole in poly.interiors:
            h = Polygon(hole)
            if h.area < (_MIN_HOLE_WIDTHS * min_w) ** 2:
                continue
            chains.append((list(hole.coords)[:-1], False, h))
    pieces = []
    ring_z: list[tuple[float, float, float]] = []      # the design ring, for the slope stat
    zsegs: list = []                                   # its segments, with z at both ends
    zseg_z: list[tuple[float, float]] = []
    for pts_ll, exterior, host in chains:
        if len(pts_ll) < 3:
            rep.skipped_rings += 1
            continue
        pts = np.asarray(pts_ll, float)
        # the ring's DESIGN elevation: its own vertex where the coverage kept
        # it (the identity join), the DEM where the union minted a point
        zr = np.empty(len(pts))
        for i, (x, y) in enumerate(pts_ll):
            vid = by_xy.get((round(x, 4), round(y, 4)))
            zr[i] = z_of[vid] if vid is not None else float("nan")
        miss = ~np.isfinite(zr)
        if miss.any():
            zr[miss] = _dem_many(dem, pts[miss, 0], pts[miss, 1])
        ring_z.extend((float(x), float(y), float(z))
                      for (x, y), z in zip(pts_ll, zr.tolist()))
        # the DESIGN boundary as z-carrying segments: the intermediate rings
        # interpolate the ring's z ALONG its edge, never to the nearest ring
        # VERTEX (a runway edge runs hundreds of metres between vertices)
        for i in range(len(pts_ll)):
            a, b = pts_ll[i], pts_ll[(i + 1) % len(pts_ll)]
            if a == b:
                continue
            zsegs.append(LineString([a, b]))
            zseg_z.append((float(zr[i]), float(zr[(i + 1) % len(pts_ll)])))
        nrm = np.asarray(_outward_normals(pts_ll), float)
        d = foot_distances(zr, pts, nrm, dem, slope, min_w)
        d = _ray_limit(pts, nrm, d, tree, segs, min_w)
        s = np.hypot(np.roll(pts[:, 0], -1) - pts[:, 0],
                     np.roll(pts[:, 1], -1) - pts[:, 1])
        d = smooth_along(d, s, w_smooth)
        d = np.maximum(min_w, d)
        d = _ray_limit(pts, nrm, d, tree, segs, min_w)
        piece, repaired = _foot_piece(pts, nrm, d, host, exterior)
        if piece is None:
            rep.skipped_rings += 1
            continue
        if repaired:
            rep.repaired_rings += 1
        pieces.append(piece)
        rep.ring_vertices += len(pts_ll)
    if not pieces:
        return surface
    # THE BANK IS ONE REGION, NOT ONE RING PER BODY (spec §9.4 deviation 4):
    # banked per body, a foot ring lands INSIDE — even ON — a neighbouring
    # body's ring wherever two bodies stand closer than a bank is wide
    # (measured HECA: 184 foot nodes within 1 m of a design node, 12.34 m
    # below it — the very cliff the bank exists to remove).  The union of
    # the coverage with every bank piece has ONE boundary, everywhere at
    # least ``bank_min_width_m`` from the design surface: where two bodies
    # stand too close the gap is simply swallowed and the two rings share
    # the bank, exactly as 09e rules.
    # ... and the coverage's own MINIMUM-WIDTH collar goes into the union, so
    # every boundary vertex of the banked region is at least
    # ``bank_min_width_m`` from the design surface BY CONSTRUCTION — a
    # repaired piece that collapsed back onto its own body cannot expose the
    # design ring as a foot (measured HECA: a foot node at distance 0.0).
    banked = unary_union([cov.buffer(min_w, join_style="mitre",
                                     mitre_limit=_MITER_MAX), *pieces])
    from scipy.spatial import cKDTree
    rz = np.asarray(ring_z, float)
    ktree = cKDTree(rz[:, :2]) if len(rz) else None
    ztree = STRtree(zsegs) if zsegs else None
    spacing = float(d_law.bank_ring_spacing_m)

    def _inner(x: float, y: float) -> tuple[float, float, float, float]:
        """THE INNER END of this foot node's bank: the nearest point of the
        DESIGN coverage (never a ring vertex — the segment from a point to
        its nearest point of a closed set meets that set only there, so the
        bank face can never re-enter the patch), its design z interpolated
        along the boundary edge, and the plan distance out to the foot."""
        pnt = Point(x, y)
        q, _ = nearest_points(cov, pnt)
        qx, qy = float(q.x), float(q.y)
        dd = math.hypot(x - qx, y - qy)
        zq = float("nan")
        if ztree is not None:
            j = int(ztree.nearest(q))
            g = zsegs[j]
            L = g.length
            t = (g.project(q) / L) if L > 1.0e-9 else 0.0
            z0, z1 = zseg_z[j]
            zq = z0 + (z1 - z0) * min(1.0, max(0.0, t))
        if not math.isfinite(zq) and ktree is not None:
            zq = float(rz[int(ktree.query([qx, qy])[1]), 2])
        return qx, qy, zq, dd

    for poly in getattr(banked, "geoms", [banked]):
        for ring in [poly.exterior, *poly.interiors]:
            pts_r = list(ring.coords)[:-1]
            if len(pts_r) < 3:
                rep.skipped_rings += 1
                continue
            pts_r = _push_off(pts_r, cov, min_w)
            fx = np.asarray([q[0] for q in pts_r], float)
            fy = np.asarray([q[1] for q in pts_r], float)
            zf = _dem_many(dem, fx, fy)
            ids: list[int] = []
            for x, y, z in zip(fx.tolist(), fy.tolist(), zf.tolist()):
                lat, lon = _to_ll(x, y)
                new_v.append(SurfaceVertex(next_id, (lat, lon), float(z)))
                ids.append(next_id)
                next_id += 1
            ref = f"bank:{rep.rings}"
            new_b.append(SurfaceBreakline(next_bl, BANK_KIND, ref,
                                          tuple(ids) + (ids[0],)))
            next_bl += 1
            rep.rings += 1
            rep.foot_vertices += len(ids)
            # the inner end of every bank ray, once
            inner = [_inner(x, y) for x, y in zip(fx.tolist(), fy.tolist())]
            for (x, y, z), (qx, qy, zq, dd) in zip(
                    zip(fx.tolist(), fy.tolist(), zf.tolist()), inner):
                dists.append(dd)
                if ktree is not None:
                    dv, k = ktree.query([x, y])
                    # the STEEPEST LOCAL TRANSITION this foot node makes: its
                    # own drop to the nearest DESIGN ring vertex over the
                    # plan distance to that vertex (never to some other
                    # body's ring at another distance — two instruments)
                    if float(dv) > 1.0e-6:
                        slopes.append(abs(float(rz[int(k), 2]) - z) / float(dv))
            # THE FACE (09f-1): one CLOSED ring per level, its vertices
            # LINEAR between the design ring and the foot along the ray.
            # CLOSED is not cosmetic and MEASURED (spec §10.5): emitted as
            # open chains these rings enter ``include_patches`` as DUMMY
            # ways, which are NOT in ``interp_alt_patch_polygons`` — so no
            # sub-face of the annulus gets its own INTERP_ALT seed, and the
            # segments still block Triangle4XP's regional plague: the bank
            # outside level 1 reverted to the raw DEM and the transect read
            # a 306 % triangle, WORSE than 09f's 111 %.  A closed ring is
            # polygonized, seeded, and its band interpolated between two
            # authored boundaries.  Where the bank is narrower than the
            # level, the ring simply RUNS ALONG THE FOOT there — the foot
            # node's own id, so no vertex is duplicated and the two rings
            # share that stretch of edge.
            levels = max((len(intermediate_offsets(r[3], spacing)) for r in inner),
                         default=0)
            rep.face_levels = max(rep.face_levels, levels)
            ftree = cKDTree(np.c_[fx, fy])
            for lv in range(1, levels + 1):
                t_out = spacing * lv
                coords: list[tuple[float, float, float]] = []
                reuse: list[int | None] = []
                minted = 0
                for i, (qx, qy, zq, dd) in enumerate(inner):
                    if not dd > t_out:
                        coords.append((float(fx[i]), float(fy[i]), float(zf[i])))
                        reuse.append(ids[i])            # the foot: no room
                        continue
                    f_ = t_out / dd
                    coords.append((qx + (float(fx[i]) - qx) * f_,
                                   qy + (float(fy[i]) - qy) * f_,
                                   zq + (float(zf[i]) - zq) * f_))
                    reuse.append(None)
                    minted += 1
                if minted == 0:
                    continue
                # A LEVEL RING MUST BE A SIMPLE POLYGON.  ``include_patches``
                # takes a closed patch way only when ``pol.is_valid and
                # pol.area`` — and a per-vertex offset self-intersects at a
                # concave corner, which drops the WHOLE ring: measured at
                # HECA, 9 of 39 level rings invalid, among them all three
                # inner levels of the 1,516-vertex ring at the §9.5 transect
                # (the mesh honoured levels 4-7 and reverted 1-3 to the DEM).
                # The repaired ring's vertices are re-derived from the bank's
                # own field: z = design z at the nearest coverage point, plus
                # the nearest foot node's slope over the plan distance out.
                for ring_xyz, ring_ids in _simple_rings(coords, reuse, ktree, rz,
                                                        ztree, zsegs, zseg_z,
                                                        ftree, zf, inner, cov):
                    if len(ring_xyz) < 3:
                        continue
                    chain: list[int] = []
                    for (x, y, z), vid in zip(ring_xyz, ring_ids):
                        if vid is not None:
                            chain.append(vid)
                            continue
                        lat, lon = _to_ll(x, y)
                        new_v.append(SurfaceVertex(next_id, (lat, lon), float(z)))
                        chain.append(next_id)
                        next_id += 1
                        rep.face_vertices += 1
                    new_b.append(SurfaceBreakline(next_bl, BANK_KIND,
                                                  f"{ref}@{lv}",
                                                  tuple(chain) + (chain[0],)))
                    next_bl += 1
                    rep.face_rings += 1
    if not new_b:
        return surface
    if dists:
        a = np.asarray(dists)
        rep.mean_m = float(a.mean())
        rep.p95_m = float(np.percentile(a, 95))
        rep.max_m = float(a.max())
        rep.min_m = float(a.min())
    if slopes:
        rep.max_slope = float(max(slopes))
        rep.p95_slope = float(np.percentile(np.asarray(slopes), 95))
    rep.wall_s = time.perf_counter() - t0
    return _dc.replace(surface,
                       vertices=surface.vertices + tuple(new_v),
                       breaklines=surface.breaklines + tuple(new_b))
