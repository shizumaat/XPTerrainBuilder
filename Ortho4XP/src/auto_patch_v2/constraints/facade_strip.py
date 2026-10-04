"""THE FACADE STRIP STANDS AT ITS HOST PAD'S LEVEL (spec §52; owner
RULINGS 2026-10-04d (3) (a) "at the pad's level ... welded to the pad
edge; the pad footprint, frontage and weld do not move"; master
2026-10-04 row 15).

One equality per strip vertex: the vertex against the pad's value at its
nearest rim (§28's own leader, ``pad_frontage_gs._GS_LEADER_K`` rim
vertices inverse-distance weighted, weights summing to 1), priced at
``[design] pad_flat`` (``pad_flat_rulings``).  The strip is a LATE cell
(``model.planar.is_late_ref``), absent from the stage-1 map, so the row
exists in stage 2 only, and the strip carries NO DEM datum of its own
(``solve/design_assemble``), so nothing but this row places it.

ROUND-2 STATE, PENDING THE MASTER'S RULING (spec §52 (6)).  Row 15 ruled
the row HARD and one-way.  MEASURED on the SPJC replay: hard, the stage-2
solve collapsed (``building16`` 30.23 -> 0.06 m); one-way, the lag
(``one_way_max_rounds`` 3) leaves the strip of a pad stage 2 itself
solves 1.11 m off it.  Two-way at the pad's own price holds all four
strips within 0.01 m; a held pad cannot move, an unheld one moved 0.03 m.

§28 (``groundside_frontage_level``) does NOT carry this: it drops a
pad|face pair whose DEM step exceeds ``frontage_step_max_m`` as a hillside
terrace, and a truck dock's DEM stands metres off the dock (SPJC
6.0-8.0 m).  The strip is the facade file's declaration that the ground
there is the pad's, so it is excluded from §28's candidates and held
here over its WHOLE face, not on its frontage vertices alone."""
from __future__ import annotations

import math

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap, facade_strip_host, is_facade_strip_ref
from .pad_frontage_gs import _GS_LEADER_K
from .pads import _pad_groups, _two_sided

__all__ = ["GEN", "LEVEL_RULING", "facade_strip_level", "STATS"]

GEN = "facade_strip_level"
#: the ruling head ``[design] hard_rulings`` and ``one_way_rulings`` name
LEVEL_RULING = "structures.building_pad facade_strip level"
STATS: dict[str, int] = {}


def facade_strip_level(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The strip's level rows (module docstring).  A generator
    (``constraints.GENERATORS``)."""
    strips = [f for f in planar.faces.values() if is_facade_strip_ref(f.ref)]
    STATS.clear()
    STATS.update(strips=len(strips), rows=0, no_host=0)
    if not strips:
        return []
    rim: dict[str, list[int]] = {}
    for _fid, ref, group in _pad_groups(planar, law):
        rim.setdefault(str(ref).split("#")[0], []).extend(group)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    for f in sorted(strips, key=lambda f: f.id):
        host = facade_strip_host(f.ref)
        pgroup = sorted(set(rim.get(host or "", ())))
        if not pgroup:
            STATS["no_host"] += 1
            continue
        own = set(pgroup)
        src = Source(GEN, LEVEL_RULING + " (owner 2026-10-04d (3) (a): the strip "
                     "under a facade wall's attached vehicles stands at the pad's "
                     "level)", (f"face:{f.id}", f.ref, f"pad:{host}"))
        vs = {v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
        for v in sorted(vs - own):
            near = sorted((math.hypot(xy[v][0] - xy[u][0], xy[v][1] - xy[u][1]), u)
                          for u in pgroup)[:_GS_LEADER_K]
            inv = [1.0 / max(1e-3, d) for d, _u in near]
            tot = sum(inv)
            terms: dict[int, float] = {v: 1.0}
            for (_d, u), w in zip(near, inv):
                terms[u] = terms.get(u, 0.0) - w / tot
            rows.extend(_two_sided(tuple(terms.items()), src, (v,)))
            STATS["rows"] += 2
    return rows
