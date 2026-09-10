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

THE ENGINE BLENDS THE BANK (owner RULINGS 2026-09-09p (1) / 2026-09-09t;
spec §13).  09f-1 answered the mesh's graph-harmonic squeeze by AUTHORING
the face with intermediate LEVEL RINGS.  09t measured what that costs: a
level ring at plan distance ``t`` degenerates onto the FOOT wherever the
bank is narrower than ``t``, re-emitting the foot's own edges as a second
constrained segment on the same nodes — Triangle's segment recovery spins
forever at HECA and errors at HEAZ, and the +30+031 tile cannot be built.
THE LEVEL RINGS ARE DELETED.  The patch emits ONE closed foot ring per
boundary and nothing between; inside the annulus the MESH ENGINE gives
every free vertex an altitude LINEAR IN PLAN DISTANCE between the two
rings (``O4_Mesh_Utils.bank_annulus_blend_values``), which reproduces the
ruled bank surface exactly with whatever vertices Triangle4XP put there.

THE DAYLIGHT LINE (owner RULINGS 2026-09-09g).  09e/09f placed the foot by
the fixed point ``d = |z_ring − DEM(foot)| / bank_slope``, which is the
daylight point only where the ground is smooth — where it is not, it erases
the very earthworks the owner names.  The foot is instead the CIVIL-
ENGINEERING DAYLIGHT (CATCH) POINT (:func:`daylight_feet`): walking outward
in ``[design] bank_sample_m`` (2 m) stations, the FIRST station where the
1:3 design slope line (down for fill, up for cut, from the ring's design z)
meets the DEM within ``bank_daylight_tol_m`` (0.3 m), never nearer than
``bank_min_width_m`` (5 m), never farther than ``bank_max_width_m`` (200 m
— a ray that never daylights takes the maximum and is REPORTED BY NAME).
Where the DEM inside the first ``bank_min_width_m`` already falls (fill) or
rises (cut) at ``bank_slope`` or steeper, the GROUND HAS ITS OWN BANK and
the foot is at the minimum.  So an embankment under the pavement edge
survives, a plateau edge or cliff beyond the daylight point is untouched,
and a terrace between ring and foot is met where it stands.  The toe is
still smoothed in plan (09f) but NEVER across a daylight discontinuity: the
chain is cut into runs wherever the raw daylight distance jumps by more
than ``bank_toe_break_m`` (:func:`smooth_runs`).

THE SHORE HAS NO BANK (owner RULINGS 2026-09-09z (3)): "only set pavement
node elevations, then the DEM should automatically grade into the water and
blend with bathymetry data".  09m (2) / 09o (4)'s shore bank is WITHDRAWN.
The daylight walk STOPS at the water line (the production frame's own water
witness, ``dem.water_many``); a ray already over water inside
``bank_min_width_m`` carries NO foot at all, and the banked REGION is cut by
the tile's water (``dem.water_geometry``) at one derivation site, so no bank
piece, no annulus and no foot node ever lands in water.  The mesh then does
what the owner rules it should: drapes the DEM with its bathymetry band into
the water and levels the water itself.  Spec §18.

THE FOOT RING IS CLOSED, and closed is load-bearing and measured (spec
§10.5): an OPEN chain enters ``include_patches`` as a DUMMY way, which is
not in ``interp_alt_patch_polygons``, so the annulus outside it gets no
INTERP_ALT seed of its own while its segments still block Triangle4XP's
regional plague — the bank reverted to the raw DEM and the transect read
306 %.  A ring straddling a tile seam is the one lawful exception (spec
§9.4).

The foot carries ``o4_feature=bank_foot`` (:data:`BANK_KIND`), the skip
register every consumer that already ignores the bank reads —
``check_grade``'s role-less register, ``verify/frame.Patch.of``,
``tools/undulation``.  Outside the foot the mesh drapes the DEM, which the
foot IS: continuous.

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
the banked region is built as a shapely union, which can move a foot
vertex off its own normal (its z is re-sampled there, so ``z = DEM`` still
holds).
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

__all__ = ["BANK_KIND", "BankReport", "FOOT_KINDS", "coverage_polygon",
           "daylight_feet", "smooth_along", "smooth_runs", "with_bank"]

#: The breakline kind and the ``o4_feature`` value of a bank foot ring.
BANK_KIND = "bank_foot"

#: THE DAYLIGHT CLASSIFICATION of a foot (owner RULINGS 2026-09-09g), in the
#: integer order :func:`daylight_feet` returns: the ground's own bank (the
#: foot is at ``bank_min_width_m``), a true daylight point, a ray that
#: never met the DEM (the foot is at ``bank_max_width_m``, reported by name),
#: and — owner RULINGS 2026-09-09z (3) — a ray that met WATER, which has no
#: earthwork foot at all.
FOOT_KINDS: tuple[str, ...] = ("min", "daylight", "max", "water")
_K_MIN, _K_DAY, _K_MAX, _K_WATER = 0, 1, 2, 3

#: A hole in the patch coverage narrower than this many bank minimum widths
#: is not banked (there is no room for a foot inside it).  A geometric floor
#: of the construction, not a law value.
_MIN_HOLE_WIDTHS = 2.0
#: The miter factor is clamped here: at a spike the exact miter runs away.
_MITER_MAX = 3.0
#: Coordinate quantum (metres) of the ring-vertex identity join.
_SNAP = 1.0e-4
#: How many never-daylighted rays are NAMED in the report (09g: "reported by
#: name") before the count alone carries the rest.
_NAME_CAP = 64


@_dc.dataclass
class BankReport:
    """What the bank pass built — the numbers the round quotes."""

    rings: int = 0
    ring_vertices: int = 0
    foot_vertices: int = 0
    repaired_rings: int = 0
    skipped_rings: int = 0
    #: THE DAYLIGHT CLASSIFICATION (09g) of every boundary-ring ray
    at_min: int = 0
    daylighted: int = 0
    at_max: int = 0
    #: THE SHORE (09z (3)): rays whose walk met WATER and carry no foot
    at_water: int = 0
    #: the rays that NEVER daylighted, named (chain, vertex, lat/lon)
    never_daylight: list[str] = _dc.field(default_factory=list)
    #: the toe-smoothing runs the daylight discontinuities cut the chains into
    toe_runs: int = 0
    mean_m: float = 0.0
    min_m: float = 0.0
    p95_m: float = 0.0
    max_m: float = 0.0
    max_slope: float = 0.0
    p95_slope: float = 0.0
    wall_s: float = 0.0

    def line(self, icao: str) -> str:
        names = ", ".join(self.never_daylight[:6])
        if len(self.never_daylight) > 6:
            names += f", +{len(self.never_daylight) - 6} more"
        return (f"[{icao}] bank (09g): {self.rings} rings banked "
                f"({self.ring_vertices} boundary vertices -> {self.foot_vertices} "
                f"foot nodes, {self.repaired_rings} repaired, {self.skipped_rings} "
                f"skipped), DAYLIGHT {self.at_min} at the minimum / "
                f"{self.daylighted} daylighted / {self.at_max} at the maximum"
                + f" / {self.at_water} STOPPED AT WATER (09z: no foot there)"
                + (f" [{names}]" if self.never_daylight else "")
                + f", toe in {self.toe_runs} smoothing run(s); foot distance min "
                f"{self.min_m:.1f} / mean {self.mean_m:.1f} m / p95 "
                f"{self.p95_m:.1f} / max {self.max_m:.1f}, bank slope p95 "
                f"{self.p95_slope:.3f} / max {self.max_slope:.3f} "
                f"(law 0.33 = 1:3); the engine blends the annulus "
                f"(09-09t); {self.wall_s:.2f} s")


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


def _water_many(dem, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """THE WATER WITNESS at frame points — the production frame's own
    (``airport/dem_production.ProductionDem.water_many``, owner RULINGS
    2026-09-09o (1)), never a second water source.  A sampler without one
    (every synthetic fixture, the authored ``DemSampler``) claims NO
    water, so the bank is bit-for-bit what it was before 09z (3)."""
    fn = getattr(dem, "water_many", None)
    if not callable(fn) or len(xs) == 0:
        return np.zeros(len(xs), dtype=bool)
    try:
        wet, _level = fn(np.asarray(xs, float), np.asarray(ys, float))
    except Exception:                                   # pragma: no cover
        return np.zeros(len(xs), dtype=bool)
    return np.asarray(wet, dtype=bool)


def daylight_feet(z_ring: np.ndarray, pts: np.ndarray, nrm: np.ndarray,
                  dem, slope: float, min_w: float, max_w: float,
                  step: float, tol: float) -> tuple[np.ndarray, np.ndarray]:
    """THE DAYLIGHT (CATCH) POINT per boundary vertex (owner RULINGS
    2026-09-09g), and its classification (an index into :data:`FOOT_KINDS`).

    From each ring vertex the walk carries the DESIGN SLOPE LINE outward
    along the vertex's normal — falling at ``slope`` where the ring stands
    ABOVE its DEM (fill), rising where it stands below (cut) — sampling the
    DEM every ``step`` metres.  The foot is the FIRST station where the two
    meet within ``tol``; where a station steps over the crossing the foot is
    the crossing itself (linear between the two stations).  It is never
    nearer than ``min_w`` and never farther than ``max_w``.

    The signed residual is written so ``r(0) >= 0`` in both directions::

        s = +1 (fill) | -1 (cut);  r(t) = s * (z_ring - DEM(t)) - slope * t

    so DAYLIGHT is simply ``r(t) <= tol`` and the ray has crossed when
    ``r(t) < -tol``.

    THE GROUND'S OWN BANK: where the DEM inside the first ``min_w`` already
    falls (fill) / rises (cut) at ``slope`` or steeper, the earthwork under
    the pavement edge IS the bank — the foot is at ``min_w`` and the DEM's
    own slope carries the drop beyond.

    ``t`` is the OFFSET PARAMETER of the mitered normal (``pts + nrm * t``),
    which is the perpendicular plan distance from the ring — the same
    parameter every other pass of this module uses.
    """
    n = len(z_ring)
    d = np.full(n, float(min_w))
    kind = np.full(n, _K_MAX, dtype=np.int8)
    if n == 0:
        return d, kind
    z0 = np.asarray(z_ring, float)
    z_at0 = _dem_many(dem, pts[:, 0], pts[:, 1])
    sgn = np.where(z0 >= z_at0, 1.0, -1.0)
    # the ground's own bank, read over the minimum width
    z_min = _dem_many(dem, pts[:, 0] + nrm[:, 0] * min_w,
                      pts[:, 1] + nrm[:, 1] * min_w)
    own = sgn * (z_at0 - z_min) >= float(slope) * float(min_w)
    kind[own] = _K_MIN
    # the residual at the minimum width: a ring already level with its DEM
    # (a plateau edge) resolves here too, at the minimum
    r_prev = sgn * (z0 - z_min) - float(slope) * float(min_w)
    t_prev = np.full(n, float(min_w))
    here = (~own) & (r_prev <= float(tol))
    kind[here] = _K_MIN
    # THE SHORE HAS NO BANK (owner RULINGS 2026-09-09z (3)).  The walk is
    # water-tested at the minimum width FIRST: a ray whose ground is
    # already water inside ``min_w`` carries NO earthwork at all — the
    # ring's outer edge is the patch boundary and the mesh grades the DEM
    # (with its bathymetry band) into the water on its own.
    wet0 = _water_many(dem, pts[:, 0] + nrm[:, 0] * min_w,
                       pts[:, 1] + nrm[:, 1] * min_w)
    if wet0.any():
        d[wet0] = 0.0
        kind[wet0] = _K_WATER
    live = np.flatnonzero(~(own | here | wet0))
    t = float(step) * math.ceil((float(min_w) + 1.0e-9) / float(step))
    while live.size and t <= float(max_w) + 1.0e-9:
        sx = pts[live, 0] + nrm[live, 0] * t
        sy = pts[live, 1] + nrm[live, 1] * t
        # THE WALK STOPS AT THE WATER LINE (09z (3)): the foot of a wet
        # ray is the LAST DRY STATION and it carries no bank beyond.
        wet = _water_many(dem, sx, sy)
        if wet.any():
            idx = live[wet]
            d[idx] = np.maximum(t_prev[idx], float(min_w))
            kind[idx] = _K_WATER
            live = live[~wet]
            if not live.size:
                break
            sx = pts[live, 0] + nrm[live, 0] * t
            sy = pts[live, 1] + nrm[live, 1] * t
        zt = _dem_many(dem, sx, sy)
        r = sgn[live] * (z0[live] - zt) - float(slope) * t
        hit = r <= float(tol)
        if hit.any():
            idx = live[hit]
            rp = r_prev[idx]
            rh = r[hit]
            # THE FOOT IS THE CROSSING, not the station that detected it
            # (spec §11.6 deviation 1): the station finds the meeting within
            # ``tol``, and the foot is placed where the slope line actually
            # meets the DEM between the two stations — otherwise the
            # realised bank would run up to ``tol / d`` steeper than the
            # law's 1:3 purely because the walk is discrete.  Detected just
            # SHORT of the crossing the fraction runs past 1; it is capped
            # at one further station, never more.
            span = np.maximum(rp - rh, 1.0e-12)
            frac = np.clip(rp / span, 0.0, 2.0)
            d[idx] = t_prev[idx] + (t - t_prev[idx]) * frac
            kind[idx] = _K_DAY
        keep = ~hit
        r_prev[live[keep]] = r[keep]
        t_prev[live[keep]] = t
        live = live[keep]
        t += float(step)
    if live.size:                       # never daylighted: at the maximum
        d[live] = float(max_w)
        kind[live] = _K_MAX
    dry = kind != _K_WATER
    d[dry] = np.clip(d[dry], float(min_w), float(max_w))
    kind[(kind == _K_DAY) & dry & (d <= float(min_w) + 1.0e-9)] = _K_MIN
    return d, kind


def smooth_along(d: np.ndarray, s: np.ndarray, w: float,
                 closed: bool = True) -> np.ndarray:
    """THE TOE DOES NOT ZIGZAG (09e): the second-difference least squares
    along the foot chain — minimise ``‖d − target‖² + w‖D²d‖²`` with ``D²``
    the arc-length-scaled second difference at each station (the same
    operator ``[design] taxi_profile`` uses along a centreline).  ``s`` is
    the chord length from each station to the next.  ``closed=False`` is one
    RUN of a chain the daylight discontinuities cut (09g (4)): the operator
    then runs over the interior stations only, and the run's two ends keep
    their own daylight distance."""
    import scipy.sparse as sp
    from scipy.sparse.linalg import spsolve
    n = len(d)
    if n < 3 or w <= 0.0:
        return d
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    r = 0
    for k in (range(n) if closed else range(1, n - 1)):
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


def smooth_runs(d: np.ndarray, raw: np.ndarray, s: np.ndarray, w: float,
                break_m: float) -> tuple[np.ndarray, int]:
    """THE TOE IS SMOOTHED IN PLAN, BUT NEVER ACROSS A DAYLIGHT
    DISCONTINUITY (owner RULINGS 2026-09-09g (4)).  The closed chain is CUT
    wherever the RAW daylight distance ``raw`` jumps by more than
    ``break_m`` between neighbours — a plateau edge, a terrace, a cliff that
    one ray catches and its neighbour does not — and each contiguous run is
    smoothed as an OPEN chain.  With no jump the chain is smoothed closed,
    exactly as 09f left it.  Returns the smoothed ``d`` and the run count."""
    n = len(d)
    if n < 3:
        return d, 1 if n else 0
    jump = np.abs(np.roll(raw, -1) - raw) > float(break_m)   # jump[k]: k -> k+1
    cuts = np.flatnonzero(jump)
    if cuts.size == 0:
        return smooth_along(d, s, w), 1
    out = np.array(d, float)
    starts = (cuts + 1) % n
    for a, b in zip(starts.tolist(), np.roll(starts, -1).tolist()):
        idx = [(a + k) % n for k in range((b - a) % n or n)]
        if len(idx) < 3:
            continue
        run = smooth_along(np.asarray(d[idx], float),
                           np.asarray(s[idx], float), w, closed=False)
        out[idx] = run
    return out, int(cuts.size)


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


def _push_off(ring: list, cov, min_w: float, dem=None) -> list:
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
    if dem is not None and out:
        # A PUSH NEVER CROSSES THE SHORELINE (owner RULINGS 2026-09-09z
        # (3)): the collar law exists to keep a foot node off the design
        # ring, and it must not buy that by putting one in the water.
        xs = np.asarray([q[0] for q in out], float)
        ys = np.asarray([q[1] for q in out], float)
        wet = _water_many(dem, xs, ys)
        if wet.any():
            out = [ring[i] if wet[i] else out[i] for i in range(len(out))]
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
    # THE SHORE (owner RULINGS 2026-09-09z (3)): the tile's WATER, from
    # the production frame's own witness, over the bank's whole reach.
    water_geom = None
    water_fn = getattr(dem, "water_geometry", None)
    if callable(water_fn):
        try:
            bx0, by0, bx1, by1 = cov.bounds
            reach = float(d_law.bank_max_width_m) + 10.0
            water_geom = water_fn((bx0 - reach, by0 - reach,
                                   bx1 + reach, by1 + reach))
        except Exception:                               # pragma: no cover
            water_geom = None
        if water_geom is not None and water_geom.is_empty:
            water_geom = None
    w_smooth = float(d_law.bank_foot_smooth)
    max_w = float(d_law.bank_max_width_m)
    sample_m = float(d_law.bank_sample_m)
    tol_m = float(d_law.bank_daylight_tol_m)
    break_m = float(d_law.bank_toe_break_m)
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
        # THE DAYLIGHT LINE (09g): the foot is where the 1:3 design slope
        # line meets the DEM, so a real embankment, terrace, plateau edge or
        # cliff is MET where it stands instead of being erased by a
        # smooth-ground fixed point.
        d_raw, kind = daylight_feet(zr, pts, nrm, dem, slope, min_w,
                                    max_w, sample_m, tol_m)
        rep.at_min += int(np.count_nonzero(kind == _K_MIN))
        rep.daylighted += int(np.count_nonzero(kind == _K_DAY))
        rep.at_max += int(np.count_nonzero(kind == _K_MAX))
        rep.at_water += int(np.count_nonzero(kind == _K_WATER))
        for i in np.flatnonzero(kind == _K_MAX).tolist():
            if len(rep.never_daylight) < _NAME_CAP:
                lat, lon = _to_ll(float(pts[i, 0]), float(pts[i, 1]))
                rep.never_daylight.append(
                    f"chain{len(pieces)}:{i}@{lat:.6f},{lon:.6f}")
        d = _ray_limit(pts, nrm, d_raw.copy(), tree, segs, min_w)
        s = np.hypot(np.roll(pts[:, 0], -1) - pts[:, 0],
                     np.roll(pts[:, 1], -1) - pts[:, 1])
        # the toe is smoothed in plan, but NEVER across a daylight
        # discontinuity (09g (4)): the runs are cut at a jump of the RAW
        # daylight distance, and the ground's own step survives
        d, runs = smooth_runs(d, d_raw, s, w_smooth, break_m)
        rep.toe_runs += runs
        d = np.clip(d, min_w, max_w)
        # the wet rays are re-zeroed AFTER the clip: the minimum width is
        # the dry law, and a shore ray carries no bank at all (09z (3))
        d[kind == _K_WATER] = np.minimum(d[kind == _K_WATER],
                                         d_raw[kind == _K_WATER])
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
    # THE SHORE HAS NO BANK (owner RULINGS 2026-09-09z (3)), cut at the
    # SINGLE derivation site: the min-width collar is the one part of the
    # banked region no ray governs, so the region — not a per-ray veto —
    # is what keeps every foot node out of the water.  What is left
    # closes ON the water line; the mesh drapes the DEM and its
    # bathymetry band from there into the water, and levels the water.
    if water_geom is not None:
        try:
            cut = banked.difference(water_geom)
            if not cut.is_empty:
                banked = cut if cut.geom_type in ("Polygon", "MultiPolygon") \
                    else banked
        except Exception:                               # pragma: no cover
            pass
    from scipy.spatial import cKDTree
    rz = np.asarray(ring_z, float)
    ktree = cKDTree(rz[:, :2]) if len(rz) else None
    ztree = STRtree(zsegs) if zsegs else None

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
            pts_r = _push_off(pts_r, cov, min_w, dem if water_geom is not None
                              else None)
            fx = np.asarray([q[0] for q in pts_r], float)
            fy = np.asarray([q[1] for q in pts_r], float)
            zf = _dem_many(dem, fx, fy)
            ids: list[int] = []
            for x, y, z in zip(fx.tolist(), fy.tolist(), zf.tolist()):
                lat, lon = _to_ll(x, y)
                new_v.append(SurfaceVertex(next_id, (lat, lon), float(z)))
                ids.append(next_id)
                next_id += 1
            new_b.append(SurfaceBreakline(next_bl, BANK_KIND,
                                          f"bank:{rep.rings}",
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
    # THE FACE IS THE ENGINE'S (owner RULINGS 2026-09-09p (1) /
    # 2026-09-09t).  09f-1/09h/09i/09j authored it here with LEVEL RINGS;
    # 09t measured a level ring re-emitting the FOOT's own edges wherever
    # the bank is narrower than the level's offset (duplicate constrained
    # segments: Triangle's recovery spins at HECA, errors at HEAZ) and the
    # graph-harmonic squeeze surviving every spacing anyway.  The rings are
    # DELETED; ``O4_Mesh_Utils.bank_annulus_blend_values`` interpolates the
    # annulus LINEARLY IN PLAN DISTANCE between this foot ring and the
    # design coverage, which is the ruled surface the levels approximated.
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
