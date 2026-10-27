"""#1355 / #1356: a heliport block, and a CIFP code whose apt.dat block is
another facility.

CIFP ``OR01`` / ``ID31`` are runway strips; Global Airports' blocks of the
same codes are hospital heliports far away that author ONE row-102 helipad
and nothing else.  The build failed the airport with "no reference point
derivable".  Two general rules, each pinned on synthetic apt.dat here:

* :meth:`AptAirport.reference_point` reads the helipads (then the
  boundary, taxi nodes and startups) when there is no runway or pavement;
* :func:`selection.apt_dat_elsewhere` skips a candidate whose apt.dat
  geometry lies outside the tile CIFP placed it in.

Headless, ``tmp_path``, no network.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from auto_patch import selection as SEL  # noqa: E402
from auto_patch_v2.airport.apt_dat import parse_airport_block, read_airport_block  # noqa: E402

HELIPAD = "102 H1 43.2153936 -123.3570164 0.0 12.20 12.20 2 0 0 0.25 0"


def _apt(tmp_path, header, body):
    path = tmp_path / "apt.dat"
    path.write_text("A\n1000 Version\n\n%s\n%s\n\n99\n" % (header, body),
                    encoding="utf-8", newline="")
    return str(path)


def _heliport(tmp_path):
    return _apt(tmp_path, "17    450 0 0 ZZH1 [H] Hospital",
                "1302 city Nowhere\n" + HELIPAD + "\n19 43.2155582 -123.3567906 1")


def test_a_heliport_block_takes_its_reference_point_from_the_helipad(tmp_path):
    path = _heliport(tmp_path)
    apt = parse_airport_block(read_airport_block(path, "ZZH1"))
    assert not apt.runways and not apt.pavements
    lat, lon = apt.reference_point()
    assert lat == pytest.approx(43.2153936) and lon == pytest.approx(-123.3570164)


def test_a_block_with_no_geometry_still_raises(tmp_path):
    path = _apt(tmp_path, "17    450 0 0 ZZH2 [H] Empty", "1302 city Nowhere")
    apt = parse_airport_block(read_airport_block(path, "ZZH2"))
    with pytest.raises(ValueError, match="no reference point"):
        apt.reference_point()


def test_a_heliport_far_from_the_cifp_tile_is_skipped_not_built(tmp_path):
    """The OR01 shape: CIFP places the code in +45-117, the apt.dat block
    is a heliport at 43.2 N, 123.4 W."""
    path = _heliport(tmp_path)
    why = SEL.apt_dat_elsewhere(path, "ZZH1", 45, -117)
    assert "outside tile +45-117" in why and "skipped" in why
    assert SEL.apt_dat_elsewhere(path, "ZZH1", 43, -124) == ""


def test_a_runway_just_across_the_tile_edge_is_still_this_tiles(tmp_path):
    """Within the seam ask reach of the cell, the block IS the airport:
    a runway 100 m west of lon -77 still belongs to cell (-13, -77)."""
    lon_w = -77.0 - 100.0 / 108800.0
    path = _apt(tmp_path, "1 10 0 0 ZZZZ Test",
                "100 30.00 1 0 0.25 1 1 0 09 -12.1500000 %.7f 0 0 0 0 0 0 "
                "27 -12.1500000 %.7f 0 0 0 0 0 0" % (lon_w - 0.01, lon_w))
    assert SEL.apt_dat_elsewhere(path, "ZZZZ", -13, -77) == ""
    assert SEL.apt_dat_elsewhere(path, "ZZZZ", -13, -76) != ""


def test_the_selector_never_queues_the_far_block(tmp_path, monkeypatch):
    """The candidate is ``apt_dat_elsewhere`` — not ``patch`` — so the
    driver logs the reason and the manifest never expects its patch."""
    import types
    path = _heliport(tmp_path)
    rw = {"18": {"lat": 45.53, "lon": -116.53, "elevation_ft": 0.0},
          "36": {"lat": 45.52, "lon": -116.53, "elevation_ft": 0.0}}
    monkeypatch.setattr("auto_patch_v2.airport.cifp.discover_cifp_airports",
                        lambda p: {"ZZH1": "ZZH1.dat"})
    monkeypatch.setattr("auto_patch_v2.airport.cifp.read_threshold_dicts",
                        lambda p: dict(rw))
    monkeypatch.setattr("auto_patch_v2.airport.cifp.xplane_root_from_cifp_path",
                        lambda p: "/fake/xplane")
    monkeypatch.setattr("auto_patch.build_support._pick_best_apt_dat_against_osm",
                        lambda root, icao, *a, **k: path)
    tile = types.SimpleNamespace(lat=45, lon=-117)
    (c,) = SEL.select_patch_airports(tile, str(tmp_path), "All")
    assert c.disposition == "apt_dat_elsewhere" and "skipped" in c.reason
    assert SEL.patch_set([c]) == set()
