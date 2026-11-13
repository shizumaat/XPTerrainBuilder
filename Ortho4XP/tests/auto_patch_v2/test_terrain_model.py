"""Owner RULINGS 2026-11-13i (#2036 (c), #2040): an object that MODELS
TERRAIN -- a mountain or a bluff with an orthophoto over its shape -- is
recognised by its geometry and its match to the DEM, never split or
re-anchored, and seated so no visible edge floats; the hide offer needs
quality elevation under it.  Synthetic OBJ8s, no corpus."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch_v2.airport import pack_terrain as PT  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport import terrain_shaped as TS  # noqa: E402
from auto_patch_v2.airport.obj8 import parse_obj8  # noqa: E402

STEP = 20.0
HALF = 400.0


def _hill(x, z):
    """A 150 m mountain over an 800 m square, its rim at y = 0."""
    r = math.hypot(x, z) / HALF
    return max(0.0, 150.0 * (1.0 - r * r))


def _write(tmp_path, name, height, *, uv="photo", rim_y=None):
    """A grid OBJ8 of ``height(x, z)``; ``uv`` "photo" maps the plan onto
    one image, "atlas" packs every cell into a tile of its own scale."""
    n = int(2 * HALF / STEP) + 1
    rng = np.random.default_rng(7)
    vt, idx = [], []
    for i in range(n - 1):
        for j in range(n - 1):
            x0, z0 = -HALF + i * STEP, -HALF + j * STEP
            quad = [(x0, z0), (x0 + STEP, z0), (x0, z0 + STEP), (x0 + STEP, z0 + STEP)]
            s0, t0, k = rng.uniform(0, 0.9), rng.uniform(0, 0.9), rng.uniform(0.001, 0.1)
            base = len(vt)
            for x, z in quad:
                y = height(x, z)
                if rim_y is not None and max(abs(x), abs(z)) >= HALF - 1e-6:
                    y = rim_y(x, z)
                if uv == "photo":
                    s, t = (x + HALF) / (2 * HALF), (z + HALF) / (2 * HALF)
                else:
                    s, t = s0 + k * (x - x0) / STEP, t0 + k * (z - z0) / STEP
                vt.append(f"VT {x} {y} {z} 0 1 0 {s} {t}")
            idx += [base, base + 1, base + 2, base + 1, base + 3, base + 2]
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}", *vt]
    body += [f"IDX {i}" for i in idx] + ["ATTR_hard", f"TRIS 0 {len(idx)}"]
    path = tmp_path / name
    path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def _dem(height, offset=0.0):
    def many(xs, ys):
        # heading 0: the frame's y is north, the object's z is south
        return np.array([height(x, -y) + offset for x, y in zip(xs, ys, strict=True)])
    return many


def _models(path, rows, fine=None):
    return TM.placement_models(rows, lambda d: path if d == "m.obj" else None,
                               lambda d: parse_obj8(path) if d == "m.obj" else None,
                               _dem(_hill), fine)


def test_a_photo_textured_mountain_is_a_candidate(tmp_path):
    s = TM.shape_of(_write(tmp_path, "m.obj", _hill))
    assert s is not None and s.plan_m >= TM.MIN_PLAN_M
    assert s.relief_m >= TM.MIN_RELIEF_M and s.photo_spread <= TM.MAX_PHOTO_SPREAD


def test_an_atlas_textured_shape_is_not(tmp_path):
    """A building's atlas packs its faces at many texel densities."""
    assert TM.shape_of(_write(tmp_path, "b.obj", _hill, uv="atlas")) is None


def test_a_flat_roofscape_is_not(tmp_path):
    assert TM.shape_of(_write(tmp_path, "f.obj", lambda x, z: 30.0)) is None


def test_the_match_follows_the_dem_and_no_edge_floats(tmp_path):
    """Sugarloaf's case: the DEM is the same mountain, the sea round it at
    0 m -- the seat is sea level, the rim on the water."""
    s = TM.shape_of(_write(tmp_path, "m.obj", _hill))
    m = TM.match(s, (0.0, 0.0), 0.0, _dem(_hill))
    assert m is not None and m["corr"] > 0.99 and m["peak_err"] < 0.01
    assert m["z0"] == pytest.approx(0.0, abs=0.5)


def test_a_rim_standing_proud_of_the_ground_lowers_the_seat(tmp_path):
    """KHAF / KOAK: one stretch of the rim stands 12 m over the ground
    (a coarse DEM, a bluff's inland edge) -- the whole frame goes down
    until that edge meets the ground; never seated on the high side."""
    path = _write(tmp_path, "r.obj", _hill,
                  rim_y=lambda x, z: 12.0 if x >= HALF - 1e-6 else 0.0)
    m = TM.match(TM.shape_of(path), (0.0, 0.0), 0.0, _dem(_hill))
    assert m is not None and m["z0"] == pytest.approx(-12.0, abs=0.5)


def test_a_mismatched_ground_is_not_a_model(tmp_path):
    """A shape over flat ground (a city block, a bridge over water) does
    not follow the DEM: no match, no seat."""
    s = TM.shape_of(_write(tmp_path, "m.obj", _hill))
    assert TM.match(s, (0.0, 0.0), 0.0, lambda xs, ys: np.full(len(xs), 5.0)) is None
    assert TM.match(s, (0.0, 0.0), 0.0,
                    lambda xs, ys: np.asarray(xs, dtype=float) * 0.2) is None


def test_the_outer_rim_skips_holes():
    cov = np.ones((7, 7), dtype=bool)
    cov[3, 3] = False
    rim = TM.outer_rim(cov)
    assert not rim[2, 3] and rim[0, 0] and rim[6, 3]


def test_the_origin_set_rides_the_model_and_the_seat_records(tmp_path):
    """The buildings sharing the shell's frame keep their place on it:
    every row of the set is written OBJECT_MSL at the frame zero plus its
    own lift; the hide offer names the model alone."""
    path = _write(tmp_path, "m.obj", _hill)
    rows = [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT"),
            ("dsf:obj1", "house.obj", (0.0, 0.0), 0.0, None, "OBJECT"),
            ("dsf:obj2", "far.obj", (900.0, 0.0), 0.0, None, "OBJECT")]
    models = _models(path, rows, lambda xs, ys: np.ones(len(xs), dtype=bool))
    assert set(models) == {"dsf:obj0"} and models["dsf:obj0"].hideable
    members = TM.set_members(rows, models)
    assert set(members) == {"dsf:obj0", "dsf:obj1"}

    class _A:
        terrain_models = (("dsf:obj0", "m.obj", members["dsf:obj0"], 0.0),
                          ("dsf:obj1", "house.obj", members["dsf:obj1"], 2.0))
    recs = TM.seat_records(_A())
    z0 = models["dsf:obj0"].z0
    assert [r["elevation"] for r in recs] == [round(z0, 3), round(z0 + 2.0, 3)]
    assert TM.hideable_paths(recs) == ("m.obj",)
    assert all(r["seat"] == TS.MODEL_SEAT for r in recs)


def test_the_seat_record_writes_an_msl_row():
    """``terrain_shaped.row_seats`` writes a model record as OBJECT_MSL."""
    class _Row:
        def __init__(self, path):
            self.def_path, self.lon, self.lat, self.heading_deg = path, -43.1, -22.9, 151.0

    class _Dump:
        placements = [_Row("m.obj"), _Row("house.obj")]
    recs = [{"id": "dsf:obj0", "resource": "m.obj", "seat": TS.MODEL_SEAT, "elevation": -3.5},
            {"id": "dsf:obj1", "resource": "house.obj", "seat": TS.MODEL_SEAT,
             "elevation": -1.5}]
    seats = TS.row_seats(_Dump(), recs, frozenset())
    assert [(m.index, m.elevation, m.why) for m in seats] == [
        (0, -3.5, "terrain_model"), (1, -1.5, "terrain_model")]


def test_without_quality_elevation_nothing_is_hideable(tmp_path):
    path = _write(tmp_path, "m.obj", _hill)
    rows = [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT")]
    assert not _models(path, rows)["dsf:obj0"].hideable


def test_an_msl_row_states_its_own_datum(tmp_path):
    path = _write(tmp_path, "m.obj", _hill)
    rows = [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, 12.0, "OBJECT_MSL")]
    assert _models(path, rows) == {}


def test_the_hidden_definitions_of_a_dump():
    dump = ["OBJECT_DEF a.obj", "OBJECT_DEF Objetos/mountain.obj", "POLYGON_DEF p.pol",
            "OBJECT 1 -43.1 -22.9 151", "OBJECT 0 -43.1 -22.9 0", "OBJECT 1 -43.2 -22.9 0"]
    got = PT.terrain_objects(dump, ["Objetos/mountain.obj"])
    assert [(m.kind, m.index, m.path, m.uses) for m in got] == [
        ("object", 1, "Objetos/mountain.obj", 2)]
    assert PT.terrain_objects(dump, []) == ()
    assert PT.decode(PT.encode(["b.obj", "a.obj", ""])) == ("a.obj", "b.obj")
