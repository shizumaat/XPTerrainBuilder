"""THE LOT AT A WALL'S FOOT (#1952 R5; owner RULINGS 2026-11-09a (5)/(14),
2026-11-10a (2)) — geometry only, one reading for its two readers: the wall
terrace (``airport/road_ramp.wall_terraces``: the lot's foot Bands, no
lot->pad pair) and the kerb a foot lot steps down from its pad at
(``planar/foot_kerb``).

A lot is AT A WALL'S FOOT when its page overlaps the LOWER band of a wall
whose low side the pack's own sheets name (``WallComponent.low_side_source
== "sheets"``, ``airport/wall_sheets``); its level is the wall's foot
(``foot_profile``) at the station of the lot's nearest point on the lower
face.  A DEM-witnessed wall's lot keeps its building's level (10-03c)."""
from __future__ import annotations

import typing as _t

__all__ = ["lots_at_foot", "sheet_walls"]


class _FootWall(_t.NamedTuple):
    """The four fields of a wall piece the foot reading takes (a
    ``road_ramp.WallPiece`` carries them too)."""

    lower_band: _t.Any
    lower_face: _t.Any
    foot_profile: tuple | None
    low_side: str


def lots_at_foot(wall, lots: _t.Mapping[int, _t.Any]) -> dict[int, float]:
    """``{lot id: level}`` for every lot of ``lots`` (``{id: polygon}``)
    overlapping the lower band of ``wall`` when its low side is the
    sheets' (module docstring); empty for any other wall.

    A LOT IS AT THE FOOT ONLY WHERE THE WALL RETAINS (#1952): no level for
    a lot whose nearest point on the lower face is nearest a station that
    retains nothing (``foot_profile`` ``None``, the same test as
    ``constraints/wall_zone.face_foot``) -- never a level interpolated
    through it; that lot keeps its building's level (10-03c).  MEASURED
    KMCI ``dsf:objpav15`` (stations 208-270 None): held 299.82 m over a DEM
    of 301.25-301.90 m."""
    band, face = getattr(wall, "lower_band", None), getattr(wall, "lower_face", None)
    prof = tuple(getattr(wall, "foot_profile", None) or ())
    st = [t for t in prof if t[1] is not None]
    if wall.low_side != "sheets" or band is None or band.is_empty or face is None or not st:
        return {}
    import numpy as np
    from shapely.ops import nearest_points
    a = np.asarray(st, float)
    out = {}
    for fid, g in lots.items():
        if g.intersection(band).area <= 0.0:
            continue
        s_ = face.project(nearest_points(g, face)[1])
        if min(prof, key=lambda t: abs(t[0] - s_))[1] is None:
            continue     # a station that retains nothing
        out[int(fid)] = float(np.interp(s_, a[:, 0], a[:, 1]))
    return out


def sheet_walls(airport) -> list[_FootWall]:
    """The pieces of every wall whose low side the pack's sheets name, with
    their sides as read (``airport.retaining_walls``, each carrying its
    ``low_side``, ``airport/wall_sides``)."""
    return [_FootWall(getattr(w, "lower", None), getattr(w, "lower_face", None),
                      getattr(w, "foot_profile", None), "sheets")
            for w in (getattr(airport, "retaining_walls", ()) or ())
            if getattr(w, "low_side", "") == "sheets"]
