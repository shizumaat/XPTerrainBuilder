"""#2206: THE LAST STAGES ON ONE MAP (``pipeline/late_stage.run_last_stages``).

Owner 2026-11-21: "we shouldn't be rerunning that long complex calculation
more than once per airport".  The gap pieces, the pad roads and the car lots
were each cut, DERIVED (planar + shapes + constraints) and solved in turn;
now every cut reads the base, the prefix runs once on the full late
classification, and each stage solves on that map with the later stages'
faces withheld (``stage_one_map.withheld_view``).

Synthetic, no corpus: ``test_backhalf_end_to_end``'s two-pass world (a gap
piece beside the pad and the pad road), the gap stage read against the same
world without its pad road (the stage the old second derive gave)."""
from __future__ import annotations

import dataclasses as dc

from auto_patch_v2.pipeline.late_stage import _junior_faces, run_last_stages
from auto_patch_v2.pipeline.prefix import Deriver
from auto_patch_v2.pipeline.stage_one_map import gap_free, withheld_vertices, withheld_view
from auto_patch_v2.solve import Options, solve_design
from tests.auto_patch_v2.test_backhalf_end_to_end import _two_pass_world
from tests.auto_patch_v2.test_solve_late_records import INPUTS, PACK


def _arm(world):
    law, airport, cl = world()
    derive = Deriver(airport, law, INPUTS, PACK)
    pm0, cs0, strips0, hold0 = derive(gap_free(cl))
    sol0, rep0 = solve_design(pm0, cs0, law, Options(), strips=strips0, hold=hold0)
    runs = derive.runs
    lines: list[str] = []
    pm, sol, rep = run_last_stages(
        cl, airport, law, derive,
        {"pm": pm0, "z": sol0.z, "pin_yield": list(rep0.pin_yield or ()),
         "hard_conflict": list(rep0.hard_conflict)},
        options=Options(), out=lines.append)
    return {"pm": pm, "sol": sol, "rep": rep, "lines": lines,
            "late_derives": derive.runs - runs}


def _gap_only_world():
    """The two-pass world without its pad road: the gap stage as the old
    first derive saw it."""
    from auto_patch_v2.classify.roles import is_pad_road_cell
    law, airport, cl = _two_pass_world()
    return law, airport, dc.replace(cl, cells=tuple(c for c in cl.cells
                                                    if not is_pad_road_cell(c)))


def _levels(arm, refs) -> dict:
    pm, z = arm["pm"], arm["sol"].z
    out = {}
    for f in pm.faces.values():
        if str(f.ref).split("#")[0] in refs:
            for cyc in (f.ring, *f.holes):
                for v in pm.ring_vertices(cyc):
                    out[tuple(pm.vertices[v].xy)] = float(z[v])
    return out


def test_two_late_stages_derive_once():
    arm = _arm(_two_pass_world)
    assert arm["late_derives"] == 1
    assert arm["rep"]["one_map"] == {"stages": ["gap", "pad_roads"], "derives": 1}
    assert any("LAST STAGES ON ONE MAP" in ln for ln in arm["lines"])
    # the composed report: the gap stage's records and the roads' both stand
    assert arm["rep"]["gap_stage"]["follow_rows"] == arm["rep"]["gap_stage"][
        "follow_rows_carried"]
    assert set(arm["rep"]["wall_s"]) == {"cut", "derive", "solve"}


def test_the_gap_stage_solves_as_if_the_pad_road_were_not_there():
    """The pad road is junior to the gap piece (13a (1)): on the one map the
    gap stage withholds it, and the piece takes the levels the map without
    the road gave it."""
    one = _arm(_two_pass_world)
    plain = _arm(_gap_only_world)
    a, b = _levels(one, {"gap:0"}), _levels(plain, {"gap:0"})
    shared = set(a) & set(b)
    assert shared
    assert max(abs(a[k] - b[k]) for k in shared) < 0.01


def test_a_withheld_view_keeps_the_ids_and_drops_the_faces():
    law, airport, cl = _two_pass_world()
    derive = Deriver(airport, law, INPUTS, PACK)
    pm, _cs, _s, _h = derive(cl)
    juniors = _junior_faces(pm, "gap")
    assert juniors                                # the pad road is on the map
    view = withheld_view(pm, juniors)
    assert not juniors & set(view.faces)
    assert set(view.vertices) == set(pm.vertices)
    for v in withheld_vertices(pm, juniors):
        assert view.vertices[v].incident_faces == ()
    for e in view.edges.values():
        assert e.left_face not in juniors and e.right_face not in juniors
    assert withheld_view(pm, frozenset()) is pm
    assert _junior_faces(pm, "car_lots") == frozenset()
