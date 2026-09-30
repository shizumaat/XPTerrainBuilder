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
  blocks.  A body standing on no block of the unit joins the block that
  holds the MAJORITY of the parts it is welded to (the ε-contact graph),
  its feet's nearest platform ring breaking a tie; a body with no strict
  majority straddles the boundary and is REPORTED (issue #126).

The cut FILES come from the pristine backup exactly as every other split
does (``obj8_split.split_obj8`` reads ``.anchor_bak`` — restore-before-
read): nothing here reads or writes an object.  Pure reading; no law
constant lives here."""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import typing as _t

from ..model.planar import block_of
from . import anchor_rule as _ar

__all__ = ["STRADDLE_KEY", "block_rings", "neighbours", "part_blocks",
           "seat_unit", "sever", "split_units"]

# counts key prefix naming a ringless body whose welded parts hold no strict
# majority in one block (``<prefix><resource>@<unit id>``), the way
# ``basin_ring`` names its arcs — a report, never a law value
STRADDLE_KEY = "block_body_straddle:"


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


def _platform_polys(pads: _t.Sequence[_ar.PadRing]) -> dict:
    """``{(unit, k): [platform polygons in local metres]}`` — every block
    ring but the COLLAR's outer ring (``placement_read._collars_as_platform``
    publishes it under the block ref; it is the block's largest ring)."""
    import math
    from shapely.geometry import Polygon
    by: dict = {}
    for unit, k, ring, _bx in block_rings(pads):
        by.setdefault((unit, k), []).append(ring)
    out: dict = {}
    for key, rs in by.items():
        ky = 111_320.0
        kx = ky * math.cos(math.radians(rs[0][0][0]))
        polys = [Polygon([(lo * kx, la * ky) for la, lo in r]).buffer(0) for r in rs]
        if len(polys) > 1:
            big = max(range(len(polys)), key=lambda i: polys[i].area)
            polys = [g for i, g in enumerate(polys) if i != big]
        out[key] = [g for g in polys if not g.is_empty]
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


def _neighbours(plan: _t.Any) -> dict[int, set[int]]:
    """``part id -> the part ids it is in ε-contact with`` over
    ``plan.contacts`` (the severed plan: no pair crosses a neck)."""
    out: dict[int, set[int]] = {}
    for a, b in getattr(plan, "contacts", ()):
        out.setdefault(a, set()).add(b)
        out.setdefault(b, set()).add(a)
    return out


def _welded_votes(pids, nbr, of, body_of, direct, blocks) -> dict:
    """``block -> how many DISTINCT parts outside the body ``pids`` it is
    welded to stand in it`` — a welded part's block is where it stands
    (``part_blocks``), else the block its own body stands on directly;
    parts on no block of this unit do not vote."""
    own = set(pids)
    seen: set[int] = set()
    votes: dict = {}
    for q in pids:
        for r in nbr.get(q, ()):
            if r in own or r in seen:
                continue
            seen.add(r)
            b = of.get(r)
            if b is None:
                b = direct.get(body_of.get(r))
            if b is not None and b in blocks:
                votes[b] = votes.get(b, 0) + 1
    return votes


def _majority(votes: _t.Mapping) -> "tuple[_t.Any, set]":
    """``(the key holding a STRICT majority of ``votes`` or None, the keys
    tied at the top)``."""
    top = max(votes.values())
    lead = {k for k, n in votes.items() if n == top}
    if len(lead) == 1 and 2 * top > sum(votes.values()):
        return next(iter(lead)), lead
    return None, lead


def _block_id(uid: str) -> "tuple[str, int] | None":
    """``(footprint unit, block k)`` of a unit id :func:`split_units`
    wrote (``<id>/b<k>``); None for any other id."""
    head, sep, tail = str(uid).rpartition("/b")
    if not sep or not head or not tail.isdigit():
        return None
    return head, int(tail)


def seat_unit(pids: _t.Iterable[int], plan_wide: _t.Mapping[int, tuple],
              welded: "_t.Mapping[int, _t.Iterable[int]] | None" = None,
              feet: _t.Sequence[tuple] = (),
              pads: _t.Sequence[_ar.PadRing] = (),
              counts: "dict | None" = None, name: str = ""
              ) -> "str | None":
    """THE ONE UNIT a written group of parts (a staged ground group, a
    placement candidate) is seated in, from the plan-wide part -> unit
    join (``footprint_seats.plan_wide_seats``): the unit most of its
    parts belong to, the first id breaking a tie — UNLESS its parts stand
    on two or more BLOCKS of one cut unit (issue #126).  Then the group
    joins the block holding the MAJORITY of the parts it is WELDED to
    (``welded``: the plan's ε-contact graph BEFORE the neck sever,
    :func:`neighbours`), its FEET breaking a tie; a group whose welded
    parts hold no strict majority in one block STRADDLES the boundary
    (flat-pad spec §7's STOP class): it is seated in the block holding the
    most of them (feet, then part count, breaking a tie) and counted by
    name (``STRADDLE_KEY``), never silently.

    Measured at SPJC building5 (``fu:0:1``): ``xp11_010``'s 830 m sheet
    (pid 25, centroid on b1, 136 welded parts all on b1 once the neck is
    severed) and a 2-foot trinket 275 m off (pid 26, on b0) are ONE rigid
    group; the part count tied 1:1 and the lexical tie-break seated the
    sheet on b0, 2.87 m off its b1 neighbours 65 m from the neck.  The
    sheet itself is welded 136 / 126 / 48 across b1 / b2 / b0 — a
    straddler, seated on b1 and reported."""
    hit: dict = {}
    pids = tuple(pids)
    for q in pids:
        row = plan_wide.get(q)
        if row is not None:
            hit[row[0]] = hit.get(row[0], 0) + 1
    if not hit:
        return None
    lead = max(sorted(hit), key=lambda k: hit[k])
    blk = _block_id(lead)
    if blk is None or not welded:
        return lead
    sib = {u for u in hit if (_block_id(u) or ("",))[0] == blk[0]}
    if len(sib) < 2:
        return lead
    own = set(pids)
    seen: set = set()
    votes: dict = {}
    for q in pids:
        for r in welded.get(q, ()):
            if r in own or r in seen:
                continue
            seen.add(r)
            row = plan_wide.get(r)
            if row is not None and (_block_id(row[0]) or ("",))[0] == blk[0]:
                votes[row[0]] = votes.get(row[0], 0) + 1
    # the seat is always a block the group has a part on (its datum row is
    # read from the group's own pids); the majority is judged over EVERY
    # block of the unit, so a weld into a third block still counts
    cand = sib
    if votes:
        win = _majority(votes)[0]
        if win is not None and win in sib:
            if counts is not None and win != lead:
                counts["block_groups_welded"] = \
                    counts.get("block_groups_welded", 0) + 1
            return win
        if counts is not None:
            tag = f"{STRADDLE_KEY}{name}@{blk[0]}"
            counts[tag] = counts.get(tag, 0) + 1
            counts["block_groups_straddle"] = \
                counts.get("block_groups_straddle", 0) + 1
        own_votes = {u: n for u, n in votes.items() if u in sib}
        if own_votes:
            cand = _majority(own_votes)[1]
    # the tie-break: the block holding most of the group's FEET, then the
    # part count, then the first id
    rings = block_rings(pads) if feet and pads else []
    fv: dict = {}
    for f in feet:
        b = _block_at(rings, float(f[0]), float(f[1])) if rings else None
        if b is None:
            continue
        uid = f"{blk[0]}/b{b[1]}"
        if uid in cand:
            fv[uid] = fv.get(uid, 0) + 1
    return max(sorted(cand), key=lambda k: (fv.get(k, 0), hit.get(k, 0)))


def neighbours(plan: _t.Any) -> dict[int, set[int]]:
    """``part id -> the part ids it is in ε-contact with`` over
    ``plan.contacts``."""
    return _neighbours(plan)


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
    plat = _platform_polys(pads)
    from shapely.geometry import Point as _Pt
    ky = 111_320.0
    kx = ky * _math.cos(_math.radians(rings[0][2][0][0])) if rings else ky
    out: list = []
    n_split = n_near = n_weld = n_strad = 0
    nbr = _neighbours(plan)
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
        # a body on no block of the unit joins the block holding the
        # MAJORITY of its WELDED parts — the parts of OTHER bodies it is in
        # ε-contact with (``plan.contacts``, already severed at the necks) —
        # and only then the block whose PLATFORM RING stands nearest its own
        # FEET (issue #126: SPJC ``xp11_010`` had its feet nearest b0 while
        # every part it is welded to stands in b1, and was seated 2.87 m off
        # them 65 m from the declared neck; spec-author RULINGS 2026-09-30u
        # (iii) had replaced the centroid by the feet).  A body whose welded
        # parts hold NO strict majority in one block STRADDLES the boundary
        # (flat-pad spec §7's STOP class): it is seated by its feet among
        # the tied blocks and REPORTED by name, never silently assigned.
        direct = {k: b for k, b in per_body.items() if b is not None}
        # a body resolved by its welds votes for the ringless bodies welded
        # to IT (a chain of ringless facade bodies off one footed wall)
        pending = [k for k, b in per_body.items() if b is None]
        grew = True
        while grew:
            grew = False
            for key in pending:
                if key in direct:
                    continue
                welded = _welded_votes(bodies.get(key, ()), nbr, of, _of_pid,
                                       direct, blocks)
                win = _majority(welded)[0] if welded else None
                if win is not None:
                    per_body[key] = direct[key] = win
                    n_weld += 1
                    grew = True
        for key in pending:
            if key in direct:
                continue
            pids = bodies.get(key, ())
            welded = _welded_votes(pids, nbr, of, _of_pid, direct, blocks)
            cand = blocks
            if welded:
                cand = _majority(welded)[1]
                n_strad += 1
                if counts is not None:
                    res = plan.units[key[0]].members[key[1]].resource
                    tag = f"{STRADDLE_KEY}{res}@{un.id}"
                    counts[tag] = counts.get(tag, 0) + 1
            pts = [(f[0], f[1]) for q in pids if q in parts
                   for f in (getattr(parts[q], "feet", ()) or ())]
            if not pts:
                pts = [(parts[q].lat, parts[q].lon) for q in pids if q in parts]
            if not pts:
                continue
            best = None
            for (unit, k), polys in plat.items():
                if (unit, k) not in cand:
                    continue
                d = min(g.distance(_Pt(lo * kx, la * ky)) for g in polys
                        for la, lo in pts)
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
        counts["block_bodies_welded"] = n_weld
        counts["block_bodies_straddle"] = n_strad
    return out
