"""THE LOWER LEVEL SPANS ITS GROUP'S LOWER FOOTPRINT (#1306, #1302; owner
RULINGS 2026-10-27h, ``planar/low_extent``).

A two-level block whose unit's lower storey runs on PAST the held pad:
the lower level extends over it, at the bottom of the objects standing
there, beside the pad behind a riser; airside never takes it.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import low_level as LL
from auto_patch_v2.planar.low_extent import AirRegion
from auto_patch_v2.planar.overlay import Region
from shapely.geometry import box
from test_two_pads1214 import AIR, P, _airport, _terminal, _wall


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _split(law, parts, tmp_path, monkeypatch, air=(AIR,)):
    from auto_patch_v2.airport.obj8_grade import STEPPED
    from auto_patch_v2.planar import pad_blocks
    monkeypatch.setattr(pad_blocks, "unit_base", lambda P, a: (STEPPED, "u"))
    A = _airport(parts, tmp_path)
    reg = Registries()
    reg.held["blk"] = {"unit": "blk"}
    region = Region(role="building", ref="blk", polygon=P, code_number=None,
                    code_letter=None, side="airside", source="cell")
    counts: dict = {}
    out = LL.low_level_split([region], [AIR], A, law, 0.5, counts, reg=reg,
                             air_all=[AirRegion(g, "cell") for g in air])
    return out, reg, counts


def test_the_lower_storey_past_the_pad_is_the_lower_level_at_its_own_bottom(
        law, tmp_path, monkeypatch):
    # the unit's lower storey runs 80 m on east of the held pad, 0.8 m
    # lower than under the pad (its own bottom, -9.0)
    east = [_wall(205.0, 0.0, 285.0, 70.0, -9.0, 200)]
    out, reg, counts = _split(law, _terminal() + east, tmp_path, monkeypatch)
    ext = {k: v for k, v in reg.landings.items() if v.get("extent_of")}
    assert len(ext) == 1
    (ref, rec), = ext.items()
    assert rec["kind"] == LL.LOW_KIND and rec["extent_of"] == "blk/p1"
    assert rec["y_feet"] == pytest.approx(-9.0)
    assert rec["y_lo"] == pytest.approx(-9.0 + 5.8)
    g = next(r.polygon for r in out if r.ref == ref)
    assert g.area > 0.9 * 80.0 * 70.0 - 600.0
    assert g.distance(P) > 0.0                        # a riser off the pad
    assert any(r.ref == ref + "#strip" for r in out)
    assert counts["low_level_extents"] == 1


def test_the_extension_never_takes_airside(law, tmp_path, monkeypatch):
    east = [_wall(205.0, 0.0, 285.0, 70.0, -9.0, 200)]
    apron = box(240.0, -10.0, 300.0, 80.0)
    out, reg, _c = _split(law, _terminal() + east, tmp_path, monkeypatch, air=(AIR, apron))
    ext = [r.polygon for r in out if reg.landings.get(str(r.ref), {}).get("extent_of")]
    assert ext and all(g.distance(apron) >= 3.0 - 1e-6 for g in ext)


def test_a_part_at_the_upper_floor_extends_nothing(law, tmp_path, monkeypatch):
    east = [_wall(205.0, 0.0, 285.0, 70.0, -5.8, 200)]
    _out, reg, _c = _split(law, _terminal() + east, tmp_path, monkeypatch)
    assert not any(v.get("extent_of") for v in reg.landings.values())


def test_no_lower_level_no_extension(law, tmp_path, monkeypatch):
    parts = [p for p in _terminal() if p.base_y > -8.0]
    parts.append(_wall(205.0, 0.0, 285.0, 70.0, -8.2, 200))
    _out, reg, _c = _split(law, parts, tmp_path, monkeypatch)
    assert not any(v.get("kind") == LL.LOW_KIND for v in reg.landings.values())




def test_no_row_spans_two_lower_levels_at_two_floors():
    """27h: the extension stands at the objects' bottom, a riser off the
    level it extends; a road row naming both is withdrawn like one across
    a level's own riser (``constraints/riser``)."""
    import types

    from auto_patch_v2.constraints import riser
    from auto_patch_v2.model.constraints import Diff, Source

    def face(i, ref, role, ring):
        return types.SimpleNamespace(id=i, ref=ref, role=role, ring=ring, holes=())
    faces = {0: face(0, "b", "building", (1, 2)), 1: face(1, "b/p1", "building", (3, 4)),
             2: face(2, "b/p2", "building", (6, 7)), 3: face(3, "b/p1#strip", "building", (2, 3)),
             4: face(4, "r", "service_road", (4, 5, 6))}
    pm = types.SimpleNamespace(
        faces=faces, registries=types.SimpleNamespace(landings={
            "b/p1": {"block": "b", "kind": "low_level", "y_lo": -13.0},
            "b/p2": {"block": "b", "kind": "low_level", "y_lo": -11.5}}),
        ring_vertices=lambda ring: ring)
    src = Source("g", "r")
    rows = [Diff(4, 6, 0.01, 1.0, src),            # level to level: withdrawn
            Diff(6, 7, 0.01, 1.0, src),            # inside the extension: kept
            Diff(4, 5, 0.01, 1.0, src)]            # level to the road off it: kept
    counts: dict = {}
    assert riser.riser_exempt(rows, pm, counts) == rows[1:]
    assert counts["riser_rows_withdrawn"] == 1


def test_a_retaining_wall_takes_the_level_along_its_lower_side_at_its_foot(
        law, tmp_path, monkeypatch):
    """KATL east terminal (#1306): an apron wall runs on from the terminal;
    the lower level follows it to its end on its LOW side, at the wall's
    own foot ("the bottom of the retaining wall"), never on the apron side."""
    import types

    from auto_patch_v2.airport.obj8_grade import STEPPED
    from auto_patch_v2.planar import pad_blocks
    monkeypatch.setattr(pad_blocks, "unit_base", lambda P, a: (STEPPED, "u"))
    wall = _wall(200.0, -200.0, 200.8, 0.5, -11.5, 4)
    wall.height_m, wall.comp = 12.0, 0
    ground = lambda x, y: 288.0 if x > 201.0 and y < 0.0 else 300.0   # noqa: E731
    A = _airport(_terminal(), tmp_path, ground)
    A.partition.units.append(types.SimpleNamespace(members=[types.SimpleNamespace(
        parts=[wall], resource="muro.obj", id="m1")]))
    apron = box(0.0, -200.0, 200.0, 0.0)              # the apron the wall retains
    reg = Registries()
    reg.held["blk"] = {"unit": "blk"}
    region = Region(role="building", ref="blk", polygon=P, code_number=None,
                    code_letter=None, side="airside", source="cell")
    out = LL.low_level_split([region], [AIR], A, law, 0.5, {}, reg=reg,
                             air_all=[AirRegion(AIR, "cell"), AirRegion(apron, "cell")])
    ext = {k: v for k, v in reg.landings.items() if v.get("extent_of")}
    assert ext, reg.landings
    (ref, rec), = ext.items()
    assert rec["y_feet"] == pytest.approx(-11.5)
    g = next(r.polygon for r in out if r.ref == ref)
    assert g.bounds[1] < -195.0                          # to the wall's end
    assert g.intersection(box(150.0, -200.0, 200.8, 0.0)).area == 0.0   # never the apron side
    assert g.intersection(box(203.0, -195.0, 240.0, -5.0)).area > 0.9 * 37.0 * 190.0
    assert g.distance(apron) >= 3.0 - 1e-6


def test_a_group_levels_vertices_are_stage_twos_but_airside_pavement_s():
    """#1302: stage 1 levelled the trench pad whole; where its group level
    reaches the pad's own ring, those ring vertices are released from the
    stage-1 constants -- never a vertex an airside pavement face carries."""
    import types

    from auto_patch_v2.constraints.group_level import stage_two_vertices

    def face(ref, role, side, ring):
        return types.SimpleNamespace(ref=ref, role=role, side=side, ring=ring, holes=())
    pm = types.SimpleNamespace(faces={0: face("b/p1", "building", "airside", (1, 2, 3)),
                                      1: face("apron", "apron", "airside", (3, 4)),
                                      2: face("lot", "parking_lot", "groundside", (1, 5))},
                               ring_vertices=lambda ring: ring)
    assert stage_two_vertices(pm, {"b/p1": {}}) == frozenset({1, 2})
