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

    class DsfToolError(RuntimeError):       # lane dump560's class, by NAME
        timed_out = False

    assert FAIL.code_for_exception(DsfToolError("crashed (SIGSEGV)")) == \
        "pack_dump_failed"


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


def test_a_pack_objects_exception_names_the_pack_and_the_object():
    """#559's class: an exception inside one member's build leaves
    ``pack_partition`` saying which pack and which object, whatever its
    own class and text are."""
    from auto_patch_v2.airport import pack_partition as PP

    class _Object:
        path = "objects/terminal_lights.obj"

    @PP._names_its_object
    def build(o, cache, law, sc, deck_family_ids, pack_root):
        raise ValueError("Ring edge missing at -185.72 80.68")

    with pytest.raises(ValueError) as caught:
        build(_Object(), None, None, None, (), "/X/Custom Scenery/Some Pack/")
    fields = FAIL.record_fields(caught.value)
    assert fields["code"] == "pack_object_failed"
    (message,) = FAIL.fold([FAIL.record(
        fields["code"], "[v2] %s" % caught.value, airport="AAAA",
        **fields["params"])], "+45-123", built=True)
    assert message["what"] == ("Tile +45-123 was built, but airport AAAA "
                               "could not be graded.")
    assert message["why"].startswith(
        "The scenery pack “Some Pack” contains an object")
    assert "[object objects/terminal_lights.obj]" in message["detail"]
    assert "Ring edge" not in FAIL.render(message)
    assert hasattr(PP._build_member, "__wrapped__")  # the real one is wrapped


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
    # nobody but a shell is driving this session: the remedy names the log
    assert failure["remedy"] == "Report it with the log: " + failure["log_path"]
    assert failure["log_path"].endswith(
        os.path.join("logs", "engine-stderr.log"))
    for shown in (done.error, FAIL.render(failure)):
        assert "Ring edge" not in shown and "NobodyCatalogued" not in shown
    assert "NobodyCataloguedThis: Ring edge missing" in failure["detail"]


def test_report_it_reads_by_who_is_driving(monkeypatch, tmp_path):
    """Master ruling: an app has the button; a shell or harness build is
    told where the log is.  ONE place decides (the catalogue's render)."""
    records = [FAIL.record(FAIL.UNMAPPED, "x"),
               FAIL.record("mesh_failed", "y")]
    (report, retry) = FAIL.fold(records, "+1+002", log_path="/d/e.log",
                                report_button=True)
    assert report["remedy"] == "Press Report this problem."
    assert retry["remedy"] == ("Build the tile again. If it fails again, "
                               "press Report this problem.")
    (report, retry) = FAIL.fold(records, "+1+002", log_path="/d/e.log")
    assert report["remedy"] == "Report it with the log: /d/e.log"
    assert retry["remedy"] == ("Build the tile again. If it fails again, "
                               "report it with the log: /d/e.log")
    assert not EngineSession().app_driven

    # the JSONL transport's peer IS an app
    import test_engine_jsonl as TRANSPORT
    monkeypatch.setattr(
        TRANSPORT, "install_stub_pipeline",
        lambda mp: install_stub_pipeline(mp, results={"mesh": 0}))
    objects = TRANSPORT._run_transport_build(monkeypatch, tmp_path, True)
    (done,) = [o for o in objects if o.get("event") == "BuildDone"]
    assert done["failures"][0]["remedy"] == "Press Report this problem."


def test_no_unmeasured_cause_and_the_ruled_remedies():
    """Master copy rulings: only a real MemoryError names memory; a
    permission cause says to check permissions; the stale pack copy is a
    retry (a stock pack cannot be updated by the user)."""
    for code, entry in FAIL.CATALOGUE.items():
        if code != "out_of_memory":
            assert "memory" not in entry.why.lower(), code
    for code in ("airport_worker_died", "worker_died"):
        assert FAIL.CATALOGUE[code].why == "A background process ended early."
    assert FAIL.CATALOGUE["mesh_failed"].why == (
        "The mesh program stopped before it finished.")
    assert {c: FAIL.CATALOGUE[c].remedy for c in (
        "out_of_memory", "no_permission", "output_folder_unwritable",
        "disk_full", "pack_dump_stale", "pack_write_failed",
        "airport_elevation_missing", "mesh_failed")} == {
        "out_of_memory": "memory", "no_permission": "permissions",
        "output_folder_unwritable": "permissions", "disk_full": "disk",
        "pack_dump_stale": "retry", "pack_write_failed": "pack",
        "airport_elevation_missing": "network", "mesh_failed": "retry"}
    # the errno decides where the code can tell
    assert FAIL.code_for_exception(OSError(28, "full")) == "disk_full"
    assert FAIL.code_for_exception(OSError(13, "denied")) == "no_permission"


def test_whatever_leaves_the_pack_dump_step_names_its_pack(monkeypatch):
    """A converter failure of any class (lane dump560's ``DsfToolError``
    carries no pack) leaves ``engine_v2`` naming the serving pack."""
    from auto_patch import engine_v2 as EV2
    import auto_patch_v2.airport.pack as PACK

    class DsfToolError(RuntimeError):
        pass

    class _Selected:
        name = "Some Pack"

    def crash(*_args):
        raise DsfToolError("DSFTool --dsf2text crashed (SIGSEGV)")

    monkeypatch.setattr(EV2, "fresh_pack_dump", crash)
    monkeypatch.setattr(PACK, "select_pack", lambda root, icao: _Selected())
    with pytest.raises(DsfToolError) as caught:
        EV2._pack_dump_naming_its_pack("/X", "AAAA", 47, -123)
    fields = FAIL.record_fields(caught.value)
    assert fields == {"code": "pack_dump_failed",
                      "params": {"pack": "Some Pack"}}
    (message,) = FAIL.fold([FAIL.record(fields["code"], "d", airport="AAAA",
                                        **fields["params"])], "+47-123",
                           built=True)
    assert "the scenery pack “Some Pack”" in message["why"]
    # a class that names its own pack keeps it
    def named(*_args):
        error = RuntimeError("x")
        error.failure_params = {"pack": "Its Own"}
        raise error
    monkeypatch.setattr(EV2, "fresh_pack_dump", named)
    with pytest.raises(RuntimeError) as caught:
        EV2._pack_dump_naming_its_pack("/X", "AAAA", 47, -123)
    assert caught.value.failure_params == {"pack": "Its Own"}


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
        monkeypatch, tmp_path, capsys):
    """Owner RULINGS 2026-10-12a (#564): the vector step carries on, the
    tile is built, and the airport without a patch is a WARNING — sourced
    from ``O4_Unpatched_Airports``, repeated as the tile's closing lines."""
    import O4_Unpatched_Airports as UNPATCHED

    def one_airport_fails(tile):
        UI.auto_patch_failed("AAAA", "build", "[v2] TopologyException: x",
                             code="airport_geometry")
        UNPATCHED.record(tile, [{"icao": "AAAA", "stage": "build",
                                 "error": "[v2] TopologyException: x",
                                 "code": "airport_geometry"}])

    install_stub_pipeline(monkeypatch, hooks={"vector": one_airport_fails})
    events = run_build(EngineSession(), [(10, 20)], tmp_path)
    done = _done(events, 10, 20)
    assert done.ok is True and done.failures == [] and done.error == ""
    (warning,) = done.warnings
    assert warning["what"] == ("Tile +10+020 was built, but airport AAAA "
                               "could not be processed.")
    assert warning["why"].endswith(FAIL.UNPATCHED)
    assert "TopologyException" in warning["detail"]
    (row,) = done.unpatched_airports
    assert (row["airports"], row["stage"], row["code"]) == (
        ["AAAA"], "build", "airport_geometry")
    assert set(warning) <= set(row)             # feeds failure_report as is
    states = [e for e in _tile_events(events, 10, 20)
              if isinstance(e, EV.TileState) and e.state == "done"]
    assert [e.label for e in states] == [SESSION.BUILT_WITH_WARNINGS]
    run_done = [e for e in events if isinstance(e, EV.RunDone)][-1]
    assert (run_done.done_count, run_done.error_count) == (1, 0)
    out = capsys.readouterr().out
    closing = out[out.index("completed in"):]
    assert "WARNING: Tile +10+020 was built, but airport AAAA" in closing


def test_the_last_steps_process_reads_the_airports_from_the_sidecar(
        monkeypatch, tmp_path):
    """THE PARALLEL CASE: each step runs in its own child, so the session
    that emits the tile's final BuildDone never saw the vector step's
    failures.  It reads the sidecar the vector step left beside the tile —
    two airports of one cause, folded, the cause named by its code."""
    import O4_Unpatched_Airports as UNPATCHED

    class _VectorProcessTile:               # another process's tile object
        build_dir = str(tmp_path)

    UNPATCHED.record(_VectorProcessTile(), [
        {"icao": a, "stage": "build", "error": "[v2] dump",
         "code": "pack_dump_failed", "params": {"pack": "Some Pack"}}
        for a in ("AAAA", "BBBB")] + [
        {"icao": "CCCC", "stage": "verify", "error": "[v2] DEFECT"}])

    install_stub_pipeline(monkeypatch)
    session = EngineSession()
    events = run_build(session, [(10, 20)], tmp_path, do_vector=False)
    assert session._tile_failures == []         # it was told nothing
    done = _done(events, 10, 20)
    assert done.ok is True
    assert [(w["code"], w["airports"]) for w in done.warnings] == [
        ("pack_dump_failed", ["AAAA", "BBBB"]), ("airport_verify", ["CCCC"])]
    assert "“Some Pack”" in done.warnings[0]["why"]
    assert [r["airports"] for r in done.unpatched_airports] == [
        ["AAAA"], ["BBBB"], ["CCCC"]]


def test_a_pack_that_could_not_be_put_back_is_a_second_message(
        monkeypatch, tmp_path):
    """Owner RULINGS 2026-10-12d: an unpatched airport gets its original
    pack back; a restore that cannot be proven is NAMED — a second message
    for that airport, from the ``pack_restore`` sentence the object stage
    left in its record (``O4_Unpatched_Airports.note_pack``)."""
    import O4_Unpatched_Airports as UNPATCHED

    class _OtherProcessTile:
        build_dir = str(tmp_path)

    tile = _OtherProcessTile()
    UNPATCHED.record(tile, [
        {"icao": "AAAA", "stage": "verify", "error": "[v2] DEFECT",
         "params": {"pack": "Some Pack"}},
        {"icao": "BBBB", "stage": "solve", "error": "[v2] infeasible"}])
    UNPATCHED.note_pack(tile, "AAAA", "its backup file is missing.")

    install_stub_pipeline(monkeypatch)
    done = _done(run_build(EngineSession(), [(10, 20)], tmp_path,
                           do_vector=False), 10, 20)
    assert [(w["code"], w["airports"]) for w in done.warnings] == [
        ("airport_verify", ["AAAA"]), ("pack_restore_unproven", ["AAAA"]),
        ("airport_solve", ["BBBB"])]
    restore = done.warnings[1]
    assert restore["what"] == ("Tile +10+020 was built, but objects at "
                               "airport AAAA may float or sink.")
    assert restore["why"] == (
        "An earlier build moved the objects of the scenery pack “Some "
        "Pack” onto graded ground, and they could not be put back: its "
        "backup file is missing.")
    assert restore["remedy"] == FAIL.REMEDIES["restore_pack"]
    # still TWO unpatched airports, not three
    assert [r["airports"] for r in done.unpatched_airports] == [
        ["AAAA"], ["BBBB"]]


def test_the_restore_remedy_names_the_control_both_apps_have():
    """Neither app has a "Restore originals" control: the per-pack button
    of the "Modified airports" row is "Revert to default" in both."""
    remedy = FAIL.REMEDIES["restore_pack"]
    assert "Revert to default" in remedy and "Modified airports" in remedy
    root = os.path.join(SRC, "..", "..")
    for path in (os.path.join(SRC, "O4_Qt_GUI.py"),
                 os.path.join(root, "Sources", "XPTerrainBuilder",
                              "BuildPane.swift")):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        assert "Revert to default" in source, path
        assert "Modified airports" in source, path


def test_stand_in_elevation_is_a_note_from_the_sidecar(monkeypatch,
                                                       tmp_path, capsys):
    """Owner RULINGS 2026-10-12e: a base cell read from a fallback source
    is never silent.  The DEM load published it beside the tile; the
    session that ends the tile — another process under the parallel
    orchestrator — reports it as a NOTE, folded per source pair, and the
    tile reads "built with warnings"."""
    import O4_Unpatched_Airports as UNPATCHED

    class _DemProcessTile:
        build_dir = str(tmp_path)

    tile = _DemProcessTile()
    UNPATCHED.record(tile, [])
    UNPATCHED.record_substitutions(tile, [
        {"cell": c, "code": "GLO30", "path": "/x/%s.tif" % c,
         "source": "Viewfinder Panoramas", "fallback": "Copernicus GLO-30"}
        for c in ("+45-123", "+45-124")])
    # the airport record written afterwards keeps the substitutions
    UNPATCHED.record(tile, [])
    assert len(UNPATCHED.read_substitutions(_DemProcessTile())) == 2

    install_stub_pipeline(monkeypatch)
    events = run_build(EngineSession(), [(10, 20)], tmp_path,
                       do_vector=False)
    done = _done(events, 10, 20)
    assert done.ok is True and done.warnings == [] and done.failures == []
    (note,) = done.notes
    assert note["code"] == "elevation_substituted"
    assert note["cells"] == ["+45-123", "+45-124"]
    assert note["what"] == ("Tile +10+020 was built with stand-in elevation "
                            "for cells +45-123 and +45-124.")
    assert note["why"] == (
        "Viewfinder Panoramas did not answer, so Copernicus GLO-30 was "
        "used. It includes trees and buildings, so the ground there may "
        "read a few metres high.")
    assert note["remedy"] == "Build the tile again later to replace it."
    states = [e for e in _tile_events(events, 10, 20)
              if isinstance(e, EV.TileState) and e.state == "done"]
    assert [e.label for e in states] == [SESSION.BUILT_WITH_WARNINGS]
    assert "NOTE: Tile +10+020 was built with stand-in" in \
        capsys.readouterr().out

    # an ordinary build restates an empty list: the note does not linger
    UNPATCHED.record_substitutions(_DemProcessTile(), [])
    again = _done(run_build(EngineSession(), [(10, 20)], tmp_path,
                            do_vector=False), 10, 20)
    assert again.notes == []


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
        "code", "what", "why", "remedy", "airports", "detail", "log_path",
        "cells"}
    # ...and goes back into the report command unchanged (#565)
    from o4_engine.failure_report import _normalise
    assert _normalise(payload["failures"])[0]["code"] == "disk_full"
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
