"""A PLATE THAT CONTINUES A RUNWAY'S PAVED END IS SEATED FLUSH WITH IT
(issue #1977; the second reading of the runway-end walled plate, owner
RULINGS 2026-10-27t / 2026-10-27u, ``airport/walled_plate``).

Owner, #1977: "the overrun and retaining wall for runway 5 are provided as an
object, it should be seated so the underside of its shell sits on the runway
end flush."  A pack may model a runway's overrun as an engineered deck on a
retaining structure — the deck carries the pavement on past the runway end
over ground that falls away, and its safety area IS the deck.  The 27t/27u
reading admits a plate only where the safety area ENDS (its inner edge at
s >= half the safety-area length, its wall across the outer end); a plate
that begins AT the paved end is the same structure one step nearer: its top
is the pavement's own continuation, so it is seated by that contact.

THE WITNESSES (geometry and position only, RULINGS 2026-10-05e), read on the
placement's static solid against one runway end:

1. A PLATE — near-horizontal faces (``[bridge] deck_plate_normal_y_min``)
   beyond the end carrying ``[walled_plate] min_area_m2``;
2. POSITION — its NEAR EDGE (the plate boundary nearest the runway, one
   station every ``station_m`` across the runway's own width) lies, as a
   median, within ``pavement_end_reach_m`` of the PAVED end (the runway end
   plus its blast pad / overrun), and the plate covers ``min_cover`` of the
   runway's width there — it continues the pavement, not the safety area;
3. A STRUCTURE — steep faces (|n_y| < ``wall_normal_y_max``) reaching
   ``wall_min_height_m`` or more under the plate: a deck on a wall, not a
   ground decal.

The record is a :class:`WalledPlate`, so every reader of the 27t/27u class
seats and grades it unchanged: ``plate_y`` is the plate's top AT its near
edge (the highest plate face within one station of it), the seat's stations
stand ``station_inset_m`` inside the near edge, on the pavement, and the
whole origin set rides one zero (``rebake_plan`` ``plate_kind = "walled"``).
Its ``inner_s`` / ``inner`` and ``footprint`` start where the plate LEAVES the
pavement (never before the paved end), so the safety area keeps the paved end
and no pavement vertex takes the under-plate ceiling (airside is king).
"""
from __future__ import annotations

import numpy as np

from ..law import Law
from ..model.walled_plate import WalledPlate
from .walled_plate import _coords, _st, _xy, faces

__all__ = ["read"]


def _rows(foot, e, half_w: float, step: float, s_far: float):
    """``(t, near s, far s)`` per station across ``[-half_w, half_w]``."""
    from shapely.geometry import LineString
    rows = []
    for t in np.arange(-half_w, half_w + 1e-9, step):
        cut = foot.intersection(LineString([_xy(e, -50.0, float(t)), _xy(e, s_far, float(t))]))
        if cut.is_empty:
            continue
        ss = [_st(e, x, y)[0] for x, y in _coords(cut)]
        rows.append((float(t), min(ss), max(ss)))
    return rows


def _top_at(f, sel: np.ndarray, s: float, t: float) -> "float | None":
    """The highest plate face over the point ``(s, t)``: its height
    interpolated in the face (barycentric in ``(s, t)``), else ``None``."""
    S, T, Y = f.S[sel], f.T[sel], f.P[sel][:, :, 2]
    d = (T[:, 1] - T[:, 2]) * (S[:, 0] - S[:, 2]) + (S[:, 2] - S[:, 1]) * (T[:, 0] - T[:, 2])
    ok = np.abs(d) > 1e-12
    d = np.where(ok, d, 1.0)
    a = ((T[:, 1] - T[:, 2]) * (s - S[:, 2]) + (S[:, 2] - S[:, 1]) * (t - T[:, 2])) / d
    b = ((T[:, 2] - T[:, 0]) * (s - S[:, 2]) + (S[:, 0] - S[:, 2]) * (t - T[:, 2])) / d
    c = 1.0 - a - b
    inside = ok & (a >= -1e-9) & (b >= -1e-9) & (c >= -1e-9)
    if not inside.any():
        return None
    return float((a * Y[:, 0] + b * Y[:, 1] + c * Y[:, 2])[inside].max())


def read(o, g, e, dem, law: Law) -> "WalledPlate | None":
    """The three witnesses (module docstring) for one placement against one
    runway end ``e`` (``walled_plate._End``), else ``None``."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from .dem import dem_z_many
    wl = law.tables.structures.walled_plate
    half_w = float(getattr(e, "pave_hw", 0.0) or 0.0)
    paved = float(getattr(e, "paved", 0.0) or 0.0)
    reach = float(wl.pavement_end_reach_m)
    if half_w <= 0.0 or reach <= 0.0:
        return None
    f = faces(o, g, e)
    if f is None:
        return None
    s_far = paved + e.L + wl.max_s_beyond_m
    near = f.ok & (f.sc > -reach - 50.0) & (f.sc < s_far) & (np.abs(f.tc) < e.hw + 150.0)
    flat = near & (f.ny >= float(law.tables.structures.bridge.deck_plate_normal_y_min))
    # witness 1: the plate
    if not flat.any() or float(f.area[flat].sum()) < wl.min_area_m2:
        return None
    sel = np.flatnonzero(flat)
    foot = unary_union([p for p in (Polygon(f.P[k, :, :2]) for k in sel)
                        if p.is_valid and p.area > 0.0])
    foot = foot.buffer(1.0).buffer(-1.0)
    if foot.is_empty:
        return None
    # witness 2: its near edge at the paved end, across the runway's width
    rows = _rows(foot, e, half_w, wl.station_m, s_far + 400.0)
    n_rows = int(2.0 * half_w // wl.station_m) + 1
    if len(rows) < wl.min_cover * n_rows:
        return None
    near_s = float(np.median([r[1] for r in rows]))
    if not (-reach <= near_s <= paved + reach):
        return None
    # the plate's top AT its near edge, per station
    tops = [z for z in (_top_at(f, sel, s0 + 1.0, t) for t, s0, _s1 in rows) if z is not None]
    if not tops:
        return None
    plate_y = float(np.median(tops))
    # witness 3: a structure under it
    steep = near & (f.ny < wl.wall_normal_y_max)
    if not steep.any():
        return None
    h = plate_y - float(f.P[steep][:, :, 2].min())
    if h < wl.wall_min_height_m:
        return None
    # where the plate LEAVES the pavement: the safety area ends there and
    # the under-plate ground starts there (never on the pavement)
    inner_s = max(near_s, paved)
    beyond = Polygon([_xy(e, paved, -e.hw - 200.0), _xy(e, s_far + 400.0, -e.hw - 200.0),
                      _xy(e, s_far + 400.0, e.hw + 200.0), _xy(e, paved, e.hw + 200.0)])
    off = foot.intersection(beyond)
    if off.is_empty:
        return None
    big = max(getattr(off, "geoms", [off]), key=lambda p: p.area)
    if big.geom_type != "Polygon":
        return None
    up = [_xy(e, max(r[1], paved) - wl.step_inside_m, r[0]) for r in rows]
    dn = [_xy(e, r[2] + wl.step_beyond_m, r[0]) for r in rows]
    step = 0.0
    if dem is not None:
        dz = (dem_z_many(dem, np.array([p[0] for p in up]), np.array([p[1] for p in up]))
              - dem_z_many(dem, np.array([p[0] for p in dn]), np.array([p[1] for p in dn])))
        dz = dz[np.isfinite(dz)]
        step = float(np.median(dz)) if dz.size else step
    return WalledPlate(
        ids=(o.id,), runway=e.runway, end=e.index, plate_y=plate_y, inner_s=inner_s,
        stations=tuple(_xy(e, r[1] - wl.station_inset_m, r[0]) for r in rows),
        inner=tuple(_xy(e, max(r[1], paved), r[0]) for r in rows),
        outer=tuple(_xy(e, r[2], r[0]) for r in rows),
        footprint=tuple((float(x), float(y)) for x, y in big.exterior.coords),
        height_m=h, step_m=step, end_name=e.name)
