"""THE TOUCHING-PAIR CENSUS (owner RULINGS 2026-11-16k/u/v, #2110; spec
2110-R3 §4): two bodies of one frame whose parts touch in plan.

Owner, 19:05:40Z: "Yes, touching buildings need to stay grouped".  The
census reads a placement plan's bodies (``to_dict`` rows) against the
rebake plan's parts and lists every PAIR of bodies of ONE frame (plan
unit: one anchor, so the authored zeros are comparable) that TOUCH by the
law's own relation (``touch_graph.touch_pairs``: part rings within
``touch_m``, the vertical veto; a LINE part touches nothing, RULINGS
2026-11-14a (2); §10 segments and basin members are no nodes), with the
step between their zeros; pairs of two frames are listed, not judged.
:func:`group_lines` prints a ``touch_seat`` table (the replay's
``--touch-out``) and :func:`base_lines` the bodies whose zero moved
against a control plan (rises, the sink histogram, what the pass did not
move).

Read-only: an instrument, never a law reader.
"""
from __future__ import annotations

import typing as _t

from .touch_graph import local_metres  # noqa: F401  (re-exported)

__all__ = ["census_touching_steps", "touching_lines", "group_lines",
           "base_lines", "local_metres", "TOUCH_M", "WALLED_M"]

#: #2110 R3 §1.2's ``[placement] touch_gap_m``
TOUCH_M = 0.1
#: §16g (10) (4)'s ``[placement] chain_min_height_m``
WALLED_M = 2.5
_DRAPED = ("line_segment", "basin")


def _member_key(res: str, lat: float, lon: float) -> tuple:
    return (str(res), round(float(lat), 6), round(float(lon), 6))


def census_touching_steps(rebake: _t.Any, splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                          touch_m: float = TOUCH_M) -> dict:
    """``{"pairs": [(step, frame, body a, body b, kinds, both buildings), ...]
    (worst first), "bodies": n, "cross": [...]}`` over ``rebake`` (a
    ``RebakePlan``) and the placement plan's ``splits``: every pair of ONE
    frame that touches by ``touch_graph.touch_pairs`` — the very relation
    the law groups by (rings within ``touch_m``, the vertical veto) — and
    the pairs of two frames, listed."""
    from . import touch_graph as _tg
    nodes = _plan_nodes(rebake, splits)
    pairs, cross = _tg.touch_pairs(nodes, touch_m)
    out = []
    for (i, j), d in pairs.items():
        A, B = nodes[i], nodes[j]
        out.append((d, A.frame, A.name, B.name, f"{A.kind[0]}{B.kind[0]}",
                    A.kind == B.kind == _tg.BUILDING))
    out.sort(key=lambda r: -r[0])
    return {"pairs": out, "bodies": len(nodes), "touch_m": touch_m, "cross": cross}


def _plan_nodes(rebake: _t.Any, splits: _t.Sequence[_t.Mapping[str, _t.Any]],
               walled_m: float = WALLED_M) -> list:
    """``touch_graph.Node``s of a placement plan's ``to_dict`` rows; a node's
    ``key`` is ``(placement index, body_id)``."""
    from . import touch_graph as _tg
    from .dsf import row_of
    by_index, by_key = {}, {}
    for u in rebake.units:
        for m in u.members:
            _t_, row = row_of(m.id)
            if row is not None and _t_ is None:
                by_index[(row, m.resource)] = (u, m)
            org = getattr(m, "origin", None) or u.anchor
            by_key[_member_key(m.resource, org[0], org[1])] = (u, m)
    nodes = []
    for s in splits:
        pl = s.get("placement") or {}
        res = str(pl.get("resource", ""))
        um = by_index.get((pl.get("index"), res)) or by_key.get(
            _member_key(res, pl.get("lat", 0.0), pl.get("lon", 0.0)))
        if um is None:
            continue
        u, m = um
        parts = {p.comp: p for p in m.parts}
        for b in s.get("bodies", ()):
            if b.get("surface_z") is None or b.get("class") in _DRAPED:
                continue
            ps = [parts[c] for c in b.get("components", ()) if c in parts
                  and not parts[c].line]
            if not ps:
                continue
            kind = (_tg.CONNECTOR if not b.get("feet") else _tg.BUILDING
                    if any(p.height_m >= walled_m for p in ps) else _tg.GROUND)
            nodes.append(_tg.Node(
                (pl.get("index"), b.get("body_id")), str(u.id),
                str(b.get("new_resource") or f"{res}#{b.get('body_id')}"),
                float(b["surface_z"]) - float(b.get("y_zero", 0.0)), kind,
                str(b.get("family_of") or "").split("/", 1)[0].split("@", 1)[0],
                ps, float(b.get("lift_m", 0.0) or 0.0)))
    return nodes


def touching_lines(census: dict, top: int = 15) -> list[str]:
    """The step table the tools print."""
    ps = census["pairs"]
    w = [p for p in ps if p[5]]
    out = [f"   --- TOUCHING PAIRS (RULINGS 2026-11-16k/u): {len(ps)} body pair(s) "
           f"within {census['touch_m']:g} m over {census['bodies']} bodies; "
           f"{len(census.get('cross', ()))} cross-frame pair(s) not judged ---"]
    for lab, rows in (("all", ps), ("bld~bld", w)):
        out.append(f"   {lab:7s} >0.05 m {sum(1 for p in rows if p[0] > 0.05):5d}  "
                   f">0.3 m {sum(1 for p in rows if p[0] > 0.3):5d}  >1 m "
                   f"{sum(1 for p in rows if p[0] > 1.0):5d}  >2 m "
                   f"{sum(1 for p in rows if p[0] > 2.0):5d}  worst "
                   f"{(rows[0][0] if rows else 0.0):.2f}")
    for d, fid, a, b, k, _w in ps[:top]:
        out.append(f"      {d:6.2f} m  {fid}  {a.rsplit('/', 1)[-1]} ~ "
                   f"{b.rsplit('/', 1)[-1]} ({k})")
    return out


def group_lines(table: _t.Mapping[str, _t.Any], top: int = 15) -> list[str]:
    """A ``touch_seat`` table: the groups by S class, the moves, the fixed
    bodies by reason, the small low members and the cross-frame pairs."""
    gs = list(table.get("groups", ()))
    out = ["   --- TOUCHING GROUPS (spec 2110-R3 §2) ---"]
    for c in ("flat", "seat", "level", "judge", "pads"):
        cg = [g for g in gs if g["class"] == c]
        out.append(f"   {c:6s} {len(cg):5d} group(s)  {sum(g['bodies'] for g in cg):6d} bodies"
                   f"  moved {sum(g['moves'] for g in cg):5d}")
    out.append(f"   moved bodies {len(table.get('moved', ()))} (riders included); "
               f"small low members {sum(len(g['small_low']) for g in gs)}; "
               f"followers kept low {sum(g['kept_low'] for g in gs)}, high "
               f"{sum(g.get('kept_high', 0) for g in gs)}")
    out.append("   fixed: " + ", ".join(f"{k} {v}" for k, v in
                                        sorted(table.get("fixed", {}).items())))
    out.append(f"   cross-frame pairs (not judged): {table.get('cross_frame_pairs', 0)}; "
               f"unit rows left at the old zero: {len(table.get('unit_rows_left', ()))}")
    inside = table.get("inside_steps", ())
    out.append(f"   touching pairs > tol left INSIDE seated groups (B4): {len(inside)}"
               + (f" (worst {inside[0][0]:.2f})" if inside else ""))
    made = table.get("fixed_steps", ())
    out.append(f"   steps a move opened against a body it may not move: {len(made)}"
               + (f" (worst {made[0][0]:.2f})" if made else ""))
    for d, a, b, why in list(made)[:5]:
        out.append(f"      OPENED {d:.2f}  {a.rsplit('/', 1)[-1]} ~ {b.rsplit('/', 1)[-1]} ({why})")
    for g in sorted(gs, key=lambda g: -g["S"])[:top]:
        out.append(f"      {g['class']:5s} S {g['S']:5.2f}  Z {g['Z']:8.2f}  {g['root']}  "
                   f"{g['buildings']}/{g['bodies']} bld/bodies  step {g['step']:.2f}"
                   f"  moved {g['moves']}")
    return out


def _bid(v: _t.Any) -> str:
    """A body id as the plan spells it (``b7``) or the split set (7)."""
    return str(v).lstrip("b")


def base_lines(arm: _t.Sequence[_t.Mapping], base: _t.Sequence[_t.Mapping],
               moved: _t.Iterable[_t.Sequence] = (), tol_m: float = 0.05) -> list[str]:
    """Every body (placement index, body id) whose zero differs from the
    base plan's: rises of footed bodies (B1), the sink histogram of footed
    buildings, and the changes the touch pass did not make (B2:
    ``moved`` = the table's ``(index, body_id, ...)`` rows)."""
    from .placement_coherence import plan_body_zero

    def zeros(splits: _t.Sequence[_t.Mapping]) -> dict:
        out = {}
        for s in splits:
            ix = (s.get("placement") or {}).get("index")
            for b in s.get("bodies", ()):
                z = plan_body_zero(b)
                if z is not None:
                    out[(ix, _bid(b.get("body_id")))] = (z, int(b.get("feet") or 0), b)
        return out
    A, B = zeros(arm), zeros(base)
    ours = {(r[0], _bid(r[1])) for r in moved}
    rises, sinks, other = [], [], []
    for k in sorted(set(A) & set(B), key=str):
        d = A[k][0] - B[k][0]
        if abs(d) <= tol_m:
            continue
        if d > 0 and A[k][1]:
            rises.append((d, A[k][2].get("new_resource")))
        if d < 0 and A[k][1]:
            sinks.append(-d)
        if k not in ours:
            other.append((d, A[k][2].get("new_resource")))
    bins = (0.05, 0.1, 0.2, 0.3, 0.4, 0.75, 1.0)
    tops = bins[1:] + (99.0,)
    hist = [sum(1 for x in sinks if lo < x <= hi)
            for lo, hi in zip(bins, tops, strict=True)]
    out = [f"   --- AGAINST THE BASE PLAN (> {tol_m:g} m) ---",
           f"   footed rises {len(rises)}  worst {max((r[0] for r in rises), default=0.0):.2f}",
           f"   footed sinks {len(sinks)}  worst {max(sinks, default=0.0):.2f}  by bin "
           + "  ".join(f"<={hi:g}:{n}" for hi, n in zip(tops, hist, strict=True)),
           f"   changed by another pass (not in the table): {len(other)}"]
    for d, name in sorted(rises, reverse=True)[:10]:
        out.append(f"      RISE {d:+.2f}  {name}")
    for d, name in sorted(other, key=lambda r: -abs(r[0]))[:10]:
        out.append(f"      OTHER {d:+.2f}  {name}")
    return out
