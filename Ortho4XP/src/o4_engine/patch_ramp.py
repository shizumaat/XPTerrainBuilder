""""Insert tunnel ramp" on the map (issue #1745, protocol 1.24): one
straight ramp shape centred at the right-click, sized from the tunnel law
so it descends the mouth depth at the ramp grade cap, for the user to
place and edit by hand.

Every number is read from the law tables (``structures.toml [tunnel]``,
through ``law.model.Tunnel``), never restated here:

* depth  = ``Tunnel.mouth_depth_m`` (7.5 m: clearance + equipment + roof
  + cover, owner RULINGS 2026-10-14f);
* grade  = ``tunnel.ramp_max_grade`` (the ramp cap, 10 %, RULINGS
  2026-10-07b (2)), so the length is depth / grade (75 m);
* width  = ``tunnel.lane_width_m`` × ``tunnel.default_lanes`` (the
  carriageway of a mapped way with no ``lanes`` / ``width``, 7 m).

The shape is north-up: the south end is the top, its two corners at the
ground under them; the north end is the floor, each corner the mouth
depth under the top corner on its side, so each side descends exactly
the depth at the cap.  Its tags are the ones the emitter writes on a
``tunnel_ramp`` face (``aeroway`` from the precedence register, ``ref`` and
``role`` the role), so the build, the census and both editors read it as
a tunnel ramp.  No solver or geometry law changes: the patch carries the
shape at the elevations its nodes hold, as any hand-edited shape.
"""
from __future__ import annotations

import typing as _t

__all__ = ["RAMP_ROLE", "rect_ring", "ramp_dimensions", "ramp_tags", "ramp_ring",
           "ramp_corners"]

#: The role the inserted shape carries (``precedence.toml``).
RAMP_ROLE = "tunnel_ramp"


def rect_ring(lat: float, lon: float, width_m: float, length_m: float
              ) -> list[tuple[float, float]]:
    """The four corners ``(lat, lon)`` of a north-up rectangle
    ``width_m`` east-west by ``length_m`` north-south centred at ``(lat,
    lon)``, counter-clockwise from the south-west corner, not closed."""
    from auto_patch_v2.model.frame import m_per_deg_exact
    m_lat, m_lon = m_per_deg_exact(lat)
    h_lat, h_lon = length_m / 2 / m_lat, width_m / 2 / m_lon
    return [(lat - h_lat, lon - h_lon), (lat - h_lat, lon + h_lon),
            (lat + h_lat, lon + h_lon), (lat + h_lat, lon - h_lon)]


def _tunnel():
    from auto_patch_v2.law.tables import load_default
    return load_default().tables.structures.tunnel


def ramp_dimensions() -> dict[str, float]:
    """``{"depth_m", "grade", "length_m", "width_m"}`` from the law."""
    t = _tunnel()
    depth, grade = float(t.mouth_depth_m), float(t.ramp_max_grade)
    return {"depth_m": depth, "grade": grade, "length_m": depth / grade,
            "width_m": float(t.lane_width_m) * int(t.default_lanes)}


def ramp_tags() -> dict[str, str]:
    """The tags the emitter writes on a ``tunnel_ramp`` face."""
    from auto_patch_v2.law.tables import load_default
    spec = load_default().tables.precedence.roles[RAMP_ROLE]
    return {"aeroway": spec.aeroway, "ref": RAMP_ROLE, "role": RAMP_ROLE}


def ramp_ring(lat: float, lon: float) -> list[tuple[float, float]]:
    """The ramp's four corners ``(lat, lon)`` centred at ``(lat, lon)``
    (:func:`rect_ring`): the top end's two first, then the floor's."""
    dims = ramp_dimensions()
    return rect_ring(lat, lon, dims["width_m"], dims["length_m"])


def ramp_corners(ring: _t.Sequence[tuple[float, float]], top_w: float, top_e: float
                 ) -> list[list[float]]:
    """``[lat, lon, alt]`` of :func:`ramp_ring`'s corners (module doc):
    the top corners at the ground ``top_w`` / ``top_e`` under them, each
    floor corner the mouth depth under the top corner on its side."""
    sw, se, ne, nw = ring
    d = ramp_dimensions()["depth_m"]
    return [[*sw, top_w], [*se, top_e], [*ne, top_e - d], [*nw, top_w - d]]
