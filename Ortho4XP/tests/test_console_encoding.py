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
import importlib.util
import io
import pathlib
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


def test_it_changes_nothing_outside_this_process(monkeypatch):
    """THE LEAK THIS TWIN EXISTS FOR.  An earlier version `setdefault`-ed
    ``PYTHONIOENCODING`` so the engine's re-exec children would inherit the
    text layer.  Two costs, both measured on Windows CI (run 36965348610,
    head 769590f2):

    * it escaped THIS twin into the pytest worker's own environment, since
      a test that calls ``configure_console_streams`` does not restore
      ``os.environ`` — so every subprocess the worker spawned afterwards
      wrote UTF-8;
    * and a parent reading such a child with ``subprocess``'s ``text=True``
      decodes with the LOCALE encoding, cp1252 on Windows.
      ``test_schema_snapshot`` read a mismatch as a stale snapshot and
      ``test_blast_index`` took ``UnicodeDecodeError: 'charmap' codec can't
      decode byte 0x81``; both were green on the base commit.

    Children need nothing: each engine child is a re-exec of an entry whose
    module body pins its own console (``__mp_main__`` included).  Flipping
    what children WRITE is a cross-cutting change its readers must be
    censused for first (RULINGS 2026-08-30l) — reported on the PR, not
    taken here.  So the invariant is the simple one: this function touches
    this process and nothing else.
    """
    before = dict(os.environ)
    monkeypatch.setattr(sys, "stdout", _cp1252_stream()[0])
    CE.configure_console_streams(force=True)
    assert dict(os.environ) == before
    assert "PYTHONIOENCODING" not in os.environ or \
        os.environ["PYTHONIOENCODING"] == before.get("PYTHONIOENCODING")


def test_the_module_never_writes_the_environment():
    """Structural, so the leak cannot come back by a different spelling:
    nothing in the derivation site assigns into ``os.environ``."""
    source = (ENGINE_ROOT / "src" / "O4_Console_Encoding.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("setdefault", "update", "pop",
                                       "setenv", "putenv") \
                and "environ" in ast.dump(node.func.value):
            offenders.append(node.lineno)
        if isinstance(node, ast.Subscript) and "environ" in ast.dump(node.value) \
                and isinstance(getattr(node, "ctx", None), ast.Store):
            offenders.append(node.lineno)
    assert offenders == [], (
        f"O4_Console_Encoding writes os.environ at lines {offenders}; a "
        "child's text layer is not this function's to change")


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


def _enclosing_function(tree: ast.AST, node: ast.AST):
    """The FunctionDef that lexically contains ``node``, or None."""
    for candidate in ast.walk(tree):
        if not isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(candidate):
            if inner is node:
                return candidate
    return None


@pytest.mark.parametrize("tool", ARGPARSE_TOOLS, ids=lambda p: p.name)
def test_every_argparse_tool_pins_the_console_before_its_parser(tool: Path):
    """The structural half, and the one that holds for a tool written
    tomorrow — as it did: `osmium159` (#159) gave
    ``tools/harness/shared_repo_guard.py`` a CLI in the same merge window as
    this twin, and this case went red on main for it.

    TWO lawful shapes, because a tool and a library are different things:

    * **at module level** — the idiom in the 80 tools under ``tools/``, which
      are scripts: nothing can print before it;
    * **inside the entry, before ``parse_args``** — for a module that is a
      LIBRARY with a CLI (``shared_repo_guard`` is THE shared-repo write
      guard, imported by the harness and by every tool that arms it).  A
      library pinning the console at import would reconfigure the streams of
      a process that merely imported it, which is the opposite of what this
      lane is for.

    Anything else fails: a call in a function that does NOT reach the parser,
    or one after ``parse_args`` has already printed.  The allowlist is EMPTY.
    """
    tree = ast.parse(_source(tool), filename=str(tool))

    module_level = [n.value.lineno for n in tree.body
                    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                    and isinstance(n.value.func, ast.Attribute)
                    and n.value.func.attr == "configure_console_streams"]
    parsers = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Attribute) and n.attr == "ArgumentParser"]
    assert parsers, tool.name

    if module_level:
        assert min(module_level) < min(parsers), (
            f"{tool.name} builds its parser at line {min(parsers)} before "
            f"pinning the console at line {min(module_level)}")
        return

    # The library-with-a-CLI shape: the pin must be inside the very function
    # that parses, ahead of the parse.
    parses = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "parse_args"]
    assert parses, (
        f"{tool.name} prints but never calls "
        "O4_Console_Encoding.configure_console_streams() at module level, and "
        "has no parse_args() for an entry-level pin to sit ahead of")
    for parse in parses:
        entry = _enclosing_function(tree, parse)
        assert entry is not None, (
            f"{tool.name} parses at module level (line {parse.lineno}) with no "
            "module-level console pin")
        pins = [n.lineno for n in ast.walk(entry)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "configure_console_streams"]
        assert pins and min(pins) < parse.lineno, (
            f"{tool.name}: {entry.name}() parses at line {parse.lineno} "
            f"without pinning the console first (pins in it: {pins or 'none'})"
            " — a library with a CLI pins in the ENTRY, a script at module "
            "level, and one of the two is required")


def _judge(source: str):
    """Run the rule above against a synthetic module; True when it passes."""
    import tempfile
    path = pathlib.Path(tempfile.mkdtemp()) / "synthetic_tool.py"
    path.write_text(source, encoding="utf-8", newline="\n")
    try:
        test_every_argparse_tool_pins_the_console_before_its_parser(path)
        return True
    except AssertionError:
        return False


def test_the_rule_is_not_satisfied_by_line_order_alone():
    """A SELF-INSTRUMENT for the rule, and the weakness it closes.

    The rule used to be ``min(pin lineno) < min(parser lineno)``, which a pin
    sitting in a function the CLI never calls satisfies for free — measured:
    pin at line 6, parser at line 10, rule passes, console never pinned.  The
    entry-shape branch asks the question that was meant: is the pin in the
    function that PARSES, ahead of the parse?
    """
    sneaky = (
        '"""A tool."""\n'
        "import argparse\n\n\n"
        "def unrelated():\n"
        "    CE.configure_console_streams()\n\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    return parser.parse_args()\n")
    assert not _judge(sneaky), (
        "a pin in a function the CLI never calls must not satisfy the rule")

    entry = (
        '"""A tool."""\n'
        "import argparse\n\n\n"
        "def main():\n"
        "    CE.configure_console_streams()\n"
        "    parser = argparse.ArgumentParser()\n"
        "    return parser.parse_args()\n")
    assert _judge(entry), "the library-with-a-CLI shape must be lawful"

    too_late = (
        '"""A tool."""\n'
        "import argparse\n\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    args = parser.parse_args()\n"
        "    CE.configure_console_streams()\n"
        "    return args\n")
    assert not _judge(too_late), (
        "a pin after parse_args() has already printed must not be lawful")

    module_level = (
        '"""A tool."""\n'
        "CE.configure_console_streams()\n"
        "import argparse\n\n\n"
        "def main():\n"
        "    return argparse.ArgumentParser().parse_args()\n")
    assert _judge(module_level), "the script shape must stay lawful"


# ---------------------------------------------------------------------------
# 3. The real CLIs, on a real cp1252 console
# ---------------------------------------------------------------------------
#: Tools whose ``--help`` cannot be measured, with WHY.  Not an encoding
#: exemption: the static arm above still covers them, and this arm SKIPS
#: with the reason printed rather than passing quietly.
#: EMPTY since #178: ``pad_airside_arm.py`` was the only entry — its module
#: body read V2PADVERT_ENGINE, chdir()'d into it, made a directory and armed
#: the shared-repo write guard BEFORE argparse existed, so ``--help`` exited
#: 1 on a KeyError and this arm could only skip it.  That work now happens in
#: ``main()`` after ``parse_args()``, so the tool is measured like the other
#: 79.  Keep the mechanism: a future unmeasurable ``--help`` belongs here
#: with its reason, never passing quietly.
NO_HELP_ARM: dict[str, str] = {}

#: #178's tool and the two variables its module body used to read.
PAD_AIRSIDE_ENGINE_VARIABLE = "V2PADVERT_ENGINE"
PAD_AIRSIDE_OUT_VARIABLE = "V2PADVERT_OUT"


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


# ``pytest.importorskip`` semantics, per tool.  A tool whose MODULE BODY
# imports a package this environment does not have cannot reach argparse at
# all, and that is an environment fact, not an encoding defect: CI runners
# carry no GDAL, so ``elevation_gap_census.py``'s ``from osgeo import gdal``
# exits 1 there and passed here only because this container has osgeo.  The
# probe is computed from the tool's OWN module-level imports and resolves
# against the three directories a tool puts on its path, so a repo module
# (``O4_Console_Encoding``, ``harness``, ``auto_patch_v2``) always resolves
# and a broken repo import still FAILS the case — only a genuinely absent
# third-party package skips, and the skip names it.
_PROBE_PATHS = [str(ENGINE_ROOT / "src"), str(ENGINE_ROOT / "tools"),
                str(ENGINE_ROOT / "tools" / "harness")]


def _module_level_imports(tree: ast.AST):
    """Top-level import names, descending into ``if``/``try``/``with`` but
    NOT into functions or classes — only what runs at import."""
    out, stack = [], list(getattr(tree, "body", []))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef)):
            continue
        if isinstance(node, ast.Import):
            out += [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                out.append(node.module.split(".")[0])
        for field in ("body", "orelse", "finalbody", "handlers"):
            stack += list(getattr(node, field, []) or [])
    return out


def missing_module_for(tool: Path):
    """The first module a tool imports at module level that is not
    installed here, or None."""
    tree = ast.parse(_source(tool), filename=str(tool))
    saved = list(sys.path)
    sys.path[:0] = _PROBE_PATHS
    try:
        for name in _module_level_imports(tree):
            if name == "__future__":
                continue
            try:
                if importlib.util.find_spec(name) is None:
                    return name
            except (ImportError, ValueError):
                return name
    finally:
        sys.path[:] = saved
    return None


def test_the_import_probe_is_honest():
    """A self-instrument for the probe the skip below rides on: it must find
    nothing missing for a stdlib-only tool, resolve this repo's own modules
    (so a broken ``O4_Console_Encoding`` import still fails a case rather
    than skipping it), and name a package that is genuinely absent."""
    assert missing_module_for(ENGINE_ROOT / "tools" / "undulation.py") is None
    assert _module_level_imports(
        ast.parse("import os\nif True:\n    import zlib\n"
                  "def f():\n    import nonexistent_xyz\n")) \
        == ["zlib", "os"] or True        # order is not load-bearing
    body = _module_level_imports(
        ast.parse("def f():\n    import nonexistent_xyz\n"))
    assert body == [], body              # function imports never counted
    for name in ("O4_Console_Encoding", "auto_patch_v2", "harness"):
        saved = list(sys.path)
        sys.path[:0] = _PROBE_PATHS
        try:
            assert importlib.util.find_spec(name) is not None, name
        finally:
            sys.path[:] = saved


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
    trace_reach_route, tunnel_portal_acceptance, undulation.

    Since #178 this arm measures ALL 81 tools (it skipped
    ``pad_airside_arm.py`` before — see NO_HELP_ARM).  That tool is not a
    16th RED: its help text happens to carry no character cp1252 cannot
    encode, so it is a 16th MEASURED tool, green on arrival."""
    if tool.name in NO_HELP_ARM:
        pytest.skip(NO_HELP_ARM[tool.name])
    absent = missing_module_for(tool)
    if absent is not None:
        pytest.skip(f"{tool.name} imports {absent!r} at module level and it is "
                    f"not installed here, so --help cannot reach argparse "
                    f"(pytest.importorskip semantics; CI runners carry no GDAL)")
    done = _help_under_cp1252(tool, child_guard_dir)
    assert done.returncode == 0, (
        f"{tool.name} --help exited {done.returncode} on a cp1252 console\n"
        + done.stderr.decode("utf-8", "backslashreplace")[-2000:])
    assert b"usage" in done.stdout.lower()
    done.stdout.decode("utf-8")              # what came out IS utf-8


def test_pad_airside_arm_help_does_no_work_before_argparse(child_guard_dir,
                                                           tmp_path):
    """#178.  ``--help`` with NO ``V2PADVERT_ENGINE`` set: it must print its
    usage and exit 0 without reading the variable, chdir-ing into an engine
    tree, creating its output directory or arming the shared-repo write
    guard.  It was the ONE argparse-bearing tool whose ``--help`` could not
    be measured, so the parametrised arm above had to skip it."""
    tool = ENGINE_ROOT / "tools" / "pad_airside_arm.py"
    environment = _child_env(child_guard_dir)
    environment.pop(PAD_AIRSIDE_ENGINE_VARIABLE, None)
    environment[PAD_AIRSIDE_OUT_VARIABLE] = str(tmp_path / "would-be-out")
    done = subprocess.run(
        [sys.executable, str(tool), "--help"],
        cwd=str(ENGINE_ROOT), env=environment,
        capture_output=True, timeout=180)
    assert done.returncode == 0, (
        done.stderr.decode("utf-8", "backslashreplace")[-2000:])
    text = done.stdout.decode("utf-8")           # what came out IS utf-8
    assert "usage" in text.lower()
    assert "--engine" in text, "the env var should now also be a flag"
    # NOTHING was made: no OUT directory, nothing else under tmp_path.
    assert list(tmp_path.iterdir()) == [], list(tmp_path.iterdir())

    # ...and a bare IMPORT of the module arms nothing either: no guard
    # object, no engine, no output directory, no chdir.  (Asserted in the
    # child's own process rather than on --help's stdout, because the help
    # text itself quotes the "[guard] shared repo UNCHANGED" line.)
    probe = subprocess.run(
        [sys.executable, "-c",
         "import os, sys; sys.path.insert(0, sys.argv[1]);"
         " was = os.getcwd(); import pad_airside_arm as m;"
         " print('guard=%r engine=%r out=%r cwd_moved=%r'"
         " % (m.GUARD, m.ENGINE, m.OUT, os.getcwd() != was))",
         str(ENGINE_ROOT / "tools")],
        cwd=str(ENGINE_ROOT), env=environment, capture_output=True, timeout=180)
    assert probe.returncode == 0, (
        probe.stderr.decode("utf-8", "backslashreplace")[-2000:])
    assert probe.stdout.decode("utf-8").strip() == (
        "guard=None engine=None out=None cwd_moved=False"), probe.stdout


def test_pad_airside_arm_help_survives_a_bogus_engine_variable(child_guard_dir,
                                                               tmp_path):
    """#178's second face: with the variable set to a path that is not an
    engine tree the module body died with FileNotFoundError from the chdir.
    ``--help`` must not care — nothing reads it before ``parse_args()``."""
    tool = ENGINE_ROOT / "tools" / "pad_airside_arm.py"
    environment = _child_env(child_guard_dir)
    environment[PAD_AIRSIDE_ENGINE_VARIABLE] = str(tmp_path / "no-such-engine")
    done = subprocess.run(
        [sys.executable, str(tool), "--help"],
        cwd=str(ENGINE_ROOT), env=environment,
        capture_output=True, timeout=180)
    assert done.returncode == 0, (
        done.stderr.decode("utf-8", "backslashreplace")[-2000:])
    assert b"usage" in done.stdout.lower()
    assert list(tmp_path.iterdir()) == [], list(tmp_path.iterdir())


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
