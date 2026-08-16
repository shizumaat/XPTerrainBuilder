"""THE ANCHOR LAW: ride never enters an anchor — the generation-binding twin.

Spec: ``docs/specs/cycle4-anchor-law-spec.md`` (cycle-4 target #2).

THE DEFECT THIS CLOSES.  A runway profile's interior stations are a
DEM-FOLLOW SEED: ``runway_segments.generate_patch_osm`` seats every
non-anchored station at ``clamp(DEM, law_baseline ± min(BAND, ½·K·d²))``.
That is lawful SEATING — DEM choosing where inside the band the profile
sits (RULINGS 2026-08-05: DEM is a seed).  But ``grade_graph._runway_anchors``
VALUE-SAMPLES the emitted runway surface where a taxi route joins the runway
and publishes that sample as a HARD band anchor, so the seating ride — up to
±10 m of world-dependent DEM follow — became LAW for every band seeded from
the join (measured: +20.000 m world-to-world on 71/75 stations of HECA
05C/23C; the canyon's 3,169-node ``BandInversionError`` class carried ~6.0 m
of pure ride).

THE FIX UNDER TEST.  Every taxi-join station is inserted into the profile's
zero-band set VALUED AT THE LAW LINE (the anchored-station interpolation)
before the DEM blend consumes it.  Two consequences are asserted
here, both generation-binding (the real emitter is driven, not a source
grep):

  A. WORLD-INVARIANCE — the same join station reads the SAME value in the
     two constant-DEM worlds (DEM ≡ 0 and DEM ≡ 10 000 m), while the free
     interior stations still ride, so the twin proves the ride EXISTS and
     that the anchor is nonetheless clean.
  B. ZERO BASELINE CHANGE — an inserted station is COLLINEAR with the law
     line by construction, so it changes the baseline by exactly zero: its
     value is the linear interpolation between the flanking CIFP anchors,
     and the thresholds themselves are untouched.

The station is seated on the law line by giving it a ZERO DEM BAND, and it
stays FREE — a join carries no authority of its own, so anchoring it would
bound the runway flex (the self-anchor lock) and freeze it off the law line
after any later lawful move.  See the deviation note in
``runway_segments.generate_patch_osm``.

Plus the SINGLE-AUTHORITY twin: the join set comes from
``grade_law.runway_join_contacts``, and both consumers (the runway profile
seeder's feed in ``elevation._runway_join_stations`` and the graph's
``grade_graph._runway_anchors``) call it rather than re-deriving "where a
join is".

R8 STAGE 1 (spec ``docs/specs/r8-runway-seeding-spec.md``) widens both halves
of the law above, and its twins are sections C-bis and D here:

  (a) A CROSSING IS A JOIN.  ``runway_join_contacts`` enumerated centreline
      ENDPOINTS only, so a taxi route running THROUGH a runway minted no
      contact and the runway kept its DEM-follow ride at every crossing.  Two
      parallel runways therefore rode their own cross-field fall
      independently — KAFW's 16L/34R vs 16R/34L came out 2.333 m apart across
      a 136 m connector whose route budget is 2.046 m, a 9-node inverted band
      that REFUSED the build.
  (b) THE SEAT SURVIVES.  A seat was computed once, at emit time, and left
      FREE; ``faa_joint_solve`` could drag it, and ``runway_redistribute``
      then moved the law line under it (seam anchors, threshold shift) without
      ever revisiting it.  ``seat_law_stations`` re-values every seat on the
      CURRENT law line and ``solve_anchor_set`` holds them through the gates —
      still never publishing them in ``anchored``, which is the self-anchor
      lock.  Measured at KAFW: 21 joins re-seated by up to +1.90 m.
  (c) The two-runway connector fixture, synthetic: with (a)+(b) the transverse
      spread the connector must span collapses to the LAW spread.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch.pavement import runway_segments as RS


class _FlatDEM:
    """A DEM that answers one constant elevation everywhere (the oracle's
    two worlds: an artificial plateau and an impossibly deep canyon)."""

    def __init__(self, value):
        self.value = value

    def alt(self, _lonlat):
        return self.value


class _Tile:
    def __init__(self, lat, lon, dem):
        self.lat = lat
        self.lon = lon
        self.dem = dem


_LAT, _LON = 30.11, 31.40
_DLAT = _DLON = 0.0116          # ~1.8 km on a NE heading
_CIFP_A_M = 100.0
_CIFP_B_M = 104.0
_PAIR_KEY = ("RW05", "RW23")

# The two constant-DEM worlds (RULINGS 2026-08-05, the constant-DEM
# invariant): floor seating and ceiling seating of the same geometry.
_WORLD_LOW = 0.0
_WORLD_HIGH = 10000.0


def _pair():
    return [(
        "RW05", {"lat": _LAT, "lon": _LON, "elevation_m": _CIFP_A_M,
                 "displaced_m": 0.0},
        "RW23", {"lat": _LAT + _DLAT, "lon": _LON + _DLON,
                 "elevation_m": _CIFP_B_M, "displaced_m": 0.0},
    )]


def _at(t: float):
    """The lat/lon of centreline fraction ``t``."""
    return (_LAT + t * _DLAT, _LON + t * _DLON)


def _law_line(t: float) -> float:
    """The law line, re-derived INDEPENDENTLY of the emitter's own
    ``_anchor_profile``: linear interpolation over the anchored stations of a
    profile built WITHOUT any join insertion.  (The profile's end anchors sit
    at the PHYSICAL runway ends, whose values are the published CIFP
    thresholds carried out along the profile — a few cm off the thresholds
    themselves — so a hand-written 100→104 line is not the baseline.)"""
    ref = _reference_profile()
    anchors = [(f, e) for (f, e, a) in
               zip(ref["fractions"], ref["elevs"], ref["anchored"]) if a]
    anchors.sort()
    if t <= anchors[0][0]:
        return anchors[0][1]
    if t >= anchors[-1][0]:
        return anchors[-1][1]
    for k in range(len(anchors) - 1):
        f0, e0 = anchors[k]
        f1, e1 = anchors[k + 1]
        if f0 <= t <= f1:
            return e0 + (t - f0) / (f1 - f0) * (e1 - e0)
    return anchors[-1][1]


_REF_CACHE: dict = {}


def _reference_profile():
    if "ref" not in _REF_CACHE:
        _REF_CACHE["ref"] = _build(_WORLD_HIGH)
    return _REF_CACHE["ref"]


def _build(dem_value, join_ts=(), break_ts=()):
    """Drive the real emitter in one constant-DEM world.  ``join_ts`` become
    taxi-join contacts, ``break_ts`` become ordinary (non-anchored) pavement
    breaks so the DEM-follow ride has somewhere to show."""
    pairs = _pair()
    tile = _Tile(30.0, 31.0, _FlatDEM(dem_value))
    kwargs = {}
    if join_ts:
        kwargs["join_stations"] = {_PAIR_KEY: [_at(t) for t in join_ts]}
    if break_ts:
        kwargs["pav_intersections"] = {_PAIR_KEY: [_at(t) for t in break_ts]}
    _xml, _chain, state = RS.generate_patch_osm(
        "TEST", pairs, tile=tile, **kwargs)
    return state[_PAIR_KEY]


def _station(state, t, *, tol=0.05):
    """The ``(fraction, elev, anchored)`` of the profile station nearest the
    requested centreline fraction.  The emitter parametrises by the PHYSICAL
    runway ends, not by the threshold pair the test lays points on, so the
    station's own fraction (returned) is what any law-line comparison must
    use."""
    best = None
    for i, f in enumerate(state["fractions"]):
        d = abs(f - t)
        if best is None or d < best[0]:
            best = (d, i)
    assert best is not None and best[0] <= tol, (
        f"no profile station within {tol} of t={t}: "
        f"{[round(f, 4) for f in state['fractions']]}")
    i = best[1]
    return state["fractions"][i], state["elevs"][i], state["anchored"][i]


# ── A. the join station is world-invariant; the free stations are not ────────

def test_join_station_is_anchored_and_identical_in_both_worlds():
    low = _build(_WORLD_LOW, join_ts=(0.5,), break_ts=(0.25, 0.75))
    high = _build(_WORLD_HIGH, join_ts=(0.5,), break_ts=(0.25, 0.75))

    lo_f, lo_v, lo_anch = _station(low, 0.5)
    hi_f, hi_v, hi_anch = _station(high, 0.5)

    assert lo_f == pytest.approx(hi_f, abs=1e-12)
    assert not lo_anch and not hi_anch, (
        "a join station carries NO authority of its own — anchoring it "
        "bounds the runway flex (the self-anchor lock) and freezes it off "
        "the law line after any later lawful move")
    assert lo_v == pytest.approx(hi_v, abs=1e-9), (
        f"join station moved {hi_v - lo_v:+.4f} m between the two "
        f"constant-DEM worlds — ride is still entering the anchor")
    assert lo_v == pytest.approx(_law_line(lo_f), abs=1e-6), (
        f"join station at {lo_v:.6f} m is not the law line "
        f"({_law_line(lo_f):.6f} m)")


def test_the_free_interior_stations_do_still_ride():
    """The control: without it, world-invariance at the join could be an
    artefact of a profile with no seating freedom at all."""
    low = _build(_WORLD_LOW, join_ts=(0.5,), break_ts=(0.25, 0.75))
    high = _build(_WORLD_HIGH, join_ts=(0.5,), break_ts=(0.25, 0.75))
    _lo_f, lo_v, lo_anch = _station(low, 0.25)
    _hi_f, hi_v, hi_anch = _station(high, 0.25)
    assert not lo_anch and not hi_anch
    assert abs(hi_v - lo_v) > 0.01, (
        "the free station did not ride between the two worlds — this twin "
        "no longer proves anything about the anchor")


def test_every_join_station_in_a_multi_join_profile_is_clean():
    joins = (0.2, 0.45, 0.8)
    low = _build(_WORLD_LOW, join_ts=joins, break_ts=(0.6,))
    high = _build(_WORLD_HIGH, join_ts=joins, break_ts=(0.6,))
    for t in joins:
        _lo_f, lo_v, lo_anch = _station(low, t)
        _hi_f, hi_v, hi_anch = _station(high, t)
        assert not lo_anch and not hi_anch, (
            f"join at t={t} was anchored — it must stay FREE (see the "
            f"self-anchor lock note in runway_segments)")
        assert lo_v == pytest.approx(hi_v, abs=1e-9), (
            f"join at t={t} moved {hi_v - lo_v:+.4f} m between worlds")


# ── B. a collinear inserted station changes the law baseline by ZERO ─────────

def test_inserted_join_station_is_collinear_with_the_law_line():
    """The baseline is already linear between flanking anchors, so a station
    valued ON it adds no information and changes nothing."""
    state = _build(_WORLD_HIGH, join_ts=(0.2, 0.45, 0.8))
    for t in (0.2, 0.45, 0.8):
        f, v, anchored = _station(state, t)
        assert not anchored
        assert v == pytest.approx(_law_line(f), abs=1e-6), (
            f"inserted station at t={f:.4f} sits {v - _law_line(f):+.8f} m "
            f"off the law line — not collinear, so it MOVED the baseline")


def test_the_thresholds_are_untouched_by_the_insertion():
    without = _build(_WORLD_HIGH)
    with_joins = _build(_WORLD_HIGH, join_ts=(0.2, 0.45, 0.8))
    assert with_joins["elevs"][0] == pytest.approx(
        without["elevs"][0], abs=1e-9)
    assert with_joins["elevs"][-1] == pytest.approx(
        without["elevs"][-1], abs=1e-9)
    # (the end anchors sit at the PHYSICAL ends, a few cm off the published
    # thresholds by the profile's own carry-out; CIFP absoluteness itself is
    # twinned in ``test_cifp_threshold_is_absolute.py``.)
    assert with_joins["elevs"][0] == pytest.approx(_CIFP_A_M, abs=0.1)
    assert with_joins["elevs"][-1] == pytest.approx(_CIFP_B_M, abs=0.1)


def test_a_join_landing_on_a_threshold_is_dropped_not_duplicated():
    """A join within the anchor-dedup radius of a CIFP threshold must not
    mint a second station there — the threshold already carries a law value
    (and CIFP thresholds are absolute for v1)."""
    state = _build(_WORLD_HIGH, join_ts=(0.0005,))
    ref = _reference_profile()
    assert state["elevs"][0] == pytest.approx(ref["elevs"][0], abs=1e-9)
    assert sum(1 for f in state["fractions"] if f < 0.002) == 1


# ── C. one authority for "where a join is" ───────────────────────────────────

def test_runway_join_contacts_returns_the_edge_crossing():
    from shapely.geometry import LineString, Polygon

    from auto_patch import grade_law as GL

    class _Shape:
        def __init__(self, polygon, ref):
            self.polygon = polygon
            self.ref = ref

    # A 60 m-wide runway along the x axis; a taxi route running in from the
    # south and ENDING on the centreline (the wide-runway case the contact
    # law exists for).
    rwy = _Shape(Polygon([(-500, -30), (500, -30), (500, 30), (-500, 30)]),
                 "09/27")
    ln = LineString([(0, -200), (0, 0)])
    got = GL.runway_join_contacts([ln], [rwy])
    assert len(got) == 1, got
    (shape, (cx, cy), (ex, ey)) = got[0]
    assert shape is rwy
    assert (ex, ey) == (0.0, 0.0), "the endpoint is reported verbatim"
    assert cy == pytest.approx(-30.0, abs=1e-6), (
        "the CONTACT must be the runway EDGE crossing, not the deep-interior "
        "centreline endpoint")


def test_a_route_that_never_reaches_the_runway_is_not_a_join():
    from shapely.geometry import LineString, Polygon

    from auto_patch import grade_law as GL

    class _Shape:
        def __init__(self, polygon, ref):
            self.polygon = polygon
            self.ref = ref

    rwy = _Shape(Polygon([(-500, -30), (500, -30), (500, 30), (-500, 30)]),
                 "09/27")
    ln = LineString([(0, -200), (0, -100)])   # stops 70 m short
    assert GL.runway_join_contacts([ln], [rwy]) == []


def test_a_crossing_mints_a_join_contact_at_each_edge():
    """R8 stage 1 twin (a).  A taxi route that CROSSES a runway joins it at
    BOTH edge crossings — the emitted taxi node is welded to the runway edge
    there exactly as at a terminating endpoint.  Enumerating endpoints only
    left every through-crossing free, and that is where KAFW's two parallel
    runways rode their own cross-field fall (spec
    ``docs/specs/r8-runway-seeding-spec.md``)."""
    from shapely.geometry import LineString, Polygon

    from auto_patch import grade_law as GL

    class _Shape:
        def __init__(self, polygon, ref):
            self.polygon = polygon
            self.ref = ref

    # Two parallel 60 m-wide runways along the y axis, 136 m apart (KAFW's
    # connector length), and ONE connector taxi route running clean through
    # both of them — no endpoint anywhere near either runway.
    rwy_a = _Shape(Polygon([(-30, -900), (30, -900), (30, 900), (-30, 900)]),
                   "16L/34R")
    rwy_b = _Shape(Polygon([(106, -900), (166, -900), (166, 900),
                            (106, 900)]), "16R/34L")
    connector = LineString([(-200, 0), (340, 0)])

    got = GL.runway_join_contacts([connector], [rwy_a, rwy_b])
    by_shape: dict = {}
    for (shape, contact, _endpoint) in got:
        by_shape.setdefault(shape.ref, []).append(contact)
    assert sorted(by_shape) == ["16L/34R", "16R/34L"], (
        f"a route crossing both runways must join both: {by_shape}")
    for ref, contacts in by_shape.items():
        xs = sorted(round(cx, 6) for (cx, _cy) in contacts)
        assert len(contacts) == 2, (
            f"{ref}: a through-crossing joins at BOTH edges, got {contacts}")
        assert all(abs(cy) < 1e-6 for (_cx, cy) in contacts)
        expect = ([-30.0, 30.0] if ref == "16L/34R" else [106.0, 166.0])
        assert xs == pytest.approx(expect, abs=1e-6), (
            f"{ref}: contacts must sit ON the runway edges, got {xs}")

    # The kill switch reverts to the endpoint-only set (nothing at all here).
    assert GL.runway_join_contacts([connector], [rwy_a, rwy_b],
                                   crossings=False) == []


def test_a_crossing_that_is_also_an_endpoint_is_not_reported_twice():
    """The contact a terminating endpoint resolves to IS an edge crossing;
    reporting it once from each rule would double-anchor the same station."""
    from shapely.geometry import LineString, Polygon

    from auto_patch import grade_law as GL

    class _Shape:
        def __init__(self, polygon, ref):
            self.polygon = polygon
            self.ref = ref

    rwy = _Shape(Polygon([(-500, -30), (500, -30), (500, 30), (-500, 30)]),
                 "09/27")
    ln = LineString([(0, -200), (0, 0)])          # ends on the centreline
    got = GL.runway_join_contacts([ln], [rwy])
    assert len(got) == 1, (
        f"the endpoint contact and the edge crossing it resolves to are ONE "
        f"join: {got}")
    assert got[0][1][1] == pytest.approx(-30.0, abs=1e-6)


# ── D. the law seat SURVIVES every later solve (R8 stage 1) ──────────────────

def test_the_gates_hold_a_law_seat_that_a_bare_solve_would_drag():
    """R8 stage 1 twin (b), at the mechanism.  A law-seated station is FREE in
    the published ``anchored`` set (anchoring it is the self-anchor lock), so
    ``faa_joint_solve`` was free to drag it off the law line and the
    neighbours' DEM ride came back at the join.  Handing the gates
    ``solve_anchor_set(anchored, seated)`` holds it; ``seat_law_stations``
    re-values it on the law line first."""
    # A level law line over 3 km, a seat 150 m in from the threshold, and a
    # free neighbour 450 m further along carrying +30 m of DEM ride.  The
    # envelope leaves the neighbour high, and the grade cap between it and the
    # seat then binds — the seat is the only thing that can move, so the ride
    # walks straight into it.
    phys_dist = 3000.0
    fractions = [0.0, 0.05, 0.20, 1.0]
    anchored = [True, False, False, True]
    seated = [False, True, False, False]
    ride = [100.0, 100.0, 130.0, 100.0]
    law = 100.0

    # The seat starts ON the law line (the zero DEM band gave it no ride).
    assert RS.law_line_at(fractions, ride, anchored, 0.05) == pytest.approx(
        law, abs=1e-12)

    dragged = list(ride)
    RS.faa_joint_solve(fractions, dragged, anchored, phys_dist)
    held = list(ride)
    RS.faa_joint_solve(fractions, held,
                       RS.solve_anchor_set(anchored, seated), phys_dist)

    assert abs(dragged[1] - law) > 0.01, (
        "the control no longer drags the seat — this twin proves nothing")
    assert held[1] == pytest.approx(law, abs=1e-9), (
        f"the law seat moved {held[1] - law:+.4f} m through the joint "
        f"solve — the ride is back at the join")
    # The free neighbour yields instead, which is the whole point.
    assert abs(held[2] - dragged[2]) > 0.01
    # The seat is not published as an anchor: that is the self-anchor lock.
    assert anchored[1] is False


def test_the_seat_follows_the_law_line_the_seam_anchors_move():
    """R8 stage 1 twin (b), at the redistribute.  ``runway_redistribute``
    folds tile-seam DEM anchors into the profile, which MOVES the law line;
    the join follows the law line by definition, but the seat was computed
    once at emit time and never revisited, so the join stayed where the old
    line was.  Measured at KAFW: 21 joins re-seated by up to +1.90 m."""
    from auto_patch import runway_redistribute as RR

    def _fixture():
        return ([0.0, 0.5, 1.0], [100.0, 100.0, 100.0],
                [True, False, True], [False, True, False])

    # A seam anchor lands at t=0.75 carrying its DEM value: the law line
    # between the threshold and the seam now runs 100 → 108.
    control_f, control_e, control_a, control_s = _fixture()
    RR._insert_seam_anchors(control_f, control_e, control_a,
                            [(0.75, 108.0)], seated=control_s)
    new_law = RS.law_line_at(control_f, control_e, control_a, 0.5)
    assert new_law == pytest.approx(105.3333333, abs=1e-6)
    RS.faa_joint_solve(control_f, control_e, control_a, 4000.0)
    i = control_f.index(0.5)
    assert abs(control_e[i] - new_law) > 0.01, (
        "the control no longer strands the seat — this twin proves nothing")

    f, e, a, s = _fixture()
    RR._insert_seam_anchors(f, e, a, [(0.75, 108.0)], seated=s)
    assert s == [False, True, False, False], (
        "the seated flags must stay index-aligned through the insert")
    RS.seat_law_stations(f, e, a, s)
    RS.faa_joint_solve(f, e, RS.solve_anchor_set(a, s), 4000.0)
    j = f.index(0.5)
    assert e[j] == pytest.approx(new_law, abs=1e-9), (
        f"the seat is {e[j] - new_law:+.4f} m off the law line the seam "
        f"anchors moved it to")
    assert a[j] is False


def test_a_seam_landing_on_a_seat_takes_the_station_over():
    """Real authority wins: a tile-seam DEM anchor on a law-seated station
    anchors it and clears the seat, so nothing re-values it afterwards."""
    from auto_patch import runway_redistribute as RR

    f = [0.0, 0.5, 1.0]
    e = [100.0, 100.0, 100.0]
    a = [True, False, True]
    s = [False, True, False]
    RR._insert_seam_anchors(f, e, a, [(0.5, 107.0)], seated=s)
    assert f == [0.0, 0.5, 1.0]
    assert a == [True, True, True]
    assert s == [False, False, False]
    assert e[1] == 107.0
    assert RS.seat_law_stations(f, e, a, s) == 0


def test_seat_law_stations_is_collinear_and_moves_only_seats():
    """Re-seating adds no information: the law line is linear between the
    flanking anchors, so a seat valued on it changes no grade the anchors did
    not already imply — which is why the gates may hold it."""
    fractions = [0.0, 0.4, 1.0]
    anchored = [True, False, True]
    seated = [False, True, False]
    elevs = [100.0, 107.0, 110.0]
    n = RS.seat_law_stations(fractions, elevs, anchored, seated)
    assert n == 1
    assert elevs == pytest.approx([100.0, 104.0, 110.0], abs=1e-12)
    # An anchored station is never re-seated, and neither is a free one.
    elevs2 = [100.0, 107.0, 110.0]
    assert RS.seat_law_stations(fractions, elevs2, anchored,
                                [False, False, False]) == 0
    assert elevs2 == [100.0, 107.0, 110.0]


class _CrossFallDEM:
    """A DEM that falls across the field: constant along each runway, so the
    two parallel runways see two DIFFERENT constant elevations (KAFW's real
    cross-field fall, which each runway followed independently)."""

    def __init__(self, lon_ref, per_deg, base):
        self.lon_ref = lon_ref
        self.per_deg = per_deg
        self.base = base

    def alt(self, lonlat):
        dlon, _dlat = lonlat
        return self.base + self.per_deg * (dlon - self.lon_ref)


_C_LAT = 32.95
_C_LON = -97.32
_C_DLAT = 0.0116                       # ~1.29 km runway
_C_SEP_DEG = 0.001412                  # ~136 m: KAFW's connector
_C_CIFP_A, _C_CIFP_B = 200.0, 202.0
_C_BUDGET_M = 2.046                    # 1.5 % taxi cap over the connector


def _parallel_pair(lon):
    return [(
        "RW16L", {"lat": _C_LAT, "lon": lon, "elevation_m": _C_CIFP_A,
                  "displaced_m": 0.0},
        "RW34R", {"lat": _C_LAT + _C_DLAT, "lon": lon,
                  "elevation_m": _C_CIFP_B, "displaced_m": 0.0},
    )]


_C_CROSS_T = 0.35                      # where the connector crosses


def _parallel_state(lon, dem, join_t=None):
    """One runway of the synthetic KAFW pair, solved through the real
    emitter.  ``join_t`` is the connector's crossing fraction.

    The runway profile is SPARSE (ends + thresholds + pavement joins), so the
    crossing station exists in BOTH arms as a pavement break — the treated arm
    only adds the JOIN authority to it.  That keeps the control and the
    treatment the same profile geometry, so the spread is the mechanism and
    not a different sample set."""
    key = ("RW16L", "RW34R")
    tile = _Tile(32.0, -98.0, dem)
    kwargs = {}
    if join_t is not None:
        kwargs["join_stations"] = {
            key: [(_C_LAT + join_t * _C_DLAT, lon)]}
    kwargs["pav_intersections"] = {
        key: [(_C_LAT + t * _C_DLAT, lon) for t in (_C_CROSS_T, 0.7)]}
    _xml, _chain, state = RS.generate_patch_osm(
        "TEST", _parallel_pair(lon), tile=tile, **kwargs)
    return state[key]


def _value_at(state, t):
    f, v, _a = _station(state, t, tol=0.06)
    return f, v


def test_the_two_runway_connector_fixture_solves():
    """R8 stage 1 twin (c) — the KAFW class, synthetic.

    Two parallel runways 136 m apart on a real cross-field fall, published at
    the SAME CIFP elevations, and a connector taxi route crossing both.  The
    connector's route budget is 1.5 % × 136 m = 2.046 m.  With the crossing
    minting a join on each runway (twin (a)) and the seat surviving the solve
    (twin (b)), both crossings sit on their own law line and the transverse
    spread the connector must span collapses to the LAW spread.  Without the
    joins each runway follows its own side of the fall and the spread exceeds
    the budget — the band inversion that refused KAFW."""
    lon_a = _C_LON
    lon_b = _C_LON + _C_SEP_DEG
    # ±3 m of cross-field fall over the 136 m separation.
    dem = _CrossFallDEM(lon_ref=0.5 * (lon_a + lon_b) + 98.0,
                        per_deg=-6.0 / _C_SEP_DEG,
                        base=0.5 * (_C_CIFP_A + _C_CIFP_B))

    # CONTROL: no join at the crossing — each runway rides its own fall.
    free_a = _parallel_state(lon_a, dem)
    free_b = _parallel_state(lon_b, dem)
    _fa, va = _value_at(free_a, _C_CROSS_T)
    _fb, vb = _value_at(free_b, _C_CROSS_T)
    free_spread = abs(va - vb)
    assert free_spread > _C_BUDGET_M, (
        f"the control spread {free_spread:.3f} m no longer exceeds the "
        f"{_C_BUDGET_M:.3f} m connector budget — this twin proves nothing")

    # TREATED: the crossing is a join on both runways.
    join_a = _parallel_state(lon_a, dem, join_t=_C_CROSS_T)
    join_b = _parallel_state(lon_b, dem, join_t=_C_CROSS_T)
    fa, va = _value_at(join_a, _C_CROSS_T)
    fb, vb = _value_at(join_b, _C_CROSS_T)
    spread = abs(va - vb)
    assert spread <= _C_BUDGET_M, (
        f"the crossing spread {spread:.3f} m still exceeds the connector's "
        f"{_C_BUDGET_M:.3f} m route budget — the pair is infeasible")
    # And each side is ON its own law line, not merely closer together.
    for state, f, v in ((join_a, fa, va), (join_b, fb, vb)):
        law = RS.law_line_at(state["fractions"], state["elevs"],
                             state["anchored"], f)
        assert v == pytest.approx(law, abs=1e-6), (
            f"join station sits {v - law:+.4f} m off its law line — the "
            f"DEM-follow ride survived the solve")


def test_both_consumers_call_the_shared_authority():
    """One authority for 'where a join is' (consult-before-create, RULINGS
    7e90032).  A private re-enumeration in either consumer is the defect the
    census-wrapper precedent priced."""
    from auto_patch import elevation as EL
    from auto_patch import grade_graph as GG

    for fn in (GG._runway_anchors, EL._runway_join_stations):
        src = inspect.getsource(fn)
        assert "runway_join_contacts(" in src, (
            f"{fn.__qualname__} no longer calls the shared join enumeration")
        assert ".runway_join_contact(" not in src, (
            f"{fn.__qualname__} re-derives the per-endpoint contact itself — "
            f"that is a second 'where a join is' rule")
