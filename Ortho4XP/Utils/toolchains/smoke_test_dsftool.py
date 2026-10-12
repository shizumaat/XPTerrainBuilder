#!/usr/bin/env python3
"""Smoke-test a DSFTool binary before bundling it as Utils/<platform>/DSFTool.

    python3 smoke_test_dsftool.py <path-to-DSFTool> [--expect-crash]

Standard library only: it runs on a bare CI runner (macOS, Windows, Linux)
as well as under the engine's venv.  Checks, in order:

1. ``--version`` names the pinned release (``DSFTool 2.4.0-b1``, Scenery
   Tools ``24-5``): the patched build must keep the version string, which
   DSFTool writes into line 2 of every dump and the engine's round-trip
   verify compares as a structural row.
2. A plain overlay (two object definitions) goes text -> DSF -> text and
   keeps its placement.
3. THE TRAIT of issue #568: an overlay whose first object uses a
   definition index above 255.  DSFTool's own writer emits
   "SetDefinition16, PoolSelect, Object", so the encoded file sets a
   16-bit definition BEFORE its first pool select — confirmed here with
   the engine's own predicate (``dsf_commands.select_pool_first``, loaded
   by file path; that module is standard library only).  The stock
   2.4.0-b1 dies with SIGSEGV on ``--dsf2text`` of that file; a build
   carrying upstream ``9c1a06c7b`` + ``a3725c8f5`` dumps it.

``--expect-crash`` inverts check 3: it PASSES when the tool dies on the
trait file.  That is the control showing the fixture discriminates — run
it against the stock binary.  The stock crash is a read far outside a
table, so on a file this small it depends on what the process's memory
holds: measured 2026-10-12 on macOS, the stock tool died (SIGSEGV) from
this script and survived the same file under other paths.  The control
is therefore evidence when it passes and nothing when it does not; the
census over real packs (``tools/dsftool_dump_census.py``) is the measure.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile

VERSION_PINS = ("DSFTool 2.4.0-b1", "X-Plane Scenery Tools release: 24-5")
_HERE = os.path.dirname(os.path.abspath(__file__))
_DSF_COMMANDS = os.path.join(_HERE, "..", "..", "src", "auto_patch_v2",
                             "airport", "dsf_commands.py")
PLACEMENT = "-122.500000000 47.500000000 90.000000"


def overlay_text(defs: int, used: int) -> str:
    """A one-object overlay for tile +47-123 with ``defs`` object
    definitions, the object using definition ``used``."""
    rows = ["A", "800", "DSF2TEXT", "", "DIVISIONS 32",
            "PROPERTY sim/west -123", "PROPERTY sim/east -122",
            "PROPERTY sim/north 48", "PROPERTY sim/south 47",
            "PROPERTY sim/planet earth", "PROPERTY sim/overlay 1"]
    rows += [f"OBJECT_DEF objects/smoke_{i:03d}.obj" for i in range(defs)]
    rows.append(f"OBJECT {used} {PLACEMENT}")
    return "\n".join(rows) + "\n"


def _run(tool: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([tool, *args], capture_output=True, timeout=120)


def _said(proc: subprocess.CompletedProcess) -> str:
    return (proc.stdout + proc.stderr).decode("utf-8", "replace").strip()


def _fail(why: str) -> None:
    print(f"FAIL: {why}", file=sys.stderr)
    sys.exit(1)


def _has_trait(dsf_path: str) -> bool:
    spec = importlib.util.spec_from_file_location("dsf_commands", _DSF_COMMANDS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with open(dsf_path, "rb") as handle:
        return module.select_pool_first(handle.read()) is not None


def round_trip(tool: str, work: str, name: str, defs: int, used: int
               ) -> tuple[str, subprocess.CompletedProcess, str]:
    """``(dsf path, the --dsf2text run, dumped text)`` of one fixture."""
    text_in = os.path.join(work, name + ".txt")
    dsf = os.path.join(work, name + ".dsf")
    text_out = os.path.join(work, name + ".dump.txt")
    with open(text_in, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(overlay_text(defs, used))
    encoded = _run(tool, "--text2dsf", text_in, dsf)
    if encoded.returncode != 0 or not os.path.isfile(dsf):
        _fail(f"{name}: --text2dsf exited {encoded.returncode}: {_said(encoded)}")
    dumped = _run(tool, "--dsf2text", dsf, text_out)
    text = ""
    if dumped.returncode == 0 and os.path.isfile(text_out):
        with open(text_out, encoding="utf-8", newline="") as handle:
            text = handle.read()
    return dsf, dumped, text


def _kept(text: str, defs: int, used: int) -> bool:
    rows = text.splitlines()
    placed = [r.split() for r in rows if r.startswith("OBJECT ")]
    return (sum(r.startswith("OBJECT_DEF ") for r in rows) == defs
            and len(placed) == 1 and placed[0][1] == str(used)
            and abs(float(placed[0][2]) + 122.5) < 1e-4
            and abs(float(placed[0][3]) - 47.5) < 1e-4
            and "PROPERTY sim/overlay 1" in rows)


def main(argv: list[str]) -> int:
    expect_crash = "--expect-crash" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if len(paths) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    tool = os.path.abspath(paths[0])
    with open(tool, "rb") as handle:
        print(f"== {tool}\n   sha256 {hashlib.sha256(handle.read()).hexdigest()}")

    version = _said(_run(tool, "--version"))
    print("== version\n   " + version.replace("\n", "\n   "))
    for pin in VERSION_PINS:
        if pin not in version:
            _fail(f"--version does not say {pin!r}")

    with tempfile.TemporaryDirectory(prefix="dsftool_smoke_") as work:
        dsf, dumped, text = round_trip(tool, work, "plain", 2, 1)
        if _has_trait(dsf):
            _fail("plain: the control fixture carries the trait")
        if dumped.returncode != 0 or not _kept(text, 2, 1):
            _fail(f"plain: --dsf2text exited {dumped.returncode}: {_said(dumped)}")
        print("== plain overlay: text -> DSF -> text keeps its placement")

        dsf, dumped, text = round_trip(tool, work, "trait", 300, 299)
        if not _has_trait(dsf):
            _fail("trait: the encoded file does not set a 16-bit definition "
                  "before its first pool select — the fixture tests nothing")
        if expect_crash:
            if dumped.returncode == 0:
                _fail("trait: --expect-crash, but the tool dumped the file")
            print(f"== trait file: the tool died as expected (exit {dumped.returncode})")
            return 0
        if dumped.returncode != 0 or not _kept(text, 300, 299):
            _fail(f"trait: --dsf2text exited {dumped.returncode} on a file that "
                  f"sets a 16-bit definition before its first pool select: "
                  f"{_said(dumped) or 'no output'}")
        print("== trait file (SetDefinition16 before the first PoolSelect): dumps")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
