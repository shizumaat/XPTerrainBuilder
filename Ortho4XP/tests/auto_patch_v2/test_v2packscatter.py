"""THE SCATTER CLASS — the predicate's twins and the census tool's
report shape (spec ``pack-read-once-fast-spec.md`` §B.2, slice S5a).

Nothing in the build consults the predicate: these twins pin the
PREDICATE (``airport/scatter.py``) at and around each of its two
thresholds, and the CENSUS TOOL's report shape
(``tools/pack_scatter_census.py``) end to end over a synthetic pack —
apt.dat, tile DSF, cached text dump, resources — with no X-Plane
install, no DEM, no network.
"""
from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from auto_patch_v2.airport import obj8 as O                      # noqa: E402
from auto_patch_v2.airport import scatter as S                   # noqa: E402
from auto_patch_v2.law import Law                                # noqa: E402

LAW = Law.for_airport("")
SC = LAW.tables.structures.scatter
THICK = LAW.tables.structures.basin.min_solid_thickness_m


# ── synthetic resources ──────────────────────────────────────────────────

def _box(x: float, z: float, w: float, d: float, h: float, y0: float = 0.0):
    """One CUBOID's triangles as vertex triples — a genuine component
    when ``h`` clears the thickness gate.  Its plan-box diagonal is
    ``hypot(w, d)``."""
    x1, z1, y1 = x + w, z + d, y0 + h
    v = [(x, y0, z), (x1, y0, z), (x1, y0, z1), (x, y0, z1),
         (x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def _sheet(x: float, z: float, length: float, h: float):
    """A VERTICAL quad — zero plan area, so line-shaped at any length
    under ``line_object_max_h`` (10bb's strongest line reading)."""
    v = [(x, 0.0, z), (x + length, 0.0, z), (x + length, h, z), (x, h, z)]
    return [(v[0], v[1], v[2]), (v[0], v[2], v[3])]


def _write_obj(path: Path, comps, hard: str | None = None) -> str:
    """An OBJ8 whose solid components are ``comps`` (each a list of
    vertex triples).  ``hard`` emits ``ATTR_hard`` / ``ATTR_hard_deck``
    before the triangles."""
    verts: list[tuple[float, float, float]] = []
    for comp in comps:
        for tri in comp:
            verts.extend(tri)
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    if hard:
        out.append(hard)
    out.append(f"TRIS 0 {len(verts)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n")
    return str(path)


def _field(tmp: Path, name: str, n: int, w: float = 0.5, h: float = 1.0,
           hard: str | None = None, extra=()) -> str:
    comps = [_box(3.0 * i, 0.0, w, w, h) for i in range(n)]
    comps.extend(extra)
    return _write_obj(tmp / name, comps, hard=hard)


def _cache():
    return O.ResourceCache(THICK)


def _read(path: str):
    return S.read(_cache(), path, LAW)


# ── T1 THE PREDICATE, at and around each threshold ───────────────────────

def test_law_table_carries_the_two_thresholds():
    """The thresholds are NAMED LAW VALUES in one table, not literals."""
    assert SC.components_min == 64
    assert SC.component_diag_max_m == 10.0
    # ...and the predicate itself states no threshold: every comparison
    # reads the table through ``_laws`` (one table, no literals)
    src = Path(ROOT / "src/auto_patch_v2/airport/scatter.py").read_text()
    body = src.split('"""', 2)[2]                    # past the module doc
    assert "64" not in body and "10.0" not in body


def test_a_bush_field_is_scatter(tmp_path):
    r = _read(_field(tmp_path, "bushes.obj", 200))
    assert r.scatter and r.reason == ""
    assert r.components == 200 and r.components_small == 200
    assert r.max_oversize_diag_m == 0.0


@pytest.mark.parametrize("n,ok", [(63, False), (64, True), (65, True)])
def test_the_components_min_threshold(tmp_path, n, ok):
    r = _read(_field(tmp_path, f"n{n}.obj", n))
    assert r.scatter is ok
    assert r.components == n
    if not ok:
        assert "components_min" in r.reason


def test_the_component_diag_threshold(tmp_path):
    """A component AT ``component_diag_max_m`` is admitted; one just over
    it refuses the whole resource and its size is reported."""
    # a 3-4-5 box: its plan diagonal is EXACTLY component_diag_max_m
    w, d = 0.6 * SC.component_diag_max_m, 0.8 * SC.component_diag_max_m
    at = _read(_field(tmp_path, "at.obj", 64,
                      extra=[_box(500.0, 0.0, w, d, 4.0)]))
    assert at.scatter, at.reason
    assert at.max_diag_m == pytest.approx(SC.component_diag_max_m, abs=1e-6)
    over = _read(_field(tmp_path, "over.obj", 64,
                        extra=[_box(500.0, 0.0, w * 1.2, d * 1.2, 4.0)]))
    assert not over.scatter
    assert "component_diag_max_m" in over.reason
    assert over.max_oversize_diag_m == pytest.approx(
        SC.component_diag_max_m * 1.2, abs=1e-6)


def test_a_terminal_with_one_twelve_metre_component_is_not_scatter(tmp_path):
    r = _read(_field(tmp_path, "terminal.obj", 300,
                     extra=[_box(900.0, 0.0, 12.0, 1.0, 9.0)]))
    assert not r.scatter
    assert r.max_oversize_diag_m == pytest.approx(math.hypot(12.0, 1.0), abs=1e-6)


def test_a_fence_of_posts_and_wire_runs_is_scatter_by_the_line_clause(tmp_path):
    """10bb's reading is IMPORTED, never restated: the wire runs are
    line-shaped, the posts are small, and the FILE is not a line object
    (its posts are not line-shaped), so the class takes it whole."""
    wires = [_sheet(0.0, 20.0 + 5.0 * k, 50.0, 1.0) for k in range(4)]
    r = _read(_field(tmp_path, "fence.obj", 64, extra=wires))
    assert r.scatter, r.reason
    assert r.components_line == 4 and r.components_small == 64
    assert not r.line_object


def test_a_pure_line_object_keeps_its_drape(tmp_path):
    comps = [_sheet(0.0, 5.0 * k, 50.0, 1.0) for k in range(70)]
    r = _read(_write_obj(tmp_path / "wire.obj", comps))
    assert r.line_object and not r.scatter
    assert "LINE OBJECT" in r.reason


def test_sixty_four_identical_struts_are_scatter_and_the_false_positive_is_named(tmp_path):
    """LEMD's ``Terminal4_yellow-LEMD11`` class: 11,537 T4 roof struts,
    every one 8.69-8.70 m.  The box-attachment discriminator was
    REFUTED (spec row 13), so this reads SCATTER by design and §B.2 (3)
    makes it harmless instead of eliminating it."""
    side = 8.695 / math.sqrt(2.0)
    comps = [_box(20.0 * i, 0.0, side, side, 3.0) for i in range(64)]
    r = _read(_write_obj(tmp_path / "struts.obj", comps))
    assert r.scatter
    assert 8.69 <= r.max_diag_m <= 8.70


@pytest.mark.parametrize("attr", ["ATTR_hard", "ATTR_hard_deck"])
def test_a_hard_file_is_never_scatter(tmp_path, attr):
    r = _read(_field(tmp_path, f"{attr}.obj", 200, hard=attr))
    assert not r.scatter and "HARD" in r.reason
    assert r.hard_triangles == 200 * 12


def test_only_genuine_components_count(tmp_path):
    """The thickness gate is the cache's (a decal never witnesses): 63
    genuine boxes plus 10 decals is 63 components, not 73."""
    decals = [_box(5.0 * i, 40.0, 0.5, 0.5, THICK / 3.0) for i in range(10)]
    r = _read(_field(tmp_path, "decals.obj", 63, extra=decals))
    assert r.components == 63 and not r.scatter


def test_components_min_zero_disables_the_class(tmp_path):
    law = type("L", (S.ScatterLaw,), {"rebake": LAW.tables.structures.rebake})(
        components_min=0, component_diag_max_m=SC.component_diag_max_m)
    r = S.read(_cache(), _field(tmp_path, "off.obj", 200), law)
    assert not r.scatter and "disabled" in r.reason
    assert r.components == 200            # the numbers are still reported


def test_the_verdict_is_frame_independent(tmp_path):
    """Pure in the FILE: the reading does not depend on any placement,
    and :func:`is_scatter` is :func:`read`'s verdict."""
    p = _field(tmp_path, "pure.obj", 100)
    c = _cache()
    assert S.is_scatter(c, p, LAW) is S.read(c, p, LAW).scatter is True


def test_an_unreadable_resource_is_not_scatter(tmp_path):
    r = _read(str(tmp_path / "missing.obj"))
    assert not r.scatter and r.components == 0


# ── T2 THE CENSUS TOOL's report shape, end to end on a synthetic pack ────

@pytest.fixture()
def pack(tmp_path):
    """A pack the tool resolves exactly as it resolves a real one:
    Custom Scenery layout, apt.dat with a 1302 datum, a tile DSF, and a
    CACHED text dump keyed by that DSF's identity."""
    xp = tmp_path / "xp"
    root = xp / "Custom Scenery" / "TestPack"
    nav = root / "Earth nav data"
    nav.mkdir(parents=True)
    (nav / "apt.dat").write_text("\n".join([
        "I", "1000 Version", "",
        "1    10 0 0 ZZZZ Test Field",
        "1302 datum_lat 0.500000",
        "1302 datum_lon 0.500000",
        "100 30.00 1 0 0.00 0 0 0 09 0.500000 0.499000 0 0 0 0 0 0 "
        "27 0.500000 0.501000 0 0 0 0 0 0", ""]))
    dsf = nav / "+00+000" / "+00+000.dsf"
    dsf.parent.mkdir()
    dsf.write_bytes(b"XPLNEDSF")
    # the resources: a bush field, a building, and a 63-component
    # near-threshold file
    _field(root / "objects", "bushes.obj", 200)
    _write_obj(root / "objects" / "building.obj",
               [_box(0.0, 0.0, 40.0, 30.0, 12.0)])
    _field(root / "objects", "near.obj", 63)
    mo = 111_412.84 * math.cos(math.radians(0.5))
    ml = 111_132.954

    def ll(x, y):
        return (0.5 + x / mo, 0.5 + y / ml)          # (lon, lat)

    rows = ["OBJECT_DEF objects/bushes.obj",
            "OBJECT_DEF objects/building.obj",
            "OBJECT_DEF objects/near.obj"]
    # the bush field stands ON the building; the near-threshold file far away
    for i, (d, x, y) in enumerate([(0, 0.0, 0.0), (1, 0.0, 0.0), (2, 300.0, 300.0)]):
        lon, lat = ll(x, y)
        rows.append(f"OBJECT {d} {lon:.9f} {lat:.9f} 0.000")
    mod = tmp_path / "mod_cache" / "TestPack"
    mod.mkdir(parents=True)
    from auto_patch_v2.airport import dsf as D
    dump = mod / f"+00+000.dsf.{D.text_dump_tag(str(dsf))}.text"
    dump.write_text("\n".join(rows) + "\n")
    t = time.time()
    os.utime(dsf, (t - 60, t - 60))
    os.utime(dump, (t, t))
    return str(xp), str(tmp_path / "mod_cache")


def test_the_census_report_shape(pack):
    import pack_scatter_census as C
    xp, mod = pack
    rep = C.census("ZZZZ", xp, mod, law=LAW)
    assert "skipped" not in rep
    assert rep["window"]["pack"] == "TestPack"
    assert rep["window"]["placements"] == 3
    assert rep["law"] == {"components_min": SC.components_min,
                          "component_diag_max_m": SC.component_diag_max_m,
                          "footprint_touch_m": LAW.tables.structures.placement.footprint_touch_m,
                          "foot_samples_max": LAW.tables.structures.rebake.foot_samples_max,
                          "basin_admission_depth_m": LAW.tables.structures.basin.admission_depth_m,
                          "min_solid_thickness_m": THICK}
    # 1 — the class and its share
    assert rep["scatter_resources"] == 1
    assert rep["placed_components"] == 200 + 1 + 63
    assert rep["scatter_placed_components"] == 200
    assert rep["scatter_component_share"] == pytest.approx(200 / 264, abs=1e-5)
    row = next(r for r in rep["rows"] if r["scatter"])
    assert row["resource"].endswith("bushes.obj")
    assert (row["components"], row["placements"]) == (200, 1)
    assert row["max_diag_m"] == pytest.approx(math.hypot(0.5, 0.5), abs=1e-3)
    # 2 (a) — the foot-row UPPER BOUND, named as one
    fr = rep["foot_rows"]
    assert fr["scatter_parts"] == 200 and fr["scatter_placements"] == 1
    assert fr["rows_upper_bound"] == 200 * LAW.tables.structures.rebake.foot_samples_max
    assert "UPPER BOUND" in fr["kind"]
    # 3 (b) — the pad proxy: the bushes over the building touch it; the
    # far ones do not, and the near-threshold file is the other side
    cp = rep["cluster_pads"]
    assert cp["scatter_boxes"] == 200
    assert 0 < cp["touching_boxes"] < 200
    assert cp["non_scatter_placements"] == 2
    assert cp["non_scatter_placements_touched"] == 1
    assert "PROXY" in cp["kind"]
    # 4 (c) — nothing here reaches a structure reader
    assert rep["structure_read_false_positives"] == []
    # 5 (d) — the 63-component file is the near-threshold row
    assert [r["resource"].split("/")[-1] for r in rep["near_threshold"]] == ["near.obj"]


def test_the_census_skips_an_airport_with_no_pack(tmp_path):
    import pack_scatter_census as C
    rep = C.census("ZZZZ", str(tmp_path / "xp"), str(tmp_path / "mc"), law=LAW)
    assert "no apt.dat" in rep["skipped"]
    assert rep.get("scatter_resources") is None


def test_the_census_skips_an_airport_with_no_cached_dump(pack, tmp_path):
    """It NEVER runs DSFTool and never writes: no dump, no census."""
    import pack_scatter_census as C
    xp, _mod = pack
    rep = C.census("ZZZZ", xp, str(tmp_path / "empty_cache"), law=LAW)
    assert "no cached DSF text dump" in rep["skipped"]
