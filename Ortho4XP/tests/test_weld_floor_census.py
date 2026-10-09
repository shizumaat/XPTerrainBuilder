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


def test_a_pair_on_a_widened_face_is_priced_at_cap_plus_delta(cg):
    """Spec §57 (3) (ii-b): ``weld_widened.{delta_pct, faces}`` — a pair whose
    TWO nodes lie on a listed face (joined by the way's ``ref``) answers to
    ``(cap + delta)·d``; a pair with one node off it gets nothing."""
    class W:
        def __init__(self, ref, nids):
            self.ref, self.nids = ref, nids
    plat = [{"ref": "building1", "weld_widened": {
        "floor_m": 1.0, "delta_pct": 1.1, "faces": ["pav7"], "contacts": []}}]
    nodes = {"n1": tuple(_ll(0.0, 0.0)), "n2": tuple(_ll(10.0, 0.0)), "n3": tuple(_ll(20.0, 0.0))}
    wn = cg.weld_widened_nodes(nodes, plat, [W("pav7", ["n1", "n2"]), W("pav8", ["n2", "n3"])])
    assert wn and dict(wn) == {} and set(wn.faces) == {"n1", "n2"}
    assert all(abs(v - 0.011) < 1e-12 for v in wn.faces.values())
    assert abs(cg._weld_give(wn, "n1", "n2", 10.0) - 0.11) < 1e-12
    assert cg._weld_give(wn, "n2", "n3", 10.0) == 0.0
    assert not cg.weld_widened_nodes(nodes, plat)            # no ways: no face read
