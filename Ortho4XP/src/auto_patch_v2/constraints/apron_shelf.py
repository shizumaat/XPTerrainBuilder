"""THE APRON-EDGE SHELF FILLS, IT NEVER CUTS — the stage-2 release of a
shelf's level (owner RULINGS 2026-10-14n D2, issue #709; ``planar/
apron_shelf`` mints the shelf).

D2 is the FLOAT rule: the part of a building on an apron that reaches past
its edge "takes the apron's level and banks to the ground" — because the
ground there is BELOW the apron and the building floats.  At the mint no
level exists (stage 1 has not run; the DEM does not know an apron filled
1.5 m over it at KASE or cut 7 m under it at HECA T3), so the witness's
second half is asked HERE, between §20b's stages, with stage 1's solved
airside levels as constants: a shelf keeps its §20 level rows (the ones
the ``[design] pad_level_rulings`` register names) only where the apron
level its rows lead to stands ABOVE the shelf's own ground (its vertices'
DEM mean) by more than ``[placement] split_tol_m`` — the object stage's
own tolerance for two grounds under one body.  Elsewhere the rows are
RELEASED and the shelf is a pad fronting nothing: flat at its own DEM
datum (``solve/design`` §9b keeps the datum of a pad no level row
governs), its collar banking to it.  MEASURED (HECA closing build,
``unit:41#345``): unreleased, a shelf beside the T3 apron stood 6.9-7.8 m
under the DEM with no room for a collar — a cut wall, which D2 never asked
for.

Called from ``road_ramp.reach_seed_rewrite``, the one stage-2 rewrite every
solve path binds; reads only the rows and the levels, so stage 1 and the
airside are untouched by construction."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap, is_collar_ref, is_shelf_ref

__all__ = ["shelf_release"]


def _head(row) -> str:
    return str(row.source.ruling).split("(", 1)[0].strip()


def _shelf_vertices(planar: PlanarMap) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for f in planar.faces.values():
        if is_shelf_ref(f.ref) and not is_collar_ref(f.ref):
            vs = out.setdefault(str(f.ref), set())
            for ring in (f.ring, *f.holes):
                vs.update(planar.ring_vertices(ring))
    return out


def _terms(row) -> tuple[int, ...]:
    if hasattr(row, "terms"):
        return tuple(int(t) for t, _c in row.terms)
    return tuple(int(v) for v in (getattr(row, "a", None), getattr(row, "b", None))
                 if v is not None)


def shelf_release(planar: PlanarMap, law: Law, cs: ConstraintSet,
                  levels: _t.Mapping[int, float]
                  ) -> tuple[ConstraintSet, list[dict]]:
    """``(cs without the level rows of every shelf that would cut, one
    record per shelf)`` — module docstring."""
    import dataclasses as _dc
    shelves = _shelf_vertices(planar)
    if not shelves or not levels:
        return cs, []
    heads = set(law.tables.emit.design.pad_level_rulings)
    tol = float(law.tables.structures.placement.split_tol_m)
    owner: dict[int, str] = {v: r for r, vs in shelves.items() for v in vs}
    lead: dict[str, list[float]] = {}
    for row in (*cs.linears, *cs.diffs):
        if _head(row) not in heads:
            continue
        ts = _terms(row)
        refs = {owner[t] for t in ts if t in owner}
        if len(refs) != 1:
            continue
        lead.setdefault(next(iter(refs)), []).extend(
            float(levels[t]) for t in ts if t in levels and t not in owner)
    recs: list[dict] = []
    drop: set[str] = set()
    for ref, vs in sorted(shelves.items()):
        dem = [float(planar.vertices[v].dem_z) for v in vs
               if planar.vertices[v].dem_z is not None]
        zs = lead.get(ref) or []
        if not dem or not zs:
            continue
        level = sum(zs) / len(zs)
        ground = sum(dem) / len(dem)
        keep = level - ground > tol
        if not keep:
            drop.add(ref)
        recs.append({"ref": ref, "level_m": round(level, 3),
                     "ground_m": round(ground, 3), "kept": keep})
    if not drop:
        return cs, recs

    def _ok(row) -> bool:
        return not (_head(row) in heads
                    and any(owner.get(t) in drop for t in _terms(row)))
    return (_dc.replace(cs, linears=tuple(r for r in cs.linears if _ok(r)),
                        diffs=tuple(r for r in cs.diffs if _ok(r))), recs)
