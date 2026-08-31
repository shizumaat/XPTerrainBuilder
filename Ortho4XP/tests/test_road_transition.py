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
    def __init__(self, polygon, role, alts=None, ref=""):
        self.polygon = polygon
        self.role = role
        self.ref = ref
        self.node_altitudes = alts
        self.station_cap_vector = None
        self.source_axis = None


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


# ── THE OWNERSHIP SHRINK (spec §3.3/§3.4) ───────────────────────────────

def _mint(lines, pav, **kw):
    from auto_patch.pavement.service_roads import build_service_road_network
    return build_service_road_network(lines, pav, width=6.0, min_len=8.0,
                                      **kw)


def test_without_a_scope_the_mint_is_unchanged():
    """``contact_scope=None`` keeps every course — the fixture path, and
    any caller with no airfield to be near."""
    pav = _rect(0.0, 0.0, 40.0, 40.0)
    far = geometry.LineString([(200.0, 20.0), (400.0, 20.0)])
    rects, _j = _mint([(far, "far")], pav)
    assert rects, "an unscoped mint still paves the whole course"


def test_a_course_beyond_the_contact_scope_leaves_the_patch():
    """THE SHRINK.  A road 200 m from any pavement is the CORE's now:
    auto_patch mints nothing for it, so no patch pavement, no road-family
    census rows, and the core's apt_area subtraction (census #104) hands
    it exactly this ground."""
    pav = _rect(0.0, 0.0, 40.0, 40.0)
    far = geometry.LineString([(200.0, 20.0), (400.0, 20.0)])
    scope = pav.buffer(float(SERVICE_ROAD_PAVEMENT_NEAR_M))
    own: dict = {}
    rects, junctions = _mint([(far, "far")], pav, contact_scope=scope,
                             ownership_out=own)
    assert not rects and not junctions
    assert own["released_to_core_m"] == pytest.approx(200.0, abs=1.0)
    assert own["kept_m"] == 0.0


def test_the_contact_stub_is_kept_and_the_rest_released():
    """A road running out of an apron keeps its CONTACT — the stub the
    transition profiler owns — and releases its course."""
    pav = _rect(0.0, 0.0, 40.0, 40.0)
    road = geometry.LineString([(40.0, 20.0), (300.0, 20.0)])
    scope = pav.buffer(float(SERVICE_ROAD_PAVEMENT_NEAR_M))
    own: dict = {}
    rects, junctions = _mint([(road, "svc")], pav, contact_scope=scope,
                             ownership_out=own)
    assert rects or junctions, "the contact stub must still be paved"
    # everything the mint keeps is inside the scope, to the metre
    for r, _axis, _role, _name in rects:
        assert r.difference(scope).area < 1.0
    assert 0.0 < own["kept_m"] < 40.0
    assert own["released_to_core_m"] > 200.0
    assert own["scoped"] is True


def test_the_scope_is_pavement_plus_asserted_bridge_and_tunnel_ways():
    """The seam with the CORE's own exclusion (census #106): the core
    refuses to level a way that ASSERTS bridge/tunnel and levels every
    other one, so auto_patch keeps exactly the tagged spans.  A
    ``bridge=no`` way is an ordinary road and belongs to the core."""
    from auto_patch.pipeline import _road_contact_scope

    def to_m(lon, lat):
        return (lon * 100000.0, lat * 100000.0)

    net = types.SimpleNamespace(
        nodes={1: (0.0, 5.0), 2: (0.0, 5.02),      # (lat, lon)
               3: (0.0, 9.0), 4: (0.0, 9.02)},
        ways=[("w1", [1, 2], {"highway": "service", "bridge": "yes"}),
              ("w2", [3, 4], {"highway": "service", "bridge": "no"})])
    lay = types.SimpleNamespace(airport_road_network=net)
    scope = _road_contact_scope(lay, None, to_m)
    assert scope is not None
    assert scope.contains(geometry.Point(500000.0, 0.0))     # the bridge
    assert not scope.contains(geometry.Point(900000.0, 0.0))  # bridge=no


def test_the_declaration_reaches_the_sidecar_reader():
    """Spec §3.4: the census must be able to READ the declared migration
    — otherwise a shrunken road population is indistinguishable from a
    silent drop (the OTHH −639 blindness verdict, census #90)."""
    sys.path.insert(0, str(_ROOT / "tools"))
    import check_grade as CG
    assert "road_ownership" in CG.SIDECAR_EVIDENCE_KEYS
    assert "road_ownership" not in CG.SIDECAR_LAW_KEYS
    src = (_ROOT / "src" / "auto_patch" / "layout.py").read_text()
    assert '"road_ownership": getattr(self, "_road_ownership", None),' in src


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


# ── BATCH 2b (RULINGS 31d) ──────────────────────────────────────────────

def test_the_carve_feed_is_clipped_to_the_SAME_contact_scope():
    """FINDING A, RULED.  ``carve_narrow_service_strips`` is the road
    family's SECOND minter: with only the mint clipped it still carved
    1,325 ref-less ``service_junction`` rings (511,207 m²) beyond 25 m of
    airside at HECA — the general road pavement RULINGS 31b hands to the
    core.  A far truck route now mints nothing and says so; a route in
    contact still carves."""
    from auto_patch.groundside import carve_narrow_service_strips

    apron = _Shape(_rect(0.0, 0.0, 60.0, 60.0), ROLE_APRON, [10.0] * 4)
    # a NARROW face the carve can cut, 600 m away from the apron
    far_face = _Shape(_rect(600.0, 0.0, 620.0, 200.0), ROLE_APRON,
                      [10.0] * 4)
    pav = geometry.MultiPolygon([apron.polygon, far_face.polygon])
    route = types.SimpleNamespace(
        line=geometry.LineString([(610.0, 5.0), (610.0, 195.0)]))
    lay = _layout([apron, far_face])
    lay.apt_service_centerlines = [route]
    scope = apron.polygon.buffer(float(SERVICE_ROAD_PAVEMENT_NEAR_M))

    own: dict = {}
    n = carve_narrow_service_strips(lay, pav, contact_scope=scope,
                                    ownership_out=own)
    assert n == 0, "a truck route 600 m from any pavement is the core's"
    assert own["carve_released_to_core_m"] > 150.0
    assert own["carve_kept_m"] == 0.0
    assert own["carve_scoped"] is True

    # …and the SAME route inside the scope still carves (the pass is
    # scoped, not disabled).
    near = types.SimpleNamespace(
        line=geometry.LineString([(610.0, 5.0), (610.0, 195.0)]))
    lay2 = _layout([apron, far_face])
    lay2.apt_service_centerlines = [near]
    own2: dict = {}
    n2 = carve_narrow_service_strips(
        lay2, pav, contact_scope=far_face.polygon.buffer(30.0),
        ownership_out=own2)
    assert n2 > 0, "a route in contact scope must still carve"
    assert own2["carve_kept_m"] > 150.0


def test_the_unscoped_carve_is_unchanged():
    """``contact_scope=None`` carves every route — the fixture path."""
    from auto_patch.groundside import carve_narrow_service_strips
    face = _Shape(_rect(600.0, 0.0, 620.0, 200.0), ROLE_APRON, [10.0] * 4)
    route = types.SimpleNamespace(
        line=geometry.LineString([(610.0, 5.0), (610.0, 195.0)]))
    lay = _layout([face])
    lay.apt_service_centerlines = [route]
    assert carve_narrow_service_strips(lay, face.polygon) > 0


def test_both_minters_read_ONE_derivation_of_the_scope():
    """One region, derived once and memoised on the layout: two
    derivations are two ownership boundaries."""
    src = (_ROOT / "src" / "auto_patch" / "pipeline.py").read_text()
    # the def plus exactly TWO call sites: the mint and the carve
    assert src.count("_road_contact_scope(layout, pav_union, to_m)") == 3
    assert src.count("def _road_contact_scope(") == 1
    assert "_road_contact_scope_cache" in src
    # the carve's far metres join the ONE declared migration
    assert "carve_released_to_core_m" in src
    assert '_own["released_to_core_m"] = round(' in src


def test_the_profiler_is_the_LAST_road_family_writer():
    """FINDING B, RULED.  ``who_wrote --at`` measured the conformance
    family moving a road value +2.14 m AFTER the writeback-seam call, so
    the profile a road emitted with was not the one the law wrote.  The
    profiler now re-runs after those passes; it is a clamp into its pins'
    envelope over a terrain base, so the second run is idempotent where
    nothing moved."""
    src = (_ROOT / "src" / "auto_patch" / "pipeline.py").read_text()
    i_conf = src.index("        _post_projection_conformance_passes()")
    i_rt = src.index("_rt2(layout, icao, dem=_dem_last")
    assert i_conf < i_rt, "the re-profile runs AFTER the conformance passes"
    # …and the writeback-seam call (the spec's own home) still stands.
    solve = (_ROOT / "src" / "auto_patch" / "elevation_per_surface"
             / "route_profile" / "solve.py").read_text()
    assert "solve_road_transitions(layout" in solve


def test_the_transition_profile_is_idempotent():
    """The property the re-run rests on: applying the law to its own
    output changes nothing."""
    s = [0.0, 10.0, 20.0, 25.0]
    base = [100.0, 100.4, 100.9, 101.2]
    pins = {0: 100.5}
    once, _ = RT.transition_profile(s, base, pins, CAP)
    twice, _ = RT.transition_profile(s, list(once), pins, CAP)
    assert twice == pytest.approx(once)
