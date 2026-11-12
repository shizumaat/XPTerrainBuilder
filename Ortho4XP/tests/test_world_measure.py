"""Twins for Measure on its own process, kept and started by itself
(``o4_engine.world_measure``, ``world_tile_facts``; owner
2026-11-12T19:08Z: "automatically kickoff the measure process in the
background so when the user opens settings it's already done" and "I'm
not getting any display of data, budgets, or caches"), offline on
``test_world_migrate``'s synthetic X-Plane folder in ``tmp_path``:

* Measure runs in ANOTHER process: while a slow stand-in measure runs,
  the commands the Storage rows wait on answer at once, and its count
  reaches the engine;
* every phase is counted, the journalled tiles read for adopting again
  (``adopt``) included, n of N with the tile in hand;
* a second Measure of the same tiles reads no header (``TileFacts``),
  and runs no timing sample (the kept seconds per tile);
* the result is kept with its time; changing Custom Scenery makes it
  stale and asks for a new one; an empty Custom Scenery asks for none;
* Cancel stops the child.
"""
from __future__ import annotations

import os
import time

import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Convert as CONVERT
from o4_engine import storage_installed as INSTALLED
from o4_engine import world_measure as MEASURE
from o4_engine import world_migrate as MIGRATE
from o4_engine import world_migrate_size as SIZE
from o4_engine import world_retire as RETIRE
from o4_engine.world_tile_facts import TileFacts
from test_world_migrate import xp  # noqa: F401


def slow_measure(emit, scenery_dir, release="", **_kw):
    """The stand-in dry run (in the child): counts, then waits for the
    test's release file; answers with its own pid."""
    from o4_engine.events import WorldMigrateProgress
    emit(WorldMigrateProgress(phase="adopt", done=3, total=12,
                              tile="zOrtho4XP_+45+007"))
    deadline = time.monotonic() + 60
    while not os.path.exists(release) and time.monotonic() < deadline:
        if MIGRATE.stopping():
            raise ValueError(MIGRATE.STOPPED_MEASURE)
        time.sleep(0.05)
    return {"pid": os.getpid(), "summary": "done", "totals": {}}


def _wait(predicate, seconds=60.0):
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, "TIMED_OUT"
        time.sleep(0.05)


def _start(scenery, tmp_path, outcome, events):
    import threading
    release = str(tmp_path / "release")

    def run():
        try:
            outcome.append(MEASURE.measure(
                scenery, events.append, tiles=["x"], release=release,
                runner="test_world_measure:slow_measure"))
        except Exception as error:
            outcome.append(error)
    threading.Thread(target=run, daemon=True).start()
    return release


def test_storage_answers_while_a_slow_measure_runs(xp, tmp_path):  # noqa: F811
    outcome, events = [], []
    release = _start(xp["scenery"], tmp_path, outcome, events)
    _wait(lambda: events)
    assert MEASURE.running() and not outcome
    started = time.monotonic()
    state = MEASURE.world_measure_state(xp["scenery"])
    installed = INSTALLED.installed_tiles(xp["scenery"], str(tmp_path / "c.json"))
    assert time.monotonic() - started < 2.0          # nothing waits on Measure
    assert installed["linked_count"] == 3 and installed["local_count"] == 1
    assert state["running"] and not state["auto"]
    assert state["progress"] == {"phase": "adopt", "done": 3, "total": 12,
                                 "tile": "zOrtho4XP_+45+007"}
    assert (events[0].phase, events[0].done, events[0].total) == ("adopt", 3, 12)
    open(release, "w", encoding="utf-8", newline="\n").close()
    _wait(lambda: outcome)
    assert outcome[0]["pid"] != os.getpid()          # its own process
    assert not MEASURE.running()


def test_cancel_stops_the_child(xp, tmp_path):  # noqa: F811
    outcome, events = [], []
    _start(xp["scenery"], tmp_path, outcome, events)
    _wait(lambda: events)
    MEASURE.stop()
    _wait(lambda: outcome)
    assert isinstance(outcome[0], ValueError) and "cancelled" in str(outcome[0])
    assert not MEASURE.running()


def test_the_result_is_kept_and_goes_stale_with_custom_scenery(xp):  # noqa: F811
    scenery = xp["scenery"]
    assert MEASURE.state(scenery)["auto"]            # tiles, never measured
    first = MEASURE.measure(scenery)
    assert first["action"] == "dry_run" and first["totals"]["sample"]
    kept = MEASURE.state(scenery)
    assert kept["result"]["summary"] == first["summary"]
    assert abs(kept["measured_at"] - time.time()) < 60
    assert not kept["stale"] and not kept["auto"] and kept["wanted"]
    # the kept seconds per tile: no sample the second time
    second = MEASURE.measure(scenery)
    assert second["totals"]["sample"] == []
    assert second["totals"]["seconds_per_tile"] == first["totals"]["seconds_per_tile"]
    os.makedirs(os.path.join(scenery, "Some Airport"))
    again = MEASURE.state(scenery)
    assert again["stale"] and again["auto"]


def test_an_empty_custom_scenery_asks_for_no_measure(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "data_path", lambda rel: str(tmp_path / "d" / rel))
    scenery = tmp_path / "Custom Scenery"
    scenery.mkdir()
    state = MEASURE.state(str(scenery))
    assert not state["wanted"] and not state["auto"] and state["result"] is None


def _dynamic_journal(xp):  # noqa: F811
    """Every tile out of Custom Scenery, two made dynamic in the journal
    (``test_world_adopt``'s case of 1.0.495)."""
    import shutil
    scenery = xp["scenery"]
    for name in os.listdir(scenery):
        path = os.path.join(scenery, name)
        if name.startswith("zOrtho4XP_"):
            if os.path.islink(path):
                os.unlink(path)
            else:
                shutil.rmtree(path)
    os.makedirs(xp["work"], exist_ok=True)
    journal = MIGRATE.Journal(xp["work"])
    for lat, lon in ((45, 7), (47, 9)):
        name = f"zOrtho4XP_{FNAMES.short_latlon(lat, lon)}"
        source = os.path.join(xp["library"], name)
        journal.set(name, state="dynamic", kind="link", source=source,
                    link_target=source, prior=None)


def test_every_phase_counts_the_adopt_one_too(xp):  # noqa: F811
    _dynamic_journal(xp)
    seen = []
    SIZE.dry_run(xp["scenery"], sample=0,
                 progress=lambda d, t, n, phase: seen.append((phase, d, t, n)))
    adopt = [s for s in seen if s[0] == "adopt"]
    assert adopt[0][1:3] == (0, 2) and adopt[-1][1:3] == (2, 2)
    assert {s[3] for s in adopt[1:]} == {"zOrtho4XP_+45+007", "zOrtho4XP_+47+009"}
    assert MEASURE.state(xp["scenery"])["wanted"]   # the journal alone


def test_a_second_measure_reads_no_header(xp, tmp_path, monkeypatch):  # noqa: F811
    _dynamic_journal(xp)
    calls = []
    real = CONVERT.plan_tile
    monkeypatch.setattr(CONVERT, "plan_tile",
                        lambda *a, **k: calls.append(a[0]) or real(*a, **k))
    path = str(tmp_path / "facts.json")
    first = TileFacts(path)
    one = SIZE.dry_run(xp["scenery"], sample=0, facts=first)
    first.save()
    assert first.read > 0 and len(calls) == 2
    second = TileFacts(path)
    two = SIZE.dry_run(xp["scenery"], sample=0, facts=second)
    assert second.read == 0 and len(calls) == 2      # stat only
    assert one["choices"] == two["choices"]
    keep_all = next(c for c in two["choices"] if c["id"] == RETIRE.KEEP_ALL)
    assert keep_all["again"] == 2
    # a tile rewritten is read again
    os.utime(os.path.join(xp["library"], "zOrtho4XP_+45+007", "terrain"),
             ns=(1, 1))
    third = TileFacts(path)
    SIZE.dry_run(xp["scenery"], sample=0, facts=third)
    assert len(calls) == 3


def test_the_state_matches_the_shared_swift_fixture(xp):  # noqa: F811
    """The keys of ``world_measure_state`` are those of the fixture
    ``WorldWireTests.swift`` decodes (``O4WorldMeasureState``), and a
    kept result carries ``measured_at``."""
    import json
    fixture_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "fixtures", "world", "world_measure_state.json")
    with open(fixture_path, encoding="utf-8") as handle:
        fixture = json.load(handle)
    MEASURE.measure(xp["scenery"])
    state = json.loads(json.dumps(MEASURE.world_measure_state(xp["scenery"])))
    assert set(state) == set(fixture)
    assert "measured_at" in state["result"] and "measured_at" in fixture["result"]
