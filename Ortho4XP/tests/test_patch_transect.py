"""Twin for ``tools/patch_transect.py`` — the patch transect reader
(promoted 2026-09-10 from the v2taxidatum lane's second use of the 10o
transect script, RULINGS `7e90032` promote-on-reuse)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
_spec = importlib.util.spec_from_file_location(
    "patch_transect", ROOT / "tools" / "patch_transect.py")
pt = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(pt)


def _patch(tmp_path: Path) -> Path:
    """Two overlapping rings over the same ground: a graded strip from
    lon -1.0e-3 to 3.0e-3 at 100 m, and a runway square inside it at 110 m.
    (Lat 0, so a degree of lon is a degree of lat in metres.)"""
    out = ["<?xml version='1.0'?>", "<osm version='0.6'>"]
    nodes = {
        # the strip
        "-1": (-0.0005, -0.001, 100.0), "-2": (0.0005, -0.001, 100.0),
        "-3": (0.0005, 0.003, 100.0), "-4": (-0.0005, 0.003, 100.0),
        # the runway, inside it
        "-5": (-0.0002, 0.0005, 110.0), "-6": (0.0002, 0.0005, 110.0),
        "-7": (0.0002, 0.0015, 112.0), "-8": (-0.0002, 0.0015, 112.0),
    }
    for nid, (lat, lon, alt) in nodes.items():
        out.append(f"<node id='{nid}' lat='{lat:.7f}' lon='{lon:.7f}'>"
                   f"<tag k='alt_abs' v='{alt}'/></node>")

    def way(wid, ids, role, ref):
        out.append(f"<way id='{wid}'>")
        out.extend(f"<nd ref='{i}'/>" for i in [*ids, ids[0]])
        out.append(f"<tag k='role' v='{role}'/><tag k='ref' v='{ref}'/></way>")

    way("-100", ["-1", "-2", "-3", "-4"], "graded_strip", "strip1")
    way("-101", ["-5", "-6", "-7", "-8"], "runway", "09/27")
    out.append("</osm>")
    p = tmp_path / "P.osm"
    p.write_text("\n".join(out))
    return p


def test_the_covering_role_wins_by_the_declared_order(tmp_path):
    """A station inside both the runway and the strip reads the RUNWAY —
    what an aircraft is standing on, the module's declared precedence."""
    rows = pt.transect(_patch(tmp_path), 0.0, -0.001, 0.003, 20.0)
    inside = [r for r in rows if 0.0005 < r["lon"] < 0.0015]
    assert inside, "the fixture must put stations inside the runway"
    assert all(r["role"] == "runway" for r in inside)
    assert all("graded_strip:strip1" in r["covered_by"] for r in inside)
    # and outside the runway the strip is what covers the station
    outer = [r for r in rows if r["lon"] < 0.0]
    assert outer and all(r["role"] == "graded_strip" for r in outer)


def test_a_station_outside_every_shape_is_named_not_guessed(tmp_path):
    rows = pt.transect(_patch(tmp_path), 0.0, -0.003, -0.002, 20.0)
    assert rows and all(r["covered_by"] == "OUTSIDE PATCH" for r in rows)
    assert all(r["z_m"] is None and r["role"] is None for r in rows)


def test_the_value_is_the_shapes_own_emitted_nodes(tmp_path):
    """At a station the shape's own emitted altitudes give the value: on
    top of a node it IS that node's ``alt_abs``, and between the runway's
    two ends it lies between them — no outside authority, no law."""
    rows = pt.transect(_patch(tmp_path), 0.00019, 0.00051, 0.00149, 5.0)
    assert all(r["role"] == "runway" for r in rows)
    assert abs(rows[0]["z_m"] - 110.0) < 0.2
    assert abs(rows[-1]["z_m"] - 112.0) < 0.2
    mid = rows[len(rows) // 2]["z_m"]
    assert 110.0 < mid < 112.0


def test_the_distance_column_is_metres_along_the_transect(tmp_path):
    rows = pt.transect(_patch(tmp_path), 0.0, -0.001, 0.001, 25.0)
    assert rows[0]["dist_m"] == 0.0
    step = rows[1]["dist_m"] - rows[0]["dist_m"]
    assert abs(step - 25.0) < 0.5


@pytest.mark.parametrize("argv,why", [
    (["--lat", "0", "--lon-from", "0.003", "--lon-to", "-0.001"],
     "an eastward transect only"),
    (["--lat", "0", "--lon-from", "-0.001", "--lon-to", "0.003",
      "--alt", "nowhere.alt"], "--alt without --tile"),
])
def test_the_refusals(tmp_path, argv, why, capsys):
    rc = pt.main([str(_patch(tmp_path)), *argv])
    assert rc == 2, why
    assert "REFUSING" in capsys.readouterr().err


def test_a_missing_patch_refuses(tmp_path, capsys):
    rc = pt.main([str(tmp_path / "nope.osm"), "--lat", "0",
                  "--lon-from", "-0.001", "--lon-to", "0.001"])
    assert rc == 2
    assert "REFUSING" in capsys.readouterr().err


def test_two_arms_are_read_alike_and_the_index_row_exists(tmp_path, capsys):
    """The arm-to-arm read prints both and their delta; and the tool is IN
    the consultation surface (RULINGS `7e90032`: a tool absent from the
    index is treated as absent)."""
    p = _patch(tmp_path)
    rc = pt.main([str(p), str(p), "--lat", "0.0002",
                  "--lon-from", "0.0005", "--lon-to", "0.0015", "--step", "20"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ctrl" in out.splitlines()[0]
    index = ROOT.parent / "tools" / "INDEX.md"
    assert index.exists()
    assert "patch_transect.py" in index.read_text()
