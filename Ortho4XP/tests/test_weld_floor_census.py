"""Owner RULINGS 2026-10-08d (2): THE CENSUS LEARNS THE PAD WELD FLOOR through
the sidecar's ``platforms[].weld_widened`` (``{"floor_m", "contacts": [[lat,
lon, give]]}``) — a pavement pair NAMING a frontage contact where the
pavement gave to weld is priced at ``cap·d + give``
(``check_grade.weld_widened_nodes``), the generator's inequality
(``constraints/weld_floor``); a pair naming none is priced as before."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_harness import (_PVC_LAT, _PVC_LON, _families, _pavcap_patch,  # noqa: E402,F401
                          _sloped_rect, cg)

ROLE = "groundside_pavement"


def _ll(dx, dy):
    return [_PVC_LAT + dy / 111_320.0,
            _PVC_LON + dx / (111_320.0 * math.cos(math.radians(_PVC_LAT)))]


def _plat(*contacts, floor=1.0, give=1.0):
    return {"platforms": [{"ref": "building1", "weld_widened": {
        "floor_m": floor, "contacts": [[*_ll(*c), give] for c in contacts]}},
        {"ref": "building2", "weld_widened": None}]}


def test_the_contact_nodes_are_joined_by_identity_and_the_give_is_the_contacts(cg):
    nodes = {"n1": tuple(_ll(0.0, 0.0)), "n2": tuple(_ll(10.0, 0.0))}
    assert cg.weld_widened_nodes(nodes, _plat((0.0, 0.0), give=0.4)["platforms"]) == {"n1": 0.4}
    # never more than the record's floor; a contact with no give takes the floor
    assert cg.weld_widened_nodes(nodes, _plat((0.0, 0.0), give=3.0)["platforms"]) == {"n1": 1.0}
    bare = [{"ref": "b", "weld_widened": {"floor_m": 1.0, "contacts": [_ll(10.0, 0.0)]}}]
    assert cg.weld_widened_nodes(nodes, bare) == {"n2": 1.0}
    assert cg.weld_widened_nodes(nodes, None) == {}
    assert cg.weld_widened_nodes(nodes, [{"ref": "b", "weld_widened": None}]) == {}


def test_a_pair_naming_a_frontage_contact_takes_its_give(cg, tmp_path):
    """12 % over 10 m: 1.2 m against ``0.10·10 + 1.0`` at the contacts; the
    same ring with no record, with the contacts elsewhere, or with a give of
    0.05 m (short of the 0.2 m the pair is over) stays priced."""
    ring = [(ROLE, _sloped_rect(0.12), "dsf:pol10")]
    bare = _families(cg, _pavcap_patch(tmp_path, name="bare", rings=ring))
    assert bare["within_shape"] and bare["pavement_over_road_cap"]
    at = _families(cg, _pavcap_patch(tmp_path, name="at", rings=ring,
                                     sidecar=_plat((0.0, 0.0), (0.0, 8.0))))
    assert at["within_shape"] == [] and at["pavement_over_road_cap"] == []
    off = _families(cg, _pavcap_patch(tmp_path, name="off", rings=ring,
                                      sidecar=_plat((500.0, 500.0))))
    assert off["within_shape"] and off["pavement_over_road_cap"]
    small = _families(cg, _pavcap_patch(tmp_path, name="small", rings=ring,
                                        sidecar=_plat((0.0, 0.0), (0.0, 8.0), give=0.05)))
    assert small["within_shape"] and small["pavement_over_road_cap"]


def test_a_pair_beyond_the_floor_stays_priced(cg, tmp_path):
    """25 % over 10 m: 2.5 m against 2.0 m — one floor per pair, never a licence."""
    fo = _families(cg, _pavcap_patch(tmp_path, name="over", sidecar=_plat((0.0, 0.0), (0.0, 8.0)),
                                     rings=[(ROLE, _sloped_rect(0.25), "dsf:pol10")]))
    assert fo["within_shape"] and fo["pavement_over_road_cap"]


def _face(delta_pct, *nodes):
    return {"platforms": [{"ref": "building1", "weld_widened": {
        "floor_m": 1.0, "delta_pct": delta_pct, "faces": ["pav7"], "contacts": [],
        "face_nodes": [_ll(*c) for c in nodes]}}]}


def test_a_pair_on_a_widened_face_is_priced_at_cap_plus_delta(cg):
    """Spec §57 (3) (ii-b): ``weld_widened.{delta_pct, face_nodes}`` — a pair
    whose TWO nodes are vertices of the faces the engine widened (joined by
    identity, never by the ``faces`` refs, which name more faces than the
    closing contacts touch) answers to ``(cap + delta)·d``; a pair with one
    node off them gets nothing."""
    plat = _face(1.1, (0.0, 0.0), (10.0, 0.0))["platforms"]
    nodes = {"n1": tuple(_ll(0.0, 0.0)), "n2": tuple(_ll(10.0, 0.0)), "n3": tuple(_ll(20.0, 0.0))}
    wn = cg.weld_widened_nodes(nodes, plat)
    assert wn and dict(wn) == {} and set(wn.faces) == {"n1", "n2"}
    assert all(abs(v - 0.011) < 1e-12 for v in wn.faces.values())
    assert abs(cg._weld_give(wn, "n1", "n2", 10.0) - 0.11) < 1e-12
    assert cg._weld_give(wn, "n2", "n3", 10.0) == 0.0
    refs_only = [{"ref": "b", "weld_widened": {"floor_m": 1.0, "delta_pct": 1.1,
                                               "faces": ["pav7"], "contacts": []}}]
    assert not cg.weld_widened_nodes(nodes, refs_only)       # a ref is not a face


def test_the_no_step_pair_on_a_widened_face_is_priced_at_cap_plus_delta(cg, tmp_path):
    """``airside_no_step`` §1.1 reads the same record as the three pavement
    families: a published route pair spanning 2.0 m against a budget of
    1.47 m over a 110 m ROUTE is the solve's own row when both ends stand on
    a face widened by 0.5 pp (1.47 + 0.005·110 = 2.02, over the record's
    ``dist_m`` — the distance the row was stated on); it stays priced with
    one end off the face, with 0.4 pp (1.91), and with no record."""
    ring = [("apron", [(0.0, 0.0, 100.0), (100.0, 0.0, 102.0),
                       (100.0, 50.0, 102.0), (0.0, 50.0, 100.0)], "pav7")]
    edge = {"airside_no_step_edges": [
        {"a": _ll(0.0, 0.0), "b": _ll(100.0, 0.0), "budget_m": 1.47, "dist_m": 110.0}]}

    def rows(name, **sidecar):
        fo = _families(cg, _pavcap_patch(tmp_path, name=name, rings=ring,
                                         sidecar={**edge, **sidecar}))
        return [v for v in fo["airside_no_step"] if v.cap_pct is not None]
    assert len(rows("bare")) == 1
    assert rows("on", **_face(0.5, (0.0, 0.0), (100.0, 0.0), (100.0, 50.0))) == []
    assert len(rows("one", **_face(0.5, (0.0, 0.0), (0.0, 50.0))) ) == 1
    assert len(rows("small", **_face(0.4, (0.0, 0.0), (100.0, 0.0)))) == 1
