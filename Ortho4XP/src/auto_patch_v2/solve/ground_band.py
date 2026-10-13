"""THE GROUND ENVELOPE — no vertex of the design surface leaves the ground
the airport stands on (issue #623).

The design surface is the airport's own ground, graded: every vertex sits
at, or is blended between, levels the elevation model holds under the
airport.  A structure cuts or bridges by its own depth, a datum pins to a
level the ground holds nearby.  So a solved elevation far outside the WHOLE
range of ground under the map is not geometry — it is a number that reached
the solve as a datum and was held exactly (measured: 15 strip vertices
pinned at 1,798 m beside a 535 m runway, solve ``optimal``, because a lake
that runs on into the next tile was levelled off the mountainside at the
tile edge).  The solve cannot tell: a pin is met, the status is optimal.

THE ENVELOPE is the hull of the DEM samples under every map vertex, widened
by ``emit.cockpit.sentinel_drop_m`` — the law's own "this far is not
geometry" distance, the one the census's ``sentinel_elevation`` family
reads.  The HULL and not a percentile band, on purpose: a road tunnel three
kilometres up the valley stands 300 m over the runway on its own ground,
and its own ground is in the hull.  A vertex outside it is outside EVERY
level the airport's ground holds.

Two readers, one derivation: the pipeline fails the airport on a solved
vertex outside it, and publishes the envelope so ``verify`` / the census
price the EMITTED patch against the same two numbers.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["ground_envelope", "outside_envelope"]


def ground_envelope(planar: PlanarMap, law: Law) -> tuple[float, float] | None:
    """``(lowest lawful elevation, highest lawful elevation)`` of the map,
    or ``None`` when no vertex carries a finite DEM sample (a fixture)."""
    dem = [float(v.dem_z) for v in planar.vertices.values()
           if v.dem_z is not None and math.isfinite(float(v.dem_z))]
    if not dem:
        return None
    drop = float(law.tables.emit.cockpit.sentinel_drop_m)
    return min(dem) - drop, max(dem) + drop


def outside_envelope(planar: PlanarMap,
                     z: _t.Sequence[float] | _t.Mapping[int, float],
                     envelope: tuple[float, float] | None
                     ) -> list[dict[str, _t.Any]]:
    """Every map vertex whose solved elevation ``z[vertex id]`` is outside
    ``envelope``, worst first: its id, its canonical lat/lon, the solved
    elevation, the DEM under it and how far outside it stands.  A
    non-finite solved value is outside by definition."""
    if envelope is None:
        return []
    lo, hi = envelope
    out: list[dict[str, _t.Any]] = []
    for vid, v in planar.vertices.items():
        zv = float(z[vid])
        if math.isfinite(zv) and lo <= zv <= hi:
            continue
        over = (zv - hi if zv > hi else lo - zv) if math.isfinite(zv) else math.inf
        out.append({"vertex": vid, "lat": v.key[0], "lon": v.key[1],
                    "z_m": zv, "dem_m": v.dem_z, "outside_m": over})
    out.sort(key=lambda r: -r["outside_m"])
    return out
