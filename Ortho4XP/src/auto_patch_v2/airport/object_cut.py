"""THE PACK'S STRUCTURE OBJECTS ARE THE CUT GEOMETRY (spec ``design-
surface-spec.md`` §33 (6); owner RULINGS 2026-09-15e items 1/3/4/6 and
2026-09-15g; 2026-09-14av; Fable 2026-09-15j).

Three authoring conventions, ONE intent — "the tunnels have object based
interior walls and hard covers where needed (like EGLL does), so we need
to cut our trenches based on those" (VHHH); "the terrain grades under the
wall object and the wall sits on top of the tunnel edges" (LEMD); "the two
edge wall objects … should be used as guides for where the author wants
the bridge" (LEMD).  Detected by GEOMETRY, never by name, never by ICAO:

* **A — crested walls** (OTHH, 14av): read by ``airport/wall_corridors.py``
  (LAW C), on the per-airport affordance ``kerb_wall_corridors`` as
  before.  §33 (6) A's retirement of that key is REFUTED by measurement —
  see the section below, which is the record.
* **B — shell + flush hard cover** (VHHH, EGLL): a SHELL whose largest
  horizontal plate lies ``shell_floor_min_m`` or more below its zero (the
  FLOOR) and, at the SAME PLACEMENT (a second object, position within
  ``cover_placement_tol_m``, same heading), a COVER whose ``HARD_DECK``
  plate stands at ``|y| <= cover_flush_m``.  Read
  here, end to end (:func:`read_shells`), because no other reader can see
  it: ``tunnel_objects``'s witness hand-off sends any floor witness to
  ``basins.py``, its crest-plate rule needs a plate ABOVE zero, and
  ``thin_plates`` takes 1.0-1.5 m of solids only.
* **C — thin surface walls and parapets** (LEMD): solids under
  ``parapet_max_height_m``, long, narrow, sitting on the surface.  The
  BAND reading lives here (:func:`thin_bands`, :func:`band_pair`) and
  ``airport/thin_plates.py`` applies it.

THE WALL LINE, and why it is not a hull.  A shell is L-shaped or a
hairpin (VHHH ``tunnel5_done``: 245.9 x 73.2 m in plan, a U-turn ramp),
so its convex hull is three times its trench.  The reading is the
object's own: the plan union of every NON-vertical solid face is the
TRENCH OUTLINE (floor plates and ramps alike); the plan segments of the
VERTICAL faces are the WALL LINE; and a stretch of the trench ring with
no wall face standing on it is an OPEN END — a mouth.  Cut the ring at
its two open ends and the two chains ARE the side walls' inner faces,
which is exactly what ``tunnel_walls.midline`` / ``stations_along`` read.

Every number is a law-table value; nothing here reads the environment.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..model.frame import XY
from . import obj8 as _obj8

__all__ = ["ObjectCut", "SHELL", "CRESTED", "THIN", "shell_reading", "read_shells",
           "thin_bands", "band_pair", "cut_placement_ids", "ObjectCutStats"]

#: The three signatures, by name (the record's ``signature`` field).
CRESTED, SHELL, THIN = "A", "B", "C"

#: A ring point this far from a vertical wall face is UNWALLED (the wall
#: faces are the ring's own solids, so the tolerance is the plan
#: quantisation, not a law length).
_WALL_PROBE_M = 1.0
#: The trench ring is simplified this fine before its ends are read.
_RING_SIMPLIFY_M = 0.25


@_dc.dataclass(frozen=True)
class ObjectCut:
    """ONE record for all three signatures (§33 (6) "one reader … ONE
    record class"), in the AIRPORT frame.

    ``outline`` is the trench outline — the region the cut may occupy and
    the region an emitted ring vertex may not leave (``object_cut_offset``
    measures against it).  ``wall_line`` is the plan union of the object's
    own wall solids.  ``floor_z`` is the AUTHORED floor in the seated
    frame, or ``None`` where the object states no depth (signature C: the
    depth is ``bore_datum_m``).  ``covered`` is the covered extent (the
    signature-B cover's flat plate), ``stations`` the cover's own
    descending profile as ``(metres along the axis, y under the object's
    zero)`` pairs, ``ends`` the two portal points."""

    id: str
    resource: str
    object_id: str
    signature: str
    outline: Polygon
    wall_line: object                     # Polygon | MultiPolygon | LineString union
    inner_a: tuple[XY, ...]
    inner_b: tuple[XY, ...]
    ends: tuple[XY, XY]
    open_ends: tuple[bool, bool]
    floor_z: float | None
    floor_y: float | None
    zero_z: float
    covered: object | None
    stations: tuple[tuple[float, float], ...]
    notes: tuple[str, ...] = ()


@_dc.dataclass
class ObjectCutStats:
    """What the §33 (6) screen saw, admitted and refused — every screened
    resource by name with its verdict (§33 (1) stands for this reader)."""

    screened: int = 0
    shells: int = 0
    covers_paired: int = 0
    crested: int = 0
    thin_pairs: int = 0
    #: placements the screen CLAIMS — the set ``basins.py`` must not see
    claimed: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    read_s: float = 0.0


# ── the face split: walls, surfaces, plates ──────────────────────────────

def _face_normals_y(v: np.ndarray, tris: np.ndarray) -> np.ndarray:
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    nrm = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(nrm, axis=1)
    ok = ln > 1e-12
    ny = np.zeros(tris.shape[0])
    ny[ok] = np.abs(nrm[ok, 1] / ln[ok])
    return ny


def _plan_area(v: np.ndarray, tris: np.ndarray) -> np.ndarray:
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    return 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 2] - p0[:, 2])
                        - (p2[:, 0] - p0[:, 0]) * (p1[:, 2] - p0[:, 2]))


def _plan_polys(v: np.ndarray, tris: np.ndarray) -> list[Polygon]:
    out = []
    for t in tris.tolist():
        p = Polygon([(float(v[i][0]), float(v[i][2])) for i in t])
        if p.area > 1e-9:
            out.append(p.buffer(0))
    return out


def _plan_segments(v: np.ndarray, tris: np.ndarray) -> list[LineString]:
    """Each (vertical) triangle's plan segment: the farthest pair of its
    three plan points — ONE implementation with
    ``wall_geometry._plan_segments_indexed``'s reading, in the AUTHORED
    frame (that one carries a placement matrix; this one does not)."""
    out = []
    for t in tris.tolist():
        P = [(float(v[i][0]), float(v[i][2])) for i in t]
        best = max(((math.dist(P[i], P[j]), i, j)
                    for i in range(3) for j in range(i + 1, 3)), key=lambda q: q[0])
        if best[0] >= 0.02:
            out.append(LineString([P[best[1]], P[best[2]]]))
    return out


def _largest_part(geom):
    if geom.is_empty:
        return None
    if geom.geom_type == "Polygon":
        return geom
    parts = [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon"]
    return max(parts, key=lambda g: g.area) if parts else None


# ── signature B: the shell ───────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class ShellReading:
    """One SHELL resource in its own AUTHORED frame."""

    floor_y: float
    floor_area_m2: float
    extra_portals: tuple[str, ...]
    interior: Polygon
    wall_line: object
    inner_a: tuple[XY, ...]
    inner_b: tuple[XY, ...]
    ends: tuple[XY, XY]
    length_m: float
    width_m: float


def _ring_ends(interior: Polygon, wall, probe_m: float) -> tuple[list[list[int]], list[XY]]:
    """The trench ring's OPEN RUNS — maximal runs of consecutive ring
    edges with no wall face standing on them — and the simplified ring.
    A shell's ring is walled everywhere but at its portals; a portal
    spanning two ring edges (a chamfered mouth) is ONE run, which is why
    the edges are joined before they are counted (measured VHHH
    ``tunnel3_done``: a 44.4 m and a 2.5 m edge at one portal)."""
    ring = list(interior.simplify(_RING_SIMPLIFY_M).exterior.coords)[:-1]
    n = len(ring)
    opens: list[int] = []
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        e = LineString([a, b])
        k = max(2, int(e.length / 2.0))
        hit = sum(1 for j in range(k + 1)
                  if wall.distance(e.interpolate(j / k, normalized=True)) <= probe_m)
        if hit / (k + 1) < 0.5:
            opens.append(i)
    runs: list[list[int]] = []
    for i in opens:
        if runs and (runs[-1][-1] + 1) % n == i:
            runs[-1].append(i)
        else:
            runs.append([i])
    if len(runs) > 1 and (runs[-1][-1] + 1) % n == runs[0][0]:
        runs[0] = runs.pop() + runs[0]
    return runs, ring


def shell_reading(geom: _obj8.ObjGeometry, genuine: _t.Sequence[_obj8.Component],
                  law) -> "ShellReading | str":
    """The SHELL reading of a resource in its own authored frame, or the
    REASON it is not one (a string; every refusal names its numbers)."""
    ob = law.tables.structures.tunnel.object
    if not genuine:
        return "no genuine solid component"
    tris = np.concatenate([c.tris for c in genuine])
    v = geom.vertices
    ny = _face_normals_y(v, tris)
    area = _plan_area(v, tris)
    horiz = ny >= ob.plate_normal_y_min
    # THE FLOOR: the largest-area bin of near-horizontal faces standing
    # shell_floor_min_m or more BELOW the object's zero.  "The largest
    # horizontal plate lies >= 2 m below its zero" (§33 (6) B).
    ymax = np.maximum(np.maximum(v[tris[:, 0], 1], v[tris[:, 1], 1]), v[tris[:, 2], 1])
    deep = horiz & (ymax <= -ob.shell_floor_min_m)
    if not deep.any():
        return (f"no floor plate: no near-horizontal solid face stands "
                f"{ob.shell_floor_min_m} m (shell_floor_min_m) under the object's zero")
    # THE FLOOR IS THE DEEPEST PLATE, not the largest-AREA bin: a shell's
    # RAMPS are near-horizontal too (VHHH tunnel5's ramp faces read
    # |n_y| = 0.998 over 100 m), so the largest bin of horizontal faces is
    # a ramp's mid-height, not the floor — measured VHHH tunnel1 (a 1,514
    # m2 ramp bin at -2.50 against the 733 m2 floor at -6.95) and tunnel4
    # (2,672 m2 at -5.25 against 454 m2 at -9.01).  The floor is the
    # LOWEST bin that carries a plate's worth, and its level is that
    # plate's own lowest vertex.
    binned = np.floor(ymax / ob.plate_bin_m).astype(int)
    bins: dict[int, float] = {}
    for k, a in zip(binned[deep].tolist(), area[deep].tolist()):
        bins[k] = bins.get(k, 0.0) + a
    floors = [k for k, a in bins.items() if a >= ob.plate_min_area_m2]
    if not floors:
        best = max(bins, key=lambda k: bins[k])
        return (f"the deepest plate is {bins[best]:.0f} m2 at {best * ob.plate_bin_m:+.2f} m "
                f"(< plate_min_area_m2 {ob.plate_min_area_m2:.0f}): not a tunnel floor")
    best = min(floors)
    floor_sel = deep & (binned == best)
    ymin_t = np.minimum(np.minimum(v[tris[:, 0], 1], v[tris[:, 1], 1]), v[tris[:, 2], 1])
    floor_y = float(ymin_t[floor_sel].min())
    floor_area = float(bins[best])
    # THE TRENCH OUTLINE — every non-vertical face's plan (the floor
    # plates AND the ramps between them), never the hull.
    interior = _largest_part(unary_union(_plan_polys(v, tris[horiz])))
    if interior is None or interior.area < ob.plate_min_area_m2:
        return "the shell's non-vertical faces have no plan area"
    segs = _plan_segments(v, tris[~horiz])
    if not segs:
        return "the shell has no vertical wall face"
    wall = unary_union(segs)
    runs, ring = _ring_ends(interior, wall, _WALL_PROBE_M)
    if len(runs) < 2:
        return (f"the trench ring has {len(runs)} open end(s), not 2 "
                f"(a shell is walled everywhere but at its portals)")
    n = len(ring)
    extra = ()
    if len(runs) > 2:
        # A MULTI-PORTAL SHELL (VHHH tunnel2_done: 28,525 m2, five
        # openings): the corridor's two ENDS are its two longest portals
        # and the others stand inside a wall chain.  The trench outline is
        # the shell's own interior either way, so a chain crossing a side
        # portal cannot let the cut out of the object.
        def run_len(r: list[int]) -> float:
            return sum(math.dist(ring[k], ring[(k + 1) % n]) for k in r)
        ordered = sorted(runs, key=run_len, reverse=True)
        extra = tuple(f"{run_len(r):.1f} m" for r in ordered[2:])
        runs = sorted(ordered[:2], key=lambda r: r[0])
    i, j = runs[0][-1], runs[1][-1]        # the LAST edge of each open run
    i0, j0 = runs[0][0], runs[1][0]        # …and the first
    chain_a = [ring[(i + 1 + k) % n] for k in range((j0 - i) % n)]
    chain_b = [ring[(j + 1 + k) % n] for k in range((i0 - j) % n)]
    if len(chain_a) < 2 or len(chain_b) < 2:
        return "a portal edge leaves no wall chain"
    ends = (((ring[i0][0] + ring[(i + 1) % n][0]) / 2.0,
             (ring[i0][1] + ring[(i + 1) % n][1]) / 2.0),
            ((ring[j0][0] + ring[(j + 1) % n][0]) / 2.0,
             (ring[j0][1] + ring[(j + 1) % n][1]) / 2.0))
    # chain_a runs end0 -> end1; chain_b runs end1 -> end0: reverse it so
    # both inner faces run the same way (``WallLines``' own convention)
    chain_b = list(reversed(chain_b))
    la, lb = LineString(chain_a).length, LineString(chain_b).length
    length = (la + lb) / 2.0
    if length < ob.hull_min_length_m:
        return f"a stub: the shell's walls run {length:.1f} m (< hull_min_length_m)"
    # THE WALL LINE AS A BAND (§33 (6) B "the shell's per-band wall
    # line"): the wall faces' plan segments widened to the law's own wall
    # thickness, so the stations can read a thickness at every point and
    # ``object_cut_offset`` has a region to measure against.
    band = unary_union([s.buffer(ob.wall_face_max_thickness_m / 2.0,
                                 cap_style="flat", join_style="mitre")
                        for s in segs]).buffer(0)
    return ShellReading(floor_y, floor_area, extra, interior, band,
                        tuple(chain_a), tuple(chain_b), ends, float(length),
                        float(interior.area / max(length, 1e-9)))


def _cover_plate(geom: _obj8.ObjGeometry, law) -> tuple[object | None, float]:
    """The COVER's flat ``HARD_DECK`` plate in the AUTHORED frame and its
    area: near-horizontal hard-deck faces at ``|y| <= cover_flush_m``.
    ``HARD_DECK`` is the machine-readable marker of the cover (§33 (6) B)."""
    ob = law.tables.structures.tunnel.object
    tris = geom.solid[geom.hardness == _obj8.HARD_DECK]
    if tris.shape[0] == 0:
        return None, 0.0
    v = geom.vertices
    ny = _face_normals_y(v, tris)
    cy = (v[tris[:, 0], 1] + v[tris[:, 1], 1] + v[tris[:, 2], 1]) / 3.0
    sel = (ny >= ob.plate_normal_y_min) & (np.abs(cy) <= ob.cover_flush_m)
    if not sel.any():
        return None, 0.0
    plate = unary_union(_plan_polys(v, tris[sel]))
    return (plate if not plate.is_empty else None), float(plate.area)


def _cover_stations(geom: _obj8.ObjGeometry, axis: LineString, mat, law
                    ) -> tuple[tuple[float, float], ...]:
    """THE RAMP STATIONS FROM THE COVER'S OWN PROFILE (§33 (6) B): the
    cover's hard-deck faces binned every ``cover_station_m`` along the
    corridor axis, each bin reporting the LOWEST authored y in it —
    VHHH ``tunnel5_done_TN``: 0.00 -> -0.91 -> -1.71 -> -6.01."""
    ob = law.tables.structures.tunnel.object
    tris = geom.solid[geom.hardness == _obj8.HARD_DECK]
    if tris.shape[0] == 0 or axis.length <= 0.0:
        return ()
    v = geom.vertices
    a, b, d, e, xoff, yoff = mat
    xs = v[:, 0] * a + v[:, 2] * b + xoff
    ys = v[:, 0] * d + v[:, 2] * e + yoff
    lo: dict[int, float] = {}
    for t in tris.tolist():
        ss = [axis.project(Point(float(xs[i]), float(ys[i]))) for i in t]
        yy = min(float(v[i][1]) for i in t)
        for s in ss:
            k = int(s // ob.cover_station_m)
            lo[k] = min(lo.get(k, 1e9), yy)
    return tuple((k * ob.cover_station_m + ob.cover_station_m / 2.0, y)
                 for k, y in sorted(lo.items()))


def read_shells(airport, objects: _t.Sequence[_obj8.PlacedObject],
                cache: _obj8.ResourceCache, law,
                taken: _t.AbstractSet[str] = frozenset()
                ) -> tuple[list[ObjectCut], ObjectCutStats]:
    """Every SIGNATURE-B object cut the pack states (§33 (6) B), in the
    airport frame.  ``taken`` are resources a senior reader already
    admitted — an object is read ONCE."""
    import time as _time
    t0 = _time.perf_counter()
    stats = ObjectCutStats()
    ob = law.tables.structures.tunnel.object
    msl = {o.id: o.y_offset_m for o in airport.dsf_objects if o.kind == "OBJECT_MSL"}
    readings: dict[str, "ShellReading | str"] = {}
    covers: dict[str, tuple[object | None, float]] = {}
    counts: dict[str, int] = {}
    placed: list[_obj8.PlacedObject] = []
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        counts[o.path] = counts.get(o.path, 0) + 1
        placed.append(o)
    # the cheap gate: a resource whose solids never reach shell_floor_min_m
    # under the object's zero cannot be a shell (never READ, never a verdict)
    out: list[ObjectCut] = []
    k_by_res: dict[str, int] = {}
    for o in placed:
        if o.path in taken:
            continue
        vmin, _vmax, _x0, _x1, _z0, _z1 = cache.y_range(o.resolved)
        if vmin > -ob.shell_floor_min_m:
            continue
        if o.path not in readings:
            stats.screened += 1
            g = cache.geometry(o.resolved)
            readings[o.path] = (shell_reading(g, cache.genuine(o.resolved), law)
                                if g is not None else "unreadable OBJ8")
        r = readings[o.path]
        if isinstance(r, str):
            continue
        # THE COVER at the SAME PLACEMENT (position within
        # cover_placement_tol_m, same heading) or INSIDE the same object.
        cover = None
        cov_area = 0.0
        cov_obj = None
        for p in placed:
            # THE COVER IS A SECOND PLACEMENT, never the shell itself.
            # §33 (6) B allows "or inside the same object"; MEASURED at
            # VHHH that self-cover form admits ``sea_X.obj`` — a 92.2 m
            # wide sea barrier whose own flush hard deck covers its own
            # -20.88 m floor — as a tunnel.  The pack's convention is a
            # PAIR (VHHH ``tunnelN_done`` + ``tunnelN_done_TN``, EGLL
            # ``Na.obj`` + ``N.obj``), so the pair is the signature and
            # the spec text yields to the measurement (the 13r precedent).
            if p is o or p.path == o.path:
                continue
            if (math.hypot(p.xy[0] - o.xy[0], p.xy[1] - o.xy[1])
                    > ob.cover_placement_tol_m
                    or abs(((p.heading_deg - o.heading_deg + 180.0) % 360.0) - 180.0) > 1.0):
                continue
            if p.path not in covers:
                g2 = cache.geometry(p.resolved)
                covers[p.path] = _cover_plate(g2, law) if g2 is not None else (None, 0.0)
            c, a = covers[p.path]
            if c is not None and a > cov_area:
                cover, cov_area, cov_obj = c, a, p
        if cover is None:
            stats.refused.append(
                f"{o.id} {_base(o.path)}: a SHELL (floor plate {r.floor_area_m2:.0f} m2 at "
                f"{r.floor_y:+.2f} m, trench {r.interior.area:.0f} m2) with no flush HARD_DECK "
                f"cover at the same placement (§33 (6) B) — not a signature-B cut")
            continue
        mat = _obj8.placement_affine(o.xy, o.heading_deg)
        place = lambda gm: shapely.affinity.affine_transform(gm, mat)  # noqa: E731
        outline = place(r.interior)
        chain_a = tuple(_apply(mat, p) for p in r.inner_a)
        chain_b = tuple(_apply(mat, p) for p in r.inner_b)
        ends = (_apply(mat, r.ends[0]), _apply(mat, r.ends[1]))
        zero = float(msl[o.id]) if o.kind == "OBJECT_MSL" else float(o.anchor_z + o.agl_m)
        axis = LineString([((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)
                           for p, q in zip(_resample(chain_a, 32), _resample(chain_b, 32))])
        gcov = cache.geometry(cov_obj.resolved)
        sts = _cover_stations(gcov, axis, _obj8.placement_affine(cov_obj.xy, cov_obj.heading_deg),
                              law) if gcov is not None else ()
        k = k_by_res.get(o.path, 0)
        k_by_res[o.path] = k + 1
        notes = [f"signature B (§33 (6)): shell {_base(o.path)} floor plate "
                 f"{r.floor_area_m2:.0f} m2 at {r.floor_y:+.2f} m, trench {r.interior.area:.0f} "
                 f"m2, walls {r.length_m:.0f} m x {r.width_m:.1f} m",
                 f"cover {_base(cov_obj.path)}: flush HARD_DECK plate {cov_area:.0f} m2 at "
                 f"|y| <= cover_flush_m {ob.cover_flush_m}",
                 f"floor {zero + r.floor_y:.2f} = the object's zero {zero:.2f} "
                 f"{r.floor_y:+.2f} (AUTHORED — it overrides bore_datum_m)"]
        if sts:
            notes.append("ramp stations from the cover's profile: "
                         + " -> ".join(f"{y:+.2f}" for _s, y in sts))
        out.append(ObjectCut(f"object-cut:{_base(o.path)}@{k}", o.path, o.id, SHELL,
                             outline, place(r.wall_line), chain_a, chain_b, ends,
                             (True, True), zero + r.floor_y, r.floor_y, zero,
                             place(cover), sts, tuple(notes)))
        stats.shells += 1
        stats.covers_paired += 1
    for path, r in readings.items():
        if isinstance(r, str):
            stats.refused.append(f"{_base(path)} x{counts.get(path, 1)}: {r}")
    out.sort(key=lambda c: c.id)
    stats.claimed = len({c.object_id for c in out})
    stats.read_s = _time.perf_counter() - t0
    return out, stats


def _base(path: str) -> str:
    import os
    return os.path.basename(path)


def _apply(mat, p: XY) -> XY:
    a, b, d, e, xoff, yoff = mat
    return (a * p[0] + b * p[1] + xoff, d * p[0] + e * p[1] + yoff)


def _resample(pts: _t.Sequence[XY], n: int) -> list[XY]:
    ln = LineString(pts)
    return [(q.x, q.y) for q in (ln.interpolate(k / (n - 1), normalized=True)
                                 for k in range(n))]


# ── signature A: REFUTED, and why nothing stands here ────────────────────
#
# §33 (6) A rules that the CRESTED-WALL signature — solids descending
# below the object's own zero WITH a crest plate ``plate_min_height_m``
# above it — should replace the per-airport affordance
# ``kerb_wall_corridors`` ("the signature admits, not the ICAO").
# MEASURED and REFUTED in one dry VHHH `--stage structures` replay (lane
# `v2objcut`, 2026-09-15): the predicate admits an ordinary BUILDING,
# because a building has a roof.  VHHH wall corridors went 0 -> 116 (bay
# 28, level 88), every one of them inside ``CITY2.obj`` — a city-block
# object off the field whose foundation walls descend 6.4-8.5 m under
# their ground — and no depth threshold repairs it, since OTHH's own
# admitted bays are 1.35 m deep.  That is RULINGS 2026-09-10ap's seven
# rounds at a THIRD airport.  The predicate is DELETED rather than kept
# gated (the standing law on refuted mechanisms); the affordance gate in
# ``airport/wall_corridors.py`` stands with this refutation recorded
# beside it, and §33 (6) A is an intent question for the owner.

# ── signature C: the thin surface bands ──────────────────────────────────

@_dc.dataclass(frozen=True)
class ThinBand:
    """One THIN SURFACE WALL in the AIRPORT frame (§33 (6) C): a solid
    under ``parapet_max_height_m`` tall, at least ``parapet_min_aspect``
    times longer than it is high, under ``parapet_max_width_m`` wide in
    plan, sitting on the surface (``y_min >= parapet_y_min``)."""

    comp: int
    poly: Polygon
    axis: LineString
    length_m: float
    width_m: float
    height_m: float
    bearing_deg: float


def _bearing(ln: LineString) -> float:
    (x0, y0), (x1, y1) = ln.coords[0], ln.coords[-1]
    return (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360.0) % 180.0


def thin_bands(geom: _obj8.ObjGeometry, genuine: _t.Sequence[_obj8.Component],
               mat, law) -> list[ThinBand]:
    """The resource's thin surface walls, in the AIRPORT frame.

    THE BAND IS A STRAIGHT RUN, NOT A COMPONENT.  A pack welds a whole
    structure into one solid component — measured LEMD ``Bridge3.obj``:
    280 triangles in TWO components (z -354.2…-281.0 and z -57.6…0, with
    224 m of the object's 354.2 m box carrying no solid at all), whose
    convex hulls read 73 x 16 m and 58 x 15 m and are not walls by any
    gate.  Its walls are inside those components: comp 0's vertical faces
    split into two 73.0 / 73.1 m runs 1.00 m thick at one bearing — the
    PAIR.  So the reading is LAW C's own band machinery
    (``wall_geometry._plan_segments_indexed`` / ``_straight_runs`` /
    ``_band_polygon`` / ``_rect_axis``, ONE derivation, never a second
    spelling) under signature C's surface gates."""
    from . import wall_geometry as _wg
    ob = law.tables.structures.tunnel.object
    wc = law.tables.structures.cutout.wall_corridor
    out: list[ThinBand] = []
    v = geom.vertices
    for k, c in enumerate(genuine):
        h = c.max_y - c.min_y
        if h > ob.parapet_max_height_m or c.min_y < ob.parapet_y_min:
            continue
        ny = _face_normals_y(v, c.tris)
        vert = c.tris[ny < ob.plate_normal_y_min]
        if vert.shape[0] == 0:
            continue
        segs = _wg._plan_segments_indexed(v, vert, mat)
        if not segs:
            continue
        for run in _wg._straight_runs(segs, wc.parallel_max_deg,
                                      ob.wall_face_max_thickness_m):
            poly, thick = _wg._band_polygon([segs[i][0] for i in run])
            if poly is None:
                continue
            ra = _wg._rect_axis(poly)
            if ra is None:
                continue
            axis, length, brg = ra
            if thick > ob.parapet_max_width_m \
                    or length < ob.parapet_min_aspect * max(h, 0.05):
                continue
            out.append(ThinBand(k, poly, axis, float(length), float(thick), float(h),
                                float(brg)))
    return out


def band_pair(bands: _t.Sequence[ThinBand], law
              ) -> "tuple[ThinBand, ThinBand, float] | None":
    """The PARALLEL PAIR of thin walls (§33 (6) C1/C3) — two bands within
    ``parallel_max_deg`` of each other, their axes
    ``pair_spacing_min_m``..``pair_spacing_max_m`` apart, overlapping
    ``pair_overlap_min_fraction`` of the shorter along the axis — and the
    INNER spacing (axis separation less the two half widths).  The
    widest-overlap pair wins."""
    ob = law.tables.structures.tunnel.object
    wc = law.tables.structures.cutout.wall_corridor
    best = None
    for i in range(len(bands)):
        for j in range(i + 1, len(bands)):
            A, B = bands[i], bands[j]
            d = abs(A.bearing_deg - B.bearing_deg) % 180.0
            if min(d, 180.0 - d) > wc.parallel_max_deg:
                continue
            gap = A.axis.distance(B.axis)
            if gap <= 1e-6:
                gap = float(np.mean([A.axis.distance(Point(q)) for q in B.axis.coords]))
            if not (ob.pair_spacing_min_m <= gap <= ob.pair_spacing_max_m):
                continue
            brg = math.radians(A.bearing_deg)
            u = (math.sin(brg), math.cos(brg))
            sa = sorted(q[0] * u[0] + q[1] * u[1] for q in A.poly.exterior.coords)
            sb = sorted(q[0] * u[0] + q[1] * u[1] for q in B.poly.exterior.coords)
            ov = min(sa[-1], sb[-1]) - max(sa[0], sb[0])
            if ov < ob.pair_overlap_min_fraction * min(A.length_m, B.length_m):
                continue
            inner = gap - (A.width_m + B.width_m) / 2.0
            if best is None or ov > best[3]:
                best = (A, B, inner, ov)
    return (best[0], best[1], best[2]) if best is not None else None


# ── the claim: what basins.py must not see ───────────────────────────────

def cut_placement_ids(cuts: _t.Sequence[ObjectCut]) -> frozenset[str]:
    """THE ONE DERIVATION of "this placement is the author's cut geometry,
    not a pit" (§33 (6): "the shell is never a basin").  Every consumer
    that used to ask ``o.witnesses`` — ``planar/basins.build_basins``'s
    intake and ``basin_witness.basin_member_ids``'s exemption set — reads
    this, and no second spelling of it exists."""
    return frozenset(c.object_id for c in cuts)
