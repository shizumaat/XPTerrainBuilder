"""EVERY v2 MODULE IMPORTS FIRST — the twin of issue #341.

``placement_body``, ``placement_census`` and ``placement_cockpit`` each
raised ``ImportError`` when imported FIRST in a fresh interpreter: each sat
on a tail re-export cycle (``placement_cut`` re-exports ``placement_body``,
``placement_carrier`` re-exports ``placement_census``, which re-exports
``placement_cockpit``) and asked its partner for names before defining its
own.  Production's import order hid it; a tool or a test that imported one
of them directly failed or passed by what happened to be imported before.

No in-process test can see that — the suite's own imports are an order —
so each module is imported by a NEW interpreter with nothing else loaded.
"""
from __future__ import annotations

import concurrent.futures as _cf
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


def _v2_modules() -> list[str]:
    out = []
    for f in sorted((SRC / "auto_patch_v2").rglob("*.py")):
        parts = list(f.relative_to(SRC).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        out.append(".".join(parts))
    return out


def _import_first(module: str) -> tuple[str, str]:
    env = dict(os.environ, PYTHONPATH=str(SRC))
    done = subprocess.run([sys.executable, "-c", f"import {module}"], env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    last = (done.stderr.strip().splitlines() or [""])[-1]
    return module, "" if done.returncode == 0 else last


def test_every_v2_module_imports_first_in_a_fresh_interpreter():
    modules = _v2_modules()
    assert len(modules) > 200, "the walk collapsed — it proves nothing"
    for named in ("auto_patch_v2.airport.placement_body",
                  "auto_patch_v2.airport.placement_census",
                  "auto_patch_v2.airport.placement_cockpit"):
        assert named in modules, named
    with _cf.ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
        failed = [(m, why) for m, why in pool.map(_import_first, modules) if why]
    assert not failed, "cannot be imported first: " + "; ".join(
        f"{m}: {why}" for m, why in failed)
