"""#2239 / #2241 (spec cyyz-decks-r3 R4 / R5): a pack deck's apron -- the
unowned ground outside its end edges (``planar/deck_apron``), flush over
its run-on band (``constraints/deck_edge_weld``) -- and the floor pinch
family (``verify/deck_pinch``, ``check_grade_lib/families/deck_floor_pinch``)."""
from __future__ import annotations

import sys
import types
from pathlib import Path

from auto_patch_v2.constraints.deck_edge_weld import edge_vertices
from auto_patch_v2.law import Law
from auto_patch_v2.planar.deck_apron import _apron_depth, apron_cells
from auto_patch_v2.verify import deck_pinch
from shapely.geometry import Point, Polygon

RING = [(0.0, 0.0), (68.0, 0.0), (68.0, 28.0), (0.0, 28.0)]
LINE = [(float(x), 0.0) for x in range(10, 61, 5)]
LAW = Law.for_airport("CYYZ")


def _deck(**kw):
    base = dict(object_id="dsf:o1", members=("dsf:o1",), cut="walls", ring=RING,
                seats_a=tuple(LINE), seats_b=tuple((x, 28.0) for x, _y in LINE),
                deck_z=167.5, family="taxi", resource="x.obj", witness="hard_deck")
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_the_apron_runs_out_past_the_run_on_to_the_ground():
    # 7.5 m over the DEM: the bank runs 7.5 / 0.667 m past the 1 m run-on
    assert abs(_apron_depth(_deck(), LAW, lambda _p: 160.0) - (1.0 + 7.5 / 0.667)) < 1e-6
    assert _apron_depth(_deck(), LAW) == 6.0
    # the taxiway owns 10-60 m south of the deck: the apron is the shoulders and the north
    taken = Polygon([(10.0, -20.0), (60.0, -20.0), (60.0, 0.0), (10.0, 0.0)])
    cells = apron_cells([_deck()], [], LAW, taken, lambda ref, q: (ref, q))
    union = [q for _r, q in cells]
    assert all(r.startswith("deck_apron:dsf:o1#") for r, _q in cells)
    assert any(q.contains(Point(5.0, -0.5)) for q in union)        # the shoulder gap
    assert any(q.contains(Point(30.0, 28.5)) for q in union)       # the north side
    assert not any(q.contains(Point(30.0, -0.5)) for q in union)   # the pavement's
    # noded on the run-on line: the near piece stops 1 m out
    near = [q for q in union if q.contains(Point(5.0, -0.5))][0]
    assert near.bounds[1] >= -1.0 - 1e-6


def test_the_run_on_band_of_the_apron_is_flush_with_the_edge():
    faces = {1: types.SimpleNamespace(ref="deck_apron:dsf:o1#0", role="graded_strip"),
             2: types.SimpleNamespace(ref="taxi:1", role="primary_parallel")}
    pts = {1: ((5.0, -0.9), (1,)), 2: ((5.0, -3.0), (1,)), 3: ((30.0, -0.8), (1, 2))}
    planar = types.SimpleNamespace(
        vertices={v: types.SimpleNamespace(xy=p, incident_faces=f) for v, (p, f) in pts.items()},
        faces=faces, roles_at=lambda v: tuple(faces[f].role for f in pts[v][1]))
    e = types.SimpleNamespace(deck=_deck(), line=LINE, depth=7.5, tops=())
    got = edge_vertices(planar, [e], 0.35, frozenset({"tunnel_ramp"}), set(), apron=1.0,
                        keep=frozenset({"primary_parallel"}))
    # inside the run-on band (1), never past it (2) nor a pavement neighbour's (3)
    assert set(got) == {1}


def test_a_floor_vertex_on_the_airside_is_a_pinch(monkeypatch):
    import auto_patch_v2.model.platform as platform
    monkeypatch.setattr(platform, "stage_air_vertices", lambda _p, _l: {1})
    roles = {1: ("tunnel_ramp", "primary_parallel"), 2: ("tunnel_ramp",), 3: ("tunnel_ramp",)}
    planar = types.SimpleNamespace(
        vertices={v: types.SimpleNamespace(xy=(float(v), 0.0)) for v in roles},
        roles_at=lambda v: roles[v], decks=(_deck(),))
    weld = types.SimpleNamespace(source=types.SimpleNamespace(
        generator="edge_deck", ruling="r", inputs=("dsf:o1", "edge v3")), terms=((3, 1.0),))
    got = deck_pinch.pinch_records(planar, LAW, [weld], lambda x, y: (y, x))
    assert [(q["v"], q["why"], q["deck"]) for q in got] == [
        (1, "airside", "dsf:o1"), (3, "edge_weld", "dsf:o1")]


def test_the_census_reads_one_row_per_pinch():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from check_grade_lib.families.deck_floor_pinch import check_deck_floor_pinch
    rows = check_deck_floor_pinch([{"deck": "d", "v": 1, "why": "airside", "lat": 1.0,
                                    "lon": 2.0}, {"deck": "d", "v": 2}])
    assert len(rows) == 1 and (rows[0].lat, rows[0].lon) == (1.0, 2.0)
