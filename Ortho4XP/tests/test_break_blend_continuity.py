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


# NO MARGIN FIXTURE: the projection enforces the RAW law budgets
# (docs/RULINGS.md 2026-08-05) — the emit-quantization margin and
# ``config.EMIT_QUANTIZATION_MARGIN_M`` are DELETED, so there is
# nothing to zero.  The 0.01 m guarantee lives in
# ``auto_patch.emit_snap``.


# ── the pocket ───────────────────────────────────────────────────────────

CHAIN = 100            # nodes 0..100, budget 1.0 m between neighbours
HIGH = CHAIN + 1       # the contradicting high anchor


# ── (a) the inversion is REPORTED ────────────────────────────────────────


# ── (b) the surviving line is the clamp, and it lands on the CEILING ─────


# ── (c) REPORTED IS NOT FROZEN ───────────────────────────────────────────


# ── (d) the continuity gate is dead ──────────────────────────────────────


def test_the_gate_has_no_reader_left():
    """Grep twin: the flag name may survive in prose, never in a read that
    decides anything (``comment-prose-may-describe-unlanded-state`` cuts
    both ways — a deleted feature must lose its READS, not just its docs)."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1] / "src"
    readers = []
    for path in root.rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.search(r"environ\.get\(\s*[\"']O4_BREAK_BLEND_CONTINUOUS",
                         line):
                readers.append(f"{path}: {line.strip()}")
    assert readers == [], readers
