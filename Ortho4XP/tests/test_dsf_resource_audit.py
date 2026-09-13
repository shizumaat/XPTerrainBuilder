"""Twin for ``tools/dsf_resource_audit.py`` — the object-stage DSF
rewrite's resource regression guard (RULINGS 2026-09-13bl / 13bq).

Everything is built in ``tmp_path``: no network, no X-Plane install, no
DSFTool, no data repo.  The dumps are handed to ``audit_pack`` directly,
which is exactly the seam the CLI uses after it has loaded them.

The two measured traps get their own tests:
  * ``os.path.exists`` is case-INSENSITIVE on APFS — a def spelled
    ``Objects/Case.obj`` against an on-disk ``objects/case.obj`` must
    come out CASE-MISS, not resolved.
  * ``EXPORT_SEASON`` / ``EXPORT_EXCLUDE_SEASON`` / ``EXPORT_RATIO``
    carry one extra token before the virtual path; parsing them as the
    two-token form stranded 678 defs.
"""
import importlib.util
import os
import sys

import pytest

# Loaded by PATH, not by putting ``tools/`` on ``sys.path`` — that
# shadows engine modules for every OTHER test sharing the worker
# (measured 2026-09-13: it turned one test_harness cfg test red).
_TOOL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tools", "dsf_resource_audit.py")
_spec = importlib.util.spec_from_file_location("dsf_resource_audit", _TOOL)
A = importlib.util.module_from_spec(_spec)
# @dataclass resolves its class through sys.modules, so the module must
# be registered before it executes.  This registers ONE unambiguous
# name; it does not put tools/ on the import path.
sys.modules[_spec.name] = A
_spec.loader.exec_module(A)


# ── fixture construction ─────────────────────────────────────────────

def _write(path: str, text: str = "") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


PRISTINE_DUMP = """\
PROPERTY sim/west -4
OBJECT_DEF Objects/a.obj
OBJECT_DEF lib/airport/x.obj
OBJECT_DEF Misc/broken.obj
OBJECT_DEF Objects/Case.obj
POLYGON_DEF lib/pol.pol
OBJECT 0 -3.5 40.4 0.0
OBJECT 0 -3.5 40.4 0.0
OBJECT_MSL 1 -3.5 40.4 12.0
OBJECT 2 -3.5 40.4 0.0
OBJECT_AGL 3 -3.5 40.4 1.0
BEGIN_POLYGON 4 0 2
END_POLYGON
"""

# live = pristine + one new body on disk + one new body missing
#      + `Objects/a.obj` garbled to `Objects/A-garbled.obj`
#      + one placement of `lib/airport/x.obj` dropped with no body to
#        account for it.
LIVE_DUMP = """\
PROPERTY sim/west -4
OBJECT_DEF Objects/A-garbled.obj
OBJECT_DEF lib/airport/x.obj
OBJECT_DEF Misc/broken.obj
OBJECT_DEF Objects/Case.obj
POLYGON_DEF lib/pol.pol
OBJECT_DEF Objects/a__b0.obj
OBJECT_DEF Objects/a__b1.obj
OBJECT 2 -3.5 40.4 0.0
OBJECT_AGL 3 -3.5 40.4 1.0
BEGIN_POLYGON 4 0 2
END_POLYGON
OBJECT 5 -3.5 40.4 0.0
OBJECT 6 -3.5 40.4 0.0
"""

ALL_SEVEN_LIBRARY = """\
# every EXPORT form, including the three carrying an extra token
EXPORT               lib/seven/plain.obj        real/plain.obj
EXPORT_BACKUP        lib/seven/backup.obj       real/backup.obj
EXPORT_EXCLUDE       lib/seven/exclude.obj      real/exclude.obj
EXPORT_EXTEND        lib/seven/extend.obj       real/extend.obj
EXPORT_RATIO   0.25  lib/seven/ratio.obj        real/ratio.obj
EXPORT_SEASON  win   lib/seven/season.obj       real/season.obj
EXPORT_EXCLUDE_SEASON win,spr lib/seven/xseason.obj real/xseason.obj
"""

SEVEN_VPATHS = (
    "lib/seven/plain.obj", "lib/seven/backup.obj", "lib/seven/exclude.obj",
    "lib/seven/extend.obj", "lib/seven/ratio.obj", "lib/seven/season.obj",
    "lib/seven/xseason.obj",
)


@pytest.fixture()
def scenery(tmp_path):
    """A fake Custom Scenery root: one audited pack plus two libraries."""
    cs = tmp_path / "Custom Scenery"
    pack = cs / "TESTPACK Airport"
    end = pack / "Earth nav data" / "+40-010"

    # DSF placeholders (never opened — the dumps are passed in directly).
    _write(str(end / "+40-004.dsf"), "")
    _write(str(end / "+40-004.dsf.anchor_bak"), "")

    # Pack-local resources.
    _write(str(pack / "Objects" / "a.obj"), "OBJ")
    _write(str(pack / "Objects" / "a__b0.obj"), "OBJ")   # body that exists
    # a__b1.obj deliberately NOT written -> OURS-NEW + BODY-MISSING
    _write(str(pack / "objects" / "case.obj"), "OBJ")    # case-only match
    # Misc/broken.obj deliberately absent -> PRISTINE-BROKEN
    _write(str(pack / "Objects" / "z.obj.anchor_bak"), "OBJ")  # ORPHAN

    # A library exporting lib/airport/x.obj and (season form) lib/pol.pol.
    lib = cs / "TESTLIB"
    _write(str(lib / "library.txt"),
           "EXPORT lib/airport/x.obj real/x.obj\n"
           "EXPORT_EXCLUDE_SEASON win,spr lib/pol.pol pol/p.pol\n")
    _write(str(lib / "real" / "x.obj"), "OBJ")
    _write(str(lib / "pol" / "p.pol"), "POL")

    return {"cs": str(cs), "pack": str(pack), "lib": str(lib)}


def _audit(scenery, live_text=LIVE_DUMP, pristine_text=PRISTINE_DUMP):
    index = A.LibraryIndex.from_roots([scenery["cs"]])
    return A.audit_pack(
        scenery["pack"],
        A.parse_dump(live_text.splitlines()),
        A.parse_dump(pristine_text.splitlines()),
        index, tile="+40-004")


# ── the seven export forms (trap 2) ──────────────────────────────────

def test_all_seven_export_forms_parse(tmp_path):
    lib = tmp_path / "Custom Scenery" / "SEVEN"
    _write(str(lib / "library.txt"), ALL_SEVEN_LIBRARY)
    parsed = list(A.parse_library_file(str(lib / "library.txt")))
    assert len(parsed) == 7
    assert {kw for kw, _v, _r in parsed} == set(A.EXPORT_KEYWORDS)
    assert [v for _kw, v, _r in parsed] == list(SEVEN_VPATHS)
    # The season/ratio token must never leak into the real path.
    for _kw, vpath, rpath in parsed:
        assert rpath.startswith("real/"), (vpath, rpath)


def test_all_seven_vpaths_land_in_the_index(tmp_path):
    lib = tmp_path / "Custom Scenery" / "SEVEN"
    _write(str(lib / "library.txt"), ALL_SEVEN_LIBRARY)
    for _kw, _v, rpath in A.parse_library_file(str(lib / "library.txt")):
        _write(str(lib / rpath), "OBJ")
    index = A.LibraryIndex.from_roots([str(tmp_path / "Custom Scenery")])
    assert index.vpath_count == 7
    for vpath in SEVEN_VPATHS:
        assert index.resolve(vpath)[0] == A.LIB, vpath
    # Case-insensitive vpath match is what X-Plane does.
    assert index.resolve("LIB/SEVEN/Season.OBJ")[0] == A.LIB


def test_season_form_export_resolves_the_polygon_def(scenery):
    report = _audit(scenery)
    row = next(r for r in report.rows if r["path"] == "lib/pol.pol")
    assert row["kind"] == "POLYGON_DEF"
    assert row["cls"] == A.OK
    assert row["live_status"] == A.LIB
    assert row["resolved_by"].endswith("TESTLIB/library.txt")


def test_library_export_with_no_real_file_is_dangling(tmp_path):
    lib = tmp_path / "Custom Scenery" / "GHOST"
    _write(str(lib / "library.txt"), "EXPORT lib/ghost.obj real/ghost.obj\n")
    index = A.LibraryIndex.from_roots([str(tmp_path / "Custom Scenery")])
    status, detail = index.resolve("lib/ghost.obj")
    assert status == A.LIB_DANGLING
    assert detail.endswith("real/ghost.obj")


# ── exact case (trap 1) ──────────────────────────────────────────────

def test_pack_relative_is_exact_case_not_os_path_exists(scenery):
    resolver = A.PackResolver(scenery["pack"])
    # os.path.exists lies on a case-insensitive volume; if it does here,
    # this is exactly the trap the segment walk exists to defeat.
    exact, on_disk = resolver.pack_relative("Objects/Case.obj")
    assert exact is False
    # Only the leaf segment differs here: the fixture's ``objects/``
    # write lands inside the existing ``Objects/`` on a case-insensitive
    # volume.  A single wrong segment is a CASE-MISS all the same.
    assert on_disk == "Objects/case.obj"
    exact, on_disk = resolver.pack_relative("Objects/a.obj")
    assert exact is True
    assert on_disk == "Objects/a.obj"
    assert resolver.pack_relative("Objects/nope.obj") == (False, None)


def test_case_only_match_is_reported_as_case_miss(scenery):
    report = _audit(scenery)
    assert report.paths(A.CASE_MISS) == {"Objects/Case.obj"}
    row = next(r for r in report.rows if r["path"] == "Objects/Case.obj")
    assert row["live_status"] == A.PACK_CASE
    assert row["on_disk"] == "Objects/case.obj"


def test_a_directory_is_not_a_resource(scenery):
    resolver = A.PackResolver(scenery["pack"])
    assert resolver.pack_relative("Objects") == (False, None)


# ── the classes ──────────────────────────────────────────────────────

def test_pristine_broken_is_the_packs_defect_not_ours(scenery):
    report = _audit(scenery)
    # ``Objects/Case.obj`` is unresolved in BOTH dumps as well — the
    # pack shipped the wrong spelling — so it is the pack's defect too,
    # flagged CASE-MISS on top (see the case-miss test below).
    assert report.paths(A.PRISTINE_BROKEN) == {"Misc/broken.obj",
                                               "Objects/Case.obj"}
    row = next(r for r in report.rows if r["path"] == "Misc/broken.obj")
    assert row["live_status"] == A.UNRESOLVED
    assert row["pristine_status"] == A.UNRESOLVED
    assert row["live_n"] == row["pristine_n"] == 1


def test_ours_is_the_garbled_path_and_the_dropped_placement(scenery):
    report = _audit(scenery)
    assert report.paths(A.OURS) == {"Objects/a.obj", "lib/airport/x.obj"}
    dropped_def = next(r for r in report.rows if r["path"] == "Objects/a.obj")
    assert dropped_def["sub"] == A.OURS_DROPPED_DEF
    assert dropped_def["live_index"] is None
    dropped_pl = next(r for r in report.rows
                      if r["path"] == "lib/airport/x.obj")
    assert dropped_pl["sub"] == A.OURS_DROPPED_PLACEMENTS
    assert (dropped_pl["pristine_n"], dropped_pl["live_n"]) == (1, 0)
    assert dropped_pl["shortfall"] == 1


def test_a_live_only_path_that_does_not_resolve_is_garbled_not_new(scenery):
    # `Objects/A-garbled.obj` is a live-only, unresolvable def.
    report = _audit(scenery)
    row = next(r for r in report.rows if r["path"] == "Objects/A-garbled.obj")
    assert row["cls"] == A.OURS_NEW


def test_ours_new_and_body_missing_are_the_unwritten_body(scenery):
    report = _audit(scenery)
    assert "Objects/a__b1.obj" in report.paths(A.OURS_NEW)
    assert report.paths(A.BODY_MISSING) == {"Objects/a__b1.obj"}


def test_ok_new_is_the_body_we_did_write(scenery):
    report = _audit(scenery)
    assert report.paths(A.OK_NEW) == {"Objects/a__b0.obj"}
    row = next(r for r in report.rows if r["path"] == "Objects/a__b0.obj")
    assert row["live_status"] == A.PACK
    assert row["body_missing"] is False


def test_split_bodies_credit_their_originals_placements(tmp_path):
    """The lawful split — original goes to 0 placements, its bodies take
    them — must NOT be reported as dropped placements."""
    pack = tmp_path / "P"
    _write(str(pack / "Objects" / "big.obj"), "OBJ")
    _write(str(pack / "Objects" / "big__b0.obj"), "OBJ")
    _write(str(pack / "Objects" / "big__b1.obj"), "OBJ")
    pristine = A.parse_dump([
        "OBJECT_DEF Objects/big.obj", "OBJECT 0 -3 40 0"])
    live = A.parse_dump([
        "OBJECT_DEF Objects/big.obj",
        "OBJECT_DEF Objects/big__b0.obj",
        "OBJECT_DEF Objects/big__b1.obj",
        "OBJECT 1 -3 40 0", "OBJECT 2 -3 40 0"])
    report = A.audit_pack(str(pack), live, pristine, None, tile="t")
    assert report.count(A.OURS) == 0
    assert report.count(A.OK_NEW) == 2
    assert report.failures == 0


def test_orphan_backup_is_a_finding(scenery):
    report = _audit(scenery)
    assert report.orphans == [os.path.join("Objects", "z.obj.anchor_bak")]
    assert report.count(A.ORPHAN) == 1


# ── dump parsing ─────────────────────────────────────────────────────

def test_parse_dump_counts_every_placement_keyword():
    dump = A.parse_dump([
        "OBJECT_DEF o.obj",
        "POLYGON_DEF p.pol",
        "NETWORK_DEF n.net",
        "OBJECT 0 -3 40 0",
        "OBJECT_MSL 0 -3 40 12",
        "OBJECT_AGL 0 -3 40 1",
        "BEGIN_POLYGON 0 0 2",
        "BEGIN_SEGMENT 0 1 1 -3 40 0",
        "BEGIN_SEGMENT_CURVED 0 1 2 -3 40 0",
        "POLYGON_POINT -3 40",
    ])
    assert dump.paths("OBJECT_DEF") == ["o.obj"]
    assert dump.placements("OBJECT_DEF", 0) == 3
    assert dump.placements("POLYGON_DEF", 0) == 1
    assert dump.placements("NETWORK_DEF", 0) == 2


def test_parse_dump_ignores_a_non_numeric_index():
    dump = A.parse_dump(["OBJECT_DEF o.obj", "OBJECT x -3 40 0"])
    assert dump.placements("OBJECT_DEF", 0) == 0


# ── verdict and CLI ──────────────────────────────────────────────────

def test_verdict_is_defect_on_the_dirty_fixture(scenery):
    report = _audit(scenery)
    verdict, code = A.verdict_line([report])
    assert code == 1
    assert verdict.startswith("VERDICT: DEFECT (")
    assert "OURS 2" in verdict
    assert "PRISTINE-BROKEN" not in verdict


def test_verdict_is_clean_when_only_the_pack_is_broken(tmp_path):
    """A clean variant: nothing but a PRISTINE-BROKEN def and a lawful
    new body — the OTHH shape (RULINGS 13bq)."""
    pack = tmp_path / "CLEANPACK"
    _write(str(pack / "Objects" / "a.obj"), "OBJ")
    _write(str(pack / "Objects" / "a__b0.obj"), "OBJ")
    text = ["OBJECT_DEF Objects/a.obj", "OBJECT_DEF Jetway/gone.obj",
            "OBJECT 0 -3 40 0", "OBJECT 1 -3 40 0"]
    pristine = A.parse_dump(text)
    live = A.parse_dump(text + ["OBJECT_DEF Objects/a__b0.obj"])
    report = A.audit_pack(str(pack), live, pristine, None, tile="t")
    assert report.count(A.PRISTINE_BROKEN) == 1
    assert report.placements(A.PRISTINE_BROKEN) == 1
    assert report.failures == 0
    verdict, code = A.verdict_line([report])
    assert (verdict, code) == ("VERDICT: CLEAN", 0)


def test_summary_line_names_every_class(scenery):
    line = A.summary_line(_audit(scenery))
    for token in ("PRISTINE-BROKEN", "OURS", "OURS-NEW", "OK-NEW",
                  "CASE-MISS", "ORPHAN", "BODY-MISSING"):
        assert token in line


def test_render_hides_ok_rows_until_verbose(scenery):
    report = _audit(scenery)
    quiet = "\n".join(A.render([report]))
    loud = "\n".join(A.render([report], verbose=True))
    assert "Objects/a__b0.obj" not in quiet      # OK-NEW
    assert "Objects/a__b0.obj" in loud
    assert "Misc/broken.obj" in quiet            # never hidden


def test_cli_end_to_end_exits_1_and_writes_json(scenery, tmp_path,
                                                monkeypatch, capsys):
    """Drive ``main`` over the fixture root with the dump lookup
    monkeypatched — no DSFTool, no data repo."""
    dumps = {"+40-004.dsf": LIVE_DUMP, "+40-004.dsf.anchor_bak": PRISTINE_DUMP}

    def fake_load(dsf_path, scratch_dir, cache_only=False):
        return A.parse_dump(dumps[os.path.basename(dsf_path)].splitlines()), \
            "fixture"

    monkeypatch.setattr(A, "load_dump", fake_load)
    out_json = tmp_path / "rows.json"
    code = A.main(["--custom-scenery", scenery["cs"],
                   "--json", str(out_json)])
    captured = capsys.readouterr().out
    assert code == 1
    assert "VERDICT: DEFECT (" in captured
    assert "PACK TESTPACK Airport" in captured
    assert "libraries: 1 library.txt, 2 virtual paths" in captured
    assert out_json.is_file()
    import json
    rows = json.loads(out_json.read_text())["packs"][0]["rows"]
    assert {r["path"] for r in rows if r["cls"] == A.OURS} == {
        "Objects/a.obj", "lib/airport/x.obj"}


def test_cli_refuses_with_no_packs(capsys):
    assert A.main([]) == 2
    assert "no packs" in capsys.readouterr().err


def test_cache_only_never_runs_dsftool(scenery, monkeypatch):
    """A cache miss under ``--cache-only`` reports missing rather than
    shelling out."""
    def boom(*_a, **_k):  # pragma: no cover - must never be called
        raise AssertionError("DSFTool must not run under --cache-only")

    monkeypatch.setattr(A, "dsftool_dump", boom)
    monkeypatch.setattr(A, "cached_dump_path", lambda _p: None)
    dump, prov = A.load_dump("/nowhere/+40-004.dsf", "/tmp", cache_only=True)
    assert (dump, prov) == (None, "missing")


# ── discovery ────────────────────────────────────────────────────────

def test_discovery_finds_the_pack_and_its_tile_pair(scenery):
    packs = A.discover_packs(scenery["cs"])
    assert packs == [scenery["pack"]]
    pairs = A.find_tile_pairs(scenery["pack"])
    assert len(pairs) == 1
    live, pristine = pairs[0]
    assert live.endswith("+40-004.dsf")
    assert pristine == live + ".anchor_bak"


def test_pack_root_resolves_both_shipped_layouts(tmp_path):
    grouped = tmp_path / "G" / "Earth nav data" / "+40-010" / "+40-004.dsf"
    flat = tmp_path / "F" / "Earth nav data" / "+40-004.dsf"
    for p in (grouped, flat):
        _write(str(p), "")
    assert A.pack_root_for_dsf(str(grouped)) == str(tmp_path / "G")
    assert A.pack_root_for_dsf(str(flat)) == str(tmp_path / "F")
    assert A.pack_root_for_dsf(str(tmp_path / "bare.dsf")) is None


def test_flat_layout_pack_is_discovered(tmp_path):
    cs = tmp_path / "Custom Scenery"
    pack = cs / "FLAT"
    _write(str(pack / "Earth nav data" / "+40-004.dsf"), "")
    _write(str(pack / "Earth nav data" / "+40-004.dsf.anchor_bak"), "")
    assert A.discover_packs(str(cs)) == [str(pack)]


def test_a_backup_with_no_live_dsf_is_not_a_pair(tmp_path):
    pack = tmp_path / "P"
    _write(str(pack / "Earth nav data" / "+40-004.dsf.anchor_bak"), "")
    assert A.find_tile_pairs(str(pack)) == []


def _fake_dsf_reader(monkeypatch, cache_dir, tag="deadbeef"):
    """Stand in for ``auto_patch.dsf_reader`` so the cache lookup can be
    exercised with no engine import and no data repo."""
    import types
    reader = types.ModuleType("auto_patch.dsf_reader")
    reader.airport_mod_cache_dir = lambda _root: cache_dir
    reader.dsf_content_tag = lambda _p: tag
    reader._default_pack_text_cache_path = lambda cd, p: os.path.join(
        cd, f"{os.path.basename(p)}.{tag}.text")
    monkeypatch.setattr(A, "_dsf_reader", lambda: reader)


def test_cached_dump_path_reads_the_content_keyed_dump(tmp_path, monkeypatch):
    pack = tmp_path / "P"
    dsf = pack / "Earth nav data" / "+40-010" / "+40-004.dsf"
    _write(str(dsf), "")
    cache = tmp_path / "Airport_mod_cache" / "P"
    _fake_dsf_reader(monkeypatch, str(cache))
    assert A.cached_dump_path(str(dsf)) is None
    hit = _write(str(cache / "+40-004.dsf.deadbeef.text"), "OBJECT_DEF a.obj")
    assert A.cached_dump_path(str(dsf)) == hit


def test_pristine_dump_is_found_under_the_live_basename_alias(tmp_path,
                                                              monkeypatch):
    """VHHH 2026-09-13: a pristine ``.dsf.anchor_bak`` whose dump was
    taken before the rewrite is filed under the LIVE basename with the
    same content tag.  Same bytes, same dump — accept it."""
    pack = tmp_path / "P"
    bak = pack / "Earth nav data" / "+20+110" / "+22+113.dsf.anchor_bak"
    _write(str(bak), "")
    cache = tmp_path / "Airport_mod_cache" / "P"
    _fake_dsf_reader(monkeypatch, str(cache))
    assert A.cached_dump_path(str(bak)) is None
    alias = _write(str(cache / "+22+113.dsf.deadbeef.text"), "OBJECT_DEF a.obj")
    assert A.cached_dump_path(str(bak)) == alias
    # The exact name still wins when both exist.
    exact = _write(str(cache / "+22+113.dsf.anchor_bak.deadbeef.text"), "")
    assert A.cached_dump_path(str(bak)) == exact


def test_a_different_content_tag_is_not_an_alias_hit(tmp_path, monkeypatch):
    pack = tmp_path / "P"
    bak = pack / "Earth nav data" / "+20+110" / "+22+113.dsf.anchor_bak"
    _write(str(bak), "")
    cache = tmp_path / "Airport_mod_cache" / "P"
    _fake_dsf_reader(monkeypatch, str(cache), tag="deadbeef")
    _write(str(cache / "+22+113.dsf.0badc0de.text"), "OBJECT_DEF a.obj")
    assert A.cached_dump_path(str(bak)) is None


def test_cached_dump_path_never_calls_ensure_dsf_text_path(monkeypatch):
    """The write-free contract, asserted structurally: the module must
    not name the writing helper at all."""
    source = open(A.__file__, encoding="utf-8").read()
    assert "ensure_dsf_text_path(" not in source
    assert "_default_pack_text_cache_path(" in source
