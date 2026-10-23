"""THE RUNWAY FAMILY HOLDS NO STEP BETWEEN ITS OWN FACES
(``constraints/runway_step``; §40 (5) (4), RULINGS 2026-09-15az).

The class HECA showed on its WED pack: a runway-shoulder RIBBON under a
metre wide between the slab and an apron that abuts it — the ribbon's
inner edge is the slab's, its outer edge the apron's — on ground falling
away from the runway, so the apron's own law pulls the outer edge down.
``runway_transverse`` bounds each vertex against the ridge only, so the
ribbon could tilt 0.5 m over 0.8 m and the census read a ``runway_step``
DEFECT.  The twins hold:

* every outer-edge vertex of the ribbon carries a contact row against the
  slab face's edge, its bound the verify allowance less the held bar;
* a welded vertex (one the slab face shares) carries none.

The closing measurement is HECA's (the rows took its ``runway_step``
DEFECT rows to zero); a synthetic solve does not reproduce the apron pull
that tilted the ribbon there, so no solve twin is claimed here.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.runway_step import runway_step_rows
from auto_patch_v2.law import Law
from tests.auto_patch_v2.test_crown import (
    HALF_WIDTH,
    Airport,
    Cell,
    Classification,
    Frame,
    Runway,
    RunwayEnd,
    SceneryPack,
    _rect,
    _rot,
    build,
)

SEAM_M = 0.8


class _FallingDem:
    """Ground falling 6 % away from the runway's north edge."""
    provenance = {"synthetic": "plane falling 6 % north"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 0.06 * max(y, 0.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def seam(law):
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", r((600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _FallingDem(), law.ruleset_key)
    top = HALF_WIDTH + SEAM_M
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -600, -HALF_WIDTH, 600, HALF_WIDTH), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "runway", "09/27", _rect(r, -300, HALF_WIDTH, 300, top), (), 3, "D",
             "airside", "runway_shoulder", {}),
        Cell(2, "apron", "apronA", _rect(r, -300, top, 300, 120), (), None, "D",
             "airside", "apron", {}),
    )
    pm, _stats = build(airport, Classification(cells, (), {}, ()), law)
    return airport, pm


def _ribbon(pm, law):
    vw = view(pm, law)
    fs = [f for f in vw.faces_of_role(("runway",))
          if any(pm.faces[g].role == "apron" for v in vw.face_vertices(f.id)
                 for g in pm.vertices[v].incident_faces)]
    assert len(fs) == 1, [(f.id, f.role) for f in fs]
    return vw, fs[0]


def test_the_ribbon_outer_edge_is_held_to_the_slab(seam, law):
    airport, pm = seam
    vw, rib = _ribbon(pm, law)
    rows = runway_step_rows(pm, law, airport)
    outer = {v for v in vw.face_vertices(rib.id)
             if any(pm.faces[g].role == "apron" for g in pm.vertices[v].incident_faces)}
    probed = {r.terms[0][0] for r in rows if r.terms[0][1] == 1.0}
    assert outer and outer <= probed, (sorted(outer), sorted(probed))
    floor = float(law.tables.emit.materiality.runway_step_m)
    assert all(0.0 <= r.hi <= floor and r.lo == -r.hi for r in rows)
    # a vertex the slab face shares (the ribbon's inner edge) reads zero
    slab = {v for f in vw.faces_of_role(("runway",)) if f.id != rib.id
            for v in vw.face_vertices(f.id)}
    assert not (probed & (set(vw.face_vertices(rib.id)) & slab) - outer)

