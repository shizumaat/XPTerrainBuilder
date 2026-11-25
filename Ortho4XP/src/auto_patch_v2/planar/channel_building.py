"""A NECK NEVER INFERS A CUT UNDER A BUILDING (§45 (23) PROPOSED, issue
#2266) — lane ``lmmun2``.

A paved neck (§45 (1) (b)) states only that the airside pavement crosses a
road; the DEPTH under it is INFERRED by §45 (3) (iii), "Cut the road down".
A mapped building standing on the corridor's floor contradicts that
inference — a building stands on the ground the cut would remove — so a
neck-ONLY channel (no pack wall/floor object, no credible lidar, no
bridge to state the structure itself) whose FLOOR carries a building is a
road at grade among the buildings and is refused at admission, beside
§45 (21)'s survey refutation and §45 (22)'s strip refusal.

The site: MMUN (#2266).  A two-lane terminal loop (ways -413/-428) crossed
the apron at two necks; (iii) cut a 183 m wide corridor 3.6 m down at its
ends, its floor polygon carried 21,743 m2 of the terminal pads, and the
floor's pin (2.12 m against the 5.94 m plateau) reached terminal
``building2`` through the apron fronting it: the pad sat 2.97 m under the
ground.

A channel with a depth witness is never asked: the pack or the survey
states the cut, and its floor stands back from a building as from a deck
(``channel_claims.channel_cells``).
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon

from ..law import Law
from ..model.structures import Channel
from .channel_geometry import _poly

__all__ = ["buildings_on_floor", "building_refusal", "building_polygons"]


def building_polygons(classification) -> list[tuple[str, Polygon]]:
    """``[(ref, footprint)]`` of every ``building`` cell of the
    classification (the pads the structure knife never cuts)."""
    out: list[tuple[str, Polygon]] = []
    for c in getattr(classification, "cells", ()) or ():
        if c.role != "building" or len(c.ring) < 3:
            continue
        p = Polygon(c.ring, [h for h in c.holes if len(h) >= 3])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            out.append((str(c.ref), p))
    return out


def buildings_on_floor(channel: Channel, buildings: _t.Sequence[tuple[str, Polygon]],
                       law: Law) -> list[tuple[str, float]]:
    """``[(building ref, m2 on the floor)]``: the buildings whose footprint,
    shrunk by ``emit.identity.min_distinct_spacing_m`` (a footprint that
    only touches the floor at the identity spacing is beside it, not on
    it), overlaps the channel's FLOOR region."""
    floor = _poly(channel.region)
    if floor is None:
        return []
    tol = float(law.tables.emit.identity.min_distinct_spacing_m)
    got: dict[str, float] = {}
    for ref, p in buildings:
        if not p.intersects(floor):
            continue
        core = p.buffer(-tol, join_style="mitre")
        a = core.intersection(floor).area if not core.is_empty else 0.0
        if a > 0.0:
            got[ref] = got.get(ref, 0.0) + a
    return sorted(got.items(), key=lambda kv: -kv[1])


def building_refusal(channel: Channel, on_floor: _t.Sequence[tuple[str, float]]) -> str:
    """The NAMED refusal line (the stats every replay publishes)."""
    names = ", ".join(f"{ref} ({a:.1f} m2)" for ref, a in on_floor[:5])
    more = f" and {len(on_floor) - 5} more" if len(on_floor) > 5 else ""
    return (f"{channel.id}: witnessed by a paved neck alone, its floor only inferred by "
            f"\"Cut the road down\" — and mapped building(s) stand on that floor: "
            f"{names}{more}; a building stands on the ground the cut would remove: "
            f"{len(channel.decks)} crossing(s) at grade, not a channel (§45 (23) "
            f"proposed, #2266). Ways {'+'.join(str(int(w)) for w in channel.ways)}")
