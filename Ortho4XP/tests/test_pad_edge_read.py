"""Twin of ``tools/pad_edge_read.py``: one flat pad, four edges, four classes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pad_edge_read as per  # noqa: E402

LAT0, LON0 = 10.0, 20.0


def _ll(x: float, y: float) -> tuple[float, float]:
    import math
    return (LAT0 + y / 110574.0, LON0 + x / (111320.0 * math.cos(math.radians(LAT0))))


def _graded(apron_far_z: float, lot_z: float) -> dict:
    """A 100 m pad at z 50.  WEST: an apron welded to it, its far edge at
    ``apron_far_z`` 8 m out.  SOUTH: a lot 1.5 m off the rim at ``lot_z``,
    unwelded.  EAST and NORTH: nothing."""
    pts = {0: (0, 0, 50), 1: (100, 0, 50), 2: (100, 100, 50), 3: (0, 100, 50),
           4: (-8, 0, apron_far_z), 5: (-8, 100, apron_far_z),
           6: (30, -1.5, lot_z), 7: (70, -1.5, lot_z), 8: (70, -9, lot_z), 9: (30, -9, lot_z),
           10: (50, 0, 50)}
    verts = [[i, *_ll(x, y), z] for i, (x, y, z) in pts.items()]
    faces = [{"id": 0, "role": "building", "ref": "building1", "ring": [0, 10, 1, 2, 3], "holes": []},
             {"id": 1, "role": "apron", "ref": "pav1", "ring": [4, 0, 3, 5], "holes": []},
             {"id": 2, "role": "parking_lot", "ref": "lot1", "ring": [6, 7, 8, 9], "holes": []}]
    return {"icao": "TEST", "frame": {"origin": [LAT0, LON0]}, "vertices": verts, "faces": faces}


def _dem_east_high(lat: float, lon: float) -> float:
    """Ground at pad level everywhere but east of the pad, where it stands 4 m up."""
    return 54.0 if lon > _ll(101, 0)[1] else 50.0


def test_flat_pad_on_flat_ground_has_no_run() -> None:
    assert per.read_edges(_graded(50.0, 50.0), lambda la, lo: 50.0) == []


def test_bare_edge_is_listed_as_bare() -> None:
    runs = per.read_edges(_graded(50.0, 50.0), _dem_east_high)
    assert {r["cls"] for r in runs} == {"B"}
    (r,) = runs
    assert r["pad"] == "building1" and r["vertices"] == 2 and abs(r["length_m"] - 100.0) < 0.5
    assert abs(r["height_m"] - 4.0) < 1e-6 and r["ground_off_m"] > 0


def test_welded_pavement_climbing_away_is_pavement_off() -> None:
    runs = per.read_edges(_graded(52.0, 50.0), lambda la, lo: 50.0)
    (r,) = [r for r in runs if r["cls"] == "P"]
    cell = r["cells"][0]
    assert cell["cell"] == "apron:pav1" and cell["touching"] and abs(cell["off_m"] - 2.0) < 1e-6
    assert abs(cell["grade_pct"] - 25.0) < 0.2          # 2 m over 8 m
    assert r["vertices"] == 2


def test_unwelded_pavement_across_a_sliver_is_pavement_off() -> None:
    runs = per.read_edges(_graded(50.0, 43.0), lambda la, lo: 50.0)
    p = [r for r in runs if r["cls"] == "P"]
    assert len(p) == 1 and p[0]["vertices"] == 1        # the rim vertex facing the lot
    cell = p[0]["cells"][0]
    assert cell["cell"] == "parking_lot:lot1" and not cell["touching"]
    assert abs(cell["dist_m"] - 1.5) < 0.01 and abs(cell["off_m"] + 7.0) < 1e-6
    assert abs(cell["step_m"] + 7.0) < 1e-6


def test_welded_flat_pavement_beside_a_bank_is_mixed_not_seat() -> None:
    def dem(lat: float, lon: float) -> float:            # a bank north of the pad
        return 53.0 if lat > _ll(0, 101)[0] else 50.0
    runs = per.read_edges(_graded(50.0, 50.0), dem)
    assert sorted(r["cls"] for r in runs) == ["B", "M"]  # corner 3 touches the apron; corner 2 is bare
    assert not any(r["cls"] == "P" for r in runs)


def test_without_a_dem_only_patch_cells_are_read() -> None:
    runs = per.read_edges(_graded(52.0, 50.0), None)
    assert [r["cls"] for r in runs] == ["P"] and runs[0]["ground_off_m"] is None
