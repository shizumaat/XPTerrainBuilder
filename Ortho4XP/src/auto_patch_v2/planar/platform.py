"""THE UNIT PLATFORM'S INNER RING AND COLLAR (unit-platform spec §1 (2)-(4);
owner RULINGS 2026-09-28a (1); issues #66 / #4 / #10).

A pad FACE is rim-only, and under 23a most of a terminal's rim is the apron
itself (welded, airside moved 0): "one platform" and "airside unmoved"
cannot both hold ON THE RIM.  The third road is a region INSIDE the
footprint.  Here, at the one site the pad polygon is final (after
``pad_cut.apron_cut_to_pads`` and ``pad_terrace.pad_terrace_split``,
before pass B nodes the pads), every pad that FRONTS AIRSIDE and is a unit
pad (area >= ``[placement] cluster_pad_min_m2``, the §30 (4) cluster-pad
bar) is split into TWO regions of its own role:

* the PLATFORM — the pad polygon ERODED by the collar width C, keeping the
  pad's own ref.  Its face is priced as the pad's plate (one plane, 1 %),
  and its level is §20's frontage fit (``constraints.pads``).
* the COLLAR — the annulus between the pad rim and the platform, ref
  ``<ref>#collar`` (``model.planar.COLLAR_SUFFIX``; every consumer that
  joins a pad on ``ref.split("#")[0]`` reads it as the same pad).  A
  ``building`` face with a HOLE, graded as a §31 (7) bank from the welded
  rim to the platform (``constraints.platform``).

C IS MEASURED PER PLATFORM (spec §1 (2); spec-author correction on #66,
2026-09-28): ``C = clamp(relief / bank_slope, bank_min_width_m,
platform_collar_max_m)`` where ``relief`` is the WELDED rim's largest
distance from the platform plane (:func:`rim_relief_m`).  The spec reads it
off stage 1; stage 1 runs after this arrangement, so the mint reads the
one level there is here, the DEM along the welded rim, against the same
tilt-bounded frontage plane — and the SOLVED relief is re-read after the
solve and published per platform (``platform_rim_relief``, with the collar
it would need), so a mint that under-read shows there, never silently.

THE SECOND PASS (issue #86; spec-author decision 2026-09-29, lane
``collar86``): the DEM along the welded rim is a PROXY for the solved rim —
measured, HECA T3 ``building4`` minted C 10.43 m where the solved relief
needed 11.2 m, SPJC ``building5`` 5.99 m vs 14.0 m.  So after the stage-1
arrangement solves, the caller re-derives C per platform from the SOLVED
relief (``constraints.platform.solved_collar_widths``, reading the same
``platform_records`` row the census publishes) and re-mints the collar
ONCE through :data:`SOLVED_C` — attempt cap 1, no iteration.  Over-
provisioning at the mint is NOT the fix.

The erosion never touches the rim: no airside vertex is created or moved
(the inner ring is at least C inside the pad, minted after the 23a cut).
A pad whose erosion leaves no inner ring of ``cluster_pad_min_m2`` is
REFUSED (no platform, today's welded plate) and published in
:data:`PLATFORMS` with the reason."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import rolled_on_roles
from ..model.planar import COLLAR_SUFFIX

__all__ = ["platform_split", "Platform", "PLATFORMS", "collar_width_m",
           "SOLVED_C"]

#: The ring sampling step of the frontage read (m) — ``pad_terrace._STEP_M``'s
#: geometric resolution, not a law value.
_STEP_M = 2.0
#: A pad needs at least this many welded ring samples to FRONT airside (a
#: plane has three degrees of freedom; a corner touch fronts nothing).
_MIN_WELDED = 3


@_dc.dataclass(frozen=True)
class Platform:
    """One unit pad's platform verdict at the arrangement."""

    ref: str
    collar_m: float
    pad_m2: float
    platform_m2: float
    welded_samples: int
    #: the welded rim's relief at the mint (DEM, against the tilt-bounded
    #: frontage plane) that set C; ``None`` without a DEM
    relief_m: "float | None" = None
    #: ``""`` when minted, else why not (``"eroded_away"``,
    #: ``"under_min_area"``)
    refused: str = ""
    #: where C was read: ``"dem"`` (the first mint's proxy) or ``"solved"``
    #: (the second pass, :data:`SOLVED_C`, issue #86)
    c_source: str = "dem"
    #: the C the first (DEM) mint chose, kept on a solved re-mint
    dem_collar_m: "float | None" = None

    def to_dict(self) -> dict[str, _t.Any]:
        return _dc.asdict(self)


#: The last arrangement's platform verdicts (the ``pad_terrace.TERRACES``
#: pattern: read back by the publication and the census).
PLATFORMS: list[Platform] = []

#: THE SECOND PASS'S WIDTHS (issue #86): ``{pad ref: C}`` read from the
#: SOLVED rim relief of the first pass.  Set by the caller between its two
#: passes and CLEARED by it after the second (the one re-mint); empty, the
#: split reads the DEM proxy as it always has.
SOLVED_C: dict[str, float] = {}


def collar_width_m(law: Law) -> float:
    """C (module docstring): the §31 (7) bank floor
    ``emit.design.bank_min_width_m`` — ONE derivation."""
    return float(law.tables.emit.design.bank_min_width_m)


def _parts(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [q for q in getattr(g, "geoms", []) if isinstance(q, Polygon) and not q.is_empty]


def _welded_samples(poly: Polygon, air, near_m: float) -> int:
    ring = poly.exterior
    n = max(4, int(ring.length // _STEP_M))
    k = 0
    for i in range(n):
        p = ring.interpolate(i * ring.length / n)
        if air.distance(p) <= near_m:
            k += 1
    return k


def rim_relief_m(P: Polygon, air, near_m: float, dem, slope_max: float
                 ) -> "float | None":
    """The WELDED rim's relief against the platform plane, read at the mint
    (spec §1 (2); spec-author correction on #66: C is the MEASURED value
    per platform).  The welded rim is every ring sample of ``P`` within
    ``near_m`` of the airside; its level there is the DEM (stage 1 has not
    run at the arrangement — the one level there is; the SOLVED relief is
    re-read after the solve and published as ``platform_rim_relief``).
    The platform plane is §20's least-squares fit of that same frontage,
    its tilt bounded at ``pad_slope_max`` (a steeper fit keeps its direction
    at the ceiling and re-centres, ``project_strip._pad_plane``'s rule).
    ``None`` without a DEM or three samples."""
    import numpy as np
    if dem is None:
        return None
    ring = P.exterior
    n = max(4, int(ring.length // _STEP_M))
    pts = []
    for i in range(n):
        q = ring.interpolate(i * ring.length / n)
        if air.distance(q) <= near_m:
            try:
                z = float(dem.z(q.x, q.y))
            except Exception:  # noqa: BLE001 — off the raster: no witness
                continue
            if z == z:
                pts.append((q.x, q.y, z))
    if len(pts) < 3:
        return None
    A = np.asarray(pts, dtype=float)
    x0, y0 = A[:, 0].mean(), A[:, 1].mean()
    M = np.c_[np.ones(len(A)), A[:, 0] - x0, A[:, 1] - y0]
    if np.linalg.matrix_rank(M) < 3:
        return float(np.max(np.abs(A[:, 2] - np.median(A[:, 2]))))
    c, *_ = np.linalg.lstsq(M, A[:, 2], rcond=None)
    g = float(np.hypot(c[1], c[2]))
    if g > slope_max > 0.0:
        c[1], c[2] = c[1] * slope_max / g, c[2] * slope_max / g
        c[0] = float(np.mean(A[:, 2] - c[1] * (A[:, 0] - x0) - c[2] * (A[:, 1] - y0)))
    return float(np.max(np.abs(A[:, 2] - M @ c)))


def platform_split(base_regions, pad_regions, law: Law,
                   grid: float = 0.0, dem=None) -> tuple[list, dict]:
    """THE SPLIT (module docstring).  Returns ``(pad_regions, counts)``;
    a no-op with ``[building_pad] platform_collar`` off."""
    PLATFORMS.clear()
    counts: dict[str, _t.Any] = {"platforms": 0, "platforms_refused": 0}
    bp = law.tables.structures.building_pad
    if not bool(getattr(bp, "platform_collar", False)) or not pad_regions:
        return list(pad_regions), counts
    from ..law.tables import design as design_law
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    near = float(design_law(law).pad_frontage_m)
    C0 = collar_width_m(law)
    bank = float(law.tables.emit.design.bank_slope)
    cmax = float(bp.platform_collar_max_m)
    slope_max = float(law.tables.emit.within_shape.pad_slope_max)
    if min_m2 <= 0.0 or C0 <= 0.0 or bank <= 0.0:
        return list(pad_regions), counts
    air_roles = rolled_on_roles(law)
    air_polys = [r.polygon for r in base_regions
                 if r.source == "cell" and r.role in air_roles
                 and r.polygon is not None and not r.polygon.is_empty]
    if not air_polys:
        return list(pad_regions), counts
    tree = STRtree(air_polys)
    out: list = []
    plat_ids: set[int] = set()
    for pr in pad_regions:
        P = pr.polygon
        if (P is None or P.is_empty or not isinstance(P, Polygon)
                or P.area < min_m2 or str(pr.ref).endswith(COLLAR_SUFFIX)):
            out.append(pr)
            continue
        cand = [air_polys[int(j)] for j in
                tree.query(P, predicate="dwithin", distance=near)]
        if not cand:
            out.append(pr)                   # fronts no airside: its DEM datum
            continue
        air = unary_union(cand)
        nw = _welded_samples(P, air, near)
        if nw < _MIN_WELDED:
            out.append(pr)
            continue
        # C PER PLATFORM (spec-author correction on #66): the §31 (7) bank
        # the welded rim's relief needs, clamped to [bank_min_width_m,
        # platform_collar_max_m]
        rel = rim_relief_m(P, air, near, dem, slope_max)
        C = C0 if rel is None else min(cmax, max(C0, rel / bank))
        c_dem = round(C, 2)
        src_c = "dem"
        if str(pr.ref) in SOLVED_C:
            # issue #86: the SOLVED relief's C, the same clamp
            C = min(cmax, max(C0, float(SOLVED_C[str(pr.ref)])))
            src_c = "solved"
        inner = P.buffer(-C, join_style=2, mitre_limit=2.0)
        parts = sorted(_parts(inner), key=lambda q: -q.area)
        if not parts:
            PLATFORMS.append(Platform(str(pr.ref), round(C, 2), round(P.area, 1), 0.0,
                                      nw, rel, "eroded_away", src_c, c_dem))
            out.append(pr)
            continue
        # EVERY piece the erosion leaves is platform (a district pad is
        # several halls joined by narrow links, and the links are what the
        # collar eats — HECA T3 ``building4``: its largest piece alone is a
        # third of the pad).  The pieces keep the pad's ref, so the plate
        # prices them as ONE plane (``cluster_pad.plane_groups``).  A piece
        # under ``[building_pad] min_area_m2`` (the smallest pad the mint
        # keeps) stays in the collar, which is where its ground is.
        pmin = float(bp.min_area_m2)
        plats = []
        for q in parts:
            if grid > 0.0:
                # the ring is noded on the arrangement's grid anyway; a
                # mitred erosion carries no vertex worth half a cell
                s_ = q.simplify(0.5 * grid, preserve_topology=True)
                q = s_ if isinstance(s_, Polygon) and not s_.is_empty else q
            if q.area >= pmin:
                plats.append(q)
        tot = sum(q.area for q in plats)
        if tot < min_m2:
            PLATFORMS.append(Platform(str(pr.ref), round(C, 2), round(P.area, 1),
                                      round(tot, 1), nw, rel, "under_min_area",
                                      src_c, c_dem))
            out.append(pr)
            continue
        cparts = _parts(P.difference(unary_union(plats)))
        if not cparts:
            out.append(pr)
            continue
        PLATFORMS.append(Platform(str(pr.ref), round(C, 2), round(P.area, 1),
                                  round(tot, 1), nw, rel, "", src_c, c_dem))
        pieces = [_dc.replace(pr, polygon=q) for q in plats]
        plat_ids.update(id(q) for q in pieces)
        out.extend(pieces)
        # the collar: the annulus around every platform piece (a polygon
        # with the pieces as its holes); an erosion that split off small
        # islands leaves them in it, which is where their ground is
        out.extend(_dc.replace(pr, ref=str(pr.ref) + COLLAR_SUFFIX, polygon=q)
                   for q in cparts)
    # ONE REF, ONE PAD: a pad the 23a cut / the 28b terrace left in several
    # regions carries its ref on each, and a piece left whole above would
    # read as a PLATFORM face by its ref — MEASURED at HECA T3 ``building4``:
    # eleven 0.1-2 m2 rim slivers between the pad and ``pav1`` came out as
    # "platform" faces holding apron vertices, and the plane dragged the
    # apron with them.  Every other region of a platform ref is COLLAR.
    minted = {p.ref for p in PLATFORMS if not p.refused}
    if minted:
        out = [r if (str(r.ref) not in minted or id(r) in plat_ids)
               else _dc.replace(r, ref=str(r.ref) + COLLAR_SUFFIX) for r in out]
    counts["platforms"] = sum(1 for p in PLATFORMS if not p.refused)
    counts["platforms_refused"] = sum(1 for p in PLATFORMS if p.refused)
    counts["platform_list"] = "; ".join(
        f"{p.ref} C {p.collar_m:g} m"
        + (f" (solved; DEM {p.dem_collar_m:g})" if p.c_source == "solved" else "")
        + f" {p.platform_m2:,.0f}/{p.pad_m2:,.0f} m2"
        + (f" REFUSED {p.refused}" if p.refused else "") for p in PLATFORMS[:12])
    return out, counts
