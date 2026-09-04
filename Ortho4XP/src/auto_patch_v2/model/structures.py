"""STRUCTURE records (M4, plan §1 row 5 "structure constraints") — the
tunnel corridors, road bridge decks and basins the planar map carries
beside its faces, so the constraint generator and the verifier read ONE
record instead of re-deriving the corridor from face rings.

Data only (no shapely, no numpy — ``test_model.py`` enforces it).  Every
coordinate is in the airport frame; every ``s`` is metres along the
ramp axis measured from the mouth (``s = 0`` at the mouth line, growing
OUTWARD, away from the bore).  Values (crest = DEM, mouth datum) are
recorded here exactly as the planar builder sampled them; the generator
turns them into rows and never invents another.

THE MODEL (RULINGS 2026-08-30 canonical mouth; 2026-09-01c/e; 2026-09-03b):
ONE ramp descending the corridor to the mouth line, a ``wall_gap_m``
unowned gap, ONE wall band per side whose crest is the DEM, ONE end cap
across the mouth; the bore under cover is NOT emitted (the covering
surface keeps its own law).  A road bridge deck (2026-08-30c/d/f) severs
the ramp: the stretch under the deck is covered, the cut stays at bore
datum from the mouth to the deck and the climb begins beyond it.
"""
from __future__ import annotations

import dataclasses as _dc

from .frame import XY

__all__ = ["Deck", "Tunnel", "Basin"]


@_dc.dataclass(frozen=True)
class Deck:
    """A road bridge deck across a ramp (RULINGS 2026-08-30c/d/f/m).
    ``s0 < s1`` is the covered stretch along the ramp axis; ``ring`` the
    deck face's outline; ``datum`` names the level the deck sits at
    (``"dem"`` = terrain deck at road level — the only kind M4 emits,
    a hard-deck object deck being ``"deck_top"``)."""

    ref: str
    way: int
    s0: float
    s1: float
    ring: tuple[XY, ...]
    datum: str = "dem"
    z: float | None = None


@_dc.dataclass(frozen=True)
class Tunnel:
    """One emitted tunnel structure.

    ``axis`` runs from the mouth outward (``axis[0]`` = the mouth line's
    centre); ``half_width_m`` the ramp's half width; ``mouth_dem_z`` the
    DEM at the mouth and ``mouth_z`` the ramp's mouth datum
    (``mouth_dem_z - tunnel.bore_datum_m``); ``top_s`` where the ramp
    reaches the DEM; ``climb_from_s`` where the climb starts (0, or the
    far edge of the last deck + the gap); ``ramp_refs`` / ``wall_ref`` /
    ``deck_refs`` the face refs the planar map carries for it;
    ``wall_path`` the wall band's centreline as a U (left band from the
    top to the mouth, across the cap, right band back to the top) — the
    crest is the DEM along it (2026-09-03b L1); ``ways`` the OSM bore
    way ids (both carriageways of a dual, 2026-08-31h)."""

    id: str
    ways: tuple[int, ...]
    axis: tuple[XY, ...]
    half_width_m: float
    mouth_dem_z: float
    mouth_z: float
    top_s: float
    climb_from_s: float
    ramp_refs: tuple[str, ...]
    wall_ref: str
    wall_path: tuple[XY, ...]
    decks: tuple[Deck, ...] = ()
    notes: tuple[str, ...] = ()
    #: The top edge reaches the DEM (pinned there); False when a building
    #: pad clipped the ramp short (08-07 ruling 3): the ramp climbs as far
    #: as the pad edge and the pad's face is the portal.
    top_pinned: bool = True
    clipped_by: str = ""
    #: The two end-cap corner points on the band's centreline (left,
    #: right): the mouth datum is their crest's mean minus ``bore_datum_m``.
    cap_corners: tuple[XY, XY] | None = None
    #: The end cap's centre point on the band's centreline: the MOUTH WALL
    #: NODE of 2026-09-03b — the mouth datum is its crest − bore_datum_m.
    cap_centre: XY | None = None


@_dc.dataclass(frozen=True)
class Basin:
    """A below-grade facility with a DECLARED floor (RULINGS 2026-08-26;
    ``structures.basin.floor = "declared"``): the floor face at
    ``floor_z``, a wall band round it whose crest is the DEM."""

    id: str
    objects: tuple[str, ...]
    floor_z: float
    floor_ref: str
    wall_ref: str
    ring: tuple[XY, ...]
