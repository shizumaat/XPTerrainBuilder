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
