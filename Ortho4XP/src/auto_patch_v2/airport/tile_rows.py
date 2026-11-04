"""ONE AIRPORT'S PLAN, WRITTEN ONE TILE DSF AT A TIME (issue #1645; spec
§38 (4), RULINGS 2026-09-13am "ONE AIRPORT, ONE SOLVE, PER-TILE PIECES").

The load reads the DSF of every tile the airport touches, so one rebake
plan names rows of several dumps: the ORIGIN tile's as ``dsf:obj<i>``, a
neighbour's as ``dsf:obj<i>@<tile>`` (``airport/dsf.row_of``).  The object
stage writes ONE tile's DSF per tile build.  :func:`for_tile` turns the
plan and the published riders into that tile's own rows — its members and
seat records with bare ids, every other tile's left out — so every reader
downstream (the split, the row half, the rider join) keeps reading a bare
``dsf:obj<i>`` as a row of the dump in hand.

A plan with no ``origin_tile`` (written before #1645) and a call with no
tile are returned unchanged: their bare ids already are the dump's rows.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from . import dsf as _dsf

__all__ = ["for_tile"]


def for_tile(plan: _t.Any, strips: _t.Sequence, tile: "tuple[int, int] | None"
             ) -> tuple[_t.Any, tuple]:
    """``(plan, jetway strips)`` as rows of ``tile``'s DSF (module doc)."""
    origin = getattr(plan, "origin_tile", None)
    strips = tuple(strips or ())
    if tile is None or origin is None:
        return plan, strips
    here = (int(tile[0]), int(tile[1]))

    def local(oid: str) -> str | None:
        t, row = _dsf.row_of(oid)
        if row is None:
            return oid                      # not a row id: no tile to judge
        return f"dsf:obj{row}" if (t or tuple(origin)) == here else None

    units = []
    for u in plan.units:
        members = tuple(_dc.replace(m, id=i) for m in u.members
                        if (i := local(m.id)) is not None)
        if members:
            units.append(_dc.replace(u, members=members))
    seats = []
    for r in plan.authored_seats:
        i = local(str(r.get("id")))
        if i is not None:
            seats.append({**r, "id": i, **({"members": [
                j for j in (local(str(x)) for x in r["members"]) if j is not None]}
                if r.get("members") else {})})
    # ``origin_tile`` cleared: the ids are now this dump's rows, so a second
    # call is a no-op
    plan = _dc.replace(plan, units=tuple(units), authored_seats=tuple(seats),
                       origin_tile=None)
    return plan, tuple(_strip_for(s, here, tuple(origin)) for s in strips)


def _strip_for(strip: _t.Mapping, here: tuple[int, int], origin: tuple[int, int]
               ) -> dict:
    """A published strip whose riders on another tile lose their row index
    (the writer then joins them by anchor and path, which no row of this
    tile's dump matches)."""
    riders = []
    for r in strip.get("riders", ()) or ():
        r = list(r)
        t = tuple(int(v) for v in r[7]) if len(r) > 7 and r[7] else origin
        if len(r) > 4 and t != here:
            r[4] = None
        riders.append(r[:7])
    return {**strip, "riders": riders}
