"""Twin for the PAD-SEAT FEASIBILITY GATE (owner ruling RULINGS
2026-08-24c).

"A pad seat that cannot reach its governing centerline anchor within
1 % x chord is a SEAT DEFECT caught at seating time (anchor-placement law
analogue), NEVER surface debt."

The reach BAND is that test already computed: ``band(x, y)`` is the
interval of levels reachable at cap from the routes serving that point, so
"inside its own reach interval" is the question, and the gate asks it of
the seat the solve is about to ship.

REPORT-FIRST BY ORDER: nothing is moved this round, so the twin asserts
the RECORD and the read-out, never a changed seat.

Headless, no network, no X-Plane install.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.elevation_per_surface.route_profile import (   # noqa: E402
    anchors as A)


def test_a_seat_inside_its_reach_interval_is_not_a_defect():
    assert A.seat_feasibility_gap(7.0, 6.0, 8.0) == (0.0, None)
    assert A.seat_feasibility_gap(6.0, 6.0, 8.0) == (0.0, None)
    assert A.seat_feasibility_gap(8.0, 6.0, 8.0) == (0.0, None)


def test_a_seat_below_the_reach_floor_is_the_class_nothing_reported():
    """The small-pad path seats at ``min(dem_centroid, ceiling)`` — bounded
    ABOVE and not below — so a pad whose DEM centroid sits under the reach
    floor shipped below every level its frontage can reach, and no surface
    could honour it.  That is the class this gate exists for."""
    gap, side = A.seat_feasibility_gap(5.0, 6.0, 8.0)
    assert side == "below_floor"
    assert gap == pytest.approx(1.0)


def test_a_seat_above_the_reach_ceiling_is_reported_too():
    gap, side = A.seat_feasibility_gap(9.25, 6.0, 8.0)
    assert side == "above_ceiling"
    assert gap == pytest.approx(1.25)


def test_an_off_network_pad_has_no_governing_anchor_to_be_judged_against():
    """An infinite or absent interval means no governing centerline anchor.
    Inventing one would be the very long-pair class A4 exists to remove, so
    the gate declines rather than guessing."""
    assert A.seat_feasibility_gap(5.0, float("-inf"), 8.0) == (0.0, None)
    assert A.seat_feasibility_gap(5.0, 6.0, float("inf")) == (0.0, None)
    assert A.seat_feasibility_gap(5.0, None, 8.0) == (0.0, None)
    assert A.seat_feasibility_gap(5.0, 6.0, None) == (0.0, None)


def test_the_materiality_floor_is_the_standing_elevation_floor():
    """0.01 m — the convergence guards' elevation floor.  A residual under
    it is reported as PASS-with-residual, never iterated on."""
    assert A._SEAT_FEASIBILITY_TOL_M == pytest.approx(0.01)
    gap, _side = A.seat_feasibility_gap(5.9950, 6.0, 8.0)
    assert gap <= A._SEAT_FEASIBILITY_TOL_M


class _Layout:
    def __init__(self):
        self.lines = []

    def m_to_ll(self, x, y):
        return (30.0 + y * 1e-5, 31.0 + x * 1e-5)


def test_the_gate_publishes_records_and_moves_no_seat():
    lay = _Layout()
    recs = [
        {"ref": "building7", "seat_m": 5.0, "reach_lo_m": 6.0,
         "reach_hi_m": 8.0, "gap_m": 1.0, "side": "below_floor",
         "centroid": (10.0, 20.0), "area_m2": 400.0},
    ]
    A._publish_seat_infeasible(lay, recs, lay.lines.append)
    assert lay._pad_seat_infeasible == recs, (
        "the records must be published verbatim for the census")
    blob = "\n".join(lay.lines)
    assert "[pad-seat]" in blob and "building7" in blob
    assert "no seat" in blob and "moved" in blob, (
        "the read-out must say the round moves nothing")
    assert "SEAT DEFECT" in blob.upper(), (
        "a seat defect must never read as surface debt")


def test_no_records_publishes_an_empty_list_and_stays_quiet():
    lay = _Layout()
    A._publish_seat_infeasible(lay, [], lay.lines.append)
    assert lay._pad_seat_infeasible == []
    assert lay.lines == [], "a clean airport must not print a gate line"


def test_the_key_is_registered_as_CENSUS_EVIDENCE_not_law():
    """A seat defect is caught at seating time and is NOT surface debt, so
    the census REPORTS it and never adjudicates it — which is also what
    keeps this round's acceptance counts comparable with the last.  Every
    emitted sidecar key must appear in one of the two registers, and
    test_harness twin-asserts that."""
    import check_grade as CG
    assert "pad_seat_infeasible" in CG.SIDECAR_EVIDENCE_KEYS
    assert "pad_seat_infeasible" not in CG.SIDECAR_LAW_KEYS


# ── THE SCAFFOLD-DERIVED SEAT (RULINGS 2026-08-24c + 2026-08-08) ───────

def test_the_seat_is_the_chebyshev_centre_of_its_frontage_band():
    """"Pads seated at the elevation that enables the 1 % cap to the
    centerlines" — the level furthest from both bounds of the interval the
    governing centerline permits, NOT the DEM pulled into that interval.

    ONE function, shared with the apron membrane, so a pad and the apron
    around it are seated by the same arithmetic."""
    from auto_patch.elevation_per_surface.route_profile.scaffold_seed \
        import taut_level
    assert taut_level((100.0, 104.0)) == pytest.approx(102.0)
    # The old rule put a low-DEM pad on the floor and a high-DEM pad on the
    # ceiling; the new one puts both in the middle, independent of terrain.
    for dem in (10.0, 102.0, 900.0):
        assert min(max(dem, 100.0), 104.0) != taut_level((100.0, 104.0)) \
            or dem == 102.0


def test_the_new_seat_is_inside_its_reach_interval_by_construction():
    """Which closes the class the feasibility gate was written to catch:
    ``min(DEM, ceiling)`` was bounded above and not below, so a pad under
    its reach floor shipped unreachable.  A Chebyshev centre cannot."""
    from auto_patch.elevation_per_surface.route_profile.scaffold_seed \
        import taut_level
    for (lo, hi) in ((100.0, 104.0), (7.0, 7.0), (-3.0, 12.5)):
        seat = taut_level((lo, hi))
        assert lo - 1e-9 <= seat <= hi + 1e-9
        assert A.seat_feasibility_gap(seat, lo, hi) == (0.0, None)


def test_the_kill_switch_restores_the_dem_clamped_seat():
    from auto_patch import config as CFG
    assert CFG.PAD_SEAT_SCAFFOLD is True, "default ON in this lane"
    src = (_ROOT / "src" / "auto_patch" / "elevation_per_surface"
           / "building_feasibility.py").read_text()
    assert "if PAD_SEAT_SCAFFOLD:" in src
    assert "min(max(de, floor), ceil)" in src, (
        "the DEM-clamped seat must survive as the gated-off path")


def test_the_seat_move_table_is_published_and_named():
    lay = _Layout()
    recs = [{"ref": "building3", "was": 100.0, "now": 101.5,
             "area_m2": 900.0},
            {"ref": "building9", "was": 100.0, "now": 99.2,
             "area_m2": 400.0}]
    A._publish_seat_moves(lay, recs, lay.lines.append)
    assert lay._pad_seat_moved == recs
    blob = "\n".join(lay.lines)
    assert "[seat-scaffold]" in blob and "2 pad seat(s) MOVED" in blob
    assert "1 up, 1 down" in blob
    assert "building3" in blob


def test_no_moves_publishes_empty_and_stays_quiet():
    lay = _Layout()
    A._publish_seat_moves(lay, [], lay.lines.append)
    assert lay._pad_seat_moved == [] and lay.lines == []
