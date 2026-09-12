"""THE APRON EDGE RAMPS TO THE GROUNDSIDE — a law generator (RULINGS
2026-09-08d (4b), spec ``heca-v1-parity-spec.md`` §4 / §6.3 (b); the cap is
``emit.toml [terrace] groundside_ramp_max``).

Split out of the deleted ``constraints/yielding.py`` unchanged (RULINGS
2026-09-08t: the yielding machinery goes, the LAW GENERATOR stays); under
the design surface its rows are one-sided quadratic penalties like every
other law row.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import groundside_ramp_max
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap

__all__ = ["RAMP_FAMILY", "groundside_face_roles", "groundside_ramps"]

#: The generator name its rows carry.
RAMP_FAMILY = "groundside_ramp"


def groundside_face_roles(law: Law) -> tuple[str, ...]:
    """THE GROUNDSIDE PAVEMENT ROLES — ONE derivation site (owner ruling
    ``7e90032``), read by this generator and by the §28 frontage rule
    (``constraints/pads.groundside_frontage``, owner RULINGS 2026-09-11ai-1
    -> 2026-09-12r "grade frontages only").

    Every role the register sides GROUNDSIDE that carries a VALUE and is
    not a STRUCTURE: ``groundside_pavement``, ``service_road``,
    ``service_junction``, ``parking_lot`` — exactly the four §28 (1)
    names, as DATA rather than a literal list.  A structure's role (a
    tunnel ramp, a door ramp, a garage ramp, a retaining wall) is no lot
    and no frontage: its rim stands at the ground by station and its
    descent rows are its own law (``constraints/structures.py``)."""
    from ..law.tables import is_structure_role, is_value_role, role_side
    return tuple(r for r in law.tables.precedence.roles
                 if role_side(law, r) == "groundside" and is_value_role(law, r)
                 and not is_structure_role(law, r))


def groundside_ramps(pm: PlanarMap, law: Law, airport=None) -> list[Row]:
    """THE APRON EDGE RAMPS TO THE GROUNDSIDE (RULINGS 2026-09-08d (4b); spec
    heca-v1-parity §4 / §6.3 (b)): for every apron ring vertex, the nearest
    GROUNDSIDE pavement ring vertex (a value role of the groundside side)
    across the stand-off — within ``zones.adjacent_ground.groundside_cutback_m
    + identity.weld_spacing_m`` plus the snap margin, and not a shared
    vertex — takes one ``Diff`` at ``terrace.groundside_ramp_max`` (5 %, v1
    ``GROUNDSIDE_MAX_GRADE``) : a step
    across the stand-off is charged as a one-sided design penalty like any
    other law row (RULINGS 2026-09-08t) and a ramp is free — the groundside
    lifts or cuts to meet the apron edge and grades away at its own cap.
    A generator (``constraints.GENERATORS``)."""
    from ..law.tables import snap_margin_m
    from .precedence import view
    vw = view(pm, law)
    ramp_max = groundside_ramp_max(law)
    # the groundside PAVEMENT only: a structure's role (a tunnel ramp, a door
    # ramp, a retaining wall — groundside value roles too) is no lot the
    # apron ramps to; its rim stands at the ground by station and its
    # descent rows are its own law (``constraints/structures.py``).  Measured
    # 2026-09-08 (lane v2shapes): six rows apron <-> tunnel_ramp rim at
    # 1.0-1.4 m lifted a ramp 8 mm over its descent law and pulled the apron
    # 0.46 m under the DEM at a door well
    ground = groundside_face_roles(law)
    gv: dict[int, tuple[float, float]] = {}
    for f in vw.faces_of_role(ground):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                gv[v] = vw.xy[v]
    if not gv:
        return []
    ids = sorted(gv)
    from scipy.spatial import cKDTree
    tree = cKDTree([gv[v] for v in ids])
    horizon = (law.tables.zones.adjacent_ground.groundside_cutback_m
               + law.tables.emit.identity.weld_spacing_m + snap_margin_m(law))
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for f in vw.faces_of_role(("apron",)):
        src = Source(RAMP_FAMILY, "2026-09-08d (4b): the apron edge ramps to the groundside "
                     "at terrace.groundside_ramp_max", (f"face:{f.id}", f.ref))
        k = 0
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                if v in gv:
                    continue                        # a shared vertex: no stand-off here
                d, j = tree.query(vw.xy[v])
                if d > horizon or d < min_d:
                    continue
                g = ids[int(j)]
                key = (min(v, g), max(v, g))
                if key in seen:
                    continue
                seen.add(key)
                k += 1
                rows.append(Diff(v, g, ramp_max, float(d), src))
    return rows
