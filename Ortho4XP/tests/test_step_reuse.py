"""Twins for ``O4_Step_Reuse`` (#615): a rebuild that changes only the
texture mode / imagery reuses the vector, mesh and masks steps; a change
any of them reads rebuilds that step and every one after it.

Headless: a stand-in tile in ``tmp_path``, the tile's OSM / patch / mask
folders redirected there, no pipeline.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Cfg_Vars as CFGVARS  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Step_Reuse as REUSE  # noqa: E402


class _Tile:
    """A configured tile: every tile setting at its registry default."""

    def __init__(self, build_dir):
        self.lat, self.lon, self.build_dir = 25, 51, str(build_dir)
        self.iterate = 0
        for name in CFGVARS.list_tile_vars:
            setattr(self, name, CFGVARS.cfg_vars[name]["default"])
        self.texture_mode = "full_ortho"
        self.default_website = "BI"
        self.default_zl = 16


@pytest.fixture
def tile(tmp_path, monkeypatch):
    for name in ("osm", "patches", "masks", "build", "insets"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(FNAMES, "osm_dir", lambda lat, lon: str(tmp_path / "osm"))
    monkeypatch.setattr(FNAMES, "patch_dir",
                        lambda lat, lon: str(tmp_path / "patches"))
    monkeypatch.setattr(FNAMES, "mask_dir", lambda lat, lon: str(tmp_path / "masks"))
    monkeypatch.setattr(FNAMES, "airport_inset_directory",
                        lambda lat, lon: str(tmp_path / "insets"))
    monkeypatch.delenv("O4_STEP_REUSE", raising=False)
    (tmp_path / "osm" / "+25+051_airports.osm.bz2").write_bytes(b"osm")
    (tmp_path / "masks" / "mask.png").write_bytes(b"mask")
    return _Tile(tmp_path / "build")


def _write_outputs(tile):
    for path in (FNAMES.input_node_file(tile), FNAMES.input_poly_file(tile),
                 FNAMES.alt_file(tile),
                 FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("data")


def _complete_build(tile, steps=REUSE.REUSABLE_STEPS):
    """What the session does for a build that runs ``steps``, reuses the
    rest, and completes (the imagery step's commit)."""
    for step in REUSE.REUSABLE_STEPS:
        if step in steps:
            REUSE.forget_from(tile, step)
            REUSE.record(tile, step)
        else:
            assert REUSE.stale_reason(tile, step) is None
            REUSE.reused(tile, step)
    REUSE.commit(tile)


def _reasons(tile):
    return {step: REUSE.stale_reason(tile, step)
            for step in REUSE.REUSABLE_STEPS}


def test_texture_only_change_reuses_vector_mesh_and_masks(tile):
    _write_outputs(tile)
    _complete_build(tile)
    tile.texture_mode = "default_xplane"
    tile.default_website = "GO2"
    tile.default_zl = 17
    tile.zone_list = [[[25, 51, 25.5, 51.5], 18, "BI"]]
    tile.cover_airports_with_highres = "True"
    tile.color_harmonization = True
    assert _reasons(tile) == {"vector": None, "mesh": None, "masks": None}


def test_no_record_before_a_completed_build(tile):
    _write_outputs(tile)
    for step in REUSE.REUSABLE_STEPS:
        REUSE.record(tile, step)            # ran, but never committed
    assert all(why == "no record of a completed build"
               for why in _reasons(tile).values())


def test_mesh_setting_rebuilds_mesh_and_masks_not_vector(tile):
    _write_outputs(tile)
    _complete_build(tile)
    tile.curvature_tol = tile.curvature_tol + 1
    reasons = _reasons(tile)
    assert reasons["vector"] is None
    assert "curvature_tol" in reasons["mesh"]
    # The session drops the mesh's record and every later one when the
    # mesh step starts; the masks then rebuild on the new mesh.
    REUSE.reused(tile, "vector")
    REUSE.forget_from(tile, "mesh")
    assert REUSE.stale_reason(tile, "masks") == "no record of a completed build"
    _complete_build(tile, steps=("mesh", "masks"))
    assert _reasons(tile) == {"vector": None, "mesh": None, "masks": None}


def test_vector_setting_rebuilds_everything(tile):
    _write_outputs(tile)
    _complete_build(tile)
    tile.road_level = 0 if tile.road_level else 1
    assert "road_level" in REUSE.stale_reason(tile, "vector")


def test_ratio_water_is_a_masks_input(tile):
    _write_outputs(tile)
    _complete_build(tile)
    tile.ratio_water = 0.9 if tile.ratio_water != 0.9 else 0.1
    reasons = _reasons(tile)
    assert reasons["vector"] is None and reasons["mesh"] is None
    assert "ratio_water" in reasons["masks"]


def test_changed_output_or_data_rebuilds(tile, tmp_path):
    _write_outputs(tile)
    _complete_build(tile)
    os.remove(FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon))
    assert REUSE.stale_reason(tile, "mesh") == (
        "its output files changed or are missing")
    # A layer a LATER step fetched (the masks step's reefs) is not one
    # the vector step read...
    (tmp_path / "osm" / "+25+051_reef.osm.bz2").write_bytes(b"reef")
    assert REUSE.stale_reason(tile, "vector") is None
    # ...a refreshed one it read is.
    (tmp_path / "osm" / "+25+051_airports.osm.bz2").write_bytes(b"refreshed")
    assert REUSE.stale_reason(tile, "vector") == (
        "the OpenStreetMap data changed")


def test_a_new_elevation_inset_rebuilds_the_vector_step(tile, tmp_path):
    _write_outputs(tile)
    _complete_build(tile)
    (tmp_path / "insets" / "OTHH_x.tif").write_bytes(b"inset")
    assert REUSE.stale_reason(tile, "vector") == (
        "the airport elevation insets changed")


def test_a_rebuilt_step_chains_to_the_next(tile):
    """A vector step that ran again (same inputs) still rebuilds the mesh:
    its committed record went when it started."""
    _write_outputs(tile)
    _complete_build(tile)
    REUSE.forget_from(tile, "vector")
    REUSE.record(tile, "vector")
    assert REUSE.stale_reason(tile, "mesh") == "no record of a completed build"


def test_reuse_can_be_turned_off(tile, monkeypatch):
    _write_outputs(tile)
    _complete_build(tile)
    monkeypatch.setenv("O4_STEP_REUSE", "0")
    assert all(why and "O4_STEP_REUSE" in why for why in _reasons(tile).values())


def test_mesh_records_the_pack_dsfs_its_object_stage_rewrote(tile, tmp_path,
                                                             monkeypatch):
    dsf = tmp_path / "pack.dsf"
    dsf.write_bytes(b"dsf")
    monkeypatch.setattr(REUSE, "_journalled_dsfs", lambda t: [str(dsf)])
    _write_outputs(tile)
    _complete_build(tile)
    assert REUSE.stale_reason(tile, "mesh") is None
    dsf.write_bytes(b"a reinstalled pack")
    assert REUSE.stale_reason(tile, "mesh") == (
        "its output files changed or are missing")


def test_no_texture_setting_is_an_input_of_the_earlier_steps():
    """The mechanism of #615, as a registry fact: the texture settings
    belong to the scenery-file step only (``ratio_water`` excepted, read
    by the masks step and listed there)."""
    texture = set(CFGVARS.list_dsf_vars) | {"default_website", "default_zl",
                                           "zone_list"}
    for step in REUSE.REUSABLE_STEPS:
        read = set(REUSE._step_settings(step)) & texture
        assert read == ({"ratio_water"} if step == "masks" else set())


def test_session_skips_reused_steps_by_name(monkeypatch, tmp_path):
    """Through the session's real step loop: the second build of an
    unchanged tile calls only the imagery step, and the tile's row names
    each reused step."""
    from o4_engine import events as EV
    from o4_engine.session import EngineSession
    from test_engine_session import install_stub_pipeline, run_build

    calls = []

    def ran(step):
        def hook(tile):
            calls.append(step)
            if step == "imagery":
                REUSE.commit(tile)          # the real step's last act
        return hook

    monkeypatch.setattr(FNAMES, "osm_dir", lambda lat, lon: str(tmp_path / "o"))
    monkeypatch.setattr(FNAMES, "patch_dir", lambda lat, lon: str(tmp_path / "p"))
    monkeypatch.setattr(FNAMES, "mask_dir", lambda lat, lon: str(tmp_path / "m"))
    install_stub_pipeline(monkeypatch, hooks={
        step: ran(step) for step in ("vector", "mesh", "masks", "imagery")})
    stub = sys.modules["O4_Config_Utils"]

    class _ConfiguredTile(stub.Tile):
        iterate = 0                 # what FNAMES' file names read

    monkeypatch.setattr(stub, "Tile", _ConfiguredTile)
    run_build(EngineSession(), [(10, 20)], tmp_path)
    assert calls == ["vector", "mesh", "masks", "imagery"]
    calls.clear()
    events = run_build(EngineSession(), [(10, 20)], tmp_path)
    assert calls == ["imagery"]
    labels = {e.step_key: e.label for e in events
              if isinstance(e, EV.StepProgress)}
    for step in REUSE.REUSABLE_STEPS:
        assert "reused" in labels[step]
    assert [e.ok for e in events if isinstance(e, EV.BuildDone)] == [True]


def test_a_reused_step_gets_a_sliver_of_the_bar(monkeypatch):
    from o4_engine import session as SESSION
    from o4_engine import tile_time_model as TTM
    monkeypatch.setattr(TTM, "predict_step_seconds",
                        lambda lat, lon, features, steps: {
                            k: 100.0 for k in steps})
    steps = ["vector", "mesh", "masks", "imagery"]
    estimates = SESSION._predict_step_seconds(
        1, 2, {"reused_steps": ["vector", "mesh"]}, steps)
    assert estimates == {"vector": 1.0, "mesh": 1.0, "masks": 100.0,
                         "imagery": 100.0}
    plan = SESSION.reweight_plan_by_seconds(
        SESSION.plan_steps(True, True, False), estimates)
    widths = {key: width for key, _base, width in plan}
    assert widths["vector"] < 0.01 and widths["imagery"] > 0.45


def test_predicted_reuse_stops_at_the_first_step_that_runs(tile):
    _write_outputs(tile)
    _complete_build(tile)
    assert REUSE.predicted_reuse(tile) == ("vector", "mesh", "masks")
    tile.min_angle = tile.min_angle + 1
    assert REUSE.predicted_reuse(tile) == ("vector",)
