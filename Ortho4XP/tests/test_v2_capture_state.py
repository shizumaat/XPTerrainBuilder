"""ISSUES #224 / #208 TWIN: THE CAPTURE STATE TRAVELS WITH THE CAPTURE, OR
THE LATE RESUME REFUSES BY FIELD NAME.

``tools/v2_solve_replay.py --capture`` pickles every value the build hands
from one stage to the next.  Four of the build's planar-stage products are
not handed as values at all: they are MODULE GLOBALS the planar stage
fills and the constraint generators read (``model.platform.HELD`` /
``PLATEAUS`` / ``PLATFORMS``, ``model.pad_terrace.TERRACES``;
``planar.overlay.PAD_AIRSIDE`` was the first of the class to travel, owner
RULINGS 2026-09-16b).  ``--from classify|planar`` re-runs
``planar/build.build``, which REFILLS them, so it was faithful by
accident; ``--from shapes|constraints`` re-use the captured map, so they
read every one EMPTY and assembled a DIFFERENT LP from the build's:

* #224 at KCLT against ``sw1005_KCLT``: 65,212 rows vs the build's 49,981,
  columns 8,934 vs 8,876, on an IDENTICAL 22,263-vertex set — the
  difference is in the ROWS, not the map, which is this class exactly.
* #208 at HECA on one capture and one tree: §5a relaxed 822 rows from
  ``--from constraints`` against 108 from ``--from planar``; and at
  CYXY/KASE the replay ARMED two jetway strips the build held disarmed
  (``constraints/jetway_strip`` disarms the strip on a HELD block, and
  with ``HELD`` empty no block is held).

WHAT IS ASSERTED HERE (offline, synthetic, no corpus and no network — the
master verifies the row counts above on the registered KCLT / HECA
captures):

1. THE DEFECT HAS TEETH.  On a synthetic planar case, ``constraints.
   generate`` over the SAME map and the SAME tree gives a DIFFERENT row
   set once the registries are empty — the generator families that read
   them, named.
2. THE RECORD CLOSES IT.  ``collect()`` at the stage boundary, the
   registries emptied as a fresh ``--from constraints`` process has them,
   ``install()`` — and the row set and EVERY row's value are identical to
   the live (``--from planar``) read.
3. THE SNAPSHOT IS DEEP: a generator mutating what it read (``constraints/
   platform`` writes ``HELD[ref]["near_miss_contacts"]``) cannot edit the
   record, so a second arm off one capture starts where the first did.
4. A CAPTURE WITHOUT THE RECORD REFUSES ``--from shapes|constraints`` and
   NAMES every absent field, the stage that fills it and the passes that
   read it; ``--from classify|planar`` is NOT refused (it re-derives
   them).  A record from a NEWER version refuses too.
"""
from __future__ import annotations

import dataclasses as _dc
import importlib.util
import pickle
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "v2_solve_replay.py"

from auto_patch_v2.classify.roles import Cell, Classification      # noqa: E402
from auto_patch_v2.constraints import generate                      # noqa: E402
from auto_patch_v2.law import Law                                   # noqa: E402
from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,  # noqa: E402
                                        SceneryPack, Startup)
from auto_patch_v2.model.frame import Frame                         # noqa: E402
from auto_patch_v2.pipeline import capture_state as CS              # noqa: E402
from auto_patch_v2.planar.build import build                        # noqa: E402

RUN_LEN = 1600.0
HALF_W = 22.5


# ── the synthetic planar case (the shape of ``test_flatpad128v3``'s) ─────

class _Dem:
    """The ground rises 1 % west to east under the apron and the pads, so
    a pad's frontage is not level and the hold has work to do."""

    provenance = {"synthetic": "capture_state"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + (0.01 * x if y > HALF_W else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _airport(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 2 * HALF_W, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    gate = Startup("G1", (0.0, 140.0), 180.0, "gate")
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (gate,), (), (), (), pack, _Dem(), law.ruleset_key)


def _cells():
    """A runway, an apron touching it, a STAND-LINE pad (the plateau) and a
    §20 conforming pad (the held block) — the fixture exercises HELD,
    PLATEAUS and PLATFORMS together."""
    return (
        Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(-300.0, HALF_W, 300.0, 180.0), (),
             None, None, "airside", "apron", {}),
        Cell(2, "building", "padA", _rect(-150.0, 180.0, 150.0, 260.0), (),
             None, None, "airside", "pad", {}),
        Cell(3, "building", "padB", _rect(200.0, 180.0, 240.0, 200.0), (),
             None, None, "airside", "pad", {}),
    )


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _planar(law):
    """ONE planar build — the capture's own stage, which FILLS the
    registries.  A fresh ``Airport`` and a fresh map per arm, so no
    identity-keyed memo of a previous arm can mask the registry read."""
    airport = _airport(law)
    pm, _st = build(airport, Classification(_cells(), (), {}, ()), law)
    return airport, pm


def _rows(cs):
    """Every row as a comparable value: its kind, its generator, its ruling
    and its own fields — the ROW SET AND THE VALUES, not a count."""
    out = []
    for r in cs.rows():
        out.append((type(r).__name__, r.source.generator, r.source.ruling,
                    tuple(sorted((f.name, repr(getattr(r, f.name)))
                                 for f in _dc.fields(r) if f.name != "source"))))
    return out


@pytest.fixture(scope="module")
def live(law):
    """The ``--from planar`` read: build, then generate with the registries
    as the build left them, and the state collected at that boundary."""
    airport, pm = _planar(law)
    state = CS.collect()
    cs, counts, _w = generate(pm, law, airport)
    return _rows(cs), dict(counts), state


# ── 1. the defect has teeth ──────────────────────────────────────────────

def test_an_empty_registry_is_a_different_problem(law, live):
    """#224 / #208's cause, on a synthetic case: the SAME map and tree with
    the registries emptied generate a different row set, in exactly the
    families that read them."""
    rows_live, counts_live, _state = live
    airport, pm = _planar(law)
    CS.clear()                                   # what a fresh process has
    cs, counts, _w = generate(pm, law, airport)
    rows_bare = _rows(cs)
    assert rows_bare != rows_live, (
        "the fixture must be sensitive to the registries, or this twin "
        "proves nothing")
    moved = {k for k in set(counts_live) | set(counts)
             if counts_live.get(k) != counts.get(k)}
    # the families that read HELD / PLATEAUS / PLATFORMS
    assert {"frontage_hold", "platform_plane", "platform_level"} <= moved, moved


# ── 2. the record closes it ──────────────────────────────────────────────

def test_the_capture_state_reproduces_the_planar_read(law, live):
    """THE TWIN THE BRIEF ASKS FOR: a synthetic planar case captured at
    planar and resumed at constraints gives the IDENTICAL row set and
    values as a planar resume."""
    rows_live, counts_live, state = live
    airport, pm = _planar(law)
    # the pickle round trip, then the fresh process, then the install
    state = pickle.loads(pickle.dumps(state))
    CS.clear()
    assert CS.missing(state) == ()
    assert CS.install(state) == tuple(r.field for r in CS.REGISTRIES)
    cs, counts, _w = generate(pm, law, airport)
    assert _rows(cs) == rows_live
    assert counts == counts_live


def test_every_declared_registry_is_carried_and_non_trivial(live):
    """A record that carries a field as an EMPTY container is not a
    carried registry: the fixture must fill every one the twin claims."""
    _r, _c, state = live
    assert state["version"] == CS.CAPTURE_STATE_VERSION
    assert set(state["fields"]) == {r.field for r in CS.REGISTRIES}
    for f in ("held", "plateaus", "platforms", "pad_airside"):
        assert state["fields"][f], f


# ── 3. the snapshot is deep ──────────────────────────────────────────────

def test_the_record_is_not_edited_by_the_arm_that_installs_it(law, live):
    """``constraints/platform`` writes ``HELD[ref]["near_miss_contacts"]``:
    a shallow snapshot would let arm 1 edit arm 2's state through the
    record."""
    _r, _c, state = live
    before = pickle.dumps(state)
    airport, pm = _planar(law)
    CS.clear()
    CS.install(state)
    from auto_patch_v2.model.platform import HELD
    ref = sorted(HELD)[0]
    HELD[ref]["near_miss_contacts"] = ["edited by the arm"]
    HELD["minted by the arm"] = {}
    generate(pm, law, airport)
    assert pickle.dumps(state) == before


# ── 4. the refusal ───────────────────────────────────────────────────────

def test_missing_names_every_declared_field_and_ignores_the_unknown():
    assert CS.missing(None) == tuple(r.field for r in CS.REGISTRIES)
    assert CS.missing({}) == tuple(r.field for r in CS.REGISTRIES)
    part = {"version": CS.CAPTURE_STATE_VERSION,
            "fields": {"held": {"padA": {}}, "a_registry_since_removed": 1}}
    assert "held" not in CS.missing(part)
    assert CS.unknown(part) == ("a_registry_since_removed",)
    assert CS.install(part) == ("held",)           # the unknown field is not installed


def test_a_newer_record_refuses():
    with pytest.raises(ValueError, match="NEWER"):
        CS.install({"version": CS.CAPTURE_STATE_VERSION + 1, "fields": {}})


def test_the_refusal_names_the_field_its_stage_and_its_readers():
    msg = CS.refusal("KCLT", "constraints", "frames/x/KCLT.pkl",
                     ("held", "terraces"), "Re-capture: <command>")
    assert "REFUSED" in msg and "--from constraints" in msg
    for f, mod, filler, reader in (
            ("held", "model.platform.HELD", "planar/platform.py",
             "constraints/jetway_strip.py"),
            ("terraces", "model.pad_terrace.TERRACES", "planar/pad_terrace.py",
             "constraints/pad_fronting.py")):
        assert f in msg and mod in msg and filler in msg and reader in msg
    assert "#208" in msg and "#224" in msg
    assert "--from classify|planar" in msg          # the faithful resume, named
    assert "Re-capture: <command>" in msg


# ── 4b. the refusal through the tool ─────────────────────────────────────

@pytest.fixture(scope="module")
def R():
    spec = importlib.util.spec_from_file_location("_v2_replay_cstate", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_late_resumes_are_the_ones_that_cannot_re_derive(R):
    assert R.LATE_RESUMES == ("shapes", "constraints")


@pytest.mark.parametrize("stage", ["shapes", "constraints"])
def test_a_legacy_capture_refuses_the_late_resume(R, stage, live):
    """A capture written before the record — ``pad_airside`` alone, the
    2026-09-16b spelling — is exactly the pickle #208 and #224 were
    measured on."""
    _r, _c, _s = live
    legacy = {"icao": "KCLT", "pad_airside": {"renode_minted": 20}}
    with pytest.raises(SystemExit) as exc:
        R.install_capture_state(legacy, "KCLT", stage, "frames/x/KCLT.pkl",
                                "Re-capture: <command>", required=False)
    msg = str(exc.value)
    assert "REFUSED" in msg and f"--from {stage}" in msg
    for r in CS.REGISTRIES:
        assert r.field in msg


def test_the_early_resumes_are_not_refused(R, capsys):
    """``--from classify|planar`` re-runs the planar build, which refills
    the registries: a record it does not need is not a refusal."""
    legacy = {"icao": "KCLT", "pad_airside": {"renode_minted": 20}}
    for stage in ("classify", "planar"):
        assert R.install_capture_state(legacy, "KCLT", stage, "x.pkl", "hint",
                                       required=False) == ()
    assert "none installed" in capsys.readouterr().out


def test_a_solved_pickle_without_the_record_refuses_every_instrument(R):
    """``--bank-from``'s emit half reads ``PLATFORMS`` / ``TERRACES``
    through ``pipeline/publication`` and ``--probe-site`` / ``--stage1-dump``
    re-solve under ``hold_pass``, which reads ``HELD``: nothing in those
    paths re-runs the planar stage, so the record is REQUIRED."""
    for stage in ("bank-from", "probe-site", "stage1-dump", "why-from"):
        with pytest.raises(SystemExit, match="REFUSED"):
            R.install_capture_state({"icao": "KCLT"}, "KCLT", stage, "s.pkl",
                                    "hint", required=True)


def test_the_record_installed_through_the_tool_is_announced(R, live, capsys):
    _r, _c, state = live
    CS.clear()
    got = R.install_capture_state({"icao": "ZZZZ", CS.CAPTURE_STATE_KEY: state},
                                  "ZZZZ", "constraints", "c.pkl", "hint")
    assert got == tuple(r.field for r in CS.REGISTRIES)
    out = capsys.readouterr().out
    assert f"capture state v{CS.CAPTURE_STATE_VERSION} installed" in out
    assert "held" in out
