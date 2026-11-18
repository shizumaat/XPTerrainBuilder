"""A DECK BUILT OF SEPARATE PLACED SPANS IS SEATED AS ONE CHAIN (#2144 P1,
spec ``sim-review/2144-spec.md`` §4 P1; owner 2026-11-17T18:47Z "keep
elevated rails and roads constructed of multiple pieces with a smooth deck
over sloping terrain"; 2026-11-17T19:08Z "any pack that draws object less
than 1km from the airport should be checked and modified if needed").

A pack may draw an elevated rail or road as a row of separate ``OBJECT``
placements, one span each, every span authored with its own height over
the author's ground (a city overlay's metro viaduct).  X-Plane seats each
on OUR mesh under its own origin, and where our ground differs from the
author's the deck steps at every joint.

THE PIECE (:func:`piece_of`).  An object whose static geometry is LONG
along its own z axis (at least :data:`ELONGATION` times its width) and
whose two END CROSS-SECTIONS (the vertices within :data:`EDGE_EPS_M` of its
least and greatest z) each span its full width: the edge's centre ``x``,
its ``z``, its width and its SOFFIT (the edge's lowest ``y``).  Read from
the geometry alone, never from a file name.

THE JOINT (:func:`joints`).  Two placed pieces join where an edge of one
meets an edge of the other in plan: gap along the axis at most
``gap_m`` (1.0), lateral offset at most ``lateral_m`` (0.5), headings
parallel within ``heading_deg`` (15, either direction) and equal widths
within ``width_m`` (0.2).  An edge that meets more than one edge (a
branch, two lines crossing) joins none.

THE CHAIN (:func:`solve`).  The connected component of joints keeps its
authored joint heights: one unknown zero per piece and each joint the
equality ``zero_i + soffit_i = zero_j + soffit_j``, solved by walking a
spanning tree; a cycle closing by more than ``cycle_m`` (0.05) cuts its
worst joint (listed).  Then ONE constant per chain: the median over its
pieces of (ground under the origin - the piece's relative zero), so a hole
under one piece cannot pull the chain; only an ELEVATED chain is seated
(its pieces' median soffit at least ``elevated_m`` over their zeros: a
track laid at grade keeps its drape); raised, where needed, until no
piece authored at or over its ground stands below it.

CO-ANCHORED.  A placement that is no piece whose origin lies within
``gap_m`` of a chain piece's origin (a pier, a pod at a joint) takes that
piece's zero, so its authored relation to the span holds.

WRITE.  Each seated placement becomes an ``OBJECT_MSL`` row at its solved
zero (``model.placement.MslSeat``; ``dsf_write`` writes it, the pristine
DSF kept as ``.anchor_bak``).  No OBJ is rewritten.  SCOPE: a chain with at
least one piece within ``scope_m`` (1 km) of an airport boundary is seated
WHOLE -- its pieces are read up to ``reach_m`` past the scope -- because a
chain cut at the scope line would step there (lane l2144 measured 0.33 ->
5.01 m at such a joint); a chain with no piece in the scope is not read.
"""
from __future__ import annotations

import dataclasses as _dc
import functools as _ft
import math
import typing as _t

import numpy as np

__all__ = ["ChainLaw", "piece_of", "Placed", "joints", "chain_seats",
           "ELONGATION", "EDGE_EPS_M", "WHY"]

#: a piece is at least this many times as long (z) as it is wide (x)
ELONGATION = 2.0
#: a vertex within this of the piece's least / greatest z is on its end edge
EDGE_EPS_M = 0.05
#: an end edge spans at least this share of the piece's width
EDGE_SPAN = 0.9
#: the MslSeat reason
WHY = "deck_chain"


@_dc.dataclass(frozen=True)
class ChainLaw:
    """The joint tolerances, the cycle bar, the scope."""

    gap_m: float = 1.0
    lateral_m: float = 0.5
    heading_deg: float = 15.0
    width_m: float = 0.2
    cycle_m: float = 0.05
    scope_m: float = 1000.0
    #: an ELEVATED chain: its pieces' median soffit at least this over
    #: their zeros (a track laid at grade drapes, piece by piece)
    elevated_m: float = 2.5
    #: a chain is read this far past the scope: a chain with ANY piece in
    #: the scope is seated WHOLE (cut at the scope line it would step there)
    reach_m: float = 6000.0


@_dc.dataclass(frozen=True)
class _Piece:
    """A deck piece's two end edges in its authored frame: ``(x, z, width,
    soffit)`` each, ``lo`` at its least z, ``hi`` at its greatest."""

    lo: tuple[float, float, float, float]
    hi: tuple[float, float, float, float]


def _edge(v: np.ndarray, at: float, width: float) -> "tuple[float, float, float, float] | None":
    e = v[np.abs(v[:, 2] - at) <= EDGE_EPS_M]
    if e.shape[0] < 2:
        return None
    w = float(e[:, 0].max() - e[:, 0].min())
    if w < EDGE_SPAN * width:
        return None
    return (float(e[:, 0].max() + e[:, 0].min()) / 2.0, float(at), w, float(e[:, 1].min()))


@_ft.lru_cache(maxsize=4096)
def piece_of(path: str) -> "_Piece | None":
    """The deck piece ``path`` draws (module doc), or None."""
    from . import obj8 as _obj8
    from .msl_feet import static_vertices
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError, IndexError):
        return None
    if g.animated.shape[0] and bool(np.any(g.animated)):
        return None
    v = static_vertices(g)
    if v is None or v.shape[0] < 4:
        return None
    width = float(v[:, 0].max() - v[:, 0].min())
    z0, z1 = float(v[:, 2].min()), float(v[:, 2].max())
    if width <= 0.0 or (z1 - z0) < ELONGATION * width:
        return None
    lo, hi = _edge(v, z0, width), _edge(v, z1, width)
    if lo is None or hi is None:
        return None
    return _Piece(lo, hi)


@_dc.dataclass(frozen=True)
class Placed:
    """One DSF row: its index, resource, origin, heading and (a piece's)
    two edges' world points ``(east, north)`` metres in the scope frame."""

    index: int
    resource: str
    lat: float
    lon: float
    heading: float
    xy: tuple[float, float]
    piece: "_Piece | None" = None


def _world(p: Placed, x: float, z: float) -> tuple[float, float]:
    """An authored ``(x, z)`` of ``p`` in the scope frame (OBJ8: x east, z
    south, rotated clockwise by the heading)."""
    h = math.radians(p.heading)
    s, c = math.sin(h), math.cos(h)
    return (p.xy[0] + x * c - z * s, p.xy[1] - (x * s + z * c))


def _edges(p: Placed) -> list[tuple[str, tuple[float, float], float, float]]:
    """``(which, world point, width, soffit)`` of a piece's two edges."""
    out = []
    for which, e in (("lo", p.piece.lo), ("hi", p.piece.hi)):
        out.append((which, _world(p, e[0], e[1]), e[2], e[3]))
    return out


def _axis(p: Placed) -> np.ndarray:
    h = math.radians(p.heading)
    return np.asarray([-math.sin(h), -math.cos(h)])        # authored +z, in plan


def joints(placed: _t.Sequence[Placed], law: ChainLaw) -> list[tuple]:
    """``(i, j, soffit_i, soffit_j)`` per joint (module doc), ``i < j``."""
    from scipy.spatial import cKDTree
    pts, own = [], []
    for k, p in enumerate(placed):
        if p.piece is None:
            continue
        for which, w, width, soffit in _edges(p):
            pts.append(w)
            own.append((k, which, width, soffit))
    if len(pts) < 2:
        return []
    tree = cKDTree(np.asarray(pts))
    reach = math.hypot(law.gap_m, law.lateral_m)
    found: dict[int, list[int]] = {}
    for a, b in tree.query_pairs(reach):
        ka, kb = own[a][0], own[b][0]
        if ka == kb or abs(own[a][2] - own[b][2]) > law.width_m:
            continue
        pa, pb = placed[ka], placed[kb]
        dh = abs((pa.heading - pb.heading + 90.0) % 180.0 - 90.0)
        if dh > law.heading_deg:
            continue
        d = np.asarray(pts[b]) - np.asarray(pts[a])
        ax = _axis(pa)
        lateral = abs(float(d[0] * ax[1] - d[1] * ax[0]))
        if abs(float(d @ ax)) > law.gap_m or lateral > law.lateral_m:
            continue
        found.setdefault(a, []).append(b)
        found.setdefault(b, []).append(a)
    out = []
    for a, bs in found.items():
        if len(bs) != 1 or len(found.get(bs[0], ())) != 1 or a > bs[0]:
            continue
        b = bs[0]
        (ka, _wa, _x, sa), (kb, _wb, _y, sb) = own[a], own[b]
        out.append((ka, kb, sa, sb) if ka < kb else (kb, ka, sb, sa))
    return out


def _solve(n: int, js: _t.Sequence[tuple], law: ChainLaw
          ) -> tuple[dict[int, tuple[int, float]], list[tuple]]:
    """``({piece: (chain id, relative zero)}, cut joints)``: each chain's
    pieces' zeros relative to its first piece, the joints keeping their
    authored heights; a joint whose cycle closes worse than ``cycle_m`` is
    cut and listed ``(i, j, misclosure)``."""
    adj: dict[int, list[tuple[int, float]]] = {}
    for i, j, si, sj in js:
        # zero_j = zero_i + soffit_i - soffit_j
        adj.setdefault(i, []).append((j, si - sj))
        adj.setdefault(j, []).append((i, sj - si))
    rel: dict[int, tuple[int, float]] = {}
    cut: list[tuple] = []
    for start in sorted(adj):
        if start in rel:
            continue
        rel[start] = (start, 0.0)
        stack = [start]
        while stack:
            u = stack.pop()
            for v, dz in adj[u]:
                want = rel[u][1] + dz
                if v not in rel:
                    rel[v] = (start, want)
                    stack.append(v)
                elif abs(rel[v][1] - want) > law.cycle_m and u < v:
                    cut.append((u, v, round(rel[v][1] - want, 3)))
    return rel, cut


def _soffit(p: Placed) -> float:
    """A piece's lower end-edge soffit over its own zero."""
    return min(p.piece.lo[3], p.piece.hi[3])


def chain_seats(placed: _t.Sequence[Placed], ground: _t.Callable[[float, float], "float | None"],
                law: ChainLaw, counts: "dict | None" = None,
                admit: "_t.Callable[[Placed], bool] | None" = None
                ) -> tuple[dict[int, float], dict]:
    """``({placed index: absolute zero}, report)``: every chain piece and
    co-anchored placement seated (module doc); with ``admit``, only the
    chains holding at least one admitted piece (seated whole)."""
    c = counts if counts is not None else {}
    js = joints(placed, law)
    rel, cut = _solve(len(placed), js, law)
    chains: dict[int, list[int]] = {}
    for k, (ch, _z) in rel.items():
        chains.setdefault(ch, []).append(k)
    zero: dict[int, float] = {}
    lifted = 0
    low = 0
    if admit is not None:
        chains = {ch: ks for ch, ks in chains.items() if any(admit(placed[k]) for k in ks)}
    for ch, ks in chains.items():
        if float(np.median([_soffit(placed[k]) for k in ks])) < law.elevated_m:
            low += 1
            continue
        g = {k: ground(placed[k].lat, placed[k].lon) for k in ks}
        offs = [g[k] - rel[k][1] for k in ks if g[k] is not None]
        if not offs:
            continue
        C = float(np.median(offs))
        # no piece whose soffit the author put at or over its ground has
        # its soffit below the ground at its origin
        need = [g[k] - rel[k][1] - _soffit(placed[k]) for k in ks
                if g[k] is not None and _soffit(placed[k]) >= 0.0]
        floor = max(need) if need else C
        if floor > C + 1e-6:
            lifted += 1
            C = floor
        for k in ks:
            zero[k] = C + rel[k][1]
    # co-anchored placements take the zero of the piece at their origin
    from scipy.spatial import cKDTree
    keys = sorted(zero)
    co = 0
    if keys:
        tree = cKDTree(np.asarray([placed[k].xy for k in keys]))
        for k, p in enumerate(placed):
            if k in zero or p.piece is not None:
                continue
            d, i = tree.query(p.xy)
            if d <= law.gap_m:
                zero[k] = zero[keys[int(i)]]
                co += 1
    seated = {k for ks in chains.values() for k in ks}
    c["chain_joints"] = c.get("chain_joints", 0) + sum(1 for j in js if j[0] in seated)
    c["chain_chains"] = c.get("chain_chains", 0) + len(chains)
    c["chain_pieces"] = c.get("chain_pieces", 0) + sum(len(ks) for ks in chains.values())
    c["chain_coanchored"] = c.get("chain_coanchored", 0) + co
    c["chain_cut_joints"] = c.get("chain_cut_joints", 0) + len(cut)
    c["chain_lifted"] = c.get("chain_lifted", 0) + lifted
    c["chain_at_grade"] = c.get("chain_at_grade", 0) + low
    return zero, {"joints": js, "cut": cut, "chains": chains, "rel": rel}
