"""A PIT STANDS UNDER THE AUTHOR'S GROUND (#1950; owner RULINGS 2026-11-07b
(1): "a pack's below-grade intent (tunnel, trench, pit, object floor) is
judged against the pack's OWN ground plates — the author's ground — never
against our terrain or the placement zero, for every airport").

Basin rule 1 (``airport/obj8``) reads each component's floor against the
DEM under its centroid — our terrain, not the pack's.  Once the region is
built, its deepest member floor is read again against the author's ground
around the ring (``airport/below_grade_witness``, the members' own faces
left out): a region whose floor stands less than ``admission_depth_m``
under that ground is no pit, and is refused with both readings.  Where no
plate reads around it, the DEM stands (the witness's own fallback).

No new law number; nothing here names a pack or an airport.
"""
from __future__ import annotations

import typing as _t

__all__ = ["author_ground_refusal"]


def author_ground_refusal(bid: str, ring, wits: _t.Sequence, member_ids: _t.AbstractSet[str],
                          ground, law, site: str) -> "str | None":
    """The refusal of region ``bid`` (``ring``, its member witnesses
    ``wits``) when its deepest floor stands less than ``admission_depth_m``
    under the author's ground around it, else ``None``."""
    from ..airport.below_grade_witness import depth_under
    bl = law.tables.structures.basin
    if ground is None or not wits:
        return None
    floor = min(float(w.z_min) for w in wits)
    b = depth_under(floor, ring, member_ids, ground, law, "its floor")
    if b.depth != b.depth or b.depth >= bl.admission_depth_m:
        return None
    return (f"{bid}: {ring.area:.0f} m2 — {b.why} (< admission_depth_m "
            f"{bl.admission_depth_m}): no pit under the author's ground (RULINGS "
            f"2026-11-07b (1), #1950) at {site}")
