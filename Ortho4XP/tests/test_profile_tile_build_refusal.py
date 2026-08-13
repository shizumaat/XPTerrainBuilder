"""Twin for the EMPTY-CIFP refusal in ``tools/profile_tile_build.py``.

The P1 tile profiler had no such refusal: the dev tree and every lane
worktree ship ``cifp_data_path`` EMPTY, ``run_auto_patch_generation`` then
never calls the generator, and the profiler happily measured a tile with
NO auto_patch surfaces at all and exited 0.  ``harness/build_airport.py
--tile`` has refused exactly this since it was written.

What these tests hold is not only "it refuses" but "it refuses with THE
harness's implementation": a second, slightly different copy of a harness
law is the census-wrapper defect (root CLAUDE.md), and a copy is what a
future edit will reach for unless a test names it.

Headless: no engine import (``O4_Config_Utils`` is stubbed), no tile
build, no network, no shared-repo access.
"""
import importlib.util
import inspect
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILER = ROOT / "tools" / "profile_tile_build.py"
BUILD_ENTRY = ROOT / "tools" / "harness" / "build_airport.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def cfg_stub(monkeypatch):
    """A stand-in for the engine's ``O4_Config_Utils``.

    ``apply_xplane_install_paths`` writes into the live engine globals; a
    test must not import the engine to prove a refusal, and must never
    leave real globals mutated behind it.
    """
    applied = {}
    stub = types.ModuleType("O4_Config_Utils")
    stub.set_global_variables = lambda var, value: applied.__setitem__(
        var, value)
    stub.config_compatibility = lambda value: value
    monkeypatch.setitem(sys.modules, "O4_Config_Utils", stub)
    return applied


@pytest.fixture(scope="module")
def profiler(request):
    # Pin O4_LOG_VERBOSITY before the import (the module setdefault()s it)
    # and restore it afterwards — importing a tool must not re-frame the
    # rest of the suite.
    before = os.environ.get("O4_LOG_VERBOSITY")
    os.environ.setdefault("O4_LOG_VERBOSITY", "1")

    def restore():
        if before is None:
            os.environ.pop("O4_LOG_VERBOSITY", None)
        else:
            os.environ["O4_LOG_VERBOSITY"] = before
    request.addfinalizer(restore)
    return _load("twin_profile_tile_build", PROFILER)


@pytest.fixture(scope="module")
def build_entry(profiler):
    """THE build entry — the module the profiler's refusal comes from."""
    return sys.modules["build_airport"]


def _owner_cfg(tmp_path, **values):
    cfg = tmp_path / "Ortho4XP.cfg"
    cfg.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    return cfg


def test_the_profiler_uses_THE_build_entrys_refusal_not_a_copy(
        profiler, build_entry):
    assert profiler.apply_xplane_install_paths is \
        build_entry.apply_xplane_install_paths
    assert Path(inspect.getfile(profiler.apply_xplane_install_paths)) == \
        BUILD_ENTRY
    source = PROFILER.read_text()
    assert "REFUSING" not in source, (
        "the profiler is spelling a refusal of its own — it must import "
        "the harness's (the census-wrapper precedent)")


def test_the_profiler_refuses_an_empty_cifp_path(profiler, build_entry,
                                                 tmp_path, cfg_stub):
    cfg = _owner_cfg(tmp_path, cifp_data_path="", custom_scenery_dir="")

    with pytest.raises(SystemExit) as profiled:
        profiler.apply_xplane_install_paths(owner_cfg=cfg)
    with pytest.raises(SystemExit) as built:
        build_entry.apply_xplane_install_paths(owner_cfg=cfg)

    assert "REFUSING" in str(profiled.value)
    assert "auto_patch generation would be SKIPPED" in str(profiled.value)
    assert str(profiled.value) == str(built.value), (
        "the profiler's reason string has drifted from the build entry's")
    assert not cfg_stub, "nothing may be applied when the refusal fires"


def test_the_profiler_proceeds_when_the_cifp_path_is_set(profiler, tmp_path,
                                                         cfg_stub):
    cifp = tmp_path / "CIFP"
    cifp.mkdir()
    cfg = _owner_cfg(tmp_path, cifp_data_path=str(cifp),
                     custom_scenery_dir="")

    applied = profiler.apply_xplane_install_paths(owner_cfg=cfg)

    assert applied == {"cifp_data_path": str(cifp)}
    assert cfg_stub == {"cifp_data_path": str(cifp)}, (
        "the resolved path must reach the engine's config globals — "
        "refusing but not APPLYING would profile the degraded tile anyway")


def test_the_refusal_runs_before_any_build_step(profiler):
    """Ordering twin: applied before the Tile is built and before step 1.

    A refusal that fired after the vector step would still have profiled
    (and written) a degraded tile.
    """
    source = inspect.getsource(profiler.main)
    call = source.index("apply_xplane_install_paths(")
    assert call < source.index("CFG.Tile(")
    assert call < source.index("step_fn[step](tile)")
