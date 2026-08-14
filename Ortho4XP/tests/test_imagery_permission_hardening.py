"""Imagery is never deleted on an error that does not prove corruption.

Reference incident (2026-08-12): the app ran while a macOS TCC
volume-access dialog was killed unanswered; in the permission-denied
window the engine treated healthy orthophotos as missing, failed to
re-fetch them, and the cleanup path deleted the KCLT imagery.

Per site, three twins:
  (a) a PermissionError during the read leaves the artifact intact and
      says so loudly;
  (b) genuinely bad readable bytes (the white-squared file the engine
      itself wrote) still trigger the existing cleanup;
  (c) the re-run with permission restored finds the preserved artifact
      byte-for-byte and does not re-download it.

Headless: tmp_path only, no network, no X-Plane install.  Reads are made
to fail by monkeypatching ``os.stat`` / ``Image.save`` rather than by
chmod, so the test is deterministic and root-proof.
"""
from __future__ import annotations

import errno
import io
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import O4_Imagery_Utils as IMG  # noqa: E402
import O4_Tile_Utils as TILE  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

TIL_X, TIL_Y, ZL, PROVIDER = 18720, 8144, 16, "TEST"
ATTRS = (TIL_X, TIL_Y, ZL, PROVIDER)


class _StubTile:
    def __init__(self, build_dir: str) -> None:
        self.lat, self.lon = 35, -81      # KCLT's tile
        self.mask_zl = 14
        self.build_dir = build_dir


def _tiny_jpeg(path, colour=(3, 5, 7)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (8, 8), colour).save(path)
    return path


@pytest.fixture
def imagery(tmp_path, monkeypatch):
    """A tile whose orthophoto for ATTRS already exists on disk."""
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "Orthophotos"))
    monkeypatch.setitem(
        IMG.providers_dict,
        PROVIDER,
        {"code": PROVIDER, "imagery_dir": "normal", "color_filters": "none"},
    )
    monkeypatch.setattr(IMG, "incomplete_imgs", {})
    # raising=False so the twins still EXECUTE against a pre-hardening
    # tree (where the registry does not exist) and fail on behaviour.
    monkeypatch.setattr(IMG, "incomplete_img_paths", {}, raising=False)
    monkeypatch.setattr(UI, "red_flag", 0)
    tile = _StubTile(str(tmp_path / "pack"))
    file_name = FNAMES.jpeg_file_name_from_attributes(*ATTRS)
    file_dir = FNAMES.jpeg_file_dir_from_attributes(
        tile.lat, tile.lon, ZL, IMG.providers_dict[PROVIDER]
    )
    path = _tiny_jpeg(os.path.join(file_dir, file_name))
    return tile, file_dir, file_name, path


def _deny_stat(monkeypatch, denied_path):
    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        if str(path) == str(denied_path):
            raise PermissionError(errno.EACCES, "Operation not permitted")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", fake_stat)


def _white_filled_download(monkeypatch):
    """Make the fetch fail (white squares) but let the save succeed."""
    monkeypatch.setattr(
        IMG,
        "build_texture_from_tilbox",
        lambda *a, **k: (0, Image.new("RGB", (64, 64), "white")),
    )
    monkeypatch.setattr(
        IMG,
        "build_texture_from_bbox_and_size",
        lambda *a, **k: (0, Image.new("RGB", (64, 64), "white")),
    )


# ---------------------------------------------------------------------------
# artifact_state: the third answer os.path.isfile cannot give
# ---------------------------------------------------------------------------
def test_artifact_state_distinguishes_absent_from_unreadable(
    tmp_path, monkeypatch
):
    present = _tiny_jpeg(str(tmp_path / "a.jpg"))
    assert IMG.artifact_state(present) == "present"
    assert IMG.artifact_state(str(tmp_path / "gone.jpg")) == "absent"
    _deny_stat(monkeypatch, present)
    assert IMG.artifact_state(present) == "unreadable"
    # The pre-hardening probe collapses the two — this is the amplifier.
    assert os.path.isfile(present) is False


# ---------------------------------------------------------------------------
# S1/S2 twin (a): a denied read/write never queues a deletion
# ---------------------------------------------------------------------------
def test_unreadable_orthophoto_is_not_redownloaded(imagery, monkeypatch):
    tile, _, _, path = imagery
    before = open(path, "rb").read()
    _deny_stat(monkeypatch, path)

    def _must_not_download(*a, **k):
        raise AssertionError("re-downloaded over an unreadable orthophoto")

    monkeypatch.setattr(IMG, "download_jpeg_ortho", _must_not_download)
    assert IMG.build_jpeg_ortho(tile, *ATTRS) == 0
    assert open(path, "rb").read() == before


def test_denied_save_registers_nothing_and_keeps_the_file(
    imagery, monkeypatch
):
    tile, file_dir, file_name, path = imagery
    before = open(path, "rb").read()
    _white_filled_download(monkeypatch)
    monkeypatch.setattr(
        Image.Image,
        "save",
        lambda self, *a, **k: (_ for _ in ()).throw(
            PermissionError(errno.EACCES, "Operation not permitted")
        ),
    )
    assert (
        IMG.download_jpeg_ortho(file_dir, file_name, *ATTRS) == 0
    )
    # Named in the warning list, but NOT in the deletable set.
    assert file_name in IMG.incomplete_imgs["+35-081"]
    assert IMG.incomplete_img_paths == {}

    TILE.delete_incomplete_imgs(tile)
    assert os.path.isfile(path)
    assert open(path, "rb").read() == before


def test_delete_refuses_when_the_removal_itself_is_denied(
    imagery, monkeypatch
):
    tile, _, file_name, path = imagery
    IMG.incomplete_imgs["+35-081"] = [file_name]
    IMG.incomplete_img_paths["+35-081"] = {file_name: path}
    monkeypatch.setattr(
        os,
        "remove",
        lambda p: (_ for _ in ()).throw(
            PermissionError(errno.EPERM, "Operation not permitted")
        ),
    )
    TILE.delete_incomplete_imgs(tile)      # must not raise
    assert os.path.isfile(path)


# ---------------------------------------------------------------------------
# S1 twin (b): a white-squared file the engine WROTE is still cleaned up
# ---------------------------------------------------------------------------
def test_white_squared_file_written_by_this_run_is_deleted(
    imagery, monkeypatch
):
    tile, file_dir, file_name, path = imagery
    _white_filled_download(monkeypatch)
    assert IMG.download_jpeg_ortho(file_dir, file_name, *ATTRS) == 1
    assert IMG.incomplete_img_paths["+35-081"][file_name] == path

    dds_dir = os.path.join(tile.build_dir, "textures")
    os.makedirs(dds_dir)
    dds = os.path.join(dds_dir, os.path.splitext(file_name)[0] + ".dds")
    with open(dds, "wb") as handle:
        handle.write(b"DDS ")

    TILE.delete_incomplete_imgs(tile)
    assert not os.path.exists(path)
    assert not os.path.exists(dds)
    assert IMG.incomplete_imgs == {} and IMG.incomplete_img_paths == {}


def test_corrupt_readable_bytes_are_still_removable(tmp_path):
    """Deletion stays lawful where the bytes were read and proved bad."""
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image at all")
    with pytest.raises(Exception):
        Image.open(io.BytesIO(bad.read_bytes()))
    assert IMG.remove_imagery_artifact(str(bad), "failed decode") is True
    assert not bad.exists()


# ---------------------------------------------------------------------------
# S1 twin (c): the re-run with permission restored finds it intact
# ---------------------------------------------------------------------------
def test_restored_permission_rerun_reuses_the_preserved_artifact(
    imagery, monkeypatch
):
    tile, file_dir, file_name, path = imagery
    before = open(path, "rb").read()

    # Arm 1: the permission-denied window.
    _white_filled_download(monkeypatch)
    monkeypatch.setattr(
        Image.Image,
        "save",
        lambda self, *a, **k: (_ for _ in ()).throw(
            PermissionError(errno.EACCES, "Operation not permitted")
        ),
    )
    assert IMG.download_jpeg_ortho(file_dir, file_name, *ATTRS) == 0
    TILE.delete_incomplete_imgs(tile)

    # Arm 2: permission restored (the stat succeeds again), nothing else
    # changed — the preserved orthophoto is found and reused.
    monkeypatch.setattr(
        IMG,
        "download_jpeg_ortho",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("re-downloaded a preserved orthophoto")
        ),
    )
    assert IMG.build_jpeg_ortho(tile, *ATTRS) == 1
    assert open(path, "rb").read() == before
