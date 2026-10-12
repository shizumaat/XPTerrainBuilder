"""Every error that leaves a tile unbuilt — or an airport unpatched — has a
user message (issue #562; owner RULINGS 2026-10-12a, #564).

The twins of ``O4_Tile_Failures``:

* the WALK — every exception class defined under ``src/`` and every error
  exit of a step module has a catalogue entry (a new raise without a user
  message fails here);
* the FOLD — one cause across several airports is one message;
* the FALLBACK — an exception nobody catalogued is "report it", never its
  own text as the headline;
* the CARRIER — failures end a tile, warnings name an airport without a
  patch on a tile that was built; a step's own abort is not a user Stop.
"""

import ast
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Tile_Failures as FAIL  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402

from test_engine_session import (  # noqa: E402
    _tile_events, install_stub_pipeline, run_build)

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
BUILTIN_EXCEPTIONS = {name for name, value in vars(__import__("builtins")).items()
                      if isinstance(value, type)
                      and issubclass(value, BaseException)}


@pytest.fixture(autouse=True)
def reset_ui_routing():
    yield
    UI.engine_session = None
    UI.red_flag = False


def _source_trees():
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in ("Unused", "__pycache__")]
        for name in sorted(files):
            if name.endswith(".py"):
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as handle:
                    yield (os.path.relpath(path, SRC),
                           ast.parse(handle.read(), filename=path))


TREES = list(_source_trees())


def _base_name(node):
    return node.attr if isinstance(node, ast.Attribute) else getattr(
        node, "id", "")


# ---------------------------------------------------------------------------
# The catalogue itself
# ---------------------------------------------------------------------------
def test_every_entry_is_three_short_plain_parts():
    """What · why · remedy: at most two sentences each, a remedy from the
    fixed set, and nothing a flight-sim user cannot read."""
    developer_words = re.compile(
        r"RULINGS|build_airport|--refresh|Traceback|Exception|\bDSFTool\b"
        r"|\bIIS\b|\bDEFECT\b|\bv2\b|pad_flat|\.py\b")
    for code, entry in FAIL.CATALOGUE.items():
        assert entry.remedy in FAIL.REMEDIES, code
        for text in (entry.what, entry.why, FAIL.REMEDIES[entry.remedy]):
            assert text.count(". ") + 1 <= 2, (code, text)
            assert not developer_words.search(text), (code, text)
    for name in (FAIL.UNMAPPED, FAIL.UNMAPPED_AIRPORT, FAIL.UNMAPPED_STEP):
        assert FAIL.CATALOGUE[name].remedy == "report"
    assert set(FAIL.EXCEPTION_CODES.values()) <= set(FAIL.CATALOGUE)
    assert set(FAIL.STAGE_CODES.values()) <= set(FAIL.CATALOGUE)


# ---------------------------------------------------------------------------
# THE WALK
# ---------------------------------------------------------------------------
def test_every_exception_class_has_a_catalogue_entry():
    """A new exception class under ``src/`` must be given a user message:
    add its NAME to ``O4_Tile_Failures.EXCEPTION_CODES`` (or set
    ``failure_code`` on the class and list the name anyway — the walk is
    by name)."""
    bases = {}
    for _path, tree in TREES:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases.setdefault(node.name, set()).update(
                    _base_name(b) for b in node.bases)

    def is_exception(name, seen=()):
        if name in BUILTIN_EXCEPTIONS:
            return True
        return any(is_exception(b, seen + (name,))
                   for b in bases.get(name, ()) if b not in seen)

    defined = sorted(name for name in bases if is_exception(name))
    assert len(defined) >= 20, defined          # the walk still finds them
    missing = [name for name in defined if name not in FAIL.EXCEPTION_CODES]
    assert not missing, (
        "exception class(es) with no user message — add each to "
        "O4_Tile_Failures.EXCEPTION_CODES: %s" % missing)


def _calls(tree, name):
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and _base_name(node.func) == name):
            yield node


def test_every_error_exit_names_its_cause():
    """``UI.exit_message_and_bottom_line(<message>)`` is how a step prints
    its error and gives up: each such call carries ``code=`` — a catalogue
    key, or an explicit ``None`` for a cancel / an already-named cause.
    ``UI.tile_failure`` takes a catalogue key."""
    exits = 0
    for path, tree in TREES:
        for call in _calls(tree, "exit_message_and_bottom_line"):
            if not call.args:
                continue                         # "Process interrupted"
            exits += 1
            where = "%s:%d" % (path, call.lineno)
            keywords = {k.arg: k.value for k in call.keywords}
            assert "code" in keywords, (
                "%s: an error exit with no code= — name its cause from "
                "O4_Tile_Failures.CATALOGUE (code=None for a cancel)" % where)
            code = keywords["code"]
            assert isinstance(code, ast.Constant), where
            assert code.value is None or code.value in FAIL.CATALOGUE, where
        for call in _calls(tree, "tile_failure"):
            if path.startswith(("o4_engine", "O4_UI_Utils")):
                continue                         # the hook itself
            first = call.args[0]
            assert (isinstance(first, ast.Constant)
                    and first.value in FAIL.CATALOGUE), (path, call.lineno)
    assert exits >= 30, exits


def test_every_airport_failure_record_has_a_known_stage_and_code():
    """An airport failure record is a dict with ``icao`` and ``stage``:
    a literal stage is in ``STAGE_CODES`` and a literal code in the
    catalogue."""
    records = 0
    for path, tree in TREES:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = {k.value: v for k, v in zip(node.keys, node.values)
                    if isinstance(k, ast.Constant)}
            if "icao" not in keys or "stage" not in keys:
                continue
            records += 1
            stage = keys["stage"]
            if isinstance(stage, ast.Constant):
                assert stage.value in FAIL.STAGE_CODES, (path, node.lineno)
            code = keys.get("code")
            if isinstance(code, ast.Constant):
                assert code.value in FAIL.CATALOGUE, (path, node.lineno)
    assert records >= 8, records


# ---------------------------------------------------------------------------
# Exception -> code: class and explicit attribute, never the message
# ---------------------------------------------------------------------------
def test_code_comes_from_the_class_not_the_message():
    class ElevationDownloadRefused(RuntimeError):
        pass

    class Reworded(ElevationDownloadRefused):
        pass

    for exc in (ElevationDownloadRefused("x"), Reworded("anything else")):
        assert FAIL.code_for_exception(exc) == "elevation_download_failed"
    assert FAIL.code_for_exception(
        OSError(28, "No space left on device")) == "disk_full"
    assert FAIL.code_for_exception(PermissionError(13, "denied")) == \
        "no_permission"
    assert FAIL.code_for_exception(MemoryError()) == "out_of_memory"


def test_an_explicit_failure_code_wins_and_carries_its_pack():
    """What a sibling lane does to name a refusal: two attributes."""
    error = RuntimeError("any wording at all")
    error.failure_code = "pack_dump_stale"
    error.failure_params = {"pack": "Global Airports"}
    assert FAIL.code_for_exception(error) == "pack_dump_stale"
    fields = FAIL.record_fields(error)
    (message,) = FAIL.fold(
        [FAIL.record(fields["code"], "d", airport="AAAA",
                     **fields["params"])], "+47-123")
    assert "“Global Airports”" in message["why"]
    assert "any wording" not in FAIL.render(message)


# ---------------------------------------------------------------------------
# THE FOLD
# ---------------------------------------------------------------------------
def test_one_cause_across_airports_is_one_message():
    airports = ["AAAA", "BBBB", "CCCC", "DDDD", "EEEE", "FFFF"]
    records = [FAIL.record("pack_dump_stale", "dump of %s" % a, airport=a)
               for a in airports]
    records.append(FAIL.record("airport_geometry", "Ring edge missing",
                               airport="GGGG"))
    folded = FAIL.fold(records, "+47-123")
    assert [f["code"] for f in folded] == ["pack_dump_stale",
                                           "airport_geometry"]
    assert folded[0]["airports"] == airports
    assert "airports AAAA, BBBB, CCCC, DDDD, EEEE and FFFF" in \
        folded[0]["what"]
    assert folded[0]["detail"].count("\n") == 5      # every detail kept
    assert folded[1]["what"] == (
        "Tile +47-123 was not built: airport GGGG could not be processed.")


def test_a_long_airport_list_is_cut_and_a_different_pack_is_not_folded():
    many = [FAIL.record("airport_solve", airport="A%03d" % i)
            for i in range(9)]
    (message,) = FAIL.fold(many, "+10+020")
    assert "and 3 more" in message["what"] and len(message["airports"]) == 9
    two = FAIL.fold([FAIL.record("pack_dump_stale", airport="AAAA", pack="P"),
                     FAIL.record("pack_dump_stale", airport="BBBB", pack="Q")],
                    "+10+020")
    assert len(two) == 2


# ---------------------------------------------------------------------------
# THE FALLBACK and THE CARRIER, through a real session
# ---------------------------------------------------------------------------
def _done(events, lat, lon):
    return [e for e in _tile_events(events, lat, lon)
            if isinstance(e, EV.BuildDone)][0]


def test_an_uncatalogued_exception_is_report_it_never_its_own_text(
        monkeypatch, tmp_path):
    import O4_File_Names as FNAMES

    class NobodyCataloguedThis(Exception):
        pass

    def boom(tile):
        raise NobodyCataloguedThis("Ring edge missing at -185.72 80.68")

    monkeypatch.setattr(FNAMES, "data_path", lambda rel: str(tmp_path / rel))
    install_stub_pipeline(monkeypatch, results={"vector": boom})
    done = _done(run_build(EngineSession(), [(10, 20)], tmp_path), 10, 20)

    assert done.ok is False
    (failure,) = done.failures
    assert failure["code"] == FAIL.UNMAPPED
    assert failure["what"] == ("Tile +10+020 was not built: the app ran "
                               "into an unexpected problem.")
    assert "Report it and attach the log" in failure["remedy"]
    assert str(tmp_path / "Ortho4XP.log") in failure["remedy"]
    assert failure["log_path"] == str(tmp_path / "Ortho4XP.log")
    for shown in (done.error, FAIL.render(failure)):
        assert "Ring edge" not in shown and "NobodyCatalogued" not in shown
    assert "NobodyCataloguedThis: Ring edge missing" in failure["detail"]


def test_a_catalogued_exception_gets_its_own_message(monkeypatch, tmp_path):
    class ElevationDownloadRefused(RuntimeError):
        pass

    def refuse(tile):
        raise ElevationDownloadRefused("REFUSING to build this tile on …")

    install_stub_pipeline(monkeypatch, results={"vector": refuse})
    done = _done(run_build(EngineSession(), [(10, 20)], tmp_path), 10, 20)
    (failure,) = done.failures
    assert failure["code"] == "elevation_download_failed"
    assert "internet connection" in failure["remedy"]
    assert "REFUSING" not in done.error


def test_a_silent_step_failure_names_the_step(monkeypatch, tmp_path):
    install_stub_pipeline(monkeypatch, results={"mesh": 0})
    done = _done(run_build(EngineSession(), [(10, 20)], tmp_path), 10, 20)
    (failure,) = done.failures
    assert failure["code"] == FAIL.UNMAPPED_STEP
    assert failure["what"] == ("Tile +10+020 was not built: the mesh step "
                               "failed.")


def test_a_named_exit_reaches_the_wire(monkeypatch, tmp_path):
    def exit_named(tile):
        UI.exit_message_and_bottom_line(
            "\nERROR: Could not find ", "x.node", code="earlier_step_missing")

    install_stub_pipeline(monkeypatch, results={"mesh": 0},
                          hooks={"mesh": exit_named})
    done = _done(run_build(EngineSession(), [(10, 20)], tmp_path), 10, 20)
    (failure,) = done.failures
    assert failure["code"] == "earlier_step_missing"
    assert "Could not find  x.node" in failure["detail"]


def test_failed_airports_end_the_tile_folded_while_the_step_fails(
        monkeypatch, tmp_path):
    """Before #564 lands the vector step returns 0 after an airport
    failure: the airports ARE what ended the tile, folded by cause."""
    def airports_fail(tile):
        for icao in ("AAAA", "BBBB"):
            UI.auto_patch_failed(icao, "build", "[v2] stale dump",
                                 code="pack_dump_stale")
        UI.auto_patch_failed("CCCC", "verify", "[v2] DEFECT pad_flat 3")

    install_stub_pipeline(monkeypatch, results={"vector": 0},
                          hooks={"vector": airports_fail})
    events = run_build(EngineSession(), [(10, 20)], tmp_path)
    done = _done(events, 10, 20)
    assert done.ok is False and done.warnings == []
    assert [(f["code"], f["airports"]) for f in done.failures] == [
        ("pack_dump_stale", ["AAAA", "BBBB"]), ("airport_verify", ["CCCC"])]
    assert "pad_flat" not in done.error
    assert [e.code for e in events if isinstance(e, EV.AutoPatchFailed)] == [
        "pack_dump_stale", "pack_dump_stale", "airport_verify"]


def test_a_built_tile_names_its_unpatched_airports_as_warnings(
        monkeypatch, tmp_path):
    """Owner RULINGS 2026-10-12a (#564): the vector step carries on, the
    tile is built, and the airport without a patch is a WARNING."""
    def one_airport_fails(tile):
        UI.auto_patch_failed("AAAA", "build", "[v2] TopologyException: x",
                             code="airport_geometry")

    install_stub_pipeline(monkeypatch, hooks={"vector": one_airport_fails})
    events = run_build(EngineSession(), [(10, 20)], tmp_path)
    done = _done(events, 10, 20)
    assert done.ok is True and done.failures == [] and done.error == ""
    (warning,) = done.warnings
    assert warning["what"] == ("Tile +10+020 was built, but airport AAAA "
                               "could not be processed.")
    assert warning["why"].endswith("The airport is left on ungraded terrain.")
    assert "TopologyException" in warning["detail"]
    run_done = [e for e in events if isinstance(e, EV.RunDone)][-1]
    assert (run_done.done_count, run_done.error_count) == (1, 0)


def test_a_later_tile_failure_is_the_message_not_the_airport(monkeypatch,
                                                            tmp_path):
    def one_airport_fails(tile):
        UI.auto_patch_failed("AAAA", "solve", "[v2] infeasible")

    install_stub_pipeline(monkeypatch, results={"mesh": 0},
                          hooks={"vector": one_airport_fails})
    done = _done(run_build(EngineSession(), [(10, 20)], tmp_path), 10, 20)
    assert [f["code"] for f in done.failures] == [FAIL.UNMAPPED_STEP]
    assert done.warnings == []


def test_a_steps_own_abort_is_a_failure_not_a_stop(monkeypatch, tmp_path):
    """The DSF thread's guard raises the red flag to stop its sibling
    threads: the tile FAILED (it used to read as the user's Stop and end
    the whole run as cancelled, with no reason shown)."""
    def dsf_guard(tile):
        if tile.lat == 10:
            UI.tile_failure("scenery_file_failed",
                            exc=RuntimeError("no Global Scenery DSF"))
            UI.red_flag = True

    install_stub_pipeline(
        monkeypatch, hooks={"imagery": dsf_guard},
        results={"imagery": lambda tile: 0 if tile.lat == 10 else 1})
    events = run_build(EngineSession(), [(10, 20), (11, 21)], tmp_path)
    done = _done(events, 10, 20)
    assert done.ok is False
    assert done.failures[0]["code"] == "scenery_file_failed"
    assert _done(events, 11, 21).ok is True
    run_done = [e for e in events if isinstance(e, EV.RunDone)][-1]
    assert (run_done.done_count, run_done.error_count,
            run_done.cancelled) == (1, 1, False)


def test_a_user_stop_is_still_a_stop(monkeypatch, tmp_path):
    session = EngineSession()

    def stop(tile):
        UI.tile_failure("mesh_failed", "printed on the way out")
        session.cancel()

    install_stub_pipeline(monkeypatch, results={"mesh": 0},
                          hooks={"mesh": stop})
    events = run_build(session, [(10, 20)], tmp_path)
    assert not [e for e in events if isinstance(e, EV.BuildDone)]
    assert [e for e in events if isinstance(e, EV.RunDone)][-1].cancelled


# ---------------------------------------------------------------------------
# The wire: additive, forwarded, harmless to an older peer
# ---------------------------------------------------------------------------
def test_the_new_fields_are_additive_and_survive_the_child_hop():
    from o4_engine.jsonl import serialize_event
    from o4_engine.parallel import _rebuild_event

    assert tuple(int(p) for p in EV.PROTOCOL_VERSION.split(".")) >= (1, 10)
    assert EV.BuildDone().failures == [] and EV.BuildDone().warnings == []
    assert EV.AutoPatchFailed().code == ""

    done = SESSION.build_done(10, 20, False, [
        FAIL.record("disk_full", "OSError: [Errno 28]"),
        FAIL.record("airport_solve", "x", airport="AAAA")])
    assert [f["code"] for f in done.failures] == ["disk_full"]
    payload = serialize_event(done)
    assert payload["event"] == "BuildDone"
    assert set(payload["failures"][0]) == {
        "code", "what", "why", "remedy", "airports", "detail", "log_path"}
    rebuilt = _rebuild_event(payload)
    assert rebuilt.failures == done.failures
    built = SESSION.build_done(10, 20, True, [
        FAIL.record("airport_solve", "x", airport="AAAA")])
    assert _rebuild_event(serialize_event(built)).warnings == built.warnings
    assert built.warnings
    # an older engine's line (no such keys) still rebuilds
    old = _rebuild_event({"event": "BuildDone", "lat": 1, "lon": 2,
                          "ok": False, "error": "x"})
    assert old.failures == [] and old.warnings == []
