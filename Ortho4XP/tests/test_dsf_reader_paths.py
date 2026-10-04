"""``dsf_reader.tile_dsf_path`` / ``find_associated_dsf`` — where a
pack's DSF for a tile lives.

``driver`` builds the tile's object-anchor worklist on these two
(``_object_anchor_worklist_entries``: the apt.dat winner's own DSF);
production reaches both on every tile build (measured: the OTHH tile
build of lane ``objtests``, 2026-10-04).  ``find_associated_dsf`` lost
its only test reference in the v1 cut — and that one was a stub
(RULINGS 2026-10-04j "coverage owed").
"""
from __future__ import annotations

import os

import pytest

from auto_patch import dsf_reader as D

from object_stage_support import write_text


@pytest.mark.parametrize("lat, lon, expected", [
    (25, 51, ("+20+050", "+25+051.dsf")),
    (60, -136, ("+60-140", "+60-136.dsf")),
    (-13, -78, ("-20-080", "-13-078.dsf")),
    (-15, -179, ("-20-180", "-15-179.dsf")),
    (0, 0, ("+00+000", "+00+000.dsf")),
    (-1, -1, ("-10-010", "-01-001.dsf")),
    (9, 179, ("+00+170", "+09+179.dsf")),
])
def test_the_tile_dsf_path_groups_by_ten_degree_block(lat, lon, expected):
    assert D.tile_dsf_path("END", lat, lon) == os.path.join("END", *expected)


def _pack(tmp_path, lat, lon, *, dir_name="Earth nav data"):
    end = tmp_path / "Custom Scenery" / "Pack" / dir_name
    apt = write_text(end / "apt.dat", "I\n1200 Version\n")
    dsf = write_text(D.tile_dsf_path(str(end), lat, lon), "dsf")
    return apt, dsf


def test_the_associated_dsf_is_the_packs_own_tile_file(tmp_path):
    apt, dsf = _pack(tmp_path, 60, -136)
    assert D.find_associated_dsf(apt, 60.7, -135.07) == dsf
    # floor, not truncation: a western / southern airport stays in ITS tile
    assert D.find_associated_dsf(apt, 60.0, -135.999) == dsf


def test_a_southern_western_airport_floors_into_its_own_tile(tmp_path):
    apt, dsf = _pack(tmp_path, -13, -78)
    assert D.find_associated_dsf(apt, -12.02, -77.11) == dsf


def test_no_dsf_for_the_tile_is_none(tmp_path):
    apt, _dsf = _pack(tmp_path, 60, -136)
    assert D.find_associated_dsf(apt, 61.2, -135.07) is None


def test_an_apt_dat_outside_earth_nav_data_has_no_associated_dsf(tmp_path):
    apt, _dsf = _pack(tmp_path, 60, -136, dir_name="nav")
    assert D.find_associated_dsf(apt, 60.7, -135.07) is None


@pytest.mark.parametrize("missing", ["", None, "no/such/Earth nav data/apt.dat"])
def test_a_missing_apt_dat_has_no_associated_dsf(missing):
    assert D.find_associated_dsf(missing, 60.7, -135.07) is None
