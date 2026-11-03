"""D1 — DUPLICATE PLACEMENTS (issue #1707, "Optimise pack").

A pack that places the same object twice on the same spot draws it
twice: measured on one heavy airport pack (the frame-rate finding of
2026-10-30), 2,720 placements were such repeats — same object, within
0.2 m, heading within 1°, same height — 53.4 M triangles drawn for
nothing.  The rows are found by ``dsf_write.duplicate_rows`` with the
tolerances below; the FIRST of each group stays, unless the placement
plan edits another member: then the edited rows stay (they carry the
seating) and the unedited ones go.
"""
from __future__ import annotations

import typing as _t

__all__ = ["DEFAULTS", "drop_set"]

#: metres apart, degrees of heading apart, metres of height apart
DEFAULTS: dict[str, float] = {"tol_m": 0.2, "tol_deg": 1.0, "tol_h": 0.001}


def drop_set(lines: _t.Sequence[str], params: _t.Mapping[str, float],
             edited: _t.AbstractSet[int] = frozenset()
             ) -> tuple[set[int], dict[str, int]]:
    """The duplicate ordinals to delete from the dump ``lines``, and
    ``{"dropped": n, "groups": g}``."""
    from ..dsf_write import duplicate_rows  # dsf_write imports this package
    groups = duplicate_rows(
        lines, tol_m=float(params.get("tol_m", DEFAULTS["tol_m"])),
        tol_deg=float(params.get("tol_deg", DEFAULTS["tol_deg"])),
        tol_h=float(params.get("tol_h", DEFAULTS["tol_h"])))
    drop: set[int] = set()
    for first, others in groups.items():
        members = [first, *others]
        keep = [o for o in members if o in edited] or [first]
        drop.update(o for o in members if o not in keep)
    return drop, {"dropped": len(drop), "groups": len(groups)}
