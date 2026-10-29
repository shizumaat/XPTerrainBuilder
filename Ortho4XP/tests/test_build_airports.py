"""The Build pane's Airports card, engine side (#818, protocol 1.15).

Three promises: the airport-time estimate is a RANGE learned from the
time records (never one number), a build's per-build switches land on
its tiles without reaching their cfg files, and both the in-process and
the parallel run carry them per batch.  Synthetic records only: no
corpus, no network, no build.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from o4_engine import tile_time_model  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(tile_time_model, "STORE_DIRECTORY", str(tmp_path))

    def write(lat, lon, *samples):
        records = [{"features": {"airports": airports,
                                 "autopatch_seconds": seconds},
                    "step_seconds": {"vector": seconds + 30.0}}
                   for (airports, seconds) in samples]
        path = tile_time_model._tile_record_path(lat, lon)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            json.dump(records, handle)
    return write


# ── the estimate is a range ───────────────────────────────────────────
def test_no_history_gives_the_default_range(store):
    low, high = tile_time_model.airport_seconds_range(47, -123)
    assert (low, high) == tile_time_model.DEFAULT_AIRPORT_SECONDS_RANGE
    assert low < high


def test_one_build_is_widened_never_quoted_exactly(store):
    store(47, -123, (2, 240.0))            # 120 s per airport
    low, high = tile_time_model.airport_seconds_range(47, -123)
    assert low < 120.0 < high
    assert low == pytest.approx(120.0 * tile_time_model.SINGLE_SAMPLE_SPREAD[0])
    assert high == pytest.approx(120.0 * tile_time_model.SINGLE_SAMPLE_SPREAD[1])


def test_the_tiles_own_history_wins_over_other_tiles(store):
    store(10, 10, (1, 900.0), (1, 1000.0))
    store(47, -123, (1, 60.0), (1, 90.0))
    assert tile_time_model.airport_seconds_range(47, -123) == (60.0, 90.0)


def test_a_first_time_tile_uses_every_recorded_tile(store):
    store(10, 10, (1, 100.0), (1, 200.0))
    store(11, 11, (2, 600.0), (1, 400.0))
    low, high = tile_time_model.airport_seconds_range(47, -123)
    assert 100.0 <= low < high <= 400.0


def test_records_that_graded_nothing_are_not_samples(store):
    store(47, -123, (0, 0.0), (0, 50.0))
    assert (tile_time_model.airport_seconds_range(47, -123)
            == tile_time_model.DEFAULT_AIRPORT_SECONDS_RANGE)


# ── the per-build switches ─────────────────────────────────────────────
def _tile(tmp_path, monkeypatch, **values):
    import O4_Config_Utils as CFG

    tile = CFG.Tile(47, -123, str(tmp_path) + os.sep)
    for key, value in values.items():
        setattr(tile, key, value)
    return tile


def test_grading_off_lands_on_the_tile_not_its_cfg(tmp_path, monkeypatch):
    import O4_Settings_Model as SM

    tile = _tile(tmp_path, monkeypatch, auto_patch="ICAO",
                 modify_custom_airports=True)
    tile.apply_build_overrides({"auto_patch": False,
                                "modify_custom_airports": False})
    assert tile.auto_patch == "None"
    assert tile.modify_custom_airports is False
    written = {}
    monkeypatch.setattr(SM, "sparse_tile_values",
                        lambda values, **kw: written.update(values) or {})
    monkeypatch.setattr(SM, "write_tile_cfg", lambda path, out: None)
    assert tile.write_to_config(str(tmp_path / "t.cfg")) == 1
    assert written["auto_patch"] == "ICAO"
    assert written["modify_custom_airports"] is True


def test_grading_on_keeps_the_tiles_mode_or_grades_all(tmp_path,
                                                       monkeypatch):
    tile = _tile(tmp_path, monkeypatch, auto_patch="ICAO")
    tile.apply_build_overrides({"auto_patch": True})
    assert tile.auto_patch == "ICAO"
    tile = _tile(tmp_path, monkeypatch, auto_patch="None")
    tile.apply_build_overrides({"auto_patch": True})
    assert tile.auto_patch == "All"


def test_unknown_keys_and_non_bools_are_ignored(tmp_path, monkeypatch):
    tile = _tile(tmp_path, monkeypatch, auto_patch="ICAO")
    tile.apply_build_overrides({"auto_patch": "None", "max_build_slots": 9,
                                "texture_mode": False})
    assert tile.auto_patch == "ICAO"
    tile.apply_build_overrides(None)
    assert tile.auto_patch == "ICAO"


def test_the_switches_reach_a_worker_childs_tile_arguments():
    from o4_engine import parallel

    class _Bare(parallel.ParallelBuildRun):
        def __getattr__(self, name):
            if name.startswith("_"):
                value = {} if name != "_queue" else []
                object.__setattr__(self, name, value)
                return value
            raise AttributeError(name)

    run = _Bare.__new__(_Bare)
    run._children = []
    run._queue = []
    run._total = 0
    run._run_cells = set()
    parallel.ParallelBuildRun._admit_batch_locked(
        run, [(38, -10)], "BI", 16, "", (True, False, False),
        overrides={"auto_patch": False})
    parallel.ParallelBuildRun._admit_batch_locked(
        run, [(39, -10)], "BI", 16, "", (True, False, False))
    assert run._tile_arguments[(38, -10)]["overrides"] == {"auto_patch": False}
    assert "overrides" not in run._tile_arguments[(39, -10)]


def test_the_build_commands_take_the_keyword():
    import inspect

    from o4_engine.session import EngineSession

    for name in ("build", "enqueue_build"):
        parameters = inspect.signature(
            getattr(EngineSession, name)).parameters
        assert parameters["overrides"].default is None


# ── the card ──────────────────────────────────────────────────────────
def test_the_card_totals_its_airports(monkeypatch):
    from o4_engine import build_airports as CARD

    rows = {(47, -123): [{"icao": "KAAA", "estimate_s": [60.0, 120.0]}],
            (48, -123): [{"icao": "KBBB", "estimate_s": [30.0, 90.0]},
                         {"icao": "KCCC", "estimate_s": [30.0, 90.0]}]}
    monkeypatch.setattr(CARD, "tile_airports",
                        lambda lat, lon, _dir="": rows.get((lat, lon), []))
    monkeypatch.setattr(CARD, "airport_packs", lambda cells, _dir=None: [])
    card = CARD.build_airports([(48, -123), (47, -123), (47, -123)])
    assert [a["icao"] for a in card["airports"]] == ["KAAA", "KBBB", "KCCC"]
    assert card["total_s"] == [120.0, 300.0]


def test_objects_are_counted_outside_the_dsf_folder(tmp_path):
    from o4_engine import build_airports as CARD

    (tmp_path / "objects").mkdir()
    (tmp_path / "objects" / "a.obj").write_text("", encoding="utf-8", newline="")
    (tmp_path / "objects" / "b.AGP").write_text("", encoding="utf-8", newline="")
    (tmp_path / "Earth nav data").mkdir()
    (tmp_path / "Earth nav data" / "c.obj").write_text("", encoding="utf-8", newline="")
    assert CARD.count_objects(str(tmp_path)) == 2


def test_the_event_is_on_the_wire():
    from o4_engine.events import BuildAirportsReady

    event = BuildAirportsReady(request=7, total_s=[1.0, 2.0])
    assert event.event == "BuildAirportsReady"
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "OrthoEngineClient.swift")
    with open(swift, encoding="utf-8") as handle:
        assert '"BuildAirportsReady"' in handle.read()
