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

4. AN AIRPORT OVERLAY, twice (owner RULINGS 2026-10-13a (9)): what a real
   pack's DSF carries beyond bare objects — ``OBJECT_MSL`` and
   ``OBJECT_AGL`` placements, a draped polygon with a HOLE (two windings),
   a facade (three planes per point), and a road NETWORK of two segments
   meeting at a junction, one with shape points.  The shape point is the
   ``DSFTuple::insert`` of ``AddSegmentShapePoint`` — the line gcc flags
   with ``-Wstringop-overflow`` when it links the Linux binary — and the
   polygons and segments are what the encoder reorders.  Once with object
   definitions below 256 (every DSFTool must round-trip it: the control
   for a good tool), once with all of them above 255 (the trait again,
   now with everything else in the file).  The dump is compared with the
   text that went in as MULTISETS of placements, polygons and segments,
   coordinates within the pool's quantum — the semantics of the engine's
   ``dsf_write.compare_dumps``, which cannot be imported on a bare runner.

``--expect-crash`` is the control for check 3: it PASSES when the tool dies
on the trait file (and stops there).  That is the control showing the fixture discriminates — run
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

#: Comparison tolerances: a 1-degree tile at DIVISIONS 32 pools positions
#: at 1/32 deg / 65535 (4.8e-7 deg), headings at 360 / 65535 (0.0055 deg)
#: and elevations at the HEIGHTS quantum (0.03125 m).  Four quanta each.
TOL_DEG, TOL_HEADING, TOL_ELEV = 2e-6, 0.03, 0.13

_HEADER = ["A", "800", "DSF2TEXT", "", "DIVISIONS 32",
           "PROPERTY sim/west -123", "PROPERTY sim/east -122",
           "PROPERTY sim/north 48", "PROPERTY sim/south 47",
           "PROPERTY sim/planet earth", "PROPERTY sim/overlay 1"]


def overlay_text(defs: int, used: int) -> str:
    """A one-object overlay for tile +47-123 with ``defs`` object
    definitions, the object using definition ``used``."""
    rows = list(_HEADER)
    rows += [f"OBJECT_DEF objects/smoke_{i:03d}.obj" for i in range(defs)]
    rows.append(f"OBJECT {used} {PLACEMENT}")
    return "\n".join(rows) + "\n"


def airport_text(first_def: int) -> str:
    """An overlay with every row family an airport pack's DSF carries.
    Its three objects use definitions ``first_def .. first_def + 2``."""
    a, b, c = first_def, first_def + 1, first_def + 2
    rows = list(_HEADER)
    # the elevation pool's scale, as every real dump carries it: without
    # the row DSFTool pools MSL / AGL heights at 1 m (measured 2026-10-13)
    rows.insert(5, "HEIGHTS 0.03125 0.0")
    rows += [f"OBJECT_DEF objects/smoke_{i:03d}.obj" for i in range(300)]
    rows += ["POLYGON_DEF pavement/smoke_apron.pol",
             "POLYGON_DEF buildings/smoke_terminal.fac",
             "NETWORK_DEF lib/g10/roads.net",
             f"OBJECT {a} -122.500000000 47.500000000 90.000000",
             f"OBJECT {a} -122.510000000 47.510000000 180.000000",
             f"OBJECT_MSL {b} -122.520000000 47.520000000 131.500000000 45.000000",
             f"OBJECT_AGL {c} -122.530000000 47.530000000 12.250000000 270.000000",
             # a draped polygon: outer ring and one hole
             "BEGIN_POLYGON 0 65535 2",
             "BEGIN_WINDING",
             "POLYGON_POINT -122.600000000 47.600000000",
             "POLYGON_POINT -122.590000000 47.600000000",
             "POLYGON_POINT -122.590000000 47.610000000",
             "POLYGON_POINT -122.600000000 47.610000000",
             "END_WINDING",
             "BEGIN_WINDING",
             "POLYGON_POINT -122.597000000 47.603000000",
             "POLYGON_POINT -122.597000000 47.607000000",
             "POLYGON_POINT -122.593000000 47.607000000",
             "POLYGON_POINT -122.593000000 47.603000000",
             "END_WINDING",
             "END_POLYGON",
             # a facade, 12 m high: the third plane is the wall type
             "BEGIN_POLYGON 1 12 3",
             "BEGIN_WINDING",
             "POLYGON_POINT -122.700000000 47.700000000 0.000000000",
             "POLYGON_POINT -122.699000000 47.700000000 1.000000000",
             "POLYGON_POINT -122.699000000 47.701000000 0.000000000",
             "POLYGON_POINT -122.700000000 47.701000000 2.000000000",
             "END_WINDING",
             "END_POLYGON",
             # two road segments meeting at junction 2; the first has shape points
             "BEGIN_SEGMENT 0 50 1 -122.800000000 47.800000000 0.000000000",
             "SHAPE_POINT -122.799000000 47.800500000 0.000000000",
             "SHAPE_POINT -122.798000000 47.801500000 0.000000000",
             "END_SEGMENT 2 -122.797000000 47.802000000 0.000000000",
             "BEGIN_SEGMENT 0 30 2 -122.797000000 47.802000000 0.000000000",
             "END_SEGMENT 3 -122.795000000 47.803000000 0.000000000"]
    return "\n".join(rows) + "\n"


def structure(text: str) -> dict:
    """What a dump SAYS, free of what the encoder may change: definitions
    in order; placements, polygons and road segments as sorted lists (the
    encoder reorders them and renumbers the network's junctions)."""
    out: dict = {"defs": [], "overlay": False, "placements": [],
                 "polygons": [], "segments": []}
    poly = seg = None
    for raw in text.splitlines():
        t = raw.split("#")[0].split()
        if not t:
            continue
        kw = t[0]
        if kw.endswith("_DEF"):
            out["defs"].append((kw, t[1]))
        elif kw == "PROPERTY" and t[1:] == ["sim/overlay", "1"]:
            out["overlay"] = True
        elif kw in ("OBJECT", "OBJECT_MSL", "OBJECT_AGL"):
            out["placements"].append((kw, int(t[1]), [float(x) for x in t[2:]]))
        elif kw == "BEGIN_POLYGON":
            poly = (int(t[1]), int(t[2]), int(t[3]), [])
        elif kw == "BEGIN_WINDING" and poly:
            poly[3].append([])
        elif kw == "POLYGON_POINT" and poly:
            poly[3][-1].append([float(x) for x in t[1:]])
        elif kw == "END_POLYGON" and poly:
            out["polygons"].append(poly)
            poly = None
        elif kw == "BEGIN_SEGMENT":
            seg = (int(t[1]), int(t[2]), [[float(x) for x in t[4:6]]])
        elif kw == "SHAPE_POINT" and seg:
            seg[2].append([float(x) for x in t[1:3]])
        elif kw == "END_SEGMENT" and seg:
            seg[2].append([float(x) for x in t[2:4]])
            if seg[2][0] > seg[2][-1]:          # one segment, either end first
                seg[2].reverse()
            out["segments"].append(seg)
            seg = None
    for key in ("placements", "polygons", "segments"):
        out[key].sort()
    return out


def _close(a, b, tol: float) -> bool:
    """Nested lists of numbers equal within ``tol``; anything else equal."""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= tol
    return a == b


def _placement_close(a: tuple, b: tuple) -> bool:
    (kind, index, va), (kind_b, index_b, vb) = a, b
    if (kind, index, len(va)) != (kind_b, index_b, len(vb)):
        return False
    turn = abs(va[-1] - vb[-1]) % 360.0
    return (_close(va[:2], vb[:2], TOL_DEG)
            and min(turn, 360.0 - turn) <= TOL_HEADING
            and _close(va[2:-1], vb[2:-1], TOL_ELEV))


def differences(sent: str, came_back: str) -> list[str]:
    """Why the dump does not say what the text said; empty when it does."""
    want, got = structure(sent), structure(came_back)
    out = []
    if want["defs"] != got["defs"]:
        out.append(f"definitions: {len(want['defs'])} sent, {len(got['defs'])} "
                   "back, or their order changed")
    if not got["overlay"]:
        out.append("PROPERTY sim/overlay 1 is gone")
    for key, same in (("placements", _placement_close),
                      ("polygons", lambda a, b: _close(a, b, TOL_DEG)),
                      ("segments", lambda a, b: _close(a, b, TOL_DEG))):
        if len(want[key]) != len(got[key]):
            out.append(f"{key}: {len(want[key])} sent, {len(got[key])} back")
            continue
        out += [f"{key}: sent {a} came back {b}"
                for a, b in zip(want[key], got[key]) if not same(a, b)]
    return out


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


def round_trip(tool: str, work: str, name: str, sent: str
               ) -> tuple[str, subprocess.CompletedProcess, str]:
    """``(dsf path, the --dsf2text run, dumped text)`` of one fixture."""
    text_in = os.path.join(work, name + ".txt")
    dsf = os.path.join(work, name + ".dsf")
    text_out = os.path.join(work, name + ".dump.txt")
    with open(text_in, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(sent)
    encoded = _run(tool, "--text2dsf", text_in, dsf)
    if encoded.returncode != 0 or not os.path.isfile(dsf):
        _fail(f"{name}: --text2dsf exited {encoded.returncode}: {_said(encoded)}")
    dumped = _run(tool, "--dsf2text", dsf, text_out)
    text = ""
    if dumped.returncode == 0 and os.path.isfile(text_out):
        with open(text_out, encoding="utf-8", newline="") as handle:
            text = handle.read()
    return dsf, dumped, text


def check(tool: str, work: str, name: str, sent: str, *, trait: bool,
          expect_crash: bool = False) -> bool:
    """One fixture through the tool; ``False`` only for an expected crash."""
    dsf, dumped, text = round_trip(tool, work, name, sent)
    if _has_trait(dsf) != trait:
        _fail(f"{name}: the encoded file "
              + ("does not set a 16-bit definition before its first pool "
                 "select — the fixture tests nothing" if trait
                 else "carries the trait — it is no control"))
    if expect_crash:
        if dumped.returncode == 0:
            _fail(f"{name}: --expect-crash, but the tool dumped the file")
        print(f"== {name}: the tool died as expected (exit {dumped.returncode})")
        return False
    if dumped.returncode != 0:
        _fail(f"{name}: --dsf2text exited {dumped.returncode}: "
              f"{_said(dumped) or 'no output'}")
    wrong = differences(sent, text)
    if wrong:
        _fail(f"{name}: the dump does not say what the text said:\n  "
              + "\n  ".join(wrong[:12]))
    return True


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
        check(tool, work, "plain", overlay_text(2, 1), trait=False)
        print("== plain overlay: text -> DSF -> text keeps its placement")
        check(tool, work, "airport", airport_text(1), trait=False)
        print("== airport overlay (MSL/AGL objects, holed polygon, facade, "
              "road network with shape points): text -> DSF -> text keeps every row")
        if not check(tool, work, "trait", overlay_text(300, 299), trait=True,
                     expect_crash=expect_crash):
            return 0
        print("== trait file (SetDefinition16 before the first PoolSelect): dumps")
        check(tool, work, "airport-trait", airport_text(297), trait=True)
        print("== airport overlay with the trait: dumps and keeps every row")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
