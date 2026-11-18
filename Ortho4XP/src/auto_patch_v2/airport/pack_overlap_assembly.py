"""A HIDDEN STRUCTURE TAKES ITS WHOLE ROUTE ASSEMBLY WITH IT (issue #2163).

Owner sim read on 1.0.559 (2026-11-18T16:26Z): "we're not hiding the one
from Chudoba correctly, since it has many pieces, it's piers and parts of
it's rail are still visible."  ``pack_overlap`` hides the LARGE structures
two packs both draw (each at least the building floor, half of the smaller
plan shared); an elevated rail drawn as a row of placed spans was hidden
only span by span where a span alone passed that bar, and its piers (below
the floor) never.  RULINGS 2026-11-16q: a pack piece on a route's path is
part of the route whatever its size.

THE ASSEMBLY of one pack's hidden rows, inside the detection region (the
airport + 1 km; a placement is read where its origin lies):

* THE CHAIN -- every chain of deck spans (``deck_chain.joints``: pieces
  joined end to end, each floating at least ``ChainLaw.elevated_m`` over
  its origin, its piers placed apart) holding a hidden row is hidden
  whole, and every chain meeting it at a branch (an edge on its edge: a
  siding, a crossover);
* THE THROUGH-STRUCTURE -- a chain whose free END lands on a hidden
  structure (a station) is hidden; a structure of the pack's own reading
  on which an assembled chain's end and another chain's end both land (the
  deck passes through it) is hidden with them;
* THE CO-ANCHORED -- a placement that is no deck piece whose origin lies
  within ``ChainLaw.gap_m`` of an assembled piece's origin or end edge (a
  pier, a pod at a joint): ``deck_chain.chain_seats``' co-anchor;
* THE STATION -- a long narrow structure the assembled deck runs along
  (``_along``), left floating with no rail were it kept;
* THE ATTACHED -- a placement below the structure floor whose plan
  touches a hidden route structure (a station the deck lands on or runs
  along), or another such piece (a footbridge off a station and its stair
  towers).

Read from the geometry alone (deck pieces by ``deck_chain.piece_of``),
never from a file or pack name.  A pack with no hidden row reads nothing.
"""
from __future__ import annotations

import functools as _ft
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Point
from shapely.prepared import prep

from . import deck_chain as _dc
from .pack_overlap import Frame, HideRow, Structure, _rows

__all__ = ["assembly", "LANDING_M"]

#: a piece hangs from a route structure whose plan it comes within this of
#: (metres): a footbridge lands on a station's mezzanine, whose solid plan
#: stops short of it (OMDB's measured 3.3-5.1 m)
LANDING_M = 6.0


@_ft.lru_cache(maxsize=4096)
def _floats(path: str, clear_m: float) -> bool:
    """A DECK SPAN: every static solid vertex of the piece at least
    ``clear_m`` over its origin -- the whole piece floats, its piers placed
    apart (a building's walls, whatever its eaves, reach its ground)."""
    from . import obj8 as _obj8
    from .msl_feet import static_vertices
    try:
        v = static_vertices(_obj8.parse_obj8(path))
    except (OSError, ValueError, IndexError):
        return False
    return v is not None and float(v[:, 1].min()) >= clear_m


def _placed(lines, frame: Frame, region, resolve, law: _dc.ChainLaw
            ) -> list[_dc.Placed]:
    """The pack's ``.obj`` rows whose origin lies in ``region``, as
    ``deck_chain.Placed`` (a deck piece read where it is one and floats,
    :func:`_floats`)."""
    inside = prep(region)
    objs, _facs = _rows(lines, frame.lonlat_box(region))
    out = []
    for i, (res, lon, lat, hdg) in enumerate(objs):
        xy = frame.xy(lon, lat)
        if not res.lower().endswith(".obj") or not inside.contains(Point(xy)):
            continue
        path = resolve(res)
        piece = _dc.piece_of(path) if path else None
        if piece is not None and not _floats(path, law.elevated_m):
            piece = None
        out.append(_dc.Placed(i, res, lat, lon, hdg, xy, piece))
    return out


class _Chains(_t.NamedTuple):
    """The pack's ELEVATED deck chains in the region."""

    members: list          # piece indices per chain
    ends: np.ndarray       # (n, 2) free end points
    end_chain: np.ndarray  # (n,) the chain of each free end
    links: dict            # chain -> the chains it meets at a branch


def _chains(placed: _t.Sequence[_dc.Placed], law: _dc.ChainLaw) -> _Chains:
    """Every chain of deck spans (``deck_chain.joints`` over the pieces
    that float, :func:`_floats`; a lone span is a chain -- a row of
    houses, a car or a track at grade is none), its free ends (no
    other piece's edge meets them), and the BRANCHES ``deck_chain`` leaves
    unjoined: an edge on an edge of the same width, or two pieces
    overlapping in plan within ``heading_deg`` (a turnout)."""
    from scipy.spatial import cKDTree
    js = _dc.joints(placed, law)
    rel, _cut = _dc._solve(len(placed), js, law)
    by: dict[int, list[int]] = {}
    for k, p in enumerate(placed):
        if p.piece is not None:
            by.setdefault(rel[k][0] if k in rel else k, []).append(k)
    members = list(by.values())
    edge, owner = [], []
    for c, ks in enumerate(members):
        for k in ks:
            for _wh, w, wd, _s in _dc._edges(placed[k]):
                edge.append(w)
                owner.append((c, k, wd))
    links: dict[int, set] = {}

    def link(a: int, b: int) -> None:
        if a != b:
            links.setdefault(a, set()).add(b)
            links.setdefault(b, set()).add(a)
    if not edge:
        return _Chains(members, np.zeros((0, 2)), np.zeros(0, dtype=int), links)
    tree = cKDTree(np.asarray(edge))
    free = []
    for i, w in enumerate(edge):
        near = [owner[j] for j in tree.query_ball_point(w, law.gap_m + law.lateral_m)
                if owner[j][1] != owner[i][1]]
        if not near:
            free.append(i)
        for c, _k, wd in near:
            if abs(wd - owner[i][2]) <= law.width_m:
                link(owner[i][0], c)
    _turnouts(placed, members, law, link)
    return _Chains(members, np.asarray([edge[i] for i in free], dtype=float).reshape(-1, 2),
                   np.asarray([owner[i][0] for i in free], dtype=int), links)


def _turnouts(placed, members, law, link) -> None:
    """Link two elevated chains whose pieces overlap in plan, parallel
    within ``heading_deg``."""
    from shapely.geometry import Polygon
    keys, rects = [], []
    for c, ks in enumerate(members):
        for k in ks:
            (_a, w0, d0, _s0), (_b, w1, d1, _s1) = _dc._edges(placed[k])
            ax = np.subtract(w1, w0)
            n = np.asarray([-ax[1], ax[0]]) / (float(np.hypot(*ax)) or 1.0)
            rects.append(Polygon([np.add(w0, n * d0 / 2), np.add(w1, n * d1 / 2),
                                  np.subtract(w1, n * d1 / 2), np.subtract(w0, n * d0 / 2)]))
            keys.append((c, k))
    if not rects:
        return
    tree = shapely.STRtree(rects)
    a, b = tree.query(rects, predicate="intersects")
    for i, j in zip(a.tolist(), b.tolist(), strict=True):
        (ci, ki), (cj, kj) = keys[i], keys[j]
        if ci == cj:
            continue
        dh = abs((placed[ki].heading - placed[kj].heading + 90.0) % 180.0 - 90.0)
        if dh <= law.heading_deg and rects[i].intersection(rects[j]).area > 0.0:
            link(ci, cj)


def _landing(poly, pts: np.ndarray, own: np.ndarray, tol: float) -> set[int]:
    """The chains with a free end within ``tol`` of ``poly``."""
    if not len(pts):
        return set()
    d = shapely.distance(poly, shapely.points(pts))
    return {int(c) for c in own[d <= tol]}


def assembly(lines: _t.Iterable[str], frame: Frame, region,
             hidden: _t.Collection[HideRow], structures: _t.Sequence[Structure],
             resolve: _t.Callable[[str], "str | None"], cache=None,
             law: "_dc.ChainLaw | None" = None) -> list[HideRow]:
    """The rows the assembly of ``hidden`` adds (module doc).
    ``structures``: the pack's own large structures (``pack_overlap.
    structures``), the through-structure candidates; ``cache`` an
    ``obj8.ResourceCache`` (``None``: no attached pieces are read)."""
    law = law or _dc.ChainLaw()
    if not hidden:
        return []
    placed = _placed(lines, frame, region, resolve, law)
    ch = _chains(placed, law)
    members = ch.members
    row = [HideRow(p.resource, p.lon, p.lat) for p in placed]
    taken = set(hidden)
    lands = {s.row: _landing(s.poly, ch.ends, ch.end_chain, law.gap_m) for s in structures}
    done: set[int] = set()
    grew = True
    while grew:
        grew = False
        for s in structures:
            hit = lands[s.row]
            if s.row not in taken and len(hit) >= 2 and hit & done:
                taken.add(s.row)
            if s.row in taken and hit - done:
                done |= hit
                grew = True
        for c, ks in enumerate(members):
            if c not in done and (any(row[k] in taken for k in ks)
                                  or ch.links.get(c, set()) & done):
                done.add(c)
                grew = True
        taken.update(row[k] for c in done for k in members[c])
    deck = [k for c in done for k in members[c]]
    taken |= _coanchored(placed, row, deck, law)
    along = _along(placed, deck, structures, law)
    taken |= along
    route = [s for s in structures
             if s.row in along or (s.row in taken and lands[s.row] & done)]
    if cache is not None:
        taken |= _attached(placed, row, resolve, cache, structures, route, taken, law)
    return sorted(taken - set(hidden))


def _along(placed, deck, structures, law) -> set[HideRow]:
    """THE STATION: a structure the assembled deck runs ALONG -- its plan
    long and narrow (long side at least twice the short), its long axis
    parallel to the deck within ``heading_deg``, and the deck inside it for
    at least half that long side."""
    if not deck:
        return set()
    import math

    from shapely.geometry import LineString
    segs = {}
    for k in deck:
        (_a, w0, _b, _c), (_d, w1, _e, _f) = _dc._edges(placed[k])
        segs[k] = LineString([w0, w1])
    tree = shapely.STRtree(list(segs.values()))
    keys = list(segs)
    out = set()
    for s in structures:
        if s.poly.area <= 0.0:
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            rect = s.poly.minimum_rotated_rectangle
        xy = list(rect.exterior.coords)[:3]
        a = math.dist(xy[0], xy[1])
        b = math.dist(xy[1], xy[2])
        p, q = (xy[0], xy[1]) if a >= b else (xy[1], xy[2])
        long_, short = max(a, b), min(a, b)
        if long_ < 2.0 * short:
            continue
        axis = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
        inside = 0.0
        for i in tree.query(s.poly):
            pl = placed[keys[int(i)]]
            dh = abs((90.0 - pl.heading - axis + 90.0) % 180.0 - 90.0)
            if dh <= law.heading_deg:
                inside += segs[keys[int(i)]].intersection(s.poly).length
        if inside >= 0.5 * long_:
            out.add(s.row)
    return out


def _attached(placed, row, resolve, cache, structures, route, taken, law
              ) -> set[HideRow]:
    """THE ATTACHED: a placement below the structure floor (no structure of
    the pack's reading, no deck piece) whose plan touches a hidden ROUTE
    structure (``route``: a station the deck lands on or runs along; within
    :data:`LANDING_M`) or another attached piece (within ``lateral_m``): a
    footbridge off a station, its stair tower -- part of what it hangs
    from."""
    from .frame_entry import transform
    from .obj8 import placement_affine
    from .skirt import footprint
    big = {s.row for s in structures}
    held = [s.poly for s in route]
    if not held:
        return set()
    memo: dict = {}
    cand, polys = [], []
    for k, p in enumerate(placed):
        if row[k] in big or row[k] in taken or p.piece is not None:
            continue
        path = resolve(p.resource)
        if path not in memo:
            memo[path] = footprint(cache, path) if path else None
        if memo[path] is None:
            continue
        cand.append(row[k])
        polys.append(transform(memo[path], placement_affine(p.xy, p.heading)))
    if not cand:
        return set()
    tree = shapely.STRtree(polys)
    out: set[HideRow] = set()
    front, reach = held, LANDING_M
    while front:
        nxt = []
        for g in front:
            for i in tree.query(g, predicate="dwithin", distance=reach):
                if cand[int(i)] not in out:
                    out.add(cand[int(i)])
                    nxt.append(polys[int(i)])
        front, reach = nxt, law.lateral_m
    return out


def _coanchored(placed, row, ks, law) -> set[HideRow]:
    """The non-piece rows within ``gap_m`` of an assembled piece's origin
    or end edge."""
    if not ks:
        return set()
    from scipy.spatial import cKDTree
    pts = [placed[k].xy for k in ks]
    pts += [w for k in ks for (_wh, w, _wd, _s) in _dc._edges(placed[k])]
    tree = cKDTree(np.asarray(pts))
    return {row[k] for k, p in enumerate(placed)
            if p.piece is None and tree.query(p.xy)[0] <= law.gap_m}
