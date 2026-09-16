"""THE STRUCTURE PASS'S STATISTICS (``planar/structures.StructureStats``).

MOVED VERBATIM out of ``planar/structures.py`` by lane ``v2rampwalk``:
that file stands at its 1,000-line budget and spec §34 (5) grows it.  No
behaviour moved with it — the dataclass is re-exported from
``planar.structures``, which is where every reader still imports it from,
and the move was proved by a byte-identical ``--stage structures`` replay
of LEMD before and after.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["StructureStats"]


@_dc.dataclass
class StructureStats:
    """What the structure pass found, made and refused."""

    bores: int = 0
    #: spec §29 (2): bores with NO mouth on the field — nothing is built for
    #: them (the old ``bores_uncovered``, whose test was the bore's cover).
    bores_no_mouth: int = 0
    #: spec §29 (2) (owner 2026-09-12ab, "Build them"): bores BUILT on an
    #: on-field mouth alone — they pass under no classified cell, so the
    #: retired cover test refused them.  Counted and named so the
    #: population the owner ruled in stays visible without a rebuild.
    bores_mouth_only: int = 0
    mouth_only_bores: list[str] = _dc.field(default_factory=list)
    mouths: int = 0
    #: spec §29 (1): mapped ends DROPPED for standing off the field —
    #: neither the mouth point nor its ramp reach inside the classified
    #: cover (with the roofed corridors) ⊕ ``[tunnel] mouth_standoff_m``.
    mouths_off_field: int = 0
    #: the NEAREST of those, reported under the structures line so a drop
    #: at the margin is visible without a rebuild.
    mouths_off_field_nearest: list[str] = _dc.field(default_factory=list)
    #: §29 (1) / §31 (2) (RULINGS 2026-09-12al): mouths held by THE
    #: APPROACH CORRIDOR alone — off the cover, in view on a runway end's
    #: extended centreline — counted apart from the on-field ones, and
    #: the corridor count the gate ran with (2 per runway, 0 = none).
    mouths_on_approach: int = 0
    mouths_on_approach_named: list[str] = _dc.field(default_factory=list)
    approach_corridors: int = 0
    #: §29 (7) (RULINGS 2026-09-13bm (ii)): how many RUNWAY LATERAL BANDS
    #: the field region carries — one per runway axis.
    runway_bands: int = 0
    duals_merged: int = 0
    #: THE OPEN CHANNELS (spec §45; owner RULINGS 2026-09-15i) the map
    #: carries, and how many faces they put in it (floor + bank).  The
    #: records themselves travel on ``PlanarMap.channels``; these two are
    #: what the structures line prints.
    channels: int = 0
    channel_faces: int = 0
    tunnels: int = 0
    decks: int = 0
    object_decks: int = 0
    #: RULINGS 2026-09-06f: pavement cells (``bridge.pavement_deck_families``)
    #: spanning an object corridor, kept as decks over the ramp.
    pavement_decks: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    #: §34 (13) (4) (Fable 2026-09-15; RULINGS 2026-09-15y): one line per
    #: MOUTH ROAD minted (``planar/structure_road.mouth_pair_roads``) plus
    #: the class's own tally, for the structures line.
    mouth_roads: list[str] = _dc.field(default_factory=list)
    #: THE PINCHED RAMPS (spec §34 (9), owner RULINGS 2026-09-14ak): one
    #: line per corridor whose climb-out ended at an airside-locked service
    #: road's edge with the cap lifted — corridor, road, span, grade.
    pinched_ramps: list[str] = _dc.field(default_factory=list)
    cells_cut: int = 0
    #: RULINGS 2026-09-05k-1 / 05n-3: object corridors built, the OSM bores
    #: replaced (both mouths inside an object), the mouths taken, and the
    #: per-bore precedence record.
    object_corridors: int = 0
    bores_replaced_by_object: int = 0
    mouths_replaced_by_object: int = 0
    bore_precedence: list[str] = _dc.field(default_factory=list)
    #: RULINGS 2026-09-08b/c: door ramps and sunken roads built through
    #: the same machinery (``planar/door_ramps.py`` groups).
    door_ramps: int = 0
    sunken_roads: int = 0
    #: RULINGS 2026-09-08m/08n Law C: kerb-wall corridors built
    wall_corridors: int = 0
    #: spec §33 (2): the mouths a THIN-PLATE wall object took, one line each
    #: (``airport/thin_plates``; ``planar/structure_approach.apply_plates``).
    plate_mouths: list[str] = _dc.field(default_factory=list)
    #: spec §33 (3): mouths whose crest was capped at the approach's ground
    #: (the DEM sample stood on an overbridge embankment).
    crest_from_approach: list[str] = _dc.field(default_factory=list)
    #: spec §34 (5): the UNDERPASSES stated by an aeroway bridge — one line
    #: per deck way naming the roads bored under it.
    underpasses: list[str] = _dc.field(default_factory=list)
    #: §33 (6) B AMENDED (3) (c) (owner RULINGS 2026-09-15br): the SURFACE
    #: ELEMENTS excluded from the terrain solve inside an object-decked
    #: trench outline — one line per outline (its open m², the pavement m²
    #: the knife took, the centreline and road metres trimmed), plus the
    #: totals the report and the twins read.
    decked_excluded: list[str] = _dc.field(default_factory=list)
    decked_outlines: int = 0
    decked_centreline_m: float = 0.0
    decked_road_m: float = 0.0
    decked_pavement_m2: float = 0.0
    #: the runway-family cells standing inside an object-decked outline —
    #: the knife's 08-07 ruling 4 exemption, MEASURED rather than widened.
    decked_runway_family: list[str] = _dc.field(default_factory=list)
