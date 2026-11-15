"""#2090: two .agp rows whose connector floors meet seat as one group
(``airport/agp_ground``, ``airport/agp_pieces``); the DSF row points at the
lifted copy and stays on the ground; ``tools/drawn_agp`` judges the joint
on the drawn datums.  Synthetic: two decks running into two ramps, as KDEN's
Concourse A sky bridge runs into the Jeppesen terminal."""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE / "tools"))

from auto_patch_v2.airport import agp_ground as AG  # noqa: E402
from auto_patch_v2.airport import agp_pieces as AP  # noqa: E402
from auto_patch_v2.airport import dsf_write as W  # noqa: E402
from auto_patch_v2.model.placement import CUT_MARK, AgpSeat, PlacementPlan, Provenance  # noqa: E402

LAT, LON = 39.0, -104.0
#: b's row stands 100 m north of a's
DLAT = 100.0 / 111_000.0


def _floor(y, n0, n1, e0=-5.0, e1=5.0):
    """One up-facing quad (X-Plane's clockwise front face) at ``y`` from
    north ``n0`` to ``n1`` (OBJ z = -north)."""
    return [(e0, y, -n1), (e1, y, -n1), (e1, y, -n0), (e0, y, -n0)]


def _obj(path: Path, quads) -> None:
    pts = [v for q in quads for v in q]
    vt = "".join(f"VT {x} {y} {z} 0 1 0 0 0\n" for x, y, z in pts)
    idx = []
    for k in range(len(quads)):
        b = 4 * k
        idx += [b, b + 1, b + 2, b, b + 2, b + 3]
    path.write_text(f"I\n800\nOBJ\n\nTEXTURE x.png\nPOINT_COUNTS {len(pts)} 0 0 {len(idx)}\n"
                    f"{vt}" + "".join(f"IDX {i}\n" for i in idx) + f"TRIS 0 {len(idx)}\n",
                    encoding="utf-8", newline="\n")


AGP = """A
1000
AG_POINT
TEXTURE_SCALE 4096.0 4096.0
TEXTURE_WIDTH 1000.0
TILE 0 0 4096 4096
ANCHOR_PT 2048 2048
GROUND_PT 2048 2048
OBJECT {obj}
OBJ_DELTA 2048 2048 0 0.0 0
"""


def _pack(tmp_path: Path):
    d = tmp_path / "Objects"
    d.mkdir(exist_ok=True)
    # a: a two-deck bridge north to n = 20 (decks 11.5 and 16.0 over a's datum)
    _obj(d / "a.obj", [_floor(11.5, 0, 20), _floor(16.0, 0, 20), _floor(0.0, -30, 0)])
    # b (its row 100 m north): two ramps topping out at 20.5 / 25.0 at n = -80
    _obj(d / "b.obj", [_floor(20.5, -81, -79.5), _floor(25.0, -81, -79.5),
                       _floor(1.0, -60, 0)])
    (d / "a.agp").write_text(AGP.format(obj="a.obj"), encoding="utf-8", newline="\n")
    (d / "b.agp").write_text(AGP.format(obj="b.obj"), encoding="utf-8", newline="\n")
    rows = (types.SimpleNamespace(def_path="Objects/a.agp", lon=LON, lat=LAT,
                                  heading_deg=0.0, kind="OBJECT", elevation=None),
            types.SimpleNamespace(def_path="Objects/b.agp", lon=LON, lat=LAT + DLAT,
                                  heading_deg=0.0, kind="OBJECT", elevation=None))
    return str(tmp_path), types.SimpleNamespace(placements=rows)


def _surface(b_ground: float):
    """a's ground point on a graded building pad (100.0), b's on ungraded
    ground at ``b_ground``."""
    def z(lat, lon):
        return 100.0 if lat < LAT + DLAT / 2 else b_ground
    z.roles = types.SimpleNamespace(roles_many=lambda lats, lons: [
        "building" if la < LAT + DLAT / 2 else None for la in lats])
    z.rolled_on = frozenset({"apron"})
    return z


def test_pieces_stand_where_the_agp_puts_them(tmp_path):
    root, _dump = _pack(tmp_path)
    agp = AP.read_agp(os.path.join(root, "Objects", "a.agp"))
    assert agp.mpp == pytest.approx((1000 / 4096, 1000 / 4096)) and agp.other == ()
    (pc,) = AP.placed_pieces(agp, LON, LAT, 0.0)
    assert (pc.lon, pc.lat, pc.height) == pytest.approx((LON, LAT, 0.0))
    assert AP.ground_point(agp, LON, LAT, 30.0) == pytest.approx((LON, LAT))
    text = AP.lifted_text(AGP.format(obj="a.obj"), 3.5, "# note")
    assert "OBJ_DELTA 2048 2048 0 3.50000000 0" in text
    assert text.splitlines()[3] == "# note"


def test_the_decks_meet_the_ramps_and_the_follower_is_lifted(tmp_path):
    root, dump = _pack(tmp_path)
    members = AG.candidates(dump, root)
    (((i, j), jn),) = AG.joins(members).items()
    assert (i, j) == (0, 1)
    assert jn.step == pytest.approx(-9.0)          # 11.5 meets 20.5, 16.0 meets 25.0
    assert jn.lat == pytest.approx(LAT + 19.75 / 111_000, abs=2e-5)
    seats, files, counts = AG.plan_lifts(dump, root, _surface(87.0), members)
    (s,) = seats
    assert (s.index, s.governor, s.resource) == (1, 0, "Objects/b.agp")
    assert s.lift_m == pytest.approx(4.0)          # 100 - 9 = 91 over ground 87
    assert s.new_resource.startswith("Objects/b__g_") and s.new_resource.endswith(".agp")
    assert files[0].resource == s.new_resource and CUT_MARK in files[0].text
    assert "OBJ_DELTA 2048 2048 0 4.00000000 0" in files[0].text
    assert counts["agp_lifted"] == 1 and counts["agp_joins"] == 1


def test_nothing_is_written_when_the_floors_meet_or_no_member_governs(tmp_path):
    root, dump = _pack(tmp_path)
    assert AG.plan_lifts(dump, root, _surface(91.0))[0] == ()
    assert AG.plan_lifts(dump, root, lambda la, lo: 90.0)[0] == ()  # no graded face


def test_low_floors_never_join(tmp_path):
    root, dump = _pack(tmp_path)
    _obj(Path(root) / "Objects" / "a.obj", [_floor(1.5, 0, 20)])
    _obj(Path(root) / "Objects" / "b.obj", [_floor(1.0, -81, -79.5)])
    assert AG.joins(AG.candidates(dump, root)) == {}


# ── the plan record and the DSF edit ─────────────────────────────────────

SEAT = AgpSeat(1, "Objects/b.agp", "Objects/b__g_00000000.agp", 4.0, 0,
               LON, LAT + DLAT, 87.0, 91.0)


def _plan(tmp_path: Path, **kw) -> PlacementPlan:
    d = dict(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
             dsf_path=str(tmp_path / "t.dsf"),
             dsf_backup_path=str(tmp_path / "t.dsf.anchor_bak"),
             provenance=Provenance("sha", "1.0", "digest"))
    d.update(kw)
    return PlacementPlan(**d)


def test_plan_record_round_trips_and_is_absent_when_empty(tmp_path):
    p = _plan(tmp_path, agp_seats=(SEAT,))
    assert PlacementPlan.from_dict(json.loads(p.to_json())).agp_seats == (SEAT,)
    assert PlacementPlan.from_dict(p.edit_rows()).agp_seats == (SEAT,)
    assert p.new_agps() == (SEAT.new_resource,) and p.counts()["agp_seats"] == 1
    empty = _plan(tmp_path)
    assert "agp_seats" not in empty.to_dict() and "agp_seats" not in empty.counts()
    assert p.compose([_plan(tmp_path, agp_seats=(SEAT,))]).agp_seats == (SEAT,)


DUMP = """A
800 written by DSFTool 2.4.0-b1
DSF2TEXT

PROPERTY sim/west -105
PROPERTY sim/east -104
PROPERTY sim/north 40
PROPERTY sim/south 39
PROPERTY sim/planet earth
PROPERTY sim/creation_agent test
PROPERTY sim/overlay 1
OBJECT_DEF Objects/a.agp
OBJECT_DEF Objects/b.agp
OBJECT 0 -104.000000000 39.000000000 0.000000
OBJECT 1 -104.000000000 39.000900901 0.000000
"""


def test_edit_dump_points_the_row_at_its_copy_on_the_ground(tmp_path):
    out = W.edit_dump(DUMP, _plan(tmp_path, agp_seats=(SEAT,)), "t").splitlines()
    assert out.index("OBJECT_DEF Objects/b__g_00000000.agp") == out.index(
        "OBJECT_DEF Objects/b.agp") + 1
    assert "OBJECT 2 -104.000000000 39.000900901 0.000000" in out
    assert "OBJECT 0 -104.000000000 39.000000000 0.000000" in out
    bad = AgpSeat(1, "Objects/x.agp", "Objects/x__g.agp", 1.0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        W.edit_dump(DUMP, _plan(tmp_path, agp_seats=(bad,)), "t")


def test_drawn_join_misfit(tmp_path):
    from drawn_agp import join_rows
    root, dump = _pack(tmp_path)
    (r,) = join_rows(dump, root, lambda lon, lat: 100.0 if lat < LAT + DLAT / 2 else 87.0)
    assert r["verdict"] == "FAIL" and r["delta"] == pytest.approx(-4.0)
    (r,) = join_rows(dump, root, lambda lon, lat: 100.0 if lat < LAT + DLAT / 2 else 91.0)
    assert r["verdict"] == "PASS" and r["delta"] == pytest.approx(0.0)


def test_a_member_on_graded_ground_never_moves(tmp_path):
    root, dump = _pack(tmp_path)
    both = _surface(87.0)
    both.roles = types.SimpleNamespace(roles_many=lambda lats, lons: ["apron"] * len(lats))
    assert AG.plan_lifts(dump, root, both)[0] == ()


def test_drawn_site_reads_an_agp_row_as_its_pieces(tmp_path):
    from drawn_site_agp import pack_dir, pieces
    root, dump = _pack(tmp_path)
    row = types.SimpleNamespace(def_path="Objects/b.agp", lon=LON, lat=LAT + DLAT,
                                heading_deg=0.0, kind="OBJECT", elevation=None)
    ((pc, where),) = pieces(row, root, None)
    assert (pc.def_path, pc.kind, pc.elevation) == ("b.obj", "OBJECT_AGL", 0.0)
    assert where == os.path.join(root, "Objects")
    assert (pc.ground_lat, pc.ground_lon) == pytest.approx((LAT + DLAT, LON))
    assert pieces(types.SimpleNamespace(def_path="x.obj", kind="OBJECT"), root, None) == []
    assert pack_dir("Objects", root) == os.path.join(root, "Objects")
    assert pack_dir(root, "/nowhere") == root


# ── spec 2090 C1 V2 / A6 ──────────────────────────────────────────────────

def test_v2_two_pairs_join_one_nonzero_pair_does_not_one_flat_pair_does():
    law = AG._LAW
    # KDEN's shape: two distinct level pairs vote one step
    assert AG._vote({(11.48, 20.50), (15.98, 25.00)}, law)[3] is True
    # one pair at +1.60 (KEWR's refused join): no join
    step, n, rival, stands = AG._vote({(3.10, 1.50)}, law)
    assert (round(step, 2), n, rival, stands) == (1.6, 1, 0, False)
    # one pair at 0.00 is enough
    assert AG._vote({(4.00, 4.00)}, law)[3] is True
    # a tie is no join
    assert AG._vote({(1.0, 0.0), (5.0, 2.0)}, law)[3] is False


def test_a_refused_join_is_listed_never_lifted(tmp_path):
    root, dump = _pack(tmp_path)
    # one deck meets one ramp: a single non-zero pair
    _obj(Path(root) / "Objects" / "a.obj", [_floor(11.5, 0, 20), _floor(0.0, -30, 0)])
    _obj(Path(root) / "Objects" / "b.obj", [_floor(20.5, -81, -79.5), _floor(1.0, -60, 0)])
    refused: dict = {}
    assert AG.joins(AG.candidates(dump, root), refused=refused) == {}
    ((_k, jn),) = refused.items()
    assert jn.step == pytest.approx(-9.0) and (jn.votes, jn.stands) == (1, False)


def _published(datum_b: float, **member_b):
    return ({"id": "agp:dsf:obj0", "governor": "dsf:obj0", "z_gov": 100.0, "delta": 0.2,
             "members": [{"row": "dsf:obj0", "index": 0, "resource": "Objects/a.agp",
                          "datum": 100.0, "airside": True},
                         {"row": "dsf:obj1", "index": 1, "resource": "Objects/b.agp",
                          "datum": datum_b, **member_b}],
             "joins": [{"a": "dsf:obj0", "b": "dsf:obj1", "step": -9.0}]},)


def test_the_published_datum_overrides_the_drawn_derivation(tmp_path):
    root, dump = _pack(tmp_path)
    # the drawn derivation would ask 91 (governor 100 - 9); the published 90.8
    seats, _files, counts = AG.plan_lifts(dump, root, _surface(87.0),
                                          published=_published(90.8))
    (s,) = seats
    assert s.need_z == pytest.approx(90.8) and s.lift_m == pytest.approx(3.8)
    assert counts["agp_governor_drawn_off_m"] == pytest.approx(0.0)
    assert s.gp_relief_m == pytest.approx(0.0)


def test_a_follower_on_a_graded_plate_is_still_lifted(tmp_path):
    root, dump = _pack(tmp_path)

    def z(lat, lon):
        return 100.0 if lat < LAT + DLAT / 2 else 89.0
    # both ground points stand on graded faces (the follower on its plate)
    z.roles = types.SimpleNamespace(roles_many=lambda lats, lons: ["building"] * len(lats))
    z.rolled_on = frozenset({"apron"})
    assert AG.plan_lifts(dump, root, z)[0] == ()               # fallback: never moved
    (s,) = AG.plan_lifts(dump, root, z, published=_published(90.8))[0]
    assert s.lift_m == pytest.approx(1.8)


def test_a7_stage1_airside_and_strip_riders_never_move(tmp_path):
    root, dump = _pack(tmp_path)
    surf = _surface(87.0)
    assert AG.plan_lifts(dump, root, surf, published=_published(90.8, stage1=True))[0] == ()
    assert AG.plan_lifts(dump, root, surf, published=_published(90.8, airside=True))[0] == ()
    assert AG.plan_lifts(dump, root, surf, published=_published(90.8), riders={1})[0] == ()
    # a published empty key lifts nothing and reads no floor
    assert AG.plan_lifts(dump, root, surf, published=())[0] == ()
