"""#2186 / #2226: a failed object stage reaches the tile's build result.

Before: ``auto_patch.object_stage`` logged a failed airport placement (or a
failed stage) and carried on, and ``O4_Object_Stage.run`` swallowed the
rest, so a tile whose pack DSF write was refused finished as a clean "ok"
and the user flew floating buildings.  Now each unfitted airport is a
DEGRADED ``pack_objects_not_fitted`` row beside the tile, the final
``BuildDone`` names it as a warning (both apps render ``warnings``), and a
reused mesh step runs the stage again until it fits.
"""

import pytest

import O4_File_Names as FNAMES
import O4_Object_Stage as OBJECT_STAGE
import O4_Step_Reuse as REUSE
import O4_Tile_Failures as FAIL
import O4_UI_Utils as UI
import O4_Unpatched_Airports as UNPATCHED
from auto_patch import object_stage
from auto_patch import post_mesh
from o4_engine import events as EV
from o4_engine import session as SESSION
from o4_engine.session import EngineSession

from test_engine_session import _tile_events, install_stub_pipeline, run_build


class _Tile:
    def __init__(self, build_dir, lat=30, lon=31):
        self.build_dir = build_dir
        self.lat = lat
        self.lon = lon
        self.modify_custom_airports = True


@pytest.fixture(autouse=True)
def reset_ui_routing():
    yield
    UI.engine_session = None
    UI.red_flag = False


@pytest.fixture()
def broken_plan(tmp_path, monkeypatch):
    """A tile whose ONE placement plan cannot be read: the per-airport
    arm of the stage fails exactly as a refused pack write does."""
    patch_dir = tmp_path / "Patches" / "zOrtho4XP_+30+031"
    patch_dir.mkdir(parents=True)
    (patch_dir / "o4_v2_rebake_HECA.json").write_text("{not json at all",
                                                     encoding="utf-8")
    mesh = tmp_path / "mesh.mes"
    mesh.write_text("", encoding="utf-8")
    monkeypatch.setattr(post_mesh, "object_anchor_worklist_path",
                        lambda _t: str(patch_dir / "worklist.json"))
    monkeypatch.setattr(post_mesh, "_mesh_is_newer_than_alt",
                        lambda _t, _m: True)
    monkeypatch.setattr(FNAMES, "mesh_file",
                        lambda _b, _lat, _lon: str(mesh))
    monkeypatch.delenv("O4_PACK_WRITES", raising=False)
    return _Tile(str(tmp_path))


def _rows(build_dir):
    return UNPATCHED.read_degraded(type("T", (), {"build_dir": build_dir})())


def test_a_failed_airport_placement_is_a_row_beside_the_tile(broken_plan):
    counts = OBJECT_STAGE.run(broken_plan)

    assert counts["airports_failed"] == 1
    # read back as ANOTHER process does: from the sidecar
    (row,) = _rows(broken_plan.build_dir)
    assert (row["code"], row["airport"]) == ("pack_objects_not_fitted",
                                             "HECA")
    assert row["detail"]
    assert OBJECT_STAGE.failed_last_run(broken_plan) == (
        "its last run did not fit the objects of HECA")


def test_a_stage_that_raises_is_a_tile_row(tmp_path, monkeypatch):
    def boom(tile, failed=None):
        raise RuntimeError("DSF write refused")
    monkeypatch.setattr(object_stage, "rebake_after_mesh", boom)
    tile = _Tile(str(tmp_path))

    assert OBJECT_STAGE.run(tile) == {}

    (row,) = _rows(str(tmp_path))
    assert row["code"] == "pack_objects_not_fitted"
    assert "airport" not in row and "DSF write refused" in row["detail"]


def test_a_clean_run_clears_the_last_runs_rows(broken_plan, monkeypatch):
    OBJECT_STAGE.run(broken_plan)
    monkeypatch.setattr(object_stage, "rebake_after_mesh",
                        lambda tile, failed=None: {"airports": 1})
    fresh = _Tile(broken_plan.build_dir)        # the next build's tile

    OBJECT_STAGE.run(fresh)

    assert _rows(broken_plan.build_dir) == []
    assert OBJECT_STAGE.failed_last_run(fresh) is None


def test_a_stale_mesh_skip_is_named(broken_plan, monkeypatch):
    monkeypatch.setattr(post_mesh, "_mesh_is_newer_than_alt",
                        lambda _t, _m: False)

    OBJECT_STAGE.run(broken_plan)

    (row,) = _rows(broken_plan.build_dir)
    assert ".alt" in row["detail"]


def test_a_reused_mesh_runs_the_stage_again_after_a_failure(broken_plan,
                                                           monkeypatch):
    """The warning says "build the tile again": that build must not serve
    the mesh step's record and skip the stage (#2226 auto-recovery)."""
    monkeypatch.setattr(REUSE, "_object_stage_code", lambda: "code-1")
    monkeypatch.setattr(REUSE, "committed_entry",
                        lambda tile, step: {"object_code": "code-1"})
    assert REUSE.object_stage_stale(_Tile(broken_plan.build_dir)) is None

    OBJECT_STAGE.run(broken_plan)

    why = REUSE.object_stage_stale(_Tile(broken_plan.build_dir))
    assert why and "HECA" in why


def test_the_catalogue_entry_is_a_degraded_retry():
    entry = FAIL.CATALOGUE[object_stage.NOT_FITTED_CODE]
    assert (entry.severity, entry.remedy) == ("degraded", "retry")
    assert FAIL.domain_of(object_stage.NOT_FITTED_CODE) == "pack"


def test_the_build_result_is_not_ok_and_tells_the_user(monkeypatch,
                                                       tmp_path):
    """END TO END through the session: the mesh step's object stage
    fails, the tile is BUILT WITH WARNINGS (never a clean ok) and the
    warning names the airport, the pack and the remedy."""
    def mesh_with_a_failed_stage(tile):
        def refused(tile_, failed=None):
            failed.append({"code": "pack_objects_not_fitted",
                           "airport": "KASE", "pack": "Aspen Pack",
                           "detail": "DSFTool: OBJECT_MSL above HEIGHTS"})
            return {"airports": 1, "airports_failed": 1}
        monkeypatch.setattr(object_stage, "rebake_after_mesh", refused)
        OBJECT_STAGE.run(tile)

    install_stub_pipeline(monkeypatch,
                          hooks={"mesh": mesh_with_a_failed_stage})
    events = run_build(EngineSession(), [(10, 20)], tmp_path)

    (done,) = [e for e in _tile_events(events, 10, 20)
               if isinstance(e, EV.BuildDone)]
    assert done.ok is True and done.failures == []
    (warning,) = done.warnings
    assert warning["code"] == "pack_objects_not_fitted"
    assert warning["severity"] == "degraded"
    assert warning["what"] == ("Tile +10+020 was built, but the buildings "
                               "of airport KASE were not fitted to its new "
                               "ground.")
    assert "“Aspen Pack”" in warning["why"]
    assert warning["remedy"].startswith("Build the tile again.")
    assert "OBJECT_MSL" in warning["detail"]
    assert done.unpatched_airports == []      # the patch itself stands
    states = [e for e in _tile_events(events, 10, 20)
              if isinstance(e, EV.TileState) and e.state == "done"]
    assert [e.label for e in states] == [SESSION.BUILT_WITH_WARNINGS]


def test_a_failed_guest_reseat_is_a_row_of_the_tile(monkeypatch):
    """The neighbours' objects this tile's mesh re-seats (#2129) stand on
    THIS tile: a re-seat that fails is this tile's warning too."""
    from auto_patch import guest_stage as GS

    def boom(*_a, **_k):
        raise OSError("pack DSF locked")
    monkeypatch.setattr(GS, "_mesh_digest", lambda _p: "digest")
    monkeypatch.setattr(GS, "_stale", boom)
    failed = []

    assert GS.reseat_guests(_Tile("/nonexistent"), "/x.mesh",
                            failed=failed) == {}

    (row,) = failed
    assert row["code"] == "pack_objects_not_fitted"
    assert "pack DSF locked" in row["detail"]
