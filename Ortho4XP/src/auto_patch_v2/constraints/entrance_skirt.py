"""THE ENTRANCE SKIRT'S ROWS (#1747; owner RULINGS 2026-11-06c (3) and its
17:37Z clarification: "the terrain on the other/back side of the mouth
object should grade flush to the back of the object at the top of the
object").

The planar map carries an entrance face's skirt as two faces of their own
(``planar/entrance_skirt``; ``Tunnel.entrance_skirt`` = the face's top and
the two faces' refs).  Every vertex of the LEVEL piece is PINNED at the
face's top, and every other vertex of the BANK at its own DEM, so the bank
falls (or rises) to the ground at its own slope; both are SENIOR to the
rim's DEM-by-station pin (``constraints/structures._rim_rows``) on the
vertices the void shares with them.  A vertex an AIRSIDE face shares is
never pinned (airside is king: the skirt keeps off the pavement in plan,
and where a ring still touches it the pavement's own law carries the
vertex); a bank vertex other governed ground shares keeps that ground's
value (the rim's ground rule).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

from ..law.tables import role_side
from ..model.constraints import Source

__all__ = ["skirt_pins"]

#: the rows' ruling head
_SKIRT_RULING = "tunnel.object.entrance_skirt_m (RULINGS 2026-11-06c (3))"


def skirt_pins(planar, airport, law, tn, faces_by_ref: _t.Mapping[str, _t.Sequence],
               vertex_faces, own_roles: _t.Container[str],
               shared: _t.Callable[[int], bool], pin: _t.Callable[..., None],
               inputs: tuple) -> int:
    """Pin ``tn``'s skirt (module doc) through ``pin(v, z, src, senior)``:
    ``faces_by_ref`` maps a ref (its ``#n`` piece suffix aside) to its
    faces, ``vertex_faces`` is the precedence view's vertex -> face ids,
    ``own_roles`` the structure roles and the skirt's, ``shared`` the rim's
    ground rule.  Returns the number pinned."""
    rec = getattr(tn, "entrance_skirt", ())
    if not rec:
        return 0
    top, core_ref, bank_ref = float(rec[0]), rec[1], rec[2]
    src_top = Source("structures", _SKIRT_RULING + ": the ground round an entrance face's "
                     "top is its top", inputs)
    src_bank = Source("structures", _SKIRT_RULING + ": the skirt's bank falls to the DEM "
                      "at emit.design.bank_slope", inputs)

    def ring_vs(ref: str) -> set[int]:
        return {v for f in faces_by_ref.get(ref, ()) for v in planar.ring_vertices(f.ring)}

    def airside(v: int) -> bool:
        return any(planar.faces[f].role not in own_roles
                   and role_side(law, planar.faces[f].role) == "airside"
                   for f in vertex_faces[v])
    core = ring_vs(core_ref)
    n = 0
    for v in sorted(core):
        if not airside(v):
            pin(v, top, src_top, senior=True)
            n += 1
    for v in sorted(ring_vs(bank_ref) - core):
        if airside(v) or shared(v):
            continue
        xy = planar.vertices[v].xy
        z = float(airport.dem.z(xy[0], xy[1]))
        if not math.isnan(z):
            pin(v, z, src_bank, senior=True)
            n += 1
    return n
