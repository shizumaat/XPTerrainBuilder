"""Twins for THE ROAD TRANSITION PROFILER (spec §3.2/§3.5).

The law being pinned here is the owner's, restated in RULINGS 31a/31b:
a road FOLLOWS TERRAIN up to its 8 % cap and is PINNED ONLY where it
meets airside pavement.  So the twins are, in order: the pin is exact,
the road away from the pin is the CORE's own clamp (one function, so the
handoff welds), a hill between two contacts is NOT flattened into their
chord (the retired chord branch), a chain with no contact is not touched
at all (the retired self-pins), the scope stops at the mint's own 25 m,
and no frozen — i.e. airside-carried — vertex is ever written.

Headless: shapely polygons, a namespace layout, no DEM file.
"""

from __future__ import annotations

import math
import sys
import types
from pathlib import Path

import pytest
from shapely import geometry

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import O4_Vector_Utils as VECT                                  # noqa: E402
from auto_patch import road_transition as RT                    # noqa: E402
from auto_patch.config import (SERVICE_ROAD_MAX_GRADE,          # noqa: E402
                               SERVICE_ROAD_PAVEMENT_NEAR_M)
from auto_patch.layout import (ROLE_SERVICE_ROAD,               # noqa: E402
                               ROLE_SERVICE_JUNCTION, ROLE_APRON)

CAP = SERVICE_ROAD_MAX_GRADE


# ── THE PROFILE LAW ITSELF ──────────────────────────────────────────────

def test_a_contact_pin_holds_exactly():
    """CONTACT IS VALUE (RULINGS 29c): the pinned station takes the
    airside number, to the bit, whatever the base says."""
    s = [0.0, 10.0, 20.0]
    t, over = RT.transition_profile(s, [100.0, 100.0, 100.0],
                                    {0: 103.5}, CAP)
    assert t[0] == pytest.approx(103.5)
    assert not over


def test_away_from_the_pin_the_road_is_the_CORE_clamp():
    """THE HANDOFF TWIN.  Past ``cap x distance`` the pin cannot reach,
    so the transition IS its base — and the base is the core's own
    function on the core's own law.  One function, so the two owners meet
    without a tolerance."""
    s = [0.0, 10.0, 20.0, 25.0]
    dem = [100.0, 100.4, 100.9, 101.2]          # ~4 %, cap-lawful
    base = list(VECT.cap_lipschitz_profile(s, dem, CAP))
    assert base == pytest.approx(dem)           # lawful terrain is itself
    # A contact 0.5 m above the terrain at station 0: within 8 % x 10 m
    # the pin binds, beyond it the road is the core's answer again.
    t, _ = RT.transition_profile(s, base, {0: 100.5}, CAP)
    assert t[0] == pytest.approx(100.5)
    assert t[-1] == pytest.approx(dem[-1])      # the OUTER END is the core's


def test_a_hill_between_two_contacts_is_not_chorded_flat():
    """THE RETIREMENT'S HEADLINE.  The retired chord branch made a
    bracketed station take the pin-to-pin interpolation EXACTLY — an
    8 %-lawful hill emitted dead flat between two welds (86 % of HECA's
    stations).  The envelope keeps the hill: it only clamps what the cap
    forbids."""
    s = [0.0, 25.0, 50.0, 75.0, 100.0]
    dem = [100.0, 101.5, 103.0, 101.5, 100.0]   # a 6 % hill, cap-lawful
    base = list(VECT.cap_lipschitz_profile(s, dem, CAP))
    t, _ = RT.transition_profile(s, base, {0: 100.0, 4: 100.0}, CAP)
    chord = 100.0
    assert t[2] > chord + 1.0, "the hill was chorded flat"
    assert t == pytest.approx(dem)


def test_an_over_cap_contact_pair_still_builds_to_both_contacts():
    """RULING 1 (kept): the weld outranks the cap.  Both contacts are met
    exactly and the excess is REPORTED, never reverted."""
    s = [0.0, 10.0, 20.0]
    t, over = RT.transition_profile(s, [100.0] * 3, {0: 100.0, 2: 105.0},
                                    CAP)
    assert over and over[0][2] == pytest.approx(0.25)
    assert t[0] == pytest.approx(100.0) and t[2] == pytest.approx(105.0)


def test_no_pins_is_no_law():
    """A stretch with no airside contact is the CORE's road, and this
    pass says nothing about it (the retired self-pins pinned every chain
    at its own ends — that is what made the pass universal)."""
    base = [100.0, 101.0, 99.0]
    t, over = RT.transition_profile([0.0, 10.0, 20.0], base, {}, CAP)
    assert t == pytest.approx(base) and not over


def test_the_scope_is_the_mints_own_constant():
    """The transition's domain and the road population the patch keeps
    are ONE region stated once (spec §3.2/§3.3)."""
    assert RT.TRANSITION_SCOPE_M() == float(SERVICE_ROAD_PAVEMENT_NEAR_M)


# ── THE PASS, ON A LAYOUT ───────────────────────────────────────────────

def _rect(x0, y0, x1, y1):
    return geometry.Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


class _Shape:
    def __init__(self, polygon, role, alts=None):
        self.polygon = polygon
        self.role = role
        self.node_altitudes = alts
        self.station_cap_vector = None


def _layout(shapes):
    return types.SimpleNamespace(
        shapes=list(shapes),
        canonical_points=None,
        m_to_ll=lambda x, y: (30.0 + y / 111320.0,
                              31.0 + x / 96000.0),
    )


def _ring_alts(shape):
    return [round(float(a), 3) for a in (shape.node_altitudes or [])]


def test_the_pass_writes_the_road_and_never_the_airside():
    """AIRSIDE IS KING, BY CONSTRUCTION.  The apron shares its edge with
    the road; the apron's values are untouched and the road's shared
    vertices keep the apron's number."""
    apron = _Shape(_rect(0.0, 0.0, 40.0, 40.0), ROLE_APRON,
                   [200.0, 200.0, 200.0, 200.0])
    # a 6 m wide road running 30 m out from the apron's east edge
    road = _Shape(_rect(40.0, 10.0, 70.0, 16.0), ROLE_SERVICE_ROAD,
                  [190.0, 190.0, 190.0, 190.0])
    lay = _layout([apron, road])
    before_apron = _ring_alts(apron)
    out = RT.solve_road_transitions(lay, "TEST")
    assert out["on"] and out["pins"] >= 1
    assert _ring_alts(apron) == before_apron
    assert out["moved"] >= 1


def test_a_road_with_no_airside_contact_is_left_to_the_core():
    """No contact ⇒ no pin ⇒ nothing written: the general road course is
    the core's and this pass has no standing over it."""
    road = _Shape(_rect(500.0, 500.0, 560.0, 506.0), ROLE_SERVICE_ROAD,
                  [190.0, 191.0, 192.0, 193.0])
    lay = _layout([road])
    before = _ring_alts(road)
    out = RT.solve_road_transitions(lay, "TEST")
    assert out["moved"] == 0 and out["pins"] == 0
    assert _ring_alts(road) == before


def test_nothing_beyond_the_scope_is_written():
    """The profiler stops at 25 m of ROAD GRAPH from its contact — the
    far end of a long corridor is the core's ground, and a pass that
    wrote it would be re-taking the ownership the redesign hands over."""
    apron = _Shape(_rect(0.0, 0.0, 40.0, 40.0), ROLE_APRON,
                   [200.0] * 4)
    # 400 m long: its far corners are ~400 m of ring away from the contact
    road = _Shape(_rect(40.0, 10.0, 440.0, 16.0), ROLE_SERVICE_ROAD,
                  [190.0, 150.0, 150.0, 190.0])
    lay = _layout([apron, road])
    RT.solve_road_transitions(lay, "TEST")
    alts = _ring_alts(road)
    # vertices 1 and 2 are the FAR end (x = 440) — untouched at 150.0
    assert alts[1] == pytest.approx(150.0)
    assert alts[2] == pytest.approx(150.0)


def test_the_transition_takes_the_terrain_where_the_cap_allows():
    """The pass's own DEM path: with terrain under it, the road away from
    the contact follows the ground (clamped by the core's function), and
    the contact end still holds the airside value exactly."""
    apron = _Shape(_rect(0.0, 0.0, 40.0, 40.0), ROLE_APRON, [200.0] * 4)
    road = _Shape(_rect(40.0, 10.0, 60.0, 16.0), ROLE_SERVICE_ROAD,
                  [190.0, 190.0, 190.0, 190.0])
    lay = _layout([apron, road])

    import auto_patch.elevation as EL
    real = EL._sample_dem
    # terrain at 199.0 everywhere: 1 m under the apron edge, reachable
    # inside 8 % x the road's own length.
    EL._sample_dem = lambda dem, tlat, tlon, lat, lon: 199.0
    try:
        out = RT.solve_road_transitions(lay, "TEST", dem=object())
    finally:
        EL._sample_dem = real
    assert out["dem_stations"] > 0
    alts = _ring_alts(road)
    assert min(alts) == pytest.approx(199.0, abs=0.6), alts


def test_the_pass_publishes_its_report():
    apron = _Shape(_rect(0.0, 0.0, 40.0, 40.0), ROLE_APRON, [200.0] * 4)
    road = _Shape(_rect(40.0, 10.0, 70.0, 16.0), ROLE_SERVICE_ROAD,
                  [190.0] * 4)
    lay = _layout([apron, road])
    RT.solve_road_transitions(lay, "TEST")
    rep = getattr(lay, "_road_transition_report", None)
    assert rep and rep["scope_m"] == float(SERVICE_ROAD_PAVEMENT_NEAR_M)


# ── THE RETIREMENT IS REAL ──────────────────────────────────────────────

def test_free_road_profile_is_gone():
    """RULINGS 31b + 29f: the chord/self-pin model is DELETED, not gated
    — no module, no flags, no call site."""
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("auto_patch.free_road_profile")
    from auto_patch import config as CFG
    for name in ("FREE_ROAD_PROFILE_PASS", "FREE_ROAD_PROFILE_PRESOLVE",
                 "FREE_ROAD_PROFILE_RESOLVE", "FREE_ROAD_PROFILE_SELF_PINS"):
        assert not hasattr(CFG, name), name
    src = (_ROOT / "src" / "auto_patch" / "pipeline.py").read_text()
    assert "solve_free_road_profiles" not in src


def test_the_profiler_is_installed_at_the_writeback_seam():
    """Spec §3.5: the pinned-transition law lives at the solver's final
    writeback, downstream of the mouth reseat — the airside-final moment,
    and the point every road-altitude writer converges at."""
    src = (_ROOT / "src" / "auto_patch" / "elevation_per_surface"
           / "route_profile" / "solve.py").read_text()
    i_reseat = src.index("_reseat_service_mouths(")
    i_wb = src.rindex("_writeback(layout, elev, b2i)")
    i_call = src.index("solve_road_transitions(layout")
    assert i_reseat < i_wb < i_call
