"""The ONE planar subdivision (plan §1 row 4; M0 §4 step 3).

Every region (a classified pavement cell, a pad, a road corridor, a zone
region) contributes its rings; every breakline source (runway profile
stations, taxi / road centrelines) its line.  All of it is noded in ONE
``unary_union`` at full precision, snapped ONCE to the identity grid
(``law.emit.identity.min_distinct_spacing_m`` — two distinct vertices
never closer than that, so the near-parallel / sub-micron class the mesh
pays for cannot exist), and polygonised.  Each face takes the region with
the largest overlap; a face no region claims (a hole beyond zone 2) is
dropped — the DEM owns it.

Shared boundaries exist once BY CONSTRUCTION: two regions that share a
boundary contribute the same coordinates, the union merges them, and the
face on each side references the same noded segment.  No annuli, no
T-vertices.  Boundaries that MERELY NEARLY coincide (two sources a
sub-metre apart) are welded first (``weld.py``, RULINGS 2026-09-04u) so
the sliver between them never becomes a face.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import shapely
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..classify.roles import Classification
from ..law import Law
from ..law.tables import chord_cap_m, is_rigid_role, role_side, rolled_on_roles
from ..model.airport import Airport
from .chords import densify, ring_lines, stations
from .terrain_edge import EdgeReport, road_lines
from ..geom.cluster_outline import AirsideRim, airside_vertex_snap
from .weld import WeldStats, weld_cells
from .zones import zone_regions

__all__ = ["Region", "SourceLine", "Arrangement", "build_arrangement", "seam_bands",
           "airside_union",
           "merge_slivers", "dissolve_degenerate_holes",
           "absorb_enclosed_pavement", "dissolve_sliver_zones",
           "inscribed_width_m", "ENCLOSED_MIN_FRAC"]

#: §41 (1): the fraction of its OWN area a pavement face must have inside
#: another pavement face's exterior ring to be that face's hole.  DEFINED
#: IN ``classify/sources.py`` and re-exported here: §42 (2) as amended
#: (RULINGS 2026-09-13dc) applies the same test to a §42 object body
#: before the slice, and ``classify`` may not import ``planar``.
from ..classify.sources import ENCLOSED_MIN_FRAC  # noqa: E402,F401


@_dc.dataclass(frozen=True)
class Region:
    """A face source: what a face inside it becomes."""

    role: str
    ref: str
    polygon: Polygon
    code_number: int | None
    code_letter: str | None
    side: str
    source: str            # "cell" | "zone"
    zone: int | None = None
    #: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19.3 C12):
    #: which rule ended this region — ``"crest"``, ``"road"``, ``"none"``.
    edge_kind: str = "none"
    #: §37 (11) (2): this region reaches the coastline — a QUAY.
    quay: bool = False


@_dc.dataclass(frozen=True)
class SourceLine:
    """A breakline source, before noding."""

    kind: str              # runway_profile | taxi_centerline | road_centerline
    ref: str
    line: LineString
    code_letter: str | None = None   # the taxi chain's letter (04t-3)


@_dc.dataclass
class Arrangement:
    """The noded, polygonised subdivision."""

    faces: list[tuple[Polygon, Region]]
    noded: MultiLineString
    sources: list[SourceLine]
    regions: list[Region]
    dropped_faces: int
    grid_m: float
    #: The tile-seam bands (``law.emit.seam``, user 2026-05-10) cut out of
    #: the arrangement, one per integer lat/lon line the regions cross;
    #: faces inside them are dropped (``dropped_seam_faces``) — the DEM
    #: owns the band, each tile's patch stops ``half_width_m`` short.
    seam_bands: list[Polygon] = _dc.field(default_factory=list)
    dropped_seam_faces: int = 0
    #: The sliver weld (``weld.py``, RULINGS 2026-09-04u) applied to the
    #: cells BEFORE the zones are derived and the rings noded.
    weld: WeldStats = _dc.field(default_factory=WeldStats)
    #: RULINGS 2026-09-08d (4a): same-region faces under the sliver area
    #: merged into their neighbour (``merge_slivers``).
    slivers_merged: int = 0
    #: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19): the edge
    #: SEGMENTS the zone clip made, in the frame — the boundary beyond
    #: which there is no patch and no bank — and what the clip did.
    terrain_edges: tuple = ()
    edge_report: EdgeReport = _dc.field(default_factory=EdgeReport)
    #: RULINGS 2026-09-10h (1): degenerate hole rings dissolved into their
    #: own face (``dissolve_degenerate_holes``) — never a vertex set.
    holes_dissolved: int = 0
    #: §41 (1) (owner RULINGS 2026-09-13co item 2; RULINGS 2026-09-13cs
    #: item 2): pavement faces enclosed by another pavement face's ring
    #: and absorbed into it (``absorb_enclosed_pavement``).
    enclosed_absorbed: int = 0
    #: The same rule's REFUSALS: an enclosed face that shares NO boundary
    #: with its enclosing body, so the union would not be one face — an
    #: island in the middle of a loop, not a notch cut into a body.
    enclosed_detached: int = 0
    #: §41 (4) (owner RULINGS 2026-09-14c item 4): sliver ZONE faces
    #: dissolved into the face they border (``dissolve_sliver_zones``) —
    #: never emitted, never a hole.  ``slivers_zone_area_m2`` is their
    #: area; ``slivers_zone_dropped`` the ones that border nothing at all
    #: (no host to dissolve into: the DEM owns them, as it owns every face
    #: no region claims).
    zone_slivers_dissolved: int = 0
    zone_slivers_dropped: int = 0
    zone_sliver_area_m2: float = 0.0
    #: One record per dissolved/dropped sliver: ``(ref, area_m2, width_m,
    #: host role:ref or None)`` — what the report names.
    zone_sliver_rows: tuple = ()


#: RULINGS 2026-09-14ax: what the ARRANGEMENT's pad clip did this build —
#: the pads trimmed, the crossing points quantised to the airside rim's
#: own nodes, the ones too far to move, every refusal by reason, and the
#: pads the clip would have erased.  ONE publication (``classify.evidence``
#: re-exports it); the report and the census read it, never re-derive it.
PAD_AIRSIDE: dict[str, object] = {}


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
    for i, r in enumerate(out):
        if r.source != "cell" or r.role not in cut_roles:
            continue
        if not r.polygon.intersects(pad_u):
            continue
        g = r.polygon.difference(pad_u)
        area_cut += r.polygon.area - g.area
        ps = _polys(g)
        if not ps:
            # the apron face lies WHOLLY under a pad: the pad is the
            # ground there, so the face yields entirely
            counts["apron_face_consumed"] = \
                int(counts.get("apron_face_consumed", 0)) + 1
            out[i] = None
            continue
        cut += 1
        welds += sum(1 for q in ps if q.boundary.intersects(pad_u.boundary))
        out[i] = _dc.replace(r, polygon=max(ps, key=lambda q: q.area))
        for extra in sorted(ps, key=lambda q: -q.area)[1:]:
            out.append(_dc.replace(r, polygon=extra))
    counts["apron_faces_cut"] = cut
    counts["apron_area_cut_m2"] = round(area_cut, 1)
    counts["pad_airside_weld_pairs"] = welds
    counts["pad_area_kept_m2"] = round(pad_u.area, 1)
    return [r for r in out if r is not None], pads_out, counts


def airside_clip(regions, law, air=None, nodes=None, rim=None) -> tuple[list, dict]:
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
    """
    counts: dict = {}
    pad_ix = [i for i, r in enumerate(regions) if is_rigid_role(law, r.role)]
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


def _node_coords(noded) -> list[tuple[float, float]]:
    """Every distinct coordinate of a noded line work — the arrangement's
    own node set, which is exactly the vertex set its polygonized faces
    can carry."""
    out: set[tuple[float, float]] = set()
    if noded is None or noded.is_empty:
        return []
    for g in getattr(noded, "geoms", (noded,)):
        cs = getattr(g, "coords", None)
        if cs is None:
            continue
        for x, y in cs:
            out.add((float(x), float(y)))
    return sorted(out)


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


def build_arrangement(airport: Airport, classification: Classification,
                      law: Law, grid_m: float | None = None) -> Arrangement:
    """Regions + breakline sources -> ONE noded arrangement."""
    grid = grid_m if grid_m is not None else \
        law.tables.emit.identity.min_distinct_spacing_m
    cells, weld = weld_cells(classification.cells, law)
    regions: list[Region] = []
    for c in cells:
        regions.append(Region(c.role, c.ref, Polygon(c.ring, c.holes),
                              c.code_number, c.code_letter, c.side, "cell"))
    # THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19): the zones
    # are clipped at their own derivation site, against the airport's DEM
    # and the tile's OSM road centrelines
    erep = EdgeReport()
    edge_lines: list[LineString] = []
    for z in zone_regions(cells, law, classification.keepouts,
                          getattr(airport, "dem", None),
                          road_lines(getattr(airport, "osm_ways", ())), erep):
        regions.append(Region("graded_strip", z.ref, z.polygon, z.code_number,
                              z.code_letter, role_side(law, "graded_strip"),
                              "zone", z.zone, z.edge_kind, z.quay))
        edge_lines.extend(z.edge_lines)

    # §16g (10) (12) (1) THE AIRSIDE CELLS ARE NODED BEFORE ANY PAD EXISTS
    # (Fable 2026-09-16; RULINGS 2026-09-16b), and this SPLIT of the line
    # set is the whole rule.  Until now every region ring — the pads' among
    # them — went into ONE ``unary_union(..., grid_size=grid)``, and
    # snap-rounding is a GLOBAL operation: adding or removing any line can
    # move an unrelated vertex by up to half a cell, and a pad ring
    # crossing an airside ring splits that ring's edges outright.  MEASURED
    # at HECA (``tools/pad_airside_arm.py``, the clip arm against the
    # shipped one, ONE variable): 1,008 airside vertices gone and 283
    # minted, 228 of the minted ones over 1 m from ANY airside vertex of
    # the other arm and the leading class a node the two arms hold 0.500 m
    # apart — the grid's own half cell.  So: pass A nodes everything the
    # airside is made of, pass B adds the pads to THAT result.  The
    # airside's vertex set is then a function of the airside alone, which
    # is what §16g (10) (5) "airside is king" means at the vertex.
    pad_ix = {i for i, r in enumerate(regions) if is_rigid_role(law, r.role)}
    base_regions = [r for i, r in enumerate(regions) if i not in pad_ix]
    pad_regions = [r for i, r in enumerate(regions) if i in pad_ix]
    # RULINGS 2026-09-23a: the pad keeps its footprint and the APRON is cut
    # back to the pad edge (``apron_cut_to_pads``) — BEFORE pass A, so the
    # airside pass A nodes is already the cut one and the pad's edge is
    # the rim's own coordinates.
    keeps = bool(getattr(law.tables.structures.placement,
                         "pad_keeps_footprint", False))
    if keeps:
        base_regions, pad_regions, _pad_clip = apron_cut_to_pads(
            base_regions, pad_regions, law, float(grid))

    def _ring_lines_of(rs) -> list[LineString]:
        out: list[LineString] = []
        for r in rs:
            cap = chord_cap_m(law, r.role)
            for ring in ring_lines(tuple(r.polygon.exterior.coords)[:-1],
                                   [tuple(h.coords)[:-1] for h in r.polygon.interiors],
                                   cap):
                if len(ring) >= 2:
                    out.append(LineString(ring))
        return out

    lines: list[LineString] = _ring_lines_of(base_regions)

    sources: list[SourceLine] = []
    spacing = law.tables.emit.chords.station_spacing_m
    cap_pav = law.tables.emit.chords.pavement_max_chord_m
    for rw in airport.runways:
        a, b = rw.ends
        (ax, ay), (bx, by) = a.xy, b.xy
        L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        if L < 1.0:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        p0 = (ax - ux * a.overrun_m, ay - uy * a.overrun_m)
        p1 = (bx + ux * b.overrun_m, by + uy * b.overrun_m)
        sources.append(SourceLine("runway_profile", rw.id,
                                  LineString(stations([p0, p1], spacing))))
    for cl in classification.cut_lines:
        if len(cl.points) >= 2:
            sources.append(SourceLine(cl.kind, cl.ref,
                                      LineString(densify(cl.points, cap_pav)),
                                      cl.code_letter))
    lines.extend(s.line for s in sources)
    bands = seam_bands(airport, regions, law.tables.emit.seam.half_width_m)
    lines.extend(LineString(b.exterior.coords) for b in bands)

    # PASS A — Node at full precision, snap the ONE result to the grid, then
    # node AGAIN under the grid's precision model: snap-rounding can create
    # new crossings between previously noded segments, and polygonize needs
    # a fully noded set.  NO PAD IS IN THIS SET.
    noded_a = shapely.unary_union(unary_union(lines), grid_size=grid)
    if noded_a.geom_type == "LineString":
        noded_a = MultiLineString([noded_a])

    # PASS B — the pads, clipped BY the airside cells pass A just fixed and
    # taking THEIR nodes (§16g (10) (12) (1)).  ``air`` is pass A's own
    # airside union put on the grid, so the pad's clipped boundary is the
    # airside's boundary coordinate for coordinate — the WELD of §16g (10)
    # (6), one coordinate one unknown — and the rim the crossing points
    # quantise to is the ARRANGEMENT's node set, not the region ring's
    # (which stands a full 60 m chord apart and is why 75 of HECA's
    # crossings had no node to reach).
    air = shapely.set_precision(airside_union(base_regions, law), grid)
    nodes_a = _node_coords(noded_a)
    rim = build_rim(air, law, nodes_a)
    if not keeps:
        pad_regions, _pad_clip = airside_clip(pad_regions, law, air=air,
                                              nodes=nodes_a, rim=rim)
    regions = base_regions + pad_regions
    # THE DENSIFIER MAY NOT NODE THE RIM EITHER.  A clipped pad's boundary
    # RUNS ALONG the airside boundary between its two crossing points, and
    # ``ring_lines`` densifies every ring at its role's chord cap — so the
    # `building` cap's own midpoints land ON airside edges the airside cap
    # spaced differently and SPLIT them.  A coordinate of a pad ring that
    # lies on the rim without being one of pass A's nodes is therefore
    # dropped: the straight run between two rim nodes IS the airside edge,
    # which is the weld (12) (1) asks for and nothing else.
    own_pad_coords = {(float(x), float(y)) for r in pad_regions
                      for ring in (r.polygon.exterior, *r.polygon.interiors)
                      for x, y in ring.coords}
    pad_lines, _dropped_mid = _drop_rim_midpoints(_ring_lines_of(pad_regions),
                                                  rim, set(nodes_a),
                                                  own_pad_coords,
                                                  float(grid) if keeps else 0.0)
    _pad_clip["rim_midpoints_dropped"] = _dropped_mid
    if pad_lines:
        noded = shapely.unary_union(
            unary_union([noded_a, *pad_lines]), grid_size=grid)
        if noded.geom_type == "LineString":
            noded = MultiLineString([noded])
    else:
        noded = noded_a
    # §16g (10) (12) (2) THE RE-NODE CENSUS, at the derivation site: the
    # nodes standing inside or on the airside union BEFORE the pads against
    # the ones standing there AFTER.  ``deleted`` and ``minted`` are both
    # the defect; the bar is 0.
    _pad_clip.update(_renode_counts(nodes_a, _node_coords(noded), air))
    PAD_AIRSIDE.clear()
    PAD_AIRSIDE.update(_pad_clip)
    polys = [g for g in shapely.get_parts(shapely.polygonize([noded]))
             if g.geom_type == "Polygon" and not g.is_empty]

    tree = STRtree([r.polygon for r in regions])
    faces: list[tuple[Polygon, Region]] = []
    dropped = 0
    dropped_seam = 0
    for poly in polys:
        if bands and any(b.contains(poly.representative_point()) for b in bands):
            dropped_seam += 1
            continue
        best: Region | None = None
        best_a = 0.0
        for j in tree.query(poly, predicate="intersects"):
            r = regions[int(j)]
            a = poly.intersection(r.polygon).area
            if a > best_a:
                best, best_a = r, a
        if best is None or best_a < 0.5 * poly.area:
            dropped += 1
            continue
        faces.append((poly, best))
    ident = law.tables.emit.identity.min_distinct_spacing_m
    faces, merged = merge_slivers(faces,
                                  (ident * law.tables.emit.terrace.sliver_area_factor) ** 2,
                                  law.tables.emit.identity.weld_spacing_m)
    # §41 (1): an enclosed pavement face is its host's hole — absorbed HERE,
    # at the single derivation site, so every consumer downstream reads one
    # body with one law (owner RULINGS 2026-08-30l: trim at the derivation
    # site, never per consumer)
    faces, absorbed, detached = absorb_enclosed_pavement(
        faces, tuple(law.tables.emit.terrace.shape_roles),
        mouth_m=law.tables.emit.terrace.narrow_mouth_max_m)
    # §41 (4): a sliver ZONE face is dissolved into the pavement it borders
    # HERE, before the host's hole is cut — the same single-derivation-site
    # discipline (owner RULINGS 2026-08-30l) the absorption above follows
    faces, zs_dissolved, zs_dropped, zs_area, zs_rows = dissolve_sliver_zones(
        faces, law.tables.emit.terrace.strip_min_m2,
        law.tables.emit.terrace.strip_min_width_m,
        tuple(law.tables.emit.terrace.shape_roles),
        tuple(r for r, spec in law.tables.precedence.roles.items()
              if spec.rigid))
    faces, holes_gone = dissolve_degenerate_holes(
        faces, law.tables.emit.terrace.separation_m, ident ** 2)
    return Arrangement(faces, noded, sources, regions, dropped, grid,
                       bands, dropped_seam, weld, merged,
                       tuple(edge_lines), erep, holes_gone,
                       absorbed, detached,
                       zs_dissolved, zs_dropped, zs_area, zs_rows)


def dissolve_degenerate_holes(faces: list[tuple[Polygon, Region]], sep_m: float,
                              area_min_m2: float
                              ) -> tuple[list[tuple[Polygon, Region]], int]:
    """THE DEGENERATE HOLE (RULINGS 2026-09-10h (1)): a face's interior ring
    that is NOWHERE as wide as ``terrace.separation_m`` — the width at which
    a gap is still one shape, so a hole under it is not a gap at all — or
    under ``area_min_m2`` (``identity.min_distinct_spacing_m²``, the smallest
    area two distinct vertices can bound) is DEGENERATE GEOMETRY, dissolved
    into its own face here.  It never becomes a vertex set.

    WHY, measured at LEMD (RULINGS 2026-09-10h): way −10892, a 35 m × 0.5 m,
    3-vertex hole in apron ``pav16``, emitted 16.3 m BELOW the apron it sits
    inside (582.7 against a DEM of 599.0) and coned to over 265 × 240 m of
    mesh — the owner's "large apron dip".  Such a ring's vertices bound no
    face law and no design target, and every triangle the face's
    triangulation gives them is obtuse enough that the cotangent Laplacian
    CLAMPS its weight (``solve/rows._cotangent_laplacian``): the columns
    reach the least-squares solve carrying no row at all, so their value is
    whatever the min-norm solution leaves there — which is why the same
    three vertices, at byte-identical coordinates, moved 7.6 m between two
    arms that changed nothing near them.

    A hole is dissolved only when NO kept face lies inside it: a real inner
    face (a pad, a trench floor) keeps its hole however thin the ring, and
    the two faces never overlap.  ``buffer(-sep/2)`` empty is the width
    test — the ring cannot hold a disc of diameter ``sep_m`` anywhere, i.e.
    it is nowhere as wide as the separation.  Returns the faces and the
    number of holes dissolved."""
    if not faces or (sep_m <= 0.0 and area_min_m2 <= 0.0):
        return faces, 0
    inner = STRtree([p for p, _r in faces])
    out: list[tuple[Polygon, Region]] = []
    gone = 0
    for i, (poly, region) in enumerate(faces):
        if not poly.interiors:
            out.append((poly, region))
            continue
        keep: list = []
        for h in poly.interiors:
            hp = Polygon(h)
            if not hp.is_valid:
                hp = hp.buffer(0)
            degenerate = (hp.is_empty or hp.area < area_min_m2
                          or (sep_m > 0.0 and hp.buffer(-0.5 * sep_m).is_empty))
            if degenerate and not _holds_a_face(hp, faces, inner, i):
                gone += 1
                continue
            keep.append(h)
        out.append((poly if len(keep) == len(poly.interiors)
                    else Polygon(poly.exterior, keep), region))
    return out, gone


def _holds_a_face(hole: Polygon, faces: list[tuple[Polygon, Region]],
                  tree: STRtree, self_i: int) -> bool:
    """A kept face other than ``faces[self_i]`` lies inside ``hole``."""
    if hole.is_empty:
        return False
    for j in tree.query(hole, predicate="intersects"):
        j = int(j)
        if j == self_i:
            continue
        if hole.contains(faces[j][0].representative_point()):
            return True
    return False


def merge_slivers(faces: list[tuple[Polygon, Region]], area_max: float,
                  width_max: float = 0.0
                  ) -> tuple[list[tuple[Polygon, Region]], int]:
    """THE SLIVER MERGE (RULINGS 2026-09-08d (4a); spec heca-v1-parity §4 /
    §6.3): a face under ``area_max`` (``(identity.min_distinct_spacing_m ×
    terrace.sliver_area_factor)²``) whose ring shares a boundary run with a
    face of the SAME region (same role, same ref — one cell the noding cut
    twice) is a classification artefact, never a cell of its own: it is
    unioned into that neighbour (the largest sharing one).  HECA pav131
    face 269 (3 nodes, 9.8 m², 47 m along face 215's edge) became a
    terrace joint of 6.2 m at the owner's site.  Returns the faces and
    the number merged.

    AREA ALONE DOES NOT READ A HAIRLINE (lane ``v2hecastep``, 2026-09-16;
    the §41 (4) lesson of RULINGS 2026-09-14g item 4 — "use the INSCRIBED
    circle" — applied to the same-region merge).  HECA's app-1.0.344
    ``runway_step`` DEFECT stood on face 37, a **0.50 m wide** strip of
    05C/23C **80.1 m** along face 14's own boundary, left where object
    pavement ``dsf:objpav100``'s ring runs a half metre inside the
    runway's: 20.7 m², which clears the 16 m² area gate, so the merge
    never looked at it and the solve gave its two long sides different
    levels (0.684 / 0.571 / 0.342 m apart — three of the four DEFECT
    rows).  ``width_max`` (the weld's own ``identity.weld_spacing_m``:
    the width below which two pavement boundaries ARE one boundary,
    RULINGS 2026-09-04u) merges such a face WHATEVER its area — it is
    the sliver the weld exists to prevent, read after the noding.  The
    inscribed circle is computed only for a face whose mean width
    (``2A/P``) is already under twice the bound, so the pass costs
    nothing on the faces that are not candidates."""
    if (area_max <= 0.0 and width_max <= 0.0) or len(faces) < 2:
        return faces, 0

    def _hairline(poly: Polygon) -> bool:
        if width_max <= 0.0:
            return False
        per = poly.length
        if per <= 0.0 or 2.0 * poly.area / per >= 2.0 * width_max:
            return False
        return inscribed_width_m(poly) < width_max

    polys = [p for p, _r in faces]
    tree = STRtree(polys)
    keep = list(faces)
    merged = 0
    for i, (poly, region) in enumerate(faces):
        if keep[i] is None or (poly.area >= area_max and not _hairline(poly)):
            continue
        best = None
        best_len = 0.0
        for j in tree.query(poly, predicate="intersects"):
            j = int(j)
            if j == i or keep[j] is None:
                continue
            pj, rj = keep[j]
            if rj.role != region.role or rj.ref != region.ref:
                continue
            shared = poly.boundary.intersection(pj.boundary).length
            if shared > best_len:
                best, best_len = j, shared
        if best is None or best_len <= 0.0:
            continue
        pj, rj = keep[best]
        u = pj.union(poly)
        if u.geom_type != "Polygon":
            u = max(shapely.get_parts(u), key=lambda g: g.area)
        keep[best] = (u, rj)
        keep[i] = None
        merged += 1
    return [f for f in keep if f is not None], merged


def inscribed_width_m(poly: Polygon, tol: float = 0.01) -> float:
    """THE WIDTH OF A FACE: twice the radius of its MAXIMUM INSCRIBED
    CIRCLE — the diameter of the largest disc the shape holds, i.e. how
    wide it is at its WIDEST place.

    Deliberately NOT ``2 A / P``, which is a mean-width proxy: a shape
    with one fat end and a long tail reads narrow under the proxy while
    holding a wide disc, and on the owner's 1.0.331 HECA patch the proxy
    called 153 zone faces narrower than 3 m where the inscribed circle
    calls 42 (RULINGS 2026-09-14g item 4 — "use the INSCRIBED circle")."""
    if poly is None or poly.is_empty or poly.area <= 0.0:
        return 0.0
    try:
        return 2.0 * float(shapely.maximum_inscribed_circle(poly, tol).length)
    except Exception:                                      # pragma: no cover
        return 0.0


def dissolve_sliver_zones(faces: list[tuple[Polygon, Region]],
                          area_min_m2: float, width_min_m: float,
                          host_roles: tuple[str, ...] = (),
                          refuse_roles: tuple[str, ...] = ()
                          ) -> tuple[list[tuple[Polygon, Region]], int, int,
                                     float, tuple]:
    """§41 (4) — A SLIVER ZONE STRIP IS DISSOLVED (owner RULINGS
    2026-09-14c item 4; attributed RULINGS 2026-09-14g item 4).

    An adjacent-ground ZONE face under ``area_min_m2`` or narrower than
    ``width_min_m`` at its widest place (:func:`inscribed_width_m`) has
    nowhere to put the transition it exists to carry: it takes whatever
    its own zone bound gives it and stands proud of the pavement all
    round it.  HECA shape 1035 — ``adjacent_ground:taxi:E:zone1#38``,
    15.7 m², 2.16 m wide, hole 0 of ``cross_connector:pav115`` at
    30.1110278, 31.4062316 — sat at 105.86-106.01 inside a taxiway at
    104.4: +1.3-1.6 m over 7 m, ≈ 23 %, the owner's hump.

    It is UNIONED INTO THE FACE IT BORDERS LONGEST — an aircraft-pavement
    face (``host_roles``) first, then any other cell, then a neighbouring
    zone face, never a RIGID one (``refuse_roles``: a building pad is one
    level for the body that stands on it, and 4.4 m² of adjacent ground
    welded onto its footprint is a pad the owner never authored) — HERE,
    at the single derivation site, so the host's hole is
    never cut, no consumer downstream ever sees the strip, and nothing has
    to veto it per-consumer (owner RULINGS 2026-08-30l).  A sliver that
    borders NOTHING (9 of HECA's 57 touch no face at all) has no host to
    dissolve into and is DROPPED, exactly as a face no region claims is
    dropped: the DEM owns it.

    Smallest-first, so a chain of slivers resolves into the body and never
    into each other.  Returns ``(faces, dissolved, dropped, area_m2,
    rows)``."""
    if (area_min_m2 <= 0.0 and width_min_m <= 0.0) or not faces:
        return faces, 0, 0, 0.0, ()
    tree = STRtree([p for p, _r in faces])
    keep: list[tuple[Polygon, Region] | None] = list(faces)
    hosts = set(host_roles)
    refused = set(refuse_roles)
    order = sorted((i for i, (_p, r) in enumerate(faces) if r.source == "zone"),
                   key=lambda i: faces[i][0].area)
    dissolved = dropped = 0
    area = 0.0
    rows: list[tuple] = []
    for i in order:
        if keep[i] is None:
            continue
        poly, region = keep[i]
        width = inscribed_width_m(poly)
        if poly.area >= area_min_m2 and width >= width_min_m:
            continue
        best = None
        best_rank = None
        for j in tree.query(poly, predicate="intersects"):
            j = int(j)
            if j == i or keep[j] is None:
                continue
            pj, rj = keep[j]
            if rj.role in refused:
                continue
            try:
                shared = poly.boundary.intersection(pj.boundary).length
            except Exception:                              # pragma: no cover
                continue
            if shared <= 0.0:
                continue
            tier = (0 if rj.role in hosts else
                    (1 if rj.source != "zone" else 2))
            rank = (tier, -shared)
            if best_rank is None or rank < best_rank:
                best, best_rank = j, rank
        area += poly.area
        if best is None:
            keep[i] = None
            dropped += 1
            rows.append((region.ref, round(poly.area, 1), round(width, 2), None))
            continue
        pj, rj = keep[best]
        u = pj.union(poly)
        if u.geom_type != "Polygon":
            u = max(shapely.get_parts(u), key=lambda g: g.area)
        keep[best] = (u, rj)
        keep[i] = None
        dissolved += 1
        rows.append((region.ref, round(poly.area, 1), round(width, 2),
                     f"{rj.role}:{rj.ref}"))
    return ([f for f in keep if f is not None], dissolved, dropped,
            round(area, 1), tuple(rows))


def absorb_enclosed_pavement(faces: list[tuple[Polygon, Region]],
                             roles: tuple[str, ...],
                             min_frac: float = ENCLOSED_MIN_FRAC,
                             mouth_m: float = 0.0
                             ) -> tuple[list[tuple[Polygon, Region]], int, int]:
    """§41 (1) — A PAVEMENT FACE INSIDE A PAVEMENT FACE IS A HOLE OF IT
    (owner RULINGS 2026-09-13co item 2; attributed RULINGS 2026-09-13cs
    item 2; spec §41).  A pavement face at least ``min_frac`` of whose own
    area lies inside another, LARGER pavement face's EXTERIOR RING is that
    face's hole: it contributes no rows of its own and the outer face's law
    governs every vertex in it.  A cross-connector inside a parallel is the
    parallel.  Implemented as an absorption into the host face, so there is
    one face, one role, one ref and one law — no boundary between them for
    a step to stand on.

    THE FRAME IS THE HOST'S EXTERIOR RING, NOT ITS SOLID, and that is the
    whole reading.  The enclosed face sits in a HOLE of the host (the
    arrangement is a partition: a face never overlaps another), so the
    hole-aware intersection of the two is 0 m² BY CONSTRUCTION and a
    solid-frame test finds nothing.  Measured on the owner's 1.0.329 HECA
    patch: 22 faces stand at ≥ 95 % inside another pavement face's ring,
    every one of them at 0.000 solid fraction; 21 of the 22 share that
    face's boundary.

    WHY IT IS A DEFECT (the owner's site 30.1312203, 31.3983896).
    ``cross_connector:pav77`` (895 m²) is a notch in ``primary_parallel:
    pav73``'s ring, pinned at 65.5 m while the parallel around it holds
    68–69.5 m: the parallel's OWN surface has to ramp 65.7 → 68.05 m over
    21 m — 11 % across a code-F taxiway against a 1.5 % cap — and the
    census sees no row, because each face is lawful on its own.

    TWO NARROWINGS, BOTH MEASURED, BOTH REPORTED.

    (a) A face that shares NO boundary run with its host is NOT absorbed —
    the union would be two disjoint pieces, which no face can be.  That is
    an island in the middle of a taxiway loop (HECA ``apron:pav5``,
    2,362 m², 12.97 m off ``cross_connector:pav67``'s solid), not a notch
    cut into a body; it is counted as ``enclosed_detached``.

    (b) A face whose contact with its host is no wider than ``mouth_m``
    (``emit.terrace.narrow_mouth_max_m``) is NOT absorbed: by the owner's
    OWN body law (RULINGS 2026-09-08k, ``planar/shapes.py``) "a neck
    narrower than the mouth … separates two bodies", and a step between
    two bodies is LAWFUL.  Absorbing across a narrow mouth outlaws a
    lawful terrace and the solve cannot deliver it.  MEASURED, and this is
    why the gate is here: at CYXY the ONE contained face is
    ``apron:pav21#204`` (528 m²) reached through a 9.31 m mouth, and
    absorbing it moved the control airport's ``airside_no_step`` from 39
    rows to 54 — 10 rows over 0.5 m to 26, worst 1.96 m — with the v1
    oracle unmoved at 39 (the flatness the merge demanded, which no solve
    could meet).  With the gate CYXY absorbs nothing.  HECA's
    ``cross_connector:pav77`` shares 103.54 m with ``primary_parallel:
    pav73`` and passes it by an order of magnitude.

    Smallest first, so a chain of nested notches folds into the outermost
    body.  Returns the faces, how many were absorbed and how many enclosed
    faces were refused for being detached."""
    if len(faces) < 2 or not roles:
        return faces, 0, 0
    role_set = set(roles)
    polys = [p for p, _r in faces]
    tree = STRtree(polys)
    keep: list[tuple[Polygon, Region] | None] = list(faces)
    #: union-find: which face each original index now lives in
    home = list(range(len(faces)))

    def root(i: int) -> int:
        while home[i] != i:
            home[i] = home[home[i]]
            i = home[i]
        return i

    absorbed = detached = 0
    for i in sorted(range(len(faces)), key=lambda k: polys[k].area):
        if keep[i] is None or faces[i][1].role not in role_set:
            continue
        poly = keep[i][0]
        if poly.area <= 0.0:
            continue
        best = None
        best_shared = 0.0
        saw_host = False
        # a BOUNDING-BOX query, not ``intersects``: the enclosed face lies
        # in the host's HOLE, so the two are disjoint as solids
        for j in tree.query(poly):
            j = root(int(j))
            if j == i or keep[j] is None:
                continue
            pj, rj = keep[j]
            if rj.role not in role_set or pj.area <= poly.area:
                continue
            try:
                inside = poly.intersection(Polygon(pj.exterior)).area
            except Exception:                             # pragma: no cover
                continue
            if inside < min_frac * poly.area:
                continue
            saw_host = True
            shared = poly.boundary.intersection(pj.boundary).length
            if shared <= float(mouth_m):
                continue        # a neck, not a notch: two bodies (08k)
            if shared > best_shared:
                best, best_shared = j, shared
        if best is None:
            detached += 1 if saw_host else 0
            continue
        pj, rj = keep[best]
        u = pj.union(poly)
        if u.geom_type != "Polygon":
            u = max(shapely.get_parts(u), key=lambda g: g.area)
        keep[best] = (u, rj)
        keep[i] = None
        home[i] = best
        absorbed += 1
    return [f for f in keep if f is not None], absorbed, detached


def _degree_offset(to_xy, lon: float, lat: float, along_lon: bool,
                   metres: float) -> float:
    """Degrees of ``lon`` (or ``lat``) that measure ``metres`` in the frame
    at ``(lat, lon)`` — the local scale, read from the frame's OWN forward
    transformer so the band is offset in the same map the patch is emitted
    in.  ``1.0`` degrees where the scale cannot be read (a degenerate
    frame): the caller then buffers as before."""
    eps = 1.0e-4
    x0, y0 = to_xy(lon, lat)
    x1, y1 = (to_xy(lon + eps, lat) if along_lon else to_xy(lon, lat + eps))
    d = math.hypot(x1 - x0, y1 - y0)
    return metres * eps / d if d > 1.0e-12 else 1.0


def seam_bands(airport: Airport, regions: list[Region], half_width_m: float
               ) -> list[Polygon]:
    """One band per integer latitude / longitude line crossing the
    regions' extent: the graticule line sampled every 25 m in the frame
    (a tmerc image of a parallel is not straight).

    THE BAND IS SYMMETRIC ABOUT THE GRATICULE LINE IN THE EMITTED FRAME
    (§38 (3)/13an (b); owner RULINGS 2026-09-13an).  Until 13an the band
    was ``LineString(pts).buffer(half_width_m)`` — a buffer of the tmerc
    IMAGE of the line, offset by ``half_width_m`` of frame metre.  Measured
    at SPLP that band's edges came back at **+5.0228 / −4.9754 m** of
    emitted longitude (centre 0.0237 m east, growing to 0.0287 m over
    1.1 km of latitude): the ``pyproj`` round trip is not the identity on
    the line itself.  The two 5.0 m bank collars then met at +0.0229 and
    +0.0245 m and left a ~1.6 mm HAIRLINE CRACK, the bank foot followed
    it, and Triangle4XP split that segment 16,298 times against the
    unsplittable tile border — the SPLP texture tear.

    So each edge is built as its OWN polyline, at the graticule value
    ± the DEGREES that measure ``half_width_m`` there
    (:func:`_degree_offset`), and the band is the polygon between them:
    the round trip carries both edges equally, so the emitted band is
    symmetric to the frame's own scale error rather than to none of it.
    """
    if not regions or half_width_m <= 0.0:
        return []
    to_xy, to_ll = airport.frame.transformers()
    xmin, ymin, xmax, ymax = unary_union([r.polygon for r in regions]).bounds
    margin = 2.0 * half_width_m
    xmin, ymin, xmax, ymax = xmin - margin, ymin - margin, xmax + margin, ymax + margin
    corners = [to_ll(x, y) for x in (xmin, xmax) for y in (ymin, ymax)]
    lat_lo, lat_hi = min(c[0] for c in corners), max(c[0] for c in corners)
    lon_lo, lon_hi = min(c[1] for c in corners), max(c[1] for c in corners)
    out: list[Polygon] = []
    n = max(2, int((max(xmax - xmin, ymax - ymin)) / 25.0) + 1)

    def _xy_at(lon: float, lat: float) -> tuple[float, float]:
        """The frame point that COMES BACK as ``(lat, lon)``.

        ``to_ll(to_xy(...))`` is not the identity — measured at SPLP the
        meridian round-trips 0.0237 m east, growing to 0.0287 m over 1.1 km
        of latitude (13an).  The band's edges are a statement about the
        EMITTED frame (the mesh's tile border sits at the exact graticule
        value), so they are specified there: one Newton step against the
        round trip, which the smoothness of the bias closes to well under a
        millimetre.
        """
        x, y = to_xy(lon, lat)
        la2, lo2 = to_ll(x, y)
        return to_xy(lon - (lo2 - lon), lat - (la2 - lat))

    def _band(pairs: list[tuple[float, float]], along_lon: bool) -> Polygon:
        """``pairs`` are the (lon, lat) samples ON the graticule line."""
        lo_side, hi_side = [], []
        for lon, lat in pairs:
            d = _degree_offset(to_xy, lon, lat, along_lon, half_width_m)
            if along_lon:
                lo_side.append(_xy_at(lon, lat - d))
                hi_side.append(_xy_at(lon, lat + d))
            else:
                lo_side.append(_xy_at(lon - d, lat))
                hi_side.append(_xy_at(lon + d, lat))
        return Polygon(lo_side + hi_side[::-1]).buffer(0)

    for L in range(math.ceil(lat_lo), math.floor(lat_hi) + 1):
        # a PARALLEL: the offset is in latitude
        out.append(_band([(lon_lo + (lon_hi - lon_lo) * k / (n - 1), float(L))
                          for k in range(n)], True))
    for L in range(math.ceil(lon_lo), math.floor(lon_hi) + 1):
        # a MERIDIAN: the offset is in longitude
        out.append(_band([(float(L), lat_lo + (lat_hi - lat_lo) * k / (n - 1))
                          for k in range(n)], False))
    return [b for b in out if not b.is_empty and b.geom_type == "Polygon"]
