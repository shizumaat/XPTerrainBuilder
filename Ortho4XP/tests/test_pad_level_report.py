"""Twin for ``tools/pad_level_report.py`` (promoted 2026-09-10, lane
``v2padlevel``; RULINGS 2026-09-10l/10y, tool discipline `7e90032`).

The three reads are held to what they CLAIM: the plane fit is the
least-squares plane's residual and tilt; the delta joins two patches on
each way's own identity tag and never on proximity; a ring's SPREAD is
reported before and after; and the index row exists (a tool absent from
the index is treated as absent).
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "pad_level_report", ROOT / "tools" / "pad_level_report.py")
plr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plr)


def _patch(path: Path, ways: dict[str, list[tuple[float, float, float]]]) -> Path:
    """A minimal emitted patch: one way per ref, ``alt_abs`` per node."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    nid = 0
    for ref, nodes in ways.items():
        ids = []
        for lat, lon, z in nodes:
            nid += 1
            ids.append(nid)
            out.append(f"  <node id='{nid}' lat='{lat}' lon='{lon}'>"
                       f"<tag k='alt_abs' v='{z}'/></node>")
        out.append(f"  <way id='{1000 + len(ids)}{abs(hash(ref)) % 97}'>")
        out += [f"    <nd ref='{i}'/>" for i in ids]
        out.append("    <tag k='o4_role' v='building'/>")
        out.append(f"    <tag k='o4_ref' v='{ref}'/>")
        out.append("  </way>")
    out.append("</osm>")
    path.write_text("\n".join(out))
    return path


def test_plane_fit_is_the_least_squares_plane_not_the_ring_spread():
    """A tilted plane has a SPREAD but no residual; a dished ring has
    both.  09c's "one plane" is the residual, the 1 % ceiling the tilt."""
    xy = [(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0)]
    flat = np.array([10.0, 10.0, 10.0, 10.0])
    resid, tilt = plr.plane_fit(xy, flat)
    assert resid < 1e-9 and tilt < 1e-9
    tilted = np.array([10.0 + 0.004 * x - 0.002 * y for x, y in xy])
    resid, tilt = plr.plane_fit(xy, tilted)
    assert resid < 1e-9
    assert abs(tilt - math.hypot(0.004, 0.002)) < 1e-9
    dished = tilted.copy()
    dished[2] -= 0.4
    resid, _tilt = plr.plane_fit(xy, dished)
    assert resid > 0.05                       # the ring is no longer a plane


def test_delta_joins_on_the_ways_own_identity_and_reports_spread(tmp_path, capsys):
    a = _patch(tmp_path / "a.osm", {
        "padA": [(1.0, 1.0, 100.0), (1.0, 1.001, 100.0)],
        "padB": [(2.0, 2.0, 50.0), (2.0, 2.001, 50.0)],
    })
    b = _patch(tmp_path / "b.osm", {
        # padA rises 0.50 m and gains a 0.20 m spread; padB moves 0.01 m
        "padA": [(1.0, 1.0, 100.4), (1.0, 1.001, 100.6)],
        "padB": [(2.0, 2.0, 50.01), (2.0, 2.001, 50.01)],
    })
    A, B = plr.read_levels(a, "building"), plr.read_levels(b, "building")
    assert set(A) == {"padA", "padB"} == set(B)
    assert A["padA"][0] == pytest.approx(100.0)
    assert B["padA"][0] == pytest.approx(100.5)
    assert plr.main(["delta", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "2 joined; 1 moved > 0.05 m" in out
    assert "rose 1, fell 0" in out
    assert "0.000 -> 0.200" in out            # padA's ring spread, before/after


def test_a_way_present_in_one_patch_only_is_never_a_move(tmp_path, capsys):
    """The join is identity: an added pad has no delta to report, and
    counting it as one would make every emitter change read as a pull."""
    a = _patch(tmp_path / "a.osm", {"padA": [(1.0, 1.0, 100.0)]})
    b = _patch(tmp_path / "b.osm", {"padA": [(1.0, 1.0, 100.0)],
                                    "padNew": [(3.0, 3.0, 7.0)]})
    assert plr.main(["delta", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "1 / 2 ways, 1 joined; 0 moved" in out


def test_the_tool_carries_its_index_rows():
    """RULINGS `7e90032`: a tool absent from the index is treated as
    absent, and the row lands in the same commit as the tool."""
    assert "pad_level_report.py" in (ROOT / "tools" / "README.md").read_text()
    idx = ROOT.parent / "tools" / "INDEX.md"
    if idx.exists():                          # absent in a pre-index worktree
        assert "pad_level_report.py" in idx.read_text()
