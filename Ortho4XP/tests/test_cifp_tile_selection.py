"""``auto_patch_v2.airport.cifp`` — the CIFP runway reader in the shape
tile selection reads (``read_threshold_dicts``) and the tile-level
discovery ``auto_patch.selection`` builds on (moved here from the retired
v1 ``auto_patch.cifp_reader``, owner 2026-10-18 #911 Q1).

``discover_cifp_airports`` and ``airport_in_tile`` decide WHICH airports
a tile build patches (``selection.py``); production reaches both on every
tile build (measured: the OTHH tile build of lane ``objtests``,
2026-10-04) and after the v1 cut no test executed either — every suite
that names them replaces them with a stub (RULINGS 2026-10-04j "coverage
owed").
"""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import cifp as C
from object_stage_support import write_text

# The record the module's own docstring documents (SPJC 16L).
RWY_16L = "RWY:RW16L,+0580,      ,00044, ,IJCH,3,   ;S12002744,W077071686,0000;"
RWY_34R = "RWY:RW34R,+2380,      ,00113, ,IJCZ,1,   ;S12021200,W077064500,0984;"


def test_arinc_coordinates_parse_to_signed_degrees():
    assert C.parse_lat("S12002744") == pytest.approx(
        -(12 + 0 / 60 + 27.44 / 3600))
    assert C.parse_lat("N25153000") == pytest.approx(25.258333333)
    assert C.parse_lon("W077071686") == pytest.approx(
        -(77 + 7 / 60 + 16.86 / 3600))
    assert C.parse_lon("E051361200") == pytest.approx(51.603333333)


def test_a_cifp_file_yields_thresholds_in_metres(tmp_path):
    path = write_text(tmp_path / "SPJC.dat", "\n".join([
        "APPCH:010,A,I16L ,AER,...",
        RWY_16L, RWY_34R,
        "RWY:XX99,+0000,      ,00010, ,    , ,   ;S12000000,W077000000,0000;",
        "RWY:RW09,+0900,      ,     , ,    , ,   ;S12000000,W077000000,0000;",
        "RWY:RW27,+2700,      ,00010, ,    , ,   ;S12,W077,0000;",
        "RWY:RW01,+0100",
    ]) + "\n")
    runways = C.read_threshold_dicts(path)
    assert sorted(runways) == ["RW16L", "RW34R"]
    r = runways["RW16L"]
    assert r["elevation_m"] == pytest.approx(44 * C.FT_TO_M)
    assert r["displaced_m"] == 0.0
    assert r["lat"] == pytest.approx(C.parse_lat("S12002744"))
    assert r["lon"] == pytest.approx(C.parse_lon("W077071686"))
    assert runways["RW34R"]["displaced_m"] == pytest.approx(984 * C.FT_TO_M)


def test_an_unreadable_cifp_file_is_no_runways(tmp_path):
    """Selection's behaviour is kept: a vanished or undecodable CIFP file
    skips the airport, it never fails the tile (v2's own
    ``read_cifp_runways`` raises; the selection shape swallows)."""
    assert C.read_threshold_dicts(str(tmp_path / "absent.dat")) == {}
    with pytest.raises(OSError):
        C.read_cifp_runways(str(tmp_path / "absent.dat"))


def test_discovery_lists_airport_files_by_upper_case_icao(tmp_path):
    cifp = tmp_path / "CIFP"
    for name in ("OTHH.dat", "spjc.DAT", "K1.dat", "7FL6.dat",
                 "TOOLONG.dat", "X.dat", "A_B.dat", "notes.txt"):
        write_text(cifp / name, RWY_16L + "\n")
    found = C.discover_cifp_airports(str(cifp))
    assert sorted(found) == ["7FL6", "K1", "OTHH", "SPJC"]
    assert found["SPJC"] == str(cifp / "spjc.DAT")


@pytest.mark.parametrize("bad", ["", None, "no/such/dir"])
def test_discovery_of_no_directory_is_empty(bad):
    assert C.discover_cifp_airports(bad) == {}


def test_an_airport_is_in_the_tile_holding_any_threshold(tmp_path):
    runways = C.read_threshold_dicts(
        write_text(tmp_path / "SPJC.dat", RWY_16L + "\n" + RWY_34R + "\n"))
    assert C.airport_in_tile(runways, -13, -78)
    assert not C.airport_in_tile(runways, -12, -78)
    assert not C.airport_in_tile(runways, -13, -77)
    assert not C.airport_in_tile({}, -13, -78)


def test_the_tile_is_half_open_on_its_north_and_east_edges():
    def at(lat, lon):
        return {"RW01": {"lat": lat, "lon": lon,
                         "elevation_m": 0.0, "displaced_m": 0.0}}
    assert C.airport_in_tile(at(25.0, 51.0), 25, 51)       # SW corner: in
    assert not C.airport_in_tile(at(26.0, 51.5), 25, 51)   # north edge: out
    assert not C.airport_in_tile(at(25.5, 52.0), 25, 51)   # east edge: out
    # a straddler counts for EACH tile holding one of its thresholds
    both = {**at(25.9, 51.5), "RW19": at(26.1, 51.5)["RW01"]}
    assert C.airport_in_tile(both, 25, 51) and C.airport_in_tile(both, 26, 51)


def test_the_install_root_is_two_levels_above_the_cifp_directory(tmp_path):
    root = tmp_path / "X-Plane 12"
    (root / "Custom Scenery").mkdir(parents=True)
    cifp = root / "Custom Data" / "CIFP"
    cifp.mkdir(parents=True)
    assert C.xplane_root_from_cifp_path(str(cifp)) == str(root)
    assert C.xplane_root_from_cifp_path(str(cifp) + "/") == str(root)
    assert C.xplane_root_from_cifp_path("") is None
    stray = tmp_path / "elsewhere" / "data" / "CIFP"
    stray.mkdir(parents=True)
    assert C.xplane_root_from_cifp_path(str(stray)) is None
