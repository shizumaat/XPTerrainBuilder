"""A BODY THE CARRIER SEARCH LEFT BARE RIDES WHAT IT IS WELDED TO (issue
#127; spec ``object-placement-spec.md`` flat-pad §7).

:func:`welded_carriers` only.  The carrier question itself
(``_footless_targets``) and what its answer cuts (``_carrier_pieces``) are
``placement_body``'s — ONE implementation; the second copy that lived here
was unreachable and is deleted (lane ``v2trim``, RULINGS 2026-10-04c (2)).

NO LAW CONSTANT LIVES HERE.
"""
from __future__ import annotations

import typing as _t

from . import placement_carrier as _pc

__all__ = ["welded_carriers"]


def welded_carriers(targets: _t.Sequence[_t.AbstractSet[int]],
                    carrier_of: _t.Mapping[int, _pc.Candidate],
                    contacts: _t.Iterable[tuple[int, int]],
                    ) -> dict[int, tuple[_pc.Candidate, str]]:
    """Issue #127 (flat-pad spec §7): A BODY THE SEARCH LEFT ON ITS OWN
    GROUND RIDES WHAT IT IS WELDED TO.

    §15's search offers only FOOTED candidates, so a footless facade
    whose one weld is to a body that is itself CARRIED (HECA T3: the
    ``glass_blue_2`` panes welded to ``T2_Brick`` b4, which rests on
    ``door`` b27) found nothing it may stand on and fell to §16 (3)'s
    own ground — the design surface under its own footprint, 1.1-1.4 m
    over the zero its wall was written at, a seam the eye reads across a
    2 mm weld.  The weld is the stronger evidence: the pack authored the
    two parts touching, so they share ONE carrier.

    ``targets`` are the part-id sets of the bodies with no carrier;
    ``carrier_of`` maps every part id already placed to the candidate its
    body is written on (a footed body's own pids to itself, a carried
    body's to its carrier); ``contacts`` is the unit's ε-contact graph
    (welds only, never abutments).  A target takes the carrier holding
    the MOST of its welds (ties: the carrier with the most feet, then
    member, then group).  The walk is breadth-first in ROUNDS read from
    a snapshot, so two facades welded to each other share the carrier of
    whichever reaches a placed body first, and the answer never depends
    on the order the targets are listed.  Targets welded to nothing
    placed are absent from the result and keep their own ground.

    ``{target index: (carrier, why)}``."""
    adj: dict[int, set[int]] = {}
    for a, b in contacts:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    placed = dict(carrier_of)
    out: dict[int, tuple[_pc.Candidate, str]] = {}
    hops = 0
    while True:
        hops += 1
        new: dict[int, tuple[_pc.Candidate, str]] = {}
        for ti, pids in enumerate(targets):
            if ti in out:
                continue
            votes: dict[int, list] = {}
            for p in pids:
                for q in adj.get(p, ()):
                    if q in pids:
                        continue
                    c = placed.get(q)
                    if c is None:
                        continue
                    v = votes.setdefault(id(c), [0, c])
                    v[0] += 1
            if not votes:
                continue
            n, c = min(votes.values(),
                       key=lambda v: (-v[0], -v[1].feet, v[1].member,
                                      v[1].group))
            new[ti] = (c, f"welded ({n} part contact(s), hop {hops}) to a "
                          f"body written on it")
        if not new:
            return out
        for ti, (c, _w) in new.items():
            for p in targets[ti]:
                placed.setdefault(p, c)
        out.update(new)
