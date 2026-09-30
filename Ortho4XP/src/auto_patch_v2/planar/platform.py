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


# ``Platform`` / ``PLATFORMS`` live in ``model/platform`` (issue #104:
# ``constraints/platform`` reads them and may not import ``planar``);
# re-exported.


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
        inner = P.buffer(-C, join_style=2, mitre_limit=2.0)
        parts = sorted(_parts(inner), key=lambda q: -q.area)
        if not parts:
            PLATFORMS.append(Platform(str(pr.ref), round(C, 2), round(P.area, 1), 0.0,
                                      nw, rel, "eroded_away"))
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
                                      round(tot, 1), nw, rel, "under_min_area"))
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
            blk = _mint_blocks(pr, P, plats, bplan, law, grid, pmin, C, nw, rel)
            if blk is not None:
                split_units[str(pr.ref)] = [b.polygon for b in bplan.blocks]
                for q in blk[0]:
                    plat_ids.add(id(q))
                out.extend(blk[0])
                out.extend(blk[1])
                continue
        PLATFORMS.append(Platform(str(pr.ref), round(C, 2), round(P.area, 1),
                                  round(tot, 1), nw, rel))
        if bplan is not None:
            HELD[str(pr.ref)] = {"unit": str(pr.ref), "k": 0, "blocks": 1,
                                 "datum_pred": bplan.blocks[0].datum,
                                 "verdict": bplan.verdict,
                                 "samples_xy": bplan.blocks[0].samples_xy,
                                 "samples_held": bplan.blocks[0].samples_held}
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
    counts["platforms"] = sum(1 for p in PLATFORMS if not p.refused)
    counts["platforms_refused"] = sum(1 for p in PLATFORMS if p.refused)
    counts["platform_list"] = "; ".join(
        f"{p.ref} C {p.collar_m:g} m {p.platform_m2:,.0f}/{p.pad_m2:,.0f} m2"
        + (f" REFUSED {p.refused}" if p.refused else "") for p in PLATFORMS[:12])
    return out, counts


def _mint_blocks(pr, P: Polygon, plats: list, bplan, law: Law, grid: float,
                 pmin: float, C: float, nw: int, rel) -> "tuple[list, list] | None":
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
                                  round(a, 1), nw, rel))
        HELD[ref] = {"unit": str(pr.ref), "k": b.k, "blocks": len(bplan.blocks),
                     "datum_pred": b.datum, "verdict": bplan.verdict,
                     "samples_xy": b.samples_xy, "samples_held": b.samples_held}
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
