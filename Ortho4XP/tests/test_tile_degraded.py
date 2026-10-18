"""A tile built, but not as asked, SAYS so on its BuildDone (issue #853).

The DEGRADED class (spec code-quality-beta3 §2): white-squared textures,
an airport inset not fetched, a mask built without its extent or without
a shallow-water category.  The step that degraded publishes a row beside
the tile (``O4_Unpatched_Airports.record_degraded``); the session that
ends the tile, maybe in another process, folds the rows into
``BuildDone.warnings``.  Every folded entry carries ``severity`` on the
wire (protocol 1.13, additive), and both apps show it.
"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Tile_Failures as FAIL  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
import O4_Unpatched_Airports as UNPATCHED  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402

from test_engine_session import (  # noqa: E402
    _tile_events, install_stub_pipeline, run_build)

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


@pytest.fixture(autouse=True)
def reset_ui_routing():
    yield
    UI.engine_session = None
    UI.red_flag = False


def _done(events, lat, lon):
    (done,) = [e for e in events if isinstance(e, EV.BuildDone)
               and (e.lat, e.lon) == (lat, lon)]
    return done


class _StepProcessTile:
    """A tile object of ANOTHER process: it only knows its folder."""

    def __init__(self, build_dir):
        self.build_dir = build_dir


# ---------------------------------------------------------------------------
# The carrier
# ---------------------------------------------------------------------------
def test_a_degraded_output_is_a_warning_from_the_sidecar(monkeypatch,
                                                         tmp_path):
    tile = _StepProcessTile(str(tmp_path))
    UNPATCHED.record(tile, [])
    UNPATCHED.record_degraded(tile, "imagery", [{
        "code": "imagery_incomplete", "detail": "WARNING: ...",
        "count": 3, "source": "BI"}])
    UNPATCHED.record_degraded(tile, "masks", [{
        "code": "mask_extent_missing", "detail": "x", "extent": "Coast"}])
    # one part restating its rows leaves the other part's
    UNPATCHED.record_degraded(_StepProcessTile(str(tmp_path)), "masks", [{
        "code": "mask_extent_missing", "detail": "x", "extent": "Coast"}])
    assert len(UNPATCHED.read_degraded(_StepProcessTile(str(tmp_path)))) == 2

    install_stub_pipeline(monkeypatch)
    events = run_build(EngineSession(), [(10, 20)], tmp_path,
                       do_vector=False)
    done = _done(events, 10, 20)
    assert done.ok is True and done.failures == []
    assert done.unpatched_airports == []
    assert [w["code"] for w in done.warnings] == ["imagery_incomplete",
                                                  "mask_extent_missing"]
    assert {w["severity"] for w in done.warnings} == {"degraded"}
    (imagery, masks) = done.warnings
    assert imagery["what"] == ("Tile +10+020 was built, but some of its "
                               "aerial images are missing.")
    assert imagery["why"] == ("3 of its aerial images could not be "
                              "downloaded from BI, so they show as white "
                              "squares.")
    assert "ungraded terrain" not in imagery["why"]
    assert "“Coast”" in masks["why"]
    states = [e for e in _tile_events(events, 10, 20)
              if isinstance(e, EV.TileState) and e.state == "done"]
    assert [e.label for e in states] == [SESSION.BUILT_WITH_WARNINGS]

    # a clean rerun of each part restates an empty list: nothing lingers
    for part in ("imagery", "masks"):
        UNPATCHED.record_degraded(_StepProcessTile(str(tmp_path)), part, [])
    again = _done(run_build(EngineSession(), [(10, 20)], tmp_path,
                            do_vector=False), 10, 20)
    assert again.warnings == []


def test_severity_is_the_occurrences_on_every_list():
    failed = SESSION.build_done(10, 20, False, [FAIL.record("disk_full")])
    assert [f["severity"] for f in failed.failures] == ["blocking"]
    built = SESSION.build_done(
        10, 20, True, [FAIL.record("airport_solve", "x", airport="AAAA")],
        notes=[FAIL.record("elevation_substituted", "d", cell="+10+020")],
        degraded=FAIL.from_degraded([{"code": "inset_fetch_failed",
                                      "airport": "AAAA", "source": "LIDAR",
                                      "detail": "timeout"}]))
    assert [(w["code"], w["severity"]) for w in built.warnings] == [
        ("airport_solve", "degraded"), ("inset_fetch_failed", "degraded")]
    # a degraded airport is not an airport without a patch
    assert [a["airports"] for a in built.unpatched_airports] == [["AAAA"]]
    assert built.warnings[1]["why"].startswith("LIDAR did not answer")
    assert built.warnings[0]["why"].endswith(FAIL.UNPATCHED)
    assert [n["severity"] for n in built.notes] == ["info"]


def test_a_step_cannot_turn_a_failure_into_a_warning():
    (rec,) = FAIL.from_degraded([{"code": "disk_full", "detail": "d",
                                  "airport": "AAAA"}])
    assert rec["code"] == FAIL.UNMAPPED and rec["airport"] == ""
    assert "[disk_full]" in rec["detail"]
    (warning,) = FAIL.fold([rec], "+10+020", built=True)
    assert FAIL.UNPATCHED not in warning["why"]


# ---------------------------------------------------------------------------
# The step sites publish their rows
# ---------------------------------------------------------------------------
def test_the_imagery_step_publishes_white_squares(monkeypatch, tmp_path):
    import O4_Imagery_Utils as IMG
    import O4_Tile_Utils as TILE

    monkeypatch.setattr(UI, "loud_warning", lambda *a: None)
    monkeypatch.setattr(IMG, "incomplete_imgs", {"+30+031": ["a", "b"]})
    monkeypatch.setattr(IMG, "incomplete_img_providers",
                        {"+30+031": {"BI", "GO2"}})
    tile = types.SimpleNamespace(lat=30, lon=31, build_dir=str(tmp_path))
    assert TILE.warn_if_imagery_incomplete(tile)
    (row,) = UNPATCHED.read_degraded(_StepProcessTile(str(tmp_path)))
    assert (row["code"], row["count"], row["source"]) == (
        "imagery_incomplete", 2, "BI, GO2")
    monkeypatch.setattr(IMG, "incomplete_imgs", {})
    assert TILE.warn_if_imagery_incomplete(tile) is None
    assert UNPATCHED.read_degraded(_StepProcessTile(str(tmp_path))) == []


def test_a_skipped_shallow_water_category_is_noted(monkeypatch):
    import O4_Mask_Utils as MASK

    monkeypatch.setattr(MASK.OSM, "OSM_layer", lambda: object())
    monkeypatch.setattr(MASK.OSM, "OSM_queries_to_OSM_layer",
                        lambda *a, **k: 0)
    tile = types.SimpleNamespace(lat=0, lon=0)
    assert MASK.load_shallow_water_polygons(tile) is None
    assert tile.shallow_water_skipped == ["reef", "tidalflat"]
    (warning,) = FAIL.fold(FAIL.from_degraded([
        {"code": "mask_shallow_water_skipped", "category": c, "detail": c}
        for c in ("reef",)]), "+00+000", built=True)
    assert "coral reefs" in warning["why"]


def test_the_inset_home_pass_restates_its_rows(monkeypatch, tmp_path):
    import O4_Airport_Elevation_Insets as INSETS

    tile = types.SimpleNamespace(lat=1, lon=2, build_dir=str(tmp_path))
    UNPATCHED.record_degraded(tile, "airport-insets", [
        {"code": "inset_fetch_failed", "detail": "old"}])
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda t: False)
    INSETS.ensure_insets_for_tile(tile, {})
    assert UNPATCHED.read_degraded(_StepProcessTile(str(tmp_path))) == []
    # a NEIGHBOUR pass never writes the home tile's rows
    UNPATCHED.record_degraded(tile, "airport-insets", [
        {"code": "inset_fetch_failed", "detail": "home"}])
    INSETS.ensure_insets_for_tile(tile, {}, meter_key="airport-insets +1+3")
    assert len(UNPATCHED.read_degraded(tile)) == 1


# ---------------------------------------------------------------------------
# The wire and both apps
# ---------------------------------------------------------------------------
def test_the_severity_key_is_additive_on_the_wire():
    from o4_engine.jsonl import serialize_event
    from o4_engine.parallel import _rebuild_event

    assert tuple(int(p) for p in EV.PROTOCOL_VERSION.split(".")) >= (1, 13)
    built = SESSION.build_done(10, 20, True, [], degraded=FAIL.from_degraded(
        [{"code": "mask_extent_missing", "detail": "x", "extent": "E"}]))
    payload = serialize_event(built)
    assert payload["warnings"][0]["severity"] == "degraded"
    assert _rebuild_event(payload).warnings == built.warnings
    # an entry without the key (an older engine) still renders in Qt
    import O4_Qt_Tile_Failures as QTFAIL
    old = types.SimpleNamespace(ok=True, failures=[], notes=[], warnings=[
        {"what": "w", "why": "y", "remedy": "r"}])
    assert QTFAIL.console_lines(old)[0] == "Warning: w"


def test_qt_shows_the_severity_label():
    import O4_Qt_Tile_Failures as QTFAIL

    failed = SESSION.build_done(10, 20, False, [FAIL.record("disk_full")])
    built = SESSION.build_done(11, 20, True, [], degraded=FAIL.from_degraded(
        [{"code": "imagery_incomplete", "detail": "x", "count": 1}]))
    (_title, body, _detail) = QTFAIL.box_texts([failed, built])
    assert body.index(FAIL.SEVERITY_LABELS["blocking"] + ": Tile +10+020") \
        < body.index(FAIL.SEVERITY_LABELS["degraded"] + ": Tile +11+020")


def test_the_mac_app_parses_and_labels_severity_like_qt():
    swift = os.path.join(ROOT, "Sources", "SceneryKit", "TileFailure.swift")
    client = os.path.join(ROOT, "Sources", "SceneryKit",
                          "OrthoEngineClient.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    with open(swift, encoding="utf-8") as handle:
        source = handle.read()
    assert 'entry["severity"]' in source
    for severity, label in FAIL.SEVERITY_LABELS.items():
        assert 'case "%s": return "%s"' % (severity, label) in source
    with open(client, encoding="utf-8") as handle:
        assert 'case "ImageryDownloadsDone":' in handle.read()
