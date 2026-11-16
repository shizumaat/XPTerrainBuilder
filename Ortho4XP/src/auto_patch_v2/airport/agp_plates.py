"""THE GROUND AT A FOLLOWER'S GROUND FLOOR: ITS PLATES (#2090 C1; spec
``2090-agp-group-groundside-spec.md`` C1 and amendment C; owner
2026-11-14T20:41Z "all the parking garages and central terminal are seated
too low burying the bottom floor of the garages").

At the pack stage, once a group's datum is predicted (``airport/agp_group``),
every FOLLOWER's up-facing static floors standing within ``[agp]
ground_band_m`` of its datum (``agp_ground._connector_floors(band=)``, read
through the pack's floor cache, ``airport/agp_floors``) are its GROUND
FLOORS.  Each connected part of their plan is a PLATE: its level is ``L =
zero_pred + y - deck_flush_m``, ``y`` the floors' plan-area median height;
a part under ``floor_min_area_m2`` or whose median ``|L - DEM|`` exceeds
``plate_max_off_m`` is listed, not built — the DEM gate reads only an inset
that is credible lidar (#2116 R2 G2, ``law/inset_class``); on a coarse DEM
the plate is built on the pack's evidence and listed ``agp_plate_unchecked``.  ``AgpGroup.plates`` carries them;
the planar stage grades them (``planar/agp_ground``) and the rows hold the
ground at the floor (``constraints/agp_level``).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..model.agp_group import AgpGroup, AgpPlate
from .agp_gap_plates import with_gap_plates

__all__ = ["with_plates"]


def _frame_tris(tris: np.ndarray, lat0: float, lon0: float, crs: str) -> np.ndarray:
    """``(k, 3, 3)`` local east / north / y triangles in the frame's x / y."""
    from pyproj import Transformer

    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(lat0)
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    x, y = fwd.transform(lon0 + tris[:, :, 0] / mo, lat0 + tris[:, :, 1] / ml)
    return np.stack([np.asarray(x, float), np.asarray(y, float), tris[:, :, 2]], axis=2)


def _parts(tris: np.ndarray):
    """The connected plan parts of the triangles (a 1 cm grid closes the
    seams between pieces)."""
    import shapely
    polys = shapely.polygons(tris[:, :, :2])
    polys = polys[shapely.area(polys) > 1e-6]
    if not len(polys):
        return []
    return [p for p in shapely.get_parts(shapely.union_all(polys, grid_size=0.01))
            if p.geom_type == "Polygon"]


def _member_plates(g: AgpGroup, row: str, tris: np.ndarray, dem, agp, flush: float,
                   lidar: bool = True) -> list[AgpPlate]:
    import shapely

    from .dem import dem_z_many
    from .object_floor import _median_z
    zp = g.zero_pred(row)
    out = []
    if zp is None or not tris.shape[0]:
        return out
    cen = tris[:, :, :2].mean(axis=1)
    for k, part in enumerate(sorted(_parts(tris), key=lambda p: -p.area)):
        inside = shapely.contains_xy(part.buffer(0.02), cen[:, 0], cen[:, 1])
        mine = tris[inside]
        y = _median_z(mine) if mine.shape[0] else 0.0
        L = float(zp) + float(y) - flush
        pts = np.asarray(shapely.segmentize(part.exterior, 10.0).coords)[:, :2]
        rp = part.representative_point()
        pts = np.vstack([pts, [[rp.x, rp.y]]])
        dz = dem_z_many(dem, pts[:, 0], pts[:, 1]) if dem is not None else np.full(len(pts),
                                                                                    np.nan)
        fin = np.isfinite(dz)
        off = float(np.median(np.abs(L - dz[fin]))) if fin.any() else math.inf
        why, built = "", True
        if part.area < float(agp.floor_min_area_m2):
            why, built = f"agp_plate_small: {part.area:.0f} m² < floor_min_area_m2", False
        elif off > float(agp.plate_max_off_m) and lidar:
            why, built = (f"agp_plate_off_dem: median |L - DEM| {off:.2f} > plate_max_off_m",
                          False)
        elif off > float(agp.plate_max_off_m):
            # #2116 R2 G2 (owner RULINGS 2026-11-16s/t): the DEM gate reads
            # only credible lidar; on a coarse DEM the pack's floor stands
            why = f"agp_plate_unchecked: |L - DEM| {off:.2f} (coarse DEM)"
        out.append(AgpPlate(g.id, row, k, tuple((float(a), float(b))
                                                for a, b in part.exterior.coords[:-1]),
                            tuple(tuple((float(a), float(b)) for a, b in h.coords[:-1])
                                  for h in part.interiors),
                            round(float(y), 4), round(L, 4), round(float(part.area), 1),
                            round(off, 3), built, why))
    return out


def _floor_plan(m, lat0: float, lon0: float, memo: dict, agp, airport):
    """A zero-argument reader of member ``m``'s whole floor plan ``(k, 3,
    2)`` in the frame (every up-facing floor at any height), read once."""
    from .agp_ground import _connector_floors
    got: list = []

    def read() -> np.ndarray:
        if not got:
            loc = _connector_floors(m, lat0, lon0, memo, agp, band=math.inf)
            got.append(_frame_tris(loc, lat0, lon0, airport.frame.crs)[:, :, :2]
                       if loc.shape[0] else np.zeros((0, 3, 2)))
        return got[0]
    return read


def _read_plates(airport, law, groups: _t.Sequence[AgpGroup]
                ) -> tuple[tuple[AgpGroup, ...], list[str]]:
    """``(groups with their plates, notes)`` (module doc)."""
    from .agp_ground import _connector_floors, member_feet
    from .agp_group import members_of
    agp = law.tables.structures.agp
    flush = float(law.tables.structures.bridge.deck_flush_m)
    governed = [g for g in groups if g.governor is not None]
    if not governed:
        return tuple(groups), []
    lat0, lon0 = airport.frame.transformers()[1](0.0, 0.0)
    by_row = {m.row: m for m in members_of(airport)}
    memo: dict = {}
    out, notes = [], []
    # #2116 R2 G2: ONE reading of the inset's class (``law/inset_class``)
    from ..law.inset_class import lidar_credible
    lidar = lidar_credible(airport, law)
    for g in groups:
        if g.governor is None:
            out.append(g)
            continue
        plates: list[AgpPlate] = []
        for fm in g.followers():
            m = by_row.get(fm.row)
            if m is None:
                continue
            loc = _connector_floors(m, lat0, lon0, memo, agp, band=float(agp.ground_band_m))
            if not loc.shape[0]:
                continue
            tris = _frame_tris(loc, lat0, lon0, airport.frame.crs)
            mine = _member_plates(g, fm.row, tris, getattr(airport, "dem", None), agp, flush,
                                  lidar)
            # #2116 R2 C1b: the open strips between two ground-floor parts
            feet = member_feet(m, lat0, lon0, memo, float(agp.ground_band_m))
            plates += with_gap_plates(mine, _frame_tris(feet, lat0, lon0, airport.frame.crs),
                                      _floor_plan(m, lat0, lon0, memo, agp, airport),
                                      g.zero_pred(fm.row), agp, flush,
                                      getattr(airport, "dem", None), notes)
        for p in plates:
            if p.built or p.area_m2 >= 10.0:
                notes.append(f"{g.id} {p.member} plate#{p.k}: y {p.y:+.2f} L {p.level:.2f} "
                             f"{p.area_m2:.0f} m², |L - DEM| {p.dem_off_m:.2f}"
                             + (f" — {p.why}" if p.built and p.why else "")
                             + ("" if p.built else f" — {p.why}, not built"))
        out.append(_dc.replace(g, plates=tuple(plates)))
    return tuple(out), notes


def with_plates(airport, law, notes_out: "list | None" = None):
    """``airport`` with every governed group's plates read (:func:`_read_plates`)."""
    groups = tuple(getattr(airport, "agp_groups", ()) or ())
    if not groups or law is None:
        return airport
    got, notes = _read_plates(airport, law, groups)
    if notes_out is not None:
        notes_out.extend(notes)
    return _dc.replace(airport, agp_groups=got)
