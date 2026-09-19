"""A cold DEM tile: REFUSED when this build DECLARED it, read CONTEXT-ONLY
when it did not.  ``_warm_tile`` / ``_may_warm`` are GONE.

Spec ``docs/specs/insets-follow-patch-set-spec.md`` §C.6 / §C.1, ruled by
RULINGS 2026-09-18b (the silent pool-child warm is the ~3 h +38-010 class)
and 2026-09-18h (the class-M far-side coupling is measured and accepted).

This file REPLACES ``test_v2coldframe_warms_in_production.py``, which
twinned the deleted mechanism.  Rewritten, not shimmed: the 2026-09-10
ruling it defended ("why wouldn't the app just refresh it?") is now
honoured by ``O4_Vector_Map.ensure_tile_frame`` in the MAIN process after
an explicit boundary choice — never inside the auto-patch pool child,
where no progress ever reached the app.

§E tests 6b and 9.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import dem_production as DP


class _Frame:
    origin = (-12.5, -77.5)          # ⇒ the airport's own cell is (-13, -78)


def _dem(core_hosted: bool = True, allow_degraded: bool = False,
         declared=()) -> DP.ProductionDem:
    d = DP.ProductionDem.__new__(DP.ProductionDem)
    d.core_hosted = core_hosted
    d.allow_degraded = allow_degraded
    d.icao = "SPLP"
    d.elevation_root = "/nonexistent/Elevation_data"
    d.osm_root = "/nonexistent/OSM_data"
    d.provenance = {}
    d._out = lambda line: d.lines.append(line)
    d.lines = []
    d._tiles = {}
    d._required_boxes = {}
    d.declared_tiles = {(-13, -78)} | {tuple(c) for c in declared}
    return d


def _cold(stem="S12W078", base=True):
    return ({"tile_stem": stem, "base_raster_present": base,
             "airports_layer_present": False, "airport_insets_present": False},
            ["NO cached airports OSM layer", "NO airport elevation insets dir"])


# ── the mechanism is GONE (§E test 9) ─────────────────────────────────
def test_warm_tile_and_may_warm_no_longer_exist():
    assert not hasattr(DP.ProductionDem, "_warm_tile")
    assert not hasattr(DP.ProductionDem, "_may_warm")


def test_a_cold_DECLARED_tile_still_refuses_and_fetches_nothing(monkeypatch):
    """The home tile — and any neighbour a boundary choice declared — is
    this build's own frame: cold is a REFUSAL, exactly as before, and
    ZERO calls into the inset fetcher happen on the way there."""
    monkeypatch.setattr(DP, "frame_state", lambda *a, **k: _cold("S13W078"))

    def explode(*a, **k):                       # any fetch at all is the bug
        raise AssertionError("the pool child must never fetch")

    import O4_Airport_Elevation_Insets as INSETS

    monkeypatch.setattr(INSETS, "ensure_insets_for_tile", explode)
    monkeypatch.setattr(INSETS, "ensure_airport_insets", explode)

    d = _dem(core_hosted=True)
    with pytest.raises(DP.ColdDemFrame) as caught:
        d._compose(-13, -78)
    assert "COLD" in str(caught.value)
    assert "TRIED to warm" not in str(caught.value)


# ── class M: the far side is CONTEXT ONLY (§E test 6b) ────────────────
def test_an_UNDECLARED_cold_tile_is_read_context_only(monkeypatch):
    """No refusal, one loud `[dem]` line, `context_only:<stem>` recorded,
    and nothing fetched.  This is the far side of a class-M airport whose
    groundside crosses the line — the case the owner accepted."""
    monkeypatch.setattr(DP, "frame_state", lambda *a, **k: _cold("S12W078"))

    import O4_Airport_Elevation_Insets as INSETS

    def explode(*a, **k):
        raise AssertionError("class M must fetch nothing")

    monkeypatch.setattr(INSETS, "ensure_insets_for_tile", explode)
    import O4_OSM_Utils as OSM

    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer", explode)

    d = _dem(core_hosted=True)
    # The base raster is present, so composition proceeds; stop it right
    # after the decision — the composition itself is not under test.
    monkeypatch.setattr(DP, "frame_state", lambda *a, **k: _cold("S12W078"))
    with pytest.raises(Exception) as caught:
        d._compose(-12, -78)
    assert not isinstance(caught.value, DP.ColdDemFrame)
    assert d.provenance.get("context_only:S12W078")
    assert any("CONTEXT-ONLY" in line for line in d.lines)


def test_no_base_raster_on_the_far_side_yields_no_tile_and_no_refusal(
        monkeypatch):
    """`None` ⇒ `z_many` NaN ⇒ `v.dem_z is None` ⇒ `seam_pins` skips the
    vertex: no pin is invented from nothing."""
    monkeypatch.setattr(DP, "frame_state",
                        lambda *a, **k: _cold("S12W078", base=False))
    d = _dem(core_hosted=True)
    assert d._compose(-12, -78) is None
    assert d.provenance["tile:S12W078"] == "ABSENT"
    assert d.provenance.get("context_only:S12W078")


def test_a_declared_neighbour_is_NOT_context_only(monkeypatch):
    """`boundary_policy="neighbour"` declares the cell, so it goes back to
    being this build's own frame — cold means refuse, not shrug."""
    monkeypatch.setattr(DP, "frame_state", lambda *a, **k: _cold("S12W078"))
    d = _dem(core_hosted=True, declared=[(-12, -78)])
    with pytest.raises(DP.ColdDemFrame):
        d._compose(-12, -78)
    assert "context_only:S12W078" not in d.provenance


def test_the_home_cell_is_declared_without_being_asked_for():
    d = DP.ProductionDem.__new__(DP.ProductionDem)
    d.declared_tiles = {(-13, -78)}
    assert d._is_declared(-13, -78) is True
    assert d._is_declared(-12, -78) is False


# ── the harness path is unchanged ─────────────────────────────────────
def test_the_harness_still_refuses_a_cold_declared_frame(monkeypatch):
    monkeypatch.setattr(DP, "frame_state", lambda *a, **k: _cold("S13W078"))
    d = _dem(core_hosted=False)
    with pytest.raises(DP.ColdDemFrame) as caught:
        d._compose(-13, -78)
    assert "--refresh-data" in str(caught.value)


def test_allow_degraded_records_instead_of_refusing(monkeypatch):
    monkeypatch.setattr(DP, "frame_state",
                        lambda *a, **k: _cold("S13W078", base=False))
    d = _dem(core_hosted=False, allow_degraded=True)
    assert d._compose(-13, -78) is None
    assert d.provenance.get("degraded")
