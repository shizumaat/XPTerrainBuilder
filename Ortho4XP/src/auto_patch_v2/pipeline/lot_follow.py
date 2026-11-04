"""THE LOT FOLLOWS ITS PAD AFTER STAGE 2 (issue #359; owner RULINGS
2026-10-03c, 2026-10-04p (B) b2) — the follower pass's rewrite, bound by
the caller into ``solve.design.solve_design(follow_rewrite=...)`` (``solve``
may not import ``constraints``, M0 §1; ``solve/follow_stage`` runs it).

THE FOLLOWERS: every vertex of a lot a declared wall terrace stands over
(``PlanarMap.road_terrace['lot_level']['lots']``, ``airport/lot_level``)
LESS every vertex another face
carries — the late stage's held rule (``stage_one_map.late_followers``): a
pad, a road, an airside face, a neighbouring lot keeps the level stage 2
gave it and the lot grades up to it.  Everything else is a constant at its
stage-2 level.

THE ROWS: stage 2's own set less every row with no follower in it
(``stage_one_map.late_constraints``), plus one lot-level row
(:data:`LOT_FOLLOW_RULING`, 10-03c's lot level) per follower the derived map
pairs with a pad (``['lot_level']['pairs']``): ``z_lot - z_pad = 0``
wherever the lot's own caps allow it, and otherwise the pad's level CLAMPED
into the follower's cap window — the levels every chain of the set's
``Diff`` caps from a constant leaves it (:func:`cap_windows`).  The row and
the caps then never disagree, so the lot is flat at the pad and ramps AT
its cap to a road or a neighbour that stands at another level.  MEASURED
HECA (``dsf:objpav394``): with the bare ``= 0`` row the caps and the row,
both at the law weight, met half way — the median follower 0.67 m off its
pad and 7 cap rows broken by up to 0.085 m; with the window, the lot's
bending to the roads beside it still held the median there until the row
was priced at the pad's own flatness (:data:`LOT_FOLLOW_RULING`).  The pad is a
constant here, so the row only ever moves the lot: no loop, no leader to
lose (stage 2's two-way coupling sank ``building8`` 1.13 m at HECA)."""
from __future__ import annotations

import heapq
import typing as _t

from ..model.constraints import ConstraintSet, Linear, Source
from ..model.planar import PlanarMap, face_vertex_set

__all__ = ["LOT_FOLLOW_RULING", "lot_followers", "lot_follow_rewrite", "cap_windows"]

#: the follower pass's lot-level row: the 10-03c lot level, registered in
#: ``[design] one_way_rulings``, ``pad_level_rulings`` (a vertex it levels
#: follows its pad and leaves its body's terrain datum, as a fronting pad's
#: vertex does) and ``pad_flat_rulings`` (priced at the pad's own flatness,
#: ``[design] pad_flat``, over the caps' ``law``: its targets sit inside
#: the cap windows, so the price never buys a broken cap)
LOT_FOLLOW_RULING = ("structures.wall_terrace lot level, follower pass "
                     "(owner 2026-10-03c, 2026-10-04p (B) b2; issue #359)")

#: metres either side of the target: a BAND, not an equality — the design
#: solve prices an equality at ``law`` whatever its register, a band's two
#: one-sided rows at their register's price; under the 0.01 m elevation
#: materiality
_LEVEL_SLACK_M = 0.005


def _record(pm: PlanarMap) -> _t.Mapping:
    return (getattr(pm, "road_terrace", None) or {}).get("lot_level") or {}


def lot_followers(pm: PlanarMap) -> set[int]:
    """The follower vertices (module docstring)."""
    lots = {int(f) for f in _record(pm).get("lots") or ()} & set(pm.faces)
    if not lots:
        return set()
    free: set[int] = set()
    held: set[int] = set()
    for f in pm.faces.values():
        (free if f.id in lots else held).update(face_vertex_set(pm, f))
    return free - held


def cap_windows(cs: ConstraintSet, fixed: _t.Mapping[int, float],
                free: _t.AbstractSet[int]) -> dict[int, tuple[float, float]]:
    """``{follower: (lo, hi)}``: the levels the set's ``Diff`` caps leave
    each follower reachable from the constants — ``hi`` the least of
    ``z_u + sum(cap x d)`` over every cap chain from a constant ``u``, ``lo``
    the greatest of ``z_u - sum(cap x d)`` (a row's relief target ``rel``
    narrows its edge).  A follower no chain reaches is unbounded."""
    adj: dict[int, list[tuple[int, float]]] = {}
    for d in cs.diffs:
        a, b = int(d.a), int(d.b)
        if a not in free and b not in free:
            continue
        w = max(0.0, float(d.cap) * float(d.d) - abs(float(getattr(d, "rel", 0.0))))
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))

    def walk(sign: float) -> dict[int, float]:
        # multi-source shortest path from every constant, in sign x z
        best: dict[int, float] = {}
        heap = [(sign * float(fixed[u]), u) for u in adj if u not in free and u in fixed]
        heapq.heapify(heap)
        while heap:
            k, u = heapq.heappop(heap)
            if u in best:
                continue
            best[u] = k
            for w, dw in adj.get(u, ()):
                if w in free and w not in best:
                    heapq.heappush(heap, (k + dw, w))
        return {v: sign * k for v, k in best.items() if v in free}
    hi, lo = walk(1.0), walk(-1.0)
    inf = float("inf")
    return {v: (lo.get(v, -inf), hi.get(v, inf)) for v in free}


def lot_follow_rewrite(pm: PlanarMap, cs: ConstraintSet, z: _t.Sequence[float]
                       ) -> tuple[ConstraintSet, dict[int, float], dict] | None:
    """``(rows, constants, report)`` of the follower pass, or ``None`` when
    no lot follows (the pass does not run)."""
    from .stage_one_map import late_constraints
    free = lot_followers(pm)
    pairs = _record(pm).get("pairs") or {}
    level = {v: q for v, q in pairs.items() if v in free and q not in free}
    if not level:
        return None
    fixed = {v: float(z[v]) for v in range(len(z)) if v not in free}
    kept, dropped = late_constraints(cs, fixed)
    win = cap_windows(kept, fixed, free)
    rows, clamped = [], 0
    for v, q in sorted(level.items()):
        lo, hi = win[v]
        # two constants the caps cannot both reach: between them
        t = min(max(fixed[q], lo), hi) if lo <= hi else 0.5 * (lo + hi)
        off = t - fixed[q]
        clamped += abs(off) > 0.0
        rows.append(Linear(((int(v), 1.0), (int(q), -1.0)),
                           off - _LEVEL_SLACK_M, off + _LEVEL_SLACK_M,
                           Source("wall_terrace", LOT_FOLLOW_RULING,
                                  (f"vertex:{v}",)),
                           follows=(int(v),)))
    cs_f = ConstraintSet.from_rows([*kept.rows(), *rows])
    return cs_f, fixed, {"followers": len(free), "lot_level_rows": len(rows),
                         "clamped_to_cap": clamped, "dropped": dropped}
