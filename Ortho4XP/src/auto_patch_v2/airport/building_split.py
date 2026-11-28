"""THE SEPARATELY SEATED BUILDINGS, FOUND ONCE AT LOAD (owner RULINGS
2026-11-27h; spec ``docs/specs/building-envelope-20261127.md`` §2).

Owner 2026-11-27: "we should only be identifying separate buildings that
need to be split so they can be seated, we don't want to spend any time
analyzing small components inside a group that all moves together";
"objects inside another object should always move with the containing
object".

ONE PASS over every solid piece of the pack (line and scatter pieces are
out, as today), on the plan LATTICE of ``[placement] footprint_touch_m``
cells (``geom/plan_lattice``; cells by ``underside_map.supercover``):

* B2 a WALL piece stands ``[placement] chain_min_height_m`` or more (its
  solid height) and is no deck of a BRIDGE frame
  (``placement_family.member_is_bridge_deck``); ``W`` is every cell its plan
  meets.  Every other solid piece is a CANDIDATE.
* B4/B5 a BUILDING is an 8-connected region of ``W`` (two-cell link at the
  finer cell) with its ROOFED enclosures: a hole of the region whose cells
  carry, for ``[basin] basement_cover_min`` of them, a surface standing
  ``chain_min_height_m`` or more over the region's lowest wall foot.
* B6 a SHEET -- a candidate that is no deck, has no ground feet and is not
  authored wholly below ``contents.CONTENTS_BELOW_M`` -- overlapping two or
  more buildings by ``[placement] sheet_chain_min_fraction`` of the smaller
  of the two JOINS them and is interior (27a on the lattice).
* B7 a candidate with ``[placement] contents_min_fraction`` of its cells in
  ONE building is INTERIOR, whatever it is: no refusal (S6's deck and
  below-grade refusals are repealed for motion).
* B8 one placement's touching pieces (10i (1) at the building's edge): a
  same-placement contact component reaching two buildings joins them; its
  exterior pieces are ATTACHED to the building it reaches.
* B9 a building's id is the smallest part id among its wall pieces.

Every step is a function of the pieces' placed triangles and verdicts
alone: no DEM, no planar product, no dict or pool order.  A REPORT until
a reader takes it (spec §10 stop 1)."""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

import numpy as np

from ..geom import plan_lattice as _pl
from ..geom.underside_map import supercover

__all__ = ["Params", "PieceTable", "split", "of_partition", "WALL",
           "INTERIOR", "ATTACHED", "SHEET"]

WALL, INTERIOR, ATTACHED, SHEET = "wall", "interior", "attached", "sheet"
#: the spec's 0.0 alternative: a 0.25 m cell with a two-cell link
FINE_CELL_M, FINE_LINK = 0.25, 2


@_dc.dataclass(frozen=True)
class Params:
    """The law the split reads (module doc)."""

    cell_m: float
    link: int
    tall_m: float
    roof_min: float
    sheet_min: float
    contents_min: float
    below_m: float

    @classmethod
    def from_law(cls, law, fine: bool = False) -> "Params":
        from .contents import CONTENTS_BELOW_M
        pl = law.tables.structures.placement
        cell = float(pl.footprint_touch_m)
        return cls(FINE_CELL_M if fine else cell, FINE_LINK if fine else 1,
                   float(pl.chain_min_height_m),
                   float(law.tables.structures.basin.basement_cover_min),
                   float(pl.sheet_chain_min_fraction), float(pl.contents_min_fraction),
                   float(CONTENTS_BELOW_M))


@_dc.dataclass(frozen=True, eq=False)
class PieceTable:
    """The solid pieces, columnar: per piece its part id, placement
    (member) index, anchor index, solid height, whether its member is a
    deck / a bridge-frame deck, whether it has ground feet, its authored
    top (over its own zero) and its lowest point in the common vertical
    frame; per TRIANGLE its plan ``(n, 3, 2)`` east/north, its highest
    point (common frame) and its piece (ascending)."""

    pid: np.ndarray
    member: np.ndarray
    anchor: np.ndarray
    solid_h: np.ndarray
    deck: np.ndarray
    bridge_deck: np.ndarray
    footed: np.ndarray
    top_authored: np.ndarray
    base: np.ndarray
    tri_xy: np.ndarray
    tri_top: np.ndarray
    tri_owner: np.ndarray

    def __len__(self) -> int:
        return len(self.pid)


@_dc.dataclass(frozen=True)
class Building:
    """One separately seated building: its id (smallest wall part id), its
    wall part ids, the anchors and placements of every piece in it, its
    cell count and plan box ``(e0, n0, e1, n1)`` in frame metres."""

    id: int
    walls: tuple[int, ...]
    anchors: tuple[int, ...]
    members: tuple[int, ...]
    cells: int
    area_m2: float
    box: tuple[float, float, float, float]


@_dc.dataclass(frozen=True, eq=False)
class Split:
    """The split (module doc): ``of`` part id -> building id and ``kind``
    part id -> :data:`WALL` / :data:`INTERIOR` / :data:`SHEET` /
    :data:`ATTACHED` for every piece in a building; ``buildings`` in id
    order; ``runs`` ``(k, 4)`` the building cells as lattice row runs
    ``(i, j0, j1, building id)`` sorted by ``(i, j0)``."""

    params: Params
    of: dict[int, int]
    kind: dict[int, str]
    buildings: tuple[Building, ...]
    runs: np.ndarray
    counts: dict[str, _t.Any]


class _Forest:
    """Union-find over building labels; a union keeps the smaller label."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, a: int) -> int:
        from ..geom.union_find import find_root
        return find_root(self.parent, a)

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        lo, hi = min(ra, rb), max(ra, rb)
        self.parent[hi] = lo
        return True

    def roots(self) -> np.ndarray:
        return np.array([self.find(a) for a in range(len(self.parent))], dtype=np.int64)


def _intervals(t: PieceTable, sel: np.ndarray, step: float):
    """``(piece, i, j0, j1, top)``: the supercover runs of the triangles of
    the pieces ``sel`` (a bool per piece), one per (triangle, row), in
    piece order."""
    tri = np.flatnonzero(sel[t.tri_owner])
    k, i, j0, j1 = supercover(t.tri_xy[tri], step)
    return t.tri_owner[tri][k], i, j0, j1, t.tri_top[tri][k]


def _boxes(t: PieceTable) -> np.ndarray:
    """``(P, 4)`` plan box ``(e0, n0, e1, n1)`` of every piece's triangles
    (``nan`` for a piece with none)."""
    out = np.full((len(t), 4), np.nan)
    if not len(t.tri_owner):
        return out
    lo, hi = t.tri_xy.min(1), t.tri_xy.max(1)
    at = np.flatnonzero(np.r_[True, t.tri_owner[1:] != t.tri_owner[:-1]])
    own = t.tri_owner[at]
    out[own, 0] = np.minimum.reduceat(lo[:, 0], at)
    out[own, 1] = np.minimum.reduceat(lo[:, 1], at)
    out[own, 2] = np.maximum.reduceat(hi[:, 0], at)
    out[own, 3] = np.maximum.reduceat(hi[:, 1], at)
    return out


def _region_boxes(i, j0, j1, lab, count: int) -> np.ndarray:
    """``(count, 4)`` lattice box ``(i0, j0, i1, j1)`` of each region."""
    out = np.empty((count, 4), dtype=np.int64)
    for k, (a, f, init) in enumerate(((i, np.minimum, np.iinfo(np.int64).max),
                                      (j0, np.minimum, np.iinfo(np.int64).max),
                                      (i, np.maximum, np.iinfo(np.int64).min),
                                      (j1, np.maximum, np.iinfo(np.int64).min))):
        v = np.full(count, init, dtype=np.int64)
        f.at(v, lab, a)
        out[:, k] = v
    return out


def _tree(boxes: np.ndarray):
    """``(STRtree, row index)`` of the finite plan boxes ``(n, 4)``."""
    import shapely
    idx = np.flatnonzero(np.isfinite(boxes).all(1))
    return shapely.STRtree(shapely.box(*boxes[idx].T)), idx


def _hits(tree, idx: np.ndarray, boxes: np.ndarray) -> list[np.ndarray]:
    """Per query box, the rows of ``idx`` whose box meets it."""
    import shapely
    q = tree.query(shapely.box(*boxes.T), predicate="intersects")
    o = np.argsort(q[0], kind="stable")
    qa, qb = q[0][o], idx[q[1][o]]
    at = np.searchsorted(qa, np.arange(len(boxes) + 1))
    return [np.sort(qb[at[k]:at[k + 1]]) for k in range(len(boxes))]


class _Roofs:
    """THE ROOF COVER of B4: for region ``c``'s hole box, the cells a
    candidate triangle covers standing ``tall_m`` or more over the region's
    lowest wall foot (its highest point, the common vertical frame)."""

    def __init__(self, cand, n: int, need: np.ndarray, near: list[np.ndarray]) -> None:
        self.p, self.i, self.j0, self.j1, self.top = cand
        self.at = np.searchsorted(self.p, np.arange(n + 1))
        self.need, self.near = need, near

    def __call__(self, c: int, a0: int, b0: int, h: int, w: int) -> np.ndarray:
        m = np.zeros((h, w), dtype=bool)
        pcs = self.near[c]
        if not len(pcs):
            return m
        sel = np.concatenate([np.arange(self.at[q], self.at[q + 1]) for q in pcs])
        ii, a, b, tp = self.i[sel], self.j0[sel], self.j1[sel], self.top[sel]
        ok = (tp >= self.need[c]) & (ii >= a0) & (ii < a0 + h) & (b >= b0) & (a < b0 + w)
        if ok.any():
            a, b = np.maximum(a[ok], b0), np.minimum(b[ok], b0 + w - 1)
            m |= _pl._dense(ii[ok], a, b, a0, b0, h, w)
        return m


def _shares(piece: np.ndarray, lab: np.ndarray, cells: np.ndarray, root: np.ndarray):
    """``(piece, root, cells)`` per piece and building it has cells in,
    ordered by piece then root."""
    if not len(piece):
        z = np.zeros(0, dtype=np.int64)
        return z, z, z
    span = int(root.max()) + 1
    code, inv = np.unique(piece * span + root[lab], return_inverse=True)
    return code // span, code % span, np.bincount(inv, weights=cells).astype(np.int64)


def _best(n: int, sp, sr, sc, total: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(root, share)`` per piece: the building holding most of its cells
    (the lower root on a tie) and that share; root -1 where none."""
    best_r = np.full(n, -1, dtype=np.int64)
    best_c = np.zeros(n, dtype=np.int64)
    if len(sp):
        o = np.lexsort((sr, -sc, sp))
        at = o[np.r_[True, sp[o][1:] != sp[o][:-1]]]
        best_r[sp[at]] = sr[at]
        best_c[sp[at]] = sc[at]
    share = np.where(total > 0, best_c / np.maximum(total, 1), 0.0)
    return best_r, share


def _same_member_components(t: PieceTable, contacts) -> "np.ndarray | None":
    """The component of every piece in the graph of the contact edges
    between pieces of one placement (``None``: no contacts given)."""
    if contacts is None:
        return None
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(t)
    c = np.asarray(contacts, dtype=np.int64).reshape(-1, 2)
    o = np.argsort(t.pid, kind="stable")
    sp = t.pid[o]
    if not n or not len(c):
        return np.arange(n)
    ia = np.minimum(np.searchsorted(sp, c[:, 0]), n - 1)
    ib = np.minimum(np.searchsorted(sp, c[:, 1]), n - 1)
    ok = (sp[ia] == c[:, 0]) & (sp[ib] == c[:, 1])
    a, b = o[ia[ok]], o[ib[ok]]
    same = t.member[a] == t.member[b]
    g = coo_matrix((np.ones(int(same.sum()), dtype=np.int8), (a[same], b[same])), shape=(n, n))
    return connected_components(g, directed=False)[1]


class _Stamps:
    """Seconds per step of :func:`split`, into ``counts["step_s"]``."""

    def __init__(self, counts: dict) -> None:
        self.at, self.out = time.perf_counter(), counts.setdefault("step_s", {})

    def __call__(self, name: str) -> None:
        now = time.perf_counter()
        self.out[name] = round(now - self.at, 3)
        self.at = now


def _walls(t: PieceTable, wall: np.ndarray, prm: Params, counts: dict):
    """B2/B5: the wall runs, their regions, each wall piece's region and
    each region's lowest wall foot."""
    wp, wi, wa, wb, _top = _intervals(t, wall, prm.cell_m)
    _g, ri, ra, rb = _pl.merge_runs(np.zeros(len(wi), dtype=np.int64), wi, wa, wb)
    lab, nreg = _pl.run_regions(ri, ra, rb, prm.link)
    counts["wall_runs"], counts["wall_regions"] = int(len(ri)), nreg
    # each wall piece's region, read at its first run's first cell
    first = np.flatnonzero(np.r_[True, wp[1:] != wp[:-1]]) if len(wp) else wp
    q, r, _n = _pl.overlaps(wi[first], wa[first], wa[first], ri, ra, rb)
    piece_region = np.full(len(t), -1, dtype=np.int64)
    piece_region[wp[first][q]] = lab[r]
    foot = np.full(max(nreg, 1), np.inf)
    held = piece_region >= 0
    np.minimum.at(foot, piece_region[held], t.base[held])
    return (ri, ra, rb, lab, nreg), piece_region, foot


def split(t: PieceTable, prm: Params, contacts=None, trace: bool = False) -> Split:
    """THE SPLIT (module doc) of the pieces ``t``; ``contacts`` the
    partition's ``(pid, pid)`` contact edges (B8; ``None`` skips it).
    ``trace`` (the census's question) also records in ``counts["trace"]``
    each wall piece's wall region and every join (``roof`` / ``sheet`` /
    ``placement``, region, region)."""
    t0 = time.perf_counter()
    n = len(t)
    counts: dict[str, _t.Any] = {"pieces": n}
    stamp = _Stamps(counts)
    wall = (t.solid_h >= prm.tall_m) & ~t.bridge_deck
    counts["wall_pieces"] = int(wall.sum())
    (ri, ra, rb, lab, nreg), piece_region, foot = _walls(t, wall, prm, counts)
    stamp("walls")
    # THE CANDIDATES that can reach a building: their box meets a region's
    step = prm.cell_m
    boxes = _boxes(t)
    rbox = _region_boxes(ri, ra, rb, lab, nreg)
    rbox_m = np.column_stack([rbox[:, 1] * step, rbox[:, 0] * step,
                              (rbox[:, 3] + 1) * step, (rbox[:, 2] + 1) * step])
    near_c = np.zeros(n, dtype=bool)
    cand_boxes = np.where(~wall[:, None], boxes, np.nan)
    tree, idx = _tree(cand_boxes)
    pad = np.array([-step, -step, step, step])
    near = _hits(tree, idx, rbox_m + pad) if nreg else []
    for h in near:
        near_c[h] = True
    cand = ~wall & near_c
    counts["candidates_near"] = int(cand.sum())
    cp, ci, ca, cb, ct = _intervals(t, cand, step)
    stamp("candidates")
    # B4 THE ROOFED ENCLOSURES; B5 the buildings' runs
    roofs = _Roofs((cp, ci, ca, cb, ct), n, foot + prm.tall_m, near)
    (bi, ba, bb, blab), joins, hc = _pl.roofed_fill(ri, ra, rb, lab, nreg, roofs,
                                                    prm.roof_min, prm.link)
    counts.update({f"enclosures_{k}": v for k, v in hc.items()})
    forest = _Forest(nreg)
    log: list = []
    for a, b in joins.tolist():
        forest.union(int(a), int(b))
        log.append(("roof", int(a), int(b)))
    root = forest.roots()
    bg, bi, ba, bb = _pl.merge_runs(root[blab], bi, ba, bb)
    o = np.lexsort((ba, bi))
    bg, bi, ba, bb = bg[o], bi[o], ba[o], bb[o]
    stamp("enclosures")
    # each candidate's cells, and its cells in each building
    mg, mi, ma, mb = _pl.merge_runs(cp, ci, ca, cb)
    total = np.bincount(mg, weights=mb - ma + 1, minlength=n).astype(np.int64)
    q, r, nc = _pl.overlaps(mi, ma, mb, bi, ba, bb)
    cpiece, clab = mg[q], bg[r]
    rcells = np.bincount(bg, weights=bb - ba + 1, minlength=nreg)
    kind = np.zeros(n, dtype=np.int8)       # 0 exterior, 1 wall, 2 interior, 3 sheet, 4 attached
    kind[wall] = 1
    # B6 THE SHEETS
    sheet_ok = cand & ~t.deck & ~t.footed & (t.top_authored >= -prm.below_m)
    sp, sr, sc = _shares(cpiece, clab, nc, root)
    with np.errstate(divide="ignore", invalid="ignore"):
        frac = sc / np.minimum(total[sp], rcells[sr])
    hit = sheet_ok[sp] & (frac >= prm.sheet_min)
    hp, hr = sp[hit], sr[hit]
    n_sheet = 0
    if len(hp):
        at = np.flatnonzero(np.r_[True, hp[1:] != hp[:-1]])
        for s0, e0 in zip(at, np.r_[at[1:], len(hp)]):
            if e0 - s0 >= 2:
                n_sheet += 1
                kind[hp[s0]] = 3
                for r2 in hr[s0 + 1:e0].tolist():
                    forest.union(int(hr[s0]), int(r2))
                    log.append(("sheet", int(hr[s0]), int(r2)))
    counts["sheets"] = n_sheet
    stamp("sheets")
    comp = _same_member_components(t, contacts)
    attached_root = np.full(n, -1, dtype=np.int64)
    best_r = np.full(n, -1, dtype=np.int64)
    for _round in range(4):
        root = forest.roots()
        sp, sr, sc = _shares(cpiece, clab, nc, root)
        best_r, share = _best(n, sp, sr, sc, total)
        free = cand & (kind != 3)
        kind[free] = 0
        kind[free & (share >= prm.contents_min)] = 2
        piece_root = np.full(n, -1, dtype=np.int64)
        piece_root[wall & (piece_region >= 0)] = root[piece_region[wall & (piece_region >= 0)]]
        inn = (kind == 2) | (kind == 3)
        piece_root[inn] = best_r[inn]
        if comp is None:
            break
        # B8: one placement's touching component reaching buildings
        held = piece_root >= 0
        pr = np.unique(np.column_stack([comp[held], piece_root[held]]), axis=0)
        joined = False
        if len(pr):
            at = np.flatnonzero(np.r_[True, pr[1:, 0] != pr[:-1, 0]])
            for s0, e0 in zip(at, np.r_[at[1:], len(pr)]):
                for r2 in pr[s0 + 1:e0, 1].tolist():
                    if forest.union(int(pr[s0, 1]), int(r2)):
                        joined = True
                        log.append(("placement", int(pr[s0, 1]), int(r2)))
        root = forest.roots()
        comp_root = np.full(int(comp.max()) + 1 if n else 0, -1, dtype=np.int64)
        if len(pr):
            comp_root[pr[:, 0]] = root[pr[:, 1]]
        ext = (kind == 0) & cand & (comp_root[comp] >= 0)
        attached_root[:] = -1
        attached_root[ext] = comp_root[comp[ext]]
        if not joined:
            break
    stamp("interior+placements")
    root = forest.roots()
    kind[(kind == 0) & (attached_root >= 0)] = 4
    final = np.full(n, -1, dtype=np.int64)
    wsel = wall & (piece_region >= 0)
    final[wsel] = root[piece_region[wsel]]
    sel = (kind == 2) | (kind == 3)
    final[sel] = root[np.maximum(best_r[sel], 0)]
    final[kind == 4] = root[attached_root[kind == 4]]
    if trace:
        counts["trace"] = {"wall_region": dict(zip(t.pid[wsel].tolist(),
                                                   piece_region[wsel].tolist())),
                           "joins": log, "region_root": root.tolist()}
    out = _finish(t, prm, wall, kind, final, root, (bg, bi, ba, bb), counts)
    stamp("record")
    out.counts["seconds"] = round(time.perf_counter() - t0, 3)
    return out


_KIND = {1: WALL, 2: INTERIOR, 3: SHEET, 4: ATTACHED}


def _finish(t, prm, wall, kind, final, root, runs, counts) -> Split:
    """The record: building ids (B9), pieces, buildings in id order."""
    bg, bi, ba, bb = runs
    wsel = np.flatnonzero(wall & (final >= 0))
    bid_of_root: dict[int, int] = {}
    for q in wsel[np.argsort(t.pid[wsel], kind="stable")].tolist():
        bid_of_root.setdefault(int(final[q]), int(t.pid[q]))
    of: dict[int, int] = {}
    kd: dict[int, str] = {}
    per: dict[int, dict[str, set]] = {}
    for q in np.flatnonzero(final >= 0).tolist():
        b = bid_of_root[int(final[q])]
        p = int(t.pid[q])
        of[p] = b
        kd[p] = _KIND[int(kind[q])]
        d = per.setdefault(b, {"walls": set(), "anchors": set(), "members": set()})
        if kind[q] == 1:
            d["walls"].add(p)
        d["anchors"].add(int(t.anchor[q]))
        d["members"].add(int(t.member[q]))
    rb = root[bg] if len(bg) else bg
    kb = np.array([bid_of_root.get(int(r), -1) for r in rb.tolist()], dtype=np.int64)
    # roots re-joined after the runs were merged: merge again by building
    g2, i2, a2, b2 = _pl.merge_runs(kb, bi, ba, bb)
    step = prm.cell_m
    blds = []
    if len(g2):
        at = np.flatnonzero(np.r_[True, g2[1:] != g2[:-1]])
        for s0, e0 in zip(at, np.r_[at[1:], len(g2)]):
            b = int(g2[s0])
            if b < 0:
                continue
            ii, a, z = i2[s0:e0], a2[s0:e0], b2[s0:e0]
            cells = int((z - a + 1).sum())
            d = per[b]
            blds.append(Building(b, tuple(sorted(d["walls"])), tuple(sorted(d["anchors"])),
                                 tuple(sorted(d["members"])), cells, cells * step * step,
                                 (float(a.min() * step), float(ii.min() * step),
                                  float((z.max() + 1) * step), float((ii.max() + 1) * step))))
    blds.sort(key=lambda b: b.id)
    counts.update({"buildings": len(blds),
                   "interior_pieces": int((kind == 2).sum()),
                   "sheet_pieces": int((kind == 3).sum()),
                   "attached_pieces": int((kind == 4).sum())})
    o = np.lexsort((a2, i2))
    return Split(prm, of, kd, tuple(blds),
                 np.column_stack([i2[o], a2[o], b2[o], g2[o]]).astype(np.int64), counts)


def from_placed(parts: _t.Sequence[_t.Any], member_deck: _t.Sequence[bool],
                member_bridge: _t.Sequence[bool], anchor_of_member: _t.Sequence[int],
                footless: _t.Collection[int] = ()) -> PieceTable:
    """The :class:`PieceTable` of the partition's placed parts
    (``contact.PlacedPart``: ``pts`` east / rendered y / north): every
    solid part (no line, no scatter), its member's deck verdicts, its
    anchor, whether it has ground feet (never in a ``footless`` member).
    The heights are rendered (one vertical frame for every anchor)."""
    rows, tx, tt, to = [], [], [], []
    for p in parts:
        if p.line or p.scatter:
            continue
        k = len(rows)
        tri = p.pts[p.tris]
        y = p.pts[:, 1]
        ylo, yhi = float(y.min()), float(y.max())
        sh = float(p.solid_h) if p.solid_h == p.solid_h else yhi - ylo
        mi = int(p.member)
        rows.append((p.pid, mi, int(anchor_of_member[mi]) if len(anchor_of_member) else 0, sh,
                     bool(member_deck[mi]), bool(member_bridge[mi]),
                     bool(p.feet is not None and len(p.feet)) and mi not in footless,
                     float(p.base_y) + (yhi - ylo), ylo))
        tx.append(tri[:, :, [0, 2]])
        tt.append(tri[:, :, 1].max(1))
        to.append(np.full(len(tri), k, dtype=np.int64))
    a = list(zip(*rows)) if rows else [()] * 9
    return PieceTable(np.asarray(a[0], np.int64), np.asarray(a[1], np.int64),
                      np.asarray(a[2], np.int64), np.asarray(a[3], float),
                      np.asarray(a[4], bool), np.asarray(a[5], bool), np.asarray(a[6], bool),
                      np.asarray(a[7], float), np.asarray(a[8], float),
                      np.concatenate(tx) if tx else np.zeros((0, 3, 2)),
                      np.concatenate(tt) if tt else np.zeros(0),
                      np.concatenate(to) if to else np.zeros(0, np.int64))


def of_partition(part, units: _t.Sequence[_t.Any], where: _t.Sequence[tuple[int, int]],
                 anchor_of_member: _t.Sequence[int], law,
                 footless: _t.Collection[int] = ()) -> "Split | None":
    """THE SPLIT of one pack partition at load (spec §10 stop 1): ``part``
    the ``contact.Partition``, ``units`` the pack's units, ``where`` per
    placed member its ``(unit index, member index)``; the record keeps no
    trace.  ``None`` where the law is disarmed (no wall height)."""
    from .placement_family import member_is_bridge_deck, member_is_deck
    prm = Params.from_law(law)
    if prm.tall_m <= 0.0 or prm.cell_m <= 0.0:
        return None
    deck = [member_is_deck(units[u].members[k]) for u, k in where]
    bridge = [member_is_bridge_deck(units[u], units[u].members[k]) for u, k in where]
    t = from_placed(part.parts, deck, bridge, anchor_of_member, footless)
    return split(t, prm, contacts=part.contacts)
