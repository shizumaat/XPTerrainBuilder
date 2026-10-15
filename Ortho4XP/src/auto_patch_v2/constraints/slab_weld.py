"""A BASE SLAB WELDS TO THE PAVEMENT BESIDE IT ACROSS THE STAND-OFF (issue
#712; owner RULINGS 2026-10-10o (B): pavement beside a slab welds to it as
to any pavement).

The base-slab pieces (``classify/gap_mint``, evidence ``base_slab``) are
minted after the pack's own gap pieces and STAND OFF them (§53 (12),
lane slab229 FIX 2), and both join in the last stage as unknowns: the
gap-follow rows (``constraints/gap_follow``) bind each to the BASE map's
standing rings, never to each other, so a slab and the lot it fills could
meet across the stand-off at any two levels.  MEASURED (HECA, the
``Seasonal_Terminal/asphalt_3`` plate in the pack's draped asphalt page's
hole, #712 at 30.1096365, 31.3889978): 14 rim pairs within 3 m, step
median 0.87 m, worst 1.86 m over 1.6 m — the owner's "the lot needs to
weld to the paved slab along its whole edge".

THE WELD: every rim vertex of a slab piece takes one HARD ``Diff`` against
the nearest vertex of a pack gap piece within the follow reach
(``gap_follow.reach_m``) at the slab's own role cap over their distance —
the two pavements meet at one level along the shared edge, each grading
under its own law behind it.  Solved in the last stage WITH both pieces,
so neither leads; every other level is a constant there.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import Diff, Source
from ..model.planar import PlanarMap

__all__ = ["slab_weld_rows", "GEN", "RULING"]

GEN = "slab_weld"
RULING = ("gap slab welds to the pavement beside it across the stand-off "
          "(owner 2026-10-10o (B); issue #712)")


def slab_weld_rows(planar: PlanarMap, law: Law, cl, fixed: _t.Mapping[int, float]
                   ) -> tuple[list, dict[str, _t.Any]]:
    """``(rows, report)`` — the weld rows (module docstring).  ``cl`` is the
    last stage's classification (the cut parts carry their piece's
    evidence); ``fixed`` its constants — a vertex an earlier stage holds
    keeps its own rows (the follow rows reach it), so only a pair of two
    unknowns is welded here."""
    from scipy.spatial import cKDTree

    from ..law.tables import role_cap
    from ..model.planar import is_gap_ref
    from .gap_follow import reach_m
    rep: dict[str, _t.Any] = {"pairs": 0, "slab_faces": 0}
    # an elevated deck's ground (``base_slab_deck``) is no slab surface
    slab = {str(c.ref) for c in cl.cells
            if is_gap_ref(c.ref) and (c.evidence or {}).get("base_slab")
            and not (c.evidence or {}).get("base_slab_deck")}
    deck = {str(c.ref) for c in cl.cells if (c.evidence or {}).get("base_slab_deck")}
    if not slab:
        return [], rep
    pack = {str(c.ref) for c in cl.cells
            if is_gap_ref(c.ref) and str(c.ref) not in slab and str(c.ref) not in deck}
    F = planar.faces

    def verts(f) -> set[int]:
        return {v for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)}
    pv = sorted({v for f in F.values() if str(f.ref) in pack for v in verts(f)})
    if not pv:
        return [], rep
    xy = {v: planar.vertices[v].xy for v in pv}
    tree = cKDTree([xy[v] for v in pv])
    reach = reach_m(law)
    rows: list = []
    seen: set[tuple[int, int]] = set()
    for f in sorted(F.values(), key=lambda q: q.id):
        if str(f.ref) not in slab:
            continue
        rc = role_cap(law, f.role)
        if rc is None:
            continue
        rep["slab_faces"] += 1
        cap = float(rc.longitudinal)
        src = Source(GEN, RULING, (f"face:{f.id}", str(f.ref)))
        for v in sorted(verts(f)):
            d, j = tree.query(planar.vertices[v].xy)
            u = pv[int(j)]
            if d > reach or d <= 0.0 or v in fixed or u in fixed or (v, u) in seen:
                continue
            seen.add((v, u))
            rows.append(Diff(v, u, cap, float(d), src))
    rep["pairs"] = len(rows)
    return rows, rep
