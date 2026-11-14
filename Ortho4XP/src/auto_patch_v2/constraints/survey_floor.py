"""THE FLOOR OF A SURVEYED UNDERPASS MOUTH (class K; #1939 round 2 R2 / R3,
spec ``docs/specs/1939-round2-spec.md``; RULINGS 2026-11-13h N1).

A class-K mouth (``planar/underpass_mouth``) digs nothing: its floor IS the
survey's road, its cap the survey's cover over the bore.  So its ramp is not
planned as a climb (no ``Flat`` per station, no descent ``Diff``, no
monotone row, no top pin, no mouth-depth tie -- the rows
``constraints/structures`` builds for a ramp the generator designs): every
ramp vertex is PINNED --

* on the sheared mouth edge (within one identity step of corner ``a`` to
  corner ``b``, ``Tunnel.survey_floor``): at the surveyed floor ``z0 + k .
  tau``, ``tau`` its metres from the axis toward ``b`` (senior);
* bare (the ramp's far edge, its side edges): at the DEM there (senior);
* shared, and the ground CARRIES a value there (amendment A1,
  ``docs/specs/1939-round2-A1.md``): no row -- a sharing face is airside
  (runway, taxi, apron, pad: stage 1 owns it; a DEM pin there is the LEMD
  infeasibility the ground rule was written for), or the vertex has a
  published target (``road_ramp_z``, ``preferred_z``, ``taxi_trend_z``);
* shared only with groundside faces that publish no target there (A1 (c)):
  at the DEM there (senior) -- no vertex of a K ramp is left to the
  objective.

The cap (R3) stands at the cover: a bare rim vertex within one identity step
of the cap line is pinned at ``Tunnel.mouth_dem_z`` (the survey's cover, N1:
"its cap the survey's cover over the bore"), never the DEM the resampled
survey smears down the face; one the ground shares keeps the ground's
value."""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point

from ..model.constraints import Source

__all__ = ["SURVEY_FLOOR_RULING", "survey_floor_pins", "cap_line"]

#: The ruling head (``[design] hard_rulings``, beside ``tunnel.mouth_depth_m``).
SURVEY_FLOOR_RULING = "tunnel.survey_floor"


def _ground_carries(planar, vw, v: int) -> bool:
    """A1 (b): does the ground carry a value at shared vertex ``v`` -- a
    governed AIRSIDE face touches it (``vw.side``; stage 1 owns it), or the
    map publishes a target there?  ``vw`` is the precedence view
    (``constraints.precedence.view``)."""
    for fid in vw.vertex_faces.get(v, ()):
        if vw.caps.get(fid) is not None and vw.side(planar.faces[fid].role) == "airside":
            return True
    return any(v in (getattr(planar, ch, None) or {})
               for ch in ("road_ramp_z", "preferred_z", "taxi_trend_z"))


def survey_floor_pins(planar, airport, tn, ramp_faces, shared_with_ground: _t.Callable[[int], bool],
                      pin: _t.Callable[..., None], inputs: tuple, grid: float, gen: str,
                      vw) -> int:
    """Pin every ramp vertex of ``tn`` (module doc); returns the count."""
    z0, k, a, b = tn.survey_floor
    edge = LineString([a, b])
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    m0 = tn.axis[0]
    src_floor = Source(gen, f"{SURVEY_FLOOR_RULING} (#1939 R2; RULINGS 2026-11-13h N1): the "
                       "floor along the mouth edge is the surveyed road", inputs)
    src_dem = Source(gen, f"{SURVEY_FLOOR_RULING} (#1939 R2): a bare ramp vertex beyond the "
                     "mouth edge stands on the survey", inputs)
    src_top = Source(gen, f"{SURVEY_FLOOR_RULING} (#1939 R2 A1 (c)): a ramp top only groundside "
                     "faces with no target share stands on the survey", inputs)
    n = 0
    for v in sorted({v for f in ramp_faces for v in planar.ring_vertices(f.ring)}):
        xy = planar.vertices[v].xy
        if edge.distance(Point(xy)) <= grid + 1e-9:
            tau = (xy[0] - m0[0]) * d[0] + (xy[1] - m0[1]) * d[1]
            pin(v, z0 + k * tau, src_floor, senior=True)
        else:
            shared = shared_with_ground(v)
            if shared and _ground_carries(planar, vw, v):
                continue
            z = float(airport.dem.z(xy[0], xy[1]))
            if math.isnan(z):
                continue
            pin(v, z, src_top if shared else src_dem, senior=True)
        n += 1
    return n


def cap_line(tn) -> tuple[LineString, float] | None:
    """R3: ``(the cap line, the cover)`` of a class-K tunnel, else ``None``."""
    if getattr(tn, "survey_floor", None) is None or tn.cap_corners is None:
        return None
    pts = [tn.cap_corners[0]] + ([tn.cap_centre] if tn.cap_centre is not None else []) \
        + [tn.cap_corners[1]]
    return LineString(pts), float(tn.mouth_dem_z)
