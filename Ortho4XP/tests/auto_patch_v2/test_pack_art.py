"""MISSING ART (owner RULINGS 2026-10-06c, issue #433): the check, the
offered omission and the write that carries it.

X-Plane drops a WHOLE pack when its DSF declares one definition whose file
it cannot find.  Every pack here is a synthetic ``tmp_path`` fake; DSFTool
is a byte-copy stand-in (the real encoder has its own twin in
``test_v2dsfagl``).  No network, no corpus, no X-Plane.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import pack_art as PA
from auto_patch_v2.model import placement as PM

#: a dump with every def kind and every use-row shape
DUMP = ("PROPERTY sim/west 51\n"
        "PROPERTY sim/overlay 1\n"
        "TERRAIN_DEF terrain_Water\n"
        "OBJECT_DEF objects/a.obj\n"
        "OBJECT_DEF objects/gone.obj\n"
        "OBJECT_DEF objects/c.obj\n"
        "POLYGON_DEF Imagery/miss1.pol\n"
        "POLYGON_DEF draped/ok.pol\n"
        "POLYGON_DEF Imagery/miss2.pol\n"
        "NETWORK_DEF roads/net.net\n"
        "RASTER_DEF elevation\n"
        "OBJECT 0 51.1 25.1 90.0\n"
        "OBJECT 1 51.2 25.2 45.0\n"
        "OBJECT_AGL 2 51.3 25.3 10.0 2.5\n"
        "OBJECT_MSL 1 51.4 25.4 11.0 3.5\n"
        "OBJECT 2 51.5 25.5 0.0\n"
        "BEGIN_POLYGON 0 65535 2\n"
        "BEGIN_WINDING\n"
        "POLYGON_POINT 51.0 25.0\n"
        "POLYGON_POINT 51.1 25.0\n"
        "END_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_POLYGON 1 65535 2\n"
        "BEGIN_WINDING\n"
        "POLYGON_POINT 51.2 25.0\n"
        "END_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_POLYGON 2 65535 2\n"
        "BEGIN_WINDING\n"
        "POLYGON_POINT 51.3 25.0\n"
        "END_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_POLYGON 1 7 2\n"
        "BEGIN_WINDING\n"
        "POLYGON_POINT 51.4 25.0\n"
        "END_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_SEGMENT 0 1 0 51.0 25.0 0.0\n"
        "SHAPE_POINT 51.05 25.0 0.0\n"
        "END_SEGMENT 2 51.1 25.0 0.0\n"
        "BEGIN_PATCH 0 0.0 -1.0 1 7\n"
        "BEGIN_PRIMITIVE 0\n"
        "PATCH_VERTEX 51.0 25.0 0.0 0.0 0.0\n"
        "END_PRIMITIVE\n"
        "END_PATCH\n")

PRESENT = ("objects/a.obj", "objects/c.obj", "draped/ok.pol", "roads/net.net")
ALL = PRESENT + ("objects/gone.obj", "Imagery/miss1.pol", "Imagery/miss2.pol")


def _write(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _pack(tmp_path: Path, present=PRESENT, dump: str = DUMP):
    pack = tmp_path / "Some Pack"
    pack.mkdir(parents=True, exist_ok=True)
    for rel in present:
        _write(pack / rel)
    dsf = _write(pack / "Earth nav data" / "+20+050" / "+25+051.dsf", dump)
    return pack, dsf


def _missing(pack: Path, dump: str = DUMP, index=None, also=None):
    return PA.missing_definitions(str(pack), dump.splitlines(True),
                                  {} if index is None else index, also)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ── THE CHECK ───────────────────────────────────────────────────────────

def test_all_present_is_nothing_missing(tmp_path):
    pack, _ = _pack(tmp_path, present=ALL)
    assert _missing(pack) == ()


def test_a_missing_object_is_named_with_its_uses(tmp_path):
    pack, _ = _pack(tmp_path, present=PRESENT + ("Imagery/miss1.pol",
                                                 "Imagery/miss2.pol"))
    got = _missing(pack)
    assert got == (PA.MissingDef("object", 1, "objects/gone.obj", 2),)
    assert PA.can_omit(got)


def test_missing_polygons_are_named_in_declaration_order(tmp_path):
    pack, _ = _pack(tmp_path, present=PRESENT + ("objects/gone.obj",))
    got = _missing(pack)
    assert [(m.kind, m.index, m.path, m.uses) for m in got] == [
        ("polygon", 0, "Imagery/miss1.pol", 1),
        ("polygon", 2, "Imagery/miss2.pol", 1)]
    assert PA.summary(got) == {"total": 2, "kinds": {"polygon": 2},
                               "uses": 2, "can_omit": True,
                               "first_paths": ["Imagery/miss1.pol",
                                               "Imagery/miss2.pol"]}


def test_a_library_path_that_resolves_is_present(tmp_path):
    phys = _write(tmp_path / "lib_pack" / "thing.obj")
    dump = "OBJECT_DEF vendor/thing.obj\nOBJECT 0 1 2 3\n"
    pack, _ = _pack(tmp_path, dump=dump)
    assert _missing(pack, dump, {"vendor/thing.obj": str(phys)}) == ()


def test_a_library_path_that_does_not_resolve_is_missing(tmp_path):
    dump = ("OBJECT_DEF vendor/thing.obj\nOBJECT_DEF vendor/gone.obj\n"
            "OBJECT 1 1 2 3\n")
    phys = _write(tmp_path / "lib_pack" / "thing.obj")
    pack, _ = _pack(tmp_path, dump=dump)
    got = _missing(pack, dump, {"vendor/thing.obj": str(phys),
                                # an index row whose file is gone
                                "vendor/gone.obj": str(tmp_path / "nope")})
    assert [(m.path, m.uses) for m in got] == [("vendor/gone.obj", 1)]


def test_stock_lib_builtin_water_and_raster_are_never_missing(tmp_path):
    dump = ("TERRAIN_DEF terrain_Water\nOBJECT_DEF lib/g10/autogen/x.ags\n"
            "RASTER_DEF elevation\nOBJECT 0 1 2 3\n")
    pack, _ = _pack(tmp_path, dump=dump)
    assert _missing(pack, dump) == ()


def test_another_export_directive_keeps_a_name_present(tmp_path):
    dump = "OBJECT_DEF vendor/Seasonal.obj\nOBJECT 0 1 2 3\n"
    pack, _ = _pack(tmp_path, dump=dump)
    assert len(_missing(pack, dump)) == 1
    assert _missing(pack, dump, also=lambda: {"vendor/seasonal.obj"}) == ()


def test_a_case_only_mismatch_is_what_the_volume_says(tmp_path):
    """X-Plane's ``open`` asks the file system; so does the check."""
    dump = "OBJECT_DEF objects/case.obj\nOBJECT 0 1 2 3\n"
    pack, _ = _pack(tmp_path, present=(), dump=dump)
    _write(pack / "objects" / "Case.obj")
    on_disk = os.path.isfile(pack / "objects" / "case.obj")
    assert (_missing(pack, dump) == ()) is on_disk


def test_backslash_paths_read_as_slash(tmp_path):
    dump = "OBJECT_DEF objects\\a.obj\nOBJECT 0 1 2 3\n"
    pack, _ = _pack(tmp_path, dump=dump)
    assert _missing(pack, dump) == ()


def test_no_library_index_says_nothing(tmp_path):
    pack, _ = _pack(tmp_path)
    assert PA.missing_definitions(str(pack), DUMP.splitlines(True), None) is None


def test_a_missing_terrain_def_is_reported_but_not_omittable(tmp_path):
    dump = "TERRAIN_DEF terrain/gone.ter\nBEGIN_PATCH 0 0 -1 1 7\nEND_PATCH\n"
    pack, _ = _pack(tmp_path, dump=dump)
    got = _missing(pack, dump)
    assert [m.kind for m in got] == ["terrain"]
    assert not PA.can_omit(got) and PA.summary(got)["can_omit"] is False
    with pytest.raises(ValueError):
        PA.omit_definitions(dump, got)


def test_the_check_reads_a_dump_path_too(tmp_path):
    pack, dsf = _pack(tmp_path)
    got = PA.missing_definitions(str(pack), str(dsf), {})
    assert {m.path for m in got} == {"objects/gone.obj", "Imagery/miss1.pol",
                                     "Imagery/miss2.pol"}


def test_the_log_line_is_the_owners_wording(tmp_path):
    pack, _ = _pack(tmp_path)
    assert PA.log_line("Some Pack", _missing(pack)) == (
        "[pack] Some Pack: 3 definition(s) the DSF declares are not "
        "installed (1 object, 2 polygon); X-Plane will not load this pack "
        "— first: objects/gone.obj")


# ── THE OMISSION ────────────────────────────────────────────────────────

def _rows(text: str, kw: str) -> list[str]:
    return [r for r in text.splitlines() if r.split(" ", 1)[0] == kw]


def test_the_omission_drops_defs_and_uses_and_renumbers(tmp_path):
    pack, _ = _pack(tmp_path)
    out, counts = PA.omit_definitions(DUMP, _missing(pack))
    assert counts == {"object_defs": 1, "object_uses": 2,
                      "polygon_defs": 2, "polygon_uses": 2}
    assert _rows(out, "OBJECT_DEF") == ["OBJECT_DEF objects/a.obj",
                                        "OBJECT_DEF objects/c.obj"]
    assert _rows(out, "POLYGON_DEF") == ["POLYGON_DEF draped/ok.pol"]
    # every surviving placement: byte-equal but for its index token
    assert _rows(out, "OBJECT") == ["OBJECT 0 51.1 25.1 90.0",
                                    "OBJECT 1 51.5 25.5 0.0"]
    assert _rows(out, "OBJECT_AGL") == ["OBJECT_AGL 1 51.3 25.3 10.0 2.5"]
    assert _rows(out, "OBJECT_MSL") == []
    assert _rows(out, "BEGIN_POLYGON") == ["BEGIN_POLYGON 0 65535 2",
                                           "BEGIN_POLYGON 0 7 2"]
    assert _rows(out, "POLYGON_POINT") == ["POLYGON_POINT 51.2 25.0",
                                           "POLYGON_POINT 51.4 25.0"]
    for a, b in (("BEGIN_POLYGON", "END_POLYGON"),
                 ("BEGIN_WINDING", "END_WINDING")):
        assert len(_rows(out, a)) == len(_rows(out, b))
    for kw in ("PROPERTY", "NETWORK_DEF", "TERRAIN_DEF", "RASTER_DEF",
               "BEGIN_SEGMENT", "SHAPE_POINT", "END_SEGMENT", "BEGIN_PATCH",
               "PATCH_VERTEX"):
        assert _rows(out, kw) == _rows(DUMP, kw)
    # the cleaned text is whole: nothing missing any more
    assert PA.missing_definitions(str(pack), out.splitlines(True), {}) == ()


def test_a_network_omission_drops_the_whole_segment(tmp_path):
    pack, _ = _pack(tmp_path, present=tuple(p for p in ALL
                                            if p != "roads/net.net"))
    missing = _missing(pack)
    assert [m.kind for m in missing] == ["network"]
    out, counts = PA.omit_definitions(DUMP, missing)
    assert counts == {"network_defs": 1, "network_uses": 1}
    assert not _rows(out, "BEGIN_SEGMENT") and not _rows(out, "SHAPE_POINT")
    assert not _rows(out, "END_SEGMENT")
    assert _rows(out, "BEGIN_PATCH") == _rows(DUMP, "BEGIN_PATCH")


def test_a_list_that_does_not_describe_the_text_raises():
    with pytest.raises(ValueError):
        PA.omit_definitions(DUMP, [PA.MissingDef("object", 1, "objects/other.obj")])
    with pytest.raises(ValueError):
        PA.omit_definitions(DUMP, [PA.MissingDef("object", 9, "objects/x.obj")])


def test_nothing_to_omit_is_the_same_text():
    assert PA.omit_definitions(DUMP, ()) == (DUMP, {})


# ── THE DECISION KEY ────────────────────────────────────────────────────

def test_the_key_follows_the_pristine_dsf_and_the_missing_set(tmp_path):
    pack, _ = _pack(tmp_path)
    missing = _missing(pack)
    k = PA.decision_key("aa", missing)
    assert k == PA.decision_key("aa", tuple(reversed(missing)))
    assert k != PA.decision_key("bb", missing)
    assert k != PA.decision_key("aa", missing[:1])
    entry = {"omitted_art": PA.record("aa", missing, {}, "t")}
    assert PA.accepted(entry, "aa", missing)
    assert not PA.accepted(entry, "bb", missing)
    assert not PA.accepted(entry, "aa", missing[:1])
    assert not PA.accepted({}, "aa", missing)


# ── THE WRITE (dsf_write.write_pack(..., omit=)) ────────────────────────

@pytest.fixture
def _memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


def _stand_in_dsftool(tmp_path, monkeypatch):
    """``--dsf2text`` / ``--text2dsf`` as a byte copy."""
    tool = tmp_path / "dsftool.py"
    tool.write_text("import shutil, sys\n"
                    "shutil.copyfile(sys.argv[2], sys.argv[3])\n",
                    encoding="utf-8", newline="")
    real_run = W.subprocess.run

    def fake_run(args, **kw):
        return real_run([sys.executable, str(tool)] + list(args[1:]), **kw)

    monkeypatch.setattr(W.subprocess, "run", fake_run)
    return str(tool)


def _art_plan(pack: Path, dsf: Path) -> PM.PlacementPlan:
    """The omission alone: no ICAO, no edit (``engine_v2._write_art_only``)."""
    return PM.PlacementPlan("", pack.name, str(pack), str(dsf),
                            str(dsf) + PM.BACKUP_SUFFIX,
                            PM.Provenance("", "1.0.test", "", {}))


def _live(dsf: Path) -> str:
    """The live DSF text without the write's own ownership mark."""
    return "".join(r for r in dsf.read_text(encoding="utf-8")
                   .splitlines(True) if not r.startswith("PROPERTY o4/"))


def _entry(dsf: Path) -> dict:
    doc = json.loads((dsf.parent / PM.PROVENANCE_FILENAME)
                     .read_text(encoding="utf-8"))
    return doc["dsfs"][dsf.name]


def test_the_write_omits_records_and_keeps_the_pristine(tmp_path, monkeypatch,
                                                        _memo):
    pack, dsf = _pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    missing = _missing(pack)
    res = W.write_pack(str(pack), _art_plan(pack, dsf), tool,
                       work_dir=str(tmp_path / "w"), omit=missing)
    assert res.omitted == {"object_defs": 1, "object_uses": 2,
                           "polygon_defs": 2, "polygon_uses": 2}
    assert _live(dsf) == PA.omit_definitions(DUMP, missing)[0]
    bak = Path(str(dsf) + PM.BACKUP_SUFFIX)
    assert bak.read_text(encoding="utf-8") == DUMP, "the pristine, untouched"
    entry = _entry(dsf)
    row = entry["omitted_art"]
    assert row["accepted"] is True and row["counts"] == dict(res.omitted)
    assert [d["path"] for d in row["definitions"]] == [m.path for m in missing]
    assert PA.accepted(entry, _sha(bak), missing)
    assert "" not in (entry.get("airports") or {}), "no airport recorded"


def test_a_write_without_omit_restores_the_definitions(tmp_path, monkeypatch,
                                                       _memo):
    pack, dsf = _pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _art_plan(pack, dsf), tool,
                 work_dir=str(tmp_path / "w1"), omit=_missing(pack))
    W.write_pack(str(pack), _art_plan(pack, dsf), tool,
                 work_dir=str(tmp_path / "w2"))
    assert _live(dsf) == DUMP
    assert _entry(dsf)["omitted_art"] is None, "never sticky"
