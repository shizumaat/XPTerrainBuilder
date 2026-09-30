"""THE OBJECT CUT AT THE BLOCK BOUNDARY (flat-pad spec §3 C15/C16 as ruled
2026-09-30r, Q-111b option (1); issue #111; #112 (2)(b)).

A unit platform the mint CUT into flat blocks (``planar/pad_blocks`` ->
faces ``<unit>/b<k>`` and ``<unit>/b<k>#collar``, published to the object
stage by ``placement_read._collars_as_platform`` under the block ref) is
seated block by block: each block is its OWN seated object.  Two joins make
that so, both keyed on WHERE A PART STANDS (the part's plan centroid inside
a block's published rings) — never on a pid the planar stage saw, because
the load partition and the filtered rebake plan number their parts
differently (``pack_partition`` module docstring):

* :func:`sever` drops every ε-contact (and 10ay abutment) pair whose two
  parts stand on DIFFERENT blocks of ONE unit — the contact graph is cut at
  the neck the mint chose, so §9's bodies, the cutters' own edges and every
  reader of ``plan.contacts`` see two bodies where the neck was.  This
  reverses 17x's contact-pair bar FOR THESE UNITS ONLY (30n option (1): the
  walls step at the block boundary).
* :func:`split_units` splits a §16g footprint unit whose bodies stand on
  two or more blocks of one unit into one unit per block (``<id>/b<k>``),
  so ``plan_unit_datums`` seats each on its own block's flat floor and
  ``placement_plan._split_by_unit`` never lets one FILE straddle two
  blocks.  A body standing on no block of the unit joins the block it
  stands nearest.

The cut FILES come from the pristine backup exactly as every other split
does (``obj8_split.split_obj8`` reads ``.anchor_bak`` — restore-before-
read): nothing here reads or writes an object.  Pure reading; no law
constant lives here."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..model.planar import block_of
from . import anchor_rule as _ar

__all__ = ["block_rings", "part_blocks", "sever", "split_units"]


def block_rings(pads: _t.Sequence[_ar.PadRing]
                ) -> list[tuple[str, int, tuple, tuple[float, float, float, float]]]:
    """``(unit, k, ring, (min_lat, min_lon, max_lat, max_lon))`` for every
    published ring of a BLOCK pad (``model.planar.block_of``)."""
    out = []
    for p in pads:
        b = block_of(p.ref)
        if b is None or len(p.ring) < 3:
            continue
        la = [v[0] for v in p.ring]
        lo = [v[1] for v in p.ring]
        out.append((b[0], b[1], tuple(p.ring), (min(la), min(lo), max(la), max(lo))))
    return out


def _block_at(rings, la: float, lo: float) -> "tuple[str, int] | None":
    for unit, k, ring, (y0, x0, y1, x1) in rings:
        if y0 <= la <= y1 and x0 <= lo <= x1 and _ar._inside(ring, la, lo):
            return unit, k
    return None


def part_blocks(plan: _t.Any, pads: _t.Sequence[_ar.PadRing]
                ) -> dict[int, tuple[str, int]]:
    """``part id -> (unit, block)`` for every part whose plan centroid
    stands inside a block pad's ring; parts elsewhere are absent."""
    rings = block_rings(pads)
    if not rings:
        return {}
    out: dict[int, tuple[str, int]] = {}
    for u in getattr(plan, "units", ()):
        for m in u.members:
            for p in m.parts:
                b = _block_at(rings, float(p.lat), float(p.lon))
                if b is not None:
                    out[p.pid] = b
    return out


def _crosses(of: _t.Mapping[int, tuple[str, int]], a: int, b: int) -> bool:
    ba, bb = of.get(a), of.get(b)
    return ba is not None and bb is not None and ba[0] == bb[0] and ba[1] != bb[1]


def sever(plan: _t.Any, pads: _t.Sequence[_ar.PadRing],
          abutments: _t.Sequence[tuple[int, int]] = ()
          ) -> tuple[_t.Any, tuple[tuple[int, int], ...], dict[str, int]]:
    """``(plan with the cross-block pairs dropped, the caller's
    ``abutments`` filtered the same way, counts)`` — the plan itself when
    no block pad is published."""
    of = part_blocks(plan, pads)
    counts = {"block_parts": len(of), "block_contacts_cut": 0,
              "block_abutments_cut": 0}
    if not of:
        return plan, tuple(abutments), counts
    con = tuple(p for p in plan.contacts if not _crosses(of, *p))
    abu = tuple(p for p in (getattr(plan, "abutments", ()) or ())
                if not _crosses(of, *p))
    ext = tuple(p for p in abutments if not _crosses(of, *p))
    counts["block_contacts_cut"] = len(plan.contacts) - len(con)
    counts["block_abutments_cut"] = (len(getattr(plan, "abutments", ()) or ())
                                     - len(abu)) + (len(abutments) - len(ext))
    return _dc.replace(plan, contacts=con, abutments=abu), ext, counts


def split_units(units: list, plan: _t.Any, pads: _t.Sequence[_ar.PadRing],
                counts: "dict | None" = None) -> list:
    """Every §16g unit whose bodies stand on two or more blocks of ONE
    platform unit, split into one unit per block (module docstring); each
    is seated by ``plan_unit_datums``'s one pad rule, the median of its
    block's (flat) floor.  A per-block FOOT SHIFT (the block's median
    authored foot ``y`` less the unit's) was tried and REFUTED on the HECA
    dry run (lane ``flatpad111b``): T3 feet within 0.3 m 3,683 -> 2,405 and
    the owner's site floor -0.25 -> -0.50 m."""
    from .placement_family import bodies_of_plan, union_area_m2
    of = part_blocks(plan, pads)
    if not of or not units:
        return units
    bodies, _of_pid = bodies_of_plan(plan)
    parts = {p.pid: p for u in plan.units for m in u.members for p in m.parts}
    rings = block_rings(pads)
    out: list = []
    n_split = n_near = 0
    for un in units:
        per_body: dict = {}
        votes_all: dict = {}
        for key in un.bodies:
            votes: dict = {}
            for q in bodies.get(key, ()):
                b = of.get(q)
                if b is not None:
                    votes[b] = votes.get(b, 0) + 1
                    votes_all[b] = votes_all.get(b, 0) + 1
            per_body[key] = (max(votes.items(), key=lambda t: (t[1], t[0]))[0]
                             if votes else None)
        blocks = {b for b in votes_all}
        units_of = {b[0] for b in blocks}
        if len(blocks) < 2 or len(units_of) != 1:
            out.append(un)
            continue
        # a body on no block of the unit joins the block it stands nearest
        for key, b in list(per_body.items()):
            if b is not None:
                continue
            pids = bodies.get(key, ())
            pts = [(parts[q].lat, parts[q].lon) for q in pids if q in parts]
            if not pts:
                continue
            la = sum(p[0] for p in pts) / len(pts)
            lo = sum(p[1] for p in pts) / len(pts)
            best = None
            for unit, k, ring, _bx in rings:
                if (unit, k) not in blocks:
                    continue
                d = min((v[0] - la) ** 2 + (v[1] - lo) ** 2 for v in ring)
                if best is None or d < best[0]:
                    best = (d, (unit, k))
            if best is not None:
                per_body[key] = best[1]
                n_near += 1
        n_split += 1
        for b in sorted(blocks, key=lambda t: t[1]):
            keys = tuple(k for k in un.bodies if per_body.get(k) == b)
            if not keys:
                continue
            pids = frozenset(q for k in keys for q in bodies.get(k, ()))
            boxes = tuple(parts[q].box for q in sorted(pids)
                          if q in parts and not getattr(parts[q], "line", False))
            out.append(_dc.replace(
                un, id=f"{un.id}/b{b[1]}", bodies=keys, pids=pids,
                members=tuple(sorted({plan.units[k[0]].members[k[1]].resource
                                      for k in keys})),
                boxes=boxes or un.boxes,
                area_m2=union_area_m2(boxes) if boxes else un.area_m2,
                deck_pids=frozenset(un.deck_pids & pids)))
    if counts is not None:
        counts["block_units_split"] = n_split
        counts["block_bodies_nearest"] = n_near
    return out
