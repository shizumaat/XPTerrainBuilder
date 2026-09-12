"""THE PAD'S RELIEF TARGET — one derivation (owner RULINGS 2026-09-11j;
spec ``object-placement-spec.md`` §11a (2)).

X-Plane drapes a whole OBJ8 body at ONE anchor.  A body whose
ground-contact feet are authored at different ``y`` therefore cannot
stand on a flat pad: whatever the terrain does between two feet, the
object does not follow it, and the difference is the gap the eye reads.
The fix is not a different grouping — LEMD38's canopy modules are nine
column feet authored 2.63 m apart inside ONE placement, no abutment
anywhere — it is a per-foot TARGET on the pad:

    surface(foot) = level + (y_foot - y_zero)

``level`` stays the pad law's own (10l apron-edge, pads by proximity,
10ag skirt): a pad with a relief target is still ONE pad entity with ONE
level, and every consumer that reads its polygon, contacts, rim or level
is unchanged (§11a (4)).  Only the rows that price the pad's SURFACE read
the offsets, and they price flatness on the LEVEL plane — the offset
subtracted from each foot — so a flat-footed body asks for exactly
today's flat pad and the machinery below is the identity for it.

**PAVEMENT IS SENIOR** (§11a (2), 09af-1: "the object goes to the terrain
there").  A foot standing on apron or taxiway takes NO relief row: the
pavement law owns that surface, the body then anchors at its low-side
foot as §9 already says, and the residual is reported rather than graded
away.

**AND SENIORITY IS BY VERTEX, NOT ONLY BY FOOT** (owner RULINGS
2026-09-12u, spec §30 (2)).  Until 12u the test was applied to the FOOT
alone, so a foot standing on the pad a metre inside its rim still handed
its authored ``y`` to the rim vertices within ``relief_radius_m`` (12 m)
— and those rim vertices are the APRON's own (identity is the weld,
09-01g).  At LEMD T4S that gave apron vertices a −2.20 m target: the
pavement law owns them and no relief may be authored onto them.  A pad
vertex SHARED with airside pavement therefore takes offset 0 and keeps
the pad's level, whatever foot is nearest.  The population is
the pavement faces this module already reads
(``pads._pavement_geoms``, the ONE derivation of "a pavement face"),
narrowed to the AIRSIDE side by ``law.tables.role_side`` — the same
population ``no_step.pad_contacts`` calls a pad's contacts.  A GROUNDSIDE
face's shared vertex is NOT senior here: 09-01g leaves it the lot's, and
§28 is where a groundside frontage is stated.

**NEAREST FOOT, NEVER INTERPOLATED.**  A pad vertex takes the target of
the nearest foot within ``[placement] relief_radius_m`` and otherwise
keeps the level.  Two feet 40 m apart say nothing about the ground
between them; interpolating would invent a slope the object never
authored.

Reads the planar map, the law and ``Airport.groups`` (``planar/group.py``,
the ONE grouping derivation).  No mesh, no environment.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import role_side
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["relief_radius_m", "pad_relief_offsets"]


def relief_radius_m(law: Law) -> float:
    """``[placement] relief_radius_m`` — ONE derivation site.  0 disarms
    the relief target (every pad targets flat, the pre-11j law)."""
    return float(law.tables.structures.placement.relief_radius_m)


def pad_relief_offsets(planar: PlanarMap, law: Law, airport: Airport
                       ) -> dict[int, float]:
    """``vertex -> the metres the terrain there stands above the pad's
    LEVEL`` (module doc).  Empty where the law is disarmed, where no pack
    was read, or where no group's feet fall on a pad.

    Only vertices of RIGID (pad) faces are ever returned: the relief
    target is the pad law's, and nothing outside a pad carries it.
    """
    radius = relief_radius_m(law)
    groups = getattr(airport, "groups", None)
    if radius <= 0.0 or groups is None or not getattr(groups, "groups", ()):
        return {}
    from .pads import _pad_polys, _pavement_geoms      # one derivation of both
    pads = _pad_polys(planar, law)
    if not pads:
        return {}
    to_xy, _to_ll = airport.frame.transformers()
    # PAVEMENT IS SENIOR: a foot standing on pavement founds no target,
    # AND (12u, §30 (2)) a pad vertex the AIRSIDE pavement shares takes
    # none either — one read of the one derivation, `_pavement_geoms`.
    geoms = _pavement_geoms(planar, law)
    pav = [poly for _role, _vs, poly in geoms]
    pav_tree = STRtree(pav) if pav else None
    senior: set[int] = set()
    for role, vs, _poly in geoms:
        if role_side(law, role) == "airside":
            senior |= vs

    #: every group's feet in the frame, with the metres above its own zero
    feet: list[tuple[float, float, float]] = []
    for g in groups.groups:
        if not g.feet:
            continue
        if g.infeasible:
            # §11 (4): an INFEASIBLE group's pad is NOT adapted.  The
            # terrain cannot carry its authored relief and stay lawful,
            # so the body anchors at its low-side foot (§9) and the
            # residual is REPORTED — measured at LEMD, without this gate
            # the published targets reached +35.53 / -14.51 m, which is
            # not a relief profile but a body whose "feet" are vertices
            # up its own structure.  The group keeps today's flat pad.
            continue
        for f in g.feet:
            x, y = to_xy(f.lon, f.lat)
            feet.append((x, y, float(f.y) - float(g.y_zero)))
    if not feet:
        return {}
    pts = [Point(x, y) for x, y, _o in feet]
    if pav_tree is not None:
        on_pavement = set()
        for i, p in enumerate(pts):
            for j in pav_tree.query(p):
                if pav[int(j)].covers(p):
                    on_pavement.add(i)
                    break
        keep = [i for i in range(len(feet)) if i not in on_pavement]
    else:
        keep = list(range(len(feet)))
    if not keep:
        return {}
    foot_pts = [pts[i] for i in keep]
    foot_off = [feet[i][2] for i in keep]
    tree = STRtree(foot_pts)

    vw_xy = {v: vx.xy for v, vx in planar.vertices.items()}
    out: dict[int, float] = {}
    r2 = radius * radius
    for _fid, _ref, group, poly in pads:
        for v in group:
            if v in out or v in senior:
                continue
            x, y = vw_xy[v]
            pt = Point(x, y)
            best = None
            best_d2 = r2
            for j in tree.query(pt.buffer(radius)):
                fx, fy = foot_pts[int(j)].x, foot_pts[int(j)].y
                d2 = (fx - x) ** 2 + (fy - y) ** 2
                if d2 <= best_d2:
                    best_d2 = d2
                    best = int(j)
            if best is not None and abs(foot_off[best]) > 0.0:
                out[v] = float(foot_off[best])
    return out


def offsets_report(offsets: _t.Mapping[int, float]) -> dict[str, float]:
    """The one line a build prints: how many pad vertices carry a relief
    target and how far it reaches."""
    if not offsets:
        return {"vertices": 0, "max_m": 0.0, "spread_m": 0.0}
    vals = list(offsets.values())
    return {"vertices": len(vals), "max_m": round(max(abs(v) for v in vals), 3),
            "spread_m": round(max(vals) - min(vals), 3)}
