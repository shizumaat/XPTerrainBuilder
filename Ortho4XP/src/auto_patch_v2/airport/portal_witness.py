"""IS THERE AN OPEN CUT AT THIS MAPPED MOUTH — the Q5 vote, and the Q6
floor it reads (#1359; owner RULINGS 2026-10-26q, 2026-10-26x; spec
``docs/specs/multi-source-terrain-spec.md`` §3 Q5 / Q6, §4.1).

A MOUTH is a mapped site only (26x: a witness never creates a cut no map
source names): an end of an OSM ``tunnel=yes`` way that no other tunnel
way continues (:func:`mapped_mouths`).  At each, yes (1) / no (0):

* **map** — the mapped feature proposes it: yes, the least senior;
* **DEM** — the ring median (``q5.ring_m``) minus the core minimum
  (``q5.core_m``), at least ``q5.portal_depth_min_m`` = yes, else no; a DEM
  coarser than the feature (not the lidar class) abstains;
* **imagery** — the method's ``portal_opening`` presence in a square of
  ``2 * q5.window_half_m`` at the mouth against its surround: an opening
  and its shadow = yes, a window no darker than its surround = no, between
  = abstain.

The vote is ``witness_vote.decide`` with the Q5 seniority.  This module
answers; it moves nothing (the admission site is ``planar/structures``,
not wired by this lane).  The DEM floor of a yes is the Q6 lidar witness.
"""
from __future__ import annotations

import numpy as np

from ..law import Law
from ..law.inset_class import dem_source_class
from ..law.tables import FLAT_CLASS_LIDAR
from . import image_edges_classic  # noqa: F401  (registers the classic method)
from .image_provider import provider
from .lidar_breaks import cut_depth
from .witness_vote import Abstain, Vote, decide

__all__ = ["mapped_mouths", "mouth_votes", "SENIORITY"]

#: Q5 seniority (spec §4.1; no pack object is read here)
SENIORITY = ("pack", "imagery", "dem", "osm")
#: an end within this of another tunnel way's end continues the bore
_JOIN_M = 2.0
#: imagery: a presence strength at or under this reads "no opening" (the
#: classic method's strength is darkness over twice its floor: 0.16 is a
#: window about 8 levels darker than its surround)
_NO_OPENING = 0.16
_SIG = 0.1


def mapped_mouths(airport) -> list[tuple[tuple[float, float], int, str]]:
    """``[(xy, way id, highway/railway value)]`` of every open end of a
    mapped ``tunnel=yes`` way (a building passage is no bore)."""
    ways = [w for w in getattr(airport, "osm_ways", ())
            if w.tags.get("tunnel") == "yes" and len(w.points) >= 2]
    ends = [(tuple(map(float, p)), w) for w in ways for p in (w.points[0], w.points[-1])]
    out = []
    for xy, w in ends:
        shared = any(o is not w and np.hypot(xy[0] - q[0], xy[1] - q[1]) <= _JOIN_M
                     for q, o in ends)
        if not shared:
            out.append((xy, int(w.id), w.tags.get("highway") or w.tags.get("railway") or ""))
    return out


def mouth_votes(airport, xy: tuple[float, float], textures, law: Law,
                klass: str | None = "") -> tuple[list, object, float | None, float | None]:
    """``(votes, decision, DEM depth, DEM floor)`` at mouth ``xy``."""
    q = law.tables.terrain_witness.q5
    if klass == "":
        try:
            klass = dem_source_class(airport.dem, law)[0]
        except Exception:                      # pragma: no cover - fixtures
            klass = None
    votes: list = [Vote("osm", 1.0, _SIG, note="mapped tunnel end")]
    depth, floor = cut_depth(airport.dem, xy, tuple(q.ring_m), q.core_m)
    if klass != FLAT_CLASS_LIDAR:
        votes.append(Abstain("dem", f"DEM class {klass or 'unknown'} is coarser than a cut"))
    elif depth is None:
        votes.append(Abstain("dem", "no DEM at the mouth"))
    else:
        votes.append(Vote("dem", 1.0 if depth >= q.portal_depth_min_m else 0.0, _SIG,
                          note=f"depth {depth:.2f} m, floor {floor:.2f} m"))
    votes.append(_image_vote(airport, xy, textures, law))
    dec = decide(votes, SENIORITY, law.tables.terrain_witness.vote.k)
    return votes, dec, depth, floor


def _image_vote(airport, xy, textures, law):
    q = law.tables.terrain_witness.q5
    if textures is None or not len(textures):
        return Abstain("imagery", "no texture of this build covers the airport")
    h = q.window_half_m
    reach = h + 20.0
    patch = textures.patch(airport.frame.crs, xy[0] - reach, xy[1] - reach,
                           xy[0] + reach, xy[1] + reach, q.m_per_px)
    if patch is None:
        return Abstain("imagery", "no texture at the mouth")
    win = np.array([(xy[0] - h, xy[1] - h), (xy[0] + h, xy[1] - h),
                    (xy[0] + h, xy[1] + h), (xy[0] - h, xy[1] + h)])
    ev = provider(law.tables.terrain_witness.image.provider).presence(patch, win, "portal_opening")
    if ev.offset_m is not None:
        return Vote("imagery", 1.0, _SIG,
                    note=f"opening, strength {ev.strength:.2f} ({patch.source})")
    if ev.strength <= _NO_OPENING:
        return Vote("imagery", 0.0, _SIG,
                    note=f"no opening, strength {ev.strength:.2f} ({patch.source})")
    return Abstain("imagery", f"undecided, strength {ev.strength:.2f} ({patch.source})")
