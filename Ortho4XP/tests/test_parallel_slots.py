"""Tests for the machine-aware "0 = Auto" slot resolution
(docs/specs/parallel-tile-builds.md §2, extended 2026-07-16).

Each parallelism knob resolves through :mod:`O4_Parallel_Utils` with the
formula its bottleneck warrants: tile builds bind on cores AND memory,
DDS conversion on cores, downloads on the network (a fixed Auto).
Headless, no network.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

import O4_Parallel_Utils as PARALLEL_UTILS


def _machine(monkeypatch, cores, memory_gigabytes, available_gigabytes=None):
    monkeypatch.setattr(
        PARALLEL_UTILS, "machine_core_count", lambda: cores
    )
    monkeypatch.setattr(
        PARALLEL_UTILS, "machine_memory_gigabytes",
        lambda: float(memory_gigabytes),
    )
    if available_gigabytes is None:
        available_gigabytes = memory_gigabytes
    monkeypatch.setattr(
        PARALLEL_UTILS, "machine_available_memory_gigabytes",
        lambda: float(available_gigabytes),
    )


# ---------------------------------------------------------------------
# Build slots: the logical core count, bounded by how many workers
# 80 % of AVAILABLE memory could ever admit at ~2 GB each (revised
# 2026-07-30, docs/specs/apron-string-and-scheduling-spec.md §A.2 —
# remote pressure is bounded by the orchestrator's class caps and memory
# by its per-step projection, so slots buy compute parallelism only).
# Explicit settings are honoured verbatim.
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "cores,available,expected",
    [
        (16, 64, 16),   # big workstation: cores bind (memory allows 25)
        (18, 128, 18),  # the machine of the 2026-07-30 defect report
        (10, 32, 10),   # typical laptop: cores bind
        (12, 6, 2),     # memory binds: 6 * 0.8 // 2 = 2
        (16, 10, 4),    # memory binds: 10 * 0.8 // 2 = 4
        (4, 8, 3),      # small machine: 8 * 0.8 // 2 = 3
        (2, 4, 1),      # ...and floors at 1
        (64, 512, 64),  # no Auto ceiling any more: cores are the answer
    ],
)
def test_auto_build_slots(monkeypatch, cores, available, expected):
    _machine(monkeypatch, cores, available, available)
    assert PARALLEL_UTILS.effective_build_slots(0) == expected


def test_auto_build_slots_floor_at_one(monkeypatch):
    """A machine reporting almost no free memory still builds one tile."""
    _machine(monkeypatch, 8, 32, 0.5)
    assert PARALLEL_UTILS.effective_build_slots(0) == 1


def test_explicit_build_slots_pass_through(monkeypatch):
    _machine(monkeypatch, 4, 8, 2)  # auto would say 1
    assert PARALLEL_UTILS.effective_build_slots(3) == 3
    assert PARALLEL_UTILS.effective_build_slots("2") == 2
    assert PARALLEL_UTILS.effective_build_slots(8) == 8


def test_available_memory_probe_is_sane():
    """The probe answers a positive number no larger than physical RAM
    (the fallback IS physical RAM when the platform will not say)."""
    available = PARALLEL_UTILS.machine_available_memory_gigabytes()
    assert available > 0.0
    assert available <= PARALLEL_UTILS.machine_memory_gigabytes() + 1e-6


# ---------------------------------------------------------------------
# Convert slots: cores - 2, clamped to 2..16, at FULL width even with
# concurrent sibling builds (2026-07-17 ruling: the operating system
# arbitrates processor contention — no per-tile rationing).
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "cores,expected",
    [(10, 8), (4, 2), (2, 2), (32, 16)],
)
def test_auto_convert_slots(monkeypatch, cores, expected):
    _machine(monkeypatch, cores, 32)
    monkeypatch.delenv(
        PARALLEL_UTILS.PARALLEL_SIBLINGS_ENVIRONMENT_KEY, raising=False
    )
    assert PARALLEL_UTILS.effective_convert_slots(0) == expected


def test_auto_convert_slots_ignore_sibling_count(monkeypatch):
    """Sibling tiles no longer shrink the conversion pool — processor
    contention is the operating system's to arbitrate."""
    _machine(monkeypatch, 16, 64)
    monkeypatch.setenv(
        PARALLEL_UTILS.PARALLEL_SIBLINGS_ENVIRONMENT_KEY, "4"
    )
    assert PARALLEL_UTILS.effective_convert_slots(0) == 14


def test_explicit_convert_slots_pass_through(monkeypatch):
    _machine(monkeypatch, 32, 32)
    monkeypatch.setenv(
        PARALLEL_UTILS.PARALLEL_SIBLINGS_ENVIRONMENT_KEY, "4"
    )
    assert PARALLEL_UTILS.effective_convert_slots(4) == 4


# ---------------------------------------------------------------------
# Download slots: network-bound, Auto is a fixed two per tile
# ---------------------------------------------------------------------
def test_auto_download_slots_is_two_regardless_of_cores(monkeypatch):
    monkeypatch.delenv(
        PARALLEL_UTILS.PARALLEL_SIBLINGS_ENVIRONMENT_KEY, raising=False
    )
    _machine(monkeypatch, 32, 128)
    assert PARALLEL_UTILS.effective_download_slots(0) == 2
    _machine(monkeypatch, 2, 4)
    assert PARALLEL_UTILS.effective_download_slots(0) == 2


def test_auto_download_slots_keep_full_width_with_siblings(monkeypatch):
    """Sibling tiles no longer halve the per-tile download streams —
    commercial imagery hosts take a handful of streams comfortably and
    the orchestrator's imagery class cap bounds concurrent tiles."""
    monkeypatch.setenv(
        PARALLEL_UTILS.PARALLEL_SIBLINGS_ENVIRONMENT_KEY, "4"
    )
    assert PARALLEL_UTILS.effective_download_slots(0) == 2
    assert PARALLEL_UTILS.effective_download_slots(3) == 3


def test_explicit_download_slots_pass_through():
    assert PARALLEL_UTILS.effective_download_slots(1) == 1
    assert PARALLEL_UTILS.effective_download_slots(4) == 4


# ---------------------------------------------------------------------
# Probes behave on this platform; session + settings wiring
# ---------------------------------------------------------------------
def test_machine_probes_return_positive_values():
    assert PARALLEL_UTILS.machine_core_count() >= 1
    assert PARALLEL_UTILS.machine_memory_gigabytes() > 0.0


def test_session_resolves_auto_through_configuration(monkeypatch):
    from o4_engine import session as SESSION

    _machine(monkeypatch, 16, 64)
    import O4_Config_Utils as CFG

    monkeypatch.setattr(CFG, "max_build_slots", 0, raising=False)
    assert SESSION._configured_build_slots() == 16
    monkeypatch.setattr(CFG, "max_build_slots", 1, raising=False)
    assert SESSION._configured_build_slots() == 1


def test_settings_model_shows_auto_label():
    import O4_Settings_Model as SM

    setting = SM.get_setting("max_build_slots")
    assert setting is not None
    assert setting.default == "0"
    assert setting.label_for("0").startswith("Auto")
