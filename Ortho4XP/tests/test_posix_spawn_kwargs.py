"""Regression twin: external-tool launches must take CPython's posix_spawn().

On macOS, once GDAL/pyproj has opened proj.db, PROJ registers a
pthread_atfork handler that closes its sqlite handles in the forked child
and segfaults in os_log before exec ever runs.  Any ``subprocess.run`` from
a PROJ-loaded parent that CPython routes through fork()+exec() therefore
"fails instantly" (2026-07-16 crash class; nine Python-*.ips reports on
2026-09-03 from census.py / solve_cut.py parents).  CPython takes
posix_spawn only when the launch kwargs satisfy the gate mirrored in
``_takes_posix_spawn`` below (``subprocess.Popen._execute_child``).

This twin reads the kwargs each guarded call site passes -- it never tries
to reproduce the segfault.  Sites: dsf_reader's DSFTool ``--dsf2text`` and
the two LERC decode interpreters in O4_Airport_Elevation_Insets.
"""
import json
import os
import subprocess
import sys
import types

import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_UI_Utils as UI
from auto_patch import dsf_reader


def _takes_posix_spawn(argv, kwargs):
    """CPython 3.14 ``_execute_child`` posix_spawn gate, kwargs-visible part
    (stdio pipes from capture_output are always > 2, so not checked)."""
    return bool(
        os.path.dirname(argv[0])
        and kwargs.get("preexec_fn") is None
        and kwargs.get("close_fds", True) is False
        and not kwargs.get("pass_fds")
        and kwargs.get("cwd") is None
        and not kwargs.get("start_new_session")
        and kwargs.get("process_group", -1) == -1
        and kwargs.get("user") is None
        and kwargs.get("group") is None
        and kwargs.get("extra_groups") is None
        and kwargs.get("umask", -1) < 0
    )


@pytest.fixture
def recorded_runs(monkeypatch):
    """Replace subprocess.run with a recorder that succeeds with the stdout
    ``fake_stdout`` (settable per test) and returns rc 0."""
    calls = []
    state = {"stdout": ""}

    def fake_run(argv, *args, **kwargs):
        assert not args, "positional kwargs would hide the gate"
        calls.append((list(argv), dict(kwargs)))
        return subprocess.CompletedProcess(
            argv, 0, stdout=state["stdout"], stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    calls_ns = types.SimpleNamespace(calls=calls, state=state)
    return calls_ns


def _assert_spawn_safe(argv, kwargs):
    assert kwargs.get("close_fds") is False, kwargs
    assert "cwd" not in kwargs, kwargs
    assert os.path.dirname(argv[0]), argv
    assert kwargs.get("capture_output") is True, kwargs
    assert _takes_posix_spawn(argv, kwargs), (argv, kwargs)


def test_helper_kwargs_satisfy_the_gate():
    kwargs = UI.external_tool_keyword_arguments()
    assert kwargs["close_fds"] is False
    assert "cwd" not in kwargs
    assert isinstance(kwargs["env"], dict)
    assert _takes_posix_spawn([sys.executable, "-c", "pass"], kwargs)
    # The gate that the helper cannot carry: a bare command name forks.
    assert not _takes_posix_spawn(["git", "status"], kwargs)
    assert not _takes_posix_spawn(
        [sys.executable], dict(kwargs, cwd="/tmp"))


def test_dsf_reader_dsftool_run_takes_posix_spawn(
        tmp_path, monkeypatch, recorded_runs):
    dsf = tmp_path / "+40-080.dsf"
    dsf.write_bytes(b"XPLNEDSF")
    tool = str(tmp_path / "Utils" / "mac" / "DSFTool")
    monkeypatch.setattr(dsf_reader, "_dsftool_path", lambda: tool)
    cache_dir = str(tmp_path / "cache")

    text_path = dsf_reader.ensure_dsf_text_path(str(dsf), cache_dir=cache_dir)

    assert text_path == os.path.join(cache_dir, "+40-080.dsf.text")
    assert len(recorded_runs.calls) == 1
    argv, kwargs = recorded_runs.calls[0]
    assert argv[:2] == [tool, "--dsf2text"]
    assert kwargs.get("check") is True and kwargs.get("timeout") == 120
    _assert_spawn_safe(argv, kwargs)


def test_dsf_reader_dsftool_fallback_run_takes_posix_spawn(
        tmp_path, monkeypatch):
    """The second launch (tempfile fallback after a cache-dir failure) is
    a separate call site and must carry the same kwargs."""
    dsf = tmp_path / "+40-080.dsf"
    dsf.write_bytes(b"XPLNEDSF")
    tool = str(tmp_path / "Utils" / "mac" / "DSFTool")
    monkeypatch.setattr(dsf_reader, "_dsftool_path", lambda: tool)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((list(argv), dict(kwargs)))
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    text_path = dsf_reader.ensure_dsf_text_path(
        str(dsf), cache_dir=str(tmp_path / "cache"))
    try:
        assert len(calls) == 2
        assert text_path == calls[1][0][3]
        for argv, kwargs in calls:
            assert argv[:2] == [tool, "--dsf2text"]
            _assert_spawn_safe(argv, kwargs)
    finally:
        if text_path and os.path.isfile(text_path):
            os.remove(text_path)


def test_inset_stac_lerc_decode_takes_posix_spawn(
        tmp_path, monkeypatch, recorded_runs):
    import requests

    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(
        requests, "get",
        lambda url, timeout=None: types.SimpleNamespace(
            status_code=200, content=b"II*\x00lerc"))
    recorded_runs.state["stdout"] = json.dumps(
        {"scale": [1.0, 1.0, 0.0], "tiepoint": [0, 0, 0, 0, 0, 0]})
    destination = str(tmp_path / "NZAA_linz.tif")
    definition = {"code": "LINZ", "source_epsg": "2193",
                  "asset_compression": "lerc"}

    INSETS.StaticStacCatalogStrategy()._decode_lerc_sources(
        definition, [{"href": "https://tiles.test/a.tif"}], destination)

    assert len(recorded_runs.calls) == 1
    argv, kwargs = recorded_runs.calls[0]
    assert argv[0] == sys.executable and argv[1] == "-c"
    assert argv[2] == INSETS.StaticStacCatalogStrategy._LERC_DECODE_SNIPPET
    assert kwargs.get("timeout") == 600 and kwargs.get("text") is True
    _assert_spawn_safe(argv, kwargs)


def test_inset_arcgis_lerc_blob_decode_takes_posix_spawn(
        tmp_path, monkeypatch, recorded_runs):
    import requests

    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setattr(
        requests, "Session",
        lambda: types.SimpleNamespace(
            get=lambda url, timeout=None: types.SimpleNamespace(
                status_code=200, content=b"lerc-blob")))
    definition = {
        "code": "TESTRIO",
        "access_strategy": "arcgis_lerc_tiles",
        "tile_url_template":
            "https://tiles.test/ImageServer/tile/{level}/{row}/{col}",
        "tile_level": "15",
    }
    destination = str(tmp_path / "SBGL_testrio.tif")

    # No decoded .npy files appear (the interpreter is faked), so the
    # strategy reports no coverage -- the launch kwargs are the subject.
    result = INSETS.fetch_inset(
        definition, (-43.255, -22.820, -43.245, -22.812), 5.0, destination)

    assert result is None
    assert len(recorded_runs.calls) == 1
    argv, kwargs = recorded_runs.calls[0]
    assert argv[0] == sys.executable and argv[1] == "-c"
    assert argv[2] == INSETS.ArcgisLercTileStrategy._LERC_BLOB_DECODE_SNIPPET
    assert kwargs.get("timeout") == 600 and kwargs.get("text") is True
    _assert_spawn_safe(argv, kwargs)


def test_git_provenance_takes_posix_spawn(monkeypatch, recorded_runs):
    """git_provenance used ``cwd=`` (forces fork) and a bare ``git``
    (no dirname: forces fork).  Now ``git -C <dir>`` via an absolute path."""
    from auto_patch import provenance

    recorded_runs.state["stdout"] = "abcdef12\n"
    got = provenance.git_provenance(cwd="/some/checkout")
    assert got["sha"] == "abcdef12" and got["dirty"] is True
    assert len(recorded_runs.calls) == 2
    for argv, kwargs in recorded_runs.calls:
        assert argv[1:3] == ["-C", "/some/checkout"]
        _assert_spawn_safe(argv, kwargs)
