"""THE AIRSIDE STEP ACROSS A DECLARED PACK WALL IS AT MOST THE WALL (owner
RULINGS 2026-10-28s (2), Q250 a, issue #507; amends 19ao, which bounded it
in the census only).

The pairs are the map's (``PlanarMap.road_terrace['wall_air']``, derived
once by ``airport/wall_air``): stage-1 pavement vertices within the pair
window of each other across a wall piece.  Which end is the lower one is a
solved answer, so the floor is stated AFTER stage 1 has solved: every pair
whose solved difference exceeds the wall's height (plus ``[design]
hard_tol_m``) floors its LOWER end at ``z_upper - h`` — ONE hard ``Band``
per lower vertex (its highest floor), head :data:`WALL_FLOOR_RULING`,
ranked in the LAST tier of ``[design] hard_conflict_ranks`` after the
runway's first hold, so the runway's bend and the taxi and apron caps win a
conflict; a floor §5a relaxes is a named residual (``unmet``).  The pass is
ONE re-solve, never a loop; no pair over the wall, no rows and no re-solve
(every other airport byte-identical).

Not the ``constraints/road_ramp._wall_step_rows`` row: that one is one-way
(the lower vertex follows), which stage 1 refuses (``design_roles.
conforming_rulings``), and it pairs a lot or road with the airside — the
two aprons of comp 12 share no row.  MEASURED (PR #1614): a hard TWO-SIDED
row dropped the upper apron 1.8 m; a one-way lag floor reached 4.05 m
unsettled.  A Band against the solved upper level moves only the lower
side."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..law.tables import design as design_law
from ..model.constraints import Band, ConstraintSet, Source
from ..model.planar import PlanarMap

__all__ = ["WALL_FLOOR_RULING", "wall_floor_rows", "wall_floor_pass"]

#: The ruling HEAD of the floor rows (``[design] hard_rulings`` and the last
#: tier of ``hard_conflict_ranks``).
WALL_FLOOR_RULING = "structures.wall_terrace airside step"
GEN = "wall_floor"


def _floors(planar: PlanarMap, law: Law, z: _t.Sequence[float]
            ) -> dict[int, tuple[float, str]]:
    """Lower vertex -> (its highest floor, the wall's label)."""
    walls = (getattr(planar, "road_terrace", None) or {}).get("wall_air") or {}
    out: dict[int, tuple[float, str]] = {}
    if not walls:
        return out
    tol = float(design_law(law).hard_tol_m)
    for _k, rec in sorted(walls.items()):
        h = float(rec.get("height_m") or 0.0)
        for a, b, _d in rec.get("pairs") or ():
            za, zb = float(z[a]), float(z[b])
            if abs(za - zb) <= h + tol:
                continue
            lo_v, floor = (b, za - h) if za > zb else (a, zb - h)
            if lo_v not in out or floor > out[lo_v][0]:
                out[lo_v] = (floor, str(rec.get("label", "")))
    return out


def wall_floor_rows(planar: PlanarMap, law: Law, z: _t.Sequence[float]
                    ) -> list[Band]:
    """The floor ``Band`` rows against the solved ``z`` (dense, per vertex
    id), empty where every pair stands within its wall (module
    docstring)."""
    return [Band(int(v), f, None,
                 Source(GEN, f"{WALL_FLOOR_RULING} (owner RULINGS 2026-10-28s (2) "
                        f"Q250 a: at most {lab}'s height below the upper side)",
                        (f"vertex:{v}", lab)))
            for v, (f, lab) in sorted(_floors(planar, law, z).items())]


def wall_floor_pass(planar: PlanarMap, cs: ConstraintSet, law: Law, got: tuple,
                    solve1: _t.Callable[[PlanarMap, ConstraintSet], tuple],
                    again: _t.Callable[..., tuple]
                    ) -> tuple[ConstraintSet, tuple, list[dict], "dict | None"]:
    """``got`` (one ``solve1`` answer on ``cs``) re-solved ONCE with the
    floors — ``(cs, got, pin releases, record)``; the input itself and
    ``None`` when no pair stands over its wall.  ``again(planar, cs, law,
    got, solve1)`` is ``flex.yield_stage_one`` (the pins stage 1 reads
    yield in this solve too)."""
    rows = wall_floor_rows(planar, law, got[0].z)
    if not rows:
        return cs, got, [], None
    cs_w = ConstraintSet.from_rows(list(cs.rows()) + rows)
    cs_w, got_w, yielded = again(planar, cs_w, law, solve1(planar, cs_w), solve1)
    tol = float(design_law(law).hard_tol_m)
    z = got_w[0].z
    unmet = [{"v": r.v, "at": list(planar.vertices[r.v].key),
              "short_m": round(float(r.lo) - float(z[r.v]), 4),
              "wall": r.source.inputs[1]}
             for r in rows if float(z[r.v]) < float(r.lo) - tol]
    before = got[0].z
    rec = {"rows": len(rows),
           "worst_lift_m": round(max(float(r.lo) - float(before[r.v]) for r in rows), 4),
           "unmet": unmet,
           "residual_after": len(_floors(planar, law, z))}
    return cs_w, got_w, yielded, rec
