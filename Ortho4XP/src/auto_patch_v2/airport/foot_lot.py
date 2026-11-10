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
    sheets' (module docstring); empty for any other wall."""
    band, face = getattr(wall, "lower_band", None), getattr(wall, "lower_face", None)
    st = [t for t in (getattr(wall, "foot_profile", None) or ()) if t[1] is not None]
    if wall.low_side != "sheets" or band is None or band.is_empty or face is None or not st:
        return {}
    import numpy as np
    from shapely.ops import nearest_points
    a = np.asarray(st, float)
    out = {}
    for fid, g in lots.items():
        if g.intersection(band).area <= 0.0:
            continue
        q = nearest_points(g, face)[1]
        out[int(fid)] = float(np.interp(face.project(q), a[:, 0], a[:, 1]))
    return out


def sheet_walls(airport, cfg) -> list[_FootWall]:
    """The pieces of every wall whose low side the pack's sheets name, with
    their sides as read (``airport.retaining_walls``); ``cfg`` is
    ``classify/rules.toml``'s ``[service]`` record, supplied by the caller."""
    if airport is None or getattr(airport, "partition", None) is None or cfg is None:
        return []
    from .wall_class import wall_class_components
    sides = tuple(getattr(airport, "retaining_walls", ()) or ())
    out = []
    for c in wall_class_components(airport, cfg):
        if str(getattr(c, "low_side_source", "") or "") != "sheets":
            continue
        for g in c.pieces:
            side = next((w for w in sides if w.poly.equals(g)), None)
            if side is not None:
                out.append(_FootWall(getattr(side, "lower", None),
                                    getattr(side, "lower_face", None),
                                    getattr(side, "foot_profile", None), "sheets"))
    return out
