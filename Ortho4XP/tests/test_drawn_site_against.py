"""``drawn_site.py --clearance-only --against CTL.json`` (#2060 round 3):
a row whose file and ``lowest_z`` equal the control's is UNMOVED and never
counted worse — HECA's sign row 5933 read 0.16 -> 1.86 m across three
rounds with its file, its lowest point and its carrier's frame identical;
only the probe point moved."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "tools"))

import drawn_site_against as DA  # noqa: E402


def _rep(*rows):
    return {"sites": [{"placements": [
        dict(tile="+30+031", row=r, **{"def": d}, clearance_m=c, lowest_z=z,
             on_object=True) for r, d, c, z in rows]}]}


CTL = _rep((5933, "A/T3_sign_2__b1_110ef48f.obj", 0.16, 105.88),
           (5247, "A/building__b44_10e43c36.obj", 0.89, 81.68),
           (4140, "A/grass__b1_e36c235e.obj", -0.38, 68.68),
           (3929, "A/metal_strip_2__b21_7d9f0fc8.obj", 1.94, 101.73))


def test_a_row_whose_file_and_lowest_point_hold_is_unmoved_never_worse(capsys):
    new = _rep((5933, "A/T3_sign_2__b1_110ef48f.obj", 1.86, 105.88),   # probe moved
               (5247, "A/building__b44_60e77233.obj", 0.0, 81.70),     # took its carrier's tilt
               (4140, "A/grass__b1_5af76511.obj", -0.63, 68.43),       # rotated: worse
               (3929, "A/metal_strip_2__b21_7d9f0fc8.obj", 1.94, 101.73))
    res = DA.compare(CTL, new)
    by = {c["row"]: c for c in res["changed"]}
    assert set(by) == {5933, 5247, 4140}
    assert by[5933]["status"] == "UNMOVED" and not by[5933]["worse"]
    assert by[5247]["status"] == "MOVED" and not by[5247]["worse"]
    assert by[4140]["status"] == "MOVED" and by[4140]["worse"]
    assert res["worse"] == 1 and res["unmoved"] == 1
    DA.print_against(res)
    out = capsys.readouterr().out
    assert "UNMOVED" in out and "worse by > 0.1 m: 1" in out


def test_split_bodies_are_matched_by_row_and_stem_not_hash():
    new = _rep((5247, "A/building__b44_60e77233.obj", 0.89, 81.68))
    res = DA.compare(_rep((5247, "A/building__b44_10e43c36.obj", 0.89, 81.68)), new)
    assert res["only_ctl"] == res["only_new"] == 0
    assert [c["status"] for c in res["changed"]] == ["MOVED"]


def test_a_row_two_sites_list_keeps_the_reading_with_a_clearance():
    """CYLW's H9 row 4820 lies in H8's 105 m search too, unread there."""
    def two(c):
        rep = _rep((4820, "A/Hangar_9__b0_2a6929cd.obj", c, 418.35))
        rep["sites"].append({"placements": [dict(tile="+30+031", row=4820,
                             **{"def": "A/Hangar_9__b0_2a6929cd.obj"}, clearance_m=None,
                             lowest_z=None, on_object=None)]})
        return rep
    res = DA.compare(two(1.13), two(0.13))
    assert [(c["clearance_ctl"], c["clearance_new"]) for c in res["changed"]] == [(1.13, 0.13)]
