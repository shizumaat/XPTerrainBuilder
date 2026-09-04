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
    """A below-grade FACILITY derived from the pack's own objects
    (RULINGS 2026-08-26; ``structures.toml [basin]``; M4b): ONE floor
    face at ``floor_z`` (role ``tunnel_trench``, ref ``floor_ref``), the
    ``wall_gap_m`` unowned gap round it, ONE wall band (role
    ``retaining_wall``, ref ``wall_ref``) whose crest is the ground
    (the DEM where bare, the governed ground's value where shared — the
    rim LEVEL with the apron, 2026-08-28c item 3).

    ``ring`` is the admitted region (the floor face's outline before the
    arrangement); ``wall_path`` the band's centreline as a closed ring
    (crest by station along it); ``rim_estimate_m`` is ``R_est`` (the
    median DEM around the ring, ``rim_sample_step_m`` apart);
    ``solid_min_z`` the RENDERED elevation of the facility's deepest
    genuine solid (``DEM(anchor) + agl + y``, thickness-gated) and
    ``solid_min_y_m`` the same relative to ``R_est`` (the sidecar's
    ``solid_minimum_y_m``, so ``floor_z == rim_estimate_m +
    solid_min_y_m − margins`` holds exactly); ``covered_fraction`` the
    cover reading (the pack's own geometry above the contact band over
    the ring — reported, never a refusal: 04i); ``anchor_ll`` a
    representative point inside the ring."""

    id: str
    objects: tuple[str, ...]
    floor_z: float
    floor_ref: str
    wall_ref: str
    ring: tuple[XY, ...]
    wall_path: tuple[XY, ...] = ()
    rim_estimate_m: float = 0.0
    solid_min_z: float = 0.0
    solid_min_y_m: float = 0.0
    covered_fraction: float = 0.0
    area_m2: float = 0.0
    anchor_ll: tuple[float, float] = (0.0, 0.0)
    notes: tuple[str, ...] = ()
    #: 04i: the deep floor plates' area inside the ring (the floor
    #: evidence) and the kind — ``"pit"`` (open) or ``"covered pit"``
    #: (cover above the contact band over it; the cover is the object).
    floor_plate_m2: float = 0.0
    kind: str = "pit"
