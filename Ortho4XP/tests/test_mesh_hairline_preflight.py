"""§39 (3) THE MESH PRE-FLIGHT and ``mesh_region_tris.py --hairline-audit``
(owner RULINGS 2026-09-13an / 13bk; spec design-surface-spec §39).

The twin is built from the two measured sightings, at their own numbers:

* LEMD (13bk): a ``PATCH_RING_MARKER`` (15) bank-foot segment 0.0595 mm
  from and 0.000 deg to a 74.63 m OSM WATER (1) edge — slenderness 417,901.
  2,301,676 triangles under 0.1 m^2 and a tile X-Plane would not load.
* SPLP (13an): a bank segment 0.0237 m from the TILE BORDER, where ``-Y``
  forbids Steiner points — Triangle split the bank 16,298 times instead.

and from what must NOT be refused: the 0.12-0.50 m gaps between ordinary
neighbouring rings (LEMD's own patch carries 367), and the ~0.44 m land
segments every tile carries beside its border.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import O4_Mesh_Utils as MESH                                  # noqa: E402
import mesh_region_tris as MRT                                # noqa: E402

TILE_LAT, TILE_LON = 40, -4
M_LAT = 111_120.0                       # GEO.lat_to_m, the tool's own


def _dlat(metres):
    return metres / M_LAT


def _dlon(metres):
    return metres / (M_LAT * math.cos(math.radians(TILE_LAT + 0.5)))


def _write(tmp_path, name, nodes, segments):
    """A Triangle ``.node``/``.poly`` pair in TILE-RELATIVE degrees."""
    prefix = tmp_path / name
    with open(str(prefix) + ".node", "w") as fh:
        fh.write(f"{len(nodes)} 2 1 0\n")
        for i, (x, y) in enumerate(nodes, start=1):
            fh.write(f"{i} {x!r} {y!r} 0\n")
    with open(str(prefix) + ".poly", "w") as fh:
        fh.write(f"0 2 1 0\n{len(segments)} 1\n")
        for i, (a, b, mk) in enumerate(segments, start=1):
            fh.write(f"{i} {a} {b} {mk}\n")
        fh.write("0\n0\n")
    return str(prefix)


def _lemd_pair(tmp_path, name, gap_m):
    """The LEMD geometry: a 74.6 m water edge and, ``gap_m`` beside it and
    exactly parallel, a 24.9 m patch ring segment."""
    x0, y0 = 0.4543258, 0.4764778
    run_x, run_y = 60.0, -44.5                  # the water edge's own run, m
    length = math.hypot(run_x, run_y)
    dx, dy = _dlon(run_x), _dlat(run_y)
    # the PERPENDICULAR unit vector, in metres, then back into degrees
    ox = _dlon(gap_m * (-run_y / length))
    oy = _dlat(gap_m * (run_x / length))
    nodes = [(x0, y0), (x0 + dx, y0 + dy),
             (x0 + ox + dx / 3.0, y0 + oy + dy / 3.0),
             (x0 + ox + 2.0 * dx / 3.0, y0 + oy + 2.0 * dy / 3.0)]
    return _write(tmp_path, name, nodes, [(1, 2, 1), (3, 4, 15)])


class _Tile:
    lat, lon = TILE_LAT, TILE_LON


def test_the_lemd_hairline_is_unmeshable(tmp_path):
    prefix = _lemd_pair(tmp_path, "lemd", 0.0000595)
    rows = MESH.hairline_pairs(prefix + ".poly", TILE_LAT)
    assert len(rows) == 1
    row = rows[0]
    assert row["gap_m"] == pytest.approx(0.0000595, rel=0.05)
    assert row["angle_deg"] < 1.0e-6
    assert row["slenderness"] > 1.0e5
    assert MESH.hairline_refusals(rows) == rows


def test_an_ordinary_neighbouring_ring_is_reported_not_refused(tmp_path):
    """LEMD's own patch carries 367 pairs 0.12-0.50 m apart between
    neighbouring rings.  They are the layout, not a hairline."""
    prefix = _lemd_pair(tmp_path, "ordinary", 0.30)
    rows = MESH.hairline_pairs(prefix + ".poly", TILE_LAT)
    assert len(rows) == 1 and rows[0]["gap_m"] == pytest.approx(0.30, rel=0.05)
    assert MESH.hairline_refusals(rows) == []


def test_a_pair_beyond_the_spacing_is_not_a_pair_at_all(tmp_path):
    prefix = _lemd_pair(tmp_path, "clear", 1.20)
    assert MESH.hairline_pairs(prefix + ".poly", TILE_LAT) == []


def test_the_splp_border_pair_is_unmeshable_however_short(tmp_path):
    """13an: ``-Y`` forbids Steiner points on the OUTER boundary, so the
    wedge can only be relieved by splitting the OTHER segment — 16,298
    times for a 5.32 m bank chain 0.0237 m from the meridian.  Its
    slenderness is only 224: the boundary clause is what catches it."""
    dx = _dlon(0.0237)
    nodes = [(0.0, 0.20), (0.0, 0.20 + _dlat(5.32)),
             (dx, 0.20), (dx, 0.20 + _dlat(5.32))]
    prefix = _write(tmp_path, "splp", nodes, [(1, 2, 0), (3, 4, 15)])
    rows = MESH.hairline_pairs(prefix + ".poly", TILE_LAT)
    assert len(rows) == 1 and rows[0]["on_boundary"]
    assert rows[0]["slenderness"] < 1.0e4        # the slenderness bar misses it
    assert MESH.hairline_refusals(rows) == rows  # the boundary clause does not


def test_a_land_segment_half_a_metre_off_the_border_is_not_refused(tmp_path):
    """Every tile carries them (LEMD: four at 0.444 m).  The boundary
    clause is a HAIRLINE clause, not a keep-off-the-border clause."""
    dx = _dlon(0.444)
    nodes = [(0.0, 0.20), (0.0, 0.20 + _dlat(54.36)),
             (dx, 0.20), (dx, 0.20 + _dlat(53.91))]
    prefix = _write(tmp_path, "land", nodes, [(1, 2, 0), (3, 4, 0)])
    rows = MESH.hairline_pairs(prefix + ".poly", TILE_LAT)
    assert len(rows) == 1 and rows[0]["on_boundary"]
    assert MESH.hairline_refusals(rows) == []


def test_a_chain_is_not_a_pair(tmp_path):
    """Two segments sharing a vertex are one chain — the 11-dp identity
    join is exactly what "shares that edge's vertices" means."""
    nodes = [(0.4543258, 0.4764778),
             (0.4543258 + _dlon(30.0), 0.4764778),
             (0.4543258 + _dlon(60.0), 0.4764778 + _dlat(0.0001))]
    prefix = _write(tmp_path, "chain", nodes, [(1, 2, 15), (2, 3, 15)])
    assert MESH.hairline_pairs(prefix + ".poly", TILE_LAT) == []


def test_the_preflight_refuses_and_names_the_pair(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("O4_HAIRLINE_PREFLIGHT", raising=False)
    prefix = _lemd_pair(tmp_path, "refuse", 0.0000595)
    assert MESH.hairline_preflight(prefix + ".poly", _Tile()) == 0
    out = capsys.readouterr().out
    assert "HAIRLINE" in out and "UNMESHABLE" in out


def test_the_preflight_passes_a_clean_poly(tmp_path, monkeypatch):
    monkeypatch.delenv("O4_HAIRLINE_PREFLIGHT", raising=False)
    prefix = _lemd_pair(tmp_path, "clean", 1.20)
    assert MESH.hairline_preflight(prefix + ".poly", _Tile()) == 1


def test_the_report_knob_builds_anyway(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_HAIRLINE_PREFLIGHT", "report")
    prefix = _lemd_pair(tmp_path, "report", 0.0000595)
    assert MESH.hairline_preflight(prefix + ".poly", _Tile()) == 1


def test_the_off_knob_skips_the_audit(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_HAIRLINE_PREFLIGHT", "off")
    prefix = _lemd_pair(tmp_path, "off", 0.0000595)
    assert MESH.hairline_preflight(prefix + ".poly", _Tile()) == 1


def test_the_tool_runs_the_engines_own_reader(tmp_path, capsys):
    """``--hairline-audit`` is the INSTRUMENT half of the pre-flight, not a
    second spelling of it: the tool calls ``O4_Mesh_Utils`` directly, so
    the instrument and the refusal can never disagree."""
    prefix = _lemd_pair(tmp_path, "tool", 0.0000595)
    rc = MRT.main(["--hairline-audit", "--inputs", prefix,
                   "--tile", str(TILE_LAT), str(TILE_LON)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "pairs within 0.5 m and 5.0 deg of parallel: 1" in out
    assert "UNMESHABLE" in out and "mk 1/15" in out


def test_the_tool_refuses_without_a_prefix(capsys):
    with pytest.raises(SystemExit):
        MRT.main(["--hairline-audit"])
