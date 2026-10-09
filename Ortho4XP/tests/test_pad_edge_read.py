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
    assert per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=_graded(50.0, 50.0), dem=lambda la, lo: 50.0) == []


def test_bare_edge_is_listed_as_bare() -> None:
    runs = per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=_graded(50.0, 50.0), dem=_dem_east_high)
    assert {r["cls"] for r in runs} == {"B"}
    (r,) = runs
    assert r["pad"] == "building1" and r["vertices"] == 2 and abs(r["length_m"] - 100.0) < 0.5
    assert abs(r["height_m"] - 4.0) < 1e-6 and r["ground_off_m"] > 0


def test_welded_pavement_climbing_away_is_pavement_off() -> None:
    runs = per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=_graded(52.0, 50.0), dem=lambda la, lo: 50.0)
    (r,) = [r for r in runs if r["cls"] == "P"]
    cell = r["cells"][0]
    assert cell["cell"] == "apron:pav1" and cell["touching"] and abs(cell["off_m"] - 2.0) < 1e-6
    assert abs(cell["grade_pct"] - 25.0) < 0.2          # 2 m over 8 m
    assert r["vertices"] == 2


def test_unwelded_pavement_across_a_sliver_is_pavement_off() -> None:
    runs = per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=_graded(50.0, 43.0), dem=lambda la, lo: 50.0)
    p = [r for r in runs if r["cls"] == "P"]
    assert len(p) == 1 and p[0]["vertices"] == 1        # the rim vertex facing the lot
    cell = p[0]["cells"][0]
    assert cell["cell"] == "parking_lot:lot1" and not cell["touching"]
    assert abs(cell["dist_m"] - 1.5) < 0.01 and abs(cell["off_m"] + 7.0) < 1e-6
    assert abs(cell["step_m"] + 7.0) < 1e-6


def test_welded_flat_pavement_beside_a_bank_is_mixed_not_seat() -> None:
    def dem(lat: float, lon: float) -> float:            # a bank north of the pad
        return 53.0 if lat > _ll(0, 101)[0] else 50.0
    runs = per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=_graded(50.0, 50.0), dem=dem)
    assert sorted(r["cls"] for r in runs) == ["B", "M"]  # corner 3 touches the apron; corner 2 is bare
    assert not any(r["cls"] == "P" for r in runs)


def test_without_a_dem_only_patch_cells_are_read() -> None:
    runs = per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=_graded(52.0, 50.0), dem=None)
    assert [r["cls"] for r in runs] == ["P"] and runs[0]["ground_off_m"] is None


def test_a_declared_structure_beside_the_pad_is_the_structures_wall() -> None:
    g = _graded(50.0, 43.0)
    g["faces"][2]["role"] = "tunnel_ramp"                # the lot becomes a trench ramp 1.5 m off the rim
    runs = per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=g, dem=lambda la, lo: 50.0)
    assert [r["cls"] for r in runs] == ["W"]


def test_the_default_structure_roles_are_the_laws_own() -> None:
    assert "tunnel_ramp" in per.structure_roles() and "apron" not in per.structure_roles()


# ── --source: the touch witness (spec §63 (3), owner RULINGS 2026-10-09j) ──

def _p_runs(lot_z: float, apron_far_z: float = 50.0) -> tuple[list, dict]:
    g = _graded(apron_far_z, lot_z)
    for f in g["faces"]:
        f["side"] = "groundside" if f["role"] == "parking_lot" else "airside"
    runs = per.read_edges(structures=frozenset({'tunnel_ramp'}), graded=g, dem=lambda la, lo: 50.0)
    return runs, g


def _source_cls(runs: list) -> list:
    return [(r["source"]["cls"], r["source"]["cell"], r["source"]["gap_m"]) for r in runs if r.get("source")]


def test_a_cell_touching_the_pad_in_the_source_and_standing_off_it_is_the_defect() -> None:
    runs, g = _p_runs(43.0)
    per.class_by_source(runs, g, [{"pad": "building1", "touching": ["parking_lot:lot1#1"], "gapped": []}])
    assert _source_cls(runs) == [("TOUCH-OFF", "parking_lot:lot1", 0.0)]
    assert any("P:TOUCH-OFF: 1 run(s)" in ln for ln in per.render_source(runs))


def test_a_cell_drawn_with_a_gap_is_accepted_and_listed_with_its_gap() -> None:
    runs, g = _p_runs(43.0)
    per.class_by_source(runs, g, [{"pad": "building1", "touching": [],
                                   "gapped": [{"cell": "parking_lot:lot1", "gap_m": 1.5}]}])
    assert _source_cls(runs) == [("GAPPED", "parking_lot:lot1", 1.5)]
    assert any("gap 1.50 m" in ln for ln in per.render_source(runs))


def test_an_airside_cell_and_a_cell_with_no_record_are_never_guessed() -> None:
    runs, g = _p_runs(50.0, apron_far_z=52.0)
    per.class_by_source(runs, g, [])
    assert _source_cls(runs) == [("AIRSIDE", "apron:pav1", None)]
    runs, g = _p_runs(43.0)
    per.class_by_source(runs, g, [])
    assert _source_cls(runs) == [("UNWITNESSED", "parking_lot:lot1", None)]


def test_the_witness_is_read_off_the_sidecar(tmp_path) -> None:
    import json
    side = tmp_path / "X.axes.json"
    side.write_text(json.dumps({"pad_touch": [{"pad": "building1", "touching": ["parking_lot:lot1"], "gapped": []}]}))
    assert per.source_witness(side)[0]["touching"] == ["parking_lot:lot1"]
    (tmp_path / "Y.axes.json").write_text("{}")
    assert per.source_witness(tmp_path / "Y.axes.json") == []
