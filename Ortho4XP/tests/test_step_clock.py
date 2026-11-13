"""#2045: the tile progress bar moves with the work.

Synthetic, headless: a time-model store in ``tmp_path``, fake clocks.
The owner's case (+39-105, 2026-11-13, data mostly cached): the vector
step was 1,626 s of a 1,837 s build (KDEN solving 1,340 s) and the bar
sat still for ~90 % of it, then raced through the rest.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import airport_time_model as ATM  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402
from o4_engine import step_clock as SC  # noqa: E402
from o4_engine import tile_time_model as TTM  # noqa: E402


@pytest.fixture
def stores(tmp_path, monkeypatch):
    monkeypatch.setattr(TTM, "STORE_DIRECTORY", str(tmp_path / "tiles"))
    monkeypatch.setattr(ATM, "STORE_DIRECTORY", str(tmp_path / "airports"))
    monkeypatch.setattr(ATM, "size_km", lambda icao, index_path=None: None)
    return tmp_path


def _features(**extra):
    base = {"zoomlevel": 16, "provider": "Arc", "airports": 0,
            "autopatch_seconds": 0.0, "textures_total": 0,
            "textures_missing": 0, "textures_downloaded": 0,
            "download_seconds": 0.0}
    base.update(extra)
    return base


def _owner_history():
    """+39-105's step records as the owner's 2026-11-13 build left them."""
    TTM.record_build(39, -105, _features(
        airports=3, autopatch_seconds=1442.6,
        airport_seconds={"KBKF": 75.5, "KAPA": 304.8, "KDEN": 1350.2}),
        {"vector": 1626.4})
    TTM.record_build(39, -105, _features(), {"mesh": 120.1})
    TTM.record_build(39, -105, _features(), {"masks": 7.6})
    TTM.record_build(39, -105, _features(textures_total=307),
                     {"imagery": 58.2})


def _plan(lat, lon, features):
    planned = TTM.planned_airports(lat, lon)
    if planned is not None:
        features["airports_planned"] = planned
    plan = SESSION.plan_steps(True, True, False)
    seconds = TTM.predict_step_seconds(lat, lon, features,
                                       [k for k, _b, _w in plan])
    return seconds, dict((k, w) for k, _b, w in
                         SESSION.reweight_plan_by_seconds(plan, seconds))


def test_a_cached_rebuild_gives_its_airports_the_bulk_of_the_bar(stores):
    _owner_history()
    seconds, widths = _plan(39, -105, {"zoomlevel": 16, "provider": "Arc",
                                       "textures_total": 307,
                                       "textures_missing": 0,
                                       "textures_to_download": 0})
    # KDEN's own solve (1,350 s) + the learned overhead (1,626 - 1,443)
    assert seconds["vector"] == pytest.approx(1350.2 + 183.8, abs=1.0)
    assert widths["vector"] > 0.8         # was capped at 0.3 before #2045
    assert widths["imagery"] < 0.1


def test_a_cold_build_prices_its_downloads(stores):
    _owner_history()
    for n, s in ((20, 40.0), (100, 56.0), (300, 96.0)):   # latency + n x 0.2
        TTM.record_build(1, 1, _features(
            textures_total=n, textures_missing=n, textures_downloaded=n,
            download_seconds=s), {"imagery": s + 30.0})
    seconds, widths = _plan(39, -105, {"zoomlevel": 16, "provider": "Arc",
                                       "textures_total": 307,
                                       "textures_missing": 307,
                                       "textures_to_download": 307})
    # render 58 s + the fitted download 36 + 0.2 x 307 s
    assert seconds["imagery"] == pytest.approx(58.2 + 36.0 + 0.2 * 307,
                                               abs=1.0)
    cached, _ = _plan(39, -105, {"zoomlevel": 16, "provider": "Arc",
                                 "textures_total": 307, "textures_missing": 0,
                                 "textures_to_download": 0})
    assert seconds["imagery"] > cached["imagery"]
    assert widths["vector"] > 0.75


def test_the_download_fit_is_a_latency_plus_a_share():
    """The owner's 307 textures took 58.6 s (0.19 s each); the old median
    seconds-per-texture over every build priced them at 1.14 s each."""
    records = [{"finished_at": i, "features": _features(
        textures_downloaded=n, download_seconds=s)}
        for i, (n, s) in enumerate(((1, 30.0), (10, 32.0), (100, 50.0),
                                    (300, 90.0)))]
    assert TTM._download_seconds("Arc", 307, records) == pytest.approx(
        30.0 + 0.2 * 307, rel=0.05)
    assert TTM._download_seconds("Arc", 10, []) is None


def test_an_airport_is_priced_by_its_own_history_first(stores):
    ATM.record("KDEN", 1340.1, now=1.0)
    ATM.record("KDEN", 1500.0, now=2.0)
    ATM.record("KDEN", 1400.0, now=3.0)
    assert ATM._predict("KDEN", size=10.0) == pytest.approx(1400.0)
    # the replay's view: only what was recorded before
    assert ATM._predict("KDEN", before=2.5) == pytest.approx(1420.05)
    # no history: its size at the learned rate, else the constant
    assert ATM._predict("KXXX", size=10.0) == pytest.approx(
        ATM.DEFAULT_SIZE_RATE * 10.0)
    assert ATM._predict("KXXX") == ATM.DEFAULT_SECONDS


def test_v1_records_and_old_windows_never_count(stores):
    store = stores / "airports"
    store.mkdir()
    (store / "KDEN.json").write_text(json.dumps(
        [{"finished_at": 1.0, "total_seconds": 9999.0}]),   # v1: no engine
        encoding="utf-8", newline="\n")
    assert ATM._predict("KDEN") == ATM.DEFAULT_SECONDS
    for i in range(ATM.RECORDS_KEPT + 3):
        ATM.record("KDEN", 100.0 + i, now=10.0 + i)
    kept = json.loads((store / "KDEN.json").read_text(encoding="utf-8"))
    assert len(kept) == ATM.RECORDS_KEPT
    assert all(r["source"] == "app" for r in kept)


def test_airports_solve_in_parallel(stores):
    ATM.record("KDEN", 1340.0)
    ATM.record("KBKF", 71.0)
    assert ATM.wall_seconds({"KDEN": None, "KBKF": None}) == 1340.0
    assert ATM.wall_seconds({}) == 0.0


def _simulate(clock, events, horizon, step=10.0):
    """Drive ``clock`` through ``events`` [(t, fn)], sampling its
    fraction every ``step`` seconds."""
    samples, pending, t = [], sorted(events, key=lambda e: e[0]), 0.0
    while t <= horizon:
        while pending and pending[0][0] <= t:
            pending.pop(0)[1]()
        samples.append((t, clock.fraction(t)))
        t += step
    return samples


def test_the_vector_bar_tracks_the_wall_clock_through_a_long_solve():
    """THE OWNER'S DEFECT: KDEN 9 min in [69/100] held the bar.  With
    predictions that match the build, the vector window advances in step
    with the clock — never more than 15 points off the time share."""
    clock = SC.StepClock("vector", 1626.0, 0.0,
                         {"KDEN": 1340.0, "KAPA": 300.0, "KBKF": 71.0})
    begin = 90.0
    events = [(begin, lambda: clock.airports_begin(
        {"KDEN": 1340.0, "KAPA": 300.0, "KBKF": 71.0}, begin))]
    for icao, end in (("KDEN", 1340.0), ("KAPA", 300.0), ("KBKF", 71.0)):
        events.append((begin, lambda i=icao: clock.airport(i, 0.0, False,
                                                           begin)))
        for pct in (0.07, 0.21, 0.39, 0.49, 0.69, 0.82):
            at = begin + pct * end
            events.append((at, lambda i=icao, p=pct, a=at:
                           clock.airport(i, p, False, a)))
        events.append((begin + end, lambda i=icao, a=begin + end:
                       clock.airport(i, 1.0, True, a)))
    samples = _simulate(clock, events, 1626.0)
    values = [f for _t, f in samples]
    assert values == sorted(values)                       # never backwards
    worst = max(abs(f - t / 1626.0) for t, f in samples)
    assert worst < 0.15
    # and inside KDEN's long solve stage the bar keeps moving
    stage = [f for t, f in samples if begin + 0.69 * 1340 < t
             < begin + 0.82 * 1340]
    assert stage[-1] - stage[0] > 0.05


def test_an_overrun_keeps_moving_and_recedes():
    clock = SC.StepClock("mesh", 100.0, 0.0)
    assert clock.fraction(50.0) == pytest.approx(0.5)
    late = [clock.fraction(t) for t in (100.0, 200.0, 400.0)]
    assert late == sorted(late) and late[-1] < 1.0
    assert clock.remaining(200.0) > 0.0                   # never "done"


def test_more_airports_than_workers_wait_their_turn():
    """Five 100 s airports on two workers take ~250 s, not 100 s."""
    clock = SC.StepClock("vector", 10.0, 0.0)
    names = ["A", "B", "C", "D", "E"]
    clock.airports_begin({n: 100.0 for n in names}, 0.0)
    clock.airport("A", 0.0, False, 0.0)
    clock.airport("B", 0.0, False, 0.0)
    assert clock.remaining(0.0) > 240.0
