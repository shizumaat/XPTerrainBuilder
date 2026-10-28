"""THE GROUND UNDER A WALLED PLATE NEVER RISES THROUGH IT (owner RULINGS
2026-10-27t / 2026-10-27u, #1201; spec ``docs/specs/walled-plate-rsa-spec.md``
§5 (2)).

A runway-end walled plate (``Airport.walled_plates``, recognised by
``airport/walled_plate``) is seated with its top flush with the safety area at
its inner edge (27u), and the safety area ends there (27t, ``model/end_area``).
Under the plate the ground is hidden — the step from the safety area down to
the road at the wall's foot happens there, in the heightfield — and it must
never stand above the plate: every map vertex inside the plate's footprint, off
its inner edge and off the safety area's own faces, takes a HARD ceiling
(``[design] hard_rulings``, ranked in the pad tier over the groundside rows)

    z(v) <= DEM step_inside_m inside the inner edge at the seat station
            nearest v - under_clearance_m

— a CONSTANT, so the vertex under the plate follows and the safety area is
never lifted by it (airside is king).  MEASURED, refuted on the KSEA replay: a
two-way row against the inner-edge vertex lifted the safety area 4.0 m to the
road mapped on the plate; a one-way hard row read its leader at the solve's
initial 0 m and sank the road to it.

Geometry only: no airport is named here (RULINGS 2026-10-05e).  KSEA: the
service road mapped on 16R's plate stood +14.1 m over its DEM.
"""
from __future__ import annotations

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Band, Diff, Linear, Offset, Row, Source
from ..model.planar import PlanarMap

__all__ = ["RULING", "TARGET_RULING", "under_plate_rows", "release_across"]

#: the ruling head ``[design] hard_rulings`` / ``one_way_rulings`` list
RULING = "structures.walled_plate under-plate cap (RULINGS 2026-10-27t/u, #1201)"

#: the ruling head of the under-plate DESIGN TARGET (soft: in no
#: ``[design] hard_rulings`` list)
TARGET_RULING = "structures.walled_plate under-plate target (RULINGS 2026-10-27t/u, #1201)"


def under_plate_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The rows (module docstring), every walled plate of ``airport``."""
    clear = float(law.tables.structures.walled_plate.under_clearance_m)
    out: list[Row] = []
    for p, under in _under(planar, airport):
        ground = _station_ground(airport, p, law)
        if ground is None:
            continue
        sxy, sz = ground
        src = Source("walled_plate_under", RULING, tuple(p.ids))
        tsrc = Source("walled_plate_under", TARGET_RULING, tuple(p.ids))
        for vid in under:
            x, y = planar.vertices[vid].xy
            k = int(np.argmin(np.hypot(sxy[:, 0] - x, sxy[:, 1] - y)))
            top = float(sz[k]) - clear
            out.append(Band(int(vid), None, top, src))
            # the hidden ground's design target IS that level (soft, at the
            # law weight): its lidar is the plate's own step, and a fit to it
            # dragged KSEA 16C's safety area 3.7 m under the plate
            out.append(Linear(((int(vid), 1.0),), top, top, tsrc))
    return out


def release_across(rows: list[Row], planar: PlanarMap, airport: Airport,
                   counts: dict[str, int] | None = None) -> list[Row]:
    """THE PLATE IS THE STEP (#1201 l1201c; RULINGS 2026-10-27t): every
    pair row (``Diff``, ``Offset``, a multi-term ``Linear``) joining a vertex
    UNDER a walled plate (the ceiling's own set) to one that is not is
    withdrawn — the ground under the plate is hidden, and a road drawn
    across it is two surfaces, the safety area's on top and the ground at
    the wall's foot.  MEASURED (KSEA replay): the road grade rows from the
    under-plate vertices pulled 16R's safety area 0.8 m and 16C's 4.0 m
    under the plate's top at the inner edge."""
    under = frozenset(v for _p, vs in _under(planar, airport) for v in vs)
    if not under:
        return rows

    def mixed(vs) -> bool:
        inside = [v in under for v in vs]
        return any(inside) and not all(inside)
    out: list[Row] = []
    n = 0
    for r in rows:
        if isinstance(r, (Diff, Offset)):
            vs = (r.a, r.b)
        elif isinstance(r, Linear) and len(r.terms) > 1:
            vs = tuple(v for v, _c in r.terms)
        else:
            out.append(r)
            continue
        if mixed(vs):
            n += 1
            continue
        out.append(r)
    if counts is not None:
        counts["walled_plate_released"] = n
    return out


def _under(planar: PlanarMap, airport: Airport) -> list[tuple]:
    """Per walled plate, the vertices UNDER it — the published
    ``PlanarMap.plate_under`` (``airport/walled_plate.
    under_plate_vertices``, one derivation), split by footprint."""
    plates = tuple(getattr(airport, "walled_plates", ()) or ())
    under = getattr(planar, "plate_under", None) or frozenset()
    if not plates or not under:
        return []
    from shapely.geometry import Point, Polygon
    out = []
    for p in plates:
        foot = Polygon(p.footprint)
        foot = foot if foot.is_valid else foot.buffer(0.0)
        out.append((p, tuple(sorted(v for v in under
                                    if foot.buffer(0.5).contains(Point(planar.vertices[v].xy))))))
    return out


def _station_ground(airport: Airport, p, law: Law
                    ) -> "tuple[np.ndarray, np.ndarray] | None":
    """``(station xy, DEM there)`` per seat station with a finite DEM, the
    DEM read ``step_inside_m`` inside the inner edge (witness 4's own upper
    sample, clear of the lidar smear down the plate's step): the ceiling
    under the plate is that ground at the station NEAREST the vertex — a
    constant the plate's top (the safety area's solved ground there, the
    seat) stands at or above wherever the safety area is graded in fill.
    MEASURED, refuted (#1201 l1201c, KSEA): the LOWEST station over the
    width sank the service roads up to 4.3 m under their own ground (16C
    117.95 against a DEM of 121.9), and the DEM AT the stations (2 m in,
    on the smear: 117.7 at 16C's east half) held the safety area 3.7 m under
    the plate through the road drawn across it."""
    dem = getattr(airport, "dem", None)
    if dem is None or not p.stations or len(p.inner) < 2 or len(p.outer) < 2:
        return None
    from shapely.geometry import LineString, Point
    wp = law.tables.structures.walled_plate
    back = float(wp.step_inside_m) - float(wp.station_inset_m)
    inner, outer = LineString(p.inner), LineString(p.outer)
    xy, zs = [], []
    for x, y in p.stations:
        pt = Point(float(x), float(y))
        q = inner.interpolate(inner.project(pt))
        o = outer.interpolate(outer.project(q))
        dx, dy = q.x - o.x, q.y - o.y
        n = float(np.hypot(dx, dy))
        sx, sy = (float(x) + dx / n * back, float(y) + dy / n * back) if n > 0 else (x, y)
        xy.append((float(x), float(y)))
        zs.append(float(dem.z(sx, sy)))
    xy_a, z_a = np.array(xy), np.array(zs)
    ok = np.isfinite(z_a)
    return (xy_a[ok], z_a[ok]) if ok.any() else None
