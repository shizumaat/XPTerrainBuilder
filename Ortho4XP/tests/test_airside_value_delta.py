"""Twin for ``tools/airside_value_delta.py`` — the whole-patch AIRSIDE
VALUE read an airside-frozen lane is adjudicated on.

What must hold, and why each one is here rather than left to a reviewer:

* the CLI's JSON **is** the library entry's result (the two-instruments
  trap: a printed number and a dumped number that can drift are two
  instruments describing one population);
* every role set is IMPORTED from the law's own modules, never re-spelled
  (the census-wrapper precedent, RULINGS ``7e90032``);
* the join is the CANONICAL 11-decimal lat/lon spelling — a node present
  in one arm only is ADDED/REMOVED, never MOVED, or every densification
  reads as a phantom pull;
* the two frames really are two populations, and the solve-owned one is
  the subset — quoting one number for both is the failure this tool's
  docstring names;
* the road-weld split classifies by the ROAD FAMILY the census itself
  publishes;
* a node with no emitted altitude is reported, never counted as 0.0;
* the index entry exists (a tool absent from ``tools/INDEX.md`` is treated
  as absent).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location(
        "avd_twin", ROOT / "tools" / "airside_value_delta.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["avd_twin"] = mod
    spec.loader.exec_module(mod)
    return mod


avd = _load()


# ── a two-node-per-way synthetic patch in the emitter's own dialect ───
def _patch(path: Path, ways) -> Path:
    """``ways`` = [(role, [(lat, lon, alt|None), ...]), ...]."""
    nodes, body, nid = [], [], -1
    seen: dict = {}
    for role, pts in ways:
        refs = []
        for (la, lo, alt) in pts:
            key = (f"{la:.11f}", f"{lo:.11f}")
            if key not in seen:
                seen[key] = nid
                if alt is None:
                    nodes.append(
                        f"<node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'/>")
                else:
                    nodes.append(
                        f"<node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'>"
                        f"<tag k='alt_abs' v='{alt}'/></node>")
                nid -= 1
            refs.append(seen[key])
        nds = "".join(f"<nd ref='{r}'/>" for r in refs + [refs[0]])
        body.append(f"<way id='{nid}'>{nds}"
                    f"<tag k='role' v='{role}'/></way>")
        nid -= 1
    path.write_text("<?xml version='1.0'?><osm version='0.6'>"
                    + "".join(nodes) + "".join(body) + "</osm>")
    return path


#: One apron (airside pavement, stage A) and one service_road
#: (groundside), sharing NOTHING; plus a graded_strip, which is airside in
#: the ROW-SIDE frame and absent from the SOLVE-OWNED one.
def _arms(tmp_path, apron_alt_b, strip_alt_b):
    a = _patch(tmp_path / "a.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
        ("graded_strip", [(2.0, 2.0, 20.0), (2.0, 2.001, 20.0),
                          (2.001, 2.0, 20.0)]),
        ("service_road", [(3.0, 3.0, 30.0), (3.0, 3.001, 30.0),
                          (3.001, 3.0, 30.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [(1.0, 1.0, apron_alt_b), (1.0, 1.001, 10.0),
                   (1.001, 1.0, 10.0)]),
        ("graded_strip", [(2.0, 2.0, strip_alt_b), (2.0, 2.001, 20.0),
                          (2.001, 2.0, 20.0)]),
        ("service_road", [(3.0, 3.0, 31.0), (3.0, 3.001, 30.0),
                          (3.001, 3.0, 30.0)]),
    ])
    return a, b


def test_the_role_sets_are_imported_not_respelled():
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES)
    from auto_patch.solve_stage import stage_of_role, STAGE_A
    from auto_patch.layout import GROUNDSIDE_ROLES
    gs, solve_air, road = avd.role_sets()
    assert gs == frozenset(GROUNDSIDE_ROLES)
    assert solve_air == frozenset(r for r in PAVEMENT_ROLES
                                  if stage_of_role(r) == STAGE_A)
    assert road == frozenset({"service_road", "service_junction"})
    # the two frames are two populations, and one contains the other
    assert not (solve_air & gs)
    assert "graded_strip" not in solve_air and "graded_strip" not in gs


def test_a_moved_airside_value_is_reported_in_both_frames(tmp_path):
    a, b = _arms(tmp_path, apron_alt_b=10.5, strip_alt_b=20.0)
    res = avd.compare(a, b)
    assert res["frames"]["solve-owned"]["n_moved"] == 1
    assert res["frames"]["solve-owned"]["worst_dz_m"] == pytest.approx(0.5)
    assert res["frames"]["row-side"]["n_moved"] == 1


def test_a_moved_soft_receiver_is_ROW_SIDE_ONLY(tmp_path):
    """``graded_strip`` is airside to the census's row_side and is NOT a
    solve variable — the whole reason two frames are printed."""
    a, b = _arms(tmp_path, apron_alt_b=10.0, strip_alt_b=21.0)
    res = avd.compare(a, b)
    assert res["frames"]["row-side"]["n_moved"] == 1
    assert res["frames"]["solve-owned"]["n_moved"] == 0
    assert res["frames"]["solve-owned"]["worst_dz_m"] == 0.0


def test_a_groundside_move_is_in_neither_frame(tmp_path):
    a, b = _arms(tmp_path, apron_alt_b=10.0, strip_alt_b=20.0)
    res = avd.compare(a, b)          # only the service_road moved
    assert res["frames"]["row-side"]["n_moved"] == 0
    assert res["frames"]["solve-owned"]["n_moved"] == 0


def test_sub_materiality_is_not_a_move(tmp_path):
    a, b = _arms(tmp_path, apron_alt_b=10.005, strip_alt_b=20.0)
    assert avd.compare(a, b)["frames"]["solve-owned"]["n_moved"] == 0
    assert avd.compare(a, b, tol_m=0.001)[
        "frames"]["solve-owned"]["n_moved"] == 1


def test_an_added_vertex_is_never_a_moved_value(tmp_path):
    """The canonical join: a node only one arm carries is ADDED/REMOVED.
    Folding it in would make every densification read as a pull."""
    a = _patch(tmp_path / "a.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.002, 10.0), (1.002, 1.0, 10.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.001, 10.0), (1.0, 1.002, 10.0),
                   (1.002, 1.0, 10.0)]),
    ])
    f = avd.compare(a, b)["frames"]["solve-owned"]
    assert f["b_only"] == 1 and f["a_only"] == 0
    assert f["n_moved"] == 0 and f["worst_dz_m"] == 0.0


def test_the_road_weld_split_is_the_road_family(tmp_path):
    """A node an apron ring AND a road ring both claim is the channel a
    groundside pull travels; one with no road contact is adoption."""
    shared = (1.0, 1.0)
    a = _patch(tmp_path / "a.osm", [
        ("apron", [shared + (10.0,), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
        ("service_junction", [shared + (10.0,), (0.999, 1.0, 10.0),
                              (0.999, 1.001, 10.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [shared + (10.4,), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
        ("service_junction", [shared + (10.4,), (0.999, 1.0, 10.0),
                              (0.999, 1.001, 10.0)]),
    ])
    f = avd.compare(a, b)["frames"]["solve-owned"]
    assert f["n_moved"] == 1
    assert f["welded_to_road"] == 1 and f["no_road_contact"] == 0
    assert f["moved"][0]["welded_to_road"] is True


def test_a_node_with_no_altitude_is_reported_never_zero(tmp_path):
    a = _patch(tmp_path / "a.osm", [
        ("apron", [(1.0, 1.0, None), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
    ])
    b = _patch(tmp_path / "b.osm", [
        ("apron", [(1.0, 1.0, 10.0), (1.0, 1.001, 10.0), (1.001, 1.0, 10.0)]),
    ])
    f = avd.compare(a, b)["frames"]["solve-owned"]
    assert f["n_no_value"] == 1
    assert f["n_moved"] == 0 and f["worst_dz_m"] == 0.0


def test_the_cli_json_IS_the_library_result(tmp_path, capsys):
    a, b = _arms(tmp_path, apron_alt_b=10.5, strip_alt_b=21.0)
    out = tmp_path / "res.json"
    assert avd.main([str(a), str(b), "--json", str(out)]) == 0
    capsys.readouterr()
    assert json.loads(out.read_text()) == json.loads(
        json.dumps(avd.compare(a, b)))


def test_a_missing_input_is_REFUSED_not_guessed(tmp_path, capsys):
    a, _b = _arms(tmp_path, apron_alt_b=10.0, strip_alt_b=20.0)
    assert avd.main([str(a), str(tmp_path / "nope.osm")]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_the_tool_is_in_the_index():
    idx = (ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/airside_value_delta.py" in idx, (
        "a tool absent from tools/INDEX.md is treated as absent")
