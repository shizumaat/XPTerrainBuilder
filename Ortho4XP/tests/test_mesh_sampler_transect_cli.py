"""The TRANSECT CLI on ``tools/mesh_elevation_sampler.py`` (round 17c).

Rounds 17/17b/17c all judge the shore and the runway ends by a PROFILE
across the built mesh — "Z0 to the wall then one sample to sea" is a
FACE, "Z0 down over four samples" is the beach ramp the owner ruled
away.  r17b answered that from a scratchpad script; its second use is
the signal to promote it into the tool that already owns the question
(tool discipline, RULINGS 7e90032).

This twins the promotion: the CLI reads the same mesh through the same
sampler, and its STEP annotation — the thing that distinguishes a face
from a ramp — fires on the drop and only on the drop.

Fixture: ``tests/fixtures/mesh/synthetic_fan_three_triangles.mesh``, the
existing hand-written mesh (no new fixture, no network, no build).
"""

from __future__ import annotations

import os
import sys

import pytest

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import mesh_elevation_sampler as MES  # noqa: E402

FIXTURE_MESH_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures", "mesh", "synthetic_fan_three_triangles.mesh")


def _run(capsys, argv):
    assert MES.main(argv) == 0
    return capsys.readouterr().out.splitlines()


class TestTheSweeps:
    def test_a_latitude_sweep_walks_the_mesh(self, capsys):
        lines = _run(capsys, [FIXTURE_MESH_PATH, "--lon", "10.0005",
                              "--lat-range", "50.0001", "50.0005",
                              "--step", "0.0001"])
        assert lines[0].startswith("=== TRANSECT lon 10.00050")
        assert len(lines) == 6                      # header + 5 samples
        assert all(line.strip().startswith("lat ") for line in lines[1:])

    def test_a_longitude_sweep_walks_the_mesh(self, capsys):
        lines = _run(capsys, [FIXTURE_MESH_PATH, "--lat", "50.0002",
                              "--lon-range", "10.0001", "10.0005",
                              "--step", "0.0001", "--label", "WEST SHORE"])
        assert lines[0].startswith("=== WEST SHORE lat 50.00020")
        assert all(line.strip().startswith("lon ") for line in lines[1:])

    def test_points_are_sampled_one_by_one(self, capsys):
        lines = _run(capsys, [FIXTURE_MESH_PATH,
                              "--point", "50.0002", "10.0005",
                              "--point", "50.0003", "10.0005"])
        assert len(lines) == 2

    def test_it_refuses_rather_than_guessing_a_sweep(self):
        with pytest.raises(SystemExit):
            MES.main([FIXTURE_MESH_PATH])


class TestTheStepAnnotation:
    """The face-vs-ramp reading: a drop is annotated once per sample
    pair that crosses the flag, so a FACE shows ONE step and a ramp
    shows several."""

    def test_a_step_is_annotated_and_a_flat_run_is_not(self, capsys):
        # The fixture's elevations run 100 -> 400 m across 0.001 deg, so
        # any real sweep crosses a 1 m flag; a huge flag never fires.
        loud = _run(capsys, [FIXTURE_MESH_PATH, "--lon", "10.0005",
                             "--lat-range", "50.0001", "50.0005",
                             "--step", "0.0001", "--step-flag", "1.0"])
        quiet = _run(capsys, [FIXTURE_MESH_PATH, "--lon", "10.0005",
                              "--lat-range", "50.0001", "50.0005",
                              "--step", "0.0001", "--step-flag", "1e9"])
        assert any("<-- STEP" in line for line in loud)
        assert not any("<-- STEP" in line for line in quiet)

    def test_the_step_names_the_signed_metres(self, capsys):
        lines = _run(capsys, [FIXTURE_MESH_PATH, "--lon", "10.0005",
                              "--lat-range", "50.0001", "50.0005",
                              "--step", "0.0001", "--step-flag", "1.0"])
        flagged = [line for line in lines if "<-- STEP" in line]
        assert flagged
        for line in flagged:
            marker = line.split("<-- STEP")[1].strip()
            assert marker.endswith("m")
            assert marker[0] in "+-"
            assert abs(float(marker[:-2])) >= 1.0


class TestItIsTheSAMESAMPLER:
    """One instrument, never a second opinion: the CLI prints exactly
    what ``MeshElevationSampler.elevation_at`` returns."""

    def test_the_printed_value_is_the_samplers_own(self, capsys):
        sampler = MES.MeshElevationSampler(
            FIXTURE_MESH_PATH, (10.0, 50.0, 10.001, 50.001))
        expected = sampler.elevation_at(50.0003, 10.0005)
        lines = _run(capsys, [FIXTURE_MESH_PATH,
                              "--point", "50.0003", "10.0005"])
        assert "{:.3f}".format(expected) in lines[0]
