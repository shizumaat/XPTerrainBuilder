"""THE AT-GRADE READ, MEMOISED PER RESOURCE (owner RULINGS 2026-09-13bp).

``obj8.at_grade_geometry`` / ``above_grade_footprint`` clipped and unioned
the same pack resource ONCE PER PLACEMENT.  VHHH: 5,078 custom objects over
785 resources and 74 basin rings — 2,626 s of a 3,800 s build inside
``unary_union`` and ``obj8_clip._clip_both``, ~25 MB retained per placement
(2.2 -> 10.0 GB in 7 minutes; the app's worker 34.9 GB), and untimed, so it
read as a hang.  The clip and the union depend only on ``(resource, the
components' clip planes)``: the placement affine is RIGID and commutes with
both, so it is applied afterwards and only IT is paid per placement.

Split from ``obj8.py`` under the 1,000-line file law, exactly as
``obj8_clip.py`` is; the laws and the readers stay there and nothing
numeric lives here but the plane quantum the ruling names.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
from shapely.ops import unary_union

from . import frame_entry as _fe
from .obj8_clip import _clip_both, _clip_component

if _t.TYPE_CHECKING:  # annotations only — obj8 imports this module
    from .obj8 import Component, ObjGeometry, PlacedObject, ResourceCache

__all__ = ["GradeStats", "planes", "memo_union", "both_clip", "above_clip", "LATER", "POLYS",
           "BasePlane", "Riser", "BaseProfile", "base_profile", "compose_profiles",
           "FLAT", "STEPPED", "SLOPED", "FEET",
           "profile_to_json", "profile_from_json"]


@_dc.dataclass
class GradeStats:
    """THE AT-GRADE READ, TIMED (owner RULINGS 2026-09-13bp (iii)).  The
    clip + union behind ``at_grade_geometry`` / ``above_grade_footprint``
    was UNTIMED, so VHHH's 2,626 s planar stage read as a hang: 5,078
    custom placements re-clipped and re-unioned FIVE pack resources once
    each, ~0.9 s and ~25 MB a placement.  ``calls`` is the placements
    asked, ``unions`` the clip+union actually run (one per distinct
    ``(resource, planes)`` key — (i)), ``vertices`` what those unions
    consumed and ``seconds`` what they cost.  ``vertex_budget`` (law
    ``[basin] rim_read_vertex_budget``, 0 = unbounded) is the REFUSAL: a
    pack past it stops being read and is named, instead of a silent 44
    minutes."""

    calls: int = 0
    unions: int = 0
    vertices: int = 0
    seconds: float = 0.0
    vertex_budget: int = 0
    over_budget: bool = False
    resources: set = _dc.field(default_factory=set)

    def asked(self, cover: bool, linework: bool, key: tuple, placement: str) -> None:
        """One request of :func:`memo_union`, before it is answered.  The
        build's own stats keep nothing of it; a work-pool worker's
        (``grade_ledger.Recorder``) keep the request, so the build's
        process can charge it as one core would (issue #362)."""

    def charge(self, resource: str, vertices: int, seconds: float) -> None:
        self.unions += 1
        self.vertices += vertices
        self.seconds += seconds
        self.resources.add(resource)
        if self.vertex_budget and self.vertices > self.vertex_budget:
            self.over_budget = True

    def pack(self) -> str:
        """The pack the read is charged to — the resources' common root."""
        if not self.resources:
            return "(no resource)"
        paths = sorted(self.resources)
        try:
            return os.path.commonpath(paths)
        except ValueError:
            return os.path.dirname(paths[0])



#: The plane QUANTUM (metres) of the memo key.  The clip plane is the DEM
#: under a component's centroid minus the placement's render datum: a
#: continuous number that would make every placement its own key.  It is
#: rounded to the centimetre — the ONE rounding this memo introduces, and
#: the reason LEMD's and OTHH's basin rims are replayed for byte-identity.
_PLANE_QUANTUM = 2

#: the sentinel a memoised ``None`` clip must not be mistaken for
_MISS = object()

#: the linework of a ``both_clip`` entry no reader has asked for yet
#: (:func:`memo_union`, ``linework=False``)
LATER = object()

#: the last element of a ``clip_memo`` key that holds one component's
#: at-grade POLYGONS alone (:func:`_comp_clip`)
POLYS = "polys"


def planes(o: "PlacedObject", comps: list[tuple[int, "Component"]],
           dem_z: _t.Callable[[float, float], float], base: float, band: float,
           above: bool, to_frame) -> tuple[tuple[int, float], ...]:
    """``(component index, clip plane)`` for the components the read
    keeps, the plane quantised — the memo key's second half.  ``to_frame``
    is ``obj8``'s own authored-to-frame map (passed, not imported: this
    module must not import back into ``obj8``)."""
    out = []
    for ci, comp in comps:
        cx, cy = to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        plane = round(local - base + band if above else local - base - band, _PLANE_QUANTUM)
        if comp.max_y < plane:
            continue
        out.append((ci, plane))
    return tuple(out)


def above_clip(v: np.ndarray, comp: "Component", plane: float):
    """One component's above-plane geometry as the cover reader wants it."""
    return _clip_component(v, comp, plane, False)


def both_clip(v: np.ndarray, comp: "Component", plane: float):
    return _clip_both(v, comp, plane)


def _line_union(lines: list):
    """The linework half of a ``both_clip`` entry: Law B's union, ``None``
    when nothing is left."""
    lu = _fe.union(lines, "obj8_grade.lines") if lines else None
    return None if lu is not None and lu.is_empty else lu


def _comp_clip(cmemo: dict, resource: str, ci: int, plane: float, clip, v: np.ndarray,
               comp: "Component", linework: bool = True) -> tuple[object, int]:
    """One component's clip at one plane, made once, and the vertices the
    read is CHARGED for it (0 on a hit).

    A ``both_clip`` reader that wants no linework (``linework=False``,
    issue #362) is given ``(LATER, polygons)``: the polygons of
    ``_clip_both`` ARE ``_clip_component``'s above-plane clip — the same
    statements over the same triangles — so they are made without the
    per-component linework union and kept under their own key.  A full
    read that follows makes the linework then and is charged nothing: the
    component was charged when its polygons were read."""
    both = clip is both_clip
    ck = (resource, ci, plane, both)
    out = cmemo.get(ck, _MISS)
    if out is not _MISS:
        return out, 0
    nv = int(comp.tris.shape[0]) * 3
    pk = (resource, ci, plane, POLYS)
    if both and not linework:
        pg = cmemo.get(pk, _MISS)
        if pg is not _MISS:
            return (LATER, pg), 0
        pg = cmemo[pk] = _clip_component(v, comp, plane, False)
        return (LATER, pg), nv
    out = cmemo[ck] = clip(v, comp, plane)
    return out, 0 if both and pk in cmemo else nv


def _lines_now(cache: "ResourceCache", memo: dict, key: tuple, pu, g: "ObjGeometry",
               comps: list[tuple[int, "Component"]]):
    """A ``both_clip`` entry whose linework was left :data:`LATER`,
    completed for the first reader that wants it — the same members in the
    same order the eager union took, so the linework is the one the eager
    read made."""
    t0 = time.perf_counter()
    by_index = dict(comps)
    lines = []
    for ci, plane in key[1]:
        comp = by_index.get(ci)
        if comp is None:
            continue
        ln = _comp_clip(cache.clip_memo, key[0], ci, plane, both_clip, g.vertices, comp)[0][0]
        if ln is not None:
            lines.append(ln)
    val = memo[key] = (_line_union(lines), pu)
    cache.grade.seconds += time.perf_counter() - t0
    return val


def memo_union(cache: "ResourceCache", memo: dict, o: "PlacedObject", g: "ObjGeometry",
               comps: list[tuple[int, "Component"]], keyed: tuple[tuple[int, float], ...],
               clip, linework: bool = True):
    """The resource's clipped geometry in ITS OWN frame for ``planes``,
    computed once and retained per ``(resource, planes)``.  ``clip`` is
    ``both_clip`` (linework + polygons) or ``above_clip`` (polygons).
    Past the vertex budget the read REFUSES — the pack is named by the
    caller and nothing further is clipped (RULINGS 2026-09-13bp (iii)).

    ``linework=False`` (issue #362) is a ``both_clip`` reader that takes
    the POLYGONS only: the union of the components' linework is not made
    for it — the entry holds :data:`LATER` in its place — and the first
    reader that does want it completes the entry (:func:`_lines_now`)."""
    st = cache.grade
    st.calls += 1
    key = (o.resolved, keyed)
    st.asked(memo is cache.cover_memo, bool(linework) and clip is both_clip, key, o.id)
    if key in memo:
        val = memo[key]
        if linework and clip is both_clip and val is not None and val[0] is LATER:
            return _lines_now(cache, memo, key, val[1], g, comps)
        return val
    if st.over_budget:
        return None
    by_index = dict(comps)
    t0 = time.perf_counter()
    lines, polys, nv = [], [], 0
    # THE COMPONENT CLIP IS THE SECOND LEVEL.  A resource's components sit
    # at different planes (the DEM under each centroid), so two placements
    # rarely agree on ALL of them — but they agree on most, and the clip
    # (with ``_clip_both``'s own union inside it) is where the seconds are.
    cmemo = cache.clip_memo
    for ci, plane in keyed:
        comp = by_index.get(ci)
        if comp is None:
            continue
        out, charged = _comp_clip(cmemo, o.resolved, ci, plane, clip, g.vertices, comp, linework)
        nv += charged
        if clip is both_clip:
            ln, pg = out
            if ln is not None and ln is not LATER:
                lines.append(ln)
            if pg is not None:
                polys.append(pg)
        elif out is not None:
            polys.append(out)
    pu = _fe.union(polys, "obj8_grade.polys") if polys else None
    if pu is not None and pu.is_empty:
        pu = None
    if clip is both_clip:
        val = (_line_union(lines) if linework else LATER, pu)
    else:
        val = pu
    memo[key] = val
    st.charge(o.resolved, nv, time.perf_counter() - t0)
    return val


# ── §1 THE BASE PROFILE ──────────────────────────────────────────────────
# base-profile spec §1 (owner RULINGS 2026-10-01f, answers 10-01k).  ONE
# DERIVATION SITE (§1 (4)): this function, called from the pack read
# inside ``obj8.ResourceCache`` once per RESOURCE — the triangles and the
# solid components are already in memory there, so the base read is one
# more O(triangles) pass over geometry nothing else has to re-parse.  The
# planar stage and the object stage both read the ANSWER; neither
# re-derives it from the DSF or the OBJ (the census-wrapper defect class,
# RULINGS 2026-08-30l).
#
# It lives beside ``planes`` for the reason this module exists: the laws
# and the readers stay in ``obj8.py``, the O(triangles) passes live here
# under the 1,000-line file law.

#: §1 (2) THE FOUR VERDICTS.  Literals, because they cross the wire (the
#: rebake plan, the sidecar and ``obj8_split_report``) — named here so no
#: reader spells one by hand.
FLAT, STEPPED, SLOPED, FEET = "flat", "stepped", "sloped", "feet"

#: §1 (1): the height BIN a horizontal face is dropped into before the
#: merge, in metres.  The spec's own number.  Clusters are RUNS of
#: adjacent non-empty bins merged while the gap is within ``split_tol_m``
#: (0.3) — which, the bin being narrower than the tolerance, is every
#: adjacent pair: the bin is the quantum, ``split_tol_m`` is the law.
_PLANE_BIN_M = 0.25


@_dc.dataclass(frozen=True)
class BasePlane:
    """§1 (1) ONE BASE PLANE of a member or a composed unit: its authored
    height, the area of the horizontal faces that made it, and its plan
    POLYGON — the UNION of those faces (never the bbox, never the hull:
    an L-shaped lot around a building would otherwise "contain" the
    building, §4, and the KASE parts' convex hull overlaps 57 % of the
    lot it must not claim)."""

    y: float
    area_m2: float
    polygon: _t.Any
    #: the roof test's own reading, kept so a report can say WHY a plane
    #: was taken as a base: the support hull's share of the polygon
    #: (§1 (1); < ``roof_support_fraction`` is a base)
    support_fraction: float = 0.0
    #: the area §1 (1) TRIMMED off this plane towards a lower plane (the
    #: cells within ``pad_frontage_m`` of the few lower vertices inside
    #: it — KASE's garage threshold, 31 m² of 6,394)
    trimmed_m2: float = 0.0


@_dc.dataclass(frozen=True)
class Riser:
    """§1 (1) THE RISER between two adjacent base planes — the pair's
    indices into :attr:`BaseProfile.planes` and the height difference.
    Only planes whose polygons are within ``[seam] pad_frontage_m`` of
    each other are adjacent; a riser under ``[terrace]
    pad_terrace_floor_m`` has already WELDED (a kerb is not a terrace)
    and never reaches this record."""

    a: int
    b: int
    dy: float


@_dc.dataclass(frozen=True)
class BaseProfile:
    """§1 (2) THE BASE PROFILE of one member, or of a composed §16g unit
    (:func:`compose_profiles`).

    ``planes`` is ordered with the ORIGIN PLANE ``p0`` first (§1 (3)) and
    every other plane carries its offset ``Δy_k = y_k − y_0``; ``risers``
    names the adjacent pairs; ``slope`` is the SLOPED verdict's own base
    gradient ``(g_x, g_z)`` in the AUTHORED frame (the pad rotates it by
    the placement heading — §1 (2): orientation is carried by the
    polygons, so a pad's edges follow the base polygon)."""

    verdict: str
    planes: tuple[BasePlane, ...] = ()
    risers: tuple[Riser, ...] = ()
    slope: tuple[float, float] = (0.0, 0.0)
    #: the plane fit's rms residual over the set the verdict was read on
    #: (the contact set for FLAT / SLOPED / FEET, 0 for STEPPED)
    residual_rms_m: float = 0.0
    #: §1 (1) THE FEET: how many ground-contact vertices the read saw and
    #: the height they sit at (the member's lowest vertex + the band).
    #: The FEET verdict publishes nothing else — 10-01k Q1 seats such a
    #: body by TILTING it, and the tilt is fitted on the feet.
    feet: int = 0
    feet_y: float = 0.0
    #: §1 (2) narrowed (see :func:`base_profile`): the share of the FEET
    #: set's plan hull covered by horizontal faces at the contact band —
    #: the FLOOR test that separates a small floor plate (FLAT) from a
    #: column-only shelter (FEET, KASE site 1).  Published so the spec
    #: author's ruling on the narrowing can be read off a report.
    floor_fraction: float = 0.0
    #: why the verdict came out as it did, for the report line (never a
    #: silent ``feet``)
    why: str = ""

    @property
    def offsets(self) -> tuple[float, ...]:
        """§1 (3) ``Δy_k = y_k − y_0`` per plane (``p0`` reads 0.0)."""
        if not self.planes:
            return ()
        y0 = self.planes[0].y
        return tuple(float(p.y - y0) for p in self.planes)

    def line(self) -> str:
        if self.verdict == SLOPED:
            return (f"{self.verdict} {100.0 * math.hypot(*self.slope):.2f} % "
                    f"rms {self.residual_rms_m:.3f} m")
        if not self.planes:
            return f"{self.verdict} ({self.feet} feet at {self.feet_y:+.2f})"
        return (f"{self.verdict} {len(self.planes)} plane(s) "
                + " / ".join(f"{p.y:+.2f} {p.area_m2:,.0f} m2" for p in self.planes)
                + (" risers " + ", ".join(f"{r.dy:+.2f}" for r in self.risers)
                   if self.risers else ""))


def _horizontal(v: np.ndarray, tris: np.ndarray, ny_min: float):
    """``(|n_y| per triangle, twice the PLAN area per triangle, the mean
    y per triangle)`` — one vectorised pass.  The plan area is the right
    one for a face's own area in a HEIGHTFIELD reading: a horizontal face
    at ``|ny| >= 0.95`` differs from its plan projection by at most 5 %,
    and the pad it becomes is a plan polygon."""
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    ny = np.zeros(tris.shape[0])
    ny[ok] = np.abs(n[ok, 1] / ln[ok])
    # twice the signed plan area of the triangle (x, z)
    a2 = np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 2] - p0[:, 2])
                - (p2[:, 0] - p0[:, 0]) * (p1[:, 2] - p0[:, 2]))
    ymean = (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0
    return ny >= ny_min, 0.5 * a2, ymean


def _clusters(ys: np.ndarray, areas: np.ndarray, merge_m: float
              ) -> list[tuple[float, float, np.ndarray]]:
    """§1 (1): the height CLUSTERS of horizontal faces — ``(area-weighted
    y, area, the face selector)`` per cluster.  Faces are binned at
    :data:`_PLANE_BIN_M` and adjacent bins MERGE while their gap is
    within ``merge_m`` (``[placement] split_tol_m``)."""
    if ys.size == 0:
        return []
    bins = np.floor(ys / _PLANE_BIN_M).astype(np.int64)
    uniq = np.unique(bins)
    out: list[tuple[float, float, np.ndarray]] = []
    run = [uniq[0]]
    for b in uniq[1:]:
        # the GAP between the two bins' near edges, in metres
        if (b - run[-1]) * _PLANE_BIN_M <= merge_m:
            run.append(b)
        else:
            out.append(_cluster(ys, areas, bins, run))
            run = [b]
    out.append(_cluster(ys, areas, bins, run))
    return out


def _cluster(ys, areas, bins, run) -> tuple[float, float, np.ndarray]:
    sel = np.isin(bins, np.asarray(run))
    a = float(areas[sel].sum())
    # §09-17t's own rule shape: the AREA-WEIGHTED height (the median over
    # a cluster of equal faces is the same number; the weighting is what
    # keeps a 6,399 m² lot from being moved by a 47 m² sliver beside it)
    y = float((ys[sel] * areas[sel]).sum() / a) if a > 0.0 else float(ys[sel].mean())
    return (y, a, sel)


def _plan_union(v: np.ndarray, tris: np.ndarray):
    """The plan UNION of the faces ``tris`` in authored ``(x, z)`` — §1
    (1)'s POLYGON, by the same construction ``obj8._plan_footprint``
    uses for a component's footprint (the rings unioned, never a hull)."""
    from .obj8_clip import _union_rings
    if tris.shape[0] == 0:
        return None
    return _union_rings([[(float(v[i][0]), float(v[i][2])) for i in tri]
                         for tri in tris.tolist()])


def _fit_plane(pts: np.ndarray) -> tuple[float, float, float, float]:
    """Least-squares plane through ``(x, y, z)`` points: ``(g_x, g_z,
    y0, rms residual)`` with ``y ≈ y0 + g_x·(x−x̄) + g_z·(z−z̄)``.  A
    degenerate set (collinear in plan, or fewer than 3 points) reads a
    LEVEL fit at the mean, with the spread as the residual — the same
    fallback ``planar/platform._plane_residual`` takes."""
    if pts.shape[0] < 3:
        y = float(pts[:, 1].mean()) if pts.shape[0] else 0.0
        r = float(np.max(np.abs(pts[:, 1] - y))) if pts.shape[0] else 0.0
        return (0.0, 0.0, y, r)
    x0, z0 = float(pts[:, 0].mean()), float(pts[:, 2].mean())
    M = np.c_[np.ones(pts.shape[0]), pts[:, 0] - x0, pts[:, 2] - z0]
    if np.linalg.matrix_rank(M) < 3:
        y = float(pts[:, 1].mean())
        return (0.0, 0.0, y, float(np.sqrt(np.mean((pts[:, 1] - y) ** 2))))
    c, *_ = np.linalg.lstsq(M, pts[:, 1], rcond=None)
    res = pts[:, 1] - M @ c
    return (float(c[1]), float(c[2]), float(c[0]),
            float(np.sqrt(np.mean(res ** 2))))


def base_profile(geom: "ObjGeometry", comps: list["Component"], *,
                 horizontal_ny: float, roof_support_fraction: float,
                 sloped_min_extent_m: float, sloped_max: float,
                 min_area_m2: float, split_tol_m: float, contact_band_m: float,
                 pad_terrace_floor_m: float, pad_frontage_m: float,
                 min_distinct_spacing_m: float, pad_slope_max: float,
                 ) -> BaseProfile:
    """§1 (1)/(2) THE BASE PROFILE OF ONE MEMBER, in its AUTHORED frame —
    the ONE derivation site (§1 (4)).

    Every threshold is passed IN, from its own existing law key at the
    caller (``obj8.ResourceCache.base_profile``): this module holds no
    law number but the plane bin the spec names (:data:`_PLANE_BIN_M`).

    The read, in the spec's own order:

    1. HORIZONTAL FACES — the solid triangles with ``|n_y| >=
       horizontal_ny``.  Draped triangles never count (they carry no
       hardness and are not the object's body).
    2. PLANES — height clusters of those faces (:func:`_clusters`) with
       face area at or over ``min_area_m2``; below that the cluster is
       FURNITURE and is dropped.  Each plane's POLYGON is the plan union
       of its own faces.
    3. THE ROOF TEST — a plane with the unit's own solid vertices
       DISTRIBUTED under it (``contact_band_m`` or more below, strictly
       inside the polygon eroded by ``min_distinct_spacing_m``, convex
       hull covering ``roof_support_fraction`` of it) is a ROOF / DECK /
       MEZZANINE and is dropped.  Otherwise it is a BASE PLANE, and the
       cells within ``pad_frontage_m`` of those FEW lower vertices are
       TRIMMED off it to the lower plane.
    4. THE WELD — adjacent base planes (polygons within
       ``pad_frontage_m``) whose riser is under ``pad_terrace_floor_m``
       are ONE plane at the area-weighted height: a kerb is not a
       terrace.
    5. THE VERDICT — :data:`STEPPED` with two or more planes left,
       :data:`FLAT` with one (or with none but a contact set flat to
       ``pad_slope_max``), :data:`SLOPED` with none but a contact set
       spanning ``sloped_min_extent_m`` whose fit grades in
       ``(pad_slope_max, sloped_max]`` with rms at most ``split_tol_m``,
       :data:`FEET` otherwise.
    """
    v = geom.vertices
    tris = geom.solid
    if horizontal_ny <= 0.0 or tris.shape[0] == 0 or v.shape[0] == 0:
        return BaseProfile(FEET, why="no solid geometry" if tris.shape[0] == 0
                           else "base read disarmed (horizontal_ny 0)")
    # ── the FEET (§17 (B), unchanged): the member's ground-contact
    #    vertices — those within ``contact_band_m`` of its lowest.
    used = np.unique(tris.reshape(-1))
    vy = v[used][:, 1]
    low = float(vy.min())
    foot_sel = used[vy <= low + contact_band_m]
    feet = int(foot_sel.shape[0])
    foot_pts = v[foot_sel]

    horiz, areas, ymean = _horizontal(v, tris, horizontal_ny)
    planes_out: list[BasePlane] = []
    if horiz.any():
        hidx = np.flatnonzero(horiz)
        for y, area, sel in _clusters(ymean[hidx], areas[hidx], split_tol_m):
            if area < min_area_m2:
                continue                      # furniture, §1 (1)
            # §1 (1) NARROWED — REPORTED, NOT DECIDED.  A PLANE is LEVEL:
            # its own faces must fit one level height within
            # ``split_tol_m``.  §1 (1) defines a horizontal face by
            # ``|n_y| >= 0.95``, which admits a face tilted up to 18°, and
            # a 2 % slab 40 m long is such a face — so without this test
            # §1 (2)'s SLOPED branch ("no base plane >= 250 m2 but a
            # contact set ... whose plane fit has grade in
            # (pad_slope_max, sloped_max]") could never be reached by the
            # very geometry it describes: the slab would mint a level
            # plane at its mean and read FLAT.  ``split_tol_m`` is the
            # spec's own "is this one plane" tolerance (it bounds SLOPED's
            # rms in the same sentence), so no new number is introduced.
            # The spec author rules whether this is the intended reading.
            ctris = tris[hidx[sel]]
            cy = v[ctris.reshape(-1)][:, 1]
            if float(np.max(np.abs(cy - y))) > split_tol_m:
                continue                      # not LEVEL: sloped or riser
            poly = _plan_union(v, tris[hidx[sel]])
            if poly is None or poly.is_empty:
                continue
            planes_out.append(BasePlane(y, area, poly))
    # ── 3. the ROOF TEST, then the TRIM (§1 (1)) ────────────────────
    kept: list[BasePlane] = []
    for p in planes_out:
        p2 = _roof_test(v, used, p, contact_band_m, min_distinct_spacing_m,
                        pad_frontage_m, roof_support_fraction)
        if p2 is not None:
            kept.append(p2)
    kept.sort(key=lambda q: -q.area_m2)
    # ── 4. the WELD (§1 (1)) ────────────────────────────────────────
    kept = _weld_risers(kept, pad_terrace_floor_m, pad_frontage_m)
    risers = _risers(kept, pad_frontage_m)
    # ── 5. the VERDICT (§1 (2)) ─────────────────────────────────────
    if len(kept) >= 2:
        return BaseProfile(STEPPED, tuple(kept), tuple(risers), feet=feet,
                           feet_y=low,
                           why=f"{len(kept)} base planes after the weld")
    gx, gz, _y0, rms = _fit_plane(foot_pts)
    grade = math.hypot(gx, gz)
    if len(kept) == 1:
        return BaseProfile(FLAT, tuple(kept), (), feet=feet, feet_y=low,
                           residual_rms_m=rms, why="one base plane")
    # no base plane over the area floor: the contact set decides
    extent = 0.0
    if feet:
        extent = max(float(np.ptp(foot_pts[:, 0])), float(np.ptp(foot_pts[:, 2])))
    # §1 (2) THE FLAT-WITHOUT-A-PLANE BRANCH, NARROWED — REPORTED, NOT
    # DECIDED (base-profile spec §1 (2) against §5 A3 / §8a Q1).
    #
    # §1 (2) reads FLAT for "exactly one base plane, OR NONE but feet
    # whose plane fit over the contact set has grade <= pad_slope_max".
    # Taken literally that makes KASE site 1 FLAT: ``Shelters.OBJ``'s
    # 1,752 column feet are all at y -0.10 and fit at 0.000 % (§0 fact
    # 1).  But the SAME §1 (2) ends "FEET otherwise (a column-only
    # shelter: site 1)", §5 A3 requires "verdict FEET, one height", and
    # the owner's 10-01k Q1 calls it "a FEET-verdict (post-only) base"
    # and seats it by TILTING THE BODY.  Three statements say FEET
    # against one branch that would say FLAT, so the branch is narrower
    # than its wording: it needs a FLOOR, not merely level feet.
    #
    # THE DISCRIMINATOR USES NO NEW NUMBER.  The horizontal faces AT THE
    # CONTACT BAND must cover ``roof_support_fraction`` of the feet set's
    # own plan hull — the one fraction the law already states for "is
    # this geometry DISTRIBUTED over this polygon".  Measured on the
    # spec's two sites: site 1's column feet carry ~0 m2 of horizontal
    # face over an 11,362 m2 hull (0 %) -> FEET; a floor plate under the
    # 250 m2 area floor covers its own hull (~100 %) -> FLAT.
    #
    # THE SPEC AUTHOR RULES THIS (CLAUDE.md: a deviation is reported, not
    # decided).  Until then the narrowing is what makes site 1 read as
    # the owner ruled; ``floor_fraction`` is published on the profile so
    # the ruling can be read off a report instead of guessed.
    floor_frac = _floor_fraction(v, tris, horiz, areas, ymean, foot_pts,
                                 low, contact_band_m)
    if grade <= pad_slope_max and floor_frac >= roof_support_fraction > 0.0:
        return BaseProfile(FLAT, (), (), (gx, gz), rms, feet, low,
                           why=f"no base plane; contact fit {100.0 * grade:.2f} % "
                               f"within pad_slope_max over a floor "
                               f"({100.0 * floor_frac:.0f} % of the feet hull)",
                           floor_fraction=floor_frac)
    if (extent >= sloped_min_extent_m > 0.0 and pad_slope_max < grade <= sloped_max
            and rms <= split_tol_m):
        return BaseProfile(SLOPED, (), (), (gx, gz), rms, feet, low,
                           why=f"no base plane; contact fit {100.0 * grade:.2f} % "
                               f"over {extent:.1f} m, rms {rms:.3f} m",
                           floor_fraction=floor_frac)
    return BaseProfile(FEET, (), (), (gx, gz), rms, feet, low,
                       why=f"no base plane; contact fit {100.0 * grade:.2f} % "
                           f"over {extent:.1f} m, rms {rms:.3f} m, floor "
                           f"{100.0 * floor_frac:.0f} % of the feet hull",
                       floor_fraction=floor_frac)


def _grounded(v: np.ndarray, p: BasePlane, contact_band_m: float,
              near_m: float) -> bool:
    """§1 (3) as amended (RULINGS 2026-10-02aj (2)): whether any of the
    unit's ground-contact vertices ``v`` ``(n, 3)`` (x, y, z) stands AT
    the plane's level — ``|y - p.y| <= contact_band_m`` — on or within
    ``near_m`` of its polygon.  A plane with none is an upper storey."""
    import shapely
    if v.shape[0] == 0 or p.polygon is None or p.polygon.is_empty:
        return False
    at = v[np.abs(v[:, 1] - float(p.y)) <= float(contact_band_m)]
    if at.shape[0] == 0:
        return False
    reach = p.polygon.buffer(float(near_m)) if near_m > 0.0 else p.polygon
    return bool(np.any(shapely.contains_xy(reach, at[:, 0], at[:, 2])))


def _roof_test(v: np.ndarray, used: np.ndarray, p: BasePlane,
               contact_band_m: float, erode_m: float, frontage_m: float,
               roof_fraction: float) -> "BasePlane | None":
    """§1 (1) THE ROOF TEST and, where the plane survives it, THE TRIM.

    ``None`` for a ROOF / DECK / MEZZANINE: the unit's own solid vertices
    lying ``contact_band_m`` or more below the plane, strictly inside its
    polygon eroded by ``erode_m``, whose CONVEX HULL covers at least
    ``roof_fraction`` of the polygon — the shelter roof's 1,752 column
    feet (hull 156 %), a mezzanine over its floor, a deck over its piers.

    Otherwise the plane is a BASE and the cells within ``frontage_m`` of
    those FEW lower vertices are trimmed off it (KASE's garage threshold:
    157 vertices, hull 0.2 %, 31 m² of a 6,394 m² lot).  A trim that
    would consume the whole plane leaves it untrimmed and says so through
    :attr:`BasePlane.trimmed_m2` staying 0 — a plane that is ALL
    threshold is not a plane with a threshold."""
    from shapely.geometry import MultiPoint
    poly = p.polygon
    area = float(poly.area)
    if area <= 0.0:
        return None
    inner = poly.buffer(-erode_m, join_style=2, mitre_limit=2.0) if erode_m > 0.0 else poly
    if inner.is_empty:
        inner = poly
    below = v[used][v[used][:, 1] <= p.y - contact_band_m]
    if below.shape[0] == 0:
        return p
    pts = MultiPoint([(float(a), float(b)) for a, b in zip(below[:, 0], below[:, 2])])
    inside = pts.intersection(inner)
    if inside.is_empty:
        return p
    hull = inside.convex_hull
    frac = float(hull.area) / area
    if frac >= roof_fraction > 0.0:
        return None                            # a ROOF, never a base
    if frontage_m <= 0.0:
        return _dc.replace(p, support_fraction=frac)
    trim = inside.buffer(frontage_m, join_style=2, mitre_limit=2.0)
    left = poly.difference(trim)
    if left.is_empty or float(left.area) <= 0.0:
        return _dc.replace(p, support_fraction=frac)
    return _dc.replace(p, polygon=left, support_fraction=frac,
                       trimmed_m2=round(area - float(left.area), 3),
                       area_m2=p.area_m2 * float(left.area) / area)


def _adjacent(a: BasePlane, b: BasePlane, frontage_m: float) -> bool:
    """§1 (1): two planes are ADJACENT when their polygons are within
    ``[seam] pad_frontage_m`` of each other — the horizon §20 already
    reads a frontage over."""
    try:
        return bool(a.polygon.distance(b.polygon) <= frontage_m)
    except Exception:
        return False


def _weld_risers(planes: list[BasePlane], floor_m: float, frontage_m: float
                 ) -> list[BasePlane]:
    """§1 (1): a riser under ``[terrace] pad_terrace_floor_m`` WELDS — the
    two adjacent planes become ONE plane at the AREA-WEIGHTED height,
    with the union of their polygons.  A kerb is not a terrace.  Welding
    is transitive and is run to a fixed point, largest plane first, so a
    staircase of sub-floor steps collapses to one plane and not to a
    chain of pairs."""
    if floor_m <= 0.0 or len(planes) < 2:
        return list(planes)
    # §51 LAW B (``frame_entry.union``): the operands are PLACED pack
    # geometry once :func:`compose_profiles` has run, and GEOS's exact
    # overlay can refuse valid input (the TNCM "side location conflict").
    # A weld that threw here would abort the whole pack read, so this
    # union takes the fallback ladder like every other union of placed
    # geometry.  ``tests/auto_patch_v2/test_v2witnessvalid.py`` G2 holds
    # the census that names this function.
    from . import frame_entry as _fe
    cur = list(planes)
    changed = True
    while changed and len(cur) > 1:
        changed = False
        for i in range(len(cur)):
            for j in range(i + 1, len(cur)):
                a, b = cur[i], cur[j]
                if abs(a.y - b.y) >= floor_m or not _adjacent(a, b, frontage_m):
                    continue
                tot = a.area_m2 + b.area_m2
                y = ((a.y * a.area_m2 + b.y * b.area_m2) / tot if tot > 0.0
                     else 0.5 * (a.y + b.y))
                merged = BasePlane(
                    y, tot, _fe.union([a.polygon, b.polygon],
                                      "obj8_grade._weld_risers"),
                    max(a.support_fraction, b.support_fraction),
                    a.trimmed_m2 + b.trimmed_m2)
                cur = [q for k, q in enumerate(cur) if k not in (i, j)] + [merged]
                cur.sort(key=lambda q: -q.area_m2)
                changed = True
                break
            if changed:
                break
    return cur


def _risers(planes: list[BasePlane], frontage_m: float) -> list[Riser]:
    """§1 (1): the RISERS of the surviving planes — one per ADJACENT pair,
    the height difference signed from the lower index to the higher."""
    out: list[Riser] = []
    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            if _adjacent(planes[i], planes[j], frontage_m):
                out.append(Riser(i, j, round(float(planes[j].y - planes[i].y), 4)))
    return out


def _part_row(row) -> "tuple[BaseProfile, tuple[float, float, float], float | None]":
    """One ``parts`` row normalised to ``(profile, (dx, dy, dz), heading)``.

    Two spellings are accepted because the composition grew a HEADING.  A
    3-tuple carries the member's own ``heading_deg`` and is PLACED
    (:func:`_place`'s affine).  A 2-tuple carries NO heading and reads
    ``None`` — a pure translation, which is the DRY upper-bound roll-up
    (``obj8_split_report --base-profile``: no heading, no plan
    translation, the per-member bound §1 (3) names).

    ``None`` RATHER THAN 0.0 is the whole point: the placement affine at
    heading 0 is ``[1, 0, 0, −1, …]`` — authored ``z`` runs SOUTH — so
    a 0° member placed through the affine and a 0° member merely
    translated sit MIRRORED to one another.  Spelling "no heading" as 0.0
    would make two members of one unit disagree whenever one of them is
    authored due north."""
    if len(row) >= 3:
        prof, off, hdg = row[0], row[1], row[2]
        return (prof, (float(off[0]), float(off[1]), float(off[2])),
                None if hdg is None else float(hdg))
    prof, off = row[0], row[1]
    return (prof, (float(off[0]), float(off[1]), float(off[2])), None)


def _place_matrix(dx: float, dz: float, heading_deg: "float | None"
                  ) -> tuple[float, float, float, float, float, float]:
    """The ``[a, b, d, e, xoff, yoff]`` taking one member's AUTHORED
    ``(x, z)`` into the unit frame — ``obj8.placement_affine``'s matrix
    for a placed member, and a pure TRANSLATION for ``heading_deg`` None
    (the dry roll-up, :func:`_part_row`).  The matrix is BUILT here and
    APPLIED by ``airport/frame_entry.enter``, which §51 (2) makes the one
    site that puts a placement affine on a polygon."""
    if heading_deg is None:
        return (1.0, 0.0, 0.0, 1.0, dx, dz)
    h = math.radians(heading_deg)
    sn, cs = math.sin(h), math.cos(h)
    return (cs, -sn, -sn, -cs, dx, dz)


def _place_all(polys: "_t.Sequence", dx: float, dz: float,
               heading_deg: "float | None", q: float):
    """§1 (2)'s "orientation is carried by the polygons", through §51 (2)'s
    ONE ENTRY SITE: one member's base-plane polygons placed into the unit
    frame by ``frame_entry.enter`` — the affine, the 1 mm snap and the
    repair, in ONE vectorised call for the member.

    IT MUST BE ``enter`` AND NOT A BARE AFFINE.  Rotating a face-union
    polygon is exactly the defect §51 names: the rotation rounds micron
    slivers into self-touching rings, and an invalid ring refuses the
    first union that reads it — which here is :func:`_weld_risers`, one
    step later.  ``tests/auto_patch_v2/test_v2witnessvalid.py`` G1 holds
    the allow-list empty, and this lane was caught by it.

    A polygon that repairs to NOTHING comes back ``None``; the caller
    drops that plane and names the drop (never a silent plane)."""
    from . import frame_entry as _fe
    return list(_fe.enter(list(polys), _place_matrix(dx, dz, heading_deg), q))


def compose_profiles(parts: "_t.Sequence[tuple]",
                     *, seat_xz: "tuple[float, float] | None" = None,
                     pad_terrace_floor_m: float, pad_frontage_m: float,
                     roof_support_fraction: float = 0.0,
                     lower_pts: "_t.Any" = None,
                     contact_band_m: float = 0.0,
                     min_distinct_spacing_m: float = 0.0,
                     input_quantum_m: float = 0.0) -> BaseProfile:
    """§1 (3) THE UNIT PROFILE — the members of ONE §16g unit composed into
    one frame.

    ``parts`` is ``(the member's profile, its offset (dx, dy, dz) into the
    unit frame, its heading in degrees)`` — the 2-tuple without the
    heading is still accepted and reads heading 0 (:func:`_part_row`).
    Nothing is FITTED here: the plan carries each member's placement
    origin (``Member.origin``) and its ``heading_deg``, and the §16c
    contact graph's welded part pairs give the relative offset exactly
    (``cluster_pads[].pad_offset_spread`` publishes it — 13.3 m at KASE's
    ``unit:108``).

    THE OFFSET IS A PLAN TRANSLATION ONLY.  ``dy`` is 0 for the members
    of ONE §16g unit: a unit carries ONE ``agl_m``, so every member's
    placement puts its authored ``y = 0`` at the SAME elevation and the
    authored heights are already in one vertical frame (it is exactly why
    ``PlanCluster.floors`` compares members' ``base_y`` directly, §16g
    (10) (1)).  ``dy`` is kept in the signature for the DRY roll-up, which
    has no origins and uses each member's authored floor as a stand-in
    upper bound.

    THE ORIGIN PLANE ``p0`` is the base plane whose polygon contains the
    unit's seat point ``seat_xz`` (the §16g datum sample centre), else the
    LARGEST base plane; it is returned FIRST and
    :attr:`BaseProfile.offsets` is read against it.

    WHY THE COMPOSITION MATTERS AND IS NOT COSMETIC (§0 fact 10, the
    HECA T3 risk the spec pre-registers): a member's own read cannot see
    supports that live in a SIBLING member, so a hall's upper floor reads
    STEPPED per member and must read ROOF once composed.  Pass the
    unit's composed lower solid vertices as ``lower_pts`` ``(n, 3)`` and
    the roof test is RE-RUN here against them; omit it and the members'
    own verdicts stand (the per-member UPPER BOUND, which is what a
    dry report reads).

    A unit with no base plane keeps today's law exactly: the composed
    verdict is the single member's where there is one, else FEET.
    """
    rows = [_part_row(r) for r in parts]
    moved: list[BasePlane] = []
    feet = 0
    low = None
    dropped = 0
    sloped: list[tuple[BaseProfile, tuple[float, float, float]]] = []
    for prof, (dx, dy, dz), hdg in rows:
        feet += int(prof.feet)
        fy = float(prof.feet_y) + float(dy)
        low = fy if low is None else min(low, fy)
        if prof.verdict == SLOPED:
            sloped.append((prof, (dx, dy, dz)))
        if not prof.planes:
            continue
        placed = _place_all([p.polygon for p in prof.planes],
                            float(dx), float(dz), hdg, float(input_quantum_m))
        for p, poly in zip(prof.planes, placed):
            if poly is None or poly.is_empty:
                dropped += 1          # repaired to nothing: NAMED, never silent
                continue
            moved.append(BasePlane(
                float(p.y) + float(dy), p.area_m2, poly,
                p.support_fraction, p.trimmed_m2))
    if not moved:
        # no member carried a base plane: the unit keeps today's law.  A
        # single SLOPED member's gradient is the unit's (its frame is the
        # unit's, the offsets being translations only).
        if len(sloped) == 1 and len(parts) >= 1:
            prof = sloped[0][0]
            return _dc.replace(prof, feet=feet, feet_y=float(low or 0.0),
                               why=prof.why + " (composed: one sloped member)")
        if len(parts) == 1:
            prof = parts[0][0]
            return _dc.replace(prof, feet=feet, feet_y=float(low or 0.0))
        return BaseProfile(FEET, feet=feet, feet_y=float(low or 0.0),
                           why=f"{len(parts)} member(s), no base plane")
    # §1 (3): the roof test RE-RUN on the composed unit, where the caller
    # gave us the unit's own lower geometry (the HECA T3 case)
    if lower_pts is not None and roof_support_fraction > 0.0:
        used = np.arange(int(np.asarray(lower_pts).shape[0]))
        pts = np.asarray(lower_pts, dtype=float)
        moved = [q for q in
                 (_roof_test(pts, used, p, contact_band_m,
                             min_distinct_spacing_m, pad_frontage_m,
                             roof_support_fraction) for p in moved)
                 if q is not None]
        # A BASE PLANE STANDS ON THE GROUND (owner RULINGS 2026-10-02aj
        # (2), "seat T3 as one level"; master decision (1) to lane
        # ``t3onelevel10``): a composed plane is a BASE only where the
        # unit's own GROUND-CONTACT vertices (``lower_pts`` — every part
        # foot of the group) stand at its level, within ``contact_band_m``
        # of its height and ``pad_frontage_m`` of its polygon.  A plane
        # with no foot at its level is an UPPER STOREY (a ceiling, a floor
        # slab, a roof net) whatever the roof test's hull read, and never
        # a riser.  MEASURED at HECA T3 (cluster ``unit:43#6330``): the
        # +0.06 m ground floor carries 5,848 feet at its level, each of
        # the 32 planes at +3.65 .. +27.95 m carries 0 — the roof test
        # passed them because the feet under a hall floor lie at its walls,
        # outside the eroded polygon (``support_fraction`` 0.00).
        moved = [q for q in moved
                 if _grounded(pts, q, contact_band_m, pad_frontage_m)]
    moved.sort(key=lambda q: -q.area_m2)
    moved = _weld_risers(moved, pad_terrace_floor_m, pad_frontage_m)
    if not moved:
        return BaseProfile(FEET, feet=feet, feet_y=float(low or 0.0),
                           why="every composed plane read as a roof")
    moved = _origin_first(moved, seat_xz)
    verdict = STEPPED if len(moved) >= 2 else FLAT
    return BaseProfile(verdict, tuple(moved), tuple(_risers(moved, pad_frontage_m)),
                       feet=feet, feet_y=float(low or 0.0),
                       why=f"composed from {len(parts)} member(s): "
                           f"{len(moved)} base plane(s)"
                           + (f" ({dropped} repaired to nothing at entry)"
                              if dropped else ""))


def _origin_first(planes: list[BasePlane],
                  seat_xz: "tuple[float, float] | None") -> list[BasePlane]:
    """§1 (3): the ORIGIN PLANE ``p0`` first — the plane whose polygon
    CONTAINS the unit's seat point, else the largest (``planes`` arrives
    sorted by area, so the fallback is already in place)."""
    if seat_xz is None or not planes:
        return planes
    from shapely.geometry import Point
    pt = Point(float(seat_xz[0]), float(seat_xz[1]))
    for i, p in enumerate(planes):
        try:
            hit = bool(p.polygon.covers(pt))
        except Exception:
            hit = False
        if hit:
            return [planes[i]] + [q for k, q in enumerate(planes) if k != i]
    return planes


def _floor_fraction(v: np.ndarray, tris: np.ndarray, horiz: np.ndarray,
                    areas: np.ndarray, ymean: np.ndarray, foot_pts: np.ndarray,
                    low: float, contact_band_m: float) -> float:
    """§1 (2) narrowed (see :func:`base_profile`): the share of the FEET
    set's plan convex hull covered by HORIZONTAL FACE AREA at the contact
    band — "does this contact set have a FLOOR, or only feet?".

    0.0 where there are fewer than three feet (no hull to cover)."""
    if foot_pts.shape[0] < 3:
        return 0.0
    from shapely.geometry import MultiPoint
    hull = MultiPoint([(float(a), float(b))
                       for a, b in zip(foot_pts[:, 0], foot_pts[:, 2])]).convex_hull
    ha = float(getattr(hull, "area", 0.0))
    if ha <= 0.0:
        return 0.0
    at_feet = horiz & (ymean <= low + contact_band_m)
    if not at_feet.any():
        return 0.0
    return float(areas[at_feet].sum()) / ha


# --------------------------------------------------------------------------
# §1 (4) THE PUBLICATION CODEC — ONE SPELLING FOR THREE READERS
# --------------------------------------------------------------------------
#: §1 (4): the profile is published on the plan (``Member.base_profile``),
#: composed per unit onto ``PlanCluster.base_profile``, and read back by
#: ``tools/obj8_split_report --base-profile``.  THREE readers of one law,
#: so there is ONE codec here rather than a dict literal at each site: the
#: census-wrapper defect (RULINGS 2026-08-30l) is exactly two hand-rolled
#: spellings of one record drifting apart, and §6's STOP list names "any
#: ``--base-profile`` read that disagrees with the planar stage's
#: published planes (two readers of one law)".
#:
#: The polygon travels through shapely's own ``mapping`` / ``shape`` — a
#: hand-walked ring list would lose a MultiPolygon, and §1 (1)'s polygon
#: is the face UNION, which at KASE's ``FireStation_7`` lot is TWO pieces
#: (§4: "the lot's face union is 6,394 m² in two pieces").


def profile_to_json(prof: "BaseProfile") -> dict:
    """``BaseProfile`` -> a JSON-safe dict (§1 (4)).

    Geometry is in the member's AUTHORED frame ``(x, z)``, as §1 (1)
    derives it; the placement affine and the DSF heading are applied by
    the reader that needs ground coordinates (§1 (2): "orientation is
    carried by the polygons").
    """
    from shapely.geometry import mapping
    return {
        "verdict": str(prof.verdict),
        "planes": [{"y": float(p.y), "area_m2": float(p.area_m2),
                    "polygon": (mapping(p.polygon)
                                if p.polygon is not None and not p.polygon.is_empty
                                else None),
                    "support_fraction": float(p.support_fraction),
                    "trimmed_m2": float(p.trimmed_m2)}
                   for p in prof.planes],
        "risers": [[int(r.a), int(r.b), float(r.dy)] for r in prof.risers],
        "slope": [float(prof.slope[0]), float(prof.slope[1])],
        "residual_rms_m": float(prof.residual_rms_m),
        "feet": int(prof.feet),
        "feet_y": float(prof.feet_y),
        "floor_fraction": float(prof.floor_fraction),
        "why": str(prof.why),
    }


def profile_from_json(d: "dict | None") -> "BaseProfile":
    """The inverse (§1 (4)).  ``None`` / ``{}`` — a plan written before the
    base read — is the pre-law profile exactly: ``FEET`` with no plane, so
    "a unit with no base plane keeps today's law exactly" (§1 (3)).
    """
    from shapely.geometry import shape
    if not d:
        return BaseProfile(FEET, why="plan predates the base read")
    planes = []
    for p in d.get("planes", ()) or ():
        geo = p.get("polygon")
        planes.append(BasePlane(
            y=float(p.get("y", 0.0)), area_m2=float(p.get("area_m2", 0.0)),
            polygon=(shape(geo) if geo else None),
            support_fraction=float(p.get("support_fraction", 0.0) or 0.0),
            trimmed_m2=float(p.get("trimmed_m2", 0.0) or 0.0)))
    sl = d.get("slope", (0.0, 0.0)) or (0.0, 0.0)
    return BaseProfile(
        verdict=str(d.get("verdict", FEET)),
        planes=tuple(planes),
        risers=tuple(Riser(int(a), int(b), float(dy))
                     for a, b, dy in (d.get("risers", ()) or ())),
        slope=(float(sl[0]), float(sl[1])),
        residual_rms_m=float(d.get("residual_rms_m", 0.0) or 0.0),
        feet=int(d.get("feet", 0) or 0),
        feet_y=float(d.get("feet_y", 0.0) or 0.0),
        floor_fraction=float(d.get("floor_fraction", 0.0) or 0.0),
        why=str(d.get("why", "")))
