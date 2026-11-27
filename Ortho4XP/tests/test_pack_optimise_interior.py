"""#1707 ``interior`` (owner 2026-11-14T21:41Z): under the pack's own roof
small props are drawn only within 150 m and nothing casts a shadow — in
an interior COPY (``<stem>.o4opt_in.obj``), never the vendor file; a
definition also placed outside keeps those rows on the vendor file.
Headless (``pack_optimise_fixture``).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import pack_optimise_fixture as FX  # noqa: E402
from auto_patch import optimise_stage as OS  # noqa: E402
from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from auto_patch_v2.airport.dsf_rows import placement_rows  # noqa: E402
from auto_patch_v2.airport.pack_optimise import impact as IM  # noqa: E402
from auto_patch_v2.airport.pack_optimise import interior as IN  # noqa: E402
from auto_patch_v2.airport.pack_optimise import objcopy as OC  # noqa: E402
from auto_patch_v2.airport.pack_optimise import roof as RF  # noqa: E402
from test_pack_optimise_swap import obj  # noqa: E402

TERMINAL = obj((-50, 50), (0, 20), (-50, 50))      # its top is the roof
SHELL = obj((-30, 30), (0, 10), (-30, 30))         # an interior shell under it
BENCH = obj((0, 1), (0, 1), (0, 1), lights=("LIGHT_NAMED lamp 0 1 0",))
PERSON = obj((0, 0.5), (0, 1.8), (0, 0.5)).replace(
    "TEXTURE car.png", "TEXTURE car.png\nATTR_LOD\t0\t400")
DUMP = ("PROPERTY sim/west 51\nPROPERTY sim/east 52\n"
        "PROPERTY sim/south 25\nPROPERTY sim/north 26\n"
        "OBJECT_DEF o/terminal.obj\nOBJECT_DEF o/shell.obj\n"
        "OBJECT_DEF o/bench.obj\nOBJECT_DEF o/person.obj\n"
        "OBJECT 0 51.500000000 25.500000000 0.000000\n"
        "OBJECT 1 51.500000000 25.500000000 0.000000\n"
        "OBJECT 2 51.500100000 25.500100000 0.000000\n"          # under
        "OBJECT_AGL 2 51.500200000 25.500000000 6.000000 0.000000\n"  # mezzanine
        "OBJECT 2 51.510000000 25.500000000 0.000000\n"          # 1 km out
        "OBJECT_AGL 2 51.500100000 25.500000000 21.000000 0.000000\n"  # on the roof
        "OBJECT 3 51.500000000 25.500200000 0.000000\n")         # under
FILES = (("terminal", TERMINAL), ("shell", SHELL), ("bench", BENCH),
         ("person", PERSON))


def _objects(root):
    (root / "o").mkdir(parents=True)
    for name, text in FILES:
        (root / "o" / f"{name}.obj").write_text(text, encoding="utf-8", newline="")
    return root


def _plan(p, dump=DUMP):
    lines = dump.splitlines(keepends=True)
    defs = [ln[11:].strip() for ln in lines if ln.startswith("OBJECT_DEF ")]
    return IN.plan_interior(str(p), defs, placement_rows(lines), set())


def test_the_roof_reads_inside_outside_and_height(tmp_path):
    plan = _plan(_objects(tmp_path / "p"))
    assert plan["defs"] == {
        "o/bench.obj": {"lod": True, "split": True},
        "o/person.obj": {"lod": True, "split": False},
        "o/shell.obj": {"lod": False, "split": False},
    }, "the terminal is the roof, never under it"
    cells = RF.decode(plan["roof"])
    lat0, lon0 = plan["origin"]
    rows = [ln.split() for ln in DUMP.splitlines() if ln.startswith("OBJECT ")
            or ln.startswith("OBJECT_AGL ")]
    assert [RF.under(cells, lat0, lon0, t) for t in rows[2:6]] == [
        True, True, False, False], "under, mezzanine, outside, on the roof"
    msl = ["OBJECT_MSL", "2", "51.500100000", "25.500100000", "4.0", "0"]
    assert not RF.under(cells, lat0, lon0, msl), "an MSL row has no ground"


def test_a_wall_at_the_roofs_edge_keeps_its_shadow(tmp_path):
    p = _objects(tmp_path / "p")
    (p / "o" / "shell.obj").write_text(obj((-50, 50), (0, 10), (-50, 50)),
                                       encoding="utf-8", newline="")
    assert "o/shell.obj" not in _plan(p)["defs"]


def test_clamp_lods_header_and_body():
    lines = ["I", "800", "OBJ", "ATTR_LOD\t0\t400", "POINT_COUNTS 3 0 0 3",
             "TRIS 0 3"]
    assert IN.clamp_lods(lines, 150)[3] == "ATTR_LOD\t0\t150"
    body = ["POINT_COUNTS 3 0 0 3", "ATTR_LOD 0 100", "TRIS 0 3",
            "ATTR_LOD 100 400", "TRIS 0 3", "ATTR_LOD 400 1000", "TRIS 0 3",
            "ATTR_LOD 1000 20000", "LIGHT_NAMED lamp 0 1 0"]
    assert IN.clamp_lods(body, 150) == [
        "POINT_COUNTS 3 0 0 3", "ATTR_LOD 0 100", "TRIS 0 3",
        "ATTR_LOD\t100\t150", "TRIS 0 3",
        "ATTR_LOD 1000 20000", "LIGHT_NAMED lamp 0 1 0"], \
        "a far block drawing triangles goes; a lights-only one stays"


def test_the_interior_copy(tmp_path):
    p = _objects(tmp_path / "p")
    phys = str(p / "o" / "bench.obj")
    params = IN.copy_params("o/bench.obj", {"lod": True}, {})
    lines = IN.copy_text(phys, params).splitlines()
    assert lines[3] == f"# o4opt {OC.stamp(phys, params)}"
    pc = lines.index(next(ln for ln in lines if ln.startswith("POINT_COUNTS")))
    assert "GLOBAL_no_shadow" in lines[:pc]
    assert "ATTR_LOD 0 150" in lines and "ATTR_LOD 150 20000" in lines, \
        "drawn within 150 m, its lamp beyond"
    shell = IN.copy_text(str(p / "o" / "shell.obj"),
                         IN.copy_params("o/shell.obj", {"lod": False}, {}))
    assert "GLOBAL_no_shadow" in shell and "ATTR_LOD" not in shell
    person = IN.copy_text(str(p / "o" / "person.obj"),
                          IN.copy_params("o/person.obj", {"lod": True}, {}))
    assert "ATTR_LOD\t0\t150" in person and "\t400" not in person
    assert (p / "o" / "bench.obj").read_text(encoding="utf-8") == BENCH
    both = IN.copy_params("o/bench.obj", {"lod": True},
                          {"o/bench.obj": {"specular": 0.5, "lod": 400}})
    assert both["lod"] == 150 and both["specular"] == 0.5


def test_apply_splits_a_definition_placed_inside_and_out(tmp_path):
    out, moved = IN.apply(DUMP, _plan(_objects(tmp_path / "p")))
    lines = out.splitlines()
    assert [ln for ln in lines if ln.startswith("OBJECT_DEF")] == [
        "OBJECT_DEF o/terminal.obj", "OBJECT_DEF o/shell.o4opt_in.obj",
        "OBJECT_DEF o/bench.obj", "OBJECT_DEF o/person.o4opt_in.obj",
        "OBJECT_DEF o/bench.o4opt_in.obj"]
    rows = [ln.split()[1] for ln in lines if ln.startswith("OBJECT ")
            or ln.startswith("OBJECT_AGL ")]
    assert rows == ["0", "1", "4", "4", "2", "2", "3"]
    assert moved == 4, "the shell, two benches and the person"


def test_estimate_and_offer_row(tmp_path):
    p = _objects(tmp_path / "p")
    lines = DUMP.splitlines(keepends=True)
    recipe = PO.build_recipe(str(p), lines, None)
    n, tris = IN.estimate(str(p), lines, recipe["interior"])
    assert (n, tris) == (4, 36), "two benches and a person drew 12 each at 150 m"
    row = next(r for r in IM.steps(str(p), lines, recipe) if r["key"] == "interior")
    assert (row["count"], row["tris"]) == (4, 36)
    assert "interior" not in PO.build_recipe(str(p), lines, None, ["objects"])


def test_written_reapplied_and_undone(tmp_path, monkeypatch):
    rp = FX.make_pack(tmp_path, monkeypatch)
    rp.dsf.write_bytes(DUMP.encode("utf-8"))
    _objects(rp.pack)
    recipe = PO.build_recipe(str(rp.pack), DUMP.splitlines(keepends=True), None,
                             ["interior"])
    FX.write(rp, optimise=recipe)
    assert "OBJECT_DEF o/bench.o4opt_in.obj" in rp.dsf.read_text(encoding="utf-8")
    made = FX.entry(rp)[PO.RECORD_KEY]["generated"]
    assert made == ["o/bench.o4opt_in.obj", "o/person.o4opt_in.obj",
                    "o/shell.o4opt_in.obj"]
    assert all((rp.pack / f).is_file() for f in made)
    first = rp.dsf.read_bytes()
    stat = (rp.pack / made[0]).stat().st_mtime_ns
    FX.write(rp)
    assert rp.dsf.read_bytes() == first, "re-applied on the next write"
    assert (rp.pack / made[0]).stat().st_mtime_ns == stat, "a current copy stays"
    OS.undo(str(rp.pack))
    assert rp.dsf.read_bytes() == DUMP.encode("utf-8")
    assert not any((rp.pack / f).exists() for f in made)
    assert (rp.pack / "o" / "bench.obj").read_text(encoding="utf-8") == BENCH


def test_a_roof_whose_faces_cover_no_cell_is_empty():
    """An instance whose roof faces rasterise to no cell (LGKR, owner
    2026-11-27) reads as an empty roof, never an IndexError."""
    import numpy as np
    from auto_patch_v2.airport.pack_optimise import roof as _rf
    sliver = np.zeros((1, 3, 3))            # degenerate: all corners equal
    inst = _rf.Instance(0, "x.obj", sliver, np.zeros(0, dtype=np.int64),
                        np.zeros(0))
    r = _rf.read_roof([inst], 39.0, 19.0)
    assert len(r.keys) == 0


def test_instances_with_no_roof_cell_read_no_roof():
    """#2250: LGKR's Adjust… failed ("boolean index did not match") when
    every instance's faces held no grid cell: they are no roof."""
    import numpy as np
    flat = RF.Instance(0, "decal.obj", np.zeros((0, 3, 3)), np.zeros(0, dtype=np.int64),
                       np.zeros(0))
    roof = RF.read_roof([flat, flat], 39.6, 19.9)
    assert not len(roof.keys) and not len(roof.top) and not len(roof.second)
