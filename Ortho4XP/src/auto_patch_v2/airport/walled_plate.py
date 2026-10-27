"""A WALLED PLATE CAPS A RUNWAY'S SAFETY AREA — the recognition (owner
RULINGS 2026-10-27t / 2026-10-27u, #1201; spec
``docs/specs/walled-plate-rsa-spec.md`` §3).

Owner, #1201: the runway-end retaining walls "are built to cap the runway
end safety area with a road running by their foot, and their top should be
flush with the runway safety area terrain.  They should be recognized by
shape, position, and surrounding features".  A pack placement (its origin
set taken whole) is a RUNWAY-END WALLED PLATE of a runway end when its
static solid, placed, shows all four witnesses (numbers: ``structures.toml
[walled_plate]``):

1. A PLATE — the largest-area ``bin_m`` bin of near-horizontal faces
   (``[bridge] deck_plate_normal_y_min``) carries ``min_area_m2``;
2. POSITION — its INNER EDGE (the plate boundary nearest the runway, one
   station every ``station_m`` across the axis) lies, as a median over the
   safety area's width, at ``[min_s_share x L, L + max_s_beyond_m]`` past
   the end (L the safety area's length, ``tables.runway_safety_area_
   length_m``), and the plate covers ``min_cover`` of that width
   (``tables.zone2_half_width_m`` either side);
3. SHAPE — steep faces (|n_y| < ``wall_normal_y_max``) at its OUTER edge
   reach ``wall_min_height_m`` or more under the plate at ``min_cover`` of
   its covered stations; the wall's height ``h`` is their median depth;
4. SURROUNDINGS — the DEM steps down across the outer edge (``step_inside_m``
   inside the inner edge against ``step_beyond_m`` past the outer one) by
   ``[step_min_share x h, h + foot_tol_m]``: lower ground stands at the foot,
   and a top seated on the safety area leaves no foot floating (27u).

Geometry and position only — no name, no airport (RULINGS 2026-10-05e).
:func:`mark` stamps the record on every placement of the origin set and takes
them out of the readings another law owns: the MSL guard's on-ground
conversion (2026-10-20s, ``origin_built``), the deck verdict (a walled plate
is not a deck candidate), and the below-grade and basin readings (the plate
has its own ground law).  KSEA (#1201): 16R, 16C and 16L are admitted.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..law import Law
from ..law.reference_code import runway_status
from ..law.tables import runway_safety_area_length_m, zone2_half_width_m
from ..model.walled_plate import WalledPlate

__all__ = ["recognise", "mark", "plates_of", "log_line"]


class _End(_t.NamedTuple):
    runway: str
    index: int
    name: str
    xy: tuple[float, float]
    u: tuple[float, float]           # outward along the axis
    L: float                         # the safety area's length
    hw: float                        # its half width


def _ends(airport, law: Law) -> list[_End]:
    out = []
    for rw in getattr(airport, "runways", ()) or ():
        a, b = rw.ends[0].xy, rw.ends[1].xy
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        if d <= 0.0:
            continue
        st = runway_status(rw)
        L = float(runway_safety_area_length_m(law, rw.code_number, rw.code_letter, st))
        hw = float(zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter, st) or 0.0)
        if L <= 0.0 or hw <= 0.0:
            continue
        ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        out.append(_End(rw.id, 0, rw.ends[0].name, a, (-ux, -uy), L, hw))
        out.append(_End(rw.id, 1, rw.ends[1].name, b, (ux, uy), L, hw))
    return out


def _st(e: _End, x, y):
    """``(s, t)``: metres past the end along the axis, metres right of it."""
    dx, dy = x - e.xy[0], y - e.xy[1]
    return dx * e.u[0] + dy * e.u[1], dx * e.u[1] - dy * e.u[0]


def _xy(e: _End, s: float, t: float) -> tuple[float, float]:
    return (e.xy[0] + e.u[0] * s + e.u[1] * t, e.xy[1] + e.u[1] * s - e.u[0] * t)


def _window(e: _End, wl) -> _t.Any:
    """The plan region an inner edge may stand in (witness 2)."""
    from shapely.geometry import Polygon
    s0, s1 = wl.min_s_share * e.L, e.L + wl.max_s_beyond_m
    return Polygon([_xy(e, s0, -e.hw), _xy(e, s1, -e.hw), _xy(e, s1, e.hw), _xy(e, s0, e.hw)])


def _placed_tris(o, g) -> np.ndarray:
    """``(m, 3, 3)`` frame ``(x, y, authored height)`` of the static solid."""
    tris = g.solid
    if g.animated.shape[0]:
        tris = tris[~g.animated]
    v = g.vertices[tris]                                   # (m, 3, 3): x, y, z
    h = math.radians(float(o.heading_deg))
    sn, cs = math.sin(h), math.cos(h)
    X = o.xy[0] + v[:, :, 0] * cs - v[:, :, 2] * sn
    Y = o.xy[1] - (v[:, :, 0] * sn + v[:, :, 2] * cs)
    return np.stack([X, Y, v[:, :, 1]], axis=2)


def _read(o, g, e: _End, dem, law: Law) -> "WalledPlate | None":
    """The four witnesses for one placement against one runway end."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union

    from .dem import dem_z_many
    wl = law.tables.structures.walled_plate
    P = _placed_tris(o, g)
    if not P.shape[0]:
        return None
    S, T = _st(e, P[:, :, 0], P[:, :, 1])
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    nn = np.linalg.norm(n, axis=1)
    ok = nn > 1e-9
    ny = np.where(ok, np.abs(n[:, 2]) / np.maximum(nn, 1e-12), 0.0)
    area = 0.5 * nn
    sc, tc, yc = S.mean(axis=1), T.mean(axis=1), P[:, :, 2].mean(axis=1)
    near = ok & (sc > wl.min_s_share * e.L - 100.0) & \
        (sc < e.L + wl.max_s_beyond_m + 150.0) & (np.abs(tc) < e.hw + 150.0)
    flat = near & (ny >= float(law.tables.structures.bridge.deck_plate_normal_y_min))
    if not flat.any():
        return None
    # witness 1: the plate
    yb = np.round(yc[flat] / wl.bin_m) * wl.bin_m
    levels, inv = np.unique(yb, return_inverse=True)
    per = np.bincount(inv, weights=area[flat])
    best = int(np.argmax(per))
    if per[best] < wl.min_area_m2:
        return None
    sel = np.flatnonzero(flat)[inv == best]
    w = area[sel]
    order = np.argsort(yc[sel])
    cum = np.cumsum(w[order])
    plate_y = float(yc[sel][order][int(np.searchsorted(cum, 0.5 * cum[-1]))])
    tri = [Polygon(P[k, :, :2]) for k in sel]
    foot = unary_union([p for p in tri if p.is_valid and p.area > 0.0])
    foot = foot.buffer(1.0).buffer(-1.0)
    if foot.is_empty:
        return None
    # the stations across the axis: the plate's inner and outer edge
    fs = np.asarray([_st(e, x, y) for x, y in _coords(foot)])
    t0, t1 = float(fs[:, 1].min()), float(fs[:, 1].max())
    s_far = e.L + wl.max_s_beyond_m + 400.0
    rows = []
    for t in np.arange(math.floor(t0 / wl.station_m) * wl.station_m, t1 + 1e-9, wl.station_m):
        cut = foot.intersection(LineString([_xy(e, -50.0, t), _xy(e, s_far, t)]))
        if cut.is_empty:
            continue
        ss = [_st(e, x, y)[0] for x, y in _coords(cut)]
        rows.append((float(t), min(ss), max(ss)))
    across = [r for r in rows if abs(r[0]) <= e.hw]
    n_across = int(2.0 * e.hw // wl.station_m) + 1
    if len(across) < wl.min_cover * n_across:
        return None
    # witness 2: the position of the inner edge
    inner_s = float(np.median([r[1] for r in across]))
    if not (wl.min_s_share * e.L <= inner_s <= e.L + wl.max_s_beyond_m):
        return None
    # witness 3: the outer wall
    # a wall face is one large quad across the plate: a station reads every
    # steep triangle whose plan extent spans it at the outer edge
    steep = near & (ny < wl.wall_normal_y_max)
    t_lo, t_hi = T[steep].min(axis=1), T[steep].max(axis=1)
    s_lo, s_hi = S[steep].min(axis=1), S[steep].max(axis=1)
    y_lo = P[steep][:, :, 2].min(axis=1)
    half = 0.5 * wl.station_m
    depth = []
    for t, s_in, s_out in across:
        m = (t_lo <= t + half) & (t_hi >= t - half) & \
            (s_hi >= s_out - 3.0) & (s_lo <= s_out + 15.0)
        depth.append(plate_y - float(y_lo[m].min()) if m.any() else 0.0)
    walled = [(r, d) for r, d in zip(across, depth) if d >= wl.wall_min_height_m]
    if len(walled) < wl.min_cover * len(across):
        return None
    h = float(np.median([d for _r, d in walled]))
    # witness 4: lower ground at the foot
    up = [_xy(e, r[1] - wl.step_inside_m, r[0]) for r, _d in walled]
    dn = [_xy(e, r[2] + wl.step_beyond_m, r[0]) for r, _d in walled]
    zu = dem_z_many(dem, np.array([p[0] for p in up]), np.array([p[1] for p in up]))
    zd = dem_z_many(dem, np.array([p[0] for p in dn]), np.array([p[1] for p in dn]))
    dz = zu - zd
    dz = dz[np.isfinite(dz)]
    if not dz.size:
        return None
    step = float(np.median(dz))
    if not (wl.step_min_share * h <= step <= h + wl.foot_tol_m):
        return None
    big = max(getattr(foot, "geoms", [foot]), key=lambda p: p.area)
    return WalledPlate(
        ids=(o.id,), runway=e.runway, end=e.index, plate_y=plate_y, inner_s=inner_s,
        stations=tuple(_xy(e, r[1] - wl.station_inset_m, r[0]) for r in across),
        inner=tuple(_xy(e, r[1], r[0]) for r in rows),
        outer=tuple(_xy(e, r[2], r[0]) for r in rows),
        footprint=tuple((float(x), float(y)) for x, y in big.exterior.coords),
        height_m=h, step_m=step, end_name=e.name)


def _coords(g) -> list[tuple[float, float]]:
    import shapely
    return [(float(x), float(y)) for x, y in shapely.get_coordinates(g)]


def recognise(airport, objects: _t.Sequence[_t.Any], cache, law: Law
              ) -> tuple[WalledPlate, ...]:
    """Every runway-end walled plate among ``objects`` (``obj8.PlacedObject``,
    read on ``cache``), each with its origin set's ids (module docstring)."""
    from .msl_feet import origin_key
    from .obj8 import is_stock_library_resource
    wl = law.tables.structures.walled_plate
    dem = getattr(airport, "dem", None)
    if not wl.enabled or dem is None:
        return ()
    ends = _ends(airport, law)
    if not ends:
        return ()
    wins = [(e, _window(e, wl)) for e in ends]
    found: list[WalledPlate] = []
    for o in objects:
        box = getattr(o, "plan_bbox", None)
        if o.resolved is None or box is None or is_stock_library_resource(o.path):
            continue
        hits = [e for e, w in wins if box.intersects(w)]
        if not hits:
            continue
        g = cache.geometry(o.resolved)
        if g is None or not g.solid.shape[0]:
            continue
        for e in hits:
            rec = _read(o, g, e, dem, law)
            if rec is not None:
                found.append(rec)
                break
    if not found:
        return ()
    by_key: dict[tuple, list[str]] = {}
    for o in objects:
        by_key.setdefault(origin_key(o.xy, o.heading_deg), []).append(o.id)
    key_of = {o.id: origin_key(o.xy, o.heading_deg) for o in objects}
    return tuple(_dc.replace(r, ids=tuple(sorted(by_key[key_of[r.ids[0]]]))) for r in found)


def mark(airport, objects: _t.Sequence[_t.Any], cache, law: Law) -> list[_t.Any]:
    """``objects`` with every walled plate's origin set stamped (module
    docstring): ``walled_plate`` set; out of the MSL guard (27u replaces
    2026-10-20s's guard for this class), the deck verdict and the
    below-grade / basin readings."""
    plates = recognise(airport, objects, cache, law)
    if not plates:
        return list(objects)
    of = {i: p for p in plates for i in p.ids}
    out = []
    for o in objects:
        p = of.get(o.id)
        out.append(o if p is None else _dc.replace(
            o, walled_plate=p, origin_built=False, deck_kind="", deck_evidence=(),
            deck_plate=None, below_grade=None, below_grade_comps=(), witnesses=(),
            buried=()))
    return out


def plates_of(objects: _t.Sequence[_t.Any]) -> tuple[WalledPlate, ...]:
    """The distinct records ``mark`` stamped on ``objects``."""
    seen: dict[tuple, WalledPlate] = {}
    for o in objects:
        p = getattr(o, "walled_plate", None)
        if p is not None:
            seen.setdefault(p.ids, p)
    return tuple(seen.values())


def log_line(icao: str, plates: _t.Sequence[WalledPlate]) -> str:
    """The build log's one line."""
    if not plates:
        return f"[walled-plate] {icao}: none recognised"
    return (f"[walled-plate] {icao}: {len(plates)} recognised (RULINGS 2026-10-27t/u): "
            + "; ".join(f"{p.end_name or p.runway} inner {p.inner_s:.1f} m, plate y "
                        f"{p.plate_y:+.2f}, wall {p.height_m:.1f} m, step {p.step_m:.1f} m, "
                        f"{len(p.ids)} row(s)" for p in plates))
