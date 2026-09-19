"""§E test 6 — the class S / M decision on synthetic apt.dat geometry.

Spec ``docs/specs/insets-follow-patch-set-spec.md`` §C.1 rev 3, ruled by
RULINGS 2026-09-18h (the far-side leak is ACCEPTED for class M) and
2026-09-18i (an airport whose AIRSIDE claim crosses ALWAYS prompts).

The five cases the spec names, plus the invariant that matters most:
the PREFLIGHT and the BUILD-TIME check are the same function on the same
apt.dat, so they cannot disagree.  Headless, ``tmp_path``, no network.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from auto_patch import selection as SEL                  # noqa: E402

#: Cell (-13, -77) spans lat [-13, -12) and lon [-77, -76).  Everything
#: below is placed relative to the lon = -77 line at latitude -12.15,
#: where one degree of longitude is ~108.8 km.
HOME = (-13, -77)
LAT = -12.15
M_PER_DEG_LON = 108800.0
M_PER_DEG_LAT = 111132.0


def _lon(metres_east_of_the_line: float) -> float:
    return -77.0 + metres_east_of_the_line / M_PER_DEG_LON


def _apt(tmp_path, name, body):
    path = tmp_path / ("%s.dat" % name)
    path.write_text(
        "A\n1000 Version\n\n1 10 0 0 ZZZZ Test\n%s\n99\n" % body,
        encoding="utf-8")
    return str(path)


def _runway(east_a_m, east_b_m, width_m=60.0):
    return ("100 %.2f 1 0 0.25 1 1 0 09 %.7f %.7f 0 0 0 0 0 0 "
            "27 %.7f %.7f 0 0 0 0 0 0"
            % (width_m, LAT, _lon(east_a_m), LAT + 0.004, _lon(east_b_m)))


def _pavement(east_m, size_m=200.0, row=110):
    """A square whose WEST edge sits *east_m* metres east of lon -77."""
    w = _lon(east_m)
    e = _lon(east_m + size_m)
    (s, n) = (LAT, LAT + size_m / M_PER_DEG_LAT)
    head = "%d 1 0.25 0.0 PAV" % row
    return "\n".join([head,
                      "111 %.7f %.7f" % (s, w),
                      "111 %.7f %.7f" % (s, e),
                      "111 %.7f %.7f" % (n, e),
                      "113 %.7f %.7f" % (n, w)])


def _candidate(apt_dat, icao="ZZZZ"):
    return SEL.PatchCandidate(icao, "x.dat", {}, "patch", "", apt_dat)


def _classify(apt_dat, reach_m=None):
    return SEL.airport_boundary_class(
        _candidate(apt_dat), HOME[0], HOME[1],
        reach_m=SEL.ask_reach_m() if reach_m is None else reach_m)


# ── the five cases of §E test 6 ───────────────────────────────────────
def test_a_pavement_580_m_from_the_edge_is_class_M(tmp_path):
    """THE LPMT TWIN.  Its groundside crosses (measured 1.18 km of tail at
    HECA) and it still must NOT ask — the owner's Q2 answer, kept intact
    by rev 3's airside-claim geometry."""
    apt = _apt(tmp_path, "lpmt", _pavement(580.0))
    (cls, cells, crossing) = _classify(apt)
    assert (cls, cells, crossing) == ("M", [], 0.0)


def test_b_an_apron_60_m_from_the_edge_is_class_S(tmp_path):
    """Inside R_air (150 m), so the airside claim reaches the line."""
    apt = _apt(tmp_path, "apron", _pavement(60.0))
    (cls, cells, crossing) = _classify(apt)
    assert cls == "S"
    assert cells == [(-13, -78)]
    assert crossing > 0.0


def test_c_a_runway_rectangle_across_the_edge_is_class_S(tmp_path):
    apt = _apt(tmp_path, "rwy", _runway(-400.0, 900.0))
    (cls, cells, _crossing) = _classify(apt)
    assert cls == "S" and cells == [(-13, -78)]


def test_d_a_row_130_boundary_across_the_edge_is_class_M(tmp_path):
    """A fence line around grass is not the airport crossing (§C.1): row
    130 is excluded, and the pavement stops 400 m short."""
    body = "\n".join([_pavement(400.0), _pavement(-800.0, row=130)])
    apt = _apt(tmp_path, "fence", body)
    (cls, cells, _crossing) = _classify(apt)
    assert (cls, cells) == ("M", [])


def test_e_class_S_with_a_warm_neighbour_needs_no_decision(tmp_path):
    apt = _apt(tmp_path, "warm", _pavement(60.0))
    decide = SEL.boundary_skipper(HOME[0], HOME[1],
                                  is_cold=lambda cell: False)
    assert decide("ZZZZ", {}, _candidate(apt)) is None


def test_class_S_with_a_cold_neighbour_is_skipped_with_a_loud_reason(
        tmp_path):
    apt = _apt(tmp_path, "cold", _pavement(60.0))
    decide = SEL.boundary_skipper(HOME[0], HOME[1],
                                  is_cold=lambda cell: True)
    reason = decide("ZZZZ", {}, _candidate(apt))
    assert reason and "-13-078" in reason and "SKIPPED" in reason


# ── the invariant §C.3 rests on ───────────────────────────────────────
@pytest.mark.parametrize("east_m,expected", [
    (-400.0, "S"), (60.0, "S"), (149.0, "S"), (400.0, "M"), (580.0, "M")])
def test_preflight_and_build_time_agree_by_construction(tmp_path, east_m,
                                                        expected):
    """ONE function, ONE apt.dat.  The preflight (§C.2) and the build-time
    check (§C.3) call it with the same arguments, so 'an airport the
    preflight missed' is not a reachable state."""
    apt = _apt(tmp_path, "agree%d" % int(east_m + 1000), _pavement(east_m))
    preflight = _classify(apt)
    build_time = _classify(apt)
    assert preflight == build_time
    assert preflight[0] == expected


def test_a_candidate_without_an_apt_dat_never_asks():
    """It gets no patch (`no_apt_dat`), so it cannot be half-built."""
    assert SEL.airport_boundary_class(
        SEL.PatchCandidate("ZZZZ", "x", {}, "no_apt_dat", "", ""),
        HOME[0], HOME[1]) == ("M", [], 0.0)


def test_the_reach_is_the_confirmed_law_value():
    assert SEL.ask_reach_m() == 150.0


def test_crossing_m_is_how_far_past_the_line_the_claim_reaches(tmp_path):
    """The value `BoundaryAirportsReady.crossing_m` carries."""
    apt = _apt(tmp_path, "reach", _pavement(60.0))
    (_cls, _cells, crossing) = _classify(apt)
    # claim west edge 60 m east of the line, buffered by 150 m ⇒ ~90 m in.
    assert 80.0 < crossing < 100.0


def test_the_selector_marks_a_straddler_boundary_skipped(tmp_path,
                                                         monkeypatch):
    """End to end through `select_patch_airports`: class S + cold ⇒
    disposition `boundary_skipped`, never `patch`."""
    apt = _apt(tmp_path, "sel", _pavement(60.0))
    monkeypatch.setattr("auto_patch.cifp_reader.discover_cifp_airports",
                        lambda path: {"ZZZZ": "z.dat"})
    monkeypatch.setattr("auto_patch.cifp_reader.parse_cifp_file",
                        lambda path: {"09": {"lat": LAT, "lon": _lon(10.0)}})
    monkeypatch.setattr("auto_patch.cifp_reader.airport_in_tile",
                        lambda rw, lat, lon: True)
    monkeypatch.setattr("auto_patch.build_support.pair_runways",
                        lambda rw: [("09", 1, "27", 2)])
    monkeypatch.setattr("auto_patch.cifp_reader.xplane_root_from_cifp_path",
                        lambda path: "/fake")
    monkeypatch.setattr(
        "auto_patch.build_support._pick_best_apt_dat_against_osm",
        lambda root, icao, *a, **k: apt)
    import types

    tile = types.SimpleNamespace(lat=HOME[0], lon=HOME[1])
    selection = SEL.select_patch_airports(
        tile, "/cifp", "ICAO", manual_icaos=(),
        boundary=SEL.boundary_skipper(HOME[0], HOME[1],
                                      is_cold=lambda cell: True))
    assert [(c.icao, c.disposition) for c in selection] == [
        ("ZZZZ", "boundary_skipped")]
    assert SEL.patch_set(selection) == set()
