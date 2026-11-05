"""#1093 rule 1 (owner 2026-11-04): A RUN-OUT'S BANK STOPS AT A ROAD'S EDGE.

"Where a bank meets a road ... the road keeps its own level and grade; the
bank stops at the road's edge and slopes down beside it, never across it."
MEASURED (KCLT east foot, matched control at main 85a4ebb1c): the strip's
own bank ``runout:2#collar`` shared vertices with the pad roads
``small_roads:-11471`` / ``-8197#1`` beside it, and its 1:3 rows from the
strip to those road vertices held ``runout:2`` up to 0.26 m under its
design profile (8 of 9 rows missed).

The fixture: a run-out strip, its bank, and a road whose edge the bank
shares.  No 1:3 bank row may name a road vertex; the strip's own vertices
keep theirs.
"""
from __future__ import annotations

from auto_patch_v2.classify.ramp_runout import BANK_EVIDENCE
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import platform
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import COLLAR_SUFFIX
from auto_patch_v2.planar.build import build
from test_unitplatform_platform import _base_cells, _Dem
from test_v2frontage import _airport, _rect

RUN = "runout:0"


def test_a_runout_bank_never_ties_a_road_to_its_strip():
    law = Law.for_airport("ZZZZ")
    ev = {"pad_road": 1.0, "ramp_runout": 1.0, "runout_x0": 0.0, "runout_y0": 300.0,
          "runout_dx": 0.0, "runout_dy": 1.0, "runout_z0": 14.0, "runout_dem0": 10.0,
          "runout_run_m": 60.0, "runout_width_m": 10.0}
    cells = _base_cells() + [
        Cell(2, "service_road", RUN, _rect(-5.0, 300.0, 5.0, 360.0), (), None, None,
             "groundside", "service_road", ev),
        Cell(3, "building", RUN + COLLAR_SUFFIX, _rect(5.0, 300.0, 8.0, 360.0), (), None,
             None, "groundside", "building", {BANK_EVIDENCE: 1.0}),
        Cell(4, "service_road", "small_roads:-1", _rect(8.0, 300.0, 14.0, 360.0), (), None,
             None, "groundside", "service_road", {"pad_road": 1.0})]
    pm, _st = build(_airport(law, _Dem()), Classification(tuple(cells), (), {}, ()), law)
    assert RUN in pm.ramp_runouts
    road = {v for f in pm.faces.values() if f.ref == "small_roads:-1"
            for v in pm.ring_vertices(f.ring)}
    strip = {v for f in pm.faces.values() if f.ref == RUN for v in pm.ring_vertices(f.ring)}
    rows = [r for r in platform.platform_collar_rows(pm, law)
            if str(r.source.inputs[1]) == RUN + COLLAR_SUFFIX]
    assert not [r for r in rows if {r.a, r.b} & road], "a bank row ties the road to the strip"
    assert any({r.a, r.b} & strip for r in rows) or not rows
