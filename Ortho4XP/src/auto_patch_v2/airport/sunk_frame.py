"""THE SUNK FRAME: a pack frame its author drew DOWN from his ground (#2120;
owner RULINGS 2026-11-13u (1), 2026-11-16d, 2026-11-16l).

A placement row's authored lift (``OBJECT_AGL``) is the author's statement of
where his ground stands in the object's frame: ``y = -lift``
(``below_grade_witness.row_depth_under``: "a row drawn on the ground STATES
its own depth under the author's ground").  A frame with a NEGATIVE lift whose
walled parts -- standing on their zero -- reach from at least ``[tunnel.object] floor_sunken_min_m`` under
that ground up to it -- their top within ``[basin] authored_rim_tol_m`` under
it or ``floor_sunken_min_m`` over it (a parapet) -- is SUNK: its walls are a
footing the author buried, and its top is his ground.  A frame standing far
over its author's ground (a viaduct, a terminal sunk into a slope, a portal
whose lift corrected the stock mesh) is no sunk frame: nothing here reads it.
MEASURED (KATL, the 2026-11 pack): ``katl126_wall`` -- a 20 m-wide block of
walls, y 0..20, its road plate at y 20 -- placed ``OBJECT_AGL -19.81``; the
object stage stood its walls' feet (y 0) on the ground and floated the road
plate 20 m (the generic seat reads FEET, ``anchor_rule``).  ``katl127_wall``
(y 0..20, ``-18.29``) stands between the terminal apron and the ground 12 m
under it; it was minted a building pad and stood 11 m over the apron.

THE SEAT (one plate per member, ``retaining_seat.RETAINING_PLATE``'s
datum: the plate's ``y`` on the solved surface at its stations):

* a FLAT sunk frame (no ground step across it) puts its author's ground
  ``y = -lift`` on the ground round its footprint -- the author's own seat,
  its footing buried (13u (1));
* a frame the ground STEPS across (the across witness of
  ``wall_class._step_across`` at least ``[service]
  retaining_wall_clear_step_m``) is a wall between two levels -- a
  retaining wall whatever its authored zero (16d) -- and its author's
  ground is its HIGH side: ``y = -lift`` on the stations of the upper level,
  its footing going where that puts it (13u (1)).  Its footprint is no pad
  (:func:`sunk_shade`, read by ``wall_shade``).

The author's ground stands, never a parapet of our own: the author drew the
parapet (KATL ``katl127_wall`` 1.71 m, ``katl838_underground_wall1`` 1.02 m
-- 16l's "about 1 m").

Nothing here names a pack or an airport; every number is a law value."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

__all__ = ["SunkFrame", "sunk_frames", "sunk_shade"]


#: a frame with a DECK member (``obj8.PlacedObject.deck_kind``: a flagged or
#: signature deck, or its family) is the bridge rule's (§16e), never sunk
DECK_KINDS = frozenset({"flag", "signature", "family"})


@_dc.dataclass(frozen=True)
class SunkFrame:
    """One sunk frame: its partition unit, authored ``lift``, the placement
    ids of its members, its sunk parts' footprint (frame xy) and highest top
    (authored ``y``), whether the ground steps across it, the ``y`` its plate
    puts on the ground and the stations (frame xy) that ground is read at."""

    unit: str
    lift: float
    ids: tuple[str, ...]
    footprint: _t.Any
    top_y: float
    stepped: bool
    plate_y: float
    stations: tuple
    resources: tuple[str, ...] = ()


def _law_numbers(law) -> tuple[float, float, float]:
    """``(floor_sunken_min_m, authored_rim_tol_m, chain_min_height_m)``."""
    st = law.tables.structures
    return (float(st.tunnel.object.floor_sunken_min_m),
            float(st.basin.authored_rim_tol_m),
            float(st.placement.chain_min_height_m))


def _sunk_parts(unit, to_xy, sunk_min: float, rim_tol: float, wall_min: float):
    """``(polygons, highest top)`` of ``unit``'s sunk walled parts, empty
    where its lift is not negative or no part reaches from its buried
    footing to its author's ground."""
    lift = float(getattr(unit, "agl_m", 0.0) or 0.0)
    if not lift < 0.0 or any(str(getattr(m, "deck_kind", "") or "") in DECK_KINDS
                             for m in getattr(unit, "members", ()) or ()):
        return [], 0.0
    ground_y = -lift
    polys: list = []
    top = -np.inf
    for m in getattr(unit, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            if getattr(p, "line", False) or float(p.height_m) < wall_min:
                continue
            base = float(getattr(p, "base_y", 0.0) or 0.0)
            up = base + float(p.height_m)
            # standing on its zero (a depth authored UNDER the zero is
            # ``wall_class``'s depth witness), buried at least ``sunk_min``
            # under the author's ground by the lift alone, its top AT that
            # ground: no more than ``sunk_min`` over it (a parapet), no more
            # than ``rim_tol`` under it
            if base < -rim_tol or base > ground_y - sunk_min \
                    or not ground_y - rim_tol <= up <= ground_y + sunk_min:
                continue
            for rg in getattr(p, "rings", ()) or ():
                if len(rg) < 3:
                    continue
                g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                if not g.is_valid:
                    g = g.buffer(0.0)
                if not g.is_empty and g.area > 0.0:
                    polys.append(g)
                    top = max(top, up)
    return polys, float(top)


def _ring_points(whole, ring: float) -> np.ndarray:
    """Points every ``ring`` metres round ``whole`` grown by ``ring``."""
    grown = whole.buffer(ring)
    pts: list = []
    for g in getattr(grown, "geoms", [grown]):
        n = max(4, int(np.ceil(g.exterior.length / ring)))
        pts.extend(g.exterior.interpolate(float(t)).coords[0]
                   for t in np.linspace(0.0, g.exterior.length, n, endpoint=False))
    return np.asarray(pts, dtype=float).reshape(-1, 2)


def _plate(dem, whole, cfg, lift: float, top_y: float) -> tuple[bool, float, tuple]:
    """``(stepped, plate y, stations)`` for one frame's footprint ``whole``
    (module docstring)."""
    from .dem import dem_z_many
    from .wall_class import _step_across
    ring = float(cfg.retaining_wall_step_ring_m)
    clear = float(cfg.retaining_wall_clear_step_m)
    wide = 2.0 * whole.area / whole.length if whole.length > 0.0 else 0.0
    step = _step_across(dem, whole, wide, max(ring, top_y + lift))
    stepped = step is not None and step >= clear
    xy = _ring_points(whole, ring)
    if not len(xy):
        return stepped, -lift, ()
    if not stepped:
        return False, -lift, tuple(map(tuple, xy))
    z = dem_z_many(dem, xy[:, 0], xy[:, 1])
    ok = np.isfinite(z)
    if not ok.any():
        return True, -lift, ()
    hi = float(np.percentile(z[ok], 90.0))
    return True, -lift, tuple(map(tuple, xy[ok & (z >= hi - clear)]))


def sunk_frames(airport, cfg, law) -> tuple[SunkFrame, ...]:
    """Every sunk frame of ``airport``'s pack partition (module docstring).
    ``cfg`` is ``classify/rules.toml``'s ``[service]`` record, supplied by
    the caller (``airport`` may not read ``classify``)."""
    part = getattr(airport, "partition", None)
    dem = getattr(airport, "dem", None)
    if part is None or dem is None or cfg is None or law is None:
        return ()
    sunk_min, rim_tol, wall_min = _law_numbers(law)
    to_xy = airport.frame.entry()
    out: list[SunkFrame] = []
    for u in part.units:
        polys, top = _sunk_parts(u, to_xy, sunk_min, rim_tol, wall_min)
        if not polys:
            continue
        whole = unary_union(polys)
        if not whole.is_valid:
            whole = whole.buffer(0.0)
        if whole.is_empty:
            continue
        lift = float(u.agl_m)
        stepped, plate_y, stations = _plate(dem, whole, cfg, lift, top)
        if not stations:
            continue
        out.append(SunkFrame(str(getattr(u, "id", "")), lift,
                             tuple(sorted({str(m.id) for m in u.members})), whole, top,
                             stepped, float(plate_y), stations,
                             tuple(sorted({str(m.resource) for m in u.members}))))
    return tuple(out)


def sunk_shade(airport, cfg, law=None):
    """The planar-frame union of every STEPPED sunk frame's footprint -- a
    wall between two levels is never a pad (``wall_shade``) -- or ``None``."""
    if law is None:
        from ..law import Law
        law = Law.load()
    polys = [f.footprint for f in sunk_frames(airport, cfg, law) if f.stepped]
    if not polys:
        return None
    got = unary_union(polys)
    if not got.is_valid:
        got = got.buffer(0.0)
    return None if got.is_empty else got
