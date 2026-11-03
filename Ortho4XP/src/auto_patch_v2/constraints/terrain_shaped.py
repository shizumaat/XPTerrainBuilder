"""THE PATCH UNDER A TERRAIN-SHAPED HARD DECK MEETS IT (issue #1730).

A terrain-shaped hard deck (``airport/terrain_shaped``: a hill with its
highway, tunnel and cloverleaf modelled as one ``ATTR_hard_deck`` skin) is
seated as one rigid unit at its fit to the DEM (``Airport.terrain_decks``).
Where the patch covers the ground under it, that ground is drawn to the
deck: every map vertex under a covered cell of the deck, all of whose faces
are groundside (airside is king), takes ONE soft target (at the law weight)

    z(v) = clamp(DEM(v), z0 + bot - UNDER_M, z0 + top - UNDER_M)

(``geom/terrain_deck.target_at``) -- cut to the deck's top where the ground
would poke through it, filled to its underside where it would leave a gap,
and left on its own ground where that lies inside the deck's span (the hill
over a tunnel).  No trench, no deck datum and no pad: the deck is not a
bridge.
"""
from __future__ import annotations

import numpy as np

from ..geom.terrain_deck import target_at
from ..law import Law
from ..law.tables import role_side
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["RULING", "deck_surface_rows"]

#: the ruling head of the target (soft: in no ``[design]`` register)
RULING = "structures.terrain_shaped deck surface target (#1730)"


def deck_surface_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The rows (module docstring), every terrain-shaped deck of ``airport``."""
    decks = tuple(getattr(airport, "terrain_decks", ()) or ())
    if not decks or not planar.vertices:
        return []
    ids = [v for v in planar.vertices
           if planar.vertices[v].incident_faces
           and all(role_side(law, r) == "groundside" for r in planar.roles_at(v))]
    if not ids:
        return []
    xy = np.array([planar.vertices[v].xy for v in ids], dtype=float)
    dem = _ground(airport.dem, xy)
    out: list[Row] = []
    for f in sorted(decks, key=lambda f: f.id):
        target, under = target_at(f, xy[:, 0], xy[:, 1], dem)
        src = Source("terrain_shaped_deck", RULING, (f.id,))
        for k in np.flatnonzero(under & np.isfinite(target)):
            t = float(target[k])
            out.append(Linear(((int(ids[k]), 1.0),), t, t, src))
    return out


def _ground(dem, xy: np.ndarray) -> np.ndarray:
    many = getattr(dem, "z_many", None)
    if many is not None:
        return np.asarray(many(xy[:, 0], xy[:, 1]), dtype=float)
    return np.array([dem.z(float(x), float(y)) for x, y in xy], dtype=float)
