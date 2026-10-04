"""THE ROAD'S OWN PATH METRIC — round-5b spec Amendment 1 twins.

Owner ruling 2026-08-28, on lane/hecar5b's measured fork: *"WITHIN-SHAPE
ROAD-FAMILY PAIRS ARE PRICED ALONG THE ROAD'S OWN PATH METRIC (the
route-metric-within-shape precedent extended to the road family), and a
chord that LEAVES the shape's own pavement polygon is the GAP-CHORD class
— never priced as surface grade.  ONE implementation, consumed by both
readers."*

THE COLLISION THESE PIN (measured, lane/hecar5b): the free-road profile
solves a chain's ramp in the PATH coordinate and the within-shape law
priced the result by EUCLIDEAN CHORD, so a path-lawful 8 % ramp across a
U-loop read 8.33-9.11 % — CYXY gained 120 within-shape road rows, every
one of them exactly 8 % x (path / chord).

Hand-computed geometry, no build, no network, no solver.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


# ══════════════════════════════════════════════════════════════════════
# CLAUSE 1 — PATH, NOT CHORD (and the arithmetic that made CYXY's +120)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# CLAUSE 1 (other half) — THE GAP CHORD, BOTH SIDES
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# "ONE IMPLEMENTATION, BOTH READERS" — the census-wrapper law, on a metric
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE GATE
# ══════════════════════════════════════════════════════════════════════

class TestTheGate:

    def test_the_metric_ships_ON_by_owner_order(self):
        """FLIPPED ON with the family (owner 2026-08-29, in-sim pass is
        acceptance; Amendment 9's fourth reader closed the collision)."""
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.ROAD_PATH_METRIC is True
        finally:
            importlib.reload(_fresh)


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 2 CLAUSE 1 — THE PER-STATION CAP: ONE DERIVATION, THREE
# READERS (the census-wrapper law applied to cap granularity)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 9 — THE CENSUS IS THE FOURTH READER OF THE ONE DERIVATION
# (5j measured what its absence costs: +100 rows at BOTH CYXY and SPJC,
#  140 and 104 of them ``lateral_contiguity`` — a road that lawfully
#  solves at 8 % on its free stations and 1 % beside an apron, judged
#  against ONE way-level number.)
# ══════════════════════════════════════════════════════════════════════

def _check_grade():
    """The harness twins' own loader — registering in ``sys.modules``
    before exec is what makes the module's own imports resolve."""
    import importlib.util
    import sys as _sys
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "tools" / "check_grade.py"
    name = "_cg_amend9"
    if name in _sys.modules:
        return _sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestTheFourthReader:

    def test_the_key_is_REGISTERED_so_omission_is_structural(self):
        """It goes through the harness register, so the
        structurally-impossible-omission twins in test_harness.py cover
        it: a key the reader does not supply, or a kwarg the reader does
        not produce, fails there."""
        cg = _check_grade()
        import inspect
        assert cg.SIDECAR_LAW_KEYS["station_caps"] == "station_caps_ll"
        assert "station_caps_ll" in inspect.signature(
            cg.run_checks).parameters


    def test_a_MISSING_key_degrades_loudly_and_deterministically(self):
        """An old patch has no ``station_caps``.  The census must then
        price at the WAY-level cap exactly as before AND say so — never
        quietly report numbers from a different law than the reader
        thinks it is applying."""
        cg = _check_grade()
        import inspect
        src = inspect.getsource(cg._check_lateral_contiguity)
        assert "no sidecar" in src and "station_caps" in src
        assert "pre-Amendment-9 frame" in src
        # the fallback is the way-level cap, unchanged
        assert "_built = eff" in src


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# the test read the SOURCE of a deleted v1 module:
# ``TestPerStationCapUnification.test_reader_2_the_solve_dem_follow_envelope``.
