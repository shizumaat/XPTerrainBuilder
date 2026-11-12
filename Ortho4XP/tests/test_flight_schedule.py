"""``O4_Flight_Schedule`` (spec flight-manager-and-world-20261110 §6.2,
§8.2, §8.4, §9; lane F1a): route times, deadlines from window entries,
list scheduling, the countdown, shedding, the laxity guard and the
readiness rows, on hand cases.  Pure: no files, no clock."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Flight_Plan as FP  # noqa: E402
import O4_Flight_Schedule as S  # noqa: E402
import pytest  # noqa: E402

PLANS = os.path.join(os.path.dirname(__file__), "fixtures", "flight_plan")


def job(tile, role="enroute", klass=None, deadline=0.0, hi=100.0, state="queued",
        kind="drape", off=0.0, remaining=None):
    if klass is None:
        klass = S.klass_for(role)
    return S.Job(tile=tile, role=role, kind=kind, klass=klass, deadline_s=deadline,
                 est_s=(hi / 2, hi), state=state, off_route_km=off,
                 remaining_s=remaining)


# --- route times and deadlines ---------------------------------------------
def test_timed_waypoints_interpolate_by_distance():
    plan = FP.read_plan_file(os.path.join(PLANS, "simbrief_ofp_full.xml"))
    samples, times = S.route_times(plan)
    assert len(samples) == len(times) and samples[0] == plan.points()[0]
    assert times[0] == 0.0 and times[-1] == pytest.approx(3300.0)
    assert all(b >= a for a, b in zip(times, times[1:], strict=False))
    toc = samples.index((60.3, 9.8))
    assert times[toc] == pytest.approx(900.0)


def test_untimed_route_flies_cruise_with_climb_and_descent_legs():
    plan = FP.read_plan_file(os.path.join(PLANS, "short_hop_v11.fms"))
    _, times = S.route_times(plan, cruise_ms=200.0)
    length_m = FP.route_length_km(plan.points()) * 1000
    climb = 250 * S.KT_TO_MS
    leg = 2 * 3.0 * 10 * 1852            # 30 nm each end at 10,000 ft
    expected = leg / climb + (length_m - leg) / 200.0
    assert times[-1] == pytest.approx(expected, rel=0.01)
    # slower than cruise: the climb leg is flown at the cruise speed
    _, slow = S.route_times(plan, cruise_ms=50.0)
    assert slow[-1] == pytest.approx(length_m / 50.0, rel=1e-6)


def test_deadlines_from_window_entries():
    times = [0.0, 100.0, 1000.0, 2000.0]
    speed = 100.0                         # 5.56 km at 100 m/s = 55.6 s -> 60 s floor
    got = S.tile_deadlines(times, {(1, 1): 0, (1, 2): 1, (1, 3): 3}, speed)
    assert got == {(1, 1): 0.0, (1, 2): 30.0, (1, 3): 2000.0 - 60.0 - S.SWAP_S}
    assert S.margin_s(10.0) == pytest.approx(S.MARGIN_KM * 100.0)


# --- estimates ----------------------------------------------------------------
def test_estimates_and_spreads_match_plan_estimate():
    from o4_engine import plan_estimate
    assert S.SPREAD_KNOWN == plan_estimate.TIME_SPREAD_KNOWN
    assert S.SPREAD_UNKNOWN == plan_estimate.TIME_SPREAD_UNKNOWN
    assert S.job_estimate("drape") == (80 * 0.5, 80 * 2.5)
    assert S.drape_seconds(1024) == S.DRAPE_SECONDS[1024]
    assert S.drape_seconds("junk") == S.drape_seconds(999) == S.DRAPE_SECONDS[512]
    assert S.job_estimate("full", 1000.0, known=True) == (750.0, 1500.0)
    with pytest.raises(ValueError):
        S.job_estimate("full")


def test_rescale_is_clamped_and_by_kind():
    jobs = [job((0, 0), hi=100.0), job((0, 1), hi=100.0, kind="full"),
            job((0, 2), hi=100.0, state="building")]
    out = S.rescale(jobs, "drape", measured_s=1000.0, predicted_s=100.0)
    assert [j.est_s[1] for j in out] == [250.0, 100.0, 100.0]
    assert S.rescale(jobs, "drape", 10.0, 100.0)[0].est_s[1] == 50.0


# --- scheduling and the countdown -----------------------------------------------
def test_finish_times_on_slots_running_first():
    jobs = [job((0, 2), "destination", hi=300.0, deadline=5000.0),
            job((0, 1), deadline=1000.0, hi=100.0),
            job((0, 0), "departure", hi=200.0),
            job((0, 3), hi=50.0, state="building", remaining=(10.0, 40.0)),
            job((0, 4), hi=50.0, state="swapped")]
    order = [(j.tile, end) for j, end in S.finish_times(jobs, 2)]
    assert order == [((0, 3), 40.0), ((0, 0), 200.0), ((0, 1), 140.0), ((0, 2), 440.0)]


def test_the_flight_waits_only_for_its_departure_area():
    """RULINGS 2026-11-12c (2): the countdown is the departure area's
    (P0: departure + first window) high-estimate finish plus a margin,
    whatever the route; what the route cannot get in time is projected
    late (warned of), never waited for."""
    jobs = [job((0, 0), "departure", hi=600.0),
            job((0, 1), klass=S.P0, hi=100.0),
            job((0, 2), deadline=100.0, hi=900.0),       # cannot make it
            job((0, 9), "destination", deadline=6000.0, hi=500.0)]
    assert S.departure_countdown(jobs, 2) == 600.0 + S.DEPARTURE_MARGIN_S
    assert S.departure_countdown([j for j in jobs if j.klass != S.P0], 2) == 0.0
    late = S.projected_late(jobs, 2, S.departure_countdown(jobs, 2))
    assert [j.tile for j in late] == [(0, 2)]
    bad = job((0, 0), "departure", hi=float("nan"))
    assert S.departure_countdown([bad], 1) is None


def test_countdown_has_no_figure_without_estimates():
    bad = S.Job((0, 0), "departure", "full", S.P0, 0.0, (float("nan"), float("nan")))
    assert S.departure_countdown([bad], 1) is None
    assert S.countdown_text(None) == "Ready in —"
    assert S.countdown_text(0) == "Ready"
    assert S.countdown_text(30) == "Ready in under a minute"
    assert S.countdown_text(661) == "Ready in about 12 min"


def test_feasible_and_shedding_order():
    jobs = [job((0, 0), "departure", hi=100.0, state="swapped"),   # in flight
            job((0, 9), "destination", deadline=10_000.0, hi=100.0),
            job((1, 1), deadline=150.0, hi=100.0),            # on route, early
            job((1, 2), deadline=250.0, hi=100.0),            # on route, later
            job((2, 1), deadline=200.0, hi=100.0, off=15.0),  # off route, far
            job((2, 2), deadline=200.0, hi=100.0, off=5.0),
            job((3, 3), "alternate", deadline=300.0, hi=100.0)]
    assert not S.feasible(jobs, 1, 0.0)
    shed = [j.tile for j in S.shed_order(jobs, 1, 0.0)]
    assert shed[:3] == [(3, 3), (2, 1), (2, 2)]
    kept = [j for j in jobs if j.tile not in shed]
    assert S.feasible(kept, 1, 0.0)
    assert all(j.tile not in shed for j in jobs if j.role in ("departure", "destination"))
    assert S.shed_order(jobs, 1, 10_000.0) == []


def test_next_job_class_order_and_laxity_guard():
    dest = job((0, 9), "destination", deadline=3000.0, hi=1000.0)
    enroute = [job((1, i), deadline=5000.0 + i, hi=100.0) for i in range(3)]
    # plenty of slack: class order (P1 before P2), earliest deadline
    assert S.next_job(enroute + [dest], now_s=0.0, takeoff_s=0.0).tile == (1, 0)
    # the destination's slack (3000 - 1000 = 2000) under one build's
    # length (1000)? not yet; at now = 1500 it is (500): it goes first
    assert S.next_job(enroute + [dest], now_s=1500.0, takeoff_s=0.0).tile == (0, 9)
    assert S.next_job([job((0, 0), state="building")], 0.0, 0.0) is None


# --- readiness ------------------------------------------------------------------
def _rows(**kw):
    return {i.key: i for i in S.readiness_items(S.Facts(**kw))}


def test_readiness_all_done():
    jobs = (job((0, 0), "departure", state="swapped"),
            job((0, 1), klass=S.P0, state="staged"),
            job((0, 2), deadline=5000.0, hi=100.0),
            job((0, 9), "destination", deadline=6000.0, hi=200.0))
    rows = _rows(jobs=jobs, world_installed=True, budget_fits=True, network_ok=True,
                 prefetch_done=True)
    assert [k for k in rows] == ["world", "budget", "network", "prefetch", "departure",
                                 "first_window", "route", "destination", "loaded"]
    assert {i.state for i in rows.values()} == {"done"}
    assert rows["destination"].detail == "Ready 95 min before it loads"


def test_readiness_blocks_and_waits():
    jobs = (job((0, 0), "departure", hi=600.0, state="building", remaining=(100, 300)),
            job((0, 1), klass=S.P0, hi=100.0),
            job((0, 2), deadline=100.0, hi=400.0),
            job((0, 9), "destination", deadline=200.0, hi=500.0, state="failed"),
            job((0, 8), "alternate", deadline=500.0, hi=100.0))
    rows = _rows(jobs=jobs, world_installed=True, xplane_running=True, world_seen=False,
                 budget_fits=False, budget_detail="Needs 4 GB more", network_ok=False,
                 build_alternate=True, flight_loaded=True, loaded_real=False)
    assert rows["world"] == ("world", "blocked", None, "Restart X-Plane once")
    assert rows["budget"] == ("budget", "blocked", None, "Needs 4 GB more")
    assert rows["network"].state == "blocked" and rows["prefetch"].state == "working"
    assert rows["departure"] == ("departure", "working", 300.0, "")
    assert rows["first_window"] == ("first_window", "waiting", 400.0, "")
    # the route builds in flight (12c (2)): shown, never waited for
    assert rows["route"].state == "working" and rows["route"].eta_s is None
    assert "1 tile(s) may show X-Plane's own scenery" in rows["route"].detail
    assert "route" not in S.READY_KEYS and "destination" not in S.READY_KEYS
    assert rows["destination"].state == "failed"
    assert rows["alternate"].state == "waiting"
    assert rows["loaded"].state == "waiting"
    # nothing remote needed: the network row is done offline
    assert _rows(jobs=(), network_ok=False, all_on_disk=True)["network"].state == "done"
    assert _rows(jobs=())["world"].detail == "Install the World pack"
