"""THE REACH TERRITORIES INSIDE A CELL (RULINGS 2026-09-07c, answering
07a-1 and 06r-1; spec ``docs/specs/auto-patch-v2/apron-reach-territory-
spec.md``; ``emit.toml [terrace]`` ``min_step_m`` / ``continue_roles`` /
``simplify_factor``).

THE LAW (owner): "for any given point on an apron, its route to runways
must be a visible path (cannot exit the apron shape) to a taxi route,
then along taxi centerlines only" — no shortcuts across aprons; two
aprons no route joins are separate and step.  06n partitioned BETWEEN
cells; HECA #364 (07a) is ONE cell touching two routes whose contacts
disagree by 43 m (81.9 / 125.2) 472 m apart in-shape — its own 1.5 %
surface bridged the 2,725 m route between them and dragged the 05C/23C
hold.  The partition must run INSIDE a cell, and the joint must cut
every face that spans it.

THE PARTITION.  A CONTACT is a reached taxi-centreline station (a
``taxi_centerline`` breakline vertex with a route band) on the cell's
cycles — the 06n "joined by a taxi route" vertices; a route THROUGH a
cell splits it in the arrangement, so its stations are cycle vertices
too.  Every cycle vertex belongs to the TERRITORY of its NEAREST
contact along the IN-SHAPE path (07c(2)) — the shortest path in the
cell's visibility graph (cycle vertices thinned to ``simplify_factor``
x the identity spacing, contacts kept; an edge where the face covers
the chord, ``geometry.face_cover``, plus the arc between cycle
neighbours).  Two ADJACENT territories (cycle neighbours, or a visible
chord between them) are ONE TERRACE when their contacts' route
CEILINGS agree within what the cell's max cap holds along the in-shape
path between the contacts (``|ceil₁ − ceil₂| ≤ cap_max · d_inshape +
min_step_m``); otherwise they are separate terraces and the boundary
between them is a JOINT.  The spec's literal budget metric (``cap · d +
budget_from_contact`` as the territory rule) was measured 2026-09-07 to
mint NO joint anywhere at HECA: at #364 the south contact owns the north
contact itself (81.67 + 0.015 × 541 = 89.8 < 125.16) — that metric IS
the shortcut — so the metric serves the joint predicate only.

THE CONTINUATION (07c(3)).  Cells are processed largest first; a vertex
a cut cell labelled is a SEED in every cell sharing it (label + its in-
shape ceiling), so the partition and the joint continue through the
neighbouring junction bodies and apron pieces along one line.  A face of
``continue_roles`` (the road family) whose ring carries two terrace
labels is cut by the same construction (labels propagated from the
nearest labelled vertex): each piece prices its own rows and ramps at
its own cap from the joint.  A pad is rigid — it belongs to one terrace
(06n majority) and the other piece retreats from it.  A taxi face is
never cut (it carries a route: a route across a joint contradicts the
joint; a dead-end lane straddling a cut is reported and stays welded).

THE CUT — construction (a) of the spec: a planar face has no interior
vertex or edge for (b) to follow, so the cell is CUT along the in-shape
shortest path between the two ring vertices where the terrace label
changes (the straight chord where the face covers it; the visibility
geodesic otherwise, whose bends are EXISTING cycle vertices — no new
vertex is ever made).  ``shapely.ops.split`` makes the pieces; every
piece must be a valid polygon carrying ONE label (the cut vertices
aside) or the cut is refused and reported.  A cut whose line enters the
runway-strip keep-out (06n ``strip_keepout``) is refused: the
territories MERGE there.  A cycle other than the ring carrying a label
change (a hole straddling the joint) refuses the cell's cut.  The pieces
then fall to 06n's ``split_terraces`` unchanged: two apron-like faces
sharing a boundary with no station on it are two groups, their boundary
a joint, the junior ring retreated ``joint_gap_m``, the joint declared
in the sidecar — the pieces of a cut face are joint sides whatever their
role (``cut_faces``).

Runs AFTER the planar build and the route graph (the dependency law
lets ``planar`` import law / model / airport / classify only, so the
pipeline hands the route bands in as data: ``constraints.no_step.
reach_band_values``).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import split as _split

from ..classify.evidence import polygon_from
from ..classify.roles import Classification
from ..law import Law
from ..law.tables import is_rigid_role, is_structure_role, role_cap, snap_margin_m
from ..model.airport import Airport
from ..model.frame import XY
from ..model.planar import Face, PlanarError, PlanarMap, validate
from .terraces import (STATION_KIND, TerraceStats, _face_cycles, reassemble,
                       split_terraces, strip_keepout)

__all__ = ["TerritoryStats", "terrace_territories"]

Band = tuple[float, float]
#: Coordinate match tolerance for the pieces' vertices (plan metres): a
#: split never computes a new point (every path vertex is a cycle vertex),
#: so this only absorbs GEOS's float round trip.  Never a law value.
COORD_TOL = 1e-6
#: Relative area a set of pieces may lose against the face (a degenerate
#: sliver refuses the cut).  Never a law value.
AREA_TOL = 1e-6
#: How many ring positions a cut end may move from the label change to
#: find a vertex with clearance (``_cut_end``).  Never a law value.
END_REACH = 8
#: How many rounds a face is cut (a piece keeping a lesser incompatible
#: pair is cut again) — the attempt cap of owner 2026-08-02, never a law value.
MAX_CUT_ROUNDS = 1


@_dc.dataclass
class TerritoryStats:
    """What the partition found and what the cut did (one line in the build log)."""

    cells: int = 0                 # apron-like cells in the partition
    contacts: int = 0              # reached contacts over those cells
    territories: int = 0           # territories (contacts owning a vertex)
    joint_pairs: int = 0           # adjacent territory pairs that disagree
    cut_cells: int = 0             # apron-like cells cut
    cut_continue: int = 0          # continue-role faces cut
    pieces: int = 0                # faces after the cut that came from a cut face
    cut_length_m: float = 0.0
    cut_by_role: dict[str, int] = _dc.field(default_factory=dict)
    refused_strip: int = 0         # a cut line entering the runway-strip keep-out (territories merge)
    refused_hole: int = 0          # a hole cycle carrying a label change
    refused_geometry: int = 0      # no valid monochromatic pairing / a piece invalid
    refused_map: int = 0           # the re-assembled map failed validation (whole pass refused)
    refused_why: dict[str, int] = _dc.field(default_factory=dict)   # geometry refusals by cause
    residual_pairs: int = 0        # disagreeing contact pairs NOT cut (a lesser pair of a complex — owed)
    seams: int = 0                 # one seam per pavement complex with a disagreeing pair
    seam_pairs: list[list] = _dc.field(default_factory=list)   # [a*, b*, ceiling a, ceiling b, gap − hold] per seam
    welded_breakline: int = 0      # cut vertices on a breakline (the step tapers there)
    welded_cut_vertices: int = 0   # cut path vertices the 06n split left SHARED (a leak: reported)
    cut_vertices: int = 0          # cut path vertices in all
    straddling_uncut: dict[str, int] = _dc.field(default_factory=dict)   # role -> faces touching two terraces that are not cut
    joints: list[list] = _dc.field(default_factory=list)   # [c1, c2, gap m, d_inshape m, hold m] — contact pairs whose territories are separate terraces
    cuts: list[list] = _dc.field(default_factory=list)     # [face, role, path vertices, length m]
    cells_trace: list[list] = _dc.field(default_factory=list)   # [face, role, contacts on it, vertices, territories on it, severest incompatible pair, cut?]
    wall_partition_s: float = 0.0
    wall_cut_s: float = 0.0
    terraces_split: TerraceStats = _dc.field(default_factory=TerraceStats)


@_dc.dataclass
class _Cell:
    fid: int
    verts: list[int]                       # cycle vertices, ring first
    cycles: list[list[int]]
    idx: dict[int, int]
    P: np.ndarray
    cover: _t.Any                          # the face grown by the snap tolerance (the partition's chords)
    exact: _t.Any                          # the face itself (a cut chord must lie inside it exactly)


class _Labels:
    """The global territories: every labelled vertex's contact (its
    territory id), its in-shape ceiling, and the JOINT PAIRS — the
    adjacent territory pairs whose contacts disagree.  Agreement is
    PAIRWISE, never transitive: along a route every neighbouring pair
    of contacts agrees, so a union-find would chain the north contact to
    the south one and lose the joint (measured HECA 2026-09-07)."""

    def __init__(self) -> None:
        self.of: dict[int, int] = {}
        self.ceil: dict[int, float] = {}
        self.joint: set[tuple[int, int]] = set()
        self.severity: dict[tuple[int, int], float] = {}   # joint pair -> gap − hold (m)
        self.dist: dict[tuple[int, int], float] = {}       # contact pair -> in-shape distance (within reach)

    def label(self, v: int) -> int | None:
        return self.of.get(v)

    def is_joint(self, a: int | None, b: int | None) -> bool:
        return a is not None and b is not None and a != b and \
            (min(a, b), max(a, b)) in self.joint


def _cell_geometry(pm: PlanarMap, fid: int, xy: dict[int, XY], tol: float) -> _Cell | None:
    cycles = _face_cycles(pm, fid)
    if not cycles or len(cycles[0]) < 3:
        return None
    verts = [v for c in cycles for v in c]
    # the face polygon a chord must stay inside, grown by the snap
    # tolerance so a chord along the boundary reads inside (the 05ae
    # cover the apron chords use, ``constraints.geometry.face_cover`` —
    # restated here because ``planar`` may not import ``constraints``)
    poly = polygon_from([xy[v] for v in cycles[0]], [[xy[v] for v in c] for c in cycles[1:]])
    if poly is None:
        return None
    cover = poly.buffer(tol)
    if cover.is_empty:
        return None
    shapely.prepare(cover)
    shapely.prepare(poly)
    return _Cell(fid, verts, cycles, {v: i for i, v in enumerate(verts)},
                 np.array([xy[v] for v in verts], float), cover, poly)


def _visible(cell: _Cell, ia: np.ndarray, ib: np.ndarray, exact: bool = False) -> np.ndarray:
    """Which index pairs the face covers (one vectorised GEOS predicate);
    ``exact`` against the face itself (a cut chord: the grown cover let a
    chord graze a concave boundary and mint a new intersection point —
    measured HECA #51 2026-09-07)."""
    if len(ia) == 0:
        return np.zeros(0, bool)
    segs = np.stack([cell.P[ia], cell.P[ib]], axis=1)
    return np.asarray(shapely.covered_by(shapely.linestrings(segs),
                                         cell.exact if exact else cell.cover), bool)


def _thin(cell: _Cell, must: set[int], spacing: float) -> list[int]:
    """Cycle vertex indices kept for the visibility graph: every ``must``
    index, and along each cycle one vertex per ``spacing`` metres of arc."""
    keep: list[int] = []
    for cyc in cell.cycles:
        acc = spacing
        m = len(cyc)
        for n, v in enumerate(cyc):
            i = cell.idx[v]
            if i in must or acc >= spacing:
                keep.append(i)
                acc = 0.0
            acc += math.dist(cell.P[i], cell.P[cell.idx[cyc[(n + 1) % m]]])
    return sorted(set(keep))


def _graph(cell: _Cell, keep: list[int]) -> tuple[csr_matrix, np.ndarray, np.ndarray]:
    """The in-shape graph over ``keep`` (indices into ``cell.verts``):
    visible chords at their length plus the arc between cycle
    neighbours; ``(matrix over len(cell.verts) ids, I, J)`` of the
    visible pairs."""
    k = np.array(keep, np.int64)
    I, J = np.triu_indices(len(k), 1)
    I, J = k[I], k[J]
    if len(I):
        ok = _visible(cell, I, J)
        I, J = I[ok], J[ok]
    L = np.hypot(cell.P[I, 0] - cell.P[J, 0], cell.P[I, 1] - cell.P[J, 1])
    # the arc between consecutive kept vertices on each cycle
    A: list[int] = []
    B: list[int] = []
    W: list[float] = []
    ks = set(keep)
    for cyc in cell.cycles:
        kept = [cell.idx[v] for v in cyc if cell.idx[v] in ks]
        if len(kept) < 2:
            continue
        pos = {cell.idx[v]: n for n, v in enumerate(cyc)}
        m = len(cyc)
        for a, b in zip(kept, kept[1:] + kept[:1]):
            s = 0.0
            n = pos[a]
            while n != pos[b]:
                s += math.dist(cell.P[cell.idx[cyc[n]]], cell.P[cell.idx[cyc[(n + 1) % m]]])
                n = (n + 1) % m
            A.append(a); B.append(b); W.append(s)
    rows = np.concatenate([I, J, np.array(A, np.int64), np.array(B, np.int64)])
    cols = np.concatenate([J, I, np.array(B, np.int64), np.array(A, np.int64)])
    w = np.concatenate([L, L, np.array(W), np.array(W)])
    n = len(cell.verts)
    m_ = csr_matrix((w, (rows, cols)), shape=(n, n))
    m_.sum_duplicates()
    return m_, I, J


def _geodesic(cell: _Cell, keep: list[int], a: int, b: int,
              avoid: _t.Container[int] = frozenset()) -> list[int] | None:
    """The in-shape shortest path (indices) from ``a`` to ``b`` over the
    visible chords among ``keep`` ∪ {a, b} — never along the boundary
    arcs (a cut along a ring edge is no cut), never bending at an
    ``avoid`` vertex (a station: a cut through a route station would
    join the pieces by that route; a breakline / seam vertex stays
    shared and would weld the cut)."""
    ks = sorted((set(keep) - set(avoid)) | {a, b})
    k = np.array(ks, np.int64)
    I, J = np.triu_indices(len(k), 1)
    I, J = k[I], k[J]
    ok = _visible(cell, I, J, exact=True)
    I, J = I[ok], J[ok]
    L = np.hypot(cell.P[I, 0] - cell.P[J, 0], cell.P[I, 1] - cell.P[J, 1])
    n = len(cell.verts)
    m = csr_matrix((np.concatenate([L, L]), (np.concatenate([I, J]), np.concatenate([J, I]))),
                   shape=(n, n))
    D, Pd = dijkstra(m, directed=False, indices=[a], return_predecessors=True)
    if not np.isfinite(D[0][b]):
        return None
    path = [b]
    while path[-1] != a:
        path.append(int(Pd[0][path[-1]]))
    return path[::-1]


def _pieces(cell: _Cell, xy: dict[int, XY], paths: list[list[int]], tol: float
            ) -> list[list[list[int]]] | None:
    """Cut the face polygon along every path (vertex ids); the pieces as
    ``[ring, *holes]`` vertex-id cycles, or ``None`` when a piece is
    invalid, a coordinate no longer matches a vertex, or area was lost.
    A geodesic hugging a concave boundary cuts SLIVERS between its
    chords and the arcs: they stay (each is one territory's face and
    the chord is its joint) and are counted in the report."""
    poly = Polygon([xy[v] for v in cell.cycles[0]],
                   [[xy[v] for v in c] for c in cell.cycles[1:] if len(c) >= 3])
    if not poly.is_valid or poly.area <= 0.0:
        return None
    pieces = [poly]
    for path in paths:
        line = LineString([xy[v] for v in path])
        nxt = []
        for pc in pieces:
            if pc.buffer(tol).covers(line) and line.length > 0.0:
                parts = [g for g in _split(pc, line).geoms if g.geom_type == "Polygon"]
                if len(parts) < 2:
                    return None
                nxt.extend(parts)
            else:
                nxt.append(pc)
        pieces = nxt
    if len(pieces) < 2:
        return None
    if abs(sum(p.area for p in pieces) - poly.area) > AREA_TOL * poly.area:
        return None
    id_of = {tuple(xy[v]): v for v in cell.verts}
    def ids(coords) -> list[int] | None:
        out: list[int] = []
        for x, y in list(coords)[:-1]:
            v = id_of.get((x, y))
            if v is None:
                near = [w for w in cell.verts if abs(xy[w][0] - x) <= COORD_TOL
                        and abs(xy[w][1] - y) <= COORD_TOL]
                if len(near) != 1:
                    return None
                v = near[0]
            if out and out[-1] == v:
                continue
            out.append(v)
        if len(out) > 1 and out[0] == out[-1]:
            out.pop()
        return out if len(out) >= 3 else None

    out: list[list[list[int]]] = []
    for pc in pieces:
        if not pc.is_valid or pc.area <= 0.0:
            return None
        pc = orient(pc, sign=1.0)
        ring = ids(pc.exterior.coords)
        if ring is None:
            return None
        holes = []
        for h in pc.interiors:
            hv = ids(h.coords)
            if hv is None:
                return None
            holes.append(hv)
        out.append([ring, *holes])
    return out


def _monochrome(pieces: list[list[list[int]]], label: dict[int, int | None],
                cut: set[int], labels: _Labels) -> bool:
    """No piece carries both sides of a joint pair (the cut vertices aside)."""
    for cycs in pieces:
        labs = sorted({label.get(v) for c in cycs for v in c if v not in cut} - {None})
        for i, a in enumerate(labs):
            for b in labs[i + 1:]:
                if labels.is_joint(a, b):
                    return False
    return True


def _cut_end(ring: list[int], n: int, inward: int, blocked: set[int], xy: dict[int, XY],
             clearance: float, reach: int) -> int:
    """The ring position a label change at ``n`` is cut at: the first
    vertex from ``n`` walking ``inward`` that is not blocked (a
    breakline / seam / structure vertex stays shared and would weld the
    cut end) and whose two ring edges both exceed ``clearance`` (the
    retreated copy of the junior side must clear the identity spacing of
    the ring neighbours — measured HECA 2026-09-07: on the 0.5 m arcs
    every end copy was refused and the cut ends welded); ``n`` itself
    when none qualifies within ``reach`` (the split then reports the
    weld).  The vertices skipped join the other side's run — a few
    metres of pavement beside the wall, never a law value."""
    m = len(ring)
    for d in range(reach + 1):
        k = (n + inward * d) % m
        v = ring[k]
        if v in blocked:
            continue
        prev, nxt = ring[(k - 1) % m], ring[(k + 1) % m]
        if math.dist(xy[v], xy[prev]) >= clearance and math.dist(xy[v], xy[nxt]) >= clearance:
            return k
    return n


def _severest(terrs: _t.Iterable[int], labels: _Labels) -> tuple[int, int] | None:
    """The most severe joint pair among ``terrs`` (largest gap over hold)."""
    ts = sorted(set(terrs))
    best = None
    for i, a in enumerate(ts):
        for b in ts[i + 1:]:
            sev = labels.severity.get((a, b))
            if sev is not None and (best is None or sev > best[0]):
                best = (sev, a, b)
    return None if best is None else (best[1], best[2])


def _sides(terrs: _t.Iterable[int], a: int, b: int, labels: _Labels,
           cxy: dict[int, XY]) -> dict[int, int]:
    """Every territory to the side of contact ``a`` (0) or ``b`` (1): the
    nearer by in-shape distance; by compatibility when one side is out
    of reach; by the plan chord when both are."""
    out: dict[int, int] = {}
    for t in set(terrs):
        if t == a:
            out[t] = 0
            continue
        if t == b:
            out[t] = 1
            continue
        da, db = labels.dist.get((min(a, t), max(a, t))), labels.dist.get((min(b, t), max(b, t)))
        if da is not None and db is not None:
            out[t] = 0 if da <= db else 1
        elif da is not None or db is not None:
            ja, jb = labels.is_joint(a, t), labels.is_joint(b, t)
            out[t] = 0 if (da is not None and not ja) or jb else 1
        else:
            out[t] = 0 if math.dist(cxy[t], cxy[a]) <= math.dist(cxy[t], cxy[b]) else 1
    return out


def _bichrome(pieces: list[list[list[int]]], side: dict[int, int], cut: set[int]) -> bool:
    for cycs in pieces:
        if len({side[v] for c in cycs for v in c if v not in cut and v in side}) > 1:
            return False
    return True


def _plan_cut(cell: _Cell, xy: dict[int, XY], keep: list[int], label: dict[int, int | None],
              labels: _Labels, blocked: set[int], keepout, tol: float, stats: TerritoryStats,
              clearance: float, reach: int, cxy: dict[int, XY]
              ) -> tuple[list[list[list[int]]], list[list[int]]] | None:
    """ONE cut of a cell: its most severe incompatible territory pair
    (a*, b*) on the ring; every ring territory takes the side of the
    nearer contact (bichromatic); the ring's label changes are paired
    (two pairings, the valid one with the shorter cut) and each pair is
    cut by the in-shape geodesic between its ends.  ``None`` (refusal
    counted) or ``(pieces, paths)``; a piece may still carry a lesser
    incompatible pair — the caller recurses."""
    ring = cell.cycles[0]
    for c in cell.cycles[1:]:
        for u, w in zip(c, c[1:] + c[:1]):
            if labels.is_joint(label.get(u), label.get(w)):
                stats.refused_hole += 1
                return None
    pair = _severest([t for v in cell.verts if (t := label.get(v)) is not None], labels)
    if pair is None:
        return None
    side_of = _sides([t for v in cell.verts if (t := label.get(v)) is not None], *pair, labels, cxy)
    side = {v: side_of[label[v]] for v in cell.verts if label.get(v) is not None}
    m = len(ring)
    ch = [n for n in range(m) if side.get(ring[n]) is not None and side.get(ring[(n + 1) % m]) is not None
          and side[ring[n]] != side[ring[(n + 1) % m]]]
    if not ch or len(ch) % 2:
        stats.refused_geometry += 1
        stats.refused_why["ends"] = stats.refused_why.get("ends", 0) + 1
        return None
    # each change at position n (between ring[n] and ring[n+1]) is cut at
    # a vertex INTO the run that starts at n+1 (or back into the run ending at n)
    cuts: list[int] = []
    side = dict(side)
    for n in ch:
        k = _cut_end(ring, (n + 1) % m, +1, blocked, xy, clearance, reach)
        for j in range((n + 1) % m, k) if k >= (n + 1) % m else list(range((n + 1) % m, m)) + list(range(0, k)):
            side[ring[j]] = side[ring[n]]          # skipped vertices join the old run
        cuts.append(k)
    if len(set(cuts)) != len(cuts) or any((cuts[i] - cuts[j]) % m in (1, m - 1)
                                          for i in range(len(cuts)) for j in range(len(cuts)) if i != j):
        stats.refused_geometry += 1
        stats.refused_why["ends"] = stats.refused_why.get("ends", 0) + 1
        return None
    avoid = {cell.idx[v] for v in cell.verts if v in blocked}
    best: tuple[float, list[list[int]], list[list[list[int]]]] | None = None
    why: list[str] = []
    for start in (0, 1):
        order = cuts[start:] + cuts[:start]
        pairs = [(order[i], order[i + 1]) for i in range(0, len(order), 2)]
        paths: list[list[int]] = []
        total = 0.0
        for ka, kb in pairs:
            # the geodesic over EVERY cycle vertex (the thinned set drops the
            # reflex corners a concave junction's path bends at — HECA #389)
            p = _geodesic(cell, list(range(len(cell.verts))), cell.idx[ring[ka]],
                          cell.idx[ring[kb]], avoid)
            if p is None or len(p) < 2:
                why.append("geodesic")
                break
            paths.append([cell.verts[i] for i in p])
            total += sum(math.dist(xy[u], xy[w]) for u, w in zip(paths[-1], paths[-1][1:]))
        else:
            if keepout is not None and not keepout.is_empty and any(
                    keepout.intersects(LineString([xy[v] for v in p])) for p in paths):
                why.append("strip")
                continue
            pieces = _pieces(cell, xy, paths, tol)
            cutset = {v for p in paths for v in p}
            if pieces is None:
                why.append("pieces")
            elif not _bichrome(pieces, side, cutset):
                why.append("mixed")
            elif best is None or total < best[0]:
                best = (total, paths, pieces)
    if best is None:
        if why and all(w == "strip" for w in why):
            stats.refused_strip += 1
        else:
            stats.refused_geometry += 1
            for w in why:
                stats.refused_why[w] = stats.refused_why.get(w, 0) + 1
        return None
    return best[2], best[1]


def _cut_face(pm: PlanarMap, f: Face, cell: _Cell, xy: dict[int, XY], keep: list[int],
              labels: _Labels, blocked: set[int], keepout, tol: float, stats: TerritoryStats,
              clearance: float, cxy: dict[int, XY], cycles: dict[int, list[list[int]]],
              protos: dict[int, Face], cut_faces: set[int]) -> bool:
    """Cut face ``f`` round by round (a piece keeping a lesser
    incompatible pair is cut again, ``MAX_CUT_ROUNDS`` deep — the
    attempt cap); registers the pieces.  True when a cut was made."""
    todo: list[tuple[list[list[int]], int]] = [(cell.cycles, 0)]
    final: list[list[list[int]]] = []
    paths_all: list[list[int]] = []
    while todo:
        cycs, depth = todo.pop()
        sub = _cell_from_cycles(f.id, cycs, xy, tol) if depth else cell
        label = {v: labels.label(v) for v in sub.verts} if sub is not None else {}
        cutset = {v for p in paths_all for v in p}
        terrs = [t for v in sub.verts if v not in cutset and (t := label.get(v)) is not None] \
            if sub is not None else []
        if sub is None or _severest(terrs, labels) is None or depth >= MAX_CUT_ROUNDS:
            final.append(cycs)
            continue
        sub_keep = _thin(sub, {sub.idx[v] for v in sub.verts if v in labels.of}, 0.0) \
            if depth else keep
        plan = _plan_cut(sub, xy, sub_keep, label, labels, blocked, keepout, tol, stats,
                         clearance, END_REACH, cxy)
        if plan is None:
            final.append(cycs)
            continue
        pieces, paths = plan
        paths_all.extend(paths)
        todo.extend((pc, depth + 1) for pc in pieces)
    if not paths_all:
        return False
    _register_cut(pm, f, final, paths_all, xy, cycles, protos, cut_faces, stats, blocked)
    return True


def _cell_from_cycles(fid: int, cycs: list[list[int]], xy: dict[int, XY], tol: float) -> _Cell | None:
    verts = [v for c in cycs for v in c]
    poly = polygon_from([xy[v] for v in cycs[0]], [[xy[v] for v in c] for c in cycs[1:]])
    if poly is None:
        return None
    cover = poly.buffer(tol)
    if cover.is_empty:
        return None
    shapely.prepare(cover)
    shapely.prepare(poly)
    return _Cell(fid, verts, cycs, {v: i for i, v in enumerate(verts)},
                 np.array([xy[v] for v in verts], float), cover, poly)


def terrace_territories(pm: PlanarMap, law: Law, airport: Airport,
                        classification: Classification,
                        bands: _t.Mapping[int, Band]) -> tuple[PlanarMap, TerritoryStats]:
    """``pm`` with every apron-like cell partitioned into reach
    territories, cut wherever two terraces meet inside it, the joint
    continued through the spanning faces, and the joints split and
    declared by ``split_terraces`` (module docstring).  ``bands`` is the
    route graph's ``(floor, ceiling)`` per reached vertex."""
    stats = TerritoryStats()
    tt = law.tables.emit.terrace
    soft_roles = set(tt.cell_roles) | set(tt.neighbour_roles)
    cont_roles = set(tt.continue_roles)
    tol = snap_margin_m(law)
    spacing = tt.simplify_factor * law.tables.emit.identity.min_distinct_spacing_m
    clearance = tt.joint_gap_m + law.tables.emit.identity.min_distinct_spacing_m
    xy = {vid: v.xy for vid, v in pm.vertices.items()}
    station: set[int] = set()
    for b in pm.breaklines.values():
        if b.kind == STATION_KIND:
            station.update(b.vertices(pm))
    blocked: set[int] = set(pm.seam_vertices)
    for b in pm.breaklines.values():
        blocked.update(b.vertices(pm))
    for v, vert in pm.vertices.items():
        if any(is_structure_role(law, pm.faces[f].role) for f in vert.incident_faces):
            blocked.add(v)
    keepout = strip_keepout(classification, law)
    labels = _Labels()
    cycles: dict[int, list[list[int]]] = {}
    protos: dict[int, Face] = {}
    cut_faces: set[int] = set()
    next_fid = max(pm.faces) + 1 if pm.faces else 0
    t0 = time.perf_counter()
    # ── ONE partition over the union of the apron-like faces ─────────
    # (the owner's "apron shape" is the welded pavement — HECA pav132 is
    # one 110 polygon the classification cut into 28 faces — so the in-
    # shape path runs through every apron-like face; the graph: every
    # cycle vertex, the arc between cycle neighbours, and the visible
    # chords inside each face among its thinned vertices)
    soft = [f for f in pm.faces.values() if f.role in soft_roles]
    cells: dict[int, _Cell] = {}
    for f in soft:
        cell = _cell_geometry(pm, f.id, xy, tol)
        if cell is not None:
            cells[f.id] = cell
    ids = sorted({v for c in cells.values() for v in c.verts})
    gid = {v: k for k, v in enumerate(ids)}
    n = len(ids)
    contacts = [v for v in ids if v in station and v in bands]
    cxy = {gid[c]: xy[c] for c in contacts}
    labels = _Labels()
    keep_of: dict[int, list[int]] = {}
    stats.contacts = len(contacts)
    if len(contacts) >= 2:
        A: list[np.ndarray] = []
        B: list[np.ndarray] = []
        W: list[np.ndarray] = []
        for fid, cell in cells.items():
            must = {cell.idx[v] for v in cell.verts if v in station}
            keep = _thin(cell, must, spacing)
            keep_of[fid] = keep
            k = np.array(keep, np.int64)
            I, J = np.triu_indices(len(k), 1)
            I, J = k[I], k[J]
            if len(I):
                ok = _visible(cell, I, J)
                I, J = I[ok], J[ok]
            L = np.hypot(cell.P[I, 0] - cell.P[J, 0], cell.P[I, 1] - cell.P[J, 1])
            A.append(np.array([gid[cell.verts[i]] for i in I], np.int64))
            B.append(np.array([gid[cell.verts[j]] for j in J], np.int64))
            W.append(L)
            for cyc in cell.cycles:
                a_ = np.array([gid[v] for v in cyc], np.int64)
                b_ = np.roll(a_, -1)
                A.append(a_); B.append(b_)
                W.append(np.array([math.dist(xy[u], xy[w]) for u, w in zip(cyc, cyc[1:] + cyc[:1])]))
        a_all, b_all, w_all = np.concatenate(A), np.concatenate(B), np.concatenate(W)
        m = csr_matrix((np.concatenate([w_all, w_all]),
                        (np.concatenate([a_all, b_all]), np.concatenate([b_all, a_all]))), shape=(n, n))
        m.sum_duplicates()
        cidx = np.array([gid[c] for c in contacts], np.int64)
        D, _p, src = dijkstra(m, directed=False, indices=cidx, min_only=True,
                              return_predecessors=True)
        ceil_of_contact = {gid[c]: bands[c][1] for c in contacts}
        terr = np.full(n, -1, np.int64)
        ok = np.isfinite(D)
        terr[ok] = src[ok]
        # every contact pair within reach: the in-shape distance between
        # the contacts (Dijkstra from each contact, limited to the longest
        # path any ceiling difference could need at the least cap) and the
        # joint predicate — PAIRWISE, never transitive
        cap_v = {v: _cap_at(pm, law, v, soft_roles) for v in contacts}
        cap_min = min(c for c in cap_v.values() if c > 0.0) if any(cap_v.values()) else 0.0
        ceils = np.array([bands[c][1] for c in contacts])
        span = float(ceils.max() - ceils.min())
        limit = (span - tt.min_step_m) / cap_min if cap_min > 0.0 and span > tt.min_step_m else 0.0
        # ADJACENT territories only (07c(2)): a pair whose territories
        # share no boundary is separated by the territories between them —
        # its shortcut is their pairs' business (the severest non-adjacent
        # pair at HECA, 3705|10286, would seat the seam south of #364)
        ta, tb = terr[a_all], terr[b_all]
        cross = (ta >= 0) & (tb >= 0) & (ta != tb)
        adjacent = {(min(int(x), int(y)), max(int(x), int(y))) for x, y in zip(ta[cross], tb[cross])}
        pos = {int(c): k for k, c in enumerate(cidx)}
        if limit > 0.0 and adjacent:
            Dcc = dijkstra(m, directed=False, indices=cidx, limit=limit)
            for ia, ib in sorted(adjacent):
                a, b = pos[ia], pos[ib]
                d = float(Dcc[a, cidx[b]])
                if not math.isfinite(d):
                    continue
                gap = abs(float(ceils[a]) - float(ceils[b]))
                cap_max = max(cap_v[contacts[a]], cap_v[contacts[b]])
                hold = cap_max * d + tt.min_step_m
                key = (min(int(cidx[a]), int(cidx[b])), max(int(cidx[a]), int(cidx[b])))
                labels.dist[key] = d
                if gap > hold:
                    labels.joint.add(key)
                    labels.severity[key] = gap - hold
                    stats.joints.append([contacts[a], contacts[b], round(gap, 2), round(d, 1),
                                         round(hold, 2)])
        for k in range(n):
            if terr[k] >= 0:
                v = ids[k]
                labels.ceil[v] = ceil_of_contact[int(terr[k])] + float(D[k]) * _cap_at(pm, law, v, soft_roles)
        stats.cells = len(cells)
        stats.territories = len({int(t) for t in terr if t >= 0})
        # THE SEAM: per connected pavement complex, the SEVEREST disagreeing
        # pair (a*, b*) — every vertex takes the side of the nearer contact
        # (in-shape), so the label boundary is ONE consistent line across
        # every face of the complex (per-face severest pairs cut
        # inconsistent seams that re-welded through the neighbours —
        # measured HECA 2026-09-07); the lesser disagreeing pairs stay
        # inside a side and are reported (``residual_pairs``)
        from scipy.sparse.csgraph import connected_components
        _nc, comp = connected_components(m, directed=False)
        by_comp: dict[int, list[tuple[float, int, int]]] = {}
        for (a, b), sev in labels.severity.items():
            by_comp.setdefault(int(comp[a]), []).append((sev, a, b))
        stats.seams = 0
        for c, prs in by_comp.items():
            sev, a, b = max(prs)
            Dab = dijkstra(m, directed=False, indices=[a, b])
            la, lb = 2 * stats.seams, 2 * stats.seams + 1
            stats.seams += 1
            stats.residual_pairs += len(prs) - 1
            for k in np.flatnonzero(comp == c):
                da, db = Dab[0][k], Dab[1][k]
                if not (np.isfinite(da) or np.isfinite(db)):
                    continue
                labels.of[ids[k]] = la if (np.isfinite(da) and (not np.isfinite(db) or da <= db)) else lb
            labels.joint.add((la, lb))
            labels.severity[(la, lb)] = sev
            stats.seam_pairs.append([ids[a], ids[b], round(float(ceils[contacts.index(ids[a])]), 2),
                                     round(float(ceils[contacts.index(ids[b])]), 2), round(sev, 2)])
    # ── the cuts: every apron-like face whose ring changes label ──────
    for f in sorted(soft, key=lambda f_: -_area(pm, f_.id, xy)):
        cell = cells.get(f.id)
        if cell is None:
            continue
        label = {v: labels.label(v) for v in cell.verts}
        terrs = [t for t in label.values() if t is not None]
        sev = _severest(terrs, labels)
        trace = [f.id, f.role, sum(1 for v in cell.verts if v in station and v in bands),
                 len(cell.verts), len(set(terrs)), list(sev) if sev else None, False]
        stats.cells_trace.append(trace)
        if sev is None:
            continue
        if _cut_face(pm, f, cell, xy, keep_of.get(f.id, []), labels, blocked, keepout, tol, stats,
                     clearance, cxy, cycles, protos, cut_faces):
            trace[-1] = True
            stats.cut_cells += 1
    stats.wall_partition_s = time.perf_counter() - t0
    stats.joint_pairs = len(labels.joint)
    # ── the continuation through the road family ────────────────────
    t1 = time.perf_counter()
    for f in sorted(pm.faces.values(), key=lambda f_: f_.id):
        if f.id in cycles or f.role in soft_roles:
            continue
        cyc = _face_cycles(pm, f.id)
        if not cyc or len(cyc[0]) < 3:
            continue
        labs = sorted({labels.label(v) for c in cyc for v in c} - {None})
        if not any(labels.is_joint(a, b) for i, a in enumerate(labs) for b in labs[i + 1:]):
            continue
        if f.role not in cont_roles or is_rigid_role(law, f.role):
            # a rigid pad belongs to one terrace (06n); a face spanned by a
            # reached route joins the terraces lawfully along that route;
            # a face with no reached station straddles WELDED — a leak
            # the cut does not close (reported, RULINGS 2026-09-07c owed)
            if is_rigid_role(law, f.role):
                key = f"{f.role} (rigid)"
            elif any(v in station and v in bands for c in cyc for v in c):
                key = f"{f.role} (routed)"
            else:
                key = f"{f.role} (dead-end)"
            stats.straddling_uncut[key] = stats.straddling_uncut.get(key, 0) + 1
            continue
        cell = _cell_geometry(pm, f.id, xy, tol)
        if cell is None:
            continue
        # labels propagated to the rest of the ring from the nearest labelled vertex
        labelled = [(v, labels.label(v)) for v in cell.verts if labels.label(v) is not None]
        label = {}
        for v in cell.verts:
            lab = labels.label(v)
            if lab is None:
                lab = min(labelled, key=lambda t: math.dist(xy[v], xy[t[0]]))[1]
            label[v] = lab
        keep = _thin(cell, {cell.idx[v] for v, _l in labelled}, spacing)
        for v, lab in label.items():
            if v not in labels.of:
                labels.of[v] = lab
        if _cut_face(pm, f, cell, xy, keep, labels, blocked, keepout, tol, stats,
                     clearance, cxy, cycles, protos, cut_faces):
            stats.cut_continue += 1
        else:
            stats.straddling_uncut[f.role] = stats.straddling_uncut.get(f.role, 0) + 1
    stats.wall_cut_s = time.perf_counter() - t1
    if not cycles:
        pm2, stats.terraces_split = split_terraces(pm, law, airport, classification)
        return pm2, stats
    # ── re-assemble, validate, split ────────────────────────────────
    vertices, edges, faces, breaklines = reassemble(pm, airport, cycles, protos, {})
    pm2 = PlanarMap(pm.icao, vertices, edges, faces, breaklines, pm.seam_vertices,
                    pm.structures, pm.basins, dict(pm.preferred_z), pm.terrace_joints,
                    dict(pm.terrace_group))
    try:
        validate(pm2)
    except PlanarError:
        stats.refused_map += 1
        pm2, stats.terraces_split = split_terraces(pm, law, airport, classification)
        return pm2, stats
    # every face's SIDE of the seam (its ring's majority label; a piece
    # is single-sided): faces of different sides are never joined
    sides: dict[int, int] = {}
    cut_v = {v for c in stats.cuts for v in c[2]}
    for fid, f in faces.items():
        if f.role not in soft_roles and fid not in cut_faces:
            continue
        labs = [labels.of[v] for cyc in (f.ring, *f.holes)
                for v in pm2.ring_vertices(cyc) if v in labels.of and v not in cut_v]
        if labs:
            sides[fid] = max(set(labs), key=labs.count)
    pm3, stats.terraces_split = split_terraces(pm2, law, airport, classification,
                                               cut_faces=frozenset(cut_faces),
                                               reached=frozenset(bands), sides=sides)
    # the cut vertices the split left shared (refused copies): a welded
    # vertex on a joint couples the two terraces through it — reported
    path_vertices = {v for c in stats.cuts for v in c[2]}
    split_v = {v for j in pm3.terrace_joints for pair in j.pairs for v in pair}
    stats.cut_vertices = len(path_vertices)
    stats.welded_cut_vertices = len(path_vertices - split_v)
    return pm3, stats


def _cap_at(pm: PlanarMap, law: Law, v: int, soft_roles: set[str]) -> float:
    """The max cap of the apron-like faces at vertex ``v`` (the surface
    the in-shape path runs over)."""
    caps = []
    for fid in pm.vertices[v].incident_faces:
        f = pm.faces[fid]
        if f.role in soft_roles:
            rc = role_cap(law, f.role, f.code_number, f.code_letter)
            if rc is not None:
                caps.append(max(rc.longitudinal, rc.transverse))
    return max(caps) if caps else 0.0


def _area(pm: PlanarMap, fid: int, xy: dict[int, XY]) -> float:
    cyc = _face_cycles(pm, fid)
    return Polygon([xy[v] for v in cyc[0]]).area if cyc and len(cyc[0]) >= 3 else 0.0


def _register_cut(pm: PlanarMap, f: Face, pieces: list[list[list[int]]],
                  paths: list[list[int]], xy: dict[int, XY],
                  cycles: dict[int, list[list[int]]], protos: dict[int, Face],
                  cut_faces: set[int], stats: TerritoryStats, blocked: set[int]) -> None:
    """Record a cut face's pieces: the largest keeps the face id, the
    rest take new ids; the paths and their length are reported."""
    order = sorted(range(len(pieces)),
                   key=lambda k: -Polygon([xy[v] for v in pieces[k][0]]).area)
    base = max(max(pm.faces), max(cycles, default=-1), max(protos, default=-1)) + 1
    for n, k in enumerate(order):
        fid = f.id if n == 0 else base + n - 1
        cycles[fid] = pieces[k]
        if n > 0:
            protos[fid] = _dc.replace(f, id=fid, ring=(), holes=())
        cut_faces.add(fid)
    stats.pieces += len(pieces)
    stats.cut_by_role[f.role] = stats.cut_by_role.get(f.role, 0) + 1
    for p in paths:
        length = sum(math.dist(xy[s], xy[t]) for s, t in zip(p, p[1:]))
        stats.cut_length_m += length
        stats.cuts.append([f.id, f.role, list(p), round(length, 1)])
        stats.welded_breakline += sum(1 for v in p if v in blocked)
