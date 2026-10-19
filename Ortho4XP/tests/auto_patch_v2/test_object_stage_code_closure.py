"""issue #879 — THE OBJECT STAGE REUSE'S CODE KEY IS THE IMPORT CLOSURE of
the stage (``airport/object_stage_code``), held like ``stage_code``'s:
a module the stage imports and the list omits would be a STALE HIT after
an edit there; a listed module the stage no longer imports is dropped.
The freeze digest reproduces from the specs' by-path execution, and both
specs bundle it."""
from __future__ import annotations

import inspect
import os
import subprocess
import sys
import types
from pathlib import Path

import O4_Code_Closure as CLOSURE
from auto_patch import object_stage as STAGE
from auto_patch_v2.airport import object_stage_code as OSC

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_every_module_the_stage_imports_is_in_its_code_key():
    closure = set(CLOSURE.closure(str(SRC), OSC.ENTRY_MODULES, OSC.CLOSURE_PREFIXES))
    missing, extra = sorted(closure - set(OSC.CODE_MODULES)), \
        sorted(set(OSC.CODE_MODULES) - closure)
    assert not missing, f"add to object_stage_code.CODE_MODULES: {missing}"
    assert not extra, f"drop from object_stage_code.CODE_MODULES: {extra}"
    assert list(OSC.CODE_MODULES) == sorted(set(OSC.CODE_MODULES))
    assert "auto_patch_v2.airport.object_stage_reuse" in OSC.CODE_MODULES


def test_the_entry_is_where_the_mesh_step_enters_the_stage():
    text = (SRC / "O4_Mesh_Utils.py").read_text(encoding="utf-8")
    assert "AUTO_PATCH_OBJECT_STAGE.rebake_after_mesh(tile)" in text
    assert STAGE.rebake_after_mesh.__module__ == OSC.ENTRY_MODULES[0]


def test_the_runtime_digest_is_the_checkouts():
    assert OSC.runtime_digest() == CLOSURE.modules_digest(str(SRC), OSC.CODE_MODULES)


_FREEZE = r"""
import os, runpy, sys
src, out = sys.argv[1], sys.argv[2]
mod = runpy.run_path(os.path.join(src, "auto_patch_v2", "airport", "object_stage_code.py"))
print(mod["write_freeze_digest"](src, out))
"""


def test_the_freeze_digest_reproduces_by_path(tmp_path):
    script = tmp_path / "freeze.py"
    script.write_text(_FREEZE, encoding="utf-8", newline="\n")
    run = subprocess.run([sys.executable, "-I", str(script), str(SRC), str(tmp_path / "o")],
                         cwd=str(tmp_path), capture_output=True, text=True,
                         encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stderr
    path = run.stdout.strip().splitlines()[-1]
    assert os.path.basename(path) == OSC.DIGEST_FILENAME
    assert CLOSURE.read_digest(os.path.dirname(path), OSC.DIGEST_FILENAME) \
        == OSC.runtime_digest()


def test_both_specs_write_and_bundle_the_digest():
    for spec in ("Ortho4XP.spec", "Ortho4XP_Qt.spec"):
        text = (ROOT / spec).read_text(encoding="utf-8")
        assert '"airport", "object_stage_code.py")\n)["write_freeze_digest"]("src"' in text
        assert '(_object_stage_digest_file, os.path.join("auto_patch_v2", "airport"))' in text


def test_the_stage_keys_each_airport_through_the_reuse(tmp_path):
    """The object stage's own key: the plan, the graded surface beside the
    patch, the pristine DSF and the plan's OBJs; and the reuse wraps the
    placement call (the sampler is built only when it runs)."""
    from auto_patch_v2.model.rebake import RebakePlan
    src = inspect.getsource(STAGE.rebake_after_mesh)
    assert src.index("_reuse_recipe(") < src.index("reuse.run(") < src.index("reuse.finish()")
    assert "mesh_placement_sampler(mesh_path" in src[src.index("def _compute"):
                                                      src.index("reuse.run(")]
    mesh = tmp_path / "t.mesh"
    mesh.write_text("m", encoding="utf-8")
    tile = types.SimpleNamespace(lat=10, lon=20, build_dir=str(tmp_path))
    reuse = STAGE._stage_reuse(tile, str(mesh))
    assert reuse is not None and reuse.code == OSC.runtime_digest()
    plan = RebakePlan("XAAA", "pack", str(tmp_path / "pack"), (), (), {})
    recipe = STAGE._reuse_recipe(reuse, plan, tile, str(tmp_path), writes=(True, False),
                                 omit=())
    assert recipe is not None
    assert recipe["inputs"]["params"]["write_enabled"] is True
    assert recipe["inputs"]["mesh"] == reuse.mesh_digest()
    assert STAGE._reuse_recipe(None, plan, tile, str(tmp_path), writes=(True, False),
                               omit=()) is None
