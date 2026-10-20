"""THE SEAM BETWEEN TWO BANKS (issue #711, HECA T3 viaduct landings).

A vertex that only collars share, of two platforms, is ground both banks
reach.  ``constraints/platform`` read each collar as "another pad" to the
other and gave the vertex no row at all, so the bending stencil alone held
it.  MEASURED (HECA replay at main e2f2e7e4): the seam of
``building4/landing4#collar`` and ``runout:building4/landing4#collar`` at
30.1113600, 31.3922450 stood at 92.02 m over a 95.28 m DEM, a 3.3 m pit
between a 100.5 m run-out and the lot at its DEM.  With each collar's
one-way 1:3 rim row on it, it stood at 96.92 m.

The fixture: two ramp landings side by side, each a flat face with its
5 m ``#collar`` bank, the two banks sharing the line x = 0.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import platform
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import COLLAR_SUFFIX, is_collar_ref
from auto_patch_v2.planar.build import build
from test_unitplatform_platform import _base_cells, _Dem
from test_v2frontage import _airport, _rect

A, B = "padU/landing0", "padU/landing1"


@pytest.fixture(scope="module")
def seam_law():
    # a landing's flat face is no held block: the 29s contact-led plane
    from tests.auto_patch_v2._plate import contact_led_law
    return contact_led_law(Law.for_airport("ZZZZ"))


@pytest.fixture(scope="module")
def seamed(seam_law):
    cells = _base_cells() + [
        Cell(2, "building", A, _rect(-55.0, 205.0, -5.0, 295.0), (), None, None,
             "airside", "pad", {}),
        Cell(3, "building", A + COLLAR_SUFFIX, _rect(-60.0, 200.0, 0.0, 300.0),
             (_rect(-55.0, 205.0, -5.0, 295.0),), None, None, "airside", "pad", {}),
        Cell(4, "building", B, _rect(5.0, 205.0, 55.0, 295.0), (), None, None,
             "airside", "pad", {}),
        Cell(5, "building", B + COLLAR_SUFFIX, _rect(0.0, 200.0, 60.0, 300.0),
             (_rect(5.0, 205.0, 55.0, 295.0),), None, None, "airside", "pad", {})]
    airport = _airport(seam_law, _Dem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), seam_law)
    return pm, airport


def test_a_vertex_only_two_collars_share_keeps_both_banks(seamed, seam_law):
    pm, airport = seamed
    edge_v = {v for e in pm.edges.values() if e.left_face is None or e.right_face is None
              for v in (e.a, e.b)}
    seam = {v for v, vx in pm.vertices.items() if v not in edge_v and vx.incident_faces
            and all(is_collar_ref(pm.faces[q].ref) for q in vx.incident_faces)
            and len({pm.faces[q].ref for q in vx.incident_faces}) == 2}
    assert seam, "the fixture must carry a seam vertex off the coverage edge"
    rows = [r for r in platform.platform_collar_rows(pm, seam_law, airport) if r.a in seam]
    plate = {v: {pm.faces[q].ref for q in vx.incident_faces}
             for v, vx in pm.vertices.items()}
    for v in seam:
        mine = [r for r in rows if r.a == v]
        # one row set from EACH landing's flat face, every one a one-way
        # 1:3 bank with the flat side leading
        assert {A, B} <= {ref for r in mine for ref in plate[r.b]}
        assert all(r.follows == (v,) and r.cap == pytest.approx(
            float(seam_law.tables.emit.design.bank_slope)) for r in mine)
