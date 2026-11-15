"""#2062 spec R3b: ONE DATUM RULE FOR EVERY STOREY SHELL (A), the floor
level along a shell standing on it (B) and a ground route carried over a
pack deck (E).  Synthetic: no pack, no airport."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport.split_level import SplitLevel
from auto_patch_v2.law import Law
from shapely.geometry import LineString, Polygon, box

LAW = Law.for_airport("SYNT")

#: a 40 x 30 box's runs CLOCKWISE (the building on their right): S, W, N, E
_CW = [((40, 0), (0, 0)), ((0, 0), (0, 30)), ((0, 30), (40, 30)), ((40, 30), (40, 0))]


def _shell(feet=(0.0, 6.0, 0.0, 0.0), levels=(0, 1, 0, 0), air=None) -> SplitLevel:
    runs = tuple((LineString(r), f) for r, f in zip(_CW, feet, strict=True))
    plan = box(0, 0, 40, 30)
    return SplitLevel("w", ("w",), ("objects/x.obj",), plan, 0.0, 6.0, (), (), 0.0, 0.0,
                      (20.0, 15.0), plan, runs, (0.0, 6.0), levels, (),
                      (plan, Polygon()), air)


def _cell(role, ref, poly, kind="structure"):
    return types.SimpleNamespace(role=role, ref=ref, kind=kind), poly


def test_a_shell_on_a_ramp_floor_is_floor_led_and_one_on_a_basin_floor_is_refused():
    """A: no airside, half its lowest level's runs face a ramp-class floor
    -> ``floor``; the same on a basin floor -> refused by name; neither ->
    ``ground``."""
    from auto_patch_v2.planar.storey_floor import FloorCells, floor_scope
    under = box(-20, -12, 60, 0)          # south of the S run, past both ends
    for ref, want in (("tunnel_ramp", "floor"), ("basin_floor:0", "")):
        c, p = _cell("tunnel_ramp" if want else "tunnel_trench", ref, under)
        leader, why = floor_scope(_shell((0.0, 6.0, 6.0, 0.0), (0, 1, 1, 0)),
                                  FloorCells([c], [p]))
        assert leader == want and (bool(why) == (not want))
    assert floor_scope(_shell(), FloorCells([], []))[0] == "ground"


def test_a_ground_led_block_is_its_walls_zero_read_on_the_ground():
    """A: ``datum_z = levels[0] +`` the length-weighted median of (DEM out
    - foot) over the judged groundside runs (110 m at foot 0, 30 m at foot
    6 on a level 100 m ground)."""
    from auto_patch_v2.planar.storey_floor import ground_datum
    assert ground_datum(_shell(), lambda x, y: 100.0, None) == pytest.approx(100.0)


def test_a_shell_block_carries_a_stage_two_datum_column():
    """A: a block that welds no frontage but carries a storey shell's level
    gets its own column (``model/platform._fill_datums``)."""
    from auto_patch_v2.model.platform import datum_vertices
    face = types.SimpleNamespace(id=0, ref="blk", role="building", ring=(1, 2, 3, 4), holes=())
    verts = {i: types.SimpleNamespace(xy=xy, incident_faces=(0,))
             for i, xy in {1: (0, 0), 2: (10, 0), 3: (10, 10), 4: (0, 10)}.items()}
    reg = types.SimpleNamespace(held={"blk": {}}, landings={
        "blk/p1": {"block": "blk", "kind": "upper_level", "y": 5.0, "shell": "w"}})
    pm = types.SimpleNamespace(faces={0: face}, vertices=verts, registries=reg,
                               ring_vertices=lambda r: r)
    assert datum_vertices(pm, LAW, air=set()) == {}
    assert set(datum_vertices(pm, LAW, air=set(), fills=True)) == {"blk"}


def test_the_shell_datum_rows_tie_a_floor_led_block_one_way_and_pin_a_ground_led_one(
        monkeypatch):
    """A: floor -> two one-sided rows ``z_D - z_f = 0`` following D; ground
    -> a pin at ``datum_z``; airside -> nothing."""
    from auto_patch_v2.constraints import shell_datum as SD
    from auto_patch_v2.constraints import structures as ST
    from auto_patch_v2.model import platform as MP
    from auto_patch_v2.model.constraints import Linear, Pin
    monkeypatch.setattr(MP, "datum_vertices", lambda pm, law, air=None, fills=False:
                        {"f": 10, "g": 20, "a": 30})
    monkeypatch.setattr(ST, "datum_group", lambda pm, tn: [7, 8])
    sh = [types.SimpleNamespace(id="s1", pad_ref="f", leader="floor", floor_xy=(0.0, 0.0),
                                datum_z=None),
          types.SimpleNamespace(id="s2", pad_ref="g", leader="ground", floor_xy=None,
                                datum_z=31.5),
          types.SimpleNamespace(id="s3", pad_ref="a", leader="airside", floor_xy=None,
                                datum_z=None)]
    verts = {7: types.SimpleNamespace(xy=(0.0, 1.0)), 8: types.SimpleNamespace(xy=(5.0, 5.0))}
    tn = types.SimpleNamespace(id="t", axis=((0.0, 0.0), (0.0, 50.0)))
    pm = types.SimpleNamespace(storey_shells=sh, structures=(tn,), vertices=verts)
    rows = SD.shell_datum_rows(pm, LAW)
    lin = [r for r in rows if isinstance(r, Linear)]
    assert len(lin) == 2 and all(r.follows == 10 and {v for v, _c in r.terms} == {10, 7}
                                 for r in lin)
    assert [(r.v, r.z) for r in rows if isinstance(r, Pin)] == [(20, 31.5)]
    assert all(r.source.ruling == SD.RULING for r in rows)


def test_the_ramp_stays_level_along_a_shell_on_its_floor_or_refuses_it_by_name():
    """B: the far station of a floor-scope shell's lowest-level runs facing
    the corridor, when their near station lies in the level zone; a shell
    beyond the zone is refused."""
    from auto_patch_v2.planar.storey_floor import shell_level_s
    sl = _shell(feet=(0.0, 6.0, 6.0, 0.0), levels=(0, 1, 1, 0))   # S, E low; W, N up
    axis = LineString([(-10.0, -3.0), (200.0, -3.0)])             # along the S run
    far, why, plans = shell_level_s([sl], "t", axis, 3.0, 0.0, 20.0)
    assert far == pytest.approx(50.0) and not why and len(plans) == 1
    far, why, plans = shell_level_s([sl], "t", axis, 3.0, 0.0, 5.0)
    assert far is None and why and "refused" in why[0]


def test_pavement_on_a_plates_end_band_is_no_class_a_witness():
    """E (master ruling 2026-11-15): pavement only on one end of a plate does
    not run across it; pavement over its mid-span does."""
    from auto_patch_v2.airport.deck_stack import _across
    plate = box(0, 0, 60, 24)
    assert not _across(plate, box(52, 0, 60, 24))
    assert _across(plate, box(10, 0, 50, 24)) and _across(plate, box(25, 0, 35, 24))


def test_a_ground_route_over_a_flag_plate_is_bridged_inside_it_only():
    """E: an apt.dat ground route is a W1 way; over a flag plate the bridge
    stretch is the part inside its plate, every piece keeping the edge's id."""
    from auto_patch_v2.airport.ground_route_ways import bridged, ground_route_ways
    nodes = {1: types.SimpleNamespace(xy=(-20.0, 10.0)), 2: types.SimpleNamespace(xy=(80.0, 10.0))}
    ap = types.SimpleNamespace(taxi_nodes=nodes, ground_routes=(
        types.SimpleNamespace(a=1, b=2, name="", one_way=False),))
    (w,) = ground_route_ways(ap)
    assert w.tags["highway"] == "service"
    parts = bridged([w], box(0, 0, 60, 24))
    assert {p.id for p in parts} == {w.id}
    inside = [p for p in parts if p.tags.get("bridge") == "yes"]
    assert len(inside) == 1 and LineString(inside[0].points).length == pytest.approx(60.0)
