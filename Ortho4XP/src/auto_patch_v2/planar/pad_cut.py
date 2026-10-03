"""THE PAD CUT: building pads against the airside (split out of
``planar/overlay.py`` for its 1,000-line budget, #70 — no behaviour change).

Every function here is one ``build_arrangement`` calls, in its order:

* ``apron_cut_to_pads`` — RULINGS 2026-09-23a, the apron cut back to the
  building pad's footprint BEFORE pass A nodes the airside;
* ``airside_union`` / ``build_rim`` — §16g (10) (12) (1), the airside
  cells' own union and the rim the pads quantise to;
* ``airside_clip`` — §16g (10) (5) (RULINGS 2026-09-14ax), every rigid
  region clipped out of what an aircraft rolls on;
* ``_drop_rim_midpoints`` / ``_renode_counts`` — the densifier filter and
  the re-node census (§16g (10) (12) (2)) the arrangement publishes into
  ``overlay.PAD_AIRSIDE``.

``overlay`` re-exports every name, so ``planar.overlay.<name>`` still
resolves for every reader.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..geom.cluster_outline import AirsideRim, airside_vertex_snap
from ..law.tables import is_rigid_role, rolled_on_roles, sliver_area_factor

__all__ = ["airside_union", "build_rim", "apron_cut_to_pads", "airside_clip",
           "plateau_cut"]


def airside_union(regions, law):
    """§16g (10) (12) (1): the AIRSIDE CELLS' own union — the cell regions
    whose role is in ``law.tables.rolled_on_roles``, and NOTHING a pad
    contributes.  ONE derivation, read by the clip and by the re-node
    census alike."""
    return unary_union([r.polygon for r in regions
                        if r.source == "cell" and r.role in rolled_on_roles(law)])


def build_rim(air, law, nodes=None) -> AirsideRim:
    """THE RIM the pads quantise to (§16g (10) (12) (1)) — built ONCE per
    arrangement, over the airside union and the ARRANGEMENT's own node set
    (pass A's), never the region ring's."""
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    return AirsideRim(air, 1.5 * ident,
                      float(law.tables.structures.placement.pad_airside_snap_max_m),
                      nodes=nodes, node_tol_m=0.5 * ident)


#: an apron/pad overlap at or under this is a TOUCH, not an overlap
#: (``apron_cut_to_pads``): a shared edge's own rounding, never ground
_TOUCH_ONLY_M2 = 0.01

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


def apron_cut_to_pads(base_regions, pad_regions, law,
                      grid: float = 0.0) -> tuple[list, list, dict]:
    """RULINGS 2026-09-23a — APRON DOES NOT EXTEND UNDER BUILDING PADS.

    The owner ruled the §16g (10) (5) / (12) subtraction BACKWARDS for a
    BUILDING UNIT: a building pad MATCHES ITS FOOTPRINT (18q / 18t's unit
    footprint), so the pad keeps every square metre of it and the APRON
    FACE is the thing that is cut back.  This is that cut, and it is the
    ONE site it happens at: each APRON-class airside CELL region is
    differenced by the union of the building pads standing on it, so the
    shared ring is the PAD's own ring, coordinate for coordinate — a §28 /
    §16g (10) (6) ``pad_airside_weld`` pair, which is what "apron and
    terminal always meet smoothly" (18t) asks for.

    THE RUNWAY AND TAXI FAMILIES ARE NOT APRON.  23a speaks of the apron;
    a pad never takes a runway or a taxiway (airside is king, 14ah), so a
    pad that reaches one is still TRIMMED by it here — the old direction,
    for those two families alone — and the area is counted
    (``pad_trimmed_by_runway_taxi_m2``).

    Returns ``(base_regions, pad_regions, counts)``.  The caller runs this
    BEFORE pass A nodes the airside (``build_arrangement``): pass A must
    see the CUT apron, or the apron's pre-cut ring and cell edges stay in
    the noded set under the pad — cutting one footprint into many faces —
    and every pad-edge vertex reads as minted on the rim by §16g (10)
    (12)'s re-node census (measured SPJC, cut after pass A: the terminal
    in 5 faces, ``renode_minted_on_rim`` 741).

    THE PAD IS PUT ON THE IDENTITY GRID FIRST (``grid``, the arrangement's
    own snap).  Pass A snap-rounds the cut apron ring, so a RAW pad edge
    added in pass B runs a hair beside its own snapped copy and the two
    cross at every few metres — each crossing a hot pixel, i.e. an airside
    node the pad minted (measured SPJC with raw pads: 180 minted along the
    shared edges, 134 of them "inside" the airside by a few cm).  A pad
    whose vertices already sit on the grid snaps to itself, so its edge
    and the apron's are one segment set.

    Measured trigger: SPJC's terminal, 87 % of its 99,080 m2 footprint
    over rolled-on apron, emitted as a ~13 k m2 pad by the old clip."""
    counts: dict = {"pads": len(pad_regions)}
    p = law.tables.precedence
    king = set(p.runway_family.members) | set(p.taxi_family.members)
    rolled = rolled_on_roles(law)
    # the rolled-on set less the two families IS the airside apron class
    # (``rolled_on_roles``' own definition) — one derivation, no list
    cut_roles = rolled - king
    king_u = unary_union([r.polygon for r in base_regions
                          if r.source == "cell" and r.role in king])
    pads_out = []
    trimmed = 0.0
    def _on_grid(g):
        if grid <= 0.0 or g is None or g.is_empty:
            return g
        q = shapely.set_precision(g, grid)
        return q if q.is_valid else q.buffer(0.0)

    gridded = []
    for r in pad_regions:
        if r.polygon is None or r.polygon.is_empty:
            continue
        for q in _polys(_on_grid(r.polygon)):
            gridded.append(r if q is r.polygon else _dc.replace(r, polygon=q))
    for r in gridded:
        g = r.polygon
        if not king_u.is_empty and g.intersects(king_u):
            before = g.area
            g = _on_grid(g.difference(king_u))
            trimmed += before - g.area
            parts = _polys(g)
            if not parts:
                counts["pad_dropped_on_runway_taxi"] = \
                    int(counts.get("pad_dropped_on_runway_taxi", 0)) + 1
                continue
            for q in parts:
                pads_out.append(_dc.replace(r, polygon=q))
            continue
        pads_out.append(r)
    counts["pad_trimmed_by_runway_taxi_m2"] = round(trimmed, 1)
    if not pads_out:
        return list(base_regions), pads_out, counts
    pad_u = unary_union([r.polygon for r in pads_out])
    out = list(base_regions)
    welds = 0
    cut = 0
    area_cut = 0.0
    cut_by_ref: dict[str, float] = {}
    consumed: list[str] = []
    for i, r in enumerate(out):
        if r.source != "cell" or r.role not in cut_roles:
            continue
        if not r.polygon.intersects(pad_u):
            continue
        # a pad that only TOUCHES the apron takes none of it: the face is
        # left exactly as it was (its ring re-densified between the pad's
        # corners would move the apron's own nodes for nothing), and pass B
        # nodes the pad onto that edge as it always has
        if r.polygon.intersection(pad_u).area <= _TOUCH_ONLY_M2:
            continue
        g = r.polygon.difference(pad_u)
        area_cut += r.polygon.area - g.area
        ps = _polys(g)
        if not ps:
            # the apron face lies WHOLLY under a pad: the pad is the
            # ground there, so the face yields entirely
            counts["apron_face_consumed"] = \
                int(counts.get("apron_face_consumed", 0)) + 1
            cut_by_ref[str(r.ref)] = cut_by_ref.get(str(r.ref), 0.0) + r.polygon.area
            consumed.append(str(r.ref))
            out[i] = None
            continue
        cut_by_ref[str(r.ref)] = cut_by_ref.get(str(r.ref), 0.0) + (
            r.polygon.area - g.area)
        cut += 1
        welds += sum(1 for q in ps if q.boundary.intersects(pad_u.boundary))
        out[i] = _dc.replace(r, polygon=max(ps, key=lambda q: q.area))
        for extra in sorted(ps, key=lambda q: -q.area)[1:]:
            out.append(_dc.replace(r, polygon=extra))
    counts["apron_faces_cut"] = cut
    # WHICH apron faces yielded, and how much each gave — the read the
    # owner's "airside lost under a terminal" question asks (a string, so
    # the arrangement's publication stays scalar-per-key)
    counts["apron_consumed_refs"] = ",".join(sorted(consumed))
    counts["apron_cut_top"] = ", ".join(
        f"{k} {v:,.0f}" for k, v in sorted(cut_by_ref.items(),
                                            key=lambda kv: -kv[1])[:6])
    counts["apron_area_cut_m2"] = round(area_cut, 1)
    counts["pad_airside_weld_pairs"] = welds
    counts["pad_area_kept_m2"] = round(pad_u.area, 1)
    return [r for r in out if r is not None], pads_out, counts


def airside_clip(regions, law, air=None, nodes=None, rim=None, select=None,
                 near_m: float = 0.0, keep_out=None) -> tuple[list, dict]:
    """§16g (10) (5) AT THE SITE WHERE THE FACES HAVE ROLES (owner RULINGS
    2026-09-14ax): every RIGID (``building``) region clipped out of the
    airside faces — ``law.tables.rolled_on_roles``: the runway family, the
    taxi family and the airside, non-rigid apron roles, which is the one
    derivation of "what an aircraft rolls on" and excludes the groundside
    lots, islands and service pavement by construction.

    Round 1 (lane ``v2padvert``, RULINGS 2026-09-14as (i)) ran this at
    ``classify/evidence._pads`` and MEASURED why it cannot live there: at
    evidence time no role is scored, so the only union available is every
    apt.dat pavement page, and armed it took the pad off a groundside
    island's shed.  Here the roles exist.

    Two halves, both round 1's, both measured at HECA (pads ON vs OFF,
    airside vertices gone/new: 280/88 unclipped):

    * THE CLIP.  The pad is differenced out of the airside union, so
      ``classify/roles``'s subtraction of the pad union from the airside
      region is area-null and the airside polygon stops being a function
      of which pads exist (59/79).
    * THE RIM SNAP.  The clip's own CROSSING POINTS are not rim NODES, and
      noded here they SPLIT an airside edge and mint a vertex that exists
      only because the pad does; within ``[placement]
      pad_airside_snap_max_m`` they move to the rim's nearest node — the
      pad yields, the airside never does (28/35).

    A pad the clip would ERASE is counted and dropped: it stands wholly
    on what an aircraft rolls on, and §16g (10) (5)'s own clause is that
    its bodies seat on the pavement.

    ``select`` (default: the rigid roles) picks the regions clipped, and
    ``near_m`` also quantises a selected region standing within it of the
    airside without touching it.  RULINGS 2026-09-30aa rule 9 (#100): the
    mapped-road RIBBONS join pass B through THIS clip — ``select`` their
    regions, ``near_m`` the rim's hot-pixel band — so no ribbon ring node
    stands within the band except AS a rim node: the contact is a WELD.
    ``keep_out``: ground the weld never grows a ribbon into (the other
    cells standing — a lot between the ribbon and an apron).
    """
    counts: dict = {}
    pick = select if select is not None else (lambda r: is_rigid_role(law, r.role))
    pad_ix = [i for i, r in enumerate(regions) if pick(r)]
    if not pad_ix:
        return list(regions), counts
    if air is None:
        air = airside_union(regions, law)
    counts["pads"] = len(pad_ix)
    if air.is_empty:
        return list(regions), counts
    # THE HOT-PIXEL BAND IS ONE AND A HALF GRID CELLS, MEASURED.  The
    # noding snap-ROUNDS to ``min_distinct_spacing_m``: a pad coordinate
    # and an airside edge each move up to half a cell diagonally, so two
    # things within ~1.4 cells of each other can round together and the
    # pad's point becomes a hot pixel the airside edge is SPLIT at.  At
    # one cell HECA still minted 29 airside vertices, every one standing
    # 0.02 .. 0.50 m off the boundary — inside the band a single cell
    # leaves open.
    if rim is None:
        rim = build_rim(air, law, nodes)
    counts["rim_nodes_ring"] = rim.nodes_ring
    counts["rim_nodes_arrangement"] = rim.nodes_kept
    out = list(regions)
    drop: set[int] = set()
    for i in pad_ix:
        r = out[i]
        if near_m > 0.0:
            # 30aa rule 9: THE WELD — no ring node within the band except AS
            # a rim node (``_weld_to_rim``)
            if r.polygon.distance(air) > near_m:
                continue
            from .ribbon_weld import _weld_to_rim   # lazy: ribbon_weld imports this module
            ps = _polys(_weld_to_rim(r.polygon.difference(air), rim, near_m,
                                     counts, keep_out))
            counts["welded"] = int(counts.get("welded", 0)) + 1
            if not ps:
                counts["dropped_wholly_in_band"] = \
                    int(counts.get("dropped_wholly_in_band", 0)) + 1
                drop.add(i)
                continue
            out[i] = _dc.replace(r, polygon=max(ps, key=lambda q: q.area))
            for extra in sorted(ps, key=lambda q: -q.area)[1:]:
                out.append(_dc.replace(r, polygon=extra))
            continue
        if not r.polygon.intersects(air):
            continue
        g = r.polygon.difference(air)
        if g.is_empty or g.area <= 0.0:
            # THE CLIP TRIMS A PAD, IT NEVER DELETES ONE.  A pad WHOLLY on
            # what an aircraft rolls on is the §30 / 14ai PAD-IN-AN-APRON
            # class — the pad that welds to the apron around it and keeps
            # its own two-sided plate (r5's "30 pads wholly in the band").
            # §16g (10) (12) (1) (Fable 2026-09-16; RULINGS 2026-09-16b):
            # THE PAD IS DROPPED.  It was KEPT until now — the §30 / 14ai
            # pad-in-an-apron class, which welds to the apron around it and
            # keeps its own two-sided plate — and the comment here said so
            # while also naming it "the one class that can still make the
            # airside depend on the pad set".  MEASURED (lane
            # ``v2padclip``, HECA): it is the ONLY class left.  With the
            # two-pass arrangement the crossing points mint 5 airside nodes
            # and these 8 pads mint **548**, every one of them STRICTLY
            # INSIDE the airside union — a ring cutting the apron face it
            # stands in.  (12) (1)'s own sentence is "a pad polygon is the
            # cluster outline MINUS the airside union", and §16g (10) (5)
            # already says a cluster wholly on airside pavement gets no pad
            # and its bodies seat on the pavement.  So the general pad now
            # obeys the derived pad's rule.
            counts["dropped_wholly_on_airside"] = \
                int(counts.get("dropped_wholly_on_airside", 0)) + 1
            drop.add(i)
            continue
        counts["clipped"] = int(counts.get("clipped", 0)) + 1
        parts = [airside_vertex_snap(q, rim, counts)
                 for q in _polys(g)]
        g = unary_union(parts)
        ps = _polys(g)
        if not ps:
            drop.add(i)
            continue
        out[i] = _dc.replace(r, polygon=max(ps, key=lambda q: q.area))
        for extra in sorted(ps, key=lambda q: -q.area)[1:]:
            out.append(_dc.replace(r, polygon=extra))
    return [r for i, r in enumerate(out) if i not in drop], counts


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area > 0.0 else []
    return [q for q in getattr(g, "geoms", ())
            if isinstance(q, Polygon) and q.area > 0.0]


def _drop_rim_midpoints(lines, rim, nodes: set, own: set,
                        tol_m: float = 0.0) -> tuple[list, int]:
    """Drop every coordinate the DENSIFIER inserted on the airside rim
    (§16g (10) (12) (1)) — a point that lies on the rim, is not one of the
    arrangement's own nodes, and is not a vertex of the pad's own polygon.

    ``own`` is what makes this a densifier filter and not a pad-corner
    eraser: a pad corner standing on the rim is the pad's own geometry (a
    crossing point the snap either quantised or counted as too far), and
    dropping it collapses the ring — the three ``test_v2padlevel``
    fixtures whose pad merely TOUCHES its apron along a straight edge are
    exactly that case.  Returns the surviving lines and the count.

    ``tol_m`` (RULINGS 2026-09-23a): how far from the rim a densifier
    point may stand and still be the rim's.  Under 23a the pad's edge IS
    the cut apron's edge, but the rim is read off the GRID-SNAPPED airside
    while the densified pad lines are raw, so a midpoint exactly on the
    raw shared edge stands up to half a grid diagonal off the snapped one
    and was never recognised: measured SPJC, 188 pad-edge midpoints minted
    as airside nodes.  A densifier point is collinear by construction, so
    dropping one within ``tol_m`` of the rim never changes the pad."""
    if rim is None or rim.boundary is None:
        return list(lines), 0
    out, gone = [], 0
    for ln in lines:
        cs = [(float(x), float(y)) for x, y in ln.coords]
        keep = []
        for c in cs:
            if c not in nodes and c not in own and (
                    rim.on_boundary(c) if tol_m <= 0.0
                    else rim.rim_distance(c, tol_m) is not None):
                gone += 1
                continue
            keep.append(c)
        if len(keep) >= 2:
            out.append(LineString(keep))
        elif len(cs) >= 2:
            out.append(ln)          # nothing left to say: keep it as found
    return out, gone


def _renode_counts(before, after, air) -> dict:
    """§16g (10) (12) (2): how many nodes inside or on the AIRSIDE union
    the pad stage DELETED and MINTED.

    The population is the nodes standing on airside ground, not the faces
    — a face-level read would have to polygonize twice and would answer
    the same question, and the node is the unknown the solve carries
    (09-01g, contact = value).  A node ON the boundary counts: it belongs
    to an airside cell as much as an interior one does."""
    if air is None or air.is_empty:
        return {"renode_deleted": 0, "renode_minted": 0}

    def _on_air(cs):
        if not cs:
            return set()
        pts = shapely.points(np.asarray(cs, dtype=float))
        keep = shapely.intersects(air, pts)
        return {cs[i] for i in range(len(cs)) if bool(keep[i])}

    b, a = _on_air(list(before)), _on_air(list(after))
    minted = a - b
    out = {"renode_deleted": len(b - a), "renode_minted": len(minted),
           "renode_airside_nodes": len(b)}
    # WHERE a minted node stands says WHICH mechanism minted it, and the
    # two have different levers: ON the airside boundary it is a pad
    # CROSSING POINT the snap could not reach a node with
    # (``snap_too_far``); INSIDE the airside it is a pad that STANDS on
    # airside ground — the ``kept_wholly_on_airside`` / refused class,
    # whose ring cuts the face it sits in.
    #: THE NODES THEMSELVES, in the frame — the census family
    #: ``pad_airside_renode`` emits ONE ROW PER NODE off this list
    #: (``pipeline/publication`` converts to lat/lon).  A count alone
    #: cannot be sited, and a family that cannot be sited cannot be read
    #: in the cockpit block.
    out["renode_deleted_xy"] = sorted(b - a)[:4000]
    out["renode_minted_xy"] = sorted(minted)[:4000]
    if minted:
        cs = sorted(minted)
        pts = shapely.points(np.asarray(cs, dtype=float))
        on = shapely.dwithin(air.boundary, pts, 1e-6)
        out["renode_minted_on_rim"] = int(sum(1 for v in on if bool(v)))
        out["renode_minted_inside"] = len(cs) - out["renode_minted_on_rim"]
    return out


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


def _held_span(samples, ramp, depth: float):
    """The SPAN of a held block's HELD contacts (spec v2 §3): the union of
    each consecutive held-sample segment's flat-capped band ``depth`` wide
    on both sides — perpendicular to the frontage, so a RAMP stretch
    between two blocks (``samples_ramp``) is covered by neither.

    ONE BAND PER RUN OF CONSECUTIVE HELD SEGMENTS, its joins filled (issue
    #284): a band per SEGMENT left a V notch ``depth`` deep at every turn
    of the frontage — at SPJC building5 a hair slit of apron every few
    metres along the plateau's outer edge, each a jagged face of its own.
    A run still ends at a ramp sample or a jump, with a flat cap, so the
    ramp between two blocks stays covered by neither.  (The same comb, at
    HECA's 90 m depth, was #288's spine at 30.1133729, 31.4011679 and its
    122 building4/b1 zone holes.)"""
    import math as _m
    pts = [tuple(map(float, p)) for p in (samples if samples is not None else ())]
    if len(pts) < 2:
        return None
    flags = [bool(r) for r in (ramp if ramp is not None else [False] * len(pts))]
    gaps = sorted(_m.dist(a, b) for a, b in zip(pts, pts[1:]))
    step = gaps[len(gaps) // 2] if gaps else 0.0
    runs: list[list] = []
    cur: list = []
    for i in range(len(pts) - 1):
        d = _m.dist(pts[i], pts[i + 1])
        ok = not (flags[i] or flags[i + 1]) and 0.0 < d <= 3.0 * step
        if ok:                                   # a held segment: extend
            if not cur:
                cur = [pts[i]]
            cur.append(pts[i + 1])
        elif cur:                                # a ramp or a jump ends it
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    bands = [LineString(r).buffer(depth, cap_style="flat", join_style="round")
             for r in runs]
    return unary_union(bands) if bands else None


def _stand_zone(parts: list, close_m: float, span, outline, ident: float):
    """THE STAND ZONE IS ONE REGION FRONTING ITS BLOCK (issue #284, owner
    sim read 1.0.371: "one apron area = one shape", no jagged interior
    pieces).

    The union of the rider rectangles and the stand capsules leaves V
    notches and hair slits between neighbours (two octagons, a rectangle
    beside a disc) and, where they ring a patch of apron, HOLES; each one
    cut out of the apron is a jagged face of its own (SPJC building5/b0:
    a plateau with 19 holes, 18 of them 0.6-5 m2 ``pav49`` faces).  So the
    union is CLOSED by half the stand radius — a notch narrower than the
    stand's own radius belongs to the stands either side of it — its holes
    are filled, it is clipped to the held span as before, and only the
    parts touching the block's outline stand (a part the span cut away
    from the block fronts nothing).  ``None`` when nothing is left."""
    zone = unary_union(parts)
    if close_m > 0.0:
        zone = zone.buffer(close_m, join_style="mitre").buffer(
            -close_m, join_style="mitre")
    zone = unary_union([Polygon(g.exterior) for g in _flat_polys(zone)])
    zone = zone.intersection(span).simplify(ident)
    near = outline.buffer(max(ident, 1e-6))
    keep = [Polygon(g.exterior) for g in _flat_polys(zone) if g.intersects(near)]
    return unary_union(keep) if keep else None


def plateau_cut(base_regions, pad_regions, law, airport,
                grid: float = 0.0) -> tuple[list, dict]:
    """flat-pad spec v2 §3 (owner RULINGS 2026-09-30y addendum) — THE STAND
    LINE: a PLATEAU inside the apron faces fronting a held block.

    The STAND ZONE of held block ``b`` (``model.platform.HELD``) is (a) the
    apron within ``[design] jetway_strip_m`` of the block's RIDER EDGES —
    the jetway strip's own geometry: each outline edge within a rider's
    reach of its anchor (``airport/riders.rider_candidates``; an ``.agp``
    inside the outline at gap 0, the host the nearest pad outline), taken
    ``D`` along its outward normal and ``D`` past each end — united with
    (b) every apt.dat 1300 startup of a ``stand_zone_startup_kinds`` kind
    within ``stand_zone_startup_reach_m`` of the block's HELD contacts,
    buffered by ``stand_zone_radius_m``; CLIPPED to the apron bodies the
    block's outline touches and to the SPAN of its HELD contacts (the ramp
    contacts excluded, :func:`_held_span`, so two blocks' plateaus never
    touch).  Each apron region is split into its plateau piece — role
    ``apron``, ref ``<apron ref>#plateau:<block ref>``
    (``model.planar.PLATEAU_MARK``) — and the rest; the piece's new
    boundary is snapped to the region's own ring coordinates within the
    identity spacing.  The ONE site (the 23a precedent: airside faces cut
    by pad geometry); it runs after ``planar/platform.platform_split``,
    which MINTS the held blocks and their ramp masks it reads.  Registry:
    ``model.platform.PLATEAUS``."""
    import math as _m

    from shapely.geometry import MultiPoint, Point
    from shapely.geometry.polygon import orient
    from shapely.ops import nearest_points
    from shapely.strtree import STRtree

    from ..law.tables import chord_cap_m, design as design_law
    from ..model.planar import PLATEAU_MARK, platform_ref_of
    from .chords import densify
    from ..model.platform import HELD, PLATEAUS
    PLATEAUS.clear()
    d = design_law(law)
    D = float(d.jetway_strip_m)
    Rz = float(d.stand_zone_radius_m)
    reach_s = float(d.stand_zone_startup_reach_m)
    kinds = frozenset(d.stand_zone_startup_kinds)
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    weld = float(law.tables.emit.identity.weld_spacing_m)
    counts: dict = {"plateaus": 0, "plateau_m2": 0.0, "plateau_apron_pieces": 0,
                    "plateau_rest_dissolved": 0, "plateau_rest_dropped": 0,
                    "plateau_rest_padded": 0, "plateau_rest_kept": 0,
                    "plateau_rest_sliver_m2": 0.0,
                    "plateau_rest_kept_m2": 0.0, "plateau_islands_dropped": 0,
                    "plateau_rest_enclosed": 0}
    if not HELD or airport is None or (D <= 0.0 and Rz <= 0.0):
        return base_regions, counts
    # every pad's outline, keyed by its PLATFORM ref (a block's collar joins
    # its block): the held blocks' and the rider hosts' candidates
    outl: dict[str, list] = {}
    for r in pad_regions:
        outl.setdefault(platform_ref_of(r.ref), []).append(r.polygon)
    outline = {k: unary_union(v) for k, v in outl.items()}
    held = [b for b in sorted(HELD) if b in outline]
    if not held:
        return base_regions, counts
    # (a) THE RIDERS and their hosts
    riders_of: dict[str, list] = {}
    if D > 0.0:
        from ..airport.riders import rider_candidates
        cands = rider_candidates(airport, law)
        objs = {o.id: o for o in (getattr(airport, "dsf_objects", ()) or ())}
        keys = sorted(outline)
        tree = STRtree([outline[k] for k in keys])
        for oid, (reach, kind) in sorted(cands.items()):
            o = objs.get(oid)
            if o is None:
                continue
            pt = Point(*o.xy)
            best = None
            for i in tree.query(pt.buffer(reach)):
                k = keys[int(i)]
                poly = outline[k]
                dd = (0.0 if kind == "agp" and poly.covers(pt)
                      else float(poly.boundary.distance(pt)))
                if dd > reach:
                    continue
                key = (round(dd, 6), -poly.area, k)
                if best is None or key < best[0]:
                    best = (key, k)
            if best is not None and best[1] in HELD:
                riders_of.setdefault(best[1], []).append((pt, float(reach)))
    starts = [st for st in (getattr(airport, "startups", ()) or ())
              if str(st.kind) in kinds]
    zones: dict[str, tuple] = {}
    for b in held:
        h = HELD[b]
        span = _held_span(h.get("samples_xy"), h.get("samples_ramp"),
                          max(D, reach_s + Rz))
        if span is None:
            continue
        parts = []
        src = set()
        # (a) the rider edges' rectangles
        for pt, reach in riders_of.get(b, ()):
            geoms = getattr(outline[b], "geoms", [outline[b]])
            for g in geoms:
                ring = list(orient(g, 1.0).exterior.coords)[:-1]
                n = len(ring)
                for k in range(n):
                    (x0, y0), (x1, y1) = ring[k], ring[(k + 1) % n]
                    L = _m.hypot(x1 - x0, y1 - y0)
                    if L <= 0.0 or LineString([ring[k], ring[(k + 1) % n]]).distance(pt) > reach:
                        continue
                    ux, uy = (x1 - x0) / L, (y1 - y0) / L
                    nx, ny = uy, -ux                    # outward on a CCW ring
                    a = (x0 - D * ux, y0 - D * uy)
                    c = (x1 + D * ux, y1 + D * uy)
                    parts.append(Polygon([a, c, (c[0] + D * nx, c[1] + D * ny),
                                          (a[0] + D * nx, a[1] + D * ny)]))
                    src.add("riders")
        # (b) the stands
        sxy = h.get("samples_xy")
        srp = h.get("samples_ramp")
        sxy = [] if sxy is None else list(sxy)
        srp = [False] * len(sxy) if srp is None else list(srp)
        hx = [tuple(map(float, p)) for p, rp in zip(sxy, srp) if not bool(rp)]
        if hx and Rz > 0.0:
            mp = MultiPoint(hx)
            for st in starts:
                p = Point(*st.xy)
                if mp.distance(p) <= reach_s:
                    # A PLATEAU TO THE STAND LINE (owner RULINGS 2026-09-30y
                    # addendum; issue #284): the stand's disc is swept to
                    # the block's outline, so a stand standing beyond
                    # ``stand_zone_radius_m`` of the pad never cuts a flat
                    # ISLAND inside the apron (SPJC building5/b2: faces
                    # 126 / 127, 3.7k / 3.4k m2, 2.8 m off the pad)
                    # ... and on INTO the pad by the radius, so the
                    # capsule's sides CROSS the pad edge (the #150 cut
                    # quantises a crossing; a capsule end lying ALONG the
                    # edge collapsed the plateau's run to one station)
                    q = nearest_points(outline[b], p)[0]
                    dd = q.distance(p)
                    if dd > 0.0:
                        ux, uy = (q.x - p.x) / dd, (q.y - p.y) / dd
                        parts.append(LineString(
                            [(p.x, p.y), (q.x + Rz * ux, q.y + Rz * uy)]
                        ).buffer(Rz, quad_segs=2))
                    else:
                        parts.append(p.buffer(Rz, quad_segs=2))
                    src.add("startups")
        if not parts:
            continue
        zone = _stand_zone(parts, 0.5 * Rz, span, outline[b], ident)
        if zone is None:
            continue
        zones[b] = (zone, "+".join(sorted(src)))
    if not zones:
        return base_regions, counts
    # ONE SLOT PER INPUT REGION, in the input's order: a cut region's rest
    # parts and plateau pieces take ITS slot, so every region the cut does
    # not touch keeps its place in the list.  The arrangement downstream is
    # ORDER-SENSITIVE (measured HECA, no plateau at all: the base regions
    # merely reversed re-node 4 / 5 airside vertices and re-tag 12 — the
    # #150 far vertex, route21 | dsf:objpav85 300 m from any plateau, was
    # this class while the pieces were appended at the end)
    slots: list[list] = [[r] for r in base_regions]
    floor = ident * ident
    sliver_m2 = _identity_sliver_m2(law)
    for b, (zone, source) in zones.items():
        edge = outline[b].buffer(max(grid, ident))
        # THE BUILDING UNIT'S FOOTPRINT RING (owner RULINGS 2026-10-02x
        # (2)): the pad outline's own exterior rings with their holes
        # FILLED -- a scrap standing inside it is the building's connected
        # structure and stays with the pad; every other scrap is GROUND
        # and rejoins the apron (:func:`_dissolve_rest_slivers`)
        pad_fill = unary_union([Polygon(g.exterior)
                                for g in _flat_polys(outline[b])])
        rec = {"source": source, "area_m2": 0.0, "apron_refs": [],
               "riders": len(riders_of.get(b, ())), "startups": 0}
        # every apron region STANDING NOW — an earlier block's rest parts
        # included (a rest's main body need not be its first part)
        cut_at = [(i, j) for i, sl in enumerate(slots)
                  for j, r in enumerate(sl) if r.role == "apron"]
        for i, j in cut_at:
            r = slots[i][j]
            if PLATEAU_MARK in str(r.ref) or not r.polygon.intersects(edge):
                continue
            # THE RING'S OWN STATIONS FIRST: the region is densified at its
            # role's chord cap (``chords.ring_lines``' own densifier) before
            # it is cut, so every station the uncut ring would have carried
            # stays where it is — a cut edge re-densified on its own would
            # move them (measured SPJC: 17 apron ring stations deleted, 15
            # minted, up to 96 m from any plateau ring)
            cap = chord_cap_m(law, r.role)
            poly = Polygon(densify(list(r.polygon.exterior.coords)[:-1], cap, closed=True),
                           [densify(list(h.coords)[:-1], cap, closed=True)
                            for h in r.polygon.interiors])
            r = _dc.replace(r, polygon=poly)
            piece = r.polygon.intersection(zone)
            if piece.is_empty or piece.area <= floor:
                continue
            # THE PLATEAU MEETS THE APRON RING ONLY AT THE RING'S OWN
            # COORDINATES (issue #150, spec v2 §3 / §7 "any airside vertex
            # minted outside plateau_rings"): every piece vertex standing on
            # or within ``tol`` of the region boundary is QUANTISED to the
            # region's nearest ring coordinate, so the cut mints nothing on
            # the ring a neighbour (a junction, a collar) shares, and no
            # pass-A hot pixel splits a ring edge beside the plateau corner
            piece = _quantise_to_ring(piece, r.polygon,
                                      max(weld, grid + ident), floor,
                                      outward=True)
            if piece is None:
                continue
            # ONE APRON AREA, ONE PLATEAU (issue #284): a piece the cut
            # leaves standing apart from its block — the zone crossed a
            # face that is not this apron's — is no plateau FRONTING the
            # block; it stays the host's ground
            own = [g for g in _polys(piece) if g.intersects(edge)]
            if not own:
                continue
            if len(own) != len(_polys(piece)):
                counts["plateau_islands_dropped"] += len(_polys(piece)) - len(own)
                piece = unary_union(own)
            rest = r.polygon.difference(piece)
            p_own = frozenset((float(x), float(y))
                              for g in _polys(piece)
                              for ring in (g.exterior, *g.interiors)
                              for x, y in ring.coords)
            rest = _quantise_to_ring(rest, r.polygon, max(weld, grid + ident),
                                     floor, keep=p_own)
            if rest is None:
                rest = Polygon()
            pieces = [g for g in getattr(piece, "geoms", [piece])
                      if g.geom_type == "Polygon" and g.area > floor]
            if not pieces:
                continue
            rests = [g for g in getattr(rest, "geoms", [rest])
                     if g.geom_type == "Polygon" and g.area > floor]
            # A REST PART UNDER THE IDENTITY-SPACING AREA IS NEVER A FACE
            # OF ITS OWN IF IT CAN HELP IT (issue #150, §7 A9) -- and it is
            # NEVER THE PLATEAU'S unless it stands inside the building
            # unit's footprint ring (owner RULINGS 2026-10-02x (2)): a
            # ground scrap is dissolved back into the host region's own
            # rest part, and where the chord pinched it off at a point it
            # STANDS, as an apron face of the host
            rests, pieces, n_enc = _enclosed_rests_to_plateau(rests, pieces)
            counts["plateau_rest_enclosed"] += n_enc
            rests, pieces, rsl = _dissolve_rest_slivers(
                rests, pieces, sliver_m2, pad_fill=pad_fill)
            counts["plateau_rest_dissolved"] += rsl["dissolved"]
            counts["plateau_rest_padded"] += rsl["padded"]
            counts["plateau_rest_kept"] += rsl["kept"]
            counts["plateau_rest_dropped"] += rsl["dropped"]
            counts["plateau_rest_sliver_m2"] = round(
                counts["plateau_rest_sliver_m2"] + rsl["m2"], 2)
            counts["plateau_rest_kept_m2"] = round(
                counts["plateau_rest_kept_m2"] + rsl["kept_m2"], 2)
            slots[i][j] = [*(_dc.replace(r, polygon=g) for g in rests),
                           *(_dc.replace(r, ref=f"{r.ref}{PLATEAU_MARK}{b}",
                                         polygon=g) for g in pieces)]
            rec["area_m2"] += sum(g.area for g in pieces)
            rec["apron_refs"].append(str(r.ref))
            counts["plateau_apron_pieces"] += len(pieces)
        if rec["apron_refs"]:
            rec["area_m2"] = round(rec["area_m2"], 1)
            PLATEAUS[b] = rec
            counts["plateaus"] += 1
            counts["plateau_m2"] = round(counts["plateau_m2"] + rec["area_m2"], 1)
        # a cut entry is a list until its block is done: flatten the slots
        for i, sl in enumerate(slots):
            slots[i] = [x for e in sl for x in (e if isinstance(e, list) else (e,))]
    return [r for sl in slots for r in sl], counts
