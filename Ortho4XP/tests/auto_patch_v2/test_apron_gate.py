"""#2134 WHAT MAY BE AN APRON (owner 2026-11-17; spec
``sim-review/2134-apron-rules.md`` §4).  Twin of ``classify/apron_gate``,
``open_default.apron_witness``, the §27 host class
(``airside_edge.airside_edge_flip``) and the library-path taxi name (Q5)."""
from __future__ import annotations

from auto_patch_v2.classify.airside_edge import airside_edge_flip
from auto_patch_v2.classify.apron_gate import PENDING_KEY, _q3_width_m, resolve_aprons, settle
from auto_patch_v2.classify.evidence import is_library_path, taxi_name_match
from auto_patch_v2.classify.open_default import A1, A2, A3, apron_witness
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from shapely.geometry import Point, box
from shapely.strtree import STRtree

LAW = Law.for_airport("SYNT")
RULES = load_rules()


def _gate(faces, witness, taxi=(), pads=(), taxi_on=frozenset(), path=None,
          no_landside=False):
    return resolve_aprons(faces, witness, list(taxi), [], list(pads),
                          taxi_on=lambda f: any(f.equals(faces[i]) for i in taxi_on),
                          letter_of=lambda f: "C", path_taxi=path or {},
                          no_landside=no_landside, law=LAW, rules=RULES)


def test_a_stand_on_the_cell_is_apron_and_a_lobe_beside_it_is_one_body():
    faces = {0: box(0, 0, 100, 100), 1: box(100, 0, 200, 100), 2: box(400, 0, 500, 100)}
    wit = {0: (A1, "startup on the face"), 1: (A3, "taxi centreline touches the face"),
           2: (A3, "taxi centreline touches the face")}
    g = _gate(faces, wit)
    assert g[0].role == "apron" and g[1].role == "apron"
    assert "one body" in g[1].evidence["apron_verdict"]
    # the detached lobe no stand vouches for is owner Q3: no building -> taxiway
    assert g[2].role == "junction" and g[2].evidence["q3_taxiway"] == 1.0
    assert g[2].letter == _q3_width_m(LAW, RULES)[1] == "F"


def test_q3_a_wide_lobe_touching_a_building_is_apron():
    faces = {0: box(0, 0, 100, 100)}
    g = _gate(faces, {0: (A3, "x")}, pads=[box(100, 0, 140, 60)])
    assert g[0].role == "apron" and "building" in g[0].evidence["apron_verdict"]


def test_a_ribbon_a_taxi_centreline_touches_is_taxi_family_after_the_shoulder_join():
    faces = {0: box(0, 0, 400, 20)}
    g = _gate(faces, {0: (A3, "taxi centreline touches the face")}, taxi_on={0})
    assert g[0].role == "apron" and g[0].evidence[PENDING_KEY] == "C"
    final = [["apron", "pav1", faces[0], None, dict(g[0].evidence), "apron"]]
    assert settle(final) == 1
    assert final[0][0] == "junction" and final[0][3] == "C"


def test_a_lane_of_a_witnessed_apron_is_apron_and_no_witness_is_groundside():
    faces = {0: box(0, 0, 100, 100), 1: box(100, 0, 120, 100), 3: box(500, 0, 520, 100)}
    wit = {0: (A1, "startup on the face"), 1: (None, None), 3: (None, None)}
    g = _gate(faces, wit)
    assert g[1].role == "apron" and "lane" in g[1].evidence["apron_verdict"]
    assert g[3].role is None
    # Q5: a library path naming a taxiway decides only where nothing else does
    assert _gate(faces, wit, path={3: "taxiway"})[3].role == "junction"
    # no terminal: no landside (user 2026-06-11) -> airside, taxi family
    assert _gate(faces, wit, no_landside=True)[3].role == "junction"


def test_the_witness_ladder_rungs():
    face = box(0, 0, 100, 100)
    starts = STRtree([Point(50, 50)])
    assert apron_witness(face, None, {}, starts, 0.0, RULES)[0] == A1
    assert apron_witness(face, None, {}, None, 0.6, RULES)[0] == A2
    # cover under a cell majority, a taxi centreline: airside, never apron (Q1)
    assert apron_witness(face, None, {}, None, 0.2, RULES)[0] == A3
    assert apron_witness(face, None, {"n_taxi": 1}, None, 0.0, RULES)[0] == A3
    # a ribbon has no lobe: a majority of cover is only airside evidence
    assert apron_witness(box(0, 0, 400, 20), None, {}, None, 0.9, RULES)[0] == A3
    assert apron_witness(face, None, {}, None, 0.0, RULES) == (None, None)


def test_a_library_path_names_a_taxiway_across_its_separators():
    path = "lib/airport/Pavement/Taxiways/Concrete/KBNA_Taxiway-H.pol"
    assert is_library_path(path) and not is_library_path("Taxiway B")
    assert taxi_name_match(path, RULES) == ("taxiway", "H")
    assert taxi_name_match("KBNA_Taxiway-TJL.pol", RULES) == ("taxiway", "TJL")


def _flip(neighbour_role, lot_role="parking_lot", evid=None):
    final = [[neighbour_role, "pav1", box(0, 0, 100, 100), "C", {}, neighbour_role],
             [lot_role, "pav2", box(100, 0, 200, 100), None,
              dict({"kind": "lot"}, **(evid or {})), "lot"]]
    n, _r = airside_edge_flip(final, [], LAW, RULES)
    return n, final[1][0]


def test_section27_writes_the_host_class():
    # owner Q2: a lot touching a taxiway is taxi family, never apron
    assert _flip("junction") == (1, "junction")
    assert _flip("primary_parallel") == (1, "junction")
    # ...a mapped road touching a taxiway stays a road
    assert _flip("junction", "service_road") == (0, "service_road")
    # 12c: an apron edge makes it apron
    assert _flip("apron") == (1, "apron")
    assert _flip("apron", "service_road") == (1, "apron")


def test_a_taxi_hosted_flip_is_no_host_for_the_next_round():
    final = [["junction", "pav1", box(0, 0, 100, 100), "C", {}, "junction"],
             ["parking_lot", "pav2", box(100, 0, 200, 100), None, {"kind": "lot"}, "lot"],
             ["parking_lot", "pav3", box(200, 0, 300, 100), None, {"kind": "lot"}, "lot"]]
    airside_edge_flip(final, [], LAW, RULES)
    assert final[1][0] == "junction" and final[2][0] == "parking_lot"
