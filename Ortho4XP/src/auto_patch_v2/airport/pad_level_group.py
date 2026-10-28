"""ONE PAD, ONE LEVEL (owner RULINGS 2026-10-28p (2), Q241 a; #1572, #1288).

Owner: "within one shared frame, a unit seated on the same flat pad as the
pad's largest unit, but drawn higher, sinks to that group's level at any
depth.  Units never float off the pad."

:func:`pad_level_links` runs after ``open_frame_seat.unchained_links`` and
composes into its ``root -> the root it moves with`` map.  In ONE frame
(one plan unit: one shared datum), the connected units (§16g roots) whose
plan-wide seat is a PAD (seat source ``pad`` / ``cluster_pad``; the seat's
``where`` names the pad level) are read per pad:

* the pad's LARGEST unit (most parts seated on it) names the target group
  (the group it already moves with, after the contact joins);
* every other group that stands on that one pad (the unit whose zero it
  takes is seated on it, and none of its units on another pad; a
  ground-seated unit chained in rides along, 22o), and whose zero is
  ABOVE the target's by more than ``tol_m``, joins the target group and
  takes its zero: its feet go into the pad (10-22c, 22o: "even if parts
  end up under ground");
* a group drawn LOWER keeps its own zero: joining would lift it off the
  pad (KMCI's building18 units at 305.31 beside a 305.48 garage).

AIRSIDE WINS (RULINGS 2026-10-23e): a group seated on the airside floor is
never moved by this rule.

KMCI (1.0.439): the bad garage's ramp island (``fu:16:6934``, 307.25)
stands on the garage's pad (``building12``, garage ``fu:16:6923`` at
306.61) with nothing within a metre to chain it; its twin at the other
garage was joined only through the adjacent terminal.  A design-copy
congruence join was refuted (the two garages' parts are cut differently).
"""
from __future__ import annotations

import typing as _t

from .open_frame_seat import group_key, unit_root

__all__ = ["PAD_SOURCES", "pad_level_links"]

#: the plan-wide seat sources that stand a unit on a pad level
PAD_SOURCES = frozenset({"pad", "cluster_pad"})


def _pad_seats(u: _t.Any, plan_wide: _t.Mapping[int, tuple]
               ) -> tuple[dict[str, dict[str, int]], dict[str, set[str]], set[str]]:
    """``(pad -> root -> parts seated on it, root -> its pads, roots with a
    part seated off any pad)`` over the parts of frame ``u``."""
    on_pad: dict[str, dict[str, int]] = {}
    pads_of: dict[str, set[str]] = {}
    off_pad: set[str] = set()
    for m in getattr(u, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            seat = plan_wide.get(p.pid)
            if not seat or not seat[0]:
                continue
            r = unit_root(seat[0])
            if len(seat) > 3 and seat[3] in PAD_SOURCES and seat[2]:
                pad = str(seat[2])
                n = on_pad.setdefault(pad, {})
                n[r] = n.get(r, 0) + 1
                pads_of.setdefault(r, set()).add(pad)
            else:
                off_pad.add(r)
    return on_pad, pads_of, off_pad


def _stands_on(g: str, rs: _t.AbstractSet[str], pad: str,
               pads_of: _t.Mapping[str, set[str]], off_pad: _t.AbstractSet[str]) -> bool:
    """Group ``g`` (its units ``rs``) stands on ``pad`` alone: the unit it
    moves with — whose zero is the group's — is seated on that pad only,
    and no unit of it is seated on another pad.  A ground-seated unit
    chained in (a sign post the ramp island touches) rides along (22o)."""
    return (g not in off_pad and pads_of.get(g) == {pad}
            and all(pads_of.get(q, {pad}) <= {pad} for q in rs))


def _note(counts: "dict | None", depth_m: float) -> None:
    if counts is None:
        return
    counts["pad_level_sunk"] = counts.get("pad_level_sunk", 0) + 1
    cm = int(round(100.0 * depth_m))
    counts["pad_level_sunk_cm_max"] = max(counts.get("pad_level_sunk_cm_max", 0), cm)


def pad_level_links(u: _t.Any, plan_wide: _t.Mapping[int, tuple],
                    merged: "_t.Mapping[str, str] | None",
                    zeros: _t.Mapping[str, tuple],
                    airside: "_t.Mapping[str, tuple] | _t.AbstractSet[str]" = frozenset(),
                    counts: "dict | None" = None, tol_m: float = 0.05,
                    movers: "list | None" = None) -> dict[str, str]:
    """``root -> the root it moves with`` in frame ``u``: ``merged``
    (``unchained_links``' answer) composed with the pad-level joins (module
    doc).  ``zeros`` is ``open_frame_seat.root_zeros``' map; ``airside``
    the keys it seated on the airside floor.  ``movers`` (optional) gets
    one ``(group, target, pad, depth m)`` per group sunk."""
    fid = str(getattr(u, "id", ""))
    out = dict(merged or {})
    on_pad, pads_of, off_pad = _pad_seats(u, plan_wide)
    if not on_pad:
        return out

    def zero(g: str) -> "float | None":
        z = zeros.get(group_key(g, fid))
        return None if z is None else float(z[0])
    members: dict[str, set[str]] = {}
    for r in set(pads_of) | off_pad | set(out):
        members.setdefault(out.get(r, r), set()).add(r)
    for pad in sorted(on_pad):
        n = on_pad[pad]
        target = out.get(r := max(sorted(n), key=lambda q: n[q]), r)
        zt = zero(target)
        if zt is None:
            continue
        for g in sorted({out.get(q, q) for q in n} - {target}):
            rs = members.get(g, {g})
            if group_key(g, fid) in airside or not _stands_on(g, rs, pad,
                                                              pads_of, off_pad):
                continue
            zg = zero(g)
            if zg is None or zg - zt <= tol_m:
                continue
            for q in rs:
                out[q] = target
            members.setdefault(target, set()).update(members.pop(g, rs))
            if movers is not None:
                movers.append((g, target, pad, zg - zt))
            _note(counts, zg - zt)
    return out
