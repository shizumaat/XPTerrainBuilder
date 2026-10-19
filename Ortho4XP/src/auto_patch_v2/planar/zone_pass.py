"""THE ZONES JOIN THE NODED AIRSIDE (issue #770; *airside is king*,
RULINGS 2026-10-15h (2)).

Until #770 the adjacent-ground zone rings were noded in the SAME pass as
the airside cells, so a zone line meeting a pavement edge split that edge
at a point that existed only because of the zone, and snap-rounding (a
GLOBAL operation) moved airside nodes near any changed zone line.
Measured on a CYXY capture: a 5 m runway / taxi zone-width change gave
the airside vertex set 71 gone and 70 new.

The rule is the pads' own (§16g (10) (12) (1)): pass A0 nodes everything
the airside is made of — the cells, the breakline sources, the seam
bands — and the zones join THAT result here:

* each zone is clipped by the airside union and its crossing points
  quantised to pass A0's rim NODES (``pad_cut.airside_clip``, the pads'
  clip and rim snap — the zone yields, the airside never does);
* a densifier point standing on the rim that is not an A0 node is
  dropped (``pad_cut._drop_rim_midpoints``) — the straight run between
  two rim nodes IS the airside edge;
* the zones' lines are noded onto A0, and every node the noding mints
  inside a hot pixel of the rim is reported (``zone_rim_mints_left``),
  with the re-node census of ``pad_cut._renode_counts`` read against A0.

The twin: a zone-width change moves 0 airside vertices
(``tests/auto_patch_v2/test_zone_pass.py``).
"""
from __future__ import annotations

import shapely
import numpy as np
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .pad_cut import _renode_counts

__all__ = ["join_zones"]

def _node_set(noded) -> set:
    out: set = set()
    for g in getattr(noded, "geoms", (noded,)):
        for x, y in getattr(g, "coords", ()):
            out.add((float(x), float(y)))
    return out


def _rim_nodes(nodes_a0: set, rim_line, tol: float) -> list:
    """The A0 nodes standing ON the airside rim (within ``tol``)."""
    cs = sorted(nodes_a0)
    if not cs:
        return []
    near = shapely.dwithin(rim_line, shapely.points(np.asarray(cs, dtype=float)), tol)
    return [c for c, k in zip(cs, near) if bool(k)]


def _off_rim_runs(line, keep_out, tree, node_pts, hops: list) -> list:
    """One zone ring line -> its RUNS outside ``keep_out`` (the airside
    and its pads, grown by the rim band), each end the cut made joined to
    the rim node nearest it.  The stretch along or inside the rim is
    dropped: the line work there is the airside's own, so the zone face
    closes on the airside's edge and never re-nodes it."""
    if not line.intersects(keep_out):
        return [list(line.coords)]
    out = []
    ends = {tuple(line.coords[0]), tuple(line.coords[-1])}
    for part in shapely.get_parts(line.difference(keep_out)):
        if part.geom_type != "LineString" or part.is_empty:
            continue
        cs = [tuple(c) for c in part.coords]
        for k in (0, -1):
            c = cs[k]
            if c in ends:
                continue
            node = node_pts[int(tree.nearest(shapely.Point(c)))]
            hops.append(((node[0] - c[0]) ** 2 + (node[1] - c[1]) ** 2) ** 0.5)
            if k == 0:
                cs.insert(0, node)
            else:
                cs.append(node)
        if len(cs) >= 2:
            out.append(cs)
    return out


def join_zones(noded_a0, zones: list, air, law, grid: float,
               ring_lines_of) -> tuple:
    """``zones`` (the ``source == "zone"`` regions) noded onto ``noded_a0``
    (pass A0, the airside alone) without adding or moving an A0 node on
    the airside rim.  Returns ``(noded, counts)``: the noded line work and
    the census.  The zone REGIONS are not changed — a face is claimed by
    its overlap, and the zone's faces close on the rim A0 drew."""
    counts: dict = {}
    if not zones:
        return noded_a0, counts
    nodes_a0 = _node_set(noded_a0)
    lines = [list(ln.coords) for ln in ring_lines_of(zones)]
    if air is not None and not air.is_empty:
        rim_line = shapely.set_precision(air, 0.0).boundary
        band = float(law.tables.emit.identity.weld_spacing_m)
        rim_nodes = _rim_nodes(nodes_a0, rim_line, 0.75 * grid)
        if rim_nodes:
            keep_out = shapely.set_precision(air, 0.0).buffer(band, join_style="mitre")
            shapely.prepare(keep_out)
            tree = STRtree([shapely.Point(c) for c in rim_nodes])
            hops: list = []
            runs = [r for ln in ring_lines_of(zones)
                    for r in _off_rim_runs(ln, keep_out, tree, rim_nodes, hops)]
            counts["zone_rim_runs"] = len(runs)
            # how far a zone's edge yields along the rim to reach a node
            counts["zone_rim_hop_max_m"] = round(max(hops, default=0.0), 2)
            counts["zone_rim_hops_over_5m"] = sum(1 for h in hops if h > 5.0)
            lines = runs
    noded = shapely.unary_union(
        unary_union([noded_a0, *(LineString(cs) for cs in lines)]), grid_size=grid)
    if noded.geom_type == "LineString":
        noded = MultiLineString([noded])
    if air is not None and not air.is_empty:
        after = _node_set(noded)
        counts.update({f"zone_{k}": v for k, v in _renode_counts(
            sorted(nodes_a0), sorted(after), air).items() if not k.endswith("_xy")})
    return noded, counts
