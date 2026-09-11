"""THE PACK'S PLACED OBJECTS, AND WHO IS A BASIN MEMBER — read ONCE, and
read FIRST (owner RULINGS 2026-09-10ax (2)).

``planar/basins.py`` owns the basin REGION (rules 2-5: the union of the
witnesses' below-ground footprints, the rim, the floor, the cut).  What
lives here is the half of the reading that has to happen EARLIER than
that: rule 1 — which PLACEMENTS carry a basin floor witness (a genuine
solid whose rim reaches grade and whose floor plate stands
``admission_depth_m`` under the local ground AND ``authored_depth_min_m``
under the placement's own render datum, RULINGS 2026-09-09ak).

Why earlier: the skirt reader (``airport/skirt.py``, 10ag) and the
re-seat plan's below-grade skip (``airport/rebake_plan.py``, 09w (1))
both ask "is this placement's below-zero geometry a FOUNDATION?", and a
basin's members answer yes by geometry alone — a pit IS uniform
below-zero extent across its footprint.  Measured at LEMD (2026-09-10,
lane ``v2basinfix``): the T4S basin's own members
``Ground-FSX-LEMD36``/``LEMD85`` read skirts of 7.01/7.03 m, covered
94 % of the T4S terminal pad ``building16``, and dropped it under 10ag;
with the pad gone the OSM road bore ``-5970`` was no longer refused
("the mouth stands against building pad building16") and its ramp — a
``kind == "structure"`` cell — landed on the pit's rim, so
``planar/basins`` rule 5 refused the basin itself ("27557 m2 overlaps a
tunnel structure").  ``basin_facilities`` 1 -> 0, the pit went uncut and
``Ground-FSX-LEMD37`` was seated +4.7 m onto the uncut surface: the
owner's "lip 2 m above the apron" on app 1.0.310.

THE RULE (10ax (2)): a basin facility admitted under 09ak is never
demoted by the skirt reader or by the below-grade skip.  A skirt is a
foundation under a building that stands ABOVE ground; a basin's members
ARE the pit.  So the admission runs FIRST and its members are exempt at
both sites — ``skirt.skirted_placements`` (the one derivation site of
"skirted", which ``classify/evidence._drop_skirted`` and
``emit/clusters`` both read) and ``rebake_plan``'s per-component
below-grade skip.

The read itself is memoised on the shared ``obj8.ResourceCache`` (the
one v2skirt made the whole build share), so asking the question at
classify time costs the planar pass nothing.
"""
from __future__ import annotations

import typing as _t

from . import deck_signature, obj8

if _t.TYPE_CHECKING:                                   # pragma: no cover
    from ..law import Law

__all__ = ["read_objects", "basin_member_ids"]


def read_objects(airport, law: "Law", cache: obj8.ResourceCache | None = None
                 ) -> tuple[list[obj8.PlacedObject], obj8.ObjReport]:
    """Every placed OBJ8 of the pack read once (``airport/obj8.py``),
    memoised on ``cache`` — ``planar/basins.read_objects`` is this
    function, and the classify-time basin admission below shares the
    same reading."""
    bl = law.tables.structures.basin
    cache = cache or obj8.ResourceCache(bl.min_solid_thickness_m)
    hit = cache.placed.get("objects")
    if hit is not None:
        return hit                                     # type: ignore[return-value]
    rows = []
    for o in airport.dsf_objects:
        if not o.path.lower().endswith(".obj"):
            continue
        rows.append((o.id, o.path, o.xy, o.heading_deg,
                     o.y_offset_m if o.kind == "OBJECT_AGL" else None, o.kind))
    # the loader already resolved: hand the resolved path through the
    # index mapping so obj8 never walks the pack a second time
    index = {o.path: o.resolved_path for o in airport.dsf_objects if o.resolved_path}
    objs, rep = obj8.read_placed_objects(rows, None, index, airport.dem.z,
                                         bl.admission_depth_m, bl.min_solid_thickness_m,
                                         bl.contact_band_m, cache,
                                         shell_reaches_grade=bl.shell_reaches_grade,
                                         floor_plate_normal_y_min=bl.floor_plate_normal_y_min,
                                         rim_reaches_grade=bl.rim_reaches_grade,
                                         rim_protrusion_max_fraction=bl.rim_protrusion_max_fraction,
                                         authored_depth_min_m=bl.authored_depth_min_m)
    # THE DECK SIGNATURE BY GEOMETRY (04k): un-flagged plates spanning a
    # mapped bridge way are decks; ``ATTR_hard_deck`` stays primary
    objs, drep = deck_signature.classify(objs, cache, law,
                                         deck_signature.bridge_lines(airport.osm_ways))
    rep.deck_families = drep.families
    rep.deck_signature_families = drep.accepted
    rep.deck_candidate_families = drep.candidates
    rep.deck_records = tuple(drep.records)
    cache.placed["objects"] = (objs, rep)
    return objs, rep


def basin_member_ids(airport, law: "Law",
                     cache: obj8.ResourceCache | None = None) -> frozenset[str]:
    """The placement ids carrying a basin FLOOR WITNESS — rule 1 of
    ``planar/basins``' admission, asked before anything else reads the
    pack's below-zero geometry (10ax (2)).  Rule 1 is the per-placement
    half of the admission and the half that founds a region: the later
    region rules (a runway, a basement, a structure overlap) can only
    REFUSE a region these members made, never make one, so exempting a
    witness here can never exempt a placement no basin would have
    claimed.

    Empty when the airport carries no DEM to judge a ground against (a
    fixture without terrain admits no basin, by rule 1's own terms)."""
    if getattr(airport, "dem", None) is None:
        return frozenset()
    objs, _rep = read_objects(airport, law, cache)
    return frozenset(o.id for o in objs if o.witnesses)
