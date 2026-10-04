"""Adjacent-ground LATERAL grade law — the corridor off a pavement edge.

The lateral generalization of the runway-END skirt: ground beside a paved
surface is a two-zone-plus-ungraded CORRIDOR of lawful height offsets relative
to the pavement-edge elevation.  Regulatory basis, the four Noah rulings and
the slice plan: ``docs/adjacent_ground_grade_law_plan.md``.

These tests pin the corridor's exact bounds at representative distances for
each role/code, the mandatory-DOWN direction (a flat surround is OUTSIDE the
corridor), the zone-3 unbounded floor (cliffs lawful), and — the load-bearing
design detail — CONTINUITY of both bounds across the zone boundaries.
"""
import pytest

from auto_patch.config import (
    APRON_EDGE_WALL_MIN_DROP_M,
    taxiway_strip_graded_half_width_for_letter,
)


# ── THIS FILE IS THE PRE-W2 CORRIDOR, HELD AS THE FLAG-OFF ARM ────────
# W2 (fabric-phase-b-spec.md) changed this law on purpose: reg-set
# ruling 1 drops the ICAO mandatory-DOWN graded strip, F-10 gives the
# taxiway/apron edge its own lip family, and ruling 4 retires the apron
# surround and the service-road shadow outright.  Every assertion below
# was written against the pre-W2 corridor and still certifies something
# load-bearing — the byte-identity of each flag's OFF arm — so it is
# PINNED to that world here rather than rewritten.  The successor
# behaviour (the ON arm, which is the default build) has its own twins
# in ``tests/test_fabric_phase_b.py``.
@pytest.fixture(autouse=True)
def _pre_w2_corridor(monkeypatch):
    for env in ("O4_FABRIC_W2_ICAO_STRIP_AUTHORITY", "O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY",
                "O4_FABRIC_W2_RETIRE_APRON_SURROUND",
                "O4_FABRIC_W2_RETIRE_APRON_EDGE_WALLS",
                "O4_FABRIC_W2_RETIRE_SERVICE_SHADOW"):
        monkeypatch.setenv(env, "0")


class TestTaxiwayGradedBand:

    def test_code_letter_keys_the_graded_width(self):
        """Narrow letters get a narrower graded band (OMGWS table)."""
        assert taxiway_strip_graded_half_width_for_letter("A") == 10.25
        assert taxiway_strip_graded_half_width_for_letter("F") == 22.0
        # Unknown/None letter falls back to code C (12.5 m), never a D-F width.
        assert taxiway_strip_graded_half_width_for_letter(None) == 12.5
        assert taxiway_strip_graded_half_width_for_letter("Z") == 12.5


# ──────────────────────────────────────────────────────────────────────
# Apron edges — 3 m shoulder (1-3 % down) then zone-3 immediately
# ──────────────────────────────────────────────────────────────────────
class TestApron:


    def test_wall_threshold_constant_exists(self):
        """Ruling 3: a retaining-wall face replaces fill past a deep drop.
        The threshold is a named single-source constant (the emitter, slice 3,
        consumes it)."""
        assert APRON_EDGE_WALL_MIN_DROP_M == pytest.approx(1.5)


