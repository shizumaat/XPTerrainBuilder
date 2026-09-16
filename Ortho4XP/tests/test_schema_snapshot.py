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
counts as drift too.  Hermetic: the repo's own files and the running
interpreter, no network.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent
SCHEMA_DUMP = REPO_ROOT / "Sources" / "SceneryKit" / "Resources" / "o4_schema_dump.py"
SNAPSHOT = REPO_ROOT / "Sources" / "SceneryKit" / "Resources" / "o4_schema_snapshot.json"

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
    assert result.stdout == committed, (
        "Sources/SceneryKit/Resources/o4_schema_snapshot.json is stale — the "
        "shipped app's settings UI silently drops any row missing from it. "
        "Regenerate with:\n  (cd Ortho4XP && venv/bin/python "
        "../Sources/SceneryKit/Resources/o4_schema_dump.py > "
        "../Sources/SceneryKit/Resources/o4_schema_snapshot.json)"
    )
