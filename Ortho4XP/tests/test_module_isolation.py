"""Twins for ``tests/module_isolation`` and conftest's stand-in guard (#639).

``test_auto_patch_freshness::test_a_relaunched_app_reuses_and_a_rebuild_
names_its_key`` was red whenever no earlier test on its xdist worker had
imported the real ``auto_patch_v2.airport.object_plan``: the shared v2 stub
replaced ``auto_patch_v2.airport`` with a path-less stand-in.  These twins
hold the three things that ended it — a stand-in package still resolves its
real submodules in a FRESH process, ``sys.modules`` is put back exactly, and
a stand-in left behind fails the test that left it, by name.
"""

import os
import subprocess
import sys
import types

import pytest

import conftest
from tests import module_isolation

ENGINE_ROOT = os.path.dirname(module_isolation.SRC)

_FRESH_PROCESS = """
import sys
sys.path[:0] = [{src!r}, {tests!r}, {root!r}]
from test_auto_patch_engine_dispatch import _stub_v2
assert not any(n.startswith("auto_patch_v2.airport.object_plan")
               for n in sys.modules), "the premise: nothing imported it yet"
_stub_v2(None)
from auto_patch_v2.airport import object_plan
from auto_patch_v2.model import pulse
from auto_patch_v2.airport.load import Inputs
assert object_plan.__file__.startswith({src!r}), object_plan.__file__
assert pulse.__file__.startswith({src!r}), pulse.__file__
assert Inputs.__module__ == "test_auto_patch_engine_dispatch", Inputs
print("ORDER-FREE")
"""


def test_the_v2_stub_resolves_real_submodules_in_a_fresh_process():
    """The #639 order, pinned: a process in which NOTHING has imported the
    real v2 package installs the shared stub and still reaches the unstubbed
    submodules the driver's gate imports."""
    script = _FRESH_PROCESS.format(
        src=module_isolation.SRC, root=ENGINE_ROOT,
        tests=os.path.join(ENGINE_ROOT, "tests"))
    done = subprocess.run([sys.executable, "-c", script], cwd=ENGINE_ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=120)
    assert done.returncode == 0, done.stderr
    assert "ORDER-FREE" in done.stdout


def test_install_then_restore_puts_sys_modules_back_exactly():
    """What was there returns; what was imported under the stand-in — and
    the attribute the import system hung on its real parent — is gone."""
    import auto_patch_v2.model as real_model
    before = {n: m for n, m in sys.modules.items()
              if n.partition(".")[0] == "auto_patch_v2"}
    had_child = "isolation_probe" in vars(real_model)

    stand_in = types.ModuleType("auto_patch_v2")
    module_isolation.install({"auto_patch_v2": stand_in})
    assert sys.modules["auto_patch_v2"] is stand_in
    assert stand_in.__path__ == list(before["auto_patch_v2"].__path__)
    child = types.ModuleType("auto_patch_v2.model.isolation_probe")
    sys.modules[child.__name__] = child
    real_model.isolation_probe = child

    module_isolation.restore_all()

    after = {n: m for n, m in sys.modules.items()
             if n.partition(".")[0] == "auto_patch_v2"}
    assert after.keys() == before.keys()
    assert all(after[n] is before[n] for n in before)
    assert ("isolation_probe" in vars(real_model)) == had_child
    assert module_isolation.left_behind() == []


def test_a_second_install_in_one_test_keeps_the_package_path():
    """``_drive_generate`` installs the stub once per call: the second
    stand-in finds the first where the real package was, and must still
    carry the package path (the freshness twin's second build read it)."""
    real = list(__import__("auto_patch_v2.airport").airport.__path__)
    for _ in range(2):
        stand_in = types.ModuleType("auto_patch_v2.airport")
        module_isolation.install({"auto_patch_v2.airport": stand_in})
        assert stand_in.__path__ == real
    module_isolation.restore_all()
    assert sys.modules["auto_patch_v2.airport"].__file__


def test_left_behind_names_a_stand_in_and_nothing_else(monkeypatch):
    """Real engine modules, an engine module that is simply absent, and a
    stand-in under a name the engine does not own are all quiet; a stand-in
    under a first-party name is named — module object or not."""
    monkeypatch.delitem(sys.modules, "O4_Geotag", raising=False)   # absent
    monkeypatch.setitem(sys.modules, "not_an_engine_module",
                        types.ModuleType("not_an_engine_module"))
    assert module_isolation.left_behind() == []

    monkeypatch.setitem(sys.modules, "auto_patch_v2.left_here",
                        types.ModuleType("auto_patch_v2.left_here"))
    monkeypatch.setitem(sys.modules, "O4_Version", types.SimpleNamespace())
    assert module_isolation.left_behind() == [
        "O4_Version", "auto_patch_v2.left_here"]


def test_the_guard_fails_the_leaking_test_by_name_and_evicts():
    """conftest's teardown wrapper, driven as pytest drives it: the leak is
    reported once, against the test that made it, and does not stay."""
    item = types.SimpleNamespace(nodeid="tests/test_x.py::test_leaks")
    wrapper = conftest.pytest_runtest_teardown(item=item, nextitem=None)
    next(wrapper)
    sys.modules["auto_patch_v2.airport.left_here"] = types.ModuleType("stub")
    with pytest.raises(pytest.fail.Exception) as raised:
        wrapper.send(None)
    message = str(raised.value)
    assert "tests/test_x.py::test_leaks" in message
    assert "auto_patch_v2.airport.left_here" in message
    assert "auto_patch_v2.airport.left_here" not in sys.modules
