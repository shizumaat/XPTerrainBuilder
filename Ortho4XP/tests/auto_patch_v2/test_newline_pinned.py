"""EVERY EMIT-PATH TEXT WRITER PINS ``newline`` — STANDING LAW (lane
``xplatcrlf``, 2026-09-17).

Python's text mode translates ``"\\n"`` to ``os.linesep`` on write.  On
POSIX that is a no-op; on Windows it writes ``"\\r\\n"``.  Nothing in the
engine ever asks for that translation — it is simply the default of an
unqualified ``open(path, "w")`` / ``Path.write_text(text)``.

MEASURED (lane ``xplatdeterminism``, Release run 35274144555, the
interventional arm ``8615f4f9`` in which all three platforms solved ONE
programme):

    file                    mac        linux      windows    windows, CRLF->LF
    CYXY_auto.patch.osm     829,277    829,181    851,654    829,279
    CYXY.report.json      3,234,103  3,233,661  3,407,754  3,234,087
    CYXY.xplat.json           5,023      5,035      5,313        5,076

The Windows patch carried 22,375 ``\\r\\n`` and zero lone ``\\r`` — exactly
the 22,375 ``\\n`` the POSIX patch carries, i.e. one inserted byte per
line and nothing else.  Normalising the CRLF away puts Windows inside
the mac-vs-linux spread that RULINGS 2026-09-17d already attributes to
PROJ's forward tmerc last ulp.

So the law: a module on the emit path opens a TEXT file for writing with
``newline=`` pinned, at the call.  ``newline="\\n"`` is the engine's own
terminator for a file the engine authors; ``newline=""`` belongs to a
format whose writer owns the terminator itself (``csv``).  An unpinned
call is the defect this twin refuses, whatever it happens to write today.

SCOPE.  Every module under ``src/auto_patch_v2/`` (v2 is the only
engine, RULINGS 2026-09-13au), plus the non-v2 modules that write a file
belonging to a v2 build's output set (``_EMIT_PATH_EXTRA``).  The wider
Ortho4XP TILE writers (``src/O4_*.py``) are deliberately NOT in scope:
they are a separate surface with their own readers, and widening this
twin to them without censusing those readers first would be the
consumer-census defect (RULINGS 2026-08-30l).
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

# Non-v2 modules that write a file belonging to a v2 build's output set:
# the engine entry's per-airport verify log, the tile driver's worklist
# and shared verify log, the v1-era layout sidecar and forensics dump,
# the constant-DEM dump, the solve-capture manifest, the object rebake
# provenance and the object-terrain assembly cache.
_EMIT_PATH_EXTRA = (
    "auto_patch/engine_v2.py",
    "auto_patch/driver.py",
    "auto_patch/layout.py",
    "auto_patch/constant_dem.py",
    "auto_patch/solve_capture.py",
    "auto_patch/object_rebake.py",
    "auto_patch/object_terrain_assembly.py",
)

# An allowlist entry is "<relpath>:<code line, stripped>" -> one-line
# reason.  Keyed by the LINE TEXT, not the line number, so an entry
# cannot drift onto an unrelated call when the file moves.  EMPTY is the
# intended steady state.
_ALLOWLIST: dict[str, str] = {}

# ``open`` attribute calls on these bases are not text-mode writers.
_NOT_TEXT_OPEN_BASES = {"os", "gzip", "bz2", "lzma", "zipfile", "tarfile",
                        "np", "numpy"}


def _scoped_files() -> list[Path]:
    files = sorted((SRC / "auto_patch_v2").rglob("*.py"))
    for rel in _EMIT_PATH_EXTRA:
        p = SRC / rel
        assert p.exists(), f"_EMIT_PATH_EXTRA names a missing file: {rel}"
        files.append(p)
    return files


def _base_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    return None


def _mode_arg(call: ast.Call, positional_index: int) -> tuple[bool, object]:
    """``(is_statically_known, value)`` for the mode argument."""
    for kw in call.keywords:
        if kw.arg == "mode":
            if isinstance(kw.value, ast.Constant):
                return True, kw.value.value
            return False, None
        if kw.arg is None:
            return False, None          # **kwargs — not readable statically
    if len(call.args) > positional_index:
        node = call.args[positional_index]
        if isinstance(node, ast.Constant):
            return True, node.value
        return False, None
    return True, None                   # absent -> the callee's own default


def _text_write_calls(path: Path) -> list[tuple[int, str, str]]:
    """``(lineno, what, kind)`` for every text write/append call.

    ``kind`` is ``"unpinned"`` (no ``newline=``), ``"unknown-mode"`` (the
    mode is not a literal, so the call cannot be judged statically) or
    ``"ok"``.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue

        if name == "write_text":
            what = "write_text"
        elif name in ("open", "NamedTemporaryFile", "TemporaryFile",
                      "SpooledTemporaryFile"):
            if _base_name(func) in _NOT_TEXT_OPEN_BASES:
                continue
            # builtins.open takes (file, mode); Path.open / tempfile.*
            # take mode first.
            idx = 1 if (name == "open" and isinstance(func, ast.Name)) else 0
            known, mode = _mode_arg(node, idx)
            if not known:
                out.append((node.lineno, f"{name}(mode=<not a literal>)",
                            "unknown-mode"))
                continue
            if mode is None:
                mode = "r" if name == "open" else "w+b"
            if not isinstance(mode, str) or "b" in mode:
                continue
            if not any(c in mode for c in "wax+"):
                continue
            what = f"{name}({mode!r})"
        else:
            continue

        pinned = any(kw.arg == "newline" for kw in node.keywords)
        out.append((node.lineno, what, "ok" if pinned else "unpinned"))
    return out


def _allow_key(path: Path, lineno: int) -> str:
    rel = path.relative_to(SRC).as_posix()
    line = path.read_text(encoding="utf-8").splitlines()[lineno - 1].strip()
    return f"{rel}:{line}"


def test_every_allowlist_entry_carries_a_reason():
    for key, reason in _ALLOWLIST.items():
        assert reason.strip(), f"allowlist entry {key!r} has no reason"


def test_no_emit_path_text_writer_leaves_newline_to_the_platform():
    """RULINGS 2026-09-17: Windows wrote the CYXY patch with CRLF."""
    offenders: list[str] = []
    for path in _scoped_files():
        for lineno, what, kind in _text_write_calls(path):
            if kind == "ok":
                continue
            if _allow_key(path, lineno) in _ALLOWLIST:
                continue
            rel = path.relative_to(SRC).as_posix()
            offenders.append(f"{rel}:{lineno} {what} [{kind}]")
    assert not offenders, (
        f"{len(offenders)} emit-path text writer(s) leave the line "
        f"terminator to the platform (Windows writes CRLF):\n  "
        + "\n  ".join(offenders)
    )


def test_the_scan_sees_the_shapes_it_claims_to_see():
    """The twin's own instrument.  Without this, the law above can go
    green because the scanner recognises nothing."""
    import tempfile

    sample = (
        'from pathlib import Path\n'
        'import tempfile\n'
        'open("a", "w")\n'
        'open("b", "w", newline="\\n")\n'
        'open("c", "wb")\n'
        'open("d")\n'
        'Path("e").write_text("x")\n'
        'Path("f").write_text("x", newline="\\n")\n'
        'Path("g").open("w")\n'
        'Path("h").open("w", newline="")\n'
        'tempfile.NamedTemporaryFile(mode="w")\n'
        'open("i", mode_from_caller)\n'
    )
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.py"
        p.write_text(sample, encoding="utf-8", newline="\n")
        found = _text_write_calls(p)
    by_line = {ln: (what, kind) for ln, what, kind in found}
    assert by_line[3] == ("open('w')", "unpinned")
    assert by_line[4] == ("open('w')", "ok")
    assert 5 not in by_line and 6 not in by_line          # 'wb', and read
    assert by_line[7] == ("write_text", "unpinned")
    assert by_line[8] == ("write_text", "ok")
    assert by_line[9] == ("open('w')", "unpinned")        # Path.open
    assert by_line[10] == ("open('w')", "ok")
    assert by_line[11] == ("NamedTemporaryFile('w')", "unpinned")
    assert by_line[12] == ("open(mode=<not a literal>)", "unknown-mode")
