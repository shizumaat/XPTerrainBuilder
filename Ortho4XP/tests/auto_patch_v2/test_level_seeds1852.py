"""THE LOWER LEVEL FROM WALLS BELOW THE ZERO (#1852, round 4;
``planar/level_regions``).

A unit whose walls stand a storey under its own zero on a pad that is no
stepped block (KIAH: the train station on a §20 conforming pad) is a level
seed; the unreachable apron piece it touches is its lower level, the
seed's depth under the datum of the block the piece fronts -- where its
ground stands nearer that floor than the block's datum.
"""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import level_regions as LR
from auto_patch_v2.planar.low_extent import AirRegion
from auto_patch_v2.planar.low_level import LOW_KIND
from auto_patch_v2.planar.overlay import Region
from shapely.geometry import box
from test_two_pads1214 import _airport, _wall

T = box(400.0, 0.0, 500.0, 100.0)        # the terminal's held block (D 30)
AIR = box(400.0, 100.0, 500.0, 130.0)    # its apron
B = box(500.0, 40.0, 600.0, 100.0)       # the unreachable apron piece


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _station(y=-4.0):
    return [_wall(500.0, 0.0, 540.0, 40.0, y, 8)]


def _cls():
    ring = tuple(AIR.exterior.coords)[:-1]
    return types.SimpleNamespace(cells=[types.SimpleNamespace(ring=ring, holes=(), role="apron")])


def _run(law, parts, tmp_path, ground=26.0):
    A = _airport(parts, tmp_path, ground=lambda x, y: ground)
    seeds, _notes = LR.level_seeds(A, _cls(), law)
    reg = Registries()
    reg.held["term"] = {"unit": "term", "datum_pred": 30.0}
    region = Region(role="building", ref="term", polygon=T, code_number=None,
                    code_letter=None, side="airside", source="cell")
    counts: dict = {}
    out = LR.seed_levels([region], reg, seeds, [AirRegion(AIR, "cell")], A, law, 0.5,
                         counts, beyond=[B])
    return seeds, out, reg, counts


def test_walls_below_the_zero_seed_the_piece_they_touch(law, tmp_path):
    seeds, out, reg, counts = _run(law, _station(), tmp_path)
    assert len(seeds) == 1 and seeds[0].depth == pytest.approx(4.0)
    (ref, rec), = ((k, v) for k, v in reg.landings.items() if v.get("witness") == "walls")
    assert ref == "term/p1" and rec["kind"] == LOW_KIND and rec["block"] == "term"
    assert rec["y_lo"] == pytest.approx(-4.0)          # 4 m under the block's datum
    g = next(r.polygon for r in out if r.ref == ref)
    assert g.area > 0.8 * B.area and g.distance(T) > 0.0 and g.distance(AIR) >= 3.0 - 1e-6
    assert any(r.ref == ref + "#strip" for r in out)
    assert counts["level_seed_levels"] == 1


def test_a_storey_over_level_ground_mints_nothing(law, tmp_path):
    # the piece's ground stands at the block's datum: a basement, no level
    _s, _out, reg, counts = _run(law, _station(), tmp_path, ground=30.0)
    assert not reg.landings and counts["level_seed_levels"] == 0


def test_walls_at_the_zero_seed_nothing(law, tmp_path):
    seeds, _out, reg, _c = _run(law, _station(y=-1.0), tmp_path)
    assert seeds == () and not reg.landings


def test_a_support_founds_no_seed(law, tmp_path):
    pole = _wall(500.0, 0.0, 500.00001, 0.00001, -4.0, 8)
    pole.box = (0.0, 500.0, 0.00001, 500.00001)
    seeds, _out, _reg, _c = _run(law, [pole], tmp_path)
    assert seeds == ()
