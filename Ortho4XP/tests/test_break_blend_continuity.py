"""THE BREAK BLEND IS DELETED — the twin of ``kill-half-spec.md`` §2.

This file used to pin the CONTINUOUS break-blend weight
(``docs/specs/break-blend-continuity-spec.md``, gate
``O4_BREAK_BLEND_CONTINUOUS``): a node whose envelope interval was
inverted took a distance-weighted value ``hi + (lo−hi)·t`` and was then
frozen out of every sweep, and that spec's work was making ``t``
continuous so the painted pocket at least carried no steps.

REWRITTEN 2026-08-04.  Owner law (docs/RULINGS.md, feasibility-is-
guaranteed, ESCALATED 2026-08-01): "quarantine is UNAUTHORIZED; break
regions are law defects to attribute, never a legitimate answer."  The
blend, its continuity gate and the freeze are gone; what this file pins is
what replaced them:

  (a) an inverted interval is REPORTED through ``broken_out`` and nothing
      else — the A2/A3/A4/B3 minters keep their report halves;
  (b) the node takes the ordinary envelope clamp, which for ``lo > hi``
      evaluates to the CEILING — the deleted blend's own ``t → 0`` end, so
      the value stays inside the range the blend could have produced;
  (c) the node is NOT frozen: it sweeps like any free node.  The freeze is
      the half that held free nodes immovable through the LATE airside
      projection (measured at HECA: 375 carried, 165 of them not hard);
  (d) ``O4_BREAK_BLEND_CONTINUOUS`` is dead — setting it changes nothing
      and no module reads it;
  (e) the SCOPED final projection's own ``pre_broken`` set (gate
      ``O4_SCOPED_FINAL_PROJECTION``, default "0") still freezes what its
      caller hands it.  That machinery is not this spec's to kill, and the
      contrast is what proves (c) is a measured behaviour change rather
      than an absence.

A materially inverted FINAL band is a BUILD ERROR now instead
(``building_feasibility.assert_no_final_band_inversion``, spec §3, with
its own twin in ``test_final_band_inversion.py``).

THE POCKET (the same frame the continuity spec used, so the two histories
line up).  A 101-node chain, budget 1.0 m per step, hard LOW anchors at
both ends (node 0 at 0.0 m, node 100 at 21.0 m) and one hard HIGH anchor
(node 101 at 200.0 m) welded to the middle node with a 20 m budget.  Every
free node is inverted: its floor (from the high anchor) is ~130-180 m
above its ceiling (from the nearer low anchor).  On a real airport this
cannot survive to the final band — that is exactly what §3's error
asserts — so this frame exists only to exercise the inverted branch.
"""
import pytest

import auto_patch.config as cfg
from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)


@pytest.fixture(autouse=True)
def _zero_emit_margin(monkeypatch):
    monkeypatch.setattr(cfg, "EMIT_QUANTIZATION_MARGIN_M", 0.0)


# ── the pocket ───────────────────────────────────────────────────────────

CHAIN = 100            # nodes 0..100, budget 1.0 m between neighbours
HIGH = CHAIN + 1       # the contradicting high anchor


def _pocket():
    edges = [(i, i + 1, 1.0) for i in range(CHAIN)]
    edges.append((CHAIN // 2, HIGH, 20.0))
    elev = [100.0] * (HIGH + 1)
    elev[0] = 0.0
    elev[CHAIN] = 21.0
    elev[HIGH] = 200.0
    return [{"edges": edges}], elev, {0, CHAIN, HIGH}


def _run(elev, sc, hard, **kw):
    out = list(elev)
    broken: set = set()
    rem, _both_hard = feasibility_project(
        out, sc, hard, force_scalar=True, max_iters=4000,
        broken_out=broken, **kw)
    return out, broken, rem


# ── (a) the inversion is REPORTED ────────────────────────────────────────

def test_the_inversion_is_reported_through_broken_out():
    sc, elev, hard = _pocket()
    _out, broken, _rem = _run(elev, sc, hard)
    assert broken == set(range(1, CHAIN)), (
        "every free chain node is inverted in this frame, and every one of "
        "them must still be REPORTED")
    assert not (broken & hard), "a hard node is never reported inverted"


# ── (b) the surviving line is the clamp, and it lands on the CEILING ─────

def test_an_inverted_band_node_is_clamped_to_its_ceiling():
    """With slack budgets the sweeps have nothing to do, so what survives
    IS the clamp — and for ``lo > hi`` it must be ``hi``."""
    loose = [{"edges": [(0, 1, 100.0), (1, 2, 100.0), (2, 3, 100.0)]}]
    band = [None, (30.0, 20.0), (30.0, 40.0), None]   # node 1 inverted 10 m
    out, broken, _rem = _run([0.0, 0.0, 0.0, 50.0], loose, {0, 3},
                             env_band=band)
    assert broken == {1}
    assert out[1] == pytest.approx(20.0), (
        "the inverted node takes its CEILING, not a blend between the two")
    assert out[2] == pytest.approx(30.0), "the feasible node clamps as ever"


# ── (c) REPORTED IS NOT FROZEN ───────────────────────────────────────────

def test_a_reported_node_still_sweeps():
    sc, elev, hard = _pocket()
    out, broken, _rem = _run(elev, sc, hard)
    kept_at_clamp = sum(1 for i in broken if out[i] == pytest.approx(100.0))
    assert kept_at_clamp < len(broken), (
        "every reported node was left exactly where the clamp put it — "
        "that is the freeze this round deleted")
    assert out[0] == 0.0 and out[CHAIN] == 21.0 and out[HIGH] == 200.0, (
        "hard anchors never move")


def test_the_scoped_pre_broken_quarantine_still_freezes():
    """CONTRAST (e) — and the proof that (c) measures something."""
    sc, elev, hard = _pocket()
    free_out, _b, _r = _run(elev, sc, hard)
    frozen_out, _b2, _r2 = _run(elev, sc, hard, pre_broken={1, 2, 3})
    # ``pre_broken`` merges AFTER the envelope pass (documented ordering),
    # so a frozen node keeps the CLAMP's value — node 1's ceiling is the
    # hard anchor at 0.0 plus one 1.0 m budget — and never sweeps off it.
    assert frozen_out[1] == pytest.approx(1.0), (
        "a pre_broken node stays at the value the clamp left it")
    assert free_out[1] != pytest.approx(frozen_out[1]), (
        "the two paths must differ — otherwise nothing was proved")


# ── (d) the continuity gate is dead ──────────────────────────────────────

@pytest.mark.parametrize("value", ["0", "1"])
def test_the_continuity_gate_is_dead(monkeypatch, value):
    sc, elev, hard = _pocket()
    monkeypatch.setenv("O4_BREAK_BLEND_CONTINUOUS", value)
    on, on_broken, on_rem = _run(elev, sc, hard)
    monkeypatch.delenv("O4_BREAK_BLEND_CONTINUOUS")
    off, off_broken, off_rem = _run(elev, sc, hard)
    assert on == off and on_broken == off_broken and on_rem == off_rem, (
        "O4_BREAK_BLEND_CONTINUOUS died with the blend it weighted")


def test_the_gate_has_no_reader_left():
    """Grep twin: the flag name may survive in prose, never in a read that
    decides anything (``comment-prose-may-describe-unlanded-state`` cuts
    both ways — a deleted feature must lose its READS, not just its docs)."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1] / "src"
    readers = []
    for path in root.rglob("*.py"):
        for line in path.read_text().splitlines():
            if re.search(r"environ\.get\(\s*[\"']O4_BREAK_BLEND_CONTINUOUS",
                         line):
                readers.append(f"{path}: {line.strip()}")
    assert readers == [], readers
