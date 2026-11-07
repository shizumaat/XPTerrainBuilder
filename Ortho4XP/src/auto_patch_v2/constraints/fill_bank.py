"""THE FILL'S TOE IS ON THE GROUND (owner RULINGS 2026-11-06a (2); #1915;
spec ``docs/specs/old-dem-fill-spec.md`` §2 (3): "its TOE vertices carry
the ground datum (z = DEM, the toe is on current ground)").

A fill-bank piece (``planar/fill_bank``) carries the weak ground datum at
the fill's level on every vertex (``solve/design_ground``), and the bending
term rounds a steep embankment's toe and crest off it: MEASURED on the
FHSH capture, the bank's ring stood up to 4.1 m off its fill, its toe 3.2 m
over the DEM the core mesh meets there.  So every vertex of a bank piece
that stands on the patch's open edge (an edge with no face beyond it: the
toe, or the stand-off gap beside a road terrace) and belongs to bank pieces
alone is pinned at its sampled level — the fill's, which is the DEM's at
the toe and the terrace's beside a road.  Its crest, shared with the zone
bands, keeps the zone law.  No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap, is_fill_bank_ref

__all__ = ["fill_toe_pins", "GEN", "RULING"]

GEN = "fill_toe_pins"
RULING = "zones.adjacent_ground old-DEM fill toe"


def fill_toe_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One hard pin per open-edge vertex of the fill bank (docstring)."""
    bank = {f.id for f in planar.faces.values() if is_fill_bank_ref(f.ref)}
    if not bank:
        return []
    rows: list[Row] = []
    seen: set[int] = set()
    for e in planar.edges.values():
        if (e.left_face is None) == (e.right_face is None):
            continue
        if (e.left_face if e.left_face is not None else e.right_face) not in bank:
            continue
        for v in (e.a, e.b):
            vx = planar.vertices[v]
            if v in seen or vx.dem_z is None or not set(vx.incident_faces) <= bank:
                continue
            seen.add(v)
            rows.append(Pin(v, float(vx.dem_z), Source(GEN, RULING, (f"vertex:{v}",))))
    return rows
