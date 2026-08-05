"""Decline loudness for the cross-strip seam healer (spec
seam-continuity-v3 §2, adjudication item 3).

``blend_cross_strip_seam_steps`` refuses to re-level a cluster whose every
logical node is an ANCHOR — a donor-pavement weld or a cross-tile seam
contract.  That refusal is CORRECT: a healer must never silently regrade
fabric another authority owns (single-authority doctrine).  Its SILENCE
was the defect — those clusters are precisely the rows that survive into
``check_grade``'s ``seam::seam`` census, and nothing in the build named
them.

v3 §2 therefore requires: **every declined cluster emits one named
forensics row — site, step height, anchored sides — unconditionally.**
Pre-registered band 5: report rows == declined clusters, zero silent
declines.  These twins defend exactly that equality, plus the
unconditionality (no env gate can suppress a decline row) and the field
content a forensics reader needs.

Hermetic: stub shapes and a stub layout anchored ON a tile meridian, so
``x ≈ 0`` vertices are cross-tile seam contracts and therefore anchors.
No builds, no network, no DEM.
"""
from __future__ import annotations

import ast
import inspect
import math
import re
import textwrap
from pathlib import Path

from shapely.geometry import Polygon

from auto_patch import adjacent_ground
from auto_patch.adjacent_ground import (
    blend_cross_strip_seam_steps,
    report_strip_seam_declines,
)

_DECLINE_ROW = re.compile(r"\[strip-seam\] DECLINED ")
_GUARD_DECLINED_ROW = re.compile(r"\[strip-seam\] GUARD-DECLINED ")
_GUARD_CLAMPED_ROW = re.compile(r"\[strip-seam\] GUARD-CLAMPED ")
_DECLINE_COUNT = re.compile(
    r"cross-strip seam healer left (\d+) step\(s\) standing — "
    r"DECLINED (\d+) cluster\(s\) \(every node anchored\), "
    r"GUARD-DECLINED (\d+) node\(s\) \(bounds inverted\), "
    r"GUARD-CLAMPED (\d+) node")


class _StubShape:
    def __init__(self, ring, altitudes, role="graded_strip"):
        self.polygon = Polygon(ring)
        self.node_altitudes = list(altitudes) + [altitudes[0]]
        self.role = role
        self.ref = "adjacent_ground"


class _StubLayout:
    """Local metres anchored ON a tile meridian: x = 0 maps to an exact
    integer longitude, so small-|x| vertices sit in the tile-seam band and
    are anchors (the only anchor class a stub layout can produce — there
    are no weld-donor pavements here)."""

    def __init__(self, shapes, icao="TEST"):
        self.shapes = shapes
        self.icao = icao
        self._anchor_lat = -12.2
        self._anchor_lon = -77.0

    def m_to_ll(self, x, y):
        latitude = self._anchor_lat + y / 111320.0
        longitude = self._anchor_lon + x / (
            111320.0 * math.cos(math.radians(latitude)))
        return latitude, longitude


def _square(x0, y0, size=20.0):
    return [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size),
            (x0, y0 + size)]


def _seam_band_pair(y0, step=3.0):
    """Two strips 3 m apart STRADDLING the meridian with a ``step`` metre
    disagreement: every node of the resulting cluster is a seam-band
    anchor, so the healer declines it."""
    return (_StubShape(_square(-24.0, y0), [10.0] * 4),
            _StubShape(_square(-1.0, y0), [10.0 + step] * 4))


def _interior_pair(y0, step=3.0):
    """Two strips 1 m apart FAR from the meridian: no node is an anchor,
    so the healer blends them (the control — a cluster that is NOT
    declined must not produce a decline row)."""
    return (_StubShape(_square(180.0, y0), [10.0] * 4),
            _StubShape(_square(201.0, y0), [10.0 + step] * 4))


def test_a_declined_cluster_emits_exactly_one_named_report_row(capsys):
    declined_a, declined_b = _seam_band_pair(300.0)
    layout = _StubLayout([declined_a, declined_b])

    blend_cross_strip_seam_steps(layout.shapes, layout)

    out = capsys.readouterr().out
    rows = [line for line in out.splitlines() if _DECLINE_ROW.search(line)]
    # Two independent clusters form (the pair's lower and upper corners
    # are 20 m apart, beyond the pairing radius) — one row each.
    assert len(rows) == 2, out
    for row in rows:
        assert "site=(" in row and "ll=" in row, row
        assert "step=3.000m" in row, row
        assert "anchored=tile_seam:2" in row, row
        assert "shapeIDs=[0, 1]" in row, row
        assert "lo=(" in row and "hi=(" in row, row
    assert "TEST" in rows[0]


def test_report_rows_equal_declined_clusters_and_only_declined_clusters(
        monkeypatch, capsys):
    """BAND 5, the hard one: rows == declined clusters.  A HEALED cluster
    in the same run must contribute no row, and every declined cluster
    must contribute exactly one."""
    seen: list = []
    real = adjacent_ground.report_strip_seam_declines

    def _spy(declined, layout, guarded=()):
        seen.append(list(declined))
        return real(declined, layout, guarded)

    monkeypatch.setattr(adjacent_ground, "report_strip_seam_declines", _spy)

    shapes = list(_seam_band_pair(300.0)) + list(_interior_pair(100.0))
    layout = _StubLayout(shapes)
    moved = blend_cross_strip_seam_steps(layout.shapes, layout)

    out = capsys.readouterr().out
    rows = [line for line in out.splitlines() if _DECLINE_ROW.search(line)]
    assert len(seen) == 1, "the report must be emitted exactly once per run"
    assert len(rows) == len(seen[0]), (
        f"{len(rows)} report row(s) for {len(seen[0])} declined cluster(s) "
        f"— a silent decline is a v3 §2 violation")
    assert len(seen[0]) == 2, seen[0]
    # The healed cluster really did heal: declines are not the whole
    # population, so the equality above is not vacuous.
    assert moved > 0
    counted = _DECLINE_COUNT.search(out)
    assert counted and int(counted.group(2)) == len(rows), out


def test_the_count_line_is_emitted_even_when_nothing_is_declined(capsys):
    """"No declines" must be distinguishable from "the healer did not
    run" — otherwise a silently skipped pass reads as a clean airport."""
    layout = _StubLayout(list(_interior_pair(100.0)))

    blend_cross_strip_seam_steps(layout.shapes, layout)

    out = capsys.readouterr().out
    counted = _DECLINE_COUNT.search(out)
    assert counted is not None, out
    assert int(counted.group(2)) == 0
    assert not [line for line in out.splitlines()
                if _DECLINE_ROW.search(line)]


def test_the_decline_report_is_unconditional(monkeypatch, capsys):
    """UNCONDITIONAL means unconditional: no ``O4_*`` gate, no debug flag.

    Source twin plus behaviour — the source twin is the load-bearing half
    (a behavioural test passes just as well with a gate that happens to be
    on by default, which is exactly how loudness gets lost)."""
    src = inspect.getsource(report_strip_seam_declines)
    assert "environ" not in src and "getenv" not in src, (
        "report_strip_seam_declines reads the environment — a declined "
        "cluster must report regardless of any gate")

    # The call must be a TOP-LEVEL statement of the healer, not nested in
    # an ``if``/``try``/``with``: a default-on gate is still a gate, and a
    # behavioural test cannot tell the difference.
    fn = ast.parse(textwrap.dedent(
        inspect.getsource(blend_cross_strip_seam_steps))).body[0]

    def _is_report(stmt):
        return (isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)
                and stmt.value.func.id == "report_strip_seam_declines")

    top_level = [s for s in fn.body if _is_report(s)]
    anywhere = [n for n in ast.walk(fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "report_strip_seam_declines"]
    assert len(anywhere) == 1, (
        f"{len(anywhere)} call sites for the decline report — exactly one, "
        f"unconditional, is the contract")
    assert len(top_level) == 1, (
        "the decline report is nested inside a conditional/try block — a "
        "declined cluster must report unconditionally")

    for name in ("O4_ADJACENT_GROUND_DEBUG", "O4_STEP_DEBUG",
                 "O4_SEAM_TAPER_PIN", "O4_LOG_VERBOSITY"):
        monkeypatch.delenv(name, raising=False)
    declined_a, declined_b = _seam_band_pair(300.0)
    layout = _StubLayout([declined_a, declined_b])
    blend_cross_strip_seam_steps(layout.shapes, layout)
    assert [line for line in capsys.readouterr().out.splitlines()
            if _DECLINE_ROW.search(line)]


def test_the_decline_report_moves_nothing(capsys):
    """The report is FORENSICS: adding it must not change one altitude.
    (The §1 absorption and §2 loudness together are pre-registered as
    byte-inert; this is the unit-level half of that proof.)"""
    declined_a, declined_b = _seam_band_pair(300.0)
    before = (list(declined_a.node_altitudes),
              list(declined_b.node_altitudes))
    layout = _StubLayout([declined_a, declined_b])

    moved = blend_cross_strip_seam_steps(layout.shapes, layout)

    assert moved == 0
    assert (declined_a.node_altitudes, declined_b.node_altitudes) == (
        list(before[0]), list(before[1]))


def _guard_blocked_scene():
    """A cluster whose free nodes CANNOT move: two radius neighbours left
    outside the cluster disagree by more than twice the step floor, so the
    non-worsening bounds invert and both nodes stay put.  This is the
    measured mechanism behind CYXY's only ``seam::seam`` site."""
    return [
        _StubShape(_square(100.0, 100.0), [10.0] * 4),
        _StubShape(_square(123.0, 100.0), [13.0] * 4),
        _StubShape([(117.0, 100.0), (117.4, 100.0),
                    (117.4, 100.4), (117.0, 100.4)], [10.5] * 4),
        _StubShape([(125.0, 100.0), (125.4, 100.0),
                    (125.4, 100.4), (125.0, 100.4)], [12.45] * 4),
    ]


def _guard_clamped_scene():
    """A cluster whose free node moves, but only to a BOUND — the law
    target (11.50) is out of reach, 11.15 is applied, and a step survives.
    This is the measured mechanism behind HECA's (-102, 30) 4.26 m row."""
    return [
        _StubShape(_square(100.0, 100.0), [10.0] * 4),
        _StubShape(_square(123.0, 100.0), [13.0] * 4),
        _StubShape([(116.0, 100.0), (116.4, 100.0),
                    (116.4, 100.4), (116.0, 100.4)], [10.2] * 4),
    ]


def test_a_guard_blocked_node_is_reported_not_left_silent(capsys):
    layout = _StubLayout(_guard_blocked_scene())

    blend_cross_strip_seam_steps(layout.shapes, layout)

    out = capsys.readouterr().out
    rows = [line for line in out.splitlines()
            if _GUARD_DECLINED_ROW.search(line)]
    assert len(rows) == 2, out
    assert not [line for line in out.splitlines()
                if _DECLINE_ROW.search(line)], (
        "these nodes are FREE — the all-anchored decline must not claim "
        "them")
    for row in rows:
        assert "target=11.500" in row, row
        assert "applied=-" in row, row          # never moved
        assert "bounds=[11.500,11.450]" in row, row
    counted = _DECLINE_COUNT.search(out)
    assert counted and (int(counted.group(2)), int(counted.group(3)),
                        int(counted.group(4))) == (0, 2, 0), out


def test_a_guard_clamped_node_is_reported_with_its_residual(capsys):
    layout = _StubLayout(_guard_clamped_scene())

    blend_cross_strip_seam_steps(layout.shapes, layout)

    out = capsys.readouterr().out
    rows = [line for line in out.splitlines()
            if _GUARD_CLAMPED_ROW.search(line)]
    assert len(rows) == 1, out
    assert "target=11.500" in rows[0] and "applied=11.150" in rows[0]
    assert "residual=0.350m" in rows[0], rows[0]
    counted = _DECLINE_COUNT.search(out)
    assert counted and (int(counted.group(2)), int(counted.group(3)),
                        int(counted.group(4))) == (0, 0, 1), out


def test_both_guard_exits_record_before_they_leave_a_step(capsys):
    """STRUCTURAL: the guard has exactly two exits that leave a step
    standing, and each records one row.  A third silent exit added later
    fails this twin instead of quietly re-creating the v3 §2 defect."""
    fn = ast.parse(textwrap.dedent(
        inspect.getsource(blend_cross_strip_seam_steps))).body[0]
    kinds = [n.args[0].value for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_strip_seam_guard_record"
             and n.args and isinstance(n.args[0], ast.Constant)]
    assert sorted(kinds) == ["blocked", "clamped"], kinds

    # The inverted-bounds branch is the one that must never be silent.
    inverted = [node for node in ast.walk(fn)
                if isinstance(node, ast.If)
                and "lo > hi" in ast.unparse(node.test)]
    assert len(inverted) == 1, ast.unparse(fn)
    body = ast.unparse(inverted[0])
    assert "_strip_seam_guard_record" in body, body
    assert body.index("_strip_seam_guard_record") < body.index("continue")


def test_the_report_returns_one_row_per_left_alone_outcome(capsys):
    """The function's return value IS the band-5 count — rows emitted."""

    class _BareLayout:                      # no icao, no m_to_ll
        shapes: list = []

    layout = _BareLayout()
    declined = [{"x": 1.0, "y": 2.0, "step_m": 3.0, "nodes": 2,
                 "strips": 2, "shape_ids": [7, 8],
                 "anchors": {"weld": 2}, "lo": (1.0, 2.0, 10.0),
                 "hi": (1.5, 2.5, 13.0)}]
    guarded = [
        {"kind": "blocked", "x": 5.0, "y": 6.0, "z": 10.0,
         "target_m": 11.5, "applied_m": None, "residual_m": 1.5,
         "bound_lo": 11.5, "bound_hi": 11.45},
        {"kind": "clamped", "x": 7.0, "y": 8.0, "z": 10.0,
         "target_m": 11.5, "applied_m": 11.15, "residual_m": 0.35,
         "bound_lo": 9.25, "bound_hi": 11.15},
    ]

    emitted = report_strip_seam_declines(declined, layout, guarded)

    out = capsys.readouterr().out
    rows = [line for line in out.splitlines()
            if (_DECLINE_ROW.search(line)
                or _GUARD_DECLINED_ROW.search(line)
                or _GUARD_CLAMPED_ROW.search(line))]
    assert emitted == len(declined) + len(guarded) == len(rows) == 3, out
    # A layout without ``m_to_ll`` must still report (forensics never
    # depends on an optional helper).
    assert "ll=?" in rows[0], rows[0]


def test_the_record_names_the_anchored_sides_and_the_step_height():
    """Field-level twin for the three things the spec names: SITE, HEIGHT,
    ANCHORED SIDES."""
    declined_a, declined_b = _seam_band_pair(300.0, step=4.25)
    layout = _StubLayout([declined_a, declined_b])
    captured: list = []
    real = adjacent_ground.report_strip_seam_declines
    adjacent_ground.report_strip_seam_declines = (
        lambda declined, lay, guarded=(): (
            captured.extend(declined), real(declined, lay, guarded))[1])
    try:
        blend_cross_strip_seam_steps(layout.shapes, layout)
    finally:
        adjacent_ground.report_strip_seam_declines = real

    assert captured, "no decline record produced"
    row = captured[0]
    assert row["step_m"] == 4.25                       # HEIGHT
    assert row["anchors"] == {"tile_seam": 2}          # ANCHORED SIDES
    assert row["nodes"] == 2 and row["strips"] == 2
    assert row["shape_ids"] == [0, 1]
    assert abs(row["hi"][2] - row["lo"][2] - 4.25) < 1e-9
    assert row["y"] in (300.0, 320.0)                  # SITE
