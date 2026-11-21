"""The taxi route runs on across pavement the planar stage adds
(``planar/route_lines``) and a generated taxiway deck nobody paints takes
its route's centreline (``airport/deck_route_paint``) -- owner
2026-11-21T16:00Z, KRDU taxiway E."""
import types

from shapely.geometry import LineString, box

from auto_patch_v2.airport.apt_edit import Dropped
from auto_patch_v2.airport.deck_route_paint import route_centreline
from auto_patch_v2.classify.roles import Classification, CutLine
from auto_patch_v2.model.airport import TaxiEdge, TaxiNode
from auto_patch_v2.planar.route_lines import with_route_lines


def _airport():
    nodes = {0: TaxiNode(0, (0.0, 0.0), "both"), 1: TaxiNode(1, (300.0, 0.0), "both")}
    return types.SimpleNamespace(taxi_nodes=nodes, runways=(),
                                 taxi_edges=(TaxiEdge(0, 1, "E", False, False, "D"),))


def _cl(lines=()):
    return Classification(cells=(), cut_lines=tuple(lines), stats={}, notes=())


def test_a_chain_over_added_pavement_gets_its_centreline():
    """KRDU STH_TML: the classifier cut taxiway E only where a source held
    it (0..100 m); the plate paved after classify (100..250 m) had none."""
    own = CutLine("taxi_centerline", "taxi0", ((0.0, 0.0), (100.0, 0.0)), "D")
    out, n = with_route_lines(_cl([own]), _airport(), [box(80.0, -20.0, 250.0, 20.0)])
    assert n == 1
    new = out.cut_lines[-1]
    assert new.kind == "taxi_centerline" and new.ref == "taxi0" and new.code_letter == "D"
    assert abs(LineString(new.points).length - 149.5) < 1.0     # 100.5 .. 250, not re-cut


def test_nothing_added_where_a_centreline_runs_or_no_chain_crosses():
    full = CutLine("taxi_centerline", "taxi0", ((0.0, 0.0), (300.0, 0.0)), "D")
    cl = _cl([full])
    assert with_route_lines(cl, _airport(), [box(80.0, -20.0, 250.0, 20.0)]) == (cl, 0)
    cl = _cl()
    assert with_route_lines(cl, _airport(), [box(80.0, 50.0, 250.0, 90.0)]) == (cl, 0)
    assert with_route_lines(cl, _airport(), []) == (cl, 0)


def _deck(family="taxi"):
    return {"family": family, "ring": [[0.0, -1.0], [10.0, -1.0], [10.0, 1.0], [0.0, 1.0]],
            "route": [[-5.0, 0.0], [15.0, 0.0]]}


def test_an_unpainted_taxiway_deck_takes_its_route_centreline():
    got = route_centreline(_deck(), [], None)
    assert len(got) == 1 and got[0].line == 1
    assert abs(LineString(got[0].points).length - 10.0) < 1e-9


def test_a_painted_or_road_deck_keeps_its_own_paint():
    centre = Dropped(7, ((0.0, 0.0), (10.0, 0.0)), 51, 0)
    assert route_centreline(_deck(), [centre], None) == []
    authored = types.SimpleNamespace(lines=(("page", [(0.0, 0.0), (10.0, 0.0)]),))
    assert route_centreline(_deck(), [], authored) == []
    # an author's EDGE line (KRDU SeasonEdge.lin) paints no centreline
    edge = types.SimpleNamespace(lines=(("page", [(0.0, 0.9), (10.0, 0.9)]),))
    assert len(route_centreline(_deck(), [], edge)) == 1
    assert route_centreline(_deck("road"), [], None) == []
