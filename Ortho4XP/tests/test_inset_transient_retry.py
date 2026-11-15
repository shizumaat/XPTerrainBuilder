"""#2098 -- national lidar is never lost to a transient failure.

EGLL's 1 m ENGLAND1M inset became FABDEM 30 m: the WCS window read was
aborted by GDAL's low-speed guard ("Operation too slow"), which the
transient classifier did not know, so the fetch answered ``None``, a
refresh deleted the cached lidar and recorded a durable no-coverage.
These twins pin each part of the fix, with no network:

* the low-speed abort is transient (classifier and the WCS window read);
* negatives written under the old law are asked once more (law 3);
* a transient raise is asked again with backoff before the provider is
  given up for the run; a capability failure or a crash is not;
* a refresh answered with no raster keeps a sound cached inset;
* a pass whose best inset ranks below the one before is reported loudly,
  as an engine-worded degraded row;
* every read of one WCS server holds one of its own fetch slots.
"""
import os
import threading
import time

import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
import O4_Tile_Failures as FAIL
import O4_UI_Utils as UI
import O4_Unpatched_Airports as UNPATCHED
from elevation_access import base as ea_base
from elevation_access import definitions as ea_definitions
from elevation_access import failures as ea_failures
from elevation_access import fetch_retry as FETCH_RETRY
from elevation_access import fetch_scratch
from elevation_access import registry as ea_registry
from elevation_access.strategies import wcs as WCS
from test_inset_resolution_ladder import BOX, HAS_GDAL, _write_raster

requires_gdal = pytest.mark.skipif(not HAS_GDAL, reason="no osgeo")

STALL = ("Operation too slow. Less than 1024 bytes/sec transferred the "
         "last 60 seconds")


# ---------------------------------------------------------------- classifier
def test_the_low_speed_abort_is_transient():
    assert ea_failures.error_message_indicates_transient_network_failure(
        RuntimeError(STALL))
    assert ea_failures.error_message_indicates_transient_network_failure(
        "HTTP error code : 429")
    assert not ea_failures.error_message_indicates_transient_network_failure(
        "no such coverage")


def test_a_stalled_wcs_window_read_raises_transient(monkeypatch, tmp_path):
    class _Gdal:
        GDT_Float32 = 6

        @staticmethod
        def Translate(*args, **kwargs):
            raise RuntimeError(STALL)

    monkeypatch.setattr(WCS, "gdal", _Gdal)
    with pytest.raises(ea_base.TransientFetchError):
        WCS.WcsStrategy()._materialize_window(
            {"native_resolution_m": 1}, object(), BOX, 1.0,
            str(tmp_path / "w.tif"))


def test_negatives_of_the_stall_law_are_asked_again():
    assert INSETS.NEGATIVE_LAW >= 3
    old = {"ENGLAND1M": INSETS.NO_COVERAGE,
           "capabilities": {"ENGLAND1M": {"negative_law": 2}}}
    assert INSETS.negative_predates_query_law(old, "ENGLAND1M")


# --------------------------------------------------------------- the retry
def test_a_transient_raise_is_asked_again_then_answers(monkeypatch):
    said = []
    monkeypatch.setattr(UI, "vprint",
                        lambda level, *a: said.append(" ".join(map(str, a))))
    answers = [ea_base.TransientFetchError("HTTP error code : 429"),
               RuntimeError(STALL), "raster"]

    def _attempt():
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    assert FETCH_RETRY.retry_transient(
        _attempt, "RETRYA", "EGLL", delays=(0.0, 0.0)) == "raster"
    assert answers == []
    assert sum("asking again" in line for line in said) == 2


def test_the_retry_gives_up_when_its_delays_are_spent():
    calls = []

    def _attempt():
        calls.append(1)
        raise ea_base.TransientFetchError("HTTP error code : 503")

    with pytest.raises(ea_base.TransientFetchError):
        FETCH_RETRY.retry_transient(_attempt, "RETRYB", "EGLL",
                                    delays=(0.0, 0.0))
    assert len(calls) == 3


@pytest.mark.parametrize("error", [
    ea_base.ProviderUnavailable("no LERC decoder"),
    ValueError("a strategy crash")])
def test_a_capability_failure_or_a_crash_is_not_retried(error):
    calls = []

    def _attempt():
        calls.append(1)
        raise error

    with pytest.raises(type(error)):
        FETCH_RETRY.retry_transient(_attempt, "RETRYC", "EGLL",
                                    delays=(0.0, 0.0))
    assert calls == [1]


def test_a_retry_pauses_the_provider_for_every_airport(monkeypatch):
    import O4_Http_Pushback as PUSHBACK
    paused = []
    monkeypatch.setattr(PUSHBACK, "pause_host",
                        lambda key, wait: paused.append((key, wait)))
    answers = [ea_base.TransientFetchError("too many requests"), "ok"]

    def _attempt():
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    FETCH_RETRY.retry_transient(_attempt, "RETRYD", "EGLL", delays=(0.0,))
    assert [key for (key, _w) in paused] == [
        FETCH_RETRY.provider_pause_key("RETRYD")]


# ------------------------------------------------------ the fetch loop twins
STRATEGY = "transient_retry_fake"


@pytest.fixture
def two_providers(monkeypatch, tmp_path):
    """LIDAR (rank 0, 1 m) above COARSE (rank 1, 30 m).  ``plan["lidar"]``
    is a list of answers LIDAR's fetches give in turn: ``"ok"``,
    ``"none"`` or an exception to raise."""
    plan = {"lidar": [], "calls": []}

    @ea_registry.register_access_strategy(STRATEGY)
    class _Fake:
        def discover(self, definition, bounding_box_wgs84):
            return [{"source_id": "s1"}]

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            code = definition["code"]
            plan["calls"].append(code)
            answer = "ok"
            if code == "LIDAR" and plan["lidar"]:
                answer = plan["lidar"].pop(0)
            if isinstance(answer, Exception):
                raise answer
            if answer == "none":
                return None
            _write_raster(destination_path, 1.0)
            return {"provider": code,
                    "native_resolution_m": definition["native_resolution_m"],
                    "resolution_m": target_resolution_m}

    definitions = [
        {"code": code, "access_strategy": STRATEGY,
         "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
         "priority": priority, "native_resolution_m": metres}
        for (code, priority, metres) in (("LIDAR", 80.0, 1.0),
                                         ("COARSE", 2.0, 30.0))]
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {d["code"]: d for d in definitions})
    monkeypatch.setenv(fetch_scratch.SCRATCH_ENV, str(tmp_path / "scratch"))
    repo = tmp_path / "corpus"
    (repo / "Elevation_data").mkdir(parents=True)
    monkeypatch.setattr(FNAMES, "Elevation_dir",
                        str(repo / "Elevation_data"))
    monkeypatch.setattr(INSETS, "inset_airport_cover_reason",
                        lambda path, box: None)
    try:
        yield plan, definitions
    finally:
        ea_registry.ACCESS_STRATEGIES.pop(STRATEGY, None)


def _lidar_path():
    return FNAMES.airport_inset_dem(39, -107, "KASE", "LIDAR")


@requires_gdal
def test_a_429_then_an_answer_keeps_the_lidar(two_providers, monkeypatch):
    plan, definitions = two_providers
    monkeypatch.setattr(FETCH_RETRY, "RETRY_DELAYS_S", (0.0, 0.0))
    plan["lidar"] = [ea_base.TransientFetchError("HTTP error code : 429"),
                     "ok"]
    index = INSETS.ensure_airport_insets(39, -107, {"KASE": BOX},
                                         definitions, None)
    assert index["KASE"]["LIDAR"] == "ok"
    assert "COARSE" not in index["KASE"]          # never fell back
    assert plan["calls"] == ["LIDAR", "LIDAR"]
    assert os.path.isfile(_lidar_path())


@requires_gdal
def test_a_refresh_answered_with_nothing_keeps_the_cached_lidar(
        two_providers, monkeypatch):
    plan, definitions = two_providers
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, definitions, None)
    assert os.path.isfile(_lidar_path())
    loud = []
    monkeypatch.setattr(UI, "vprint",
                        lambda level, *a: loud.append(" ".join(map(str, a))))
    plan["lidar"] = ["none"]
    downgrades = []
    index = INSETS.ensure_airport_insets(
        39, -107, {"KASE": BOX}, definitions, None, refresh=True,
        inset_downgrades=downgrades)
    assert index["KASE"]["LIDAR"] == "ok"
    assert os.path.isfile(_lidar_path())          # never deleted
    assert downgrades == []
    assert any("answered NO raster" in line for line in loud)


@requires_gdal
def test_a_lost_lidar_is_a_reported_downgrade(two_providers, monkeypatch):
    """The cached lidar is void (the R13-1 rule archives it) and the
    re-fetch fails on transport: the airport ends on COARSE, and the pass
    reports the downgrade."""
    plan, definitions = two_providers
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, definitions, None)
    monkeypatch.setattr(INSETS, "_void_inset_record_reason",
                        lambda path, definition: (
                            "void" if definition["code"] == "LIDAR"
                            else None))
    monkeypatch.setattr(INSETS, "_archive_void_inset_record",
                        lambda path, icao, code, reason: os.remove(path))
    plan["lidar"] = [ea_base.TransientFetchError("HTTP error code : 429")]
    downgrades = []
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, definitions, None,
                                 inset_downgrades=downgrades)
    assert [(r["airport"], r["lost"], r["used"]) for r in downgrades] == [
        ("KASE", "LIDAR", "COARSE")]
    assert "429" in downgrades[0]["reason"]


def test_the_downgrade_row_compares_ranks():
    row = INSETS._inset_downgrade_row
    assert row("A", (0, "LIDAR"), (1, "COARSE"), {"LIDAR": "429"}) == {
        "airport": "A", "lost": "LIDAR", "used": "COARSE", "reason": "429"}
    assert row("A", (0, "LIDAR"), (0, "LIDAR")) is None
    assert row("A", (1, "COARSE"), (0, "LIDAR")) is None      # an upgrade
    assert row("A", None, (1, "COARSE")) is None              # first build
    assert row("A", (0, "LIDAR"), None)["used"] is None


def test_the_downgrade_is_loud_and_an_engine_worded_degraded_row(
        monkeypatch):
    loud = []
    monkeypatch.setattr(UI, "loud_warning",
                        lambda *a: loud.append(" ".join(map(str, a))))
    rows = INSETS._report_inset_downgrades(
        [{"airport": "EGLL", "lost": "ENGLAND1M", "used": "FABDEM",
          "reason": "HTTP error code : 429"}],
        [{"code": "ENGLAND1M", "native_resolution_m": 1.0},
         {"code": "FABDEM", "native_resolution_m": 30.0}])
    assert len(loud) == 1
    assert "INSET DOWNGRADE at EGLL" in loud[0]
    assert "ENGLAND1M 1 m" in loud[0] and "FABDEM 30 m" in loud[0]
    assert [r["code"] for r in rows] == ["inset_downgraded"]
    assert FAIL.severity_of("inset_downgraded") == "degraded"
    [failure] = FAIL.fold(FAIL.from_degraded(rows), "+51-001", built=True)
    assert "less detailed" in failure["what"]
    assert "ENGLAND1M 1 m" in failure["why"]
    assert "FABDEM 30 m" in failure["why"]


def test_the_home_pass_records_the_downgrade(monkeypatch):
    """``ensure_insets_for_tile`` turns the fetch loop's downgrade rows
    into the tile's degraded record (the build summary both apps show)."""
    class _Tile:
        lat, lon = 39, -107
        airport_elevation_providers = "auto"
        airport_elevation_level = "auto"

    def _fake_fetch(lat, lon, boxes, definitions, resolution, **kwargs):
        kwargs["inset_downgrades"].append(
            {"airport": "KASE", "lost": "LIDAR", "used": "COARSE",
             "reason": "HTTP error code : 429"})

    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda t: True)
    monkeypatch.setattr(INSETS, "resolved_inset_mode", lambda t: "ICAO")
    monkeypatch.setattr(INSETS, "inset_keys", lambda d, m: {"KASE"})
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda t, d, only=None: {"KASE": BOX})
    monkeypatch.setattr(INSETS, "select_provider_definitions",
                        lambda providers: [{"code": "LIDAR"},
                                           {"code": "COARSE"}])
    monkeypatch.setattr(INSETS, "ensure_airport_insets", _fake_fetch)
    monkeypatch.setattr(INSETS, "_write_inset_completion_stamp",
                        lambda tile: None)
    monkeypatch.setattr(UI, "loud_warning", lambda *a: None)
    tile = _Tile()
    INSETS.ensure_insets_for_tile(tile, {"KASE": {}})
    assert [(r["code"], r["airport"]) for r in
            UNPATCHED.read_degraded(tile)] == [("inset_downgraded", "KASE")]


# ------------------------------------------------------ the per-server cap
def test_every_wcs_read_of_one_server_holds_its_own_slot(monkeypatch):
    """Eight concurrent fetches of one WCS provider (insets and ring cells
    alike reach ``fetch``) never put more than its slot count on the
    server at once."""
    monkeypatch.setattr(WCS, "has_gdal", True)
    live, peak, lock = [0], [0], threading.Lock()

    def _window(self, definition, box, resolution, destination):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.05)
        with lock:
            live[0] -= 1
        return None

    monkeypatch.setattr(WCS.WcsStrategy, "_fetch_window", _window)
    definition = {"code": "WCSCAPTWIN", "fetch_slots": 2}
    threads = [threading.Thread(target=WCS.WcsStrategy().fetch,
                                args=(definition, BOX, 1.0, "x.tif"))
               for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert peak[0] == 2
