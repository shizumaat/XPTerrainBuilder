"""§37 (6) THE ROAD RAMP'S ROWS (Fable 2026-09-13; owner RULINGS
2026-09-13j item 5, ruled 2026-09-13aj).

The DERIVATION is ``airport/road_ramp.py`` — it reads the DEM along the
road's own route, which is an M1 producer's job (M0 §1: a constraints
module imports ``law`` and ``model`` only) — and the pipeline publishes it
as ``PlanarMap.road_ramp_z``.  THIS module is the generator: one DESIGN
TARGET per governed vertex at the design-target weight (``[design] law``,
the weight every law row is priced at) and one HARD CEILING a
``[cockpit] visual_m`` above it, so smoothness can never lift the road
back onto the airside fill — the mechanism 13aj measured holding KCLT's
``dsf:pol51`` +9.71 m above its own ``preferred_road_z`` target with NO
row binding it.
"""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Band, Linear, Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["GEN", "RULING", "RULING_CEILING", "JOIN_RULING",
           "road_ramp_rows", "road_join_rows"]

GEN = "road_ramp"
#: The ruling HEAD of the DESIGN TARGET (everything before the first
#: parenthesis is what ``solve.design.ruling_head`` reads).
RULING = ("roads.groundside_road ramp to the DEM "
          "(owner 2026-09-13j item 5; spec §37 (6))")
#: The ruling HEAD of the HARD CEILING — registered in ``[design]
#: hard_rulings``, so the ceiling is a CONSTRAINT of the active set and
#: not one more weight in the contest the objective already won (13aj).
RULING_CEILING = ("roads.groundside_road ramp ceiling "
                  "(owner 2026-09-13j item 5; spec §37 (6))")
#: §37 (9) THE COVERAGE-EDGE JOIN's ruling head (owner RULINGS
#: 2026-09-13be): the patch's road takes the CORE ribbon's altitude where
#: its way leaves the coverage — an EQUALITY, because the two surfaces are
#: one road and the pilot drives across the join.
JOIN_RULING = ("roads.coverage_edge join "
               "(owner 2026-09-13be; spec §37 (9))")


def road_ramp_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The DESIGN TARGET (a one-vertex equality, priced at ``[design] law``
    with every other law row) and the HARD CEILING (a ``Band`` at
    ``target + [cockpit] visual_m``, hard through ``[design]
    hard_rulings``) for every groundside-road vertex §37 (6) governs.

    Reads ``PlanarMap.road_ramp_z`` — the channel :func:`with_road_ramp`
    publishes in the pipeline's target-channel order.  A map without it
    (an older capture, a probe that skipped the publisher) mints NOTHING,
    exactly as the taxi and apron trends do: the derivation has one site.
    """
    targets = getattr(planar, "road_ramp_z", None) or {}
    if not targets:
        return []
    vis = float(law.tables.emit.cockpit.visual_m)
    rows: list[Row] = []
    for v in sorted(targets):
        t = float(targets[v])
        ref = next((planar.faces[f].ref for f in planar.vertices[v].incident_faces
                    if planar.faces[f].ref), "")
        src = Source(GEN, RULING, (f"vertex:{v}", ref))
        rows.append(Linear(((v, 1.0),), t, t, src))
        rows.append(Band(v, None, t + vis,
                         Source(GEN, RULING_CEILING, (f"vertex:{v}", ref))))
    return rows


def road_join_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§37 (9): one ``Pin`` per road vertex at a coverage exit, at the core
    ribbon's own altitude just outside (``PlanarMap.road_coverage_join``,
    derived in ``emit/road_join.py``).  A map without the channel mints
    nothing — the derivation has one site."""
    joins = getattr(planar, "road_coverage_join", None) or {}
    rows: list[Row] = []
    for v in sorted(joins):
        ref = next((planar.faces[f].ref for f in planar.vertices[v].incident_faces
                    if planar.faces[f].ref), "")
        rows.append(Pin(v, float(joins[v]),
                        Source(GEN, JOIN_RULING, (f"vertex:{v}", ref))))
    return rows
