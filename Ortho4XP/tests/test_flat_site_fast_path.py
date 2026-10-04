"""FLAT-SITE FAST PATH (phase 3) — the SOLVE PARTITION.

Spec: ``docs/specs/flat-site-fast-path-spec.md`` (2026-08-10, FROZEN).

THE EQUIVALENCE TWIN IS THE SPEC.  On a synthetic flat fixture (constant
DEM, one runway, apron / junction / taxi spine / service road, one tunnel
ramp) the fast-path arm and the full-solve arm must agree at EVERY shared
node within the solver quantum (0.01 m), the born-at-Z0 shapes must read
EXACTLY Z0, and the runway profile must be byte-identical.  Everything
else here is the partition predicate: what it admits, what it refuses,
and that the gate off is byte-identical output.

No network, no DEM file, no X-Plane install: a hand-built layout, a
constant-DEM stub and the production solver.
"""
from __future__ import annotations

import importlib

import pytest
from shapely.geometry import Polygon

# NOTE the import ORDER: ``auto_patch.pipeline`` first, per the subsystem's
# ``junction_repair`` <-> ``elevation`` cycle note in src/auto_patch/CLAUDE.md.
from auto_patch import config as CFG

Z0 = 12.0
TILE_LAT, TILE_LON = 30, 31
ANCHOR = (30.5, 31.5)


class _Centerline:
    """The minimal shape ``grade_graph.centerline_specs`` reads."""

    def __init__(self, line, is_service=False):
        self.line = line
        self.is_service = is_service
        self.seg_sizes = []
        self.route_line = line


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    """Every test states its own gate; default the module to ON."""
    monkeypatch.setattr(CFG, "FLAT_SITE_FAST_PATH", True, raising=False)


# ── THE EQUIVALENCE TWIN ─────────────────────────────────────────────


# ── THE PARTITION PREDICATE ──────────────────────────────────────────


def _by_ref(layout, plan):
    return {s.ref for s in layout.shapes if id(s) in plan.candidates}


# ── THE ROLE ENUMERATION (role literals are wire-adjacent) ───────────


# ── THE SEAM: senior pins own their value ────────────────────────────


# ── WIRING TWINS (a rename on one side must fail here) ───────────────


# ── THE FLATNESS-CERTIFICATE EXEMPTION (lead ruling 2026-08-10) ─────
#
# ``_build_shape_constraints`` refuses the flatness certificate to any
# shape touching a hard node, because such a node "sits at profile
# values, not the DEM seed".  A born-at-Z0 pin is the one hard family
# that is FALSE of — it sits exactly AT its DEM sample — so it is
# exempted, and the exemption is scoped to THIS family's own pins.  Both
# directions are pinned below.


def test_config_gate_reads_the_env_default():
    """Default ON; ``O4_FLAT_SITE_FAST_PATH=0`` is the kill switch."""
    module = importlib.reload(CFG)
    try:
        assert module.FLAT_SITE_FAST_PATH is True
        assert module.FLAT_SITE_FAST_PATH_QUANTUM_M == 0.01
        assert "FLAT_SITE_FAST_PATH" in module.__all__
    finally:
        importlib.reload(CFG)


# ── DECIMATION (spec §3: VERIFY, do not add machinery) ───────────────

