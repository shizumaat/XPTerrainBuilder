"""A DECK-ROOFED BUILDING: a pack building whose roof is an airside deck
(owner 2026-11-06T01:06Z, LFSB: "a unique building that the entire roof is
a hard deck apron that aircraft drive on, currently our terrain is covering
some of its walls").  The rule: a building whose roof is a hard deck
(``ATTR_hard`` or ``ATTR_hard_deck``) is an airside deck -- the apron welds
flush to the roof edge, and its walls are fully exposed, cut down to the
building's floor around it.

It is a split-level building (``airport/split_level``) whose UPPER FLOOR
is its roof, and it is read as one: the record is a
:class:`~.split_level.SplitLevel`, so ``planar/split_level_pit`` cuts its
pit, holds the open sides flush and cuts the back down.

THE WITNESS IS THE ROOF PLATE AND THE WALLS UNDER IT.  A member of a
family (one frame) carrying a FLAT plan-bearing hard plate
(:attr:`~.obj8.ObjGeometry.hard_deck` or its ``ATTR_hard`` triangles,
relief within ``split_level.BAND_M``) of at least ``[building_pad]
min_area_m2``; its plan's rotated rectangle gives four SIDES, and the
family's walls under it give each side's foot (``split_level._side_feet``).
A BUILDING is walled on all four sides under its roof (a bridge deck
passes a road or a taxiway under it: a side with no foot), and its floor
is the lowest foot, a storey (``low_level_min_step_m``) or more under the
roof.  A side whose outside lies on APRON (``law.tables.apron_roles``;
half its stations or more) is OPEN -- the apron meets the roof there --
and every other side is TALL; a deck with no open side, or no tall one,
is no deck-roofed building (a car park's roof meets no apron; an arrestor
bed's meets the runway), and the roof IS the apron's ground: the DEM
along the open sides stands within half a storey of the roof as placed
(the DEM under the anchor, plus its AGL, plus the roof's y) -- a flat
roof over a building standing ON the apron is no deck.

Pure reading: nothing names a pack, a resource or an airport."""
from __future__ import annotations

import statistics as _st
import typing as _t

import numpy as np
from shapely.geometry import LineString, MultiPoint, Polygon

from . import obj8 as _obj8
from .split_level import (BAND_M, SplitLevel, _airside_share, _families, _ground,
                          _side_feet, _solids)

__all__ = ["read_deck_roofs"]


def _plate(g: _obj8.ObjGeometry) -> "np.ndarray | None":
    """The plan-bearing hard triangles of ``g`` (its deck, else its
    ``ATTR_hard`` plate), or ``None``."""
    for kind in (_obj8.HARD_DECK, _obj8.HARD):
        tri = g.solid[g.hardness == kind]
        if tri.shape[0]:
            P = g.vertices[tri]
            n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
            tri = tri[np.abs(n[:, 1]) > 1e-6]
            if tri.shape[0]:
                return tri
    return None


def read_deck_roofs(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                    law, dem_z, airside) -> tuple[list[SplitLevel], list[str]]:
    """Every deck-roofed building of ``objects`` (module docstring), as
    split-level records, and one note per roof plate read.  ``airside`` is
    a prepared plan geometry of the APRON pavement (frame metres)."""
    bp = law.tables.structures.building_pad
    cover = float(getattr(bp, "split_level_wall_cover", 0.0) or 0.0)
    step = float(getattr(bp, "low_level_min_step_m", 0.0) or 0.0)
    if cover <= 0.0 or step <= 0.0 or dem_z is None or airside is None:
        return [], []
    probe, pmin = float(bp.split_level_probe_m), float(bp.min_area_m2)
    out: list[SplitLevel] = []
    notes: list[str] = []
    for fam in _families(objects):
        got = _solids(fam, cache)
        if got is None:
            continue
        v, t = got
        for m in fam:
            g = cache.geometry(m.resolved)
            tri = None if g is None or g.solid is None else _plate(g)
            if tri is None:
                continue
            P = g.vertices[tri]
            area = float(0.5 * np.abs(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])[:, 1]).sum())
            y_up = float(np.median(P[:, :, 1]))
            if area < pmin or float(np.ptp(P[:, :, 1])) > BAND_M:
                continue
            rect = MultiPoint(P[:, :, [0, 2]].reshape(-1, 2).tolist()).minimum_rotated_rectangle
            if rect.geom_type != "Polygon":
                continue
            cs = list(rect.exterior.coords)[:4]
            sides = [(cs[i], cs[(i + 1) % 4]) for i in range(4)]
            feet = _side_feet(v, t, sides, probe, cover)
            known = [f for f in feet if f is not None]
            if len(known) < len(feet) or y_up - min(known) < step:
                continue
            aff = _obj8.placement_affine(m.xy, m.heading_deg)

            def frame(p, a=aff):
                return (a[0] * p[0] + a[1] * p[1] + a[4], a[2] * p[0] + a[3] * p[1] + a[5])
            segs = [LineString([frame(p0), frame(p1)]) for p0, p1 in sides]
            foot = Polygon([frame(c) for c in cs])
            centre = foot.centroid.coords[0]
            share = [_airside_share(airside, s, centre) for s in segs]
            opened = [s for s, a in zip(segs, share, strict=True) if a >= 0.5]
            closed = [s for s, a in zip(segs, share, strict=True) if a < 0.5]
            name = m.path.rsplit("/", 1)[-1]
            y_lo = min(known)
            g_open = [z for s in opened for z in _ground(dem_z, s, centre)]
            g_closed = [z for s in closed for z in _ground(dem_z, s, centre)]
            try:
                roof_z = float(dem_z(*m.xy)) + float(getattr(m, "agl_m", 0.0) or 0.0) + y_up
            except Exception:  # noqa: BLE001 -- off the raster
                roof_z = float("nan")
            at_ground = bool(g_open) and abs(_st.median(g_open) - roof_z) < 0.5 * step
            ok = bool(opened) and bool(closed)
            notes.append(f"{m.id} {name}: hard roof {area:.0f} m2 at y {y_up:+.1f}, floor y "
                         f"{y_lo:+.1f}, airside sides {len(opened)} of 4"
                         + (": DECK-ROOFED" if ok and at_ground and g_closed
                            else ": refused, no apron meets the roof" if not opened
                            else ": refused, no tall side" if not closed
                            else f": refused, the roof stands {roof_z - _st.median(g_open):+.1f}"
                            " m off the apron's ground" if g_open and g_closed
                            else ": refused, no ground read"))
            if not (ok and at_ground and g_closed):
                continue
            out.append(SplitLevel(str(m.id), tuple(str(o.id) for o in fam),
                                  tuple(sorted({o.path for o in fam})), foot,
                                  round(y_lo, 3), round(y_up, 3), tuple(opened), tuple(closed),
                                  round(_st.median(g_open), 3), round(_st.median(g_closed), 3),
                                  (float(m.xy[0]), float(m.xy[1]))))
    return out, notes
