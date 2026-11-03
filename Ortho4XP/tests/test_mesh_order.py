"""Twins for O4_Mesh_Order and O4_DSF_Header on a synthetic Custom Scenery.

The defect (#1729): an airport's own mesh pack, listed ABOVE our tile in
``scenery_packs.ini``, shipped a base-mesh DSF for the same tile; X-Plane
draws the first base mesh it meets, so the owner saw that pack's ground and
none of ours.  The reverse holds as well: the Mac app's ini tidy-up files a
newly installed mesh pack below our ortho tiles, so our tile hides it.
"""

from __future__ import annotations

import lzma
import os
import struct
from unittest import mock

import O4_DSF_Header as HEADER
import O4_Mesh_Order as MESH
import O4_Tile_Failures as FAIL

LAT, LON = 39, -77
REL = os.path.join("Earth nav data", "+30-080", "+39-077.dsf")


def _dsf_bytes(overlay: bool) -> bytes:
    """A minimal raw DSF: HEAD{PROP} then the MD5 footer."""
    strings = b"sim/west\0-77\0" + (b"sim/overlay\0" + b"1\0" if overlay
                                     else b"")
    prop = struct.pack("<4sI", b"PORP", 8 + len(strings)) + strings
    head = struct.pack("<4sI", b"DAEH", 8 + len(prop)) + prop
    return b"XPLNEDSF" + struct.pack("<i", 1) + head + b"\0" * 16


def _seven_zip(payload: bytes) -> bytes:
    """A 7z-shaped file: signature header + a raw LZMA stream + a dummy
    end header — what the reader reads of a real one."""
    packed = lzma.compress(payload, format=lzma.FORMAT_RAW, filters=[
        {"id": lzma.FILTER_LZMA1, "lc": 3, "lp": 0, "pb": 2,
         "dict_size": 1 << 16}])
    sig = (b"7z\xbc\xaf\x27\x1c" + b"\0\x04" + b"\0" * 4
           + struct.pack("<QQI", len(packed), 3, 0))
    return sig + packed + b"\x01\x04\x00"


def _pack(csd, name, overlay=None, tiles=((LAT, LON),), compress=False):
    root = csd / name
    root.mkdir()
    for (lat, lon) in tiles:
        rel = os.path.join("Earth nav data", "+30-080",
                           "%+03d%+04d.dsf" % (lat, lon))
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _dsf_bytes(bool(overlay))
        path.write_bytes(_seven_zip(data) if compress else data)
    return root


def _ini(csd, *rows):
    (csd / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n" + "".join(
            "%s Custom Scenery/%s/\n" % (
                "SCENERY_PACK_DISABLED" if name.startswith("!")
                else "SCENERY_PACK", name.lstrip("!")) for name in rows),
        encoding="utf-8", newline="")


def _install(tmp_path):
    """Custom Scenery holding our tile's folder (no link: Windows CI)."""
    csd = tmp_path / "Custom Scenery"
    build = csd / "zOrtho4XP_+39-077"
    (build / REL).parent.mkdir(parents=True)
    (build / REL).write_bytes(_dsf_bytes(False))
    return csd, str(build)


def test_header_reads_raw_and_seven_zip_dsfs(tmp_path):
    for compress in (False, True):
        for overlay in (False, True):
            path = tmp_path / ("%s%s.dsf" % (compress, overlay))
            data = _dsf_bytes(overlay)
            path.write_bytes(_seven_zip(data) if compress else data)
            assert HEADER.dsf_is_overlay(str(path)) is overlay
    junk = tmp_path / "junk.dsf"
    junk.write_bytes(b"not a dsf at all")
    assert HEADER.dsf_is_overlay(str(junk)) is None
    assert HEADER.dsf_is_overlay(str(tmp_path / "absent.dsf")) is None


def test_a_mesh_above_our_tile_hides_it(tmp_path):
    csd, build = _install(tmp_path)
    _pack(csd, "Airport Mesh", compress=True)
    _pack(csd, "Airport Overlay", overlay=True)
    _ini(csd, "Airport Overlay", "Airport Mesh", "zOrtho4XP_+39-077")
    reply = MESH.tile_mesh_order(str(csd), LAT, LON, build)
    assert reply["checked"] is True
    assert reply["hidden_by"] == ["Airport Mesh"] and reply["hides"] == []
    kinds = [kind for kind, _line, _detail in MESH.warning_lines(reply)]
    assert kinds == ["hidden_by"]
    assert MESH.warning_lines(reply)[0][1] == (
        "Hidden in X-Plane by “Airport Mesh”")


def test_a_local_mesh_below_our_tile_is_hidden_not_a_regional_or_ortho(
        tmp_path):
    csd, build = _install(tmp_path)
    _pack(csd, "Airport Mesh")
    _pack(csd, "Regional Mesh",
          tiles=[(LAT, LON)] + [(LAT, LON - i) for i in range(1, 6)])
    ortho = _pack(csd, "One Tile Ortho")
    (ortho / "terrain").mkdir()
    (ortho / "textures").mkdir()
    for i in range(20):
        (ortho / "terrain" / ("%d.ter" % i)).write_text(
            "A", encoding="utf-8", newline="")
        (ortho / "textures" / ("%d.dds" % i)).write_bytes(b"DDS ")
    _ini(csd, "zOrtho4XP_+39-077", "Airport Mesh", "Regional Mesh",
         "One Tile Ortho")
    reply = MESH.tile_mesh_order(str(csd), LAT, LON, build)
    assert reply["hidden_by"] == [] and reply["hides"] == ["Airport Mesh"]


def test_disabled_and_unlisted_packs_follow_x_plane(tmp_path):
    csd, build = _install(tmp_path)
    _pack(csd, "Disabled Mesh")
    _pack(csd, "New Mesh")                 # unlisted: X-Plane puts it on top
    _ini(csd, "!Disabled Mesh", "zOrtho4XP_+39-077")
    reply = MESH.tile_mesh_order(str(csd), LAT, LON, build)
    assert reply["hidden_by"] == ["New Mesh"]
    _ini(csd, "New Mesh", "!zOrtho4XP_+39-077")
    assert MESH.tile_mesh_order(str(csd), LAT, LON, build)["checked"] is False
    assert MESH.tile_mesh_order("", LAT, LON, build)["checked"] is False


def test_apply_moves_our_tile_or_disables_the_pack(tmp_path):
    csd, build = _install(tmp_path)
    _pack(csd, "Airport Mesh")
    _ini(csd, "Other", "Airport Mesh", "Library", "zOrtho4XP_+39-077")
    ini = csd / "scenery_packs.ini"
    reply = MESH.apply_mesh_order(str(csd), LAT, LON, build, "raise",
                                  "Airport Mesh")
    assert reply["hidden_by"] == [] and reply["hides"] == ["Airport Mesh"]
    rows = ini.read_text(encoding="utf-8").splitlines()[4:]
    assert rows[1:3] == ["SCENERY_PACK Custom Scenery/zOrtho4XP_+39-077/",
                         "SCENERY_PACK Custom Scenery/Airport Mesh/"]
    reply = MESH.apply_mesh_order(str(csd), LAT, LON, build, "lower",
                                  "Airport Mesh")
    assert reply["hidden_by"] == ["Airport Mesh"]
    rows = ini.read_text(encoding="utf-8").splitlines()[4:]
    assert rows[1:3] == ["SCENERY_PACK Custom Scenery/Airport Mesh/",
                         "SCENERY_PACK Custom Scenery/zOrtho4XP_+39-077/"]
    reply = MESH.apply_mesh_order(str(csd), LAT, LON, build, "disable",
                                  "Airport Mesh")
    assert reply["hidden_by"] == [] and reply["hides"] == []
    assert ("SCENERY_PACK_DISABLED Custom Scenery/Airport Mesh/"
            in ini.read_text(encoding="utf-8"))


def test_apply_keeps_windows_line_endings_and_refuses_unlisted(tmp_path):
    csd, build = _install(tmp_path)
    _pack(csd, "Airport Mesh")
    ini = csd / "scenery_packs.ini"
    ini.write_bytes(b"I\r\n1000 Version\r\nSCENERY\r\n\r\n"
                    b"SCENERY_PACK Custom Scenery/Airport Mesh/\r\n"
                    b"SCENERY_PACK Custom Scenery/zOrtho4XP_+39-077/\r\n")
    MESH.apply_mesh_order(str(csd), LAT, LON, build, "raise", "Airport Mesh")
    assert ini.read_bytes().endswith(
        b"SCENERY_PACK Custom Scenery/zOrtho4XP_+39-077/\r\n"
        b"SCENERY_PACK Custom Scenery/Airport Mesh/\r\n")
    for action, pack in (("raise", "Nowhere"), ("bogus", "Airport Mesh")):
        try:
            MESH.apply_mesh_order(str(csd), LAT, LON, build, action, pack)
        except ValueError:
            continue
        raise AssertionError(action)


def test_build_end_rows_become_warnings_naming_the_pack(tmp_path):
    csd, build = _install(tmp_path)
    _pack(csd, "Airport Mesh")
    _ini(csd, "Airport Mesh", "zOrtho4XP_+39-077")
    rows = MESH.degraded_rows(str(csd), LAT, LON, build)
    assert rows == [{"code": "scenery_hidden_by_mesh",
                     "pack": "Airport Mesh"}]
    warnings = FAIL.fold(FAIL.from_degraded(rows), "+39-077", built=True)
    assert warnings[0]["severity"] == "degraded"
    assert "“Airport Mesh” draws its own ground" in warnings[0]["what"]
    with mock.patch.object(MESH, "tile_mesh_order", side_effect=OSError):
        assert MESH.degraded_rows(str(csd), LAT, LON, build) == []


def test_the_engine_answers_both_commands(tmp_path):
    from o4_engine import jsonl
    handlers = jsonl._build_handlers(mock.MagicMock())
    assert handlers["tile_mesh_order"] is MESH.tile_mesh_order
    assert handlers["apply_mesh_order"] is MESH.apply_mesh_order
