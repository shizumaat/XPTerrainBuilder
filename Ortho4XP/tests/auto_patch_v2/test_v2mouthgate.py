"""§29 TWINS — A MOUTH IS BUILT ONLY ON THE FIELD (owner RULINGS
2026-09-12r "we should never emit anything for actual tunnels, only the
tunnel mouths and entrance/exit ramps"; Fable 2026-09-12t; spec §29).

The defect these twins found: LEMD's two 4.9 km rail bores were admitted
by 125–162 m of cover under ONE building pad and then built BOTH mapped
ends — the south-west pair standing 4.0 km west of every other feature
and 95 m up a hillside (ramps, rims and banks, 149 vertices, the patch's
whole western bbox edge, zero grade rows).  The law: a mapped end
outside the classified cover ⊕ ``[tunnel] mouth_standoff_m`` is DROPPED,
and admission follows the mouth — a bore with no on-field mouth emits
nothing, however much of its length runs under a cell.

One synthetic airport, one apron, one bore per case; law values are read
from the tables, never retyped.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, OsmWay, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structures import build_structures


class _PlaneDem:
    provenance = {"synthetic": "plane 0.5 % up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.005 * x

    def bounds(self):
        return (-20000.0, -20000.0, 20000.0, 20000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells():
    """A runway and the apron the bore passes under (x −80 … 80)."""
    return [
        Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apron1", _rect(-80, -60, 80, 60), (), None, None,
             "airside", "apron", {}),
    ]


TAGS_T = {"highway": "secondary", "tunnel": "yes", "lanes": "2", "layer": "-1"}
TAGS_R = {"highway": "secondary", "lanes": "2"}


def _run(law, bore_pts, approaches=(), extra_cells=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    ways = [OsmWay(-101, "big_roads", tuple(bore_pts), False, TAGS_T)]
    ways += [OsmWay(-200 - i, "big_roads", tuple(a), False, TAGS_R)
             for i, a in enumerate(approaches)]
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), tuple(ways), (), (), pack, _PlaneDem(), law.ruleset_key)
    cl = Classification(tuple(_cells()) + tuple(extra_cells), (), {}, ())
    return build_structures(airport, cl, law)


def test_a_mouth_on_the_field_is_kept_and_built(law):
    """The baseline: a bore under the apron with both mapped ends ON it —
    two mouths, none off-field, a ramp cell for each."""
    cl2, tunnels, st = _run(law, ((-80.0, -6.0), (80.0, -6.0)),
                            (((80.0, -6.0), (900.0, -6.0)),
                             ((-80.0, -6.0), (-900.0, -6.0))))
    assert st.bores == 1 and st.bores_no_mouth == 0
    assert st.mouths == 2 and st.mouths_off_field == 0
    assert st.tunnels == 2 and not st.refused, st.refused
    assert [c.role for c in cl2.cells].count("tunnel_ramp") == 2


def test_an_off_field_mouth_is_dropped_and_counted(law):
    """§29 (1): the same bore run 2 km east — its east end stands far
    outside the cover ⊕ standoff, so that mouth is dropped (counted) and
    only the on-field west mouth is built."""
    cl2, tunnels, st = _run(law, ((-80.0, -6.0), (2000.0, -6.0)),
                            (((2000.0, -6.0), (2900.0, -6.0)),
                             ((-80.0, -6.0), (-900.0, -6.0))))
    assert st.bores == 1 and st.bores_no_mouth == 0
    assert st.mouths == 1 and st.mouths_off_field == 1
    assert st.tunnels == 1 and not st.refused, st.refused
    # the one ramp built stands at the WEST mouth
    assert [c.role for c in cl2.cells].count("tunnel_ramp") == 1
    assert tunnels[0].axis[0][0] == pytest.approx(-80.0, abs=1.0)


def test_a_bore_admitted_only_by_cover_emits_nothing(law):
    """§29 (2) — THE LEMD RAIL BORE: 4 km of bore crossing the apron (160 m
    of cover, far past the retired ≥ 1 m admission) with BOTH mapped ends
    off the field emits NOTHING: no mouth, no tunnel, no cell touched."""
    cl2, tunnels, st = _run(law, ((-2000.0, -6.0), (2000.0, -6.0)))
    assert st.bores == 1 and st.bores_no_mouth == 1
    assert st.mouths == 0 and st.mouths_off_field == 2
    assert st.tunnels == 0 and tunnels == () and st.cells_cut == 0
    assert [c.role for c in cl2.cells] == [c.role for c in _cells()]
    assert not any(c.role in ("tunnel_ramp", "retaining_wall") for c in cl2.cells)


def test_the_gate_is_the_cover_grown_by_the_standoff(law):
    """The region is the classified cover ⊕ ``mouth_standoff_m`` (150 m,
    round 3 — the MEASURED population of on-field highway mouths at LEMD
    ends at 146 m and the next drop stands at 208 m, so the value sits in
    that gap; the rail mouths are 4,000 m out): a mouth inside the
    standoff of the apron edge is built, one well beyond it is dropped.
    The law value is read, never retyped."""
    so = law.tables.structures.tunnel.mouth_standoff_m
    assert so >= 146.0, ("the standoff must clear the whole measured on-field "
                         "population (the farthest kept mouth stands 146 m off)")
    x_in = 80.0 + 0.5 * so
    x_out = 80.0 + 2.0 * so
    _cl, _t, st_in = _run(law, ((0.0, -6.0), (x_in, -6.0)))
    assert st_in.mouths == 2 and st_in.mouths_off_field == 0   # both within the standoff
    _cl, _t, st_out = _run(law, ((0.0, -6.0), (x_out, -6.0)))
    assert st_out.mouths == 1 and st_out.mouths_off_field == 1  # the far end is beyond it


def test_a_mouth_on_the_field_is_built_though_its_bore_covers_nothing(law):
    """§29 (2) as the owner ruled it (2026-09-12ab, "Build them"): a bore
    whose mouth stands on the field is BUILT whether or not the bore
    passes under an airport surface — a portal on the field is visible on
    approach — and is counted and named where the retired cover test
    would have refused it (LEMD: 8 such bores, 9 corridors, +329 census
    rows, accepted)."""
    so = law.tables.structures.tunnel.mouth_standoff_m
    x = 80.0 + 0.5 * so                       # on the field, under nothing
    cl2, tunnels, st = _run(law, ((x, -6.0), (x + 300.0, -6.0)))
    assert st.mouths == 1 and st.mouths_off_field == 1 and st.bores_no_mouth == 0
    assert st.bores_mouth_only == 1 and st.mouth_only_bores == ["-101"]
    assert st.tunnels == 1 and len(tunnels) == 1
    assert [c.role for c in cl2.cells].count("tunnel_ramp") == 1
    # a bore that IS under the cover is built too, and is not counted there
    _cl, t2, st2 = _run(law, ((-80.0, -6.0), (80.0, -6.0)))
    assert st2.bores_mouth_only == 0 and st2.bores_no_mouth == 0
    assert st2.tunnels == 2 and len(t2) == 2


def test_a_mouth_off_the_cover_whose_ramp_reaches_the_field_is_kept(law):
    """§29 (1) tests the mouth point AND ITS RAMP REACH: a mapped end far
    outside the standoff of every cell, whose approach corridor runs ON
    to a cell beyond it, keeps its mouth (the ramp is built across the
    field it serves); the other end of the same bore — nothing but
    hillside beyond it — is dropped."""
    so = law.tables.structures.tunnel.mouth_standoff_m
    x = 80.0 + 4.0 * so                                   # far outside the standoff
    far = Cell(3, "apron", "apron2", _rect(x + 2.0 * so, -60, x + 4.0 * so, 60), (), None,
               None, "airside", "apron", {})
    cl2, tunnels, st = _run(law, ((-2000.0, -6.0), (x, -6.0)),
                            (((x, -6.0), (x + 900.0, -6.0)),), (far,))
    assert st.mouths == 1 and st.mouths_off_field == 1
    assert st.bores_no_mouth == 0
    assert st.tunnels == 1
    assert tunnels[0].axis[0][0] == pytest.approx(x, abs=1.0)
