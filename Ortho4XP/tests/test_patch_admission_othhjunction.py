"""Issues #13 / #15 (lane ``othhjunction``): ONE admission test for the
auto patches a tile's mesh carries, shared by the patch ingest and the
post-mesh object stage.

MEASURED (build 350, 2026-09-18, ``+25+051``): a JOSM-saved manual
``OTHH.patch.osm`` replaced ``OTHH_auto.patch.osm`` in the mesh ("Skipping
auto-patch ... (manual patch exists)" at verbosity 1 only), yet the object
stage still placed the 08:15 ``o4_v2_rebake_OTHH.json`` plan — 726 bodies
split into 2,222 files, the pack DSF rewritten — against the AUTO patch's
design surface, which the mesh did not have.
"""

import types

import pytest

import O4_Vector_Map as VMAP
from auto_patch import engine_v2
from auto_patch import post_mesh
from auto_patch_v2.model import rebake as _rb
import O4_File_Names as FNAMES


class _Tile:
    def __init__(self, build_dir="", lat=25, lon=51, mode="ICAO"):
        self.build_dir = build_dir
        self.lat = lat
        self.lon = lon
        self.auto_patch = mode
        self.modify_custom_airports = True


def _touch(p, text="<osm/>"):
    p.write_text(text)
    return p


def test_auto_patch_alone_is_applied(tmp_path):
    _touch(tmp_path / "OTHH_auto.patch.osm")
    assert VMAP.auto_patch_not_applied(_Tile(), "OTHH", str(tmp_path)) is None


def test_a_manual_patch_overrides_and_is_named(tmp_path):
    _touch(tmp_path / "OTHH_auto.patch.osm")
    _touch(tmp_path / "OTHH.patch.osm")
    why = VMAP.auto_patch_not_applied(_Tile(), "othh", str(tmp_path))
    assert why is not None and "OTHH.patch.osm" in why
    # the prefix rule is include_patches's: OTHH_mine.patch.osm covers it too
    (tmp_path / "OTHH.patch.osm").unlink()
    _touch(tmp_path / "OTHH_mine.patch.osm")
    assert "OTHH_mine.patch.osm" in VMAP.auto_patch_not_applied(
        _Tile(), "OTHH", str(tmp_path))
    # another airport's manual patch does not
    (tmp_path / "OTHH_mine.patch.osm").unlink()
    _touch(tmp_path / "OTBD.patch.osm")
    assert VMAP.auto_patch_not_applied(_Tile(), "OTHH", str(tmp_path)) is None


def test_missing_file_and_mode_filter(tmp_path):
    assert "no OTHH_auto.patch.osm" in VMAP.auto_patch_not_applied(
        _Tile(), "OTHH", str(tmp_path))
    _touch(tmp_path / "OTHH_auto.patch.osm")
    assert VMAP.auto_patch_not_applied(
        _Tile(mode="None"), "OTHH", str(tmp_path)) == "auto_patch=None"


def test_boundary_skip(tmp_path):
    _touch(tmp_path / "OTHH_auto.patch.osm")
    tile = _Tile()
    tile.auto_patch_selection = [types.SimpleNamespace(
        icao="OTHH", disposition="boundary_skipped")]
    assert "boundary" in VMAP.auto_patch_not_applied(tile, "OTHH",
                                                     str(tmp_path))


@pytest.fixture()
def rebake_stage(tmp_path, monkeypatch):
    """A tile whose patch dir holds ONE parseable OTHH plan with no units:
    if the plan is admitted the loop books ``airports`` 1 at the no-unit
    arm; if it is refused it books ``airports_skipped_unapplied``."""
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    _touch(patch_dir / "o4_v2_rebake_OTHH.json", "{}")
    _touch(patch_dir / "OTHH_auto.patch.osm")
    mesh = _touch(tmp_path / "mesh.mes", "")
    monkeypatch.setattr(post_mesh, "object_anchor_worklist_path",
                        lambda _t: str(patch_dir / "worklist.json"))
    monkeypatch.setattr(post_mesh, "_mesh_is_newer_than_alt",
                        lambda _t, _m: True)
    monkeypatch.setattr(FNAMES, "mesh_file",
                        lambda _b, _lat, _lon: str(mesh))
    monkeypatch.setattr(_rb.RebakePlan, "from_json", classmethod(
        lambda cls, _t: types.SimpleNamespace(icao="OTHH", units=[],
                                              skipped=[])))
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    return _Tile(str(tmp_path)), patch_dir


def test_rebake_places_a_plan_whose_patch_is_in_the_mesh(rebake_stage):
    tile, _ = rebake_stage
    counts = engine_v2.rebake_after_mesh(tile)
    assert counts["airports"] == 1
    assert "airports_skipped_unapplied" not in counts


def test_rebake_skips_a_plan_a_manual_patch_overrode(rebake_stage, capsys):
    tile, patch_dir = rebake_stage
    _touch(patch_dir / "OTHH.patch.osm")
    counts = engine_v2.rebake_after_mesh(tile)
    assert counts["airports"] == 0
    assert counts["airports_failed"] == 0
    assert counts["airports_skipped_unapplied"] == 1
    assert "placement SKIPPED" in capsys.readouterr().out
