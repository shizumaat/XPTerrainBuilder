"""TOUCHING BUILDINGS STAY GROUPED (owner RULINGS 2026-11-16k, #2110;
narrows 2026-10-22o).

Owner, 19:05:40Z: "Yes, touching buildings need to stay grouped" —
building components, of one placement or of different placements or §16g
units, that touch share ONE datum (one group zero); a fence or wall
between them does not chain them (RULINGS 2026-11-14a (2) stands).

:func:`touch_links` runs after ``open_frame_seat.unchained_links`` and
composes into its ``root -> the root it moves with`` map.  In ONE frame
(one plan unit: one shared datum, so one zero keeps the author's
relation) two connected units (§16g roots) are one group where

* their parts come within ``touch_m`` (§16g's ``footprint_touch_m``) of
  each other — rings, a part's plan box where it has none — whatever §16g
  kept apart (a thin leaf, §16g (10) (4); another authored floor level,
  §16g (10)); an UNCHAINED part counts as the unit its body, or the body
  it rests on, is mostly in (:func:`_part_roots`);
* ONE staged body holds parts of both: a body is one rigid piece (LOWS:
  Terminal_LOWS_59 b3 holds 82 parts of the terminal's ``fu:2:10907`` and
  2 of the north building's ``fu:2:10895``, seated 0.24 m apart).

A LINE part (``Part.line``: a fence, wall or barrier) is never a node, so
it joins nothing.  The group moves with ``open_frame_seat.group_keep``'s
root — airside first (23e: the share whose airside floor the most feet
read), else the largest — the one rule the other within-frame joins
read.  A body of NO unit touching a unit takes it too (``touched``,
``open_frame_seat.body_root``).
"""
from __future__ import annotations

import math
import typing as _t

from .open_frame_seat import group_keep, resolved, unit_root

__all__ = ["touch_links", "local_metres"]


def local_metres(la0: float, lo0: float
                 ) -> _t.Callable[[float, float], tuple[float, float]]:
    """``(lat, lon) -> (x, y)`` metres about ``(la0, lo0)``."""
    ml, mo = 111132.0, 111320.0 * math.cos(math.radians(la0))
    return lambda la, lo: ((lo - lo0) * mo, (la - la0) * ml)


def _rests(st: _t.Any) -> _t.Iterator[tuple[_t.Sequence[int], frozenset[int]]]:
    """``(raw indices, the carrier's parts)`` of each body a staged member
    rests on another member's body (its ``carried`` groups) — none where
    the carrier search answered with a no-evidence fallback
    (``free_column.fallback_only``: no contact, so no touch)."""
    from .free_column import fallback_only
    for g, c, why in getattr(st, "carried", ()) or ():
        if not fallback_only([(c, why)]):
            yield g, frozenset(getattr(c, "pids", ()) or ())


def _majority(pids: _t.Iterable[int], plan_wide: _t.Mapping[int, tuple]) -> "str | None":
    """The connected unit most of ``pids`` are seated in (``body_root``'s
    reading), or ``None``."""
    n: dict[str, int] = {}
    for q in pids:
        seat = plan_wide.get(q)
        if seat and seat[0]:
            r = unit_root(seat[0])
            n[r] = n.get(r, 0) + 1
    return max(sorted(n), key=lambda r: n[r]) if n else None


def _part_roots(u: _t.Any, staged: _t.Sequence[_t.Any],
                plan_wide: _t.Mapping[int, tuple],
                spans: "list[set[str]] | None" = None) -> dict[int, str]:
    """``pid -> connected unit`` of every part of frame ``u`` the joins
    read: a chained part's own unit; an unchained part of a staged group
    the unit most of its raw body's parts are in, else its group's (a
    body: ``Staged.groups`` / ``carried`` / ``unit_carried`` /
    ``own_ground``), else the unit most of the parts it RESTS on are in
    (:func:`_rests`), else the §16g unit that carries it
    (``unit_carried``).  ``spans`` is filled with the units each staged
    body holds (its non-line parts')."""
    out = {p.pid: unit_root(plan_wide[p.pid][0])
           for m in getattr(u, "members", ()) or () for p in getattr(m, "parts", ()) or ()
           if plan_wide.get(p.pid) and plan_wide[p.pid][0]}
    under = {}
    spans = [] if spans is None else spans
    for st in staged:
        raw = getattr(st, "raw", ()) or ()
        for g, pids in _rests(st):
            cr = _majority(pids, plan_wide)
            if cr is not None:
                for i in g:
                    for p in (raw[i][0] if i < len(raw) else ()):
                        under.setdefault(p.pid, cr)
        for g, uc in getattr(st, "unit_carried", ()) or ():
            if getattr(uc, "unit", ""):
                for i in g:
                    for p in (raw[i][0] if i < len(raw) else ()):
                        under.setdefault(p.pid, unit_root(uc.unit))
        groups = list(getattr(st, "groups", ()) or ()) + [
            g for g, *_r in getattr(st, "carried", ()) or ()] + [
            g for g, *_r in getattr(st, "unit_carried", ()) or ()] + list(
            getattr(st, "own_ground", ()) or ())
        for g in groups + [[i] for i in range(len(raw))]:
            pids = [p.pid for i in g if i < len(raw) for p in raw[i][0]]
            r = _majority(pids, plan_wide)
            for q in pids:
                if q not in out and r is not None:
                    out[q] = r
        spans.extend({out[q] for i in g if i < len(raw) for p in raw[i][0]
                      if (q := p.pid) in out and not getattr(p, "line", False)}
                     for g in groups)
    for q, r in under.items():
        out.setdefault(q, r)
    return out


def _ground_spans(u: _t.Any, plan_wide: _t.Mapping[int, tuple],
                  size: dict[str, int]) -> dict[str, tuple[float, float]]:
    """``root -> (zero, zero)`` of every connected unit of frame ``u``
    holding a FOOTED part (a ground contact): the median of its parts'
    plan-wide zeros — the unit's own seat.  ``size`` is filled with the
    parts per root."""
    zs: dict[str, list[float]] = {}
    footed: set[str] = set()
    for m in getattr(u, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            seat = plan_wide.get(p.pid)
            if not seat or not seat[0]:
                continue
            r = unit_root(seat[0])
            size[r] = size.get(r, 0) + 1
            if len(seat) > 1 and seat[1] is not None:
                zs.setdefault(r, []).append(float(seat[1]))
            if getattr(p, "feet", ()):
                footed.add(r)
    out = {}
    for r in footed & set(zs):
        v = sorted(zs[r])
        out[r] = (v[len(v) // 2], v[len(v) // 2])
    return out


def _footprints(u: _t.Any, roots: _t.Mapping[int, str]
                ) -> tuple[list, list[tuple["str | None", int]]]:
    """``(polygons in local metres, (root or None, pid) of each)`` over
    frame ``u``'s non-line parts: each part's rings, its plan box where it
    has none."""
    from shapely.geometry import Polygon
    from shapely.geometry import box as _box
    xy = local_metres(*(float(q) for q in u.anchor))
    geoms, owner = [], []
    for m in getattr(u, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            r = roots.get(p.pid)
            if getattr(p, "line", False):
                continue
            gs = [Polygon([xy(la, lo) for la, lo in rg])
                  for rg in getattr(p, "rings", ()) or () if len(rg) >= 3]
            if not gs and getattr(p, "box", None):
                (x0, y0), (x1, y1) = xy(p.box[0], p.box[1]), xy(p.box[2], p.box[3])
                gs = [_box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))]
            for g in gs:
                g = g if g.is_valid else g.buffer(0.0)
                if not g.is_empty:
                    geoms.append(g)
                    owner.append((r, p.pid))
    return geoms, owner


def touch_links(u: _t.Any, staged: _t.Sequence[_t.Any], plan_wide: _t.Mapping[int, tuple],
                merged: "_t.Mapping[str, str] | None" = None,
                airside: "_t.Mapping[str, tuple] | _t.AbstractSet[str]" = frozenset(),
                counts: "dict | None" = None, touch_m: float = 0.5,
                touched: "dict[int, str] | None" = None,
                ground_m: float = 0.5) -> dict[str, str]:
    """``root -> the root it moves with`` inside frame ``u``: ``merged``
    (the joins before this one) with the touching joins of the module doc.
    ``staged``: the frame's staged members (:func:`_part_roots`).
    ``touched``, when given, is filled with ``pid -> unit`` for every part
    of no unit and no feet that touches a unit's part (the least such unit
    by name): a footless body of no unit takes the group it touches.
    ``ground_m`` (``[cockpit] visual_m``): a join that would put FOOTED
    units whose own seats lie more than this apart into one group is
    refused and counted (``touch_joins_refused_ground``) — one zero would
    float or bury a building standing on its own ground."""
    base = dict(merged or {})
    up: dict[str, str] = {}

    def find(r: str) -> str:
        up.setdefault(r, r)
        while up[r] != r:
            up[r] = up[up[r]]
            r = up[r]
        return r

    size: dict[str, int] = {}
    ground = _ground_spans(u, plan_wide, size)
    refused = 0

    def join(a: str, b: str, guard: bool = True) -> bool:
        nonlocal refused
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        ga, gb = ground.get(ra), ground.get(rb)
        if ga and gb:
            lo, hi = min(ga[0], gb[0]), max(ga[1], gb[1])
            if guard and hi - lo > ground_m:
                refused += 1
                return False
            ground[rb] = (lo, hi)
        elif ga:
            ground[rb] = ga
        up[ra] = rb
        return True
    for r, t in base.items():
        join(r, t, guard=False)
    n_join = 0
    spans: list[set[str]] = []
    roots = _part_roots(u, staged, plan_wide, spans)
    for rs in spans:
        rs = sorted(rs)
        for r in rs[1:]:
            n_join += join(rs[0], r)
    geoms, owner = _footprints(u, roots)
    footed = {p.pid for m in getattr(u, "members", ()) or ()
              for p in getattr(m, "parts", ()) or () if getattr(p, "feet", ())}
    if geoms and (touched is not None
                  or len({o[0] for o in owner if o[0] is not None}) > 1):
        from shapely.strtree import STRtree
        a, b = STRtree(geoms).query(geoms, predicate="dwithin", distance=touch_m)
        for i, j in zip(a.tolist(), b.tolist(), strict=True):
            (ri, pi), (rj, pj) = owner[i], owner[j]
            if i >= j or ri == rj:
                continue
            if ri is not None and rj is not None:
                n_join += join(ri, rj)
            elif touched is not None and pi not in footed and pj not in footed:
                # a part of no unit touching a unit's part joins that unit
                # (``open_frame_seat.body_root``'s ``touched``)
                q, r = (pi, rj) if ri is None else (pj, ri)
                if r < touched.get(q, "\uffff"):
                    touched[q] = r
    if counts is not None and refused:
        counts["touch_joins_refused_ground"] = \
            counts.get("touch_joins_refused_ground", 0) + refused
    if not n_join:
        return base
    comp: dict[str, set[str]] = {}
    for r in list(up):
        comp.setdefault(find(r), set()).add(r)
    fid = str(getattr(u, "id", ""))
    out = dict(base)
    for rs in comp.values():
        if len(rs) < 2:
            continue
        keep = group_keep(rs, fid, airside, size)
        for r in rs:
            if r != keep:
                out[r] = keep
            else:
                out.pop(r, None)
    if counts is not None:
        counts["touch_joins"] = counts.get("touch_joins", 0) + n_join
    return resolved(out)
