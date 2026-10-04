"""Kill-prep round — the three fixes that unblock quarantine deletion.

Spec: ``docs/specs/kill-prep-round-spec.md`` (+ the owner amendment of
2026-08-03 on §1: portion-only absorption, mandatory mouth cuts, the SPINE
remains, cap constants are owner-only).  Owner rulings: ``docs/RULINGS.md``
(lateral-contiguity absorption is class-universal; feasibility is
guaranteed; quarantine is unauthorized; law compliance, not
instrument-zero).

Each gate is tested on BOTH sides — the behaviour it introduces and the
inertness of its off state — because every one of them is default-OFF and
ships that way this round.
"""
from __future__ import annotations

import importlib
import types

import numpy as np
from shapely.geometry import Polygon


# ═════════════════════════════════════════════════════════════════════
# helpers
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    return types.SimpleNamespace(shapes=list(shapes))


# ═════════════════════════════════════════════════════════════════════
# §1 — service↔lot absorption (the emitter half)
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §1 — the service DEM-follow envelope (the second-authority half)
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §2 — the triangle-plane demotion
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §3 — the raster seed-cell fix
# ═════════════════════════════════════════════════════════════════════

class TestSeedCellExactness:
    """One 3 m cell can hold two attachments metres apart; collapsing them
    prices the route leg between them at ZERO and manufactures a band
    inversion (HEAZ: four of four observed inversions reproduced)."""

    CXS = np.array([1.5, 4.5, 7.5])
    CYS = np.array([1.5, 4.5, 7.5])
    CAP = np.full((3, 3), 0.015)


    def test_the_gates_default_on_after_the_kill_half_flip(self,
                                                            monkeypatch):
        """FLIPPED 2026-08-04 (spec ``docs/specs/kill-half-spec.md`` §1).

        All three of this round's gates ship ON; the evidence is the
        kill-prep measurement recorded in ``495660a`` (HEAZ band inversions
        10 → 3 / 0.0569 m → 0.0003 m, CYXY break nodes 52 → 16, every
        runway vertex byte-identical under the seed fix and the triangle
        demotion).  The env override still restores the pre-flip default,
        which is what the second half asserts."""
        import auto_patch.config as cfg
        for name in ("O4_BAND_SEED_EXACT", "O4_SERVICE_LOT_ABSORPTION",
                     "O4_TRIANGLE_PLANE_REPORTS"):
            monkeypatch.delenv(name, raising=False)
        importlib.reload(cfg)
        assert cfg.BAND_SEED_EXACT is True
        assert cfg.SERVICE_LOT_ABSORPTION is True
        assert cfg.TRIANGLE_PLANE_REPORTS is True
        # ``O4_SERVICE_LOT_ABSORPTION`` is DELETED (owner 2026-08-05, no
        # gates), and ``O4_TRIANGLE_PLANE_REPORTS`` followed it in the
        # integration sweep the same day: neither retired env name can
        # restore its pre-flip default any more.  Only BAND_SEED_EXACT
        # still carries an override.
        for name in ("O4_BAND_SEED_EXACT", "O4_SERVICE_LOT_ABSORPTION",
                     "O4_TRIANGLE_PLANE_REPORTS"):
            monkeypatch.setenv(name, "0")
        importlib.reload(cfg)
        assert cfg.BAND_SEED_EXACT is False
        assert cfg.SERVICE_LOT_ABSORPTION is True
        assert cfg.TRIANGLE_PLANE_REPORTS is True
