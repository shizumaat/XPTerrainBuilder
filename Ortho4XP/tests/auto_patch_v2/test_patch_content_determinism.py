"""Step reuse chains the mesh on the airport patch's CONTENT (#837): that
only helps when the same inputs write the same patch.  This twin builds
the synthetic ZZZZ airport of ``test_m4`` (planar map, generators, design
solve, emit) in two fresh interpreters with different hash seeds and
different run stamps (``o4_code`` / ``o4_engine``), and asserts the
patches differ in those stamps alone: the stamp-free content digest
``O4_Step_Reuse`` keys on is equal.

A real airport's determinism is the master's check on one tile build.
"""

from __future__ import annotations

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "..", "..", "src")
sys.path.insert(0, _SRC)

from auto_patch import provenance  # noqa: E402


def build_patch(out_dir: str, code: str) -> str:
    """The ZZZZ patch written into ``out_dir``, stamped ``code``; its path."""
    from test_m4 import _PlaneDem, _cells, _ways

    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.emit.osm_adapter import write_patch
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.pipeline.publication import publication
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.planar.structures import build_structures
    from auto_patch_v2.solve import solve_design

    law = Law.for_airport("ZZZZ")
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    runway = Runway("09/27", 45.0, 1, ends, 3, "D")
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (runway,), (), (), {}, (),
                      (), (), (), _ways(), (), (),
                      SceneryPack("fixture", "apt.dat", "0", (), ()),
                      _PlaneDem(), law.ruleset_key)
    classification = Classification(tuple(_cells()), (), {}, ())
    build_structures(airport, classification, law)
    planar, _stats = build(airport, classification, law)
    constraints, _counts, _w = generate(planar, law, airport)
    solution = solve_design(planar, constraints, law)[0]
    surface = graded_surface(planar, law, solution, frame.origin, frame.crs, {})
    paths = write_patch(surface, law, out_dir,
                        publication(planar, law, airport, solution.z),
                        {"o4_code": code, "o4_engine": "engine-" + code})
    return str(paths.patch)


def _build_in_a_fresh_interpreter(out_dir: str, code: str, seed: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED=seed,
               PYTHONPATH=os.pathsep.join([_HERE, _SRC]))
    script = ("import sys, test_patch_content_determinism as t; "
              "print(t.build_patch(sys.argv[1], sys.argv[2]))")
    done = subprocess.run([sys.executable, "-c", script, out_dir, code],
                          env=env, capture_output=True, text=True,
                          encoding="utf-8", timeout=600)
    assert done.returncode == 0, done.stderr[-3000:]
    return done.stdout.strip().splitlines()[-1]


def test_the_same_inputs_write_the_same_stamp_free_patch(tmp_path):
    first = _build_in_a_fresh_interpreter(str(tmp_path / "a"), "aaaa", "1")
    second = _build_in_a_fresh_interpreter(str(tmp_path / "b"), "bbbb", "2")
    with open(first, "rb") as a, open(second, "rb") as b:
        assert a.read() != b.read()                 # the run stamps differ
    assert provenance.content_digest(first) == provenance.content_digest(second)
