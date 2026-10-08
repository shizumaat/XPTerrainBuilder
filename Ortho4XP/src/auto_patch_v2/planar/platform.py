"""THE UNIT PAD'S BLOCK PLANNER (flat-pad spec §2; spec §56 (3): the collar
is DELETED — owner RULINGS 2026-10-07b (4) / 07c (6); issue #452).

A unit pad (area >= ``[placement] cluster_pad_min_m2``, the §30 (4)
cluster-pad bar) that FRONTS AIRSIDE is ONE face on ONE flat plane, its
whole rim on the plane, SEATED by the stage-1 solve at the level the apron
can reach along its frontage (the free datum and the hard welds, RULINGS
2026-10-02ah; ``constraints/platform``, ``constraints/no_step``).  Here, at
the one site the pad polygon is final (after ``pad_cut.apron_cut_to_pads``
and ``pad_terrace.pad_terrace_split``, before pass B nodes the pads), each
such pad is TESTED and PLANNED (``pad_blocks.plan_blocks``):

* ONE block — the region is left WHOLE under its own ref and registered in
  :data:`HELD` with the plan's record;
* SEVERAL blocks (a stepped base, RULINGS 2026-09-30r / 10-02aj) — the unit
  is CUT at its necks into block faces ``<ref>/b<k>``, and between two
  blocks a STRIP ``<ref>/b<k>#strip`` (``model.planar.STRIP_SUFFIX``) wide
  enough for the 1:3 bank the predicted step needs — the declared pad|pad
  terrace, inside the footprint.

No region is eroded and none is refused for its shape: the erosion, the
``#collar`` annulus and the ``under_min_area`` / ``eroded_away`` refusals
went with the collar (the relief it was minted for is taken out of the rim
by the hard hold; a weld the solve cannot hold is RELEASED, reported and
warned — ``constraints/pad_warning``).  No airside vertex is created or
moved.  A DRAPED FACADE's footprint (:data:`REFUSED_DRAPED_FACADE`) is the
one refusal left.  A §20 pad under the unit bar that fronts airside is a
HELD conforming pad (flat-pad spec v2 §4), and the RAMP LANDINGS of a
unit's viaduct (#290, ``planar/landing``) are minted last — a landing
keeps its own ``#collar`` bank."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import frontage_roles
from ..model.planar import STRIP_SUFFIX, block_ref, is_bank_ref
from ..model.platform import HELD, PLATFORMS, Platform
from ..geom.parts import nonempty_polygon_parts

__all__ = ["platform_split", "Platform", "PLATFORMS", "merge_platform_faces"]

#: The ring sampling step of the frontage read (m) — ``pad_terrace._STEP_M``'s
#: geometric resolution, not a law value.
_STEP_M = 2.0
#: A pad needs at least this many welded ring samples to FRONT airside (a
#: plane has three degrees of freedom; a corner touch fronts nothing).
_MIN_WELDED = 3
#: A DRAPED FACADE'S FOOTPRINT IS NOT A UNIT PLATFORM (issue #223, owner read
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
    """THE BLOCK PLANNER (module docstring).  Returns ``(pad_regions,
    counts)``.

    Flat-pad spec §2 (RULINGS 2026-09-30f): with ``[building_pad]
    frontage_hold`` on, every unit pad is TESTED and PARTITIONED per rigid
    block here (``planar.pad_blocks``), the verdicts published in
    ``pad_blocks.BLOCK_PLANS``."""
    PLATFORMS.clear()
    HELD.clear()
    from ..model.platform import LANDINGS
    LANDINGS.clear()
    from .pad_blocks import BLOCK_PLANS, plan_blocks
    BLOCK_PLANS.clear()
    split_units: dict[str, list] = {}
    counts: dict[str, _t.Any] = {"platforms": 0, "platforms_refused": 0}
    bp = law.tables.structures.building_pad
    if not pad_regions:
        return list(pad_regions), counts
    from ..law.tables import design as design_law
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    near = float(design_law(law).pad_frontage_m)
    pmin = float(bp.min_area_m2)
    slope_max = float(law.tables.emit.within_shape.pad_slope_max)
    if min_m2 <= 0.0:
        return list(pad_regions), counts
    air_roles = frontage_roles(law)
    air_polys = [r.polygon for r in base_regions
                 if r.source == "cell" and r.role in air_roles
                 and r.polygon is not None and not r.polygon.is_empty]
    if not air_polys:
        return list(pad_regions), counts
    tree = STRtree(air_polys)
    draped = draped_facade_pads(pad_regions, airport)
    hold = bool(getattr(bp, "frontage_hold", False))
    out: list = []
    unit_ids: set[int] = set()
    for pr in pad_regions:
        P = pr.polygon
        if (P is None or P.is_empty or not isinstance(P, Polygon)
                or P.area < min_m2 or is_bank_ref(pr.ref)):
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
        rel = rim_relief_m(P, air, near, dem, slope_max)
        if id(pr) in draped:
            # a DRAPED FACADE's footprint (module constant): the sim floors
            # the facade on the terrain under the WHOLE footprint, so the
            # plate stays a §20 plate and §4 holds it flat (``conforming``)
            PLATFORMS.append(Platform(str(pr.ref), round(P.area, 1), nw, rel,
                                      REFUSED_DRAPED_FACADE))
            out.append(pr)
            continue
        bplan = None
        if hold:
            bplan = plan_blocks(str(pr.ref), P, base_regions, law, dem, airport, near)
            if bplan is not None:
                BLOCK_PLANS.append(bplan)
        if bplan is not None and len(bplan.blocks) > 1:
            # flat-pad spec §2 as ruled 2026-09-30r (Q-111b option (1)): the
            # unit is CUT into flat blocks at its necks, ``<ref>/b<k>``;
            # between two blocks a STRIP wide enough for the 1:3 bank the
            # predicted step needs (§2 (5): the declared pad|pad terrace,
            # never a shared vertex at two floors)
            blk = _mint_blocks(pr, P, bplan, law, pmin, nw, rel)
            if blk is not None:
                split_units[str(pr.ref)] = [b.polygon for b in bplan.blocks]
                unit_ids.update(id(q) for q in blk[0])
                out.extend(blk[0])
                out.extend(blk[1])
                continue
        PLATFORMS.append(Platform(str(pr.ref), round(P.area, 1), nw, rel))
        if bplan is not None:
            one = len(bplan.blocks) == 1
            # a partition the mint could not cut (a block left no face over
            # ``min_area_m2``) keeps the unit whole: every welded contact is
            # held and the solve finds the one datum
            HELD[str(pr.ref)] = {"unit": str(pr.ref), "k": 0, "blocks": 1,
                                 "datum_pred": bplan.blocks[0].datum if one else None,
                                 "verdict": bplan.verdict if one else "unminted_split",
                                 "samples_xy": bplan.blocks[0].samples_xy if one else None,
                                 "samples_held": bplan.blocks[0].samples_held if one else None,
                                 "samples_reach": bplan.blocks[0].samples_reach if one else None,
                                 "samples_ramp": bplan.blocks[0].samples_ramp if one else None}
        unit_ids.add(id(pr))
        out.append(pr)
    if split_units:
        # ONE REF, ONE PAD: a region still carrying a CUT unit's own ref (a
        # 23a rim sliver, a 28b terrace piece) is the block it stands nearest
        def _to_block(r):
            polys = split_units.get(str(r.ref))
            if polys is None or id(r) in unit_ids or r.polygon is None:
                return r
            k = min(range(len(polys)), key=lambda i: polys[i].distance(r.polygon))
            return _dc.replace(r, ref=block_ref(str(r.ref), k))
        out = [_to_block(r) for r in out]
    # flat-pad spec v2 §4 (owner RULINGS 2026-09-30y (1) "EVERY building"):
    # a §20 CONFORMING pad — a welded pad of at least ``[building_pad]
    # min_area_m2`` fronting airside that is no planned unit (the
    # ``cluster_pad_min_m2`` gate stands; a draped facade; a unit with no
    # plan) — is a HELD block too, of ONE register move: its contacts are
    # its own airside rim vertices, its datum column one of its own vertices
    # (``model.platform.datum_vertices``)
    if hold:
        for r in out:
            ref = str(r.ref)
            P = r.polygon
            if (ref in HELD or is_bank_ref(ref)
                    or ref in split_units or P is None or P.is_empty
                    or not isinstance(P, Polygon) or P.area < pmin):
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
    # owner RULINGS 2026-10-03e (#290): the RAMP LANDINGS of a unit's
    # viaduct — flat groundside pads with their collars, minted after every
    # block is registered and after the ref pass above (it never renames
    # a ``<unit>/landing<k>``)
    from .landing import landing_regions
    from ..law.tables import role_side as _side
    out.extend(landing_regions(
        out, split_units,
        # EVERY airside region, the zones among them (a graded strip is a
        # stage-1 face: MEASURED, HECA replay — a landing collar over one
        # moved stage 1, taxi 294 nodes <= 0.08 m)
        [r.polygon for r in base_regions if r.polygon is not None
         and not r.polygon.is_empty and _side(law, r.role) == "airside"],
        airport, law, float(grid),
        # the LANDING BANK's width (master ruling 2026-10-08 R3 (1))
        float(bp.platform_collar_max_m), counts))
    counts["platforms"] = sum(1 for p in PLATFORMS if not p.refused)
    counts["platforms_refused"] = sum(1 for p in PLATFORMS if p.refused)
    counts["platform_list"] = "; ".join(
        f"{p.ref} {p.pad_m2:,.0f} m2"
        + (f" REFUSED {p.refused}" if p.refused else "") for p in PLATFORMS[:12])
    return out, counts


def _mint_blocks(pr, P: Polygon, bplan, law: Law, pmin: float, nw: int,
                 rel) -> "tuple[list, list] | None":
    """The block faces of one CUT unit (``platform_split``): per block ``k``
    its polygon less a STRIP along every cut chord it touches (half the bank
    the predicted step needs, at least half ``bank_min_width_m`` — the
    terrace between two flat floors is a 1:3 bank in the heightfield, §2
    (5)); the strip half (and any scrap the cut leaves under
    ``min_area_m2``) is ``<ref>/b<k>#strip``.  Registers each block in
    ``PLATFORMS`` and ``HELD``.  ``None`` when a block would carry no face
    (the caller keeps the unit whole)."""
    bank = float(law.tables.emit.design.bank_slope)
    bmin = float(law.tables.emit.design.bank_min_width_m)
    strips = []
    for (i, j, step), chord in zip(bplan.steps, bplan.cuts):
        w = max(0.5 * bmin, 0.5 * abs(step) / bank) if bank > 0.0 else 0.5 * bmin
        strips.append((i, j, chord.buffer(w, cap_style=2)))
    face_regs: list = []
    strip_regs: list = []
    recs: list = []
    for b in bplan.blocks:
        Q = b.polygon
        cut = [g for i, j, g in strips if b.k in (i, j)]
        body = Q.intersection(P)
        if cut:
            body = body.difference(unary_union(cut))
        keep = [q for q in nonempty_polygon_parts(body) if q.area >= pmin]
        if not keep:
            return None
        ref = block_ref(str(pr.ref), b.k)
        face_regs.extend(_dc.replace(pr, ref=ref, polygon=q) for q in keep)
        rest = nonempty_polygon_parts(Q.difference(unary_union(keep)))
        strip_regs.extend(_dc.replace(pr, ref=ref + STRIP_SUFFIX, polygon=q) for q in rest)
        recs.append((ref, b))
    for ref, b in recs:
        PLATFORMS.append(Platform(ref, round(b.polygon.area, 1), nw, rel))
        HELD[ref] = {"unit": str(pr.ref), "k": b.k, "blocks": len(bplan.blocks),
                     "datum_pred": b.datum, "verdict": bplan.verdict,
                     "samples_xy": b.samples_xy, "samples_held": b.samples_held,
                     "samples_reach": b.samples_reach,
                     "samples_ramp": b.samples_ramp}
    return face_regs, strip_regs


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
#: per pad / strip ref with more than one face (``None`` after =
#: the merge refused a pinch and kept the faces).
MERGE_READ: dict[str, tuple[int, "int | None"]] = {}


def merge_platform_faces(faces: list) -> tuple[list, int]:
    """ONE PAD, ONE FACE (owner RULINGS 2026-09-29n (4), issue #94).

    A unit pad is ONE region, but the arrangement nodes every ring it is
    given, and a foreign ring edge that runs THROUGH the pad (#94: the
    apron cell's east shell edge at x = 20, which its own hole touches
    along the whole pad) splits it — and a block's strip — into several
    faces of one ref, of which each consumer reading "the face" saw one.
    At this single derivation site (RULINGS 2026-08-30l) the faces of
    every unit pad / block ref, and of its strip, are merged back along
    the edges they share (:func:`_merge_group`); the dividing edge becomes
    interior and is dropped with any vertex it alone carried.  Pieces that
    share no edge stay separate faces.  Returns ``(faces, merged)``: faces
    removed."""
    MERGE_READ.clear()
    refs = {p.ref for p in PLATFORMS if not p.refused}
    if not refs:
        return faces, 0
    keys = refs | {r + STRIP_SUFFIX for r in refs}
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
