"""RULINGS 2026-11-25j: a ROCK OUTCROP or an ADDED HILL a pack lays on the
ground (a plain ``OBJECT`` row, often hard, often tiled-textured) is a
terrain shell (``terrain_rock``): recognised by a witness of natural
relief read on its geometry only, matched at its row's datum and seated
by the shells' skirt seat.  Built look-alikes -- a terrace of storeys, a
field of scattered piles, a gentle mound, a fence -- are not.  Synthetic
OBJ8s, no corpus."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import test_terrain_model as TTM  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport import terrain_rock as TR  # noqa: E402
from auto_patch_v2.airport.obj8 import parse_obj8  # noqa: E402

HALF = 50.0


def _outcrop(x, z):
    """A 20 m outcrop over a 100 m square, its rim at y = 0."""
    r = math.hypot(x, z) / HALF
    return max(0.0, 20.0 * (1.0 - r))


def _write(tmp_path, name="rock.obj", height=_outcrop, **kw):
    kw.setdefault("hard", True)
    kw.setdefault("uv", "atlas")
    return TTM._write(tmp_path, name, height, half=HALF, step=5.0, **kw)


def _soup(tmp_path, name, tris):
    """An OBJ8 of the triangles ``tris`` (``(n, 3, 3)`` x y z corners)."""
    vt = [f"VT {x} {y} {z} 0 1 0 0 0" for t in tris for x, y, z in t]
    idx = list(range(len(vt)))
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}", *vt]
    body += [f"IDX {i}" for i in idx] + [f"TRIS 0 {len(idx)}"]
    path = tmp_path / name
    path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def _quad(a, b, c, d):
    return [[a, b, c], [a, c, d]]


def _box(x0, x1, z0, z1, h):
    """A roofed box: four walls and the roof that caps them."""
    p = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    out = _quad(*[(x, h, z) for x, z in p])
    for (xa, za), (xb, zb) in zip(p, p[1:] + p[:1]):
        out += _quad((xa, 0.0, za), (xb, 0.0, zb), (xb, h, zb), (xa, h, za))
    return out


def _flat(z):
    return lambda xs, ys: np.full(len(xs), float(z))


def test_a_hard_atlas_textured_outcrop_is_a_rock(tmp_path):
    s = TM.shape_of(_write(tmp_path))
    assert s is not None and s.small and s.rock
    assert s.relief_m >= TR.ROCK_MIN_RELIEF_M


def test_a_berm_with_free_standing_tree_cards_is_a_rock(tmp_path):
    g = parse_obj8(_write(tmp_path, "berm.obj"))
    ground = g.vertices[g.solid].tolist()
    cards = []
    for k in range(-30, 31, 10):            # cards on the slope, capped by nothing
        y = _outcrop(float(k), 0.0)
        cards += _quad((k - 3.0, y, 0.0), (k + 3.0, y, 0.0), (k + 3.0, y + 9.0, 0.0),
                       (k - 3.0, y + 9.0, 0.0))
    path = _soup(tmp_path, "berm_trees.obj", ground + cards)
    s = TM.shape_of(path)
    assert s is not None and s.rock
    g2 = parse_obj8(path)
    assert TR.capped_wall_share(g2.vertices, g2.solid) == 0.0


def test_a_terrace_of_storeys_is_not(tmp_path):
    # six roofed blocks rising 4 m each: steep enough, one body, but every
    # wall stands under a roof
    tris = []
    for k in range(6):
        tris += _box(-30.0 + 10.0 * k, -20.0 + 10.0 * k, -30.0, 30.0, 4.0 * (k + 1))
    path = _soup(tmp_path, "terrace.obj", tris)
    g = parse_obj8(path)
    assert TR.capped_wall_share(g.vertices, g.solid) > TR.ROCK_MAX_CAPPED
    assert TM.shape_of(path) is None


def test_scattered_piles_a_gentle_mound_and_a_fence_are_not(tmp_path):
    def piles(x, z):
        # 20 m piles 40 m apart: no piece spans 50 m
        cx, cz = (x + HALF) % 40.0 - 20.0, (z + HALF) % 40.0 - 20.0
        return max(0.0, 8.0 * (1.0 - math.hypot(cx, cz) / 10.0))
    mound = TTM._write(tmp_path, "mound.obj",
                       lambda x, z: 6.0 * (1 - abs(x) / 200) * (1 - abs(z) / 200),
                       half=200.0, step=10.0, hard=True, uv="atlas")
    assert TM.shape_of(mound) is None
    fence = _quad((-100.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 6.0, 0.0), (-100.0, 6.0, 0.0))
    assert TM.shape_of(_soup(tmp_path, "fence.obj", fence)) is None
    g = parse_obj8(_write(tmp_path, "piles.obj", piles))
    tris = [t.tolist() for t in g.vertices[g.solid] if t[:, 1].max() > 0.0]
    assert TM.shape_of(_soup(tmp_path, "piles2.obj", tris)) is None


def test_row_datum_is_the_msl_column_or_the_ground_plus_the_lift():
    dem = _flat(12.0)
    assert TR.row_datum("OBJECT_MSL", 40.0, (0.0, 0.0), dem) == 40.0
    assert TR.row_datum("OBJECT", None, (0.0, 0.0), dem) == 12.0
    assert TR.row_datum("OBJECT_AGL", 1.5, (0.0, 0.0), dem) == 13.5
    assert TR.row_datum("OBJECT", None, (0.0, 0.0), _flat(math.nan)) is None


def test_a_plain_row_matches_where_its_base_rests_on_our_ground(tmp_path):
    path = _write(tmp_path)
    rows = [("dsf:obj1", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT"),
            ("dsf:obj2", "m.obj", (900.0, 0.0), 0.0, None, "OBJECT")]

    def dem(xs, ys):
        # flat at 10 m but a 20 m pit under the second rock's anchor: its
        # datum there leaves its rim 20 m under our ground
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        return 10.0 - np.where((np.abs(xs - 900.0) < 5.0) & (np.abs(ys) < 5.0), 20.0, 0.0)
    found = TM.placement_models(rows, lambda d: path, lambda d: parse_obj8(path), dem)
    assert set(found) == {"dsf:obj1"}
    m = found["dsf:obj1"]
    assert m.small and m.datum is None and m.z0 == pytest.approx(10.0)
    rec = TR.rock_match(TM.shape_of(path), (0.0, 0.0), 0.0, _flat(10.0), 10.0)
    assert rec["level_m"] == pytest.approx(0.0, abs=0.01) and not rec["hideable"]
