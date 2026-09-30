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
from ..law.tables import is_rigid_role, rolled_on_roles

__all__ = ["airside_union", "build_rim", "apron_cut_to_pads", "airside_clip"]


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


def _weld_to_rim(g, rim, band: float, counts: dict, keep_out=None):
    """RULINGS 2026-09-30aa rules 2 and 9 — A RIBBON'S CONTACT IS A WELD AT
    THE RIM'S OWN NODES.  ``g`` is the ribbon already clipped by the
    airside.  Its part within ``band`` of the airside (the hot-pixel band,
    where noding would round a ribbon coordinate onto an airside edge and
    SPLIT it) is rebuilt: every coordinate standing ON the rim is replaced,
    per contact run, by the rim NODES lying on that run in order (the
    weld: the ribbon shares the airside's vertices and no other), every
    coordinate between the rim and the band's edge is dropped, and the
    band edge is kept.  A contact run with no node on it has nothing to
    weld to: the ribbon stands off by the band there, counted
    (``unwelded_contacts``) — never an airside node minted, never a
    stand-off anywhere a node exists."""
    if g is None or g.is_empty or rim.boundary is None:
        return g
    # the airside union carries the IDENTITY GRID's precision model, and a
    # buffer of it would round the band edge onto that grid (a 0.75 m band
    # read 0.5 m on one side, 1.0 m on the other): the band is cut FLOATING
    air0 = shapely.set_precision(rim.airside, 0.0)
    zone = air0.buffer(band, join_style="mitre", mitre_limit=2.0)
    g = shapely.set_precision(g, 0.0)
    # A RIBBON WITHIN THE BAND OF THE RIM TOUCHES IT: it is grown to the rim
    # there (never more than the band), so its contact is a run of rim
    # nodes — a ribbon standing a hair off an apron edge would otherwise
    # sit in the hot-pixel band, where its crossings with the zone lines
    # round onto the rim and re-route it (measured HECA
    # ``small_roads:-4059#5``, 0.75 m off ``dsf:objpav1``)
    grow = g.buffer(band, join_style="mitre", mitre_limit=2.0).intersection(zone)
    if keep_out is not None and not keep_out.is_empty:
        grow = grow.difference(keep_out)
    g = unary_union([g, grow]).difference(air0)
    core = g.difference(zone)
    strip = g.intersection(zone)
    eps = 1e-6
    tabs: list[Polygon] = []
    for w in _polys(strip):
        ring = [(float(x), float(y)) for x, y in w.exterior.coords[:-1]]
        dist = [rim.rim_distance(c, band) for c in ring]
        on = [d is not None and d <= eps for d in dist]
        if all(on) or not any(on):
            if any(on):
                counts["unwelded_contacts"] = int(counts.get("unwelded_contacts", 0)) + 1
            continue
        k0 = on.index(False)
        ring, dist, on = ring[k0:] + ring[:k0], dist[k0:] + dist[:k0], on[k0:] + on[:k0]
        new: list[tuple[float, float]] = []
        run: list[tuple[float, float]] = []

        def _flush() -> None:
            if not run:
                return
            ns = rim.nodes_along(run, rim.node_tol) if len(run) > 1 else \
                ([run[0]] if rim.has(run[0]) else [])
            if not ns:
                counts["unwelded_contacts"] = int(counts.get("unwelded_contacts", 0)) + 1
            new.extend(ns)
            run.clear()

        for c, d, o in zip(ring, dist, on):
            if o:
                run.append(c)
                continue
            _flush()
            if d is None or d >= band - eps:
                new.append(c)          # the band edge (a side vertex inside it drops)
        _flush()
        dedup = [c for i, c in enumerate(new) if i == 0 or c != new[i - 1]]
        if len(dedup) >= 2 and dedup[0] == dedup[-1]:
            dedup.pop()
        if len(dedup) < 3:
            continue
        t = Polygon(dedup)
        if not t.is_valid or t.area <= 0.0 or \
                t.intersection(rim.airside).area > 1e-6 * max(t.area, 1.0):
            counts["weld_refused"] = int(counts.get("weld_refused", 0)) + 1
            continue
        tabs.append(t)
        counts["weld_tabs"] = int(counts.get("weld_tabs", 0)) + 1
    return unary_union([core, *tabs]) if tabs else core


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
