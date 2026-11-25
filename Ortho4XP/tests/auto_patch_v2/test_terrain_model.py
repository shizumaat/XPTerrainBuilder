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
from auto_patch_v2.model.frame import Frame  # noqa: E402

STEP = 20.0
HALF = 400.0


def _hill(x, z):
    """A 150 m mountain over an 800 m square, its rim at y = 0."""
    r = math.hypot(x, z) / HALF
    return max(0.0, 150.0 * (1.0 - r * r))


def _write(tmp_path, name, height, *, uv="photo", rim_y=None, half=HALF, step=STEP,
           hard=True):
    """A grid OBJ8 of ``height(x, z)`` over ``[-half, half]``; ``uv``
    "photo" maps the plan onto one image, "atlas" packs every cell into a
    tile of its own scale; ``hard``: its triangles are ``ATTR_hard``."""
    HALF, STEP = half, step  # noqa: N806 -- the grid this file is written on
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
    body += [f"IDX {i}" for i in idx] + (["ATTR_hard"] if hard else []) + [f"TRIS 0 {len(idx)}"]
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


def test_a_rim_standing_proud_of_the_ground_is_filled_not_sunk(tmp_path):
    """#2077 rule B (owner 2026-11-15): one stretch of the rim stands 12 m
    over the ground -- the frame keeps its L1 fit to the ground (the hill
    where the hill is) and the tile build fills up to that edge; the
    2026-11-13i seat (the whole frame down until that edge meets the
    ground) is ``rim_seat``, the ground shell's bound."""
    path = _write(tmp_path, "r.obj", _hill,
                  rim_y=lambda x, z: 12.0 if x >= HALF - 1e-6 else 0.0)
    shape = TM.shape_of(path)
    m = TM.match(shape, (0.0, 0.0), 0.0, _dem(_hill))
    assert m is not None and m["z0"] == pytest.approx(0.0, abs=0.5)
    assert TM.rim_seat(shape.grid, (0.0, 0.0), 0.0, _dem(_hill)) == pytest.approx(-12.0, abs=0.5)


def test_a_wet_rim_caps_the_fit_seat(tmp_path):
    """#2077 2.1: the ground under water cannot be filled -- with a tenth
    of the rim over water the zero stands no higher than those wet rim
    cells' ``ground - bottom`` (the skirt stays under the water)."""
    path = _write(tmp_path, "w.obj", _hill,
                  rim_y=lambda x, z: 12.0 if x >= HALF - 1e-6 else 0.0)
    shape = TM.shape_of(path)

    def water(xs, ys):
        wet = np.asarray(xs, float) >= HALF - 1e-6
        return wet, np.where(wet, 0.0, np.nan)
    z0 = TM._fit_seat(shape.grid, (0.0, 0.0), 0.0, _dem(_hill), water)
    assert z0 == pytest.approx(-12.0, abs=0.5)
    assert TM._fit_seat(shape.grid, (0.0, 0.0), 0.0, _dem(_hill),
                       lambda xs, ys: (np.zeros(len(xs), bool), np.full(len(xs), np.nan))
                       ) == pytest.approx(0.0, abs=0.5)


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
        frame = Frame("TEST", (-22.95, -43.15), 11)
    recs = TM.seat_records(_A())
    z0 = models["dsf:obj0"].z0
    assert [r["elevation"] for r in recs] == [round(z0, 3), round(z0 + 2.0, 3)]
    assert TM.hideable_paths(recs) == ("m.obj",)
    assert all(r["seat"] == TS.MODEL_SEAT for r in recs)
    # owner RULINGS 2026-11-13k: the model's own row names what the tile
    # build cuts the ground to -- its file, anchor and heading
    assert recs[0]["cut"] == {"file": path, "lat": -22.95, "lon": -43.15, "heading": 0.0,
                              "fill": True}
    assert "cut" not in recs[1]


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


def test_an_msl_row_is_a_model_and_keeps_its_datum(tmp_path):
    """#2077 (LOWS's Festungsberg shell, OBJECT_MSL 430): the 11d
    conversion drops every MSL column, so an MSL row is read like any
    other -- seated by its rim, its authored datum kept on the model."""
    path = _write(tmp_path, "m.obj", _hill)
    rows = [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, 12.0, "OBJECT_MSL")]
    m = _models(path, rows)["dsf:obj0"]
    assert m.datum == 12.0 and m.z0 == pytest.approx(0.0, abs=0.5)
    assert TM.member_lift(m, "OBJECT_MSL", 12.0) == 0.0


def test_msl_rows_over_an_msl_model_ride_it_by_their_authored_height(tmp_path):
    """The castle the author set at 92 m on a hill shell set at 12 m is the
    shell's content: it keeps its 80 m over the shell's zero.  An MSL row
    off the plan, a plain row on it and a stock library row on it do not
    join (the plain row follows the drawn ground; the stock row is
    ``frame_riders``')."""
    path = _write(tmp_path, "m.obj", _hill)
    rows = [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, 12.0, "OBJECT_MSL"),
            ("dsf:obj1", "castle.obj", (40.0, 30.0), 329.0, 92.0, "OBJECT_MSL"),
            ("dsf:obj2", "far.obj", (900.0, 0.0), 0.0, 12.0, "OBJECT_MSL"),
            ("dsf:obj3", "lamp.obj", (40.0, 30.0), 0.0, None, "OBJECT"),
            ("dsf:obj4", "lib/street/bench.obj", (40.0, 30.0), 0.0, 90.0, "OBJECT_MSL"),
            ("dsf:obj5", "station.obj", (0.0, 0.0), 0.0, 20.0, "OBJECT_MSL")]
    models = _models(path, rows)
    assert set(models) == {"dsf:obj0"}
    members = TM.set_members(rows, models)
    assert set(members) == {"dsf:obj0", "dsf:obj1", "dsf:obj5"}
    # a row at the model's own origin is of its set whatever its MSL column
    assert TM.member_lift(members["dsf:obj5"], "OBJECT_MSL", 20.0) == 8.0
    assert TM.member_lift(members["dsf:obj1"], "OBJECT_MSL", 92.0) == 80.0
    # a plain-row model has no datum: its members lift by their own AGL
    plain = _models(path, [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT")])
    assert TM.member_lift(plain["dsf:obj0"], "OBJECT_MSL", 92.0) is None


def test_the_hidden_definitions_of_a_dump():
    dump = ["OBJECT_DEF a.obj", "OBJECT_DEF Objetos/mountain.obj", "POLYGON_DEF p.pol",
            "OBJECT 1 -43.1 -22.9 151", "OBJECT 0 -43.1 -22.9 0", "OBJECT 1 -43.2 -22.9 0"]
    got = PT.terrain_objects(dump, ["Objetos/mountain.obj"])
    assert [(m.kind, m.index, m.path, m.uses) for m in got] == [
        ("object", 1, "Objetos/mountain.obj", 2)]
    assert PT.terrain_objects(dump, []) == ()
    assert PT.decode(PT.encode(["b.obj", "a.obj", ""])) == ("a.obj", "b.obj")


def test_the_hide_offer_needs_a_source_no_coarser_than_the_shells_post(tmp_path):
    """#2077 4.1: quality elevation must cover the plan at a pixel no
    coarser than the shell's own post (here 20 m, so the 10 m ceiling
    rules) and model it at the L1 fit."""
    path = _write(tmp_path, "m.obj", _hill)
    shape = TM.shape_of(path)
    assert shape.post_m == pytest.approx(STEP, abs=1e-6)
    asked = []

    def fine(xs, ys, pixel_m=TM.QUALITY_PIXEL_M):
        asked.append(pixel_m)
        return np.full(len(xs), pixel_m >= 10.0)
    cover, ok = TM.quality(shape, (0.0, 0.0), 0.0, _dem(_hill), fine)
    assert asked == [10.0] and cover == 1.0 and ok
    # the ground disagrees with the shell (a 30 m bump): no offer
    bump = lambda x, z: _hill(x, z) + (30.0 if x > 0 else 0.0)  # noqa: E731
    assert not TM.quality(shape, (0.0, 0.0), 0.0, _dem(bump), fine)[1]
    assert TM.quality(shape, (0.0, 0.0), 0.0, _dem(_hill), None) == (0.0, False)


def test_a_model_the_user_hid_dissolves_and_keeps_its_offer(tmp_path):
    """#2077 4.2: a hidden model is ``ground = "hidden"`` -- its own row a
    hidden seat, the offer kept for Undo -- and its frame is not read as
    its content."""
    path = _write(tmp_path, "m.obj", _hill)
    rows = [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT")]
    models = TM.placement_models(rows, lambda d: path, lambda d: parse_obj8(path),
                                 _dem(_hill), None, hidden=frozenset({"m.obj"}))
    m = models["dsf:obj0"]
    assert m.ground == "hidden" and m.hideable and m.fill

    class _A:
        terrain_models = (("dsf:obj0", "m.obj", m, 0.0),)
        frame = Frame("TEST", (-22.95, -43.15), 11)
    recs = TM.seat_records(_A())
    assert recs[0]["seat"] == TS.HIDDEN_SEAT and "cut" not in recs[0]
    assert TM.hideable_paths(recs) == ("m.obj",)
    assert "HIDDEN" in TM.log_line("TEST", [m])


def test_a_pack_hiding_its_offer_hides_a_hideable_model_this_build(tmp_path):
    """#2285: a pack whose terrain row hides by default hides the model
    this build offers (quality elevation models it), never one it does
    not offer, never one the user keeps."""
    from auto_patch_v2.airport.pack_choice import _TerrainHiding
    path = _write(tmp_path, "m.obj", _hill)
    rows = [("dsf:obj0", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT")]
    fine = lambda xs, ys: np.ones(len(xs), dtype=bool)   # noqa: E731

    def run(hidden, fine):
        return TM.placement_models(rows, lambda d: path, lambda d: parse_obj8(path),
                                   _dem(_hill), fine, hidden=hidden)["dsf:obj0"]
    assert run(_TerrainHiding((), kept=()), fine).ground == "hidden"
    assert run(_TerrainHiding((), kept=()), None).ground == "", "not offered: kept"
    assert run(_TerrainHiding((), kept=("m.obj",)), fine).ground == "", "the user keeps it"
    assert run(_TerrainHiding(()), fine).ground == "", "the pack does not hide its offer"
    assert run(frozenset(), fine).ground == ""
