"""ISSUE #208 -- THE REPLAY'S STAGE BOUNDARY CARRIES THE PLANAR
REGISTRIES (owner RULINGS 2026-10-02m (G); lane ``basepads4``).

THE DEFECT, MEASURED.  ``tools/v2_solve_replay.py`` resumes at
``--from constraints`` by default, which does NOT run
``planar/build.build`` -- and every registry the planar stage mints lives
in a MODULE GLOBAL.  So the generators that read one saw an EMPTY
registry and the replay solved a different problem from the build and
from ``--from planar`` on the SAME capture: §5a relaxed **822 rows
against 108**, CYXY showed 441 movers up to 2.35 m with nothing minted,
KASE read 1,773 nodes against 1,757, the jetway strip armed differently,
and the §2 (1) plane-pad pin had no ``PLANE_PADS`` to mint from at all.
A replay that is not the build's problem cannot adjudicate a mint
against a build reference, which is why #208 blocks this spec's §5.

THE FIX is the capture/replay boundary itself: ``planar_registries()``
copies them at ``--capture`` time (after the arrangement, where they are
full) and ``restore_planar_registries()`` puts them back before anything
reads them.  A resume that DOES re-run the arrangement repopulates them
itself -- ``build_planar`` clears and re-mints every one -- so the
restore is correct on every arm and load-bearing on the later ones.

Hermetic: no corpus, no capture on disk, no network.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "tools")]
RP = importlib.import_module("v2_solve_replay")

from auto_patch_v2.model import base_step as BS
from auto_patch_v2.model import platform as MP

_REGS = (BS.PLANE_PADS, BS.BASE_STEPS, MP.HELD, MP.PLATFORMS, MP.PLATEAUS)


@pytest.fixture(autouse=True)
def _clean():
    for reg in _REGS:
        reg.clear()
    yield
    for reg in _REGS:
        reg.clear()


def _a_plane_pad() -> BS.PlanePad:
    return BS.PlanePad(ref="building2/p1", unit="building2", k=1, dy_m=3.9,
                       y_m=3.9, area_m2=6394.0, verdict="stepped")


def _a_base_step() -> BS.BaseStep:
    return BS.BaseStep(unit="building2", lower_ref="building2",
                       upper_ref="building2/p1", lower_k=0, upper_k=1,
                       declared_step_m=3.9, strip_m2=31.5, strip_width_m=0.5)


def test_every_planar_registry_the_generators_read_is_NAMED():
    """The register is the point: a registry a generator reads but the
    capture does not carry is #208 again, silently.  ``PLANE_PADS`` and
    ``BASE_STEPS`` are this spec's; the other five are where the
    measured 822-vs-108 relaxation came from."""
    labels = {label for label, _m, _a in RP._PLANAR_REGISTRIES}
    assert {"plane_pads", "base_steps"} <= labels
    assert {"held", "platforms", "plateaus", "block_plans",
            "terraces"} <= labels
    for label, mod, attr in RP._PLANAR_REGISTRIES:
        assert RP._registry(label, mod, attr) is not None, label


def test_the_capture_carries_the_plane_pads_and_the_declared_risers():
    """§2 (1)/(3) across the boundary: what the mint registered is what
    the capture holds."""
    BS.PLANE_PADS["building2/p1"] = _a_plane_pad()
    BS.BASE_STEPS.append(_a_base_step())
    got = RP.planar_registries()
    assert "building2/p1" in got["plane_pads"]
    assert len(got["base_steps"]) == 1
    assert got["base_steps"][0].declared_step_m == pytest.approx(3.9)


def test_a_resume_after_the_arrangement_gets_them_BACK():
    """THE #208 BAR.  The registries are emptied -- which is exactly the
    state ``--from constraints`` starts in -- and the capture puts them
    back, so the pin has a registry to mint from and the stage-1 problem
    is the build's."""
    BS.PLANE_PADS["building2/p1"] = _a_plane_pad()
    BS.BASE_STEPS.append(_a_base_step())
    MP.HELD["building2"] = {"conforming": True}
    cap = {"planar_registries": RP.planar_registries()}
    for reg in _REGS:
        reg.clear()
    assert not BS.PLANE_PADS and not BS.BASE_STEPS and not MP.HELD
    counts = RP.restore_planar_registries(cap, "ZZZZ")
    assert BS.PLANE_PADS["building2/p1"].dy_m == pytest.approx(3.9)
    assert BS.BASE_STEPS[0].upper_ref == "building2/p1"
    assert MP.HELD["building2"]["conforming"] is True
    assert counts["plane_pads"] == 1 and counts["base_steps"] == 1
    assert counts["held"] == 1


def test_the_restore_REPLACES_rather_than_accumulating():
    """Two replays in one process must not stack: a registry restored
    twice holds what the capture holds, not twice it."""
    BS.BASE_STEPS.append(_a_base_step())
    cap = {"planar_registries": RP.planar_registries()}
    RP.restore_planar_registries(cap, "ZZZZ")
    RP.restore_planar_registries(cap, "ZZZZ")
    assert len(BS.BASE_STEPS) == 1


def test_a_capture_PREDATING_the_registries_says_so(capsys):
    """The ``capture predates`` rule: a silent zero is how #208 went
    unnoticed, so an old capture is NAMED and nothing is restored."""
    BS.PLANE_PADS["building2/p1"] = _a_plane_pad()
    counts = RP.restore_planar_registries({"icao": "ZZZZ"}, "ZZZZ")
    assert counts == {}
    out = capsys.readouterr().out
    assert "predates" in out and "#208" in out
    assert "building2/p1" in BS.PLANE_PADS
