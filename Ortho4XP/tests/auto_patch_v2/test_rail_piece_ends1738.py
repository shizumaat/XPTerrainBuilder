"""Twins for #1738 / #1739 (owner RULINGS 2026-11-03b (6) Q345 a and the
owner's answers of 2026-11-03; spec ``docs/specs/rail-piece-ends-station-
spec.md`` R1-R6).  Synthetic ways and files; law values read from the
tables, never retyped; nothing here names an airport."""
from __future__ import annotations

import struct
from types import SimpleNamespace

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.bore_continuation import continues_underground, tunnel_ends
from auto_patch_v2.planar.end_witness import needs_witness
from auto_patch_v2.planar.structure_approach import _unwitnessed, approach, chains
from shapely.geometry import Polygon

_RAIL_T = {"railway": "rail", "tunnel": "yes", "layer": "-2"}
_SVC_T = {"highway": "service", "tunnel": "yes", "layer": "-1"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _switch():
    through = OsmWay(-1, "big_roads", ((0.0, 0.0), (0.0, 100.0), (0.0, 200.0)), False, _RAIL_T)
    branch = OsmWay(-2, "big_roads", ((10.0, -80.0), (0.0, 100.0)), False, _RAIL_T)
    return through, branch


def test_r1_a_switch_end_on_an_interior_node_goes_on_underground(law):
    """R1: a branch piece ending on the THROUGH piece's interior node (a
    switch) is no portal -- the tunnel goes on underground there."""
    tn = law.tables.structures.tunnel
    ways = list(_switch())
    bore = next(b for b in chains(ways) if -2 in [w.id for w in b.ways])
    end = (0.0, 100.0)
    inward = (0.1, -0.99)
    path = approach(end, inward, ways, 400.0, tn.admitted_values, tn.approach_turn_max_deg)
    why = continues_underground(bore, inward, path, tunnel_ends(ways, tn.admitted_values),
                                law, 400.0)
    assert why is not None and "-1" in why


def test_r1_the_witness_tool_reads_the_same_switch():
    """R1: ``portal_witness.mapped_mouths`` does not call a switch end a mouth."""
    from auto_patch_v2.airport.portal_witness import mapped_mouths
    got = {(xy, wid) for xy, wid, _k in mapped_mouths(SimpleNamespace(osm_ways=list(_switch())))}
    assert ((0.0, 100.0), -2) not in got
    assert ((10.0, -80.0), -2) in got and ((0.0, 0.0), -1) in got


class _Fence:
    def __init__(self, poly):
        self.p = poly

    def covers(self, g):
        return self.p.covers(g)


def _bore(tags):
    return chains([OsmWay(-1, "b", ((0.0, 0.0), (50.0, 0.0)), False, tags)])[0]


def test_r2_rail_deep_and_fenced_service_ends_need_a_witness(law):
    """R2 (b)/(a)/(c): which ends ask for a per-end portal witness."""
    fence = _Fence(Polygon([(-500, -500), (500, -500), (500, 500), (-500, 500)]))
    deep = str(law.tables.structures.tunnel.deep_layer_max)
    assert needs_witness(_bore({"railway": "rail", "tunnel": "yes"}), (0, 0), law, fence) == "rail"
    deep_bore = _bore({"highway": "primary", "tunnel": "yes", "layer": deep})
    assert needs_witness(deep_bore, (0, 0), law, fence, surfaces=False) == "deep"
    assert needs_witness(deep_bore, (0, 0), law, fence) is None   # a road comes out
    assert needs_witness(_bore(_SVC_T), (0.0, 0.0), law, fence) == "service"
    assert needs_witness(_bore(_SVC_T), (900.0, 0.0), law, fence) is None   # outside the fence
    assert needs_witness(_bore({"highway": "primary", "tunnel": "yes", "layer": "-1"}),
                         (0.0, 0.0), law, fence) is None


class _Witness:
    def __init__(self, answer):
        self.answer = answer

    def at(self, end, path):
        return self.answer


def test_r2_an_unwitnessed_rail_end_is_not_opened_and_a_witnessed_one_is(law):
    bore = _bore(_RAIL_T)
    why = _unwitnessed(bore, (0.0, 0.0), [(0.0, 0.0), (-10.0, 0.0)], law, None, _Witness(None))
    assert why is not None and "no portal witness" in why
    assert _unwitnessed(bore, (0.0, 0.0), [], law, None, _Witness("a pack hard deck")) is None


def test_r5_bore_roads_take_rail_only_for_hard_decks(law):
    from auto_patch_v2.planar.structure_underpass import bore_roads
    ap = SimpleNamespace(osm_ways=[
        OsmWay(-1, "b", ((0.0, 0.0), (50.0, 0.0)), False, {"railway": "rail"}),
        OsmWay(-2, "b", ((0.0, 5.0), (50.0, 5.0)), False, {"highway": "service"})])
    assert [w.id for w in bore_roads(ap, law)] == [-2]
    assert sorted(w.id for w in bore_roads(ap, law, rail=True)) == [-2, -1]


def _dsf_header(path, props: dict) -> None:
    body = b"".join(k.encode() + b"\0" + v.encode() + b"\0" for k, v in props.items())
    prop = struct.pack("<4sI", b"PORP", 8 + len(body)) + body
    head = struct.pack("<4sI", b"DAEH", 8 + len(prop)) + prop
    path.write_bytes(b"XPLNEDSF" + struct.pack("<I", 1) + head)


def test_r6_the_screen_reads_overlays_and_our_own_tiles_out(tmp_path):
    from auto_patch_v2.airport.terrain_mesh_witness import _screened
    mesh, ovl, own = tmp_path / "m.dsf", tmp_path / "o.dsf", tmp_path / "t.dsf"
    _dsf_header(mesh, {"sim/creation_agent": "Some Mesh Tool"})
    _dsf_header(ovl, {"sim/overlay": "1"})
    _dsf_header(own, {"sim/creation_agent": "XPTerrainBuilder 1.0.1 (engine 1.0)"})
    (tmp_path / "z.dsf").write_bytes(b"7z\xbc\xaf\x27\x1c")
    assert _screened(str(mesh))
    assert not _screened(str(ovl)) and not _screened(str(own))
    assert not _screened(str(tmp_path / "z.dsf"))


def test_r6_candidates_by_coverage_never_by_name(tmp_path, monkeypatch):
    """R6: the candidate meshes are the enabled packs covering the tile
    (``pack_local.tile_candidates``) whose DSF header screens in."""
    from auto_patch_v2.airport import pack_local, terrain_mesh_witness
    rel = "Earth nav data/+10+020/+10+020.dsf"
    roots = {}
    for name, props in (("a mesh", {"sim/creation_agent": "Mesh Tool"}),
                        ("an overlay", {"sim/overlay": "1"})):
        p = tmp_path / name / rel
        p.parent.mkdir(parents=True)
        _dsf_header(p, props)
        roots[name] = str(tmp_path / name)
    monkeypatch.setattr(pack_local, "tile_candidates", lambda main, lat, lon: sorted(roots.values()))
    assert terrain_mesh_witness.dump_candidates(str(tmp_path / "main"), 10, 20) == [roots["a mesh"]]


def _tri(lines, pts):
    lines.append("BEGIN_PRIMITIVE 0")
    for x, y, z in pts:
        lines.append(f"PATCH_VERTEX {x} {y} {z} 0 0")
    lines.append("END_PRIMITIVE")


def test_r6_read_cuts_finds_a_trench_under_a_flat_field():
    """A flat field with a narrow 10 m-deep slot: one cut, its depth under
    the field; the field triangles are no cut."""
    from auto_patch_v2.airport.terrain_mesh_witness import _read_cuts
    f = 100.0
    lines = ["PROPERTY sim/creation_agent Some Mesh Tool", "BEGIN_PATCH 0 0 -1 1 5"]
    for t in (((0, 0, f), (1, 0, f), (1, 1, f)), ((0, 0, f), (1, 1, f), (0, 1, f))):
        _tri(lines, [(x * 0.01, y * 0.01, z) for x, y, z in t])
    s = [(0.0045, 0.002, f - 10), (0.0055, 0.002, f - 10), (0.0055, 0.008, f - 10),
         (0.0045, 0.008, f - 10)]
    _tri(lines, [s[0], s[1], s[2]])
    _tri(lines, [s[0], s[2], s[3]])
    lines.append("END_PATCH")

    def enter(lon, lat):
        return (lon * 10000.0, lat * 10000.0)
    boundary = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    field, cuts = _read_cuts(lines, None, boundary, enter, (0.0, 0.0, 0.01, 0.01), 2.0)
    assert field == f
    assert len(cuts) == 1 and cuts[0].depth_m == pytest.approx(10.0)


def test_r6_our_own_dsf_is_never_a_witness():
    from auto_patch_v2.airport.terrain_mesh_witness import _read_cuts
    lines = ["PROPERTY sim/creation_agent Ortho4XP 1.3", "BEGIN_PATCH 0 0 -1 1 5", "END_PATCH"]
    assert _read_cuts(lines, None, Polygon([(0, 0), (1, 0), (1, 1)]), lambda a, b: (a, b),
                     (0, 0, 1, 1), 2.0) is None


def test_r3_station_corridors_take_every_railway_and_keep_to_the_parts(law):
    from auto_patch_v2.planar.covered_cut import _keep_to_parts, station_corridors
    ap = SimpleNamespace(osm_ways=[
        OsmWay(-1, "b", ((0.0, 0.0), (0.0, 300.0)), False, _RAIL_T),
        OsmWay(-2, "b", ((0.0, -200.0), (0.0, 0.0)), False, {"railway": "rail"})])
    allc = station_corridors(ap, law)
    openc = station_corridors(ap, law, open_only=True)
    assert allc.bounds[1] == pytest.approx(-200.0) and allc.bounds[3] == pytest.approx(300.0)
    assert openc.bounds[3] == pytest.approx(0.0)
    # the station's parts stand over y 0..40: the deep tunnel north of them is
    # not in the level; the open rail joined to them inside the pad is
    station = Polygon([(-10, 0), (10, 0), (10, 40), (-10, 40)])
    pad = Polygon([(-30, -100), (30, -100), (30, 250), (-30, 250)])
    kept = _keep_to_parts(allc.intersection(pad), [(None, station)], openc, 5.0)
    assert kept.bounds[3] <= 45.0 + 1e-6 and kept.bounds[1] == pytest.approx(-100.0)
