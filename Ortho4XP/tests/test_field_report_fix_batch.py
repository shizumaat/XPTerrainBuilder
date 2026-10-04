"""Field-report fix batch (Fable spec 2026-08-02): the four class-disjoint
laws, tested at their law functions and their readers.

Headless, no X-Plane install, no network: every case is synthetic geometry
or a pure law call.  Build-level behaviour (which shapes an emitter skips)
is covered by the battery arms, not here — what these tests pin is that the
LAW says what the ruling says and that the emitter and the validator read
the SAME law function.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_REPO, "src"), os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import config as CFG                     # noqa: E402
import check_grade as CG                                 # noqa: E402


# ── §A runway-strip wall inadmissibility ────────────────────────────

def _straight_runway_ring(length_m=3000.0, half_width_m=22.5):
    return [(0.0, -half_width_m), (length_m, -half_width_m),
            (length_m, half_width_m), (0.0, half_width_m)]


# ── §B drainage-spine law ───────────────────────────────────────────


# ── §C exact route legs + the chord gate ────────────────────────────

class _CL:
    is_service = False

    def __init__(self, pts):
        self.pts = pts


# ── §C3 transverse reader ───────────────────────────────────────────

def test_transverse_cap_mapping_follows_the_role_letter_law():
    assert CG._transverse_cap_for_seg_cap(CFG.TAXI_MAX_GRADE) == \
        pytest.approx(CFG.TAXI_MAX_GRADE)                 # C-F isotropic
    assert CG._transverse_cap_for_seg_cap(CFG.TAXI_MAX_GRADE_NARROW) == \
        pytest.approx(CFG.TAXI_MAX_TRANSVERSE_NARROW)     # A/B 3%∥ 2%⊥
    assert CG._transverse_cap_for_seg_cap(CFG.SERVICE_ROAD_MAX_GRADE) == \
        pytest.approx(CFG.SERVICE_ROAD_MAX_TRANSVERSE)


def _way(wid, role, nids, elevs, tags=None):
    return CG.Way(wid=wid, role=role, ref="", aeroway="", nids=list(nids),
                  elevs=list(elevs), tags=dict(tags or {"role": role}))


def test_transverse_check_flags_a_cross_corridor_step():
    """A 40 m-wide junction with a 4 m cross-fall, one straight axis down
    its middle: the transverse law must see it."""
    # 40 m wide, 200 m long corridor; z rises 4 m across.
    nodes = {"1": (0.0, 0.0), "2": (0.0, 0.0), "3": (0.0, 0.0),
             "4": (0.0, 0.0)}
    # place them via a fake ll_to_m so the metre frame is explicit
    coords = {"1": (0.0, -20.0), "2": (200.0, -20.0),
              "3": (200.0, 20.0), "4": (0.0, 20.0)}

    def ll_to_m(lat, lon):
        return coords[f"{int(lat)}"]

    nodes = {k: (float(k), 0.0) for k in coords}
    w = _way("-1", "junction", ["1", "2", "3", "4"],
             [100.0, 100.0, 104.0, 104.0])
    axes = [([(0.0, 0.0), (200.0, 0.0)], [0.015], None, 0)]
    vios, n_st, n_rows, n_shapes = CG._check_transverse_grade(
        [w], nodes, ll_to_m, axes)
    assert n_rows > 0 and n_shapes == 1
    assert vios, "a 4 m step across 40 m (10 %) must flag at a 1.5 % cap"
    assert vios[0].grade_pct == pytest.approx(10.0, abs=0.1)


def test_transverse_check_passes_a_lawful_cross_fall():
    coords = {"1": (0.0, -20.0), "2": (200.0, -20.0),
              "3": (200.0, 20.0), "4": (0.0, 20.0)}
    nodes = {k: (float(k), 0.0) for k in coords}

    def ll_to_m(lat, lon):
        return coords[f"{int(lat)}"]

    # 1.0 % across 40 m = 0.4 m — inside the 1.5 % cap.
    w = _way("-1", "junction", ["1", "2", "3", "4"],
             [100.0, 100.0, 100.4, 100.4])
    axes = [([(0.0, 0.0), (200.0, 0.0)], [0.015], None, 0)]
    vios, _n_st, n_rows, _n_shapes = CG._check_transverse_grade(
        [w], nodes, ll_to_m, axes)
    assert n_rows > 0
    assert not vios


# ── §B3 spine reader ────────────────────────────────────────────────

def test_spine_reader_flags_a_spine_at_its_lower_pavement_level():
    coords = {
        # two parallel taxiway slabs 100 m apart, at 100.0 and 97.0
        "1": (0.0, 0.0), "2": (200.0, 0.0), "3": (200.0, 20.0),
        "4": (0.0, 20.0),
        "5": (0.0, 120.0), "6": (200.0, 120.0), "7": (200.0, 140.0),
        "8": (0.0, 140.0),
        # the spine down the middle
        "9": (50.0, 70.0), "10": (150.0, 70.0),
    }
    nodes = {k: (float(k), 0.0) for k in coords}

    def ll_to_m(lat, lon):
        return coords[f"{int(lat)}"]

    a = _way("-1", "junction", ["1", "2", "3", "4"], [100.0] * 4)
    b = _way("-2", "junction", ["5", "6", "7", "8"], [97.0] * 4)
    dam = _way("-3", "", ["9", "10"], [97.5, 97.5],
               tags={"o4_feature": "gap_drainage_spine"})
    vios, n_checked, _short = CG._check_drainage_spine_below_pavement(
        [dam], [a, b], nodes, ll_to_m)
    assert n_checked == 2
    assert len(vios) == 2
    assert vios[0].de_m == pytest.approx(0.5)

    drains = _way("-4", "", ["9", "10"], [96.0, 96.0],
                  tags={"o4_feature": "gap_drainage_spine"})
    vios2, n2, short2 = CG._check_drainage_spine_below_pavement(
        [drains], [a, b], nodes, ll_to_m)
    assert n2 == 2 and not vios2 and short2 == 0


def test_parse_osm_can_hand_back_the_open_breakline_ways(tmp_path):
    """The ring-skip stays (a spine is not a pavement ring) but the ways
    are recoverable in the SAME parse for their own law."""
    osm = tmp_path / "p.osm"
    osm.write_text(
        "<?xml version='1.0'?>\n<osm version='0.6'>\n"
        "<node id='-1' lat='30.0000000' lon='31.0000000'>"
        "<tag k='alt_abs' v='10.0' /></node>\n"
        "<node id='-2' lat='30.0001000' lon='31.0000000'>"
        "<tag k='alt_abs' v='10.5' /></node>\n"
        "<node id='-3' lat='30.0001000' lon='31.0001000'>"
        "<tag k='alt_abs' v='10.5' /></node>\n"
        "<way id='-10'><nd ref='-1' /><nd ref='-2' /><nd ref='-3' />"
        "<tag k='o4_feature' v='gap_drainage_spine' /></way>\n"
        "</osm>\n", encoding="utf-8", newline="")
    feats = {}
    _nodes, ways = CG._parse_osm(osm, feature_out=feats)
    assert ways == []                                  # ring-skip kept
    assert len(feats["gap_drainage_spine"]) == 1
    assert feats["gap_drainage_spine"][0].elevs[:3] == [10.0, 10.5, 10.5]


# ── §D coverage check wiring ────────────────────────────────────────

