"""THE UNITS' TWO FLOORS, READ ONCE ON THE MAP (RULINGS 2026-11-25g, 25h;
spec ``docs/specs/terminal-frontage-split-level-20261125.md`` §2, step 2).

``airport/unit_storey.unit_levels`` read once the pads stand
(``planar/platform.platform_split``), against the map's airside regions
and its groundside pavement: the one record every consumer reads --
``planar/low_level.plan_low`` (C7, a held record a storey down is its
block's witness) and the frontage law (C12, ``planar/kerb_frontage``,
``constraints/kerb_frontage``), which finds it on its block's ``held``
entry under :data:`model.registries.UNIT_LEVELS` (:func:`publish_levels`).

THE MINTED LEVEL WINS (step-1 finding (b), C8's twin: a reader never
contradicts a held record of the same unit).  Where a level of the
record's sign was minted on the block (``Registries.landings``
``<block>/p<k>``: a lower level, an upper level or a storey shell's), the
record's groundside floor is that level -- the reader that minted it read
the walled feet (``geom/foot_planes``), a rung above the storey parts.
MEASURED KATL ``building32``: storey parts -18.8 (the ground's best),
the frame's lower floor -15.00 minted as ``building32/p2``."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.ops import unary_union

from ..model.registries import UNIT_LEVELS

__all__ = ["publish_levels", "read_levels"]


def read_levels(base_regions, air_polys, airport, law, shells=()) -> list:
    """``unit_levels`` over the airside polygons ``air_polys`` and the
    groundside pavement regions of ``base_regions``; ``[]`` without a
    partition."""
    if airport is None or getattr(airport, "partition", None) is None or not air_polys:
        return []
    from ..airport.unit_storey import unit_levels
    from ..law.tables import is_structure_role, is_value_role, role_side
    # the groundside pavement (``constraints/groundside.groundside_face_roles``'
    # reading: a groundside value role that is no structure)
    ground = unary_union([r.polygon for r in base_regions if r.polygon is not None
                          and not r.polygon.is_empty
                          and role_side(law, r.role) == "groundside"
                          and is_value_role(law, r.role)
                          and not is_structure_role(law, r.role)])
    return unit_levels(airport, law, unary_union(list(air_polys)), ground=ground,
                       shells=tuple(shells))


def _minted(reg, block: str, rise: float) -> "float | None":
    """The level of ``rise``'s sign minted on ``block`` nearest ``rise``."""
    ys = [float(v["y"]) for k, v in (reg.landings or {}).items()
          if str(v.get("block")) == block and v.get("deck") is None and "/p" in str(k)
          and v.get("y") is not None and float(v["y"]) * rise > 0.0]
    return min(ys, key=lambda y: abs(y - rise)) if ys else None


def publish_levels(levels: _t.Sequence, regions: _t.Sequence, reg, airport,
                   counts: dict) -> int:
    """Put each record of ``levels`` on the held block its plan covers most
    (a quarter of the smaller plan or more, its unit's block by
    ``planar/low_level.unit_share``), reconciled to the level minted there
    (module docstring); returns the records placed."""
    if not levels:
        return 0
    from .low_level import unit_share
    blocks: dict[str, list] = {}
    for r in regions:
        if r.polygon is not None and str(r.ref) in reg.held:
            blocks.setdefault(str(r.ref), []).append(r.polygon)
    union = {k: unary_union(v) for k, v in blocks.items()}
    to_xy = airport.frame.entry()
    n, notes = 0, []
    for rec in levels:
        cand = []
        for k, B in union.items():
            a = B.intersection(rec.plan).area if B.intersects(rec.plan) else 0.0
            if a >= 0.25 * min(B.area, rec.plan.area) and unit_share(B, airport, to_xy)[0] \
                    == rec.unit:
                cand.append((-a, k))
        if not cand:
            continue
        block = min(cand)[1]
        if rec.land_y is not None and (y := _minted(reg, block, rec.rise)) is not None \
                and abs(y - rec.rise) > 0.005:
            notes.append(f"{block}: {rec.rise:+.2f} -> minted {y:+.2f}")
            rec = _dc.replace(rec, land_y=round(float(rec.air_y) + y, 3), witness="minted")
        reg.held[block] = {**reg.held[block], UNIT_LEVELS: rec}
        n += 1
    counts["unit_levels_blocks"] = n
    if notes:
        counts["unit_levels_minted"] = "; ".join(notes)
    return n
