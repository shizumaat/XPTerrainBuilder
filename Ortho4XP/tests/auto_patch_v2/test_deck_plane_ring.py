"""RULINGS 2026-11-18f (#2157 part A/C): a two-level hard deck's datum ring
is its deck plane (``airport/deck_plane_ring``), and a pack's shipped
Ortho4XP patch reads as a level witness (``airport/pack_patch_witness``)."""
from __future__ import annotations

from auto_patch_v2.airport import deck_plane_ring as DPR
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import pack_patch_witness as W
from auto_patch_v2.law import Law

LAW = Law.for_airport("")


def _quad(x0, z0, x1, z1, y):
    return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]


def _obj(tmp_path, quads, name="t.obj"):
    """An OBJ8 whose every quad is ``ATTR_hard_deck`` (two triangles)."""
    vts, idx = [], []
    for q in quads:
        b = len(vts)
        vts += q
        idx += [b, b + 1, b + 2, b, b + 2, b + 3]
    lines = ["I", "800", "OBJ", "", "TEXTURE t.png",
             f"POINT_COUNTS {len(vts)} 0 0 {len(idx)}"]
    lines += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vts]
    lines += [f"IDX {i}" for i in idx]
    lines += ["ATTR_hard_deck concrete", f"TRIS 0 {len(idx)}"]
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n")
    return str(p)


def test_two_level_deck_reads_its_plane(tmp_path):
    path = _obj(tmp_path, [_quad(0, 0, 40, 30, 6.0), _quad(0, 40, 40, 60, 1.0)])
    dp = DPR.deck_plane(O.ResourceCache(0.3), path, LAW)
    assert dp is not None
    assert dp.y == 6.0 and dp.floor_y == 1.0 and abs(dp.floor_m2 - 800.0) < 1e-6
    zs = {z for r in dp.rings for _x, z in r}
    assert max(zs) <= 30.0          # the floor's faces never enter the plane


def test_one_level_deck_keeps_its_ring(tmp_path):
    # a floor under one storey, and a deep floor too small to count
    near = _obj(tmp_path, [_quad(0, 0, 40, 30, 6.0), _quad(0, 40, 40, 60, 4.0)], "a.obj")
    tiny = _obj(tmp_path, [_quad(0, 0, 40, 30, 6.0), _quad(0, 40, 5, 45, 1.0)], "b.obj")
    cache = O.ResourceCache(0.3)
    assert DPR.deck_plane(cache, near, LAW) is None
    assert DPR.deck_plane(cache, tiny, LAW) is None


PATCH = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6'>
  <node id='-1' lat='0.0' lon='0.0' /><node id='-2' lat='0.0' lon='0.001' />
  <node id='-3' lat='0.001' lon='0.001' /><node id='-4' lat='0.001' lon='0.0' />
  <node id='-5' lat='0.002' lon='0.0' /><node id='-6' lat='0.002' lon='0.001' />
  <way id='-10'><nd ref='-1' /><nd ref='-2' /><nd ref='-3' /><nd ref='-4' /><nd ref='-1' />
    <tag k='altitude' v='114' /></way>
  <way id='-11'><nd ref='-4' /><nd ref='-3' /><nd ref='-6' /><nd ref='-5' /><nd ref='-4' />
    <tag k='altitude_high' v='119' /><tag k='altitude_low' v='114' /></way>
</osm>
"""


def test_pack_patch_pads_and_ramps(tmp_path):
    d = tmp_path / "pack" / "Ortho4XP" / "Patches" / "+00+000" / "+00+000"
    d.mkdir(parents=True)
    (d / "X.patch.osm").write_text(PATCH)
    pads = W.pack_pads(str(tmp_path / "pack"), 0, 0)
    assert len(pads) == 2
    assert W.level_at(pads, 0.0005, 0.0005) == 114.0
    # the ramp: low side nodes[1:3] (lon 0.001), high side nodes[3], nodes[0] (lon 0)
    z = W.level_at(pads, 0.0015, 0.0008)
    assert abs(z - 115.0) < 0.05
    assert W.level_at(pads, 0.01, 0.01) is None
    note = W.deck_note(pads, [(0.0015, 0.0002), (0.0015, 0.0008)],
                       [(-0.0001, -0.0001), (-0.0001, 0.0011), (0.0021, 0.0011), (0.0021, -0.0001)])
    assert "trench floor 114.00" in note
