"""Issue #2272 (owner decisions 2026-11-24T15:33Z): a SMALL TERRAIN SHELL
-- a soft, photo-textured rock, cliff or islet under 500 m that a pack
writes ``OBJECT_MSL`` -- is recognised (``terrain_shell``), matched at
its author's datum and seated there, the wet rim capping it, and then
travels ``terrain_model``'s one path (never split; seated by its skirt,
``test_shell_seat``).  Synthetic OBJ8s, no corpus."""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import test_terrain_model as TTM  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport import terrain_shell as TSH  # noqa: E402
from auto_patch_v2.airport.obj8 import parse_obj8  # noqa: E402

HALF = 100.0


def _rock(x, z):
    """A 30 m rock over a 200 m square, its rim at y = 0."""
    r = math.hypot(x, z) / HALF
    return max(0.0, 30.0 * (1.0 - r * r))


def _write(tmp_path, name="rock.obj", height=_rock, **kw):
    kw.setdefault("hard", False)
    return TTM._write(tmp_path, name, height, half=HALF, step=5.0, **kw)


def _seeing(xs, ys, pixel_m=10.0):
    """Quality elevation fine enough for any shell, everywhere."""
    return np.ones(len(xs), dtype=bool)


def _coarse(xs, ys, pixel_m=10.0):
    """Only a source coarser than the shell's quarter plan."""
    return np.zeros(len(xs), dtype=bool)


def _flat(z):
    return lambda xs, ys: np.full(len(xs), float(z))


def test_a_soft_photo_textured_rock_is_a_small_shell(tmp_path):
    s = TM.shape_of(_write(tmp_path))
    assert s is not None and s.small
    assert TSH.SHELL_MIN_PLAN_M <= s.plan_m < TM.MIN_PLAN_M
    assert s.relief_m >= TSH.SHELL_MIN_RELIEF_M


def test_a_hard_an_atlas_or_a_flat_object_is_not(tmp_path):
    assert TSH.small_shape(_write(tmp_path, "hard.obj", hard=True),
                           parse_obj8(str(tmp_path / "hard.obj"))) is None
    assert TSH.small_shape(_write(tmp_path, "atlas.obj", uv="atlas"),
                           parse_obj8(str(tmp_path / "atlas.obj"))) is None
    assert TM.shape_of(_write(tmp_path, "kerb.obj", lambda x, z: 0.5)) is None
    # RULINGS 2026-11-25j: the hard or atlas-textured hill is no shell but
    # a ROCK (``terrain_rock``, test_terrain_rock)
    assert TM.shape_of(str(tmp_path / "hard.obj")).rock


def test_a_terrace_is_not_one_steep_piece(tmp_path):
    """Three flat levels 6 m apart: relief, but no hillside."""
    def terrace(x, z):
        return 6.0 * min(2, int((x + HALF) // 70.0))
    assert TM.shape_of(_write(tmp_path, "terrace.obj", terrace)) is None


def test_only_an_msl_row_matches_and_it_seats_at_the_authors_datum(tmp_path):
    s = TM.shape_of(_write(tmp_path))
    assert TM.match(s, (0.0, 0.0), 0.0, TTM._dem(_rock, 2.0)) is None
    m = TM.match(s, (0.0, 0.0), 0.0, TTM._dem(_rock, 2.0), _seeing, None, 2.0)
    assert m is not None and m["z0"] == pytest.approx(2.0) and m["corr"] > 0.99
    # our ground 1.5 m over the author's: still the author's height
    m = TM.match(s, (0.0, 0.0), 0.0, TTM._dem(_rock, 3.5), _seeing, None, 2.0)
    assert m is not None and m["z0"] == pytest.approx(2.0)


def test_an_author_frame_off_our_ground_is_not_a_shell(tmp_path):
    s = TM.shape_of(_write(tmp_path))
    assert TM.match(s, (0.0, 0.0), 0.0, TTM._dem(_rock, 40.0), _seeing, None, 0.0) is None


def test_a_shape_the_dem_sees_must_follow_it(tmp_path):
    """Ground of the same level but another shape (a slope across the
    plan): with fine elevation that sees it, no match; with only a coarse
    source, or over flat sea, the level alone decides."""
    s = TM.shape_of(_write(tmp_path))

    def slope(xs, ys):
        return 12.0 + 0.12 * np.asarray(xs, dtype=float)
    assert TM.match(s, (0.0, 0.0), 0.0, slope, _seeing, None, 0.0) is None
    assert TM.match(s, (0.0, 0.0), 0.0, slope, _coarse, None, 0.0) is not None
    m = TM.match(s, (0.0, 0.0), 0.0, _flat(8.0), _seeing, None, 0.0)
    assert m is not None and m["z0"] == pytest.approx(0.0)


def test_a_wet_rim_caps_the_authors_datum(tmp_path):
    """An islet whose skirt stops 3 m over its zero: over the sea at 0 m
    the zero comes down so the skirt stays under the water."""
    s = TM.shape_of(_write(tmp_path, rim_y=lambda x, z: 3.0))

    def water(xs, ys):
        return np.ones(len(xs), dtype=bool), np.zeros(len(xs))
    m = TM.match(s, (0.0, 0.0), 0.0, _flat(0.0), _seeing, water, 1.0)
    assert m is not None and m["z0"] == pytest.approx(-3.0, abs=0.01)
    m = TM.match(s, (0.0, 0.0), 0.0, _flat(0.0), _seeing, None, 1.0)
    assert m is not None and m["z0"] == pytest.approx(1.0)


def test_placement_models_marks_the_small_shell(tmp_path):
    path = _write(tmp_path)
    rows = [("dsf:obj7", "m.obj", (0.0, 0.0), 0.0, 2.0, "OBJECT_MSL"),
            ("dsf:obj8", "m.obj", (500.0, 0.0), 0.0, None, "OBJECT")]
    found = TM.placement_models(rows, lambda d: path, lambda d: parse_obj8(path),
                                TTM._dem(_rock, 2.0), _seeing)
    # RULINGS 2026-11-25l: the shell's plain row is read as a ROCK (the
    # witness passes; ``terrain_rock``), at its anchor's ground
    assert set(found) == {"dsf:obj7", "dsf:obj8"}
    assert found["dsf:obj8"].small and found["dsf:obj8"].datum is None
    m = found["dsf:obj7"]
    assert m.small and m.fill and m.datum == 2.0 and m.z0 == pytest.approx(2.0)
    assert "its author's datum, a small shell" in TM.log_line("TEST", found.values())
