"""Twin of ``tools/drawn_site.py`` (#1903): the drawn-mesh reader, the
loose-triangle sampler and the per-component readings, on synthetic
geometry -- no DSFTool, no installed scenery."""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, _TOOLS)

import drawn_site as DC  # noqa: E402
from auto_patch.mesh_sampler import MeshElevationSampler  # noqa: E402
from auto_patch_v2.airport.dsf_mesh import (  # noqa: E402
    expand_primitive,
    physical_triangles,
)
from auto_patch_v2.airport.obj8 import Component  # noqa: E402

LAT, LON = 40.0, 10.0


def _text(flags: int, ptype: int, verts) -> list[str]:
    lines = [f"BEGIN_PATCH 0 0.0 -1.0 {flags} 5", f"BEGIN_PRIMITIVE {ptype}"]
    lines += [f"PATCH_VERTEX {x} {y} {z} 0 0" for x, y, z in verts]
    return lines + ["END_PRIMITIVE", "END_PATCH"]


def test_physical_triangles_keeps_physical_patches_in_the_box():
    sq = [(10.0, 40.0, 5.0), (10.001, 40.0, 6.0), (10.0, 40.001, 7.0), (10.001, 40.001, 8.0)]
    text = (_text(1, 1, sq)                                       # strip: 2 triangles
            + _text(0, 0, sq[:3])                                 # overlay patch: not drawn ground
            + _text(1, 2, sq)                                     # fan: 2 triangles
            + _text(1, 0, [(11.0, 41.0, 1.0), (11.001, 41.0, 1.0),
                           (11.0, 41.001, 1.0)]))           # off the box
    got = physical_triangles(text, (9.99, 39.99, 10.01, 40.01))
    assert got.shape == (4, 3, 3)
    assert set(np.unique(got[:, :, 2])) == {5.0, 6.0, 7.0, 8.0}
    assert len(expand_primitive(0, sq[:3] + sq[:3])) == 2


def test_sampler_over_loose_triangles_interpolates_and_misses_outside():
    corners = np.array([[[0, 0, 0], [1, 0, 10], [0, 1, 20]],
                        [[1, 0, 10], [1, 1, 30], [0, 1, 20]]], float)
    smp = MeshElevationSampler.from_triangles(corners, (0, 0, 1, 1))
    assert smp.sample_at(0.25, 0.25).elevation_metres == pytest.approx(7.5)
    assert smp.sample_many([0.75, 2.0], [0.75, 2.0])[1] is None


class _Mesh:
    """A drawn surface given as ``f(east, north)`` in the site frame."""

    def __init__(self, frame: DC.Frame, f):
        self.frame, self.f = frame, f

    def z(self, lat, lon):
        lat, lon = np.asarray(lat, float).reshape(-1), np.asarray(lon, float).reshape(-1)
        e, n = self.frame.enter(lat, lon)
        return np.array([self.f(a, b) for a, b in zip(e, n, strict=True)], float)


def _trench(base: float):
    """An open-top trench 40 m east-west, 10 m wide: a floor 4 m down,
    walls on its north and south sides, both ends open."""
    V = np.array([[-20, -5, base - 4], [20, -5, base - 4], [20, 5, base - 4], [-20, 5, base - 4],
                  [-20, -5, base], [20, -5, base], [20, 5, base], [-20, 5, base]], float)
    tris = np.array([[0, 1, 2], [0, 2, 3],                   # floor
                     [0, 1, 5], [0, 5, 4], [3, 2, 6], [3, 6, 7]])  # south and north walls
    return V, Component(tris, -4.0, 0.0, 0.0, 0.0, False, np.arange(len(tris)))


def _no_others(e, n):
    return np.full(len(e), np.nan)


def test_trench_on_uncut_ground_reads_buried_with_terrain_over_its_ends():
    fr = DC.Frame(LAT, LON)
    V, comp = _trench(100.0)
    rec = DC.measure(V, comp, fr, _Mesh(fr, lambda e, n: 100.0), _no_others)
    assert rec["bottom_minus_mesh"]["p50"] == pytest.approx(-4.0, abs=0.01)
    assert rec["shape"]["class"] == "concave cut shell"
    ends = [q for q in rec["open_runs"] if q["length_m"] >= 8.0]
    assert len(ends) == 2 and all(q["step_m"] == pytest.approx(-4.0, abs=0.01) for q in ends)


def test_trench_in_its_cut_reads_on_the_mesh_and_flush_at_its_ends():
    fr = DC.Frame(LAT, LON)
    V, comp = _trench(100.0)
    cut = lambda e, n: 96.0 if abs(n) <= 5.5 else 100.0                # noqa: E731 (cut + ramps)
    rec = DC.measure(V, comp, fr, _Mesh(fr, cut), _no_others)
    assert abs(rec["bottom_minus_mesh"]["p50"]) <= DC.PAVEMENT_BAR_M
    ends = [q for q in rec["open_runs"] if q["length_m"] >= 8.0]
    assert len(ends) == 2 and all(abs(q["step_m"]) <= DC.PAVEMENT_BAR_M for q in ends)


def test_deck_ends_read_the_step_to_the_ground_beyond():
    fr = DC.Frame(LAT, LON)
    V = np.array([[-30, -6, 101.0], [30, -6, 101.0], [30, 6, 101.0], [-30, 6, 101.0]], float)
    comp = Component(np.array([[0, 1, 2], [0, 2, 3]]), 0.0, 0.0, 0.0, 0.0, True, np.arange(2))
    ground = lambda e, n: 100.3 if abs(e) > 30 else 95.0                # noqa: E731
    rec = DC.measure(V, comp, fr, _Mesh(fr, ground), _no_others)
    ends = sorted((q for q in rec["open_runs"] if q["length_m"] < 20.0), key=lambda q: q["at"][1])
    assert [q["step_m"] for q in ends] == [pytest.approx(0.7, abs=0.01)] * 2
    assert rec["shape"]["class"].startswith("flat plate")


def test_a_box_is_a_convex_body():
    fr = DC.Frame(LAT, LON)
    b = 100.0
    V = np.array([[-10, -10, b], [10, -10, b], [10, 10, b], [-10, 10, b],
                  [-10, -10, b + 8], [10, -10, b + 8], [10, 10, b + 8], [-10, 10, b + 8]], float)
    tris = np.array([[4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                     [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    rec = DC.measure(V, Component(tris, 0, 8, 0, 0, False, np.arange(len(tris))), fr,
                     _Mesh(fr, lambda e, n: b), _no_others)
    assert rec["shape"]["class"] == "convex body"
    feet = [sd["foot_minus_mesh"]["p50"] for sd in rec["outline_sides"]]
    assert feet and all(abs(f) <= DC.PAVEMENT_BAR_M for f in feet)


def test_the_surface_outside_is_the_higher_of_mesh_and_object():
    out, obj = DC.drawn_outside(np.array([10.0, 10.0, np.nan]), np.array([np.nan, 11.0, 9.0]))
    assert out.tolist() == [10.0, 11.0, 9.0] and obj.tolist() == [False, True, True]


def test_row_base_follows_the_row_kind():
    class P:
        kind, elevation = "OBJECT_MSL", 42.0
    assert DC.row_base(P, 7.0) == 42.0
    P.kind, P.elevation = "OBJECT_AGL", 1.5
    assert DC.row_base(P, 7.0) == 8.5
    P.kind, P.elevation = "OBJECT", None
    assert DC.row_base(P, 7.0) == 7.0


def test_placed_vertices_turn_by_heading():
    class G:
        vertices = np.array([[0.0, 0.0, -10.0]])        # 10 m north of the origin (z south)
    v = DC.placed_vertices(G, 0.0, 0.0, 90.0, 5.0)[0]
    assert v[0] == pytest.approx(10.0) and v[1] == pytest.approx(0.0, abs=1e-9) and v[2] == 5.0
    assert math.isclose(DC.Frame(LAT, LON).leave(*DC.Frame(LAT, LON).enter(LAT, LON))[0], LAT)


# ── #1903 lane l1903: the drawn shape at rest, clearance, mouths, bars ──

import drawn_site_bars as BARS  # noqa: E402
from auto_patch_v2.airport import obj8 as OBJ8  # noqa: E402


def _box_obj(tmp_path, name: str, lift: float) -> str:
    """A 4 x 4 x 3 m box authored on y = 0 inside a constant ANIM offset of
    ``lift`` (the block ``obj8_split`` wraps a split body in)."""
    vs = [(x, y, z) for x in (-2, 2) for y in (0, 3) for z in (-2, 2)]
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
             (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    idx = [i for f in faces for i in f]
    lines = ["I", "800", "OBJ", "", f"POINT_COUNTS 8 0 0 {len(idx)}"]
    lines += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vs] + [f"IDX {i}" for i in idx]
    lines += ["ANIM_begin", f"ANIM_trans 0 {lift} 0 0 {lift} 0 0 0 none",
              f"TRIS 0 {len(idx)}", "ANIM_end"]
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(p)


class _P:
    def __init__(self, path, lat=LAT, lon=LON, kind="OBJECT", elevation=None):
        self.def_path, self.lat, self.lon = path, lat, lon
        self.kind, self.elevation, self.heading_deg = kind, elevation, 0.0


def _item(path, row, **kw):
    g = OBJ8.parse_obj8(path, at_rest=True)
    return {"key": ("pack", "+40+010", row), "row": row, "p": _P(path, **kw), "root": "pack",
            "tile": "+40+010", "g": g, "comps": OBJ8.solid_components(g), "named": True}


def test_a_lifted_split_body_reads_its_clearance(tmp_path):
    """KEGE's jetways (#1984): the split's offset block draws the body
    1.2 m over the mesh under its anchor -- the CLEARANCE reads it."""
    fr = DC.Frame(LAT, LON)
    site = DC.measure_site(DC.Site("j", LAT, LON, 0.0),
                           [_item(_box_obj(tmp_path, "jet__b0_ab12.obj", 1.2), 7)],
                           _Mesh(fr, lambda e, n: 100.0))
    gap = site["placements"][0]
    assert gap["clearance_m"] == pytest.approx(1.2, abs=0.01)
    objs = BARS.object_bars(site["components"], 0.3, DC.GROUND_BAR_M, DC.PRINT_RUN_M,
                            site["placements"])
    assert objs[0]["clearance"]["verdict"] == "FLOAT" and objs[0]["verdict"] == "FAIL"
    seated = DC.measure_site(DC.Site("j", LAT, LON, 0.0),
                             [_item(_box_obj(tmp_path, "s.obj", 0.0), 8)],
                             _Mesh(fr, lambda e, n: 100.0))
    assert seated["placements"][0]["clearance_m"] == pytest.approx(0.0, abs=0.01)


def test_an_object_resting_on_another_reads_no_float(tmp_path):
    """An interior on its terminal's floor stands on that floor, not over
    the mesh: the clearance reads the other placement's surface."""
    fr = DC.Frame(LAT, LON)
    low = _item(_box_obj(tmp_path, "slab.obj", 0.0), 1)
    up = _item(_box_obj(tmp_path, "interior.obj", 3.0), 2)
    site = DC.measure_site(DC.Site("t", LAT, LON, 0.0), [low, up], _Mesh(fr, lambda e, n: 100.0))
    by_row = {p["row"]: p for p in site["placements"]}
    assert by_row[2]["clearance_m"] == pytest.approx(0.0, abs=0.01) and by_row[2]["on_object"]


def test_clearance_only_lists_each_floating_row(tmp_path, capsys):
    """#1969: ``--clearance-only`` reads no component and lists each FLOAT
    ROW -- KBZN places one object per MATERIAL, so a stem's folded bar is
    the least of every building's and hides the floating ones."""
    fr = DC.Frame(LAT, LON)
    items = [_item(_box_obj(tmp_path, "BROWN__b0_ab12.obj", 0.0), 1),
             _item(_box_obj(tmp_path, "BROWN__b1_cd34.obj", 15.0), 2, lat=LAT + 0.001)]
    site = DC.measure_site(DC.Site("a", LAT, LON, 0.0), items,
                           _Mesh(fr, lambda e, n: 100.0), clearance_only=True)
    assert site["components"] == []
    by_row = {p["row"]: p["clearance_m"] for p in site["placements"]}
    assert by_row == pytest.approx({1: 0.0, 2: 15.0}, abs=0.01)
    DC.print_clearances({"sites": [site]}, DC.GROUND_BAR_M, 10)
    out = capsys.readouterr().out
    assert "FLOAT > 0.5 m: 1" in out and "obj2" in out and "obj1 " not in out


def test_split_bodies_fold_to_one_object():
    rec = {"pack": "p", "tile": "+40+010", "row": 3, "def": "objects/T__b40_90d352ac.obj"}
    assert BARS.object_key(rec) == ("p", "+40+010", "objects/T.obj")
    assert BARS.object_key({**rec, "def": "objects/T.obj"})[2] == 3


def test_trench_floor_ends_are_mouths_and_walls_are_not():
    fr = DC.Frame(LAT, LON)
    V, comp = _trench(100.0)
    cut = lambda e, n: 96.0 if abs(n) <= 5.5 else 100.0                # noqa: E731
    rec = DC.measure(V, comp, fr, _Mesh(fr, cut), _no_others)
    ends = sorted(rec["mouths"], key=lambda m: m["at"][1])
    assert len(ends) == 2
    assert all(abs(m["floor_step"]["p50"]) <= DC.PAVEMENT_BAR_M for m in ends)
    assert all(m["opening_m"] == pytest.approx(10.0, abs=1.0) for m in ends)
    assert all(m["ramp_width_m"] >= 10.0 for m in ends)


def _bars_at(rec, site=None):
    rec = {**rec, "row": 1, "tile": "+40+010", "pack": "p", "def": "objects/trench.obj",
           "deck": False, "moving": False, "component": 0, "anchor": [LAT, LON]}
    return BARS.object_bars([rec], 0.3, DC.GROUND_BAR_M, DC.PRINT_RUN_M, [], site)[0]


def test_bars_judge_the_trench_base_and_the_named_mouth():
    fr = DC.Frame(LAT, LON)
    V, comp = _trench(100.0)
    uncut = DC.measure(V, comp, fr, _Mesh(fr, lambda e, n: 100.0), _no_others)
    o = _bars_at(uncut)
    assert o["base"]["verdict"] == "BURY" and o["verdict"] == "FAIL"
    narrow = lambda e, n: 96.0 if abs(n) <= 3.0 else 100.0            # noqa: E731
    o = _bars_at(DC.measure(V, comp, fr, _Mesh(fr, narrow), _no_others),
                 site=(LAT, LON + 21.0 / DC.Frame(LAT, LON).kx, 10.0))
    assert len(o["mouths"]) == 1 and o["mouths"][0]["width_verdict"] == "FAIL"
    assert len(o["mouth_candidates"]) == 1          # the far end: listed, not judged


def test_a_box_has_no_mouth():
    fr = DC.Frame(LAT, LON)
    b = 100.0
    V = np.array([[-10, -10, b], [10, -10, b], [10, 10, b], [-10, 10, b],
                  [-10, -10, b + 8], [10, -10, b + 8], [10, 10, b + 8], [-10, 10, b + 8]], float)
    tris = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                     [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    rec = DC.measure(V, Component(tris, 0, 8, 0, 0, False, np.arange(len(tris))), fr,
                     _Mesh(fr, lambda e, n: b), _no_others)
    assert rec["mouths"] == []


def test_tile_dirs_and_rows_are_read(tmp_path):
    d = tmp_path / "zOrtho4XP_+47+012" / "Earth nav data" / "+40+010"
    d.mkdir(parents=True)
    (d / "+47+012.dsf").write_bytes(b"")
    got = DC.tile_dsf(None, "+47+012", [str(tmp_path / "zOrtho4XP_+47+012")])
    assert got == str(d / "+47+012.dsf")
    assert DC.tile_dsf(None, "+47+013", [str(tmp_path / "zOrtho4XP_+47+012")]) is None
    assert DC.parse_row("+47+012:obj247") == ("+47+012", 247)
    assert DC.parse_datarefs(["sam/jetway/wheels=0.5"]) == {"sam/jetway/wheels": 0.5}


def test_end_edge_mode_reads_a_decks_end_at_the_plans_end_lines():
    """Spec othh-deck-round2 S5: a ramp's long open sides (334 m) are no
    deck END; the run at each of the plan's end lines is, the rest edges."""
    import drawn_site_bars as DB
    side = {"at": [25.2521, 51.6176], "step": 8.46, "length_m": 334.2, "joins": "top",
            "verdict": "FAIL"}
    end = {"at": [25.25057, 51.6162], "step": -0.42, "length_m": 8.9, "joins": "top",
           "verdict": "FAIL"}
    line = ((25.25055, 51.61615), (25.25060, 51.61625))
    ends, rest = DB._true_ends([side, end], [line])
    assert [e["step"] for e in ends] == [-0.42] and rest == [side]
    assert DB._stem("objects/OTHH_Bridge_06_LOD0_000__b0_7273f3aa.obj") == "othh_bridge_06_lod0_000"
