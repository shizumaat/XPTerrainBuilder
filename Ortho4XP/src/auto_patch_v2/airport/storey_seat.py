"""ONE FRAME SEAT FOR A STOREY SHELL (#2062, owner RULINGS 2026-11-13w;
spec ``2062-storey-shell-spec`` §1 "Frame", §3 R2).

A split-level building laid on its storey pad (``planar/storey_pad``) is a
terrain-shaped object: its RIGID SET -- every row of its own frame (the
placements sharing its anchor) and every row of ANOTHER frame whose plan
lies at least half inside the shell's plan widened by
``open_frame_seat.TOUCH_M`` (a canopy, the people on its upper floor) -- is
written WHOLE at the building's zero plus each row's own lift:
``elevation = z0 + lift``, ``z0 = D_block - levels[block]``, ``D_block``
the solved datum of the block pad (the median of its vertices on the
solved surface).  One record per row, seat :data:`SEAT`
(``terrain_shaped.row_seats`` writes it as ``OBJECT_MSL``); the rows go
into the rebake's ``exclude`` so no other seat moves them.  A frame
failing the test keeps today's path (22o).

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import statistics as _st
import typing as _t

from shapely.ops import unary_union

from .terrain_shaped import STOREY_SEAT as SEAT

__all__ = ["SEAT", "block_zero", "rigid_rows", "seat_records"]


def rigid_rows(shell: _t.Any, objects: _t.Sequence[_t.Any], touch_m: float) -> list:
    """The placements of ``shell``'s RIGID SET (module docstring), sorted by
    id."""
    from shapely.geometry import Polygon
    from .split_level import _families
    plan = Polygon(shell.plan).buffer(float(touch_m))
    own = set(str(m) for m in shell.member_ids)
    out = []
    for fam in _families(objects):
        if own.intersection(str(o.id) for o in fam):
            out.extend(fam)
            continue
        boxes = [o.plan_bbox for o in fam if getattr(o, "plan_bbox", None) is not None]
        g = unary_union(boxes) if boxes else None
        if g is not None and g.area > 0.0 and g.intersection(plan).area >= 0.5 * g.area:
            out.extend(fam)
    return sorted(out, key=lambda o: str(o.id))


def block_zero(shell: _t.Any, pm: _t.Any, z_at: _t.Callable) -> "float | None":
    """``z0``: the block pad's solved datum (the median of its vertices'
    solved levels) less the block's level."""
    xy = sorted({pm.vertices[v].xy for f in pm.faces.values() if f.ref == shell.pad_ref
                 for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)})
    zs = [z for z in (z_at(x, y) for x, y in xy) if z is not None]
    if not zs:
        return None
    return float(_st.median(zs)) - float(shell.levels[shell.block])


def seat_records(shells: _t.Sequence[_t.Any], pm: _t.Any, z_at: _t.Callable,
                 objects: _t.Sequence[_t.Any], touch_m: float) -> list[dict[str, _t.Any]]:
    """One ``RebakePlan.authored_seats`` record per row of every shell's
    rigid set (module docstring); ``z_at(x, y)`` the solved surface's level
    at a map vertex."""
    out: list[dict[str, _t.Any]] = []
    seen: set[str] = set()
    for sh in shells:
        z0 = block_zero(sh, pm, z_at)
        if z0 is None:
            continue
        for o in rigid_rows(sh, objects, touch_m):
            if str(o.id) in seen:
                continue
            seen.add(str(o.id))
            out.append({"id": str(o.id), "resource": str(o.path), "datum": "terrain",
                        "seat": SEAT, "shell": str(sh.id), "zero": round(z0, 3),
                        "elevation": round(z0 + float(getattr(o, "agl_m", 0.0) or 0.0), 3)})
    return out
