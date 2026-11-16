"""THE SUNK WITNESS: a wall its author drew DOWN from his ground, read by
its row's negative lift (#2120 R2, spec ``docs/specs/2120-R2.md`` §1;
owner RULINGS 2026-11-16d, 16l, 16n, 13t, 13u (1)).

The fourth witness of ``airport/wall_class.wall_class_components``, tried
only for a component the three others (its height, its buried face, the
pack's sheets) left retaining nothing.  It emits nothing of its own: the
component it admits is an ordinary retaining :class:`WallComponent`, read
by every consumer of the wall class (two sides, band set-back, wall slope,
wall zone, road cut-back, the seat).

R1 A placement row's authored lift (``OBJECT_AGL``) is the author's ground
   at the row origin IN HIS OWN MESH: ``y_g = -lift``.  It says which of the
   frame's LEVELS the origin stands on; it is never added to our ground (the
   author's mesh is hand-flattened: KATL's plateaus 305/290/285/278 against
   a lidar 4.7 m under to 8.5 m over at the same origins).
R2 UPPER ORIGIN: a walled part standing on its zero, buried at least
   ``[tunnel.object] floor_sunken_min_m`` under ``y_g`` by the lift, its
   top ``T`` within ``[basin] authored_rim_tol_m`` under ``y_g`` and
   ``floor_sunken_min_m`` over it (the author's parapet, 16l: KATL
   ``katl126`` 0.19, ``katl127`` 1.71, ``katl838`` 1.02 m) holds its upper
   ground at ``y_up = y_g``.
R3 PLATE-TOPPED: a walled part standing on its zero, capped by a
   near-horizontal plate of its own frame at ``T`` covering at least half
   its plan, with a mapped road (no bore, no ``covered``, no negative
   ``layer``) running on that plate at least ``[service]
   retaining_wall_min_length_m``, holds its upper ground at the plate:
   ``y_up = T`` whatever ``y_g`` says (KATL ``katl125``: its origin on the
   low level, lift -4.57, its road plate at y 20).
R4 TWO LEVELS: R2 / R3 count only where the ground steps across the BLOCK
   (the union of the frame's walled parts the same rule reads) by
   ``[service] retaining_wall_clear_step_m`` on at least half the across
   samples (``wall_class._across_pairs`` at the wall class's own ring:
   ``retaining_wall_step_ring_m`` or the solid height, whichever is more).
   A flat sunk frame is no wall: ELLX ``pool_5`` (lift -2.20, walls 3-4 m)
   steps 2 m on none of its samples 4 m out (54 % 8 m out: the slope it is
   sunk in).  It RETAINS that step (the 90th percentile of the samples),
   capped at ``y_up - base``.
R5 THE SEAT is ``retaining_seat``'s: ``y_up`` on the solved upper ground
   beside the block; its footing goes where that puts it (13u (1)).

Nothing here names a pack or an airport; every number is a law value."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

__all__ = ["SunkReading", "sunk_wall"]


#: a frame with a DECK member (``obj8.PlacedObject.deck_kind``: a flagged or
#: signature deck, or its family) is the bridge rule's (§16e), never sunk
DECK_KINDS = frozenset({"flag", "signature", "family"})

#: the across samples that must step (R4)
STEPPED_SHARE = 0.5


@_dc.dataclass(frozen=True)
class SunkReading:
    """What the sunk witness reads of one walled part: the height it
    retains, the authored ``y`` of its upper ground (``y_up``) and which
    rule read it (``"upper"`` R2 / ``"plate"`` R3)."""

    retained_m: float
    y_up: float
    rule: str


def _numbers(law) -> tuple[float, float]:
    """``(floor_sunken_min_m, authored_rim_tol_m)``."""
    st = law.tables.structures
    return float(st.tunnel.object.floor_sunken_min_m), float(st.basin.authored_rim_tol_m)


def sunk_wall(airport, unit, part, whole, wide: float, cfg, law=None
              ) -> SunkReading | None:
    """The sunk witness's reading of ``part`` (a walled part of placement
    ``unit``, its footprint ``whole`` in frame xy, ``wide`` across), or
    ``None`` where R2 / R3 / R4 do not hold (module doc).  ``cfg`` is
    ``classify/rules.toml``'s ``[service]`` record, supplied by the caller."""
    lift = float(getattr(unit, "agl_m", 0.0) or 0.0)
    dem = getattr(airport, "dem", None)
    if not lift < 0.0 or dem is None or getattr(part, "line", False) or \
            any(str(getattr(m, "deck_kind", "") or "") in DECK_KINDS
                for m in getattr(unit, "members", ()) or ()):
        return None
    if law is None:
        from ..law import Law
        law = Law.load()
    sunk_min, rim_tol = _numbers(law)
    base = float(getattr(part, "base_y", 0.0) or 0.0)
    top = base + float(part.height_m)
    y_g = -lift
    if abs(base) > rim_tol:
        return None                     # it does not stand on its zero
    if _upper(base, top, y_g, sunk_min, rim_tol):
        y_up, rule = y_g, "upper"       # R2
    elif _road_plate(airport, unit, part, whole, top, cfg, law, rim_tol):
        y_up, rule = top, "plate"       # R3
    else:
        return None
    block = _block(airport, unit, part, whole, rule, y_g, top, sunk_min, rim_tol)
    step = _two_levels(dem, block, 2.0 * block.area / block.length,
                       max(float(cfg.retaining_wall_step_ring_m), float(part.height_m)), cfg)
    if step is None:
        return None                     # R4: a flat sunk frame is no wall
    return SunkReading(min(step, y_up - base), float(y_up), rule)


def _upper(base: float, top: float, y_g: float, sunk_min: float, rim_tol: float) -> bool:
    """R2's window: standing on its zero, buried ``sunk_min`` under ``y_g``
    by the lift, its top within ``rim_tol`` under ``y_g`` / ``sunk_min``
    over it."""
    return abs(base) <= rim_tol and base <= y_g - sunk_min and \
        y_g - rim_tol <= top <= y_g + sunk_min


def _block(airport, unit, part, whole, rule: str, y_g: float, top: float,
           sunk_min: float, rim_tol: float):
    """THE BLOCK R4 reads: the union of ``unit``'s walled parts the same rule
    reads (R2's window, or R3's top at ``top``), standing on the ground --
    a frame is judged whole: a pool sunk in a slope steps across each of its
    thin walls, never across the pool (ELLX ``pool_5``)."""
    to_xy = airport.frame.entry()
    polys = [whole]
    for m in getattr(unit, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            if p is part or getattr(p, "line", False) or not (getattr(p, "feet", None) is None
                                                              or len(p.feet) > 0):
                continue
            b = float(getattr(p, "base_y", 0.0) or 0.0)
            t = b + float(p.height_m)
            if not (_upper(b, t, y_g, sunk_min, rim_tol) if rule == "upper"
                    else abs(b) <= rim_tol and abs(t - top) <= rim_tol):
                continue
            for rg in getattr(p, "rings", ()) or ():
                if len(rg) >= 3:
                    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                    g = g if g.is_valid else g.buffer(0.0)
                    if not g.is_empty and g.area > 0.0:
                        polys.append(g)
    got = unary_union(polys)
    return got if got.is_valid else got.buffer(0.0)


def _two_levels(dem, whole, wide: float, ring: float, cfg) -> float | None:
    """R4: the step across ``whole`` (the 90th percentile of its across
    samples ``ring`` out) where at least :data:`STEPPED_SHARE` of them step
    ``retaining_wall_clear_step_m``, else ``None``."""
    from .dem import dem_z_many
    from .wall_class import _across_pairs
    near, _wall, far = _across_pairs(whole, wide, ring)
    if len(near) < 4:
        return None
    d = np.abs(dem_z_many(dem, near[:, 0], near[:, 1]) - dem_z_many(dem, far[:, 0], far[:, 1]))
    d = d[np.isfinite(d)]
    if d.size < 4 or np.mean(d >= float(cfg.retaining_wall_clear_step_m)) < STEPPED_SHARE:
        return None
    return float(np.percentile(d, 90.0))


def _road_plate(airport, unit, part, whole, top: float, cfg, law, rim_tol: float) -> bool:
    """R3: a near-horizontal plate of ``unit``'s frame at ``top`` (within
    ``rim_tol``; flat: under ``rim_tol`` tall) covering at least half of
    ``whole``, a mapped road running on it at least
    ``retaining_wall_min_length_m``."""
    to_xy = airport.frame.entry()
    plates = []
    for m in getattr(unit, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            if p is part or getattr(p, "line", False) or float(p.height_m) > rim_tol \
                    or abs(float(getattr(p, "base_y", 0.0) or 0.0) - top) > rim_tol:
                continue
            for rg in getattr(p, "rings", ()) or ():
                if len(rg) >= 3:
                    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                    g = g if g.is_valid else g.buffer(0.0)
                    if not g.is_empty:
                        plates.append(g)
    if not plates or whole.area <= 0.0:
        return False
    plate = unary_union(plates).intersection(whole)
    if plate.area < 0.5 * whole.area:
        return False
    need = float(cfg.retaining_wall_min_length_m)
    return any(LineString(pts).intersection(plate).length >= need
               for pts in _surface_roads(airport, law))


def _surface_roads(airport, law) -> list:
    """The airport's mapped roads at grade (frame xy polylines): a
    ``highway`` way that is no admitted bore, not ``covered`` and on no
    negative ``layer``."""
    from .deck_signature import is_tunnel_way
    admitted = tuple(law.tables.structures.tunnel.admitted_values)
    out = []
    for w in getattr(airport, "osm_ways", None) or ():
        t = w.tags or {}
        if len(w.points) < 2 or not t.get("highway") or is_tunnel_way(t, admitted) \
                or str(t.get("covered", "no")).lower() not in ("", "no") \
                or _layer(t) < 0:
            continue
        out.append(tuple(tuple(p) for p in w.points))
    return out


def _layer(tags: _t.Mapping[str, str]) -> float:
    """A way's ``layer`` (0 when unset or unread)."""
    try:
        return float(str(tags.get("layer", "0")).split(";")[0])
    except ValueError:
        return 0.0
