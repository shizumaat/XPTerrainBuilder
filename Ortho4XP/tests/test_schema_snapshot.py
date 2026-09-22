"""Bundled config-schema snapshot tripwire.

A FROZEN engine (what ``scripts/make_engine.sh`` bundles into the shipped
app) cannot run the loose ``o4_schema_dump.py``, so
``OrthoConfigSchema.bundledSnapshot()`` — the committed JSON resource — is
the shipped app's ONLY schema.  Rows in ``SettingsLayout.swift`` whose
variable is absent from the schema are silently not shown, so a stale
snapshot hides settings without any error anywhere.  That is exactly what
happened between 1.50.0 and 1.50.1689: ``solve_model`` and the
``flat_site_declared`` pair existed in ``O4_Cfg_Vars`` and in the layout,
and never appeared in the app.

This twin regenerates the snapshot from the tree and requires the committed
file to match BYTE FOR BYTE — encoding drift (the ``ensure_ascii`` episode)
counts as drift too.  The one masked field is ``engineVersion``: it comes
from ``O4_Version.py``, which every app build bumps, and a tripwire that
fires on every build is a standing red, not a tripwire.  Hermetic: the
repo's own files and the running interpreter, no network.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent
SCHEMA_DUMP = REPO_ROOT / "Sources" / "SceneryKit" / "Resources" / "o4_schema_dump.py"
SNAPSHOT = REPO_ROOT / "Sources" / "SceneryKit" / "Resources" / "o4_schema_snapshot.json"
_ENGINE_VERSION = re.compile(r'"engineVersion": "[^"]*"')


def _mask_engine_version(text: str) -> str:
    return _ENGINE_VERSION.sub('"engineVersion": "*"', text, count=1)

app_side = pytest.mark.skipif(
    not SCHEMA_DUMP.is_file(),
    reason="engine checked out standalone — no XPTerrainBuilder app tree",
)


@app_side
def test_bundled_snapshot_matches_the_tree() -> None:
    result = subprocess.run(
        [sys.executable, str(SCHEMA_DUMP)],
        capture_output=True,
        text=True,
        cwd=str(ENGINE_DIR),
    )
    assert result.returncode == 0, result.stderr
    committed = SNAPSHOT.read_text(encoding="utf-8")
    assert _mask_engine_version(result.stdout) == _mask_engine_version(committed), (
        "Sources/SceneryKit/Resources/o4_schema_snapshot.json is stale — the "
        "shipped app's settings UI silently drops any row missing from it. "
        "Regenerate with:\n  (cd Ortho4XP && venv/bin/python "
        "../Sources/SceneryKit/Resources/o4_schema_dump.py > "
        "../Sources/SceneryKit/Resources/o4_schema_snapshot.json)"
    )


# ──────────────────────────────────────────────────────────────────────
# Every settings var belongs to exactly ONE schema group (#34)
# ──────────────────────────────────────────────────────────────────────
#: Vars the dump deliberately publishes in NO group: the ``global_*``
#: mirrors (the per-tile default of a tile var, never a row of their own)
#: and the three map-managed tile vars (``O4_Settings_Model`` twin
#: ``test_map_managed_vars_absent``: the tile grid sets them, not a row).
UNGROUPED_BY_DESIGN = frozenset({"default_website", "default_zl", "zone_list"})


def _dumped_schema() -> dict:
    import json

    result = subprocess.run(
        [sys.executable, str(SCHEMA_DUMP)],
        capture_output=True, text=True, cwd=str(ENGINE_DIR),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@app_side
def test_every_var_is_in_exactly_one_group() -> None:
    """``auto_patch_boundary`` sat in ``vars`` but in no ``groups`` entry
    (#34): the mac app resolves rows by NAME so its row rendered, the Qt
    row was added by hand, and a front end that walks ``groups`` never saw
    it.  The groups are the ``O4_Cfg_Vars.list_*_vars`` lists, so a var
    added to ``cfg_*_vars`` without a list entry is exactly this defect
    again — this twin fails on it.
    """
    sys.path.insert(0, str(ENGINE_DIR / "src"))
    from O4_Cfg_Vars import global_prefix

    schema = _dumped_schema()
    membership: dict[str, list[str]] = {}
    for group, names in schema["groups"].items():
        for name in names:
            membership.setdefault(name, []).append(group)
    twice = {n: g for n, g in membership.items() if len(g) > 1}
    assert not twice, f"vars in more than one group: {twice}"
    unknown = sorted(set(membership) - set(schema["vars"]))
    assert not unknown, f"groups name vars the schema does not carry: {unknown}"
    rows = {n for n in schema["vars"]
            if not n.startswith(global_prefix) and n not in UNGROUPED_BY_DESIGN}
    missing = sorted(rows - set(membership))
    assert not missing, (
        f"settings vars in no schema group (add each to its "
        f"O4_Cfg_Vars.list_*_vars): {missing}")
    assert membership["auto_patch_boundary"] == ["app"]
