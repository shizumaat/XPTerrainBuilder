"""THE AIRSIDE FLOOR OF A FRAME IS ITS ZERO (spec ``docs/specs/2120-F.md``
R1; owner RULINGS 2026-11-16x option (a), with 2026-10-22q and 2026-10-19ai).

Owner, KATL Terminal F (new pack): "modify the ground to match the pack
where need, option a" -- the concourse floor sits on the apron and the
hall's lower floor gets its own, lower pad.  The pack authors the frame's
zero at the LOWER floor (the hall, y 0) and the concourse a storey and more
above it (y 15): read at y 0 the concourse's feet are ``elevated`` and
footless (``contact.partition``), so nothing seats it on the apron.

THE WITNESS IS THE FRAME'S OWN FEET ON THE MAP.  Each ANCHOR FAMILY (one
anchor at 1 cm, one heading at 0.01 deg -- ``split_level._families``' key)
of plain ``OBJECT`` / unlifted ``OBJECT_AGL`` rows is read by the feet of
its WALLED genuine components (``[placement] chain_min_height_m`` tall),
through the partition's own foot band and sampling
(``contact.component_feet``).  The feet standing on the apt.dat airside
pavement or within ``airside_group_seat.TOUCH_M`` of it give the AIRSIDE
FLOOR ``y_a`` (``foot_planes.floor_plane`` of ``-y``, storey-aware); the
others the LOWER FLOOR ``y_l``.  The frame is RE-ZEROED at ``y_a`` when

* ``y_a >= [building_pad] low_level_min_step_m`` (a storey over its zero),
* ``y_l <= y_a - low_level_min_step_m`` (a lower floor a storey down),
* at least ``foot_planes.PLANE_MIN_FEET`` feet on each side, and
* NO airside foot stands under ``y_a - foot_planes.PLANE_BAND_M`` -- nothing
  of the frame on the airside is under its floor (the strict clause: KSFO
  Main_Building's 15 of 317 airside feet under a y 20.67 plane would sink
  it 20 m without it; spec §6 census).

Every member then reads ``zero_y = y_a`` and ``floor_zero``, both set at
``obj8._msl_frame`` (the one site, #1102): the partition places the frame
with its concourse on its zero, the hall a storey under it, and
``planar/low_level`` seeds the frame's lower pad from the flag (R3).

Never a family with a lifted, ``OBJECT_MSL``, hidden or terrain-read
member (a terrain feature, model, shell, fit or rider: the sets
``obj8.read_placed_objects`` builds before this reading), and never a
stock library object."""
from __future__ import annotations

import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.foot_planes import PLANE_BAND_M, PLANE_MIN_FEET, floor_plane

__all__ = ["FloorWitness", "FloorFrame", "airside_union", "witness", "floor_lifts",
           "family_key"]


class FloorWitness(_t.NamedTuple):
    """What the reading needs, read once from the airport and the law."""

    #: the apt.dat airside pavement buffered by ``TOUCH_M`` (frame metres)
    airside: _t.Any
    step_m: float
    wall_min_m: float
    band_m: float
    k_max: int
    storey_m: float


class FloorFrame(_t.NamedTuple):
    """One re-zeroed family: its members, floors and foot counts."""

    ids: tuple[str, ...]
    xy: tuple[float, float]
    y_a: float
    y_l: float
    feet_air: int
    feet_off: int

    def note(self) -> str:
        """One report line."""
        return (f"{self.ids[0]} +{len(self.ids) - 1} at ({self.xy[0]:.1f}, {self.xy[1]:.1f}): "
                f"y_a {self.y_a:+.2f} y_l {self.y_l:+.2f} feet {self.feet_air} airside / "
                f"{self.feet_off} off")


def airside_union(airport):
    """THE APT.DAT AIRSIDE PAVEMENT: every ``Airport.pavements`` polygon
    that is not a DSF page (a ``dsf:`` page carries no side here;
    ``classify/evidence`` splits them the same way); ``None`` without one."""
    polys = []
    for pv in getattr(airport, "pavements", ()) or ():
        if str(pv.id).startswith("dsf:") or len(pv.outer) < 3:
            continue
        g = Polygon(list(pv.outer), [list(h) for h in pv.holes if len(h) >= 3])
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty:
            polys.append(g)
    if not polys:
        return None
    u = unary_union(polys)
    return None if u.is_empty else u


def witness(airport, law) -> "FloorWitness | None":
    """The airport's airside floor witness, or ``None`` where it carries
    no apt.dat airside pavement (the rule is then inert)."""
    from .airside_group_seat import TOUCH_M, storey_m
    air = airside_union(airport)
    bp = law.tables.structures.building_pad
    step = float(getattr(bp, "low_level_min_step_m", 0.0) or 0.0)
    if air is None or step <= 0.0:
        return None
    g = air.buffer(TOUCH_M)
    shapely.prepare(g)
    return FloorWitness(g, step, float(law.tables.structures.placement.chain_min_height_m),
                        float(law.tables.structures.basin.contact_band_m),
                        int(law.tables.structures.rebake.foot_samples_max), storey_m(law))


def family_key(xy: _t.Sequence[float], heading_deg: float) -> tuple[float, float, float]:
    """One anchor at 1 cm, one heading at 0.01 deg (``split_level._families``)."""
    return (round(float(xy[0]), 2), round(float(xy[1]), 2),
            round(float(heading_deg) % 360.0, 2))


def floor_lifts(placements: _t.Sequence[tuple], path_of: _t.Callable[[str], "str | None"],
                cache, wit: "FloorWitness | None", skip: _t.AbstractSet[str] = frozenset(),
                hidden: _t.AbstractSet[str] = frozenset()
                ) -> tuple[dict[str, float], list[FloorFrame]]:
    """``({id: -y_a}, frames)``: the lift (``obj8._msl_lifts``' sign) of
    every member of every re-zeroed family (module docstring).
    ``placements`` as ``obj8.read_placed_objects`` takes them; ``skip``:
    the placement ids read as terrain; ``hidden``: the def paths hidden."""
    if wit is None:
        return {}, []
    from .obj8 import is_stock_library_resource
    fams: dict[tuple, list] = {}
    bad: set[tuple] = set()
    for oid, dpath, xy, heading, elev, kind in placements:
        if is_stock_library_resource(dpath):
            continue
        k = family_key(xy, heading)
        lifted = kind == "OBJECT_AGL" and elev is not None and float(elev) != 0.0
        if kind not in ("OBJECT", "OBJECT_AGL") or lifted or oid in skip or dpath in hidden:
            bad.add(k)
            continue
        fams.setdefault(k, []).append((oid, dpath, xy, heading))
    lifts: dict[str, float] = {}
    frames: list[FloorFrame] = []
    for k in sorted(fams):
        if k in bad:
            continue
        got = _family_floor(fams[k], path_of, cache, wit)
        if got is not None:
            frames.append(got)
            lifts.update((i, -got.y_a) for i in got.ids)
    return lifts, frames


def _family_floor(mem: list, path_of, cache, wit: FloorWitness) -> "FloorFrame | None":
    """One family's :class:`FloorFrame`, or ``None`` where it is no
    two-floor frame standing a storey up on the airside."""
    from .contact import component_feet
    from .obj8 import placement_affine
    xy, heading = mem[0][2], mem[0][3]
    geoms = []
    reach = 0.0
    for _oid, dpath, _xy, _h in mem:
        phys = path_of(dpath)
        g = cache.geometry(phys) if phys is not None else None
        if g is not None and g.vertices.shape[0]:
            reach = max(reach, float(np.hypot(g.vertices[:, 0], g.vertices[:, 2]).max()))
            geoms.append((phys, g))
    x, y = float(xy[0]), float(xy[1])
    bx0, by0, bx1, by1 = wit.airside.bounds
    if not geoms or x + reach < bx0 or x - reach > bx1 or y + reach < by0 or y - reach > by1:
        return None
    walled = [(g, c) for phys, g in geoms for c in cache.genuine(phys)
              if c.max_y - c.min_y >= wit.wall_min_m]
    # a foot stands within the band of its component's floor: no walled
    # component that high, no airside floor a storey up
    if not walled or max(c.min_y for _g, c in walled) + wit.band_m < wit.step_m - PLANE_BAND_M:
        return None
    feet = np.concatenate([component_feet(g, c, wit.band_m, wit.k_max) for g, c in walled])
    a = placement_affine(xy, heading)
    fx = a[0] * feet[:, 0] + a[1] * feet[:, 1] + a[4]
    fy = a[2] * feet[:, 0] + a[3] * feet[:, 1] + a[5]
    on = shapely.contains_xy(wit.airside, fx, fy)
    n_on, n_off = int(on.sum()), int((~on).sum())
    if n_on < PLANE_MIN_FEET or n_off < PLANE_MIN_FEET:
        return None
    fa = floor_plane([-float(v) for v in feet[on, 2]], wit.storey_m)
    if fa is None or math.isnan(fa) or -fa < wit.step_m:
        return None
    y_a = -float(fa)
    if float(feet[on, 2].min()) < y_a - PLANE_BAND_M:
        return None                          # something of it is under the floor
    fl = floor_plane([-float(v) for v in feet[~on, 2]], wit.storey_m)
    if fl is None or -float(fl) > y_a - wit.step_m:
        return None
    return FloorFrame(tuple(sorted(str(m[0]) for m in mem)), (x, y), round(y_a, 3),
                      round(-float(fl), 3), n_on, n_off)
