"""Every text read/write in the SUITE names its encoding, every text write
its newline (#92, RULINGS 17g).

On Windows the default text encoding is cp1252 and the default write
newline is CRLF.  Before #92 ~110 twins read UTF-8 sources/fixtures with a
bare ``read_text()`` / ``open()`` and died on ``UnicodeDecodeError:
'charmap'``, and fixtures written with a bare ``write_text()`` came back as
CRLF bytes.  macOS and Linux default to UTF-8/LF, so a new bare call is
green everywhere the author runs it — this twin makes it red there too.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def _const_mode(call: ast.Call):
    mode = None
    if len(call.args) >= 2:
        m = call.args[1]
        if not (isinstance(m, ast.Constant) and isinstance(m.value, str)):
            return False            # computed mode: not judged here
        mode = m.value
    for k in call.keywords:
        if k.arg == "mode":
            if not (isinstance(k.value, ast.Constant)
                    and isinstance(k.value.value, str)):
                return False
            mode = k.value.value
    return mode or "r"


def _offences(tree: ast.AST):
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        kws = {k.arg for k in n.keywords}
        if None in kws:             # **kwargs: not judged here
            continue
        f = n.func
        if isinstance(f, ast.Name) and f.id == "open":
            mode = _const_mode(n)
            if mode is False or "b" in mode or len(n.args) > 3:
                continue
            if not n.args and "file" not in kws:
                continue
            if "encoding" not in kws:
                yield n.lineno, "open() without encoding="
            elif any(c in mode for c in "wax+") and "newline" not in kws:
                yield n.lineno, "text-mode open() for write without newline="
        elif isinstance(f, ast.Attribute) and f.attr == "read_text":
            if not n.args and "encoding" not in kws:
                yield n.lineno, "read_text() without encoding="
        elif isinstance(f, ast.Attribute) and f.attr == "write_text":
            if len(n.args) == 1 and not {"encoding", "newline"} <= kws:
                yield n.lineno, "write_text() without encoding= and newline="


def test_suite_text_io_names_encoding_and_newline():
    bad = []
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        bad += [f"{path.relative_to(TESTS).as_posix()}:{line}: {what}"
                for line, what in _offences(tree)]
    assert not bad, ("text I/O that is cp1252/CRLF on Windows (#92):\n  "
                     + "\n  ".join(bad[:40]))


# -- the engine (#539) ---------------------------------------------------
#
# The same scan over src and the two entry files, as a RATCHET: the
# count of text opens that name no encoding may fall, never rise.  It
# started at 134 (2026-10-10); every read of a file that ships with the
# app or that a user or a third party supplies was named then.  What is
# recorded below is files the engine writes and reads back itself: JSON
# written by json.dump (ASCII on disk, ensure_ascii is never
# turned off in src) and numeric mesh text.  A NEW text open names its
# encoding -- O4_Text_Files says which one.

ENGINE = TESTS.parent
ENGINE_SOURCES = ("src", "Ortho4XP.py", "Ortho4XP_Qt.py")
NOT_SHIPPED = "src/Unused/"

RECORDED_UNNAMED = {
    "src/O4_Airport_Elevation_Insets.py": 18,
    "src/O4_Bathymetry_Band.py": 3,
    "src/O4_Coral_Atlas.py": 2,
    "src/O4_Elevation_Level.py": 5,
    "src/O4_LERC_Decode.py": 1,
    "src/O4_Mask_Utils.py": 2,
    "src/O4_Mesh_Utils.py": 5,
    "src/O4_OSM_Extracts.py": 3,
    "src/O4_Parallel_Utils.py": 1,
    "src/O4_Qt_GUI.py": 4,
    "src/O4_Tile_Utils.py": 2,
    "src/O4_Vector_Utils.py": 2,
    "src/auto_patch/mesh_sampler.py": 1,
    "src/auto_patch/object_rebake.py": 3,
    "src/auto_patch/object_stage.py": 1,
    "src/auto_patch/post_mesh.py": 1,
    "src/auto_patch_v2/airport/dem.py": 1,
    "src/auto_patch_v2/airport/dem_production.py": 1,
    "src/elevation_access/strategies/arcgis_feature_tiles.py": 4,
    "src/elevation_access/strategies/coordinate_named_url_list.py": 2,
    "src/elevation_access/strategies/geojson_tile_index.py": 2,
    "src/elevation_access/strategies/las_tile_index.py": 2,
    "src/elevation_access/strategies/os_grid_bucket.py": 2,
    "src/elevation_access/strategies/static_stac.py": 3,
    "src/elevation_access/strategies/tile_grid_http.py": 2,
    "src/elevation_access/strategies/xyz_archive_drop.py": 2,
    "src/o4_engine/tile_time_model.py": 3,
}


def _engine_offences():
    found = {}
    for root in ENGINE_SOURCES:
        root = ENGINE / root
        for path in sorted(root.rglob("*.py")) if root.is_dir() else [root]:
            name = path.relative_to(ENGINE).as_posix()
            if name.startswith(NOT_SHIPPED):
                continue
            count = sum(1 for _ in _offences(
                ast.parse(path.read_text(encoding="utf-8"), str(path))))
            if count:
                found[name] = count
    return found


def test_engine_text_io_without_an_encoding_never_grows():
    found = _engine_offences()
    grown = ["%s: %d, recorded %d" % (name, count,
                                       RECORDED_UNNAMED.get(name, 0))
             for (name, count) in sorted(found.items())
             if count > RECORDED_UNNAMED.get(name, 0)]
    assert not grown, (
        "a text open/read_text/write_text that names no encoding= (or a "
        "text write with no newline=) is the ANSI code page on Windows "
        "(#539); name it -- see src/O4_Text_Files.py:\n  "
        + "\n  ".join(grown))


def test_the_recorded_count_is_the_measured_one():
    # A fall is recorded in the same commit, so the next rise is caught.
    assert _engine_offences() == RECORDED_UNNAMED
