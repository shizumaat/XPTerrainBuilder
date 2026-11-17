"""#2144 P2: A DECK TOUCHING TWO BUILDINGS AT TWO LEVELS IS WARPED, NOT
STEPPED (``airport/obj8_warp`` + ``obj8_split.BodyCut.warp``).

Synthetic and hermetic: a hand-built OBJ8 deck between two building boxes,
cut and read back through the engine's own reader.
"""
from __future__ import annotations

import numpy as np
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_split as OS
from auto_patch_v2.airport import obj8_warp as OW


def _write(path, verts, tris, anim: bool = False) -> str:
    idx = [q for t in tris for q in t]
    cmds = []
    if anim:
        cmds += ["ANIM_begin", "ANIM_trans\t0 0 0\t0 0 0\t0 1\tsim/none"]
    cmds.append(f"TRIS\t0 {len(idx)}")
    if anim:
        cmds.append("ANIM_end")
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.5 0.5" for x, y, z in verts]
    out += [f"IDX\t{q}" for q in idx]
    out += [""] + cmds
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return str(path)


def _deck(tmp_path, anim: bool = False) -> str:
    """A 100 m deck at y 6 along x, 4 m wide, cut every 10 m."""
    v, t = [], []
    xs = np.arange(-50.0, 50.01, 10.0)
    for x in xs:
        v += [(float(x), 6.0, 0.0), (float(x), 6.0, 4.0)]
    for k in range(len(xs) - 1):
        a = 2 * k
        t += [(a, a + 3, a + 2), (a, a + 1, a + 3)]
    return _write(tmp_path / ("deck_a.obj" if anim else "deck.obj"), v, t, anim)


def _box(x0, x1):
    return ((x0, -5.0), (x1, -5.0), (x1, 9.0), (x0, 9.0))


#: building A covers x <= -40 at D 0; building B covers x >= 40, 0.4 m
#: lower (a 0.4 m step over 80 m: 0.5 %)
NODES = ((0.0, (_box(-60.0, -40.0),)), (-0.4, (_box(40.0, 60.0),)))


def _ys(text: str) -> dict:
    out = {}
    for ln in text.splitlines():
        if ln.startswith("VT"):
            x, y, _z = (float(q) for q in ln.split()[1:4])
            out[round(x, 2)] = y
    return out


def test_field_is_exact_inside_each_node_and_straight_between():
    f = OW.Field(NODES)
    d = f.at(np.asarray([-50.0, -40.0, 0.0, 40.0, 50.0]), np.zeros(5))
    assert abs(d[0]) < 1e-9 and abs(d[1]) < 1e-9
    assert abs(d[3] + 0.4) < 1e-9 and abs(d[4] + 0.4) < 1e-9
    assert abs(d[2] + 0.2) < 1e-6          # the midpoint of two nodes
    gx, _gz = f.grad(np.asarray([0.0]), np.asarray([0.0]))
    assert abs(gx[0] + 0.4 / 80.0) < 1e-3


def test_a_warped_deck_lands_on_both_buildings_within_a_centimetre(tmp_path):
    path = _deck(tmp_path)
    comps = tuple(range(len(obj8.solid_components(obj8.parse_obj8(path)))))
    res = OS.split_obj8(path, [OS.BodyCut(0, comps, warp=NODES)], "objects/deck.obj",
                        allow_single=True)
    assert len(res.files) == 1 and res.files[0].warped
    ys = _ys(res.files[0].text)
    assert abs(ys[-50.0] - 6.0) < 0.01 and abs(ys[-40.0] - 6.0) < 0.01
    assert abs(ys[50.0] - 5.6) < 0.01 and abs(ys[40.0] - 5.6) < 0.01
    assert 5.6 < ys[0.0] < 6.0
    # x and z never move
    assert sorted(ys) == [round(float(x), 2) for x in np.arange(-50.0, 50.01, 10.0)]


def test_no_warp_writes_the_same_bytes(tmp_path):
    path = _deck(tmp_path)
    comps = tuple(range(len(obj8.solid_components(obj8.parse_obj8(path)))))
    a = OS.split_obj8(path, [OS.BodyCut(0, comps, (1.0, 2.0, 3.0))], "objects/deck.obj",
                      allow_single=True)
    b = OS.split_obj8(path, [OS.BodyCut(0, comps, (1.0, 2.0, 3.0), warp=())],
                      "objects/deck.obj", allow_single=True)
    assert a.files[0].text == b.files[0].text and not a.files[0].warped
    assert a.files[0].resource == OS.body_resource_name("objects/deck.obj", 0, (1.0, 2.0, 3.0))


def test_the_file_name_follows_the_warp():
    n0 = OS.body_resource_name("objects/deck.obj", 0, (0.0, 0.0, 0.0))
    n1 = OS.body_resource_name("objects/deck.obj", 0, (0.0, 0.0, 0.0), warp=NODES)
    n2 = OS.body_resource_name("objects/deck.obj", 0, (0.0, 0.0, 0.0),
                               warp=((0.0, NODES[0][1]), (-0.3, NODES[1][1])))
    assert len({n0, n1, n2}) == 3


def test_an_anim_body_is_refused(tmp_path):
    path = _deck(tmp_path, anim=True)
    comps = tuple(range(len(obj8.solid_components(obj8.parse_obj8(path)))))
    res = OS.split_obj8(path, [OS.BodyCut(0, comps, warp=NODES)], "objects/deck_a.obj",
                        allow_single=True)
    assert res.counts.get("warp_refused_anim") == 1
    assert all(not f.warped for f in res.files)


def _pier(tmp_path) -> str:
    """A 1 m square pier from y -10 to the deck soffit at y 6, at x 0."""
    v = [(x, y, z) for y in (-10.0, 6.0) for x, z in ((-0.5, 1.5), (0.5, 1.5), (0.5, 2.5), (-0.5, 2.5))]
    t = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return _write(tmp_path / "pier.obj", v, t)


def test_a_pier_foot_stretches_down_and_its_top_stays_with_the_deck(tmp_path):
    """Owner 2026-11-17T20:43Z: a floating pier foot is lowered (at most
    3 m, ``[deck] pier_foot_stretch_max_m``); the foot item lowers only
    the bottom band within reach of its point, and names the file."""
    path = _pier(tmp_path)
    comps = tuple(range(len(obj8.solid_components(obj8.parse_obj8(path)))))
    foot = ("foot", 0.0, 2.0, -9.99, 1.7)
    res = OS.split_obj8(path, [OS.BodyCut(0, comps, warp=NODES + (foot,))], "objects/pier.obj",
                        allow_single=True)
    got = [tuple(float(q) for q in ln.split()[1:4]) for ln in res.files[0].text.splitlines()
           if ln.startswith("VT")]
    src = [tuple(float(q) for q in ln.split()[1:4]) for ln in open(path).read().splitlines()
           if ln.startswith("VT")]
    field = OW.Field(NODES)
    assert len(got) == len(src) == 8
    for (x, z, y), (x1, z1, y1) in zip(sorted((a, c, b) for a, b, c in src),
                                       sorted((a, c, b) for a, b, c in got), strict=True):
        want = y + float(field.at(np.asarray([x]), np.asarray([z]))[0]) - (1.7 if y < 0 else 0.0)
        assert (x1, z1) == (x, z) and abs(y1 - want) < 2e-3
    assert (OS.body_resource_name("objects/pier.obj", 0, (0.0, 0.0, 0.0), warp=NODES)
            != OS.body_resource_name("objects/pier.obj", 0, (0.0, 0.0, 0.0),
                                     warp=NODES + (foot,)))
    # a foot alone is still a warp; far from it nothing moves
    f = OW.Field((foot,))
    assert bool(f) and f.drop(np.asarray([10.0]), np.asarray([-10.0]), np.asarray([2.0]))[0] == 0.0
