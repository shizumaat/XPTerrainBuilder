"""THE KERB'S WALL, DECLARED (#2279 step 2; spec
``docs/specs/2279-kerb-frontage-spec.md`` §2 K3).

A unit's landside meets the building at its kerb a storey over the floor
(``constraints/kerb_frontage``); between them stands the building's wall
(RULINGS 2026-11-25b (5): pavements touching, the step is a wall), and the
solve's rows across it are withdrawn.  This module declares that wall on
the sidecar's ``terrace_joints`` channel (``publication.terrace_joints_ll``,
the ``upper_rim_joints`` form): one ``wall_terrace`` joint per run of the
WALL LINE that a kerb vertex stands within the frontage radius of — the
boundary of the plan (grown by the groundside cut-back) and of the pad and
airside faces the kerb meets — its step the largest the solve put across
it (each kerb vertex against its nearest wall vertex) plus the emit's
rounding.  Nothing else on that boundary is declared."""
from __future__ import annotations

import typing as _t

#: the patch writes elevations to the centimetre (``publication._EMIT_Z_ROUND_M``)
_ROUND_M = 0.01

__all__ = ["kerb_wall_joints"]


def kerb_wall_joints(planar, law, z: "_t.Sequence[float] | None") -> list[dict[str, _t.Any]]:
    """The wall joints (module docstring); ``[]`` before a solve."""
    from ..constraints.kerb_frontage import kerb_vertices, wall_line
    if z is None:
        return []
    kerb, wall = kerb_vertices(planar, law)
    if not kerb or not wall:
        return []
    import numpy as np
    from scipy.spatial import cKDTree
    from shapely.geometry import LineString

    from .ribbon_steps import _to_ll
    ws = sorted(wall)
    tree = cKDTree(np.array([planar.vertices[w].xy for w in ws]))
    steps = {}
    for v in kerb:
        _d, j = tree.query(planar.vertices[v].xy)
        steps[v] = abs(float(z[v]) - float(z[ws[int(j)]]))
    line = wall_line(planar, law)
    if line is None or line.is_empty:
        return []
    to_ll = _to_ll(planar)
    from ..law.tables import design as design_law
    reach = float(design_law(law).pad_frontage_m) + float(
        law.tables.zones.adjacent_ground.groundside_cutback_m)
    kv = sorted(steps)
    ktree = cKDTree(np.array([planar.vertices[v].xy for v in kv]))
    out = []
    for part in getattr(line, "geoms", [line]):
        if not isinstance(part, LineString) or part.length <= 0.0:
            continue
        # the part's step: the largest over the kerb vertices it fronts
        near = {int(j) for xy in part.coords for j in ktree.query_ball_point(xy, reach)}
        if not near:
            continue
        h = max(steps[kv[j]] for j in near)
        pts = [list(to_ll(x, y)) for x, y in part.coords]
        out.append({"points": pts, "step_m": round(h + _ROUND_M, 4),
                    "declared_step_m": round(h + _ROUND_M, 4), "faced": False,
                    "kind": "wall_terrace", "faces": [], "shapes": ["landside_kerb"],
                    "gap": False, "roles": [], "pairs": len(near),
                    "length_m": round(part.length, 2), "height_m": round(h, 3), "lots": 0})
    return out
