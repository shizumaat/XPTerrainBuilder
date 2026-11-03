"""#1707 O1/O2/D3: "Optimise pack" writes a lighter COPY of a pack object
(``<stem>.o4opt.obj``, never the vendor file) — its specular made global
so it instances, a draw distance of 1000 x size clamped to 400-1,500 m on
an object under 12 m with its un-animated lights again past it — and the
optimised DSF names the copy.  Headless (``pack_optimise_fixture``).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import pack_optimise_fixture as FX  # noqa: E402
from auto_patch import optimise_stage as OS  # noqa: E402
from auto_patch_v2.airport import pack_optimise as PO  # noqa: E402
from auto_patch_v2.airport.pack_optimise import objcopy as OC  # noqa: E402
from test_pack_optimise_swap import obj  # noqa: E402

SHINY = obj((0, 2), (0, 1.5), (-4, 0), tris=60).replace(
    "TRIS 0 180", "TRIS 0 90\nATTR_shiny_rat 0.6\nTRIS 90 90") + (
    "LIGHT_NAMED headlight 0 1 -0.1\n")


def _plan(root, defs, uses, skip):
    return OC.plan_objects(root, OC.placed_objects(root, defs, uses, skip))


def _pack(tmp_path, text):
    p = tmp_path / "p"
    (p / "o").mkdir(parents=True)
    (p / "o" / "Cone.obj").write_text(text, encoding="utf-8", newline="")
    return p


def test_the_plan_gives_specular_to_a_repeated_object_and_lod_to_a_heavy_one(
        tmp_path, monkeypatch):
    p = _pack(tmp_path, SHINY)
    monkeypatch.setattr(OC, "MIN_WEIGHT", 1000)
    got = _plan(str(p), ["o/Cone.obj"], {0: 20}, set())
    assert got == {"o/Cone.obj": {"specular": 0.6, "lod": 1500}}, "4 m x 1000 clamps to 1500"
    assert _plan(str(p), ["o/Cone.obj"], {0: 1}, set()) == {}, \
        "one placement instances nothing and weighs too little"
    assert _plan(str(p), ["o/Cone.obj"], {0: 20}, {"o/Cone.obj"}) == {}, \
        "a swapped object has no copy"


def test_small_and_big_and_lodded_objects(tmp_path, monkeypatch):
    monkeypatch.setattr(OC, "MIN_WEIGHT", 1)
    for size, want in ((0.3, 400), (0.9, 900), (11.0, 1500), (13.0, None)):
        p = _pack(tmp_path / str(size), obj((0, size), (0, 0.2), (0, 0.2)))
        got = _plan(str(p), ["o/Cone.obj"], {0: 1}, set())
        assert (got.get("o/Cone.obj") or {}).get("lod") == want, size
    p = _pack(tmp_path / "lod", obj((0, 1), (0, 1), (0, 1)) + "ATTR_LOD 0 900\n")
    assert _plan(str(p), ["o/Cone.obj"], {0: 9}, set()) == {}, \
        "the author's own draw distance stays"
    p = _pack(tmp_path / "anim", obj((0, 1), (0, 1), (0, 1)) +
              "ANIM_begin\nLIGHT_NAMED beacon 0 1 0\nANIM_end\n")
    assert _plan(str(p), ["o/Cone.obj"], {0: 9}, set()) == {}, \
        "a light inside an animation keeps the object without a draw distance"


def test_the_copy(tmp_path):
    p = _pack(tmp_path, SHINY)
    text = OC.copy_text(str(p / "o" / "Cone.obj"), {"specular": 0.6, "lod": 1500})
    lines = text.splitlines()
    assert lines[:3] == ["I", "800", "OBJ"] and lines[3].startswith("# o4opt ")
    assert "ATTR_shiny_rat" not in text
    assert lines.index("GLOBAL_specular 0.6") < lines.index(
        next(ln for ln in lines if ln.startswith("POINT_COUNTS")))
    lod = lines.index("ATTR_LOD 0 1500")
    assert lines[lod + 1] == "TRIS 0 90", "the LOD opens the commands"
    tail = lines.index("ATTR_LOD 1500 20000")
    assert lines[tail + 1:] == ["LIGHT_NAMED headlight 0 1 -0.1"]
    assert (p / "o" / "Cone.obj").read_text(encoding="utf-8") == SHINY


def test_crlf_and_bytes_are_kept(tmp_path):
    raw = SHINY.replace("\n", "\r\n").replace("TEXTURE car.png", "TEXTURE caf\xe9.png")
    p = tmp_path / "p" / "o"
    p.mkdir(parents=True)
    (p / "Cone.obj").write_bytes(raw.encode("latin-1"))
    text = OC.copy_text(str(p / "Cone.obj"), {"specular": None, "lod": 400})
    assert "\r\n" in text and "\n" not in text.replace("\r\n", "")
    assert "caf\xe9.png" in text


def test_rename_rows_points_the_dsf_at_the_copy():
    text = "OBJECT_DEF o/Cone.obj\nOBJECT_DEF o/Other.obj\nOBJECT 0 1 2 3\n"
    out, n = OC.rename_rows(text, {"o/Cone.obj": {"lod": 400}})
    assert n == 1 and out.splitlines()[:2] == ["OBJECT_DEF o/Cone.o4opt.obj",
                                               "OBJECT_DEF o/Other.obj"]


def test_written_reapplied_and_undone(tmp_path, monkeypatch):
    rp = FX.make_pack(tmp_path, monkeypatch)
    (rp.pack / "objects" / "van.obj").write_text(SHINY, encoding="utf-8", newline="")
    monkeypatch.setattr(OC, "MIN_WEIGHT", 1)
    original = rp.dsf.read_bytes()
    recipe = PO.build_recipe(str(rp.pack), FX.DUMP.splitlines(keepends=True), None)
    assert set(recipe["objects"]) == {"objects/van.obj"}
    FX.write(rp, optimise=recipe)
    copy = rp.pack / "objects" / "van.o4opt.obj"
    assert copy.is_file() and "OBJECT_DEF objects/van.o4opt.obj" in rp.dsf.read_text(
        encoding="utf-8")
    assert FX.entry(rp)[PO.RECORD_KEY]["generated"] == ["objects/van.o4opt.obj"]
    stat = copy.stat().st_mtime_ns
    first = rp.dsf.read_bytes()
    FX.write(rp)
    assert rp.dsf.read_bytes() == first and copy.stat().st_mtime_ns == stat, \
        "a current copy is not written again"
    OS.undo(str(rp.pack))
    assert rp.dsf.read_bytes() == original and not copy.exists()
    assert (rp.pack / "objects" / "van.obj").read_text(encoding="utf-8") == SHINY
