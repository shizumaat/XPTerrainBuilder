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

C IS THE WIDEST WIDTH THE PAD CAN CARRY (owner RULINGS 2026-10-02v (5)
as amended by 2026-10-02z, issue #86): the collar is minted at
``platform_collar_max_m``, the widest the law allows, and the SOLVE places
the toe inside it (``constraints.platform``: the collar's rows are one-way
INEQUALITIES at the 1:3 bank, never a fixed-toe equality).  Where the cap
would erode the pad past the platform's own gates it is NARROWED to the
widest width that still leaves a platform — never below the width the
pre-collar86 engine already minted, and so never below
``bank_min_width_m`` (:func:`_collar_for_pad` — ONE pass, bisection on
§46 (4)'s coordinate lattice, no re-mint and no second solve).  THE
PLATFORM SET IS UNCHANGED BY CONSTRUCTION: the refusal is judged at that
status-quo width, so round 2 alters a collar's WIDTH and nothing else.  Round 1 minted the cap
UNCONDITIONALLY and 10-02z MEASURED what that costs: live platforms KCLT
10 -> 3, SPJC 8 -> 5, HECA 14 -> 8, the plateaus lost with them and KCLT
18L/36R runway flex at 98 % of budget.  Where the platform survived the
bank goal WAS met (HECA ``building4`` 1:3.27 -> 1:4.61, SPJC ``building5``
1:1.89 -> 1:4.41) — so round 2 keeps the one-way rows and widens the
collar only as far as the pad allows.  The DEM proxy both replace — ``C = clamp(relief / bank_slope,
bank_min_width_m, platform_collar_max_m)`` read off the DEM along the
welded rim (:func:`rim_relief_m`) — under-read the SOLVED relief at HECA
T3 ``building4`` (C 10.43 m, 11.2 m needed) and SPJC ``building5`` (C
5.99 m, 14.0 m needed), and the two-pass re-mint that would close it is
REFUSED (RULINGS 2026-09-29l: it does not converge — widening the collar
moves the platform's plane, so the needed C grows again, 5.99 -> 13.99 ->
17.88 m — and it doubles the solve, 08k (4) ONE pass).  The mint still
READS the DEM relief and records it per platform (``Platform.rim_relief``),
and the SOLVED relief is re-read after the solve and published
(``platform_rim_relief``, with the collar it would need), so a collar too
narrow for the relief shows there, never silently.  Each platform also
records WHY its C is what it is (``Platform.collar_why``: ``"cap"`` /
``"area"`` / ``"floor"``), so an area-limited collar is read off the
report, never inferred.

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
from ..law.tables import frontage_roles
from ..model.planar import COLLAR_SUFFIX, block_ref
from ..model.platform import HELD, PLATFORMS, Platform

__all__ = ["platform_split", "Platform", "PLATFORMS", "collar_width_m",
           "merge_platform_faces"]

#: The ring sampling step of the frontage read (m) — ``pad_terrace._STEP_M``'s
#: geometric resolution, not a law value.
_STEP_M = 2.0
#: A pad needs at least this many welded ring samples to FRONT airside (a
#: plane has three degrees of freedom; a corner touch fronts nothing).
_MIN_WELDED = 3
#: A DRAPED FACADE'S FOOTPRINT TAKES NO COLLAR (issue #223, owner read
#: 2026-10-02: SPJC ``building14`` = ``dsf:fac170``, the facade FLOATING at
#: −12.0257776, −77.1063868).  The collar is a terrace INSIDE the footprint
#: whose premise is unit-platform spec §1 (3)/(5): the object stage seats
#: the unit on the platform plane, so the bank under the walls is invisible.
#: A ``.fac`` building is not a pack object: the SIM drapes it, at ONE floor
#: over the terrain under its footprint, and no stage of ours seats it — so
#: every metre of collar relief under it is the facade's own float (sw1010:
#: platform 24.63 m, collar rim to 31.56 m, the apron it fronts 24.23 m).
#: Such a pad keeps the plate the pre-collar engine gave it, which flat-pad
#: spec v2 §4 HOLDS flat at its frontage datum (``conforming``), and the
#: patch-boundary bank (``emit/bank``) carries the relief OUTSIDE the
#: footprint.  The footprint is the facade's when a ``dsf:fac:*`` building
#: covers at least this fraction of the pad's area (the 23a cut trims a pad
#: at its airside edge; a pad a facade merely touches is not its footprint).
DRAPED_FACADE_COVER = 0.5
#: The ``Platform.refused`` reason of such a pad.
REFUSED_DRAPED_FACADE = "draped_facade"


def draped_facade_pads(pad_regions, airport) -> "set[int]":
    """``id(region)`` of every pad region whose polygon is a draped
    facade's footprint (:data:`DRAPED_FACADE_COVER`): the ``airport``'s
    ``dsf:fac:*`` buildings (``model.airport.Building.source``), in the
    arrangement's own frame.  ONE derivation, read by the mint and its
    twin.  Empty without an airport."""
    out: set[int] = set()
    bs = [b for b in getattr(airport, "buildings", ()) or ()
          if str(getattr(b, "source", "")).startswith("dsf:fac")]
    if not bs:
        return out
    polys = []
    for b in bs:
        try:
            q = Polygon(b.outer, [list(h) for h in (b.holes or ())])
        except Exception:
            continue
        if q.is_valid and not q.is_empty:
            polys.append(q)
    if not polys:
        return out
    tree = STRtree(polys)
    for r in pad_regions:
        P = r.polygon
        if P is None or P.is_empty or P.area <= 0.0:
            continue
        cov = 0.0
        for j in tree.query(P, predicate="intersects"):
            cov = max(cov, P.intersection(polys[int(j)]).area)
        if cov >= DRAPED_FACADE_COVER * P.area:
            out.add(id(r))
    return out


# ``Platform`` / ``PLATFORMS`` live in ``model/platform`` (issue #104:
# ``constraints/platform`` reads them and may not import ``planar``);
# re-exported.


def collar_width_m(law: Law) -> float:
    """C's CEILING (module docstring): the CAP, ``structures.building_pad
    platform_collar_max_m`` (owner RULINGS 2026-10-02v (5)) — the width
    every platform takes where its pad can carry it, and the top of
    :func:`_collar_for_pad`'s search.  ONE derivation, read by the mint
    and by its twins."""
    return float(law.tables.structures.building_pad.platform_collar_max_m)


def _eroded(P: Polygon, C: float, grid: float, pmin: float
            ) -> "tuple[list[Polygon], list[Polygon], float]":
    """``(parts, platform pieces, their total area)`` of ``P`` eroded by
    ``C`` — the erosion and the two gates ``platform_split`` has always
    run, at ONE width, lifted out so the width search and the mint read
    the SAME predicate (no second implementation to drift).

    EVERY piece the erosion leaves is platform (a district pad is several
    halls joined by narrow links, and the links are what the collar eats —
    HECA T3 ``building4``: its largest piece alone is a third of the pad).
    The pieces keep the pad's ref, so the plate prices them as ONE plane
    (``cluster_pad.plane_groups``).  A piece under ``[building_pad]
    min_area_m2`` (the smallest pad the mint keeps) stays in the collar,
    which is where its ground is."""
    inner = P.buffer(-C, join_style=2, mitre_limit=2.0)
    parts = sorted(_parts(inner), key=lambda q: -q.area)
    plats = []
    for q in parts:
        if grid > 0.0:
            # the ring is noded on the arrangement's grid anyway; a
            # mitred erosion carries no vertex worth half a cell
            s_ = q.simplify(0.5 * grid, preserve_topology=True)
            q = s_ if isinstance(s_, Polygon) and not s_.is_empty else q
        if q.area >= pmin:
            plats.append(q)
    return parts, plats, sum(q.area for q in plats)


def _collar_for_pad(P: Polygon, grid: float, cap: float, cmin: float,
                    bank: float, rel: "float | None", step: float,
                    pmin: float, min_m2: float
                    ) -> "tuple[float, str, list[Polygon], list[Polygon], float]":
    """THE ONE DERIVATION OF C (module docstring; owner RULINGS 2026-10-02z
    re-land of #86): the WIDEST width at or under ``cap`` whose erosion
    still leaves this pad a platform — ``_eroded`` leaves a part AND the
    platform pieces total at least ``min_m2``.  ONE pass: no re-mint, no
    second solve, and the toe stays solve-placed by
    ``constraints.platform``'s one-way rows.

    THE SEARCH FLOOR IS THE STATUS QUO, not ``cmin``.  ``origin/main``
    (pre-collar86) minted ``C_main = clamp(relief / bank_slope,
    bank_min_width_m, platform_collar_max_m)`` and REFUSED the pad when
    that erosion left no platform; round 2 starts there and only widens.
    So the set of pads that get a platform is main's set EXACTLY — round 2
    changes a collar's WIDTH and nothing else, which is the whole of what
    10-02z asks for and the only delta a sweep then has to attribute.  A
    floor at ``cmin`` instead would also MINT platforms main refuses (a
    pad whose relief-width erosion crossed the min-area bar while a 5 m one
    does not): MEASURED on
    ``test_round_2_never_refuses_a_platform_main_grants``'s 50-pad sweep,
    2 of 50.  That is a strict gain in 10-02z's own direction, but it is a
    CHANGE TO THE PLATFORM SET and so the owner's to rule, not this lane's
    — REPORTED, not taken.  ``cmin`` remains the absolute floor: the
    status-quo width is never under it.

    MONOTONE, so the search is a bisection and not a scan: eroding further
    can only shrink every piece (``inner(C') ⊆ inner(C)`` and each part of
    the narrower erosion lies inside one part of the wider), and a piece
    dropped under ``pmin`` can never come back — so the passing widths are
    a prefix of the lattice.  The lattice is the law's OWN coordinate
    resolution, ``emit.identity.input_quantum_m`` (§46 (4), 1 mm: the grid
    every coordinate entering the metric frame is snapped to) — C carries
    no resolution constant of its own, and the granularity is a thousandth
    of the ``hard_tol_m`` a held row is allowed, so the search can move no
    vertex a census reads.  WHY IT MUST BE THAT FINE: the status-quo width
    is an arbitrary real, and C must never come out NARROWER than it.  A
    coarser lattice shortfalls by up to one station — MEASURED on the same
    sweep at a 48 m-deep pad: 9.0909 m against a 2 m lattice's 9.0 m.
    Integer bisection on the station index keeps the answer exact and
    reproducible (no float accumulation); the CAP is probed first — the
    common case, one erosion, exactly round 1's cost — then the floor,
    then at most ``log2(K)`` ≈ 14 more.

    Returns ``(C, why, parts, platform pieces, their area)``.  ``why`` is
    ``"cap"`` (the pad carries the full collar), ``"area"`` (an
    intermediate width — the min-area gate is what bounded it) or
    ``"floor"`` (the status-quo width itself, the one width round 2 could
    not improve on).  Empty platform pieces is the REFUSAL, judged at the
    floor: the caller names it from ``parts``."""
    import math
    cap = max(cap, cmin)
    floor = cmin if (rel is None or bank <= 0.0) else min(cap, max(cmin, rel / bank))
    step = step if step > 0.0 else cap - floor
    K = 0 if cap <= floor else max(1, int(math.ceil((cap - floor) / step)))

    def _w(k: int) -> float:
        return min(cap, floor + k * step)

    def _probe(k: int):
        pa, pl, tot = _eroded(P, _w(k), grid, pmin)
        return (bool(pa) and tot >= min_m2), (pa, pl, tot)

    ok, got = _probe(K)
    if ok:
        return _w(K), ("cap" if K else "floor"), got[0], got[1], got[2]
    if K == 0:
        return floor, "floor", got[0], [], got[2]
    ok, got = _probe(0)
    if not ok:
        return floor, "floor", got[0], [], got[2]
    lo, hi, best = 0, K, got             # lo PASSES, hi does not
    while hi - lo > 1:
        mid = (lo + hi) // 2
        ok, g = _probe(mid)
        if ok:
            lo, best = mid, g
        else:
            hi = mid
    return _w(lo), ("floor" if lo == 0 else "area"), best[0], best[1], best[2]


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
                   grid: float = 0.0, dem=None, airport=None) -> tuple[list, dict]:
    """THE SPLIT (module docstring).  Returns ``(pad_regions, counts)``;
    a no-op with ``[building_pad] platform_collar`` off.

    Flat-pad spec §2 (RULINGS 2026-09-30f): with ``[building_pad]
    frontage_hold`` on, every minted platform is TESTED and PARTITIONED
    per rigid block here (``planar.pad_blocks``), the verdicts published
    in ``pad_blocks.BLOCK_PLANS``."""
    PLATFORMS.clear()
    HELD.clear()
    from .pad_blocks import BLOCK_PLANS, plan_blocks
    BLOCK_PLANS.clear()
    split_units: dict[str, list] = {}
    counts: dict[str, _t.Any] = {"platforms": 0, "platforms_refused": 0}
    bp = law.tables.structures.building_pad
    if not bool(getattr(bp, "platform_collar", False)) or not pad_regions:
        return list(pad_regions), counts
    from ..law.tables import design as design_law
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    near = float(design_law(law).pad_frontage_m)
    cap = collar_width_m(law)
    bank = float(law.tables.emit.design.bank_slope)
    # C's absolute floor is the BANK law's narrowest bank (owner RULINGS
    # 2026-10-02z names it); the lattice the width is searched on is the
    # law's own coordinate resolution, §46 (4)'s input quantum.  The
    # SEARCH's floor is the status-quo width ``_collar_for_pad`` derives
    # from ``rel`` — that is what keeps the platform SET main's exactly
    cmin = float(law.tables.emit.design.bank_min_width_m)
    step = float(law.tables.emit.identity.input_quantum_m)
    pmin = float(bp.min_area_m2)
    slope_max = float(law.tables.emit.within_shape.pad_slope_max)
    if min_m2 <= 0.0 or cap <= 0.0 or bank <= 0.0:
        return list(pad_regions), counts
    air_roles = frontage_roles(law)
    air_polys = [r.polygon for r in base_regions
                 if r.source == "cell" and r.role in air_roles
                 and r.polygon is not None and not r.polygon.is_empty]
    if not air_polys:
        return list(pad_regions), counts
    tree = STRtree(air_polys)
    draped = draped_facade_pads(pad_regions, airport)
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
        if id(pr) in draped:
            # a DRAPED FACADE's footprint (module constant): no collar —
            # the sim floors the facade on the terrain under the WHOLE
            # footprint, so the plate stays whole and §4 holds it flat
            PLATFORMS.append(Platform(str(pr.ref), 0.0, round(P.area, 1), 0.0,
                                      nw, rim_relief_m(P, air, near, dem, slope_max),
                                      REFUSED_DRAPED_FACADE, ""))
            out.append(pr)
            continue
        # C IS THE WIDEST WIDTH THIS PAD CAN CARRY (owner RULINGS 2026-10-02z
        # re-land of #86): the cap wherever the pad carries it — so the
        # solve has the whole bank to place the toe in — narrowed station by
        # station only where the cap's erosion would take the platform
        # away, never below ``bank_min_width_m``.  ONE derivation, ONE pass.
        # The DEM relief is still READ — it is what round 1's mint
        # under-read (#86), and the record is how C is judged against the
        # solved relief the census re-reads.
        rel = rim_relief_m(P, air, near, dem, slope_max)
        C, why, parts, plats, tot = _collar_for_pad(
            P, grid, cap, cmin, bank, rel, step, pmin, min_m2)
        if not plats:
            # REFUSED at the SEARCH FLOOR — the status-quo (DEM-relief)
            # width left no platform, which is exactly the pad
            # ``origin/main`` refuses; no wider width could mint it
            # (``_collar_for_pad`` is monotone)
            PLATFORMS.append(Platform(str(pr.ref), round(C, 2), round(P.area, 1),
                                      round(tot, 1), nw, rel,
                                      "eroded_away" if not parts else "under_min_area",
                                      why))
            out.append(pr)
            continue
        cparts = _parts(P.difference(unary_union(plats)))
        if not cparts:
            out.append(pr)
            continue
        bplan = None
        if bool(getattr(bp, "frontage_hold", False)):
            bplan = plan_blocks(str(pr.ref), P, base_regions, law, dem, airport, near)
            if bplan is not None:
                BLOCK_PLANS.append(bplan)
        if bplan is not None and len(bplan.blocks) > 1:
            # flat-pad spec §2 as ruled 2026-09-30r (Q-111b option (1)): the
            # unit is CUT into flat blocks at its necks — one platform +
            # collar per block, ``<ref>/b<k>``; between two blocks' platforms
            # a STRIP of collar wide enough for the 1:3 bank the predicted
            # step needs (§2 (5): the declared pad|pad terrace, never a
            # shared platform vertex at two floors)
            blk = _mint_blocks(pr, P, plats, bplan, law, grid, pmin, C, nw, rel, why)
            if blk is not None:
                split_units[str(pr.ref)] = [b.polygon for b in bplan.blocks]
                for q in blk[0]:
                    plat_ids.add(id(q))
                out.extend(blk[0])
                out.extend(blk[1])
                continue
        PLATFORMS.append(Platform(str(pr.ref), round(C, 2), round(P.area, 1),
                                  round(tot, 1), nw, rel, "", why))
        if bplan is not None:
            one = len(bplan.blocks) == 1
            # a partition the mint could not cut (a block left no platform
            # piece over ``min_area_m2``) keeps the unit whole: every
            # welded contact is held and the solve finds the one datum
            HELD[str(pr.ref)] = {"unit": str(pr.ref), "k": 0, "blocks": 1,
                                 "datum_pred": bplan.blocks[0].datum if one else None,
                                 "verdict": bplan.verdict if one else "unminted_split",
                                 "samples_xy": bplan.blocks[0].samples_xy if one else None,
                                 "samples_held": bplan.blocks[0].samples_held if one else None,
                                 "samples_reach": bplan.blocks[0].samples_reach if one else None,
                                 "samples_ramp": bplan.blocks[0].samples_ramp if one else None}
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
    if split_units:
        # a region still carrying a CUT unit's own ref (a 23a rim sliver)
        # is the collar of the block it stands nearest
        def _to_block(r):
            polys = split_units.get(str(r.ref))
            if polys is None or id(r) in plat_ids or r.polygon is None:
                return r
            k = min(range(len(polys)), key=lambda i: polys[i].distance(r.polygon))
            return _dc.replace(r, ref=block_ref(str(r.ref), k) + COLLAR_SUFFIX)
        out = [_to_block(r) for r in out]
    # flat-pad spec v2 §4 (owner RULINGS 2026-09-30y (1) "EVERY building"):
    # a §20 CONFORMING pad — a welded pad of at least ``[building_pad]
    # min_area_m2`` fronting airside that mints no platform (the
    # ``cluster_pad_min_m2`` gate stands) — is a HELD block too, of ONE
    # register move: its contacts are its own airside rim vertices, its
    # datum column one of its own vertices (``model.platform.datum_vertices``)
    if bool(getattr(bp, "frontage_hold", False)):
        pmin4 = float(bp.min_area_m2)
        minted_refs = {p.ref for p in PLATFORMS if not p.refused}
        for r in out:
            ref = str(r.ref)
            P = r.polygon
            if (ref in HELD or ref in minted_refs or ref.endswith(COLLAR_SUFFIX)
                    or ref in split_units or P is None or P.is_empty
                    or not isinstance(P, Polygon) or P.area < pmin4):
                continue
            cand = [air_polys[int(j)] for j in
                    tree.query(P, predicate="dwithin", distance=near)]
            if not cand or _welded_samples(P, unary_union(cand), near) < _MIN_WELDED:
                continue
            HELD[ref] = {"unit": ref, "k": 0, "blocks": 1, "datum_pred": None,
                         "verdict": "conforming", "conforming": True,
                         "samples_xy": None, "samples_held": None,
                         "samples_reach": None, "samples_ramp": None}
        counts["conforming_held"] = sum(1 for h in HELD.values() if h.get("conforming"))
    counts["platforms"] = sum(1 for p in PLATFORMS if not p.refused)
    counts["platforms_refused"] = sum(1 for p in PLATFORMS if p.refused)
    # THE REPORT ROW (#86 round 2): C and WHY per platform — ``cap`` where
    # the pad carries the full collar, ``area`` where the min-area gate
    # bounded it, ``floor`` where the status-quo (pre-collar86) width is
    # the widest the pad carries
    counts["platform_list"] = "; ".join(
        f"{p.ref} C {p.collar_m:g} m ({p.collar_why}) "
        f"{p.platform_m2:,.0f}/{p.pad_m2:,.0f} m2"
        + (f" REFUSED {p.refused}" if p.refused else "") for p in PLATFORMS[:12])
    counts["platform_collar_why"] = {
        w: sum(1 for p in PLATFORMS if not p.refused and p.collar_why == w)
        for w in ("cap", "area", "floor")}
    return out, counts


def _mint_blocks(pr, P: Polygon, plats: list, bplan, law: Law, grid: float,
                 pmin: float, C: float, nw: int, rel,
                 why: str = "cap") -> "tuple[list, list] | None":
    """The block faces of one CUT unit (``platform_split``): per block ``k``
    the platform pieces inside its polygon, less a STRIP along every cut
    chord it touches (half the bank the predicted step needs, at least half
    ``bank_min_width_m`` — the terrace between two flat floors is a 1:3 bank
    in the heightfield, §2 (5)), and the collar = the rest of the block.
    Registers each block in ``PLATFORMS`` and ``HELD``.  ``None`` when a
    block would carry no platform piece (the caller keeps the unit whole)."""
    bank = float(law.tables.emit.design.bank_slope)
    bmin = float(law.tables.emit.design.bank_min_width_m)
    strips = []
    for (i, j, step), chord in zip(bplan.steps, bplan.cuts):
        w = max(0.5 * bmin, 0.5 * abs(step) / bank) if bank > 0.0 else 0.5 * bmin
        strips.append((i, j, chord.buffer(w, cap_style=2)))
    plat_regs: list = []
    col_regs: list = []
    recs: list = []
    inner = unary_union(plats)
    for b in bplan.blocks:
        Q = b.polygon
        cut = [g for i, j, g in strips if b.k in (i, j)]
        body = Q.intersection(inner)
        if cut:
            body = body.difference(unary_union(cut))
        keep = []
        for q in _parts(body):
            if grid > 0.0:
                s_ = q.simplify(0.5 * grid, preserve_topology=True)
                q = s_ if isinstance(s_, Polygon) and not s_.is_empty else q
            if q.area >= pmin:
                keep.append(q)
        if not keep:
            return None
        ref = block_ref(str(pr.ref), b.k)
        plat_regs.extend(_dc.replace(pr, ref=ref, polygon=q) for q in keep)
        col = _parts(Q.difference(unary_union(keep)))
        col_regs.extend(_dc.replace(pr, ref=ref + COLLAR_SUFFIX, polygon=q) for q in col)
        recs.append((ref, b, sum(q.area for q in keep)))
    for ref, b, a in recs:
        PLATFORMS.append(Platform(ref, round(C, 2), round(b.polygon.area, 1),
                                  round(a, 1), nw, rel, "", why))
        HELD[ref] = {"unit": str(pr.ref), "k": b.k, "blocks": len(bplan.blocks),
                     "datum_pred": b.datum, "verdict": bplan.verdict,
                     "samples_xy": b.samples_xy, "samples_held": b.samples_held,
                     "samples_reach": b.samples_reach,
                     "samples_ramp": b.samples_ramp}
    return plat_regs, col_regs


def _signed_area(ring: list) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0
                     for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def _merge_group(polys: list[Polygon]) -> "list[Polygon] | None":
    """The faces of ONE ref merged along the edges they share, EXACTLY:
    every oriented ring edge is collected, an edge walked both ways (the
    two faces' common boundary) cancels, and what is left is traced into
    rings — so every vertex of the surviving boundary is kept coordinate
    for coordinate (a GEOS union may drop a collinear node another face
    still walks), and a vertex standing only on a cancelled edge leaves
    the face (the platform is rim-only, spec §1 (4)).  ``None`` when the
    residue is not a set of simple rings (a pinch vertex) — the caller
    then keeps the faces as they were."""
    from collections import Counter

    from shapely.geometry.polygon import orient
    edges: Counter = Counter()
    for p in polys:
        p = orient(p, sign=1.0)
        for ring in (p.exterior, *p.interiors):
            c = [(float(x), float(y)) for x, y in ring.coords][:-1]
            for a, b in zip(c, c[1:] + c[:1]):
                if a != b:
                    edges[(a, b)] += 1
    nxt: dict = {}
    for (a, b), n in edges.items():
        k = n - edges.get((b, a), 0)
        if k <= 0:
            continue
        if k > 1 or a in nxt:
            return None
        nxt[a] = b
    rings: list[list] = []
    while nxt:
        a0, b = nxt.popitem()
        ring = [a0]
        while b != a0:
            if b not in nxt:
                return None
            ring.append(b)
            b = nxt.pop(b)
        if len(ring) >= 3:
            rings.append(ring)
    shells = [r for r in rings if _signed_area(r) > 0.0]
    holes = [r for r in rings if _signed_area(r) < 0.0]
    if not shells:
        return None
    sp = [Polygon(r) for r in shells]
    own: list[list] = [[] for _ in shells]
    for h in holes:
        hp = Polygon(h)
        pt = hp.representative_point()
        hit = [i for i, s in enumerate(sp) if s.contains(pt) and s.area > hp.area]
        if not hit:
            return None
        own[min(hit, key=lambda i: sp[i].area)].append(h)
    out = [Polygon(s, own[i]) for i, s in enumerate(shells)]
    if any(not q.is_valid for q in out):
        return None
    return out


#: The last arrangement's merge read: ``{ref: (faces before, faces after)}``
#: per platform / collar ref with more than one face (``None`` after =
#: the merge refused a pinch and kept the faces).
MERGE_READ: dict[str, tuple[int, "int | None"]] = {}


def merge_platform_faces(faces: list) -> tuple[list, int]:
    """ONE PLATFORM, ONE FACE (owner RULINGS 2026-09-29n (4), issue #94).

    The platform is minted here as ONE region, but the arrangement nodes
    every ring it is given, and a foreign ring edge that runs THROUGH the
    pad (#94: the apron cell's east shell edge at x = 20, which its own
    hole touches along the whole pad) splits the platform — and its collar
    — into several faces of one ref, of which each consumer reading "the
    face" saw one.  At this single derivation site (RULINGS 2026-08-30l)
    the faces of every minted platform ref, and of its collar, are merged
    back along the edges they share (:func:`_merge_group`); the dividing
    edge becomes interior and is dropped with any vertex it alone carried.
    Pieces that share no edge (a district pad's erosion islands) stay
    separate faces.  Returns ``(faces, merged)``: faces removed."""
    MERGE_READ.clear()
    refs = {p.ref for p in PLATFORMS if not p.refused}
    if not refs:
        return faces, 0
    keys = refs | {r + COLLAR_SUFFIX for r in refs}
    groups: dict[tuple, list[int]] = {}
    for i, (_poly, reg) in enumerate(faces):
        if str(reg.ref) in keys:
            groups.setdefault((str(reg.ref), reg.role), []).append(i)
    drop: set[int] = set()
    add: dict[int, list] = {}
    for _k, ix in groups.items():
        if len(ix) < 2:
            continue
        merged = _merge_group([faces[i][0] for i in ix])
        MERGE_READ[_k[0]] = (len(ix), None if merged is None else len(merged))
        if merged is None or len(merged) >= len(ix):
            continue
        reg = max((faces[i] for i in ix), key=lambda t: t[0].area)[1]
        drop.update(ix)
        add[min(ix)] = [(q, reg) for q in merged]
    if not drop:
        return faces, 0
    # the merged face takes its group's first slot (face order stable)
    out: list = []
    for i, t in enumerate(faces):
        if i in add:
            out.extend(add[i])
        elif i not in drop:
            out.append(t)
    return out, len(faces) - len(out)
