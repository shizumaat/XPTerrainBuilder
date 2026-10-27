"""Settings that live in other modules' globals (``O4_Cfg_Module_Values``,
#836 cut C5): ``O4_Config_Utils`` no longer imports the owning modules,
yet every owning module ends up holding the config's value — whether it
was imported before the config or after it — exactly the value the old
``exec("IMG.x=" + value)`` gave.  Each case runs in a FRESH interpreter
(import order is the thing under test) against a private data root."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "src")
sys.path.insert(0, SRC)

import O4_Cfg_Module_Values as MODULE_VALUES  # noqa: E402
from O4_Cfg_Vars import cfg_vars  # noqa: E402

MODULE_VARS = sorted(v for v, spec in cfg_vars.items() if "module" in spec)


def _changed(var: str) -> tuple[str, object]:
    """A config-file line value for ``var`` that differs from its default,
    and the object the retired ``exec(target + "=" + value)`` assigned
    for it (a bool/list line was evaluated; others went through the
    registered type)."""
    spec = cfg_vars[var]
    default = spec["default"]
    if spec["type"] is bool:
        return repr(not default), (not default)
    if spec["type"] is list:
        return repr([7, 11]), [7, 11]
    if spec["type"] is int:
        return str(default + 3), default + 3
    if spec["type"] is float:
        return str(default + 0.5), default + 0.5
    return "changed_" + str(default), "changed_" + str(default)


_PROBE = r"""
import importlib, json, sys
sys.path.insert(0, {src!r})
order = {order!r}
mods = {mods!r}
if order == "targets_first":
    for name in mods.values():
        importlib.import_module(name)
import O4_Config_Utils as CFG
unloaded = sorted(n for n in mods.values() if n not in sys.modules)
if order == "config_first":
    for name in mods.values():
        importlib.import_module(name)
import O4_Cfg_Vars as V
out = {{}}
for var, spec in V.cfg_vars.items():
    if "module" in spec:
        out[var] = getattr(sys.modules[mods[spec["module"]]], var)
holders = {{alias: getattr(CFG, alias).__name__ for alias in mods}}
print(json.dumps({{"values": out, "unloaded": unloaded, "holders": holders}}))
"""


def _run(tmp_path, order: str, lines: dict[str, str]) -> dict:
    root = tmp_path / order
    root.mkdir()
    (root / "XPTerrainBuilder.cfg").write_text(
        "".join(f"{k}={v}\n" for k, v in lines.items()),
        encoding="utf-8", newline="")
    env = dict(os.environ, ORTHO4XP_DATA_ROOT=str(root))
    code = _PROBE.format(src=SRC, order=order, mods=MODULE_VALUES.MODULES)
    done = subprocess.run([sys.executable, "-c", code], env=env, cwd=SRC,
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=300, check=True)
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_every_module_alias_is_mapped_and_owns_its_setting():
    for var in MODULE_VARS:
        alias = cfg_vars[var]["module"]
        assert alias in MODULE_VALUES.MODULES, (var, alias)
        path = os.path.join(SRC, MODULE_VALUES.MODULES[alias] + ".py")
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        assert f"\n{var} =" in text, (var, path)
        assert text.rstrip().endswith("MODULE_VALUES.pull(__name__, globals())"), path


@pytest.mark.parametrize("order", ["config_first", "targets_first"])
def test_defaults_reach_every_owning_module(tmp_path, order):
    got = _run(tmp_path, order, {})
    for var in MODULE_VARS:
        assert got["values"][var] == cfg_vars[var]["default"], var
    assert got["holders"] == MODULE_VALUES.MODULES


@pytest.mark.parametrize("order", ["config_first", "targets_first"])
def test_global_cfg_values_match_the_old_exec(tmp_path, order):
    changed = {var: _changed(var) for var in MODULE_VARS}
    got = _run(tmp_path, order, {v: text for v, (text, _) in changed.items()})
    for var in MODULE_VARS:
        want = changed[var][1]
        assert want != cfg_vars[var]["default"], var
        assert got["values"][var] == want, var


def test_config_no_longer_imports_the_tile_pipeline(tmp_path):
    got = _run(tmp_path, "config_first", {})
    for name in ("O4_Tile_Utils", "O4_Imagery_Utils", "O4_DEM_Utils",
                 "O4_Overlay_Utils"):
        assert name in got["unloaded"], name
