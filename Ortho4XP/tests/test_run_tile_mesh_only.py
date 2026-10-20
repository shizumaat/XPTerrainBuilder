"""``tools/run_tile_mesh_only.py --patches-as-is`` (#976).

The flag meshes the ``Patches/`` files on disk without generating any.  It
used to get there by leaving the CIFP unresolved, which step 1 now refuses
(``auto_patch=ICAO`` with no CIFP is FATAL, beta plan §1 B2) and which also
switched flat-site DEM prep off.  The tool now replaces the generator call
by name and applies the install paths non-fatally.  Static twins: the tool
cannot be imported in a test (it redirects the engine caches at import).
"""
from __future__ import annotations

import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
TOOL = ENGINE / "tools" / "run_tile_mesh_only.py"


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def test_the_vector_step_calls_the_generator_through_its_module_global():
    """The tool's replacement of ``VMAP.run_auto_patch_generation`` holds
    only while ``include_airports`` looks the name up at call time."""
    tree = _tree(ENGINE / "src" / "O4_Vector_Map.py")
    func = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "include_airports")
    calls = [n for n in ast.walk(func) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)
             and n.func.id == "run_auto_patch_generation"]
    assert calls, "include_airports no longer calls run_auto_patch_generation by name"


def test_patches_as_is_skips_generation_by_name_and_keeps_the_install():
    tree = _tree(TOOL)
    assigned = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Attribute)
                        and t.attr == "run_auto_patch_generation"
                        and isinstance(t.value, ast.Name) and t.value.id == "VMAP"
                        for t in n.targets)]
    assert len(assigned) == 1
    stand_in = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_patches_as_is_generation")
    assert [a.arg for a in stand_in.args.args] == [
        "tile", "airport_layer", "dico_airports"]
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Name)}
    assert "apply_xplane_install_paths_for_preflight" in called
