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
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
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


def _track(d_east: float):
    """The deck's track along its centreline z 2: flat at D 0 inside
    building A (x <= -40), flat at ``d_east`` inside building B (x >= 40),
    linear along the track between."""
    return (("track", ((-60.0, 2.0, 0.0), (-40.0, 2.0, 0.0),
                       (40.0, 2.0, d_east), (60.0, 2.0, d_east))),)


#: building B 0.4 m lower than building A (a 0.4 m step over 80 m: 0.5 %)
NODES = _track(-0.4)


def _ys(text: str) -> dict:
    out = {}
    for ln in text.splitlines():
        if ln.startswith("VT"):
            x, y, _z = (float(q) for q in ln.split()[1:4])
            out[round(x, 2)] = y
    return out


def test_field_is_exact_inside_each_node_and_straight_along_the_track():
    f = OW.Field(NODES)
    d = f.at(np.asarray([-50.0, -40.0, 0.0, 40.0, 50.0]), np.zeros(5))
    assert abs(d[0]) < 1e-9 and abs(d[1]) < 1e-9
    assert abs(d[3] + 0.4) < 1e-9 and abs(d[4] + 0.4) < 1e-9
    assert abs(d[2] + 0.2) < 1e-6          # the midpoint of two nodes
    gx, _gz = f.grad(np.asarray([0.0]), np.asarray([0.0]))
    assert abs(gx[0] + 0.4 / 80.0) < 1e-3
    # off the line a point takes its nearest station's D (no bow sideways)
    off = f.at(np.asarray([0.0, 0.0]), np.asarray([-30.0, 30.0]))
    assert np.allclose(off, -0.2, atol=1e-9)


def test_a_curving_track_is_linear_in_distance_along_it():
    """Owner 2026-11-17T23:33Z: the field is linear in distance ALONG the
    track between nodes, round a bend too (an L: 50 m east, 50 m north)."""
    f = OW.Field((("track", ((0.0, 0.0, 0.0), (50.0, 0.0, -1.0), (50.0, 50.0, -2.0))),))
    d = f.at(np.asarray([25.0, 50.0, 50.0]), np.asarray([0.0, 25.0, 50.0]))
    assert np.allclose(d, [-0.5, -1.5, -2.0], atol=1e-9)


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
                               warp=_track(-0.3))
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
    ring = ((-0.5, 1.5), (0.5, 1.5), (0.5, 2.5), (-0.5, 2.5))
    v = [(x, y, z) for y in (-10.0, 6.0) for x, z in ring]
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
    src = [tuple(float(q) for q in ln.split()[1:4]) for ln in open(path,
        encoding="utf-8").read().splitlines()
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


def test_the_centreline_follows_a_curving_deck_across_a_gap():
    """``deck_profile._centreline``: an L-shaped deck (100 m east, 80 m
    north) cut by a 20 m gap where a station stands is ONE line along it,
    and a side piece hanging off it is no part of it."""
    from auto_patch_v2.airport import deck_profile as DP
    from shapely.geometry import LineString, box
    from shapely.ops import unary_union
    leg = LineString([(0.0, 0.0), (100.0, 0.0), (100.0, 80.0)]).buffer(5.0)
    plan = unary_union([leg.difference(box(40.0, -10.0, 60.0, 10.0)),
                        box(70.0, -40.0, 76.0, -20.0)])          # the side piece
    line = DP._centreline(plan)
    assert 160.0 < line.length < 195.0
    c = np.asarray(line.coords)
    assert c[:, 1].min() > -6.0                                   # never into the side piece
    assert abs(c[0][1]) < 3.0 and abs(c[-1][0] - 100.0) < 3.0


def test_the_knots_hold_each_node_flat_in_order_along_the_track():
    """``deck_profile._knots``: flat over each node's stretch, in station
    order; two overlapping stretches of different D part at the middle."""
    from auto_patch_v2.airport import deck_profile as DP
    k = DP._knots([(100.0, 120.0, -1.0), (0.0, 10.0, 0.0), (115.0, 140.0, -2.0)], 0.05)
    st = [q[0] for q in k]
    assert st == sorted(st)
    assert k[0] == (0.0, 0.0) and k[1] == (10.0, 0.0)
    assert k[2] == (100.0, -1.0) and k[-1] == (140.0, -2.0)
    assert k[3][0] < k[4][0] and k[3][1] == -1.0 and k[4][1] == -2.0


def _bent(ground, *, length=400.0, d_a=0.0, d_b=0.0, radius=1000.0):
    """``deck_track_bend.bend`` over a straight track: node A flat over
    [0, 20] at ``d_a``, node B flat over [length - 20, length] at ``d_b``,
    a foot every 8 m between asking for ``ground(s)``."""
    from auto_patch_v2.airport import deck_track_bend as DB
    st = np.arange(0.0, length + 1e-9, 4.0)
    kn = [(0.0, d_a), (20.0, d_a), (length - 20.0, d_b), (length, d_b)]
    d = np.interp(st, [q[0] for q in kn], [q[1] for q in kn])
    feet = [(float(s), float(ground(s))) for s in np.arange(24.0, length - 20.0, 8.0)]
    out, rep = DB.bend(st, d, kn, feet, grade_max=0.035, radius_m=radius, stretch_m=3.0)
    return st, d, out, rep, feet


def _grades(st, d):
    return np.diff(d) / np.diff(st)


def test_the_track_bends_to_follow_gentle_ground_and_keeps_its_nodes():
    """Owner 2026-11-18T00:32Z (RULINGS 2026-11-17t (3)): between nodes the
    track follows the ground under it (a 1.5 m hump, 1 % flanks) and the
    nodes stay exactly where they were."""
    hump = lambda s: max(0.0, 1.5 - abs(s - 200.0) * 0.01)      # noqa: E731
    st, d, out, rep, feet = _bent(hump)
    assert rep["bent"] == 1 and rep["infeasible"] == 0
    at = np.interp([f[0] for f in feet], st, out)
    assert np.abs(at - np.asarray([f[1] for f in feet])).max() < 0.25
    node = (st <= 20.0) | (st >= 380.0)
    assert np.array_equal(out[node], d[node])


def test_the_bent_track_never_passes_the_rail_cap_and_curves_smoothly():
    """A 9 m fall over 60 m (15 %): the track keeps the capped grade, and
    its grade changes by at most 1/R per metre (a node reads grade 0)."""
    cliff = lambda s: 8.0 if s < 100.0 else (-1.0 if s > 160.0 else 8.0 - 0.15 * (s - 100.0))  # noqa: E731
    st, _d, out, rep, _feet = _bent(cliff, d_a=8.0, d_b=-1.0)
    assert rep["bent"] == 1
    g = _grades(st, out)
    assert np.abs(g).max() <= 0.035 + 1e-6
    dg = np.abs(np.diff(np.concatenate([[0.0], g, [0.0]])))
    run = np.concatenate([[2.0], np.full(len(g) - 1, 4.0), [2.0]])
    assert (dg <= run / 1000.0 + 1e-6).all()
    # past the cliff's foot the track still comes down the capped grade
    assert out[np.searchsorted(st, 160.0)] > -1.0 + 0.5


def test_no_feet_or_no_radius_keeps_the_straight_grade():
    from auto_patch_v2.airport import deck_track_bend as DB
    st = np.arange(0.0, 100.0 + 1e-9, 4.0)
    kn = [(0.0, 0.0), (10.0, 0.0), (90.0, -1.0), (100.0, -1.0)]
    d = np.interp(st, [q[0] for q in kn], [q[1] for q in kn])
    out, rep = DB.bend(st, d, kn, [], grade_max=0.035, radius_m=1000.0, stretch_m=3.0)
    assert np.array_equal(out, d) and rep["bent"] == 0
    # a stretch too short to curve at R takes a tighter radius (counted) ...
    kn2 = [(0.0, 0.0), (32.0, 0.0), (68.0, 0.35), (100.0, 0.35)]
    d2 = np.interp(st, [q[0] for q in kn2], [q[1] for q in kn2])
    out2, rep2 = DB.bend(st, d2, kn2, [(50.0, 3.0)], grade_max=0.035, radius_m=1000.0,
                         stretch_m=3.0)
    assert rep2["tight"] == 1 and rep2["bent"] == 1
    assert np.abs(np.diff(np.diff(out2) / 4.0)).max() <= 4.0 / 500.0 + 1e-6
    # ... and one too short for R/8 keeps its straight grade, counted
    kn3 = [(0.0, 0.0), (46.0, 0.0), (54.0, 0.25), (100.0, 0.25)]
    d3 = np.interp(st, [q[0] for q in kn3], [q[1] for q in kn3])
    out3, rep3 = DB.bend(st, d3, kn3, [(50.0, 3.0)], grade_max=0.035, radius_m=1000.0,
                         stretch_m=3.0)
    assert rep3["infeasible"] == 1 and np.array_equal(out3, d3)
