"""``tools/drawn_site_plan.py`` (``drawn_site.py --plan``, #1884 round 2
spec D): a placement plan judged on the drawn mesh by WHAT CARRIES each
body — footed feet against the mesh, riders against their carrier's drawn
zero, group members against their group, own-ground bodies by their base.
Synthetic: a flat 100 m mesh with a 5 m step east of LON + 0.001."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, _TOOLS)

import drawn_site_plan as DP  # noqa: E402

LAT, LON = 47.0, 13.0


class _Mesh:
    def z(self, lat, lon):
        lon = np.asarray(lon, float).reshape(-1)
        return np.where(lon > LON + 0.001, 105.0, 100.0)


def _body(bid, lon, y0, sz, pts, reason, feet=1, elevated=False, res="objects/a__b{}_0a1b2c3d.obj"):
    return {"body_id": bid, "anchor": {"lat": LAT, "lon": lon}, "y_zero": y0, "surface_z": sz,
            "geom_pts": [[LAT, lon, y] for y in pts], "anchor_reason": reason, "feet": feet,
            "elevated": elevated, "merged_into": None, "new_resource": res.format(bid[1:])}


def _plan(tmp_path, bodies, name="p.json", pl_lon=LON):
    p = tmp_path / name
    p.write_text(json.dumps({"splits": [{"placement": {"resource": "objects/a.obj", "index": 7,
                                                       "lat": LAT, "lon": pl_lon},
                                         "bodies": bodies}]}), encoding="utf-8", newline="")
    return str(p)


def _rows(tmp_path, bodies, **kw):
    return {r["key"][2]: r for r in DP.compare(_plan(tmp_path, bodies), _Mesh(), **kw)["rows"]}


def test_footed_bodies_are_judged_by_their_feet(tmp_path):
    rows = _rows(tmp_path, [
        _body("b0", LON, 0.0, 100.0, [0.0, 0.2, 6.0], "surface at the body's zero"),
        _body("b1", LON, -0.8, 100.0, [0.0, 0.1], "one connected group fu:1:5 at 100.80"
              "; was: carried by objects/x.obj")])
    assert rows["b0"]["kind"] == "footed" and rows["b0"]["foot_min"] == 0.0
    assert rows["b0"]["foot_max"] == 0.2                  # 6.0 is no foot (band 0.5)
    assert rows["b1"]["kind"] == "footed" and rows["b1"]["foot_min"] == 0.8   # floats
    s = DP.summary(list(rows.values()))
    assert s["footed_within_ground_bar"] == 1 and len(s["footed_float"]) == 1


def test_a_rider_is_judged_against_its_carrier_not_the_ground(tmp_path):
    """A roof on its walls stands at eave height: no float."""
    rows = _rows(tmp_path, [
        _body("b0", LON, 0.0, 100.0, [0.0], "low-side foot"),
        _body("b1", LON, 0.0, 100.0, [6.5], "carried by objects/a__b0.obj (rests on it)",
              feet=0, elevated=True),
        _body("b2", LON, 0.3, 100.0, [6.5], "carried by objects/a__b0.obj (rests on it)",
              feet=0, elevated=True)])
    assert rows["b1"]["kind"] == "rider" and rows["b1"]["offset"] == 0.0
    assert rows["b2"]["offset"] == -0.3
    assert [r["key"][2] for r in DP.summary(list(rows.values()))["carried_off"]] == ["b2"]


def test_groups_and_own_ground(tmp_path):
    rows = _rows(tmp_path, [
        _body("b0", LON, 0.0, 100.0, [33.6], "footless_carried_by_unit: unit fu:1:263",
              feet=0, elevated=True),
        _body("b1", LON + 0.002, 5.0, 105.0, [33.6], "one connected group fu:1:263 at 100.00",
              feet=0, elevated=True),
        _body("b2", LON, 33.6, 100.0, [33.6, 34.0], "footless_own_ground: base is the "
              "author's terrain", feet=0, elevated=True)])
    assert rows["b0"]["kind"] == rows["b1"]["kind"] == "group"
    assert rows["b0"]["offset"] == rows["b1"]["offset"] == 0.0
    assert rows["b2"]["kind"] == "own_ground" and rows["b2"]["foot_min"] == 0.0
    g = DP.group_seats(list(rows.values()))
    assert g[0]["group"] == "fu:1:263" and g[0]["foot_min"] == 28.6   # the group floats (b1 on the 105 m step)


def test_worse_and_the_rigid_base(tmp_path):
    new = [_body("b0", LON + 0.002, 0.0, 105.0, [0.0], "low-side foot")]
    rep = DP.compare(_plan(tmp_path, new), _Mesh(), base_rigid=True)
    # drawn rigid at its row (LON, 100 m) the foot was 5 m under the 105 m ground
    assert rep["base_summary"]["footed_within_ground_bar"] == 0
    assert rep["summary"]["footed_within_ground_bar"] == 1
    assert rep["worse"] == []
    old = [_body("b0", LON, 0.0, 100.0, [0.0], "low-side foot")]
    bad = [_body("b0", LON, -1.0, 100.0, [0.0], "low-side foot")]
    rep = DP.compare(_plan(tmp_path, bad, "n.json"), _Mesh(),
                     base_plan=_plan(tmp_path, old, "o.json"))
    assert [(r["was"], r["now"]) for r in rep["worse"]] == [(0.0, 1.0)]
    only = DP.compare(_plan(tmp_path, bad, "n2.json"), _Mesh(), only=lambda b: False)
    assert only["rows"] == []
