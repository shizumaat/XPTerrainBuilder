"""THE PLATEAU QUANTISATION AND THE SLIVER RULE.

What ``pad_cut.plateau_cut`` does with the scraps a cut leaves: quantise a
part to the region's own ring (:func:`_quantise_to_ring`), judge a rest
part a SLIVER against the law's identity spacing
(:func:`_identity_sliver_m2`, :func:`_dissolve_rest_slivers`) and hand an
ENCLOSED rest to the plateau (:func:`_enclosed_rests_to_plateau`); and,
after the arrangement, what a PAD scrap the plateau surrounds becomes
(:func:`rerole_plateau_scraps`, spec §56 (10) R-F).

Split out of ``planar/pad_cut`` (issue #303: that file stood at 1,079
lines against the ``planar`` package's 1,000-line budget,
``tests/auto_patch_v2/test_planar.py::test_import_and_budget``).  THE
BUDGET IS NOT RAISED.  ``plateau_cut`` and the apron/airside cuts stay
next door and call these.

No cycle, so no lazy import: this module reads shapely and the law's
sliver factor and never reads ``pad_cut`` back.  Every name keeps its
import path - ``pad_cut`` re-exports all of it, which is what
``planar/overlay`` (``_SHARED_TIE_DP``) and ``test_slivers150``
(``_dissolve_rest_slivers``) read.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..law.tables import sliver_area_factor

__all__ = ["_SHARED_TIE_DP", "_PAD_INSIDE_SLACK", "_QUANTISE_PASSES",
           "_polys", "_flat_polys", "_quantise_to_ring", "_ring_key",
           "_identity_sliver_m2", "_dissolve_rest_slivers",
           "_enclosed_rests_to_plateau", "rerole_plateau_scraps"]


#: shared-boundary lengths equal to this many decimals (metres) are a TIE
#: in :func:`_dissolve_rest_slivers` and in
#: ``overlay.dissolve_sliver_zones``, which reads it from here (1 µm: the
#: float noise of two computations of one shared run, never a real
#: difference).  ONE definition: ``overlay`` imports this module, so the
#: constant cannot live upstream of its second reader.
_SHARED_TIE_DP = 6

#: a scrap stands INSIDE the BUILDING UNIT'S FOOTPRINT RING (owner
#: RULINGS 2026-10-02x (2)) when the area of it standing OUTSIDE that ring
#: is under this fraction of the identity-spacing area it is judged by
#: (``_identity_sliver_m2``, the law's own derivation from
#: ``identity.min_distinct_spacing_m``, so there is no second number):
#: GEOS's own rounding of a run the two geometries share, never ground
_PAD_INSIDE_SLACK = 1e-6


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area > 0.0 else []
    return [q for q in getattr(g, "geoms", ())
            if isinstance(q, Polygon) and q.area > 0.0]


#: the plateau quantisation's pass cap (:func:`_quantise_to_ring`): a pass
#: quantises, the next re-clips to the region and re-quantises what the clip
#: crossed; the loop ends at the first pass that changes nothing
_QUANTISE_PASSES = 4


def _flat_polys(g) -> list[Polygon]:
    """Every polygon of ``g`` with area, through any nesting —
    ``make_valid`` returns a GeometryCollection that HOLDS a MultiPolygon,
    which :func:`_polys` (one level) reads as nothing."""
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area > 0.0 else []
    return [p for part in getattr(g, "geoms", ()) for p in _flat_polys(part)]


def _quantise_to_ring(piece, region: Polygon, tol: float, floor: float,
                      keep: frozenset = frozenset(), outward: bool = False):
    """The plateau piece ``piece`` (``region ∩ zone``) with every coordinate
    standing within ``tol`` of ``region``'s boundary and not one of its own
    ring coordinates moved ONTO a ring coordinate (issue #150).

    ``region ∩ zone`` puts a new vertex wherever the zone's edge crosses the
    apron ring.  That vertex is a node MINTED on the ring — and the ring edge
    is shared: with a junction (a vertex minted on a taxi-family face), with
    a pad collar (pass B nodes it as a crossing), and pass A's 0.5 m
    snap-rounding put the ring's node one hot pixel beside the plateau's own
    corner, so the ring carried a vertex no plateau ring owns (HECA, the
    flatpad128v3 fix arm: 7 added / 2 removed airside nodes outside the
    plateau rings, 0.5-10 m from a ring).  Quantised, the piece meets the
    ring only at coordinates the uncut ring already carries — the ring's
    node set is unchanged and every new vertex stands inside the apron, ON
    the plateau ring.  ``None`` when nothing over ``floor`` m² is left.

    ``outward`` (the plateau): a CROSSING — a coordinate with exactly one
    ring neighbour, the run the piece follows along the ring — goes to the
    station of its ring edge BEYOND it, so the plateau keeps the whole run
    of frontage it reached (nearest-station rounding collapsed a 52 m run
    between two stations 58 m apart onto ONE point).  It grows by at most
    one station spacing.  Every other coordinate goes to the nearest.

    ``keep``: coordinates that stay where they are (the REST of the region
    is quantised too, keeping the plateau's own vertices: GEOS's difference
    resolves a near-touching ring — a neck — with a node of its own, which
    measured HECA put a vertex 0.35 m off pav1's ring, a junction it shares
    re-noded 60 m from any plateau)."""
    rings_r = [[(float(x), float(y)) for x, y in list(ring.coords)[:-1]]
               for ring in (region.exterior, *region.interiors)]
    ring_cs = [c for r in rings_r for c in r]
    if not ring_cs:
        return None
    own = set(ring_cs) | set(keep)
    arr = np.asarray(ring_cs, dtype=float)
    seg_a = np.asarray([r[k] for r in rings_r for k in range(len(r))], dtype=float)
    seg_b = np.asarray([r[(k + 1) % len(r)] for r in rings_r for k in range(len(r))],
                       dtype=float)
    bnd = region.boundary
    from shapely.geometry import Point

    def _near_ring(c) -> bool:
        return c in own or bnd.distance(Point(c)) <= tol

    def _q(c, along=None):
        if c in own or bnd.distance(Point(c)) > tol:
            return c
        if along is not None:
            # the ring edge the crossing stands on, and its station BEYOND
            # the run (the end farther from the along-ring neighbour)
            ab = seg_b - seg_a
            L2 = np.maximum((ab ** 2).sum(axis=1), 1e-18)
            t = np.clip(((c[0] - seg_a[:, 0]) * ab[:, 0]
                         + (c[1] - seg_a[:, 1]) * ab[:, 1]) / L2, 0.0, 1.0)
            dx = seg_a[:, 0] + t * ab[:, 0] - c[0]
            dy = seg_a[:, 1] + t * ab[:, 1] - c[1]
            k = int(np.argmin(dx * dx + dy * dy))
            a, b = tuple(seg_a[k]), tuple(seg_b[k])
            da = (a[0] - along[0]) ** 2 + (a[1] - along[1]) ** 2
            db = (b[0] - along[0]) ** 2 + (b[1] - along[1]) ** 2
            return a if da >= db else b
        i = int(np.argmin(np.hypot(arr[:, 0] - c[0], arr[:, 1] - c[1])))
        return ring_cs[i]

    for _ in range(_QUANTISE_PASSES):
        moved = False
        out = []
        for g in _polys(piece):
            rings = []
            for ring in (g.exterior, *g.interiors):
                cs: list = []
                raw = [(float(x), float(y)) for x, y in list(ring.coords)[:-1]]
                for k, c in enumerate(raw):
                    along = None
                    if outward and len(raw) >= 3:
                        nb = [raw[k - 1], raw[(k + 1) % len(raw)]]
                        on = [q for q in nb if _near_ring(q)]
                        if len(on) == 1:
                            along = on[0]
                    qc = _q(c, along)
                    moved = moved or qc != c
                    if not cs or cs[-1] != qc:
                        cs.append(qc)
                while len(cs) > 1 and cs[0] == cs[-1]:
                    cs.pop()
                rings.append(cs)
            if len(rings[0]) < 3:
                moved = True
                continue
            out.extend(_flat_polys(shapely.make_valid(
                Polygon(rings[0], [h for h in rings[1:] if len(h) >= 3]))))
        piece = unary_union(out) if out else None
        if piece is None or piece.is_empty:
            return None
        # a quantised edge may cut a concave corner of the ring: re-clip,
        # and the next pass quantises whatever the clip crossed
        outside = piece.difference(region).area
        if outside > floor:
            piece = piece.intersection(region)
            moved = True
        if not moved:
            break
    polys = [g for g in _polys(piece) if g.area > floor]
    return unary_union(polys) if polys else None


def _ring_key(g: Polygon) -> tuple:
    """A PART'S OWN IDENTITY: its lexicographically least exterior
    coordinate.  The last word in a tie that must read only the two
    candidates (the #81 rule), never their order in a list."""
    return min((round(float(x), _SHARED_TIE_DP), round(float(y), _SHARED_TIE_DP))
               for x, y in g.exterior.coords)


def _identity_sliver_m2(law) -> float:
    """THE IDENTITY-SPACING AREA: ``(identity.min_distinct_spacing_m x
    terrace.sliver_area_factor)**2`` (0.5 x 8 = 4 m, so 16 m2) — the law's
    OWN single derivation of "too small to be a cell of its own", read by
    the planar build's sliver merge (``overlay.merge_slivers``, RULINGS
    2026-09-08d (4a)).  The plateau cut's REST parts (issue #150) are the
    same artefact class, so they are judged by the same number and there
    is no second one to keep in sync."""
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    return (ident * sliver_area_factor(law)) ** 2


def _dissolve_rest_slivers(rests: list, pieces: list, area_max: float,
                           *, pad_fill=None) -> tuple[list, list, dict]:
    """A PLATEAU CUT MUST NOT CHANGE THE AIRSIDE FACE SET OUTSIDE THE
    PLATEAU RINGS (issue #150, flat-pad spec v2 §7 A9), AND A GROUND SCRAP
    IS THE APRON'S, NEVER THE PLATEAU'S (owner RULINGS 2026-10-02x (2)).

    ``region - piece`` does not leave only the apron's body.  Where the
    quantised piece runs a CHORD between two ring stations the ring itself
    bulges past, the difference pinches off a SCRAP: measured at KCLT ~40
    ``pav14`` parts of 0-6 m2 within 1-23 m of the restored building84
    plateau, at SPJC ~21 ``pav49`` parts of 1-5 m2 (lane sweep1005attr on
    #150, RULINGS 2026-10-02q).  Emitted, each is a FACE — 4-5 airside
    vertices outside every plateau ring, which is exactly what the §7
    criterion counts.  The planar build's own sliver merge
    (``overlay.merge_slivers``, the same area bound) cannot reach them: it
    unions a face only into a face of the SAME ref, and a scrap's one
    neighbour ACROSS A RUN is the plateau piece, whose ref carries
    ``model.planar.PLATEAU_MARK``.

    THE RULING: such a scrap is GROUND — apron surface standing between
    the quantised plateau chord and the apron ring — so it joins the
    APRON host and GRADES WITH IT.  Only a scrap inside the BUILDING
    UNIT'S FOOTPRINT RING (``pad_fill``: the pad outline's own exterior
    rings, holes filled) is part of the building's connected structure and
    stays with the pad.  So a rest part under ``area_max`` is resolved
    HERE, at the derivation site that cut it (owner RULINGS 2026-08-30l:
    trim at the single derivation site, never per consumer), SMALLEST
    FIRST (a chain of scraps resolves into the body and never into each
    other — ``overlay.dissolve_sliver_zones``'s own order), with a TIE
    READING ONLY THE TWO CANDIDATES (the #81 rule: one shared run computed
    twice differs by microns, and a list's order is a function of every
    face at the airport):

    1. UNIONED INTO THE PART OF ITS OWN HOST REGION IT BORDERS LONGEST —
       another REST part (the host's own face: same role, same ref, so
       nothing about the host changes except the run of ring that comes
       back).  Inside ``pad_fill`` the host's PLATEAU PIECE comes first
       instead: the ruling's structure exception, inside the rings where
       §7 permits the change.
    2. Otherwise the scrap STAYS AN APRON FACE OF THE HOST (``kept``),
       with the host's own role and ref.  WHY THE REST TIER CANNOT FIRE
       FOR IT: a scrap pinched between the chord and the ring meets the
       host's body at the CHORD'S END STATIONS ONLY — a POINT, so the
       shared run is zero-length and the tier never fired over 375 scraps
       at three airports (RULINGS 2026-10-02w); and a union across a point
       is TWO polygons, i.e. the scrap still standing as a face of its own
       under another name.  A plateau piece that touches the ring at an
       isolated station disconnects the rest there, and a ring touching
       itself at a point is not a polygon, so there is no union to make.
       The three alternatives are all refused upstream: giving it to the
       plateau is the ruling itself (the plateau never grows past its
       quantised footprint); DROPPING it, or letting a NEIGHBOURING apron
       region absorb it across their shared ring run, takes the bulge's
       own stations out of the arrangement, which is the §7 bar.  So it
       stands, and is COUNTED: ``kept`` / ``kept_m2`` is the residual the
       spec author rules on.
    3. A scrap bordering NOTHING is dropped, exactly as a part under the
       cut's own area floor is: the DEM owns it.

    THE HOST'S STATIONS STAY THE HOST'S either way: a scrap's outer
    boundary IS the region ring it was cut from, so unioning it back
    restores that run station for station and the chord that cut it goes
    interior, and leaving it standing moves nothing at all.

    Returns ``(rests, pieces, stats)``.  ``stats`` counts the parts under
    ``area_max`` by what became of them — ``dissolved`` (a rest part of
    the host), ``padded`` (the host's plateau piece, inside the footprint
    ring), ``kept`` (standing, an apron face of the host), ``dropped``
    — with ``m2`` their TOTAL area (so it is comparable with the 10-02w
    measurement) and ``kept_m2`` the part of it still standing."""
    stats = {"dissolved": 0, "padded": 0, "kept": 0, "dropped": 0,
             "m2": 0.0, "kept_m2": 0.0}
    if area_max <= 0.0 or not rests:
        return rests, pieces, stats
    keep: list = list(rests)
    out_pieces: list = list(pieces)
    order = sorted(range(len(keep)), key=lambda i: (keep[i].area, _ring_key(keep[i])))
    for i in order:
        scrap = keep[i]
        if scrap is None or scrap.area >= area_max:
            continue
        # THE RULING'S ONE EXCEPTION: inside the building unit's footprint
        # ring the scrap is the building's connected structure, so the PAD
        # is its host and the plateau piece ranks first
        in_pad = (pad_fill is not None and not pad_fill.is_empty
                  and scrap.difference(pad_fill).area
                  <= area_max * _PAD_INSIDE_SLACK)
        sb = scrap.bounds
        ranked: list = []
        bordered = False
        for bid, bucket in ((0, keep), (1, out_pieces)):
            for j, cand in enumerate(bucket):
                if cand is None or (bid == 0 and j == i):
                    continue
                cb = cand.bounds                   # a shared run touches
                if (cb[0] > sb[2] or cb[2] < sb[0]  # ... so touching boxes
                        or cb[1] > sb[3] or cb[3] < sb[1]):   # stay in
                    continue
                try:
                    shared = scrap.boundary.intersection(cand.boundary)
                except Exception:                          # pragma: no cover
                    continue
                if shared.is_empty:
                    continue
                bordered = True            # a POINT is a border too: the
                run = float(shared.length)  # ... scrap is not orphaned
                if run <= 0.0 or (bid == 1 and not in_pad):
                    continue
                ranked.append(((1 if bid == 0 else 0) if in_pad else bid,
                               -round(run, _SHARED_TIE_DP),
                               -round(cand.area, _SHARED_TIE_DP),
                               _ring_key(cand), bid, j))
        stats["m2"] += scrap.area
        keep[i] = None
        for _tier, _sh, _ar, _k, bid, j in sorted(ranked):
            bucket = keep if bid == 0 else out_pieces
            # ONE face or no dissolve: two parts meeting at a POINT union
            # into a multipolygon, which is the scrap still standing as a
            # face of its own under another name
            u = _flat_polys(shapely.make_valid(bucket[j].union(scrap)))
            if len(u) != 1:
                continue
            bucket[j] = u[0]
            stats["dissolved" if bid == 0 else "padded"] += 1
            break
        else:
            if bordered:
                keep[i] = scrap          # GROUND: an apron face of the
                stats["kept"] += 1       # ... host, never the plateau's
                stats["kept_m2"] += scrap.area
            else:
                stats["dropped"] += 1
    stats["m2"] = round(stats["m2"], 2)
    stats["kept_m2"] = round(stats["kept_m2"], 2)
    return [g for g in keep if g is not None], out_pieces, stats


def _enclosed_rests_to_plateau(rests: list, pieces: list) -> tuple[list, list, int]:
    """A REST PART INSIDE A PLATEAU PIECE'S OUTLINE IS THE PLATEAU'S
    (issue #288).

    The zone is filled to its outline (``_stand_zone``), but the ring
    QUANTISATION can still close a hole in a piece the raw cut did not
    have (HECA building4/b3: 43.2 m2 at 30.1096273, 31.39589).  ``region -
    piece`` turns such a hole into a rest part ENCLOSED by the plateau: it
    borders no apron ring and no rest body, so neither 10-02x (2)'s "rejoin
    the apron host" nor the scrap tiers can reach it, and it stood as an
    apron face of its own inside the plateau — a separate surface the
    plateau's own rows never see (the 1.92 m pit of #288 was this class).
    What really is not plateau inside an outline — a pad, a building — is
    a hole of the REGION, so it is never a rest part and is untouched here.

    Returns ``(rests, pieces, n_enclosed)``; a union that does not come out
    ONE polygon leaves the part where it was."""
    if not rests or not pieces:
        return rests, pieces, 0
    pieces = list(pieces)
    outlines = [Polygon(p.exterior) for p in pieces]
    kept: list = []
    n = 0
    for g in rests:
        host = next((k for k, o in enumerate(outlines)
                     if o.covers(g) or g.difference(o).area <= 1e-9 * max(g.area, 1.0)),
                    None)
        if host is not None:
            u = _flat_polys(shapely.make_valid(pieces[host].union(g)))
            if len(u) == 1:
                pieces[host] = u[0]
                n += 1
                continue
        kept.append(g)
    return kept, pieces, n


def rerole_plateau_scraps(faces: list, law, counts: "dict | None" = None
                          ) -> list:
    """A SURPLUS PAD PIECE ITS OWN PLATEAU SURROUNDS IS THE PLATEAU (spec
    §56 (10) R-F; the §23a rim-sliver rule read at the arrangement).

    The stand-zone plateau cut (§20) can leave scraps of a pad standing
    between plateau pieces: faces of the pad's role under the pad's base
    ref (``model.planar.pad_base_ref``) that are not its largest face, are
    under the cluster outline's own thin-piece floor (rule 6: mean width
    ``2 A / P`` under ``geom.cluster_outline.THIN_PIECE_WIDTH_M``) and
    whose WHOLE boundary runs along that pad's own plateau
    (``plateau_block_of``) and, between the plateau's ends, along STRUCTURE
    faces (``law.tables.is_structure_role``: MEASURED on the OTHH replay,
    every such scrap is a triangle pinched between the plateau and a basin
    wall's band, 0.5-2.9 m of it).  The plateau is held at the pad's value
    (owner RULINGS 2026-09-01g) and a structure keeps its own law, so the
    scrap stands on the pad's plane whichever of the two it is called: it
    takes the region of the plateau face it shares the longest run with —
    one building face fewer, no vertex moved, no level changed.  A scrap
    any other face borders (open apron, another pad, ground), one no
    plateau borders, or one whose boundary is not covered is left as it is.

    ``faces`` is the arrangement's ``(polygon, region)`` list; the result
    is the same list with the scraps' regions replaced (counted
    ``pad_scraps_reroled`` / ``pad_scraps_reroled_m2``)."""
    from shapely.strtree import STRtree

    from ..geom.cluster_outline import THIN_PIECE_WIDTH_M
    from ..law.tables import is_structure_role, role_side
    from ..model.planar import pad_base_ref, plateau_block_of
    rigid = {r for r, spec in law.tables.precedence.roles.items() if spec.rigid}
    biggest: dict = {}
    for k, (g, r) in enumerate(faces):
        if r.role in rigid and plateau_block_of(r.ref) is None:
            key = (r.role, pad_base_ref(r.ref))
            if key not in biggest or g.area > faces[biggest[key]][0].area:
                biggest[key] = k
    cand = [k for k, (g, r) in enumerate(faces)
            if r.role in rigid and plateau_block_of(r.ref) is None
            and biggest.get((r.role, pad_base_ref(r.ref)), k) != k
            and 2.0 * g.area < THIN_PIECE_WIDTH_M * g.length]
    n, m2 = 0, 0.0
    if cand:
        tree = STRtree([g for g, _r in faces])
        out = list(faces)
        for k in cand:
            g, r = faces[k]
            base = pad_base_ref(r.ref)
            best, run_best, covered, own = None, 0.0, 0.0, True
            for j in sorted(int(q) for q in tree.query(g, predicate="intersects")):
                if j == k:
                    continue
                run = float(g.boundary.intersection(faces[j][0].boundary).length)
                if run <= 0.0:
                    continue
                nr = faces[j][1]
                covered += run
                if is_structure_role(law, nr.role):
                    continue
                if (role_side(law, nr.role) != "airside"
                        or plateau_block_of(nr.ref) != base):
                    own = False
                    break
                if run > run_best:
                    best, run_best = nr, run
            if (not own or best is None
                    or covered < g.length * (1.0 - _PAD_INSIDE_SLACK) - 1e-6):
                continue
            out[k] = (g, best)
            n += 1
            m2 += g.area
        faces = out
    if counts is not None:
        counts["pad_scraps_reroled"] = n
        counts["pad_scraps_reroled_m2"] = round(m2, 1)
    return faces
