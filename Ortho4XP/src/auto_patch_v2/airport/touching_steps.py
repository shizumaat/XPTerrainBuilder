"""THE TOUCHING-PAIR CENSUS (owner RULINGS 2026-11-16k, #2110): two bodies
of one frame whose parts touch in plan stand at one zero.

Owner, 19:05:40Z: "Yes, touching buildings need to stay grouped".  The
census reads a placement plan's bodies (``to_dict`` rows) against the
rebake plan's parts and lists every PAIR of bodies of ONE frame (plan
unit: one anchor, so the authored zeros are comparable) whose part
footprints come within ``touch_m`` — part rings, a part's plan box where
it has no ring — with the step between their zeros
(``placement_coherence.plan_body_zero``).  A LINE part (a fence, wall or
barrier, ``Part.line``) touches nothing (RULINGS 2026-11-14a (2)), and a
§10 line segment's bodies drape by ruling.  A body is WALLED when one of
its parts stands ``chain_min_height_m`` tall (§16g (10) (4)).

Read-only: an instrument, never a law reader.
"""
from __future__ import annotations

import typing as _t

__all__ = ["census_touching_steps", "touching_lines", "TOUCH_M", "WALLED_M"]

#: §16g (1)'s ``[placement] footprint_touch_m``
TOUCH_M = 0.5
#: §16g (10) (4)'s ``[placement] chain_min_height_m``
WALLED_M = 2.5
_DRAPED = ("line_segment",)


def _member_key(res: str, lat: float, lon: float) -> tuple:
    return (str(res), round(float(lat), 6), round(float(lon), 6))


def census_touching_steps(rebake: _t.Any, splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                          touch_m: float = TOUCH_M) -> dict:
    """``{"pairs": [(step, frame, body a, body b, part pairs, walled), ...]
    (worst first), "bodies": n}`` over ``rebake`` (a ``RebakePlan``) and
    the placement plan's ``splits``."""
    from shapely.geometry import Polygon
    from shapely.geometry import box as _box
    from shapely.strtree import STRtree

    from .dsf import row_of
    from .placement_coherence import plan_body_zero
    from .touch_group import local_metres
    by_index, by_key = {}, {}
    for u in rebake.units:
        for m in u.members:
            _t_, row = row_of(m.id)
            if row is not None and _t_ is None:
                by_index[(row, m.resource)] = (u, m)
            org = getattr(m, "origin", None) or u.anchor
            by_key[_member_key(m.resource, org[0], org[1])] = (u, m)
    frames: dict[str, list] = {}
    nbod = 0
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
            z = plan_body_zero(b)
            if z is None or b.get("class") in _DRAPED:
                continue
            ps = [parts[c] for c in b.get("components", ()) if c in parts
                  and not parts[c].line]
            if not ps:
                continue
            nbod += 1
            name = str(b.get("new_resource") or f"{res}#{b.get('body_id')}")
            frames.setdefault(str(u.id), []).append(
                (name, z, ps, any(p.height_m >= WALLED_M for p in ps), u.anchor))
    out = []
    for fid, bodies in frames.items():
        xy = local_metres(*bodies[0][4])
        geoms, owner = [], []
        for bi, (_n, _z, ps, _w, _a) in enumerate(bodies):
            for p in ps:
                gs = [Polygon([xy(la, lo) for la, lo in rg]) for rg in p.rings if len(rg) >= 3]
                if not gs:
                    x0, y0 = xy(p.box[0], p.box[1])
                    x1, y1 = xy(p.box[2], p.box[3])
                    gs = [_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))]
                for g in gs:
                    g = g if g.is_valid else g.buffer(0.0)
                    if not g.is_empty:
                        geoms.append(g)
                        owner.append(bi)
        if len(geoms) < 2:
            continue
        a, c = STRtree(geoms).query(geoms, predicate="dwithin", distance=touch_m)
        n: dict[tuple[int, int], int] = {}
        for i, j in zip(a.tolist(), c.tolist(), strict=True):
            bi, bj = owner[i], owner[j]
            if bi < bj:
                n[(bi, bj)] = n.get((bi, bj), 0) + 1
        for (bi, bj), k in n.items():
            A, B = bodies[bi], bodies[bj]
            out.append((abs(A[1] - B[1]), fid, A[0], B[0], k, A[3] and B[3]))
    out.sort(key=lambda r: -r[0])
    return {"pairs": out, "bodies": nbod, "touch_m": touch_m}


def touching_lines(census: dict, top: int = 15) -> list[str]:
    """The step table the tools print."""
    ps = census["pairs"]
    w = [p for p in ps if p[5]]
    out = [f"   --- TOUCHING PAIRS (RULINGS 2026-11-16k): {len(ps)} body pair(s) "
           f"within {census['touch_m']:g} m over {census['bodies']} bodies ---"]
    for lab, rows in (("all", ps), ("walled", w)):
        out.append(f"   {lab:7s} >0.05 m {sum(1 for p in rows if p[0] > 0.05):5d}  "
                   f">0.3 m {sum(1 for p in rows if p[0] > 0.3):5d}  worst "
                   f"{(rows[0][0] if rows else 0.0):.2f}")
    for d, fid, a, b, k, wl in ps[:top]:
        out.append(f"      {d:6.2f} m  {fid}  {a.rsplit('/', 1)[-1]} ~ "
                   f"{b.rsplit('/', 1)[-1]} ({k} part pair(s){', walled' if wl else ''})")
    return out
