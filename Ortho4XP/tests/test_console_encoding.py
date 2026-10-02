"""THE CONSOLE IS UTF-8 WITH A FALLBACK THAT CANNOT RAISE (#171, #125).

One derivation site, ``src/O4_Console_Encoding.py``, and three things to
hold true:

1. a cp1252 stream handed to :func:`configure_console_streams` comes back
   UTF-8, and a line of the house spelling (``Δ ε ≥ →``) or of a real
   airport name (``Adolfo Suárez``) written to it round-trips as UTF-8
   instead of raising ``UnicodeEncodeError`` — #171's crash and #125's
   mangling are the same defect at the same layer;
2. a stream that cannot be re-encoded still cannot raise: the fallback
   NAMES the codepoint (``\\u03b5``) rather than spending it on ``?``;
3. every argparse-bearing tool inherits it — statically (the call is in
   the file, ahead of its parser) and in fact (``--help`` under a cp1252
   console exits 0).  16 of the 80 were RED before this landed.

The ``cp1252`` streams here are built with ``io.TextIOWrapper(buf,
encoding="cp1252")`` because that is what a Windows console IS at the
Python layer; the subprocess arms use ``PYTHONIOENCODING=cp1252``, which
is the reproduction #171 was filed with.
"""
from __future__ import annotations

import ast
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT / "src"))

import O4_Console_Encoding as CE                                  # noqa: E402

#: The house spelling that cp1252 cannot carry, plus the airport name from
#: #125's own stderr log.
HOUSE = "Δ ε ≥ → Σ ∩ − Adolfo Suárez Madrid-Barajas"

#: #125's exact line, as the Windows engine printed it.
LEMD_LINE = ("   LEMD   Adolfo Suárez Madrid-Barajas Airport"
             "                         4 runways, lat= 40.48, lon= -3.57")


def _cp1252_stream():
    """A stream shaped like a Windows console: a byte sink behind cp1252."""
    buf = io.BytesIO()
    buf.close = lambda: None            # keep the bytes readable after use
    return io.TextIOWrapper(buf, encoding="cp1252", newline="\n"), buf


def _pinned(monkeypatch, name="stdout"):
    """Install a cp1252 ``sys.<name>`` and pin it.  Returns (stream, buf)."""
    stream, buf = _cp1252_stream()
    monkeypatch.setattr(sys, name, stream)
    CE.configure_console_streams(force=True)
    return getattr(sys, name), buf


# ---------------------------------------------------------------------------
# 1. The derivation site itself
# ---------------------------------------------------------------------------
def test_a_cp1252_console_is_pinned_to_utf8(monkeypatch):
    stream, buf = _cp1252_stream()
    assert stream.encoding.lower() == "cp1252"          # the defect's shape
    monkeypatch.setattr(sys, "stdout", stream)
    record = CE.configure_console_streams(force=True)

    assert record["stdout"] == "reconfigured"
    assert sys.stdout.encoding.lower().replace("_", "-") == "utf-8"
    assert sys.stdout.errors == CE.WRITE_ERRORS


def test_the_house_spelling_round_trips_instead_of_raising(monkeypatch):
    """#171: ``ε`` through a cp1252 stdout was ``UnicodeEncodeError``."""
    stream, buf = _pinned(monkeypatch)
    stream.write(HOUSE + "\n")                  # pre-fix: raises here
    stream.flush()
    assert buf.getvalue().decode("utf-8") == HOUSE + "\n"


def test_a_non_ascii_log_line_survives_on_stderr(monkeypatch):
    """#125: the frozen engine's stderr was the ANSI code page, so this
    line reached ``logs/engine-stderr.log`` as undecodable cp1252 bytes
    (``Adolfo Su?rez``) — the file bug reports ask users for."""
    stream, buf = _pinned(monkeypatch, "stderr")
    print(LEMD_LINE, file=stream)
    stream.flush()
    raw = buf.getvalue()
    assert raw.decode("utf-8") == LEMD_LINE + "\n"      # decodes AS UTF-8
    assert "á".encode("utf-8") in raw                   # 0xC3 0xA1, not 0xE1
    assert b"\xe1" not in raw                           # the cp1252 byte


def test_an_unencodable_character_names_its_codepoint_and_never_raises(
        monkeypatch):
    """The fallback for a stream whose ENCODING cannot be changed (a
    detached or oddly-wrapped console): the errors policy alone still
    turns a crash into a legible, reversible escape."""
    stream, buf = _cp1252_stream()
    real = stream.reconfigure

    def encoding_is_refused(**kwargs):
        if "encoding" in kwargs:
            raise io.UnsupportedOperation("encoding is fixed on this stream")
        return real(**kwargs)

    monkeypatch.setattr(stream, "reconfigure", encoding_is_refused)
    monkeypatch.setattr(sys, "stdout", stream)
    record = CE.configure_console_streams(force=True)

    assert record["stdout"].startswith("errors-only")
    stream.write("ε\n")                          # must NOT raise
    stream.flush()
    text = buf.getvalue().decode("cp1252")
    assert text == "\\u03b5\n"                   # names the codepoint
    assert "\\u03b5".encode().decode("unicode_escape") == "ε"   # reversible


def test_a_console_less_process_is_tolerated(monkeypatch):
    """A frozen windowed build (``console=False`` in ``Ortho4XP_Qt.spec``)
    and ``pythonw.exe`` have no standard streams at all."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert CE.configure_console_streams(force=True)["stdout"] == "absent"


def test_a_capture_object_is_left_alone(monkeypatch):
    """pytest's capture and ``io.StringIO`` have no byte layer, so there is
    no code page to get wrong and nothing to swap out from under a host."""
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert CE.configure_console_streams(force=True)["stdout"] == "no-reconfigure"


def test_stdin_is_pinned_too_with_a_read_policy_that_cannot_raise(monkeypatch):
    """The JSONL command stream carries raw UTF-8 from front ends (Swift's
    ``JSONEncoder`` does not escape non-ASCII), and one bad byte must not
    end the read loop."""
    raw = io.BytesIO(("{\"cmd\": \"tile_info\", \"working_dir\": "
                      "\"C:/Users/Jörg\"}\n").encode("utf-8"))
    monkeypatch.setattr(sys, "stdin",
                        io.TextIOWrapper(raw, encoding="cp1252"))
    CE.configure_console_streams(force=True)
    assert sys.stdin.errors == CE.READ_ERRORS
    assert "Jörg" in sys.stdin.readline()


def test_children_inherit_the_text_layer(monkeypatch):
    """The engine re-execs itself (``--engine-worker``, ``--lerc-decode``)
    and a frozen exe has no ``-X utf8`` to hand a child."""
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    record = CE.configure_console_streams(force=True)
    assert record["PYTHONIOENCODING"] == CE.CHILD_IO_ENCODING
    assert os.environ["PYTHONIOENCODING"] == "utf-8:backslashreplace"


def test_an_explicit_child_encoding_still_wins(monkeypatch):
    """``setdefault``, the ``PYTHONHASHSEED`` precedent — and it is what
    lets the subprocess arms below reproduce #171 at all."""
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    assert CE.configure_console_streams(force=True)["PYTHONIOENCODING"] \
        == "cp1252"


def test_it_is_idempotent(monkeypatch):
    """An entry point, ``jsonl.serve`` and a tool may each call it."""
    monkeypatch.setattr(sys, "stdout", _cp1252_stream()[0])
    first = CE.configure_console_streams(force=True)
    assert CE.configure_console_streams() is first


# ---------------------------------------------------------------------------
# 2. Nothing forks it
# ---------------------------------------------------------------------------
TOOLS = sorted(
    [p for p in (ENGINE_ROOT / "tools").glob("*.py")]
    + [p for p in (ENGINE_ROOT / "tools" / "harness").glob("*.py")])
ENTRIES = (ENGINE_ROOT / "Ortho4XP.py", ENGINE_ROOT / "Ortho4XP_Qt.py")


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_only_the_derivation_site_reconfigures_a_stream():
    """Owner ruling ``7e90032`` in spirit: extend the one helper, never
    fork it.  ``tools/run_with_ledger.py`` carried its own partial
    ``reconfigure(encoding="utf-8")`` for #92 and is now wired to the
    helper; a second one is the census-wrapper precedent again."""
    offenders = []
    for path in list(TOOLS) + list(ENTRIES) + sorted(
            (ENGINE_ROOT / "src").rglob("*.py")):
        if path.name == "O4_Console_Encoding.py":
            continue
        for node in ast.walk(ast.parse(_source(path), filename=str(path))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "reconfigure":
                offenders.append(f"{path.relative_to(ENGINE_ROOT)}:{node.lineno}")
    assert offenders == [], (
        "these configure a stream encoding themselves instead of calling "
        "O4_Console_Encoding.configure_console_streams(): " + ", ".join(offenders))


ARGPARSE_TOOLS = [p for p in TOOLS if "ArgumentParser" in _source(p)]


def test_the_argparse_tool_set_is_not_empty():
    """A self-instrument: if the discovery below silently found nothing,
    every parametrised case would vacuously pass."""
    assert len(ARGPARSE_TOOLS) >= 70, len(ARGPARSE_TOOLS)


@pytest.mark.parametrize(
    "tool", ARGPARSE_TOOLS, ids=lambda p: p.name)
def test_every_argparse_tool_pins_the_console_before_its_parser(tool: Path):
    """The structural half, and the one that holds for a tool written
    tomorrow: the call is at MODULE level and ahead of the first
    ``ArgumentParser``, so no help text and no report line can be printed
    through an unpinned stream.  The allowlist is EMPTY."""
    tree = ast.parse(_source(tool), filename=str(tool))
    calls = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "configure_console_streams"]
    parsers = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Attribute) and n.attr == "ArgumentParser"]
    assert calls, (f"{tool.name} prints but never calls "
                   "O4_Console_Encoding.configure_console_streams()")
    assert min(calls) < min(parsers), (
        f"{tool.name} builds its parser at line {min(parsers)} before "
        f"pinning the console at line {min(calls)}")


# ---------------------------------------------------------------------------
# 3. The real CLIs, on a real cp1252 console
# ---------------------------------------------------------------------------
#: Tools whose ``--help`` cannot be measured, with WHY.  Not an encoding
#: exemption: the static arm above still covers them, and this arm SKIPS
#: with the reason printed rather than passing quietly.
NO_HELP_ARM = {
    "pad_airside_arm.py":
        "its module body reads V2PADVERT_ENGINE, chdir()s into it and arms "
        "the shared-repo write guard BEFORE argparse exists, so --help "
        "cannot run without doing real work (pre-existing, #178)",
}


# The suite's socket guard (``conftest``, #122) lives in the pytest process
# and its xdist workers — a CHILD is below it.  This arm spawns 80 children,
# so without the same refusal in each one a tool that grows a network call at
# import would put #122's 600 s Windows hang back into the suite through this
# very twin.  ``sitecustomize`` is the only hook that reaches a script before
# its own first line: on PYTHONPATH it is imported by ``site`` at interpreter
# startup.  Measured 2026-10-02: no child reaches the network today, and this
# is what keeps that true.
_CHILD_NETWORK_GUARD = '''
import ipaddress, socket


def _loopback(host):
    if host is None:
        return True
    if isinstance(host, (bytes, bytearray)):
        host = bytes(host).decode("ascii", "replace")
    name = str(host).strip().strip("[]").lower()
    if name in ("", "localhost") or name.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(name.split("%", 1)[0])
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


_getaddrinfo, _connect = socket.getaddrinfo, socket.socket.connect


def getaddrinfo(host, port, *args, **kwargs):
    if not _loopback(host):
        raise RuntimeError(
            "O4_CHILD_NETWORK_REFUSED: DNS lookup of %r (issue #122)" % (host,))
    return _getaddrinfo(host, port, *args, **kwargs)


def connect(self, address, *args, **kwargs):
    if isinstance(address, tuple) and address and not _loopback(address[0]):
        raise RuntimeError(
            "O4_CHILD_NETWORK_REFUSED: connect to %r (issue #122)" % (address,))
    return _connect(self, address, *args, **kwargs)


socket.getaddrinfo = getaddrinfo
socket.socket.connect = connect
'''


@pytest.fixture(scope="session")
def child_guard_dir(tmp_path_factory) -> Path:
    """A directory holding nothing but the child network guard."""
    path = tmp_path_factory.mktemp("child_network_guard")
    (path / "sitecustomize.py").write_text(
        _CHILD_NETWORK_GUARD, encoding="utf-8", newline="\n")
    return path


def _child_env(guard_dir: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"        # #171's own reproduction
    env.pop("PYTHONWARNINGS", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(guard_dir)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    return env


def _help_under_cp1252(tool: Path, guard_dir: Path):
    return subprocess.run(
        [sys.executable, str(tool), "--help"],
        cwd=str(ENGINE_ROOT), env=_child_env(guard_dir),
        capture_output=True, timeout=180)


def test_the_child_network_guard_is_live(child_guard_dir):
    """A self-instrument: if ``sitecustomize`` were not reaching the
    children, every case below would be measuring an unguarded child and
    this file would be the hole it was written to close."""
    done = subprocess.run(
        [sys.executable, "-c",
         "import socket; socket.getaddrinfo('overpass-api.de', 80)"],
        cwd=str(ENGINE_ROOT), env=_child_env(child_guard_dir),
        capture_output=True, timeout=120)
    assert done.returncode != 0
    assert b"O4_CHILD_NETWORK_REFUSED" in done.stderr, done.stderr[-800:]


@pytest.mark.parametrize("tool", ARGPARSE_TOOLS, ids=lambda p: p.name)
def test_every_tool_help_renders_on_a_cp1252_console(tool: Path,
                                                     child_guard_dir):
    """The in-fact half.  RED before this landed for 15 of these tools:
    arm_site_read, band_clamp_attrib, harness/build_airport, harness/oracle,
    jetway_rider_census, mesh_region_tris, obj8_split_report,
    object_pad_evidence_report, object_seating_report,
    pad_frontage_step, patch_proximity_diff, patch_water_audit,
    trace_reach_route, tunnel_portal_acceptance, undulation."""
    if tool.name in NO_HELP_ARM:
        pytest.skip(NO_HELP_ARM[tool.name])
    done = _help_under_cp1252(tool, child_guard_dir)
    assert done.returncode == 0, (
        f"{tool.name} --help exited {done.returncode} on a cp1252 console\n"
        + done.stderr.decode("utf-8", "backslashreplace")[-2000:])
    assert b"usage" in done.stdout.lower()
    done.stdout.decode("utf-8")              # what came out IS utf-8


def test_the_171_reproducer_prints_its_greek(child_guard_dir):
    """#171 by name: ``obj8_split_report.py --help`` exited rc 1 on
    ``ε`` (U+03B5, module docstring + ``--contact-eps``'s help) and
    ``Δ`` (U+0394).  Both must now reach stdout as UTF-8."""
    tool = ENGINE_ROOT / "tools" / "obj8_split_report.py"
    done = _help_under_cp1252(tool, child_guard_dir)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-2000:]
    text = done.stdout.decode("utf-8")
    assert "ε" in text, "the epsilon that #171 died on never reached stdout"


# ---------------------------------------------------------------------------
# 4. The engine's own transport (#125's site), driven for real
# ---------------------------------------------------------------------------
def test_the_jsonl_transport_pins_a_cp1252_stderr(monkeypatch):
    """#125 end to end at the layer the suite can reach: the frozen exe is
    this code with a frozen interpreter, and ``serve`` is where the
    engine's console is decided — it repoints ``sys.stdout`` at
    ``sys.stderr``, so stderr carries every pipeline print.  Drive it with
    a cp1252 ``sys.stderr`` and a bare ``shutdown``; the stream must come
    back UTF-8 and a pipeline-shaped line must land as UTF-8 bytes."""
    import json

    sys.path.insert(0, str(ENGINE_ROOT / "src"))
    from o4_engine import jsonl

    stderr, buf = _cp1252_stream()
    monkeypatch.setattr(sys, "stderr", stderr)
    CE._RESULT = None                      # a fresh process is what ships
    captured = io.StringIO()
    jsonl.serve(io.StringIO(json.dumps({"cmd": "shutdown", "id": 1}) + "\n"),
                captured)

    assert sys.stderr.encoding.lower().replace("_", "-") == "utf-8"
    assert sys.stderr.errors == CE.WRITE_ERRORS
    print(LEMD_LINE, file=sys.stderr)       # a pipeline print, post-serve
    sys.stderr.flush()
    assert LEMD_LINE in buf.getvalue().decode("utf-8")

    replies = [json.loads(line) for line in
               captured.getvalue().splitlines() if line.strip()]
    assert any(r.get("reply") == 1 and r.get("ok") for r in replies), replies
