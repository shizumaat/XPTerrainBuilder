"""Issue #1849: the last stage's map decides the structures as the base map
did.  The base map is built without the LAST-STAGE cells
(``pipeline/stage_one_map.gap_free``: the gap pieces and the pad roads), so
every such cell must FOLLOW the structures on the last stage's map
(``planar/structure_approach.standing_cover``) and be no field
(``cover_polygons``).  MEASURED KPHX T4: a standing pad road stopped bore
-22827's mouth off ``building15`` and the bore took R6 run 0's place."""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import box

from auto_patch_v2.model.planar import GAP_PREFIX, ROAD_REACH_KEY
from auto_patch_v2.pipeline.stage_one_map import gap_free
from auto_patch_v2.planar.structure_approach import (cover_polygons, cut_gap_cells,
                                                     standing_cover)


@_dc.dataclass(frozen=True)
class _Cell:
    ref: str
    ring: tuple
    holes: tuple = ()
    evidence: dict = _dc.field(default_factory=dict)


@_dc.dataclass(frozen=True)
class _Cl:
    cells: tuple


def _sq(x: float) -> tuple:
    return tuple(box(x, 0.0, x + 10.0, 10.0).exterior.coords)[:-1]


CELLS = (
    _Cell("pav1", _sq(0.0)),
    _Cell("small_roads:-1", _sq(20.0), evidence={"pad_road": 1.0}),
    _Cell("small_roads:-2", _sq(40.0), evidence={"pad_road": 1.0, ROAD_REACH_KEY: 1.0}),
    _Cell("small_roads:-3", _sq(60.0), evidence={ROAD_REACH_KEY: 1.0}),
    _Cell(f"{GAP_PREFIX}:0", _sq(80.0)),
)


def test_every_cell_the_base_map_drops_follows_the_structures():
    cl = _Cl(CELLS)
    base = gap_free(cl)
    dropped = {c.ref for c in cl.cells} - {c.ref for c in base.cells}
    cells, late, polys = standing_cover(cl)
    assert dropped <= {c.ref for c in late}
    assert {c.ref for c in cells} == {"pav1"} and len(polys) == 1
    assert len(cover_polygons(cl)) == 1


def test_a_pad_road_is_cut_flush_and_a_gap_piece_stood_off():
    knife = box(0.0, 4.0, 100.0, 6.0)
    got: dict = {}
    cut_gap_cells([c for c in CELLS if c.ref != "pav1"], knife, _law(),
                  lambda c, _p, blade: got.__setitem__(c.ref, blade))
    for ref in ("small_roads:-1", "small_roads:-2", "small_roads:-3"):
        assert got[ref].equals(knife)
    assert got[f"{GAP_PREFIX}:0"].area > knife.area


def _law():
    from auto_patch_v2.law import Law
    return Law.for_airport("SYNT")
