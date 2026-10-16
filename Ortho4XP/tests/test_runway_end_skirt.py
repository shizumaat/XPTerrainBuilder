"""Runway end skirt (inverse RESA) — the law.  (The approach class of an
end is the v2 witness, ``tests/auto_patch_v2/test_runway_witness.py``.)

The skirt governs terrain that DROPS beyond a runway end, mirroring the
Pass C RESA cut that governs terrain that rises.  Regulatory basis and
plan: ``docs/runway_end_skirt_plan.md``.
"""

# ──────────────────────────────────────────────────────────────────────
# Floor profile (lowest lawful surface beyond the runway end)
# ──────────────────────────────────────────────────────────────────────
_STATIONS = [float(d) for d in range(0, 306, 5)]


# ──────────────────────────────────────────────────────────────────────
# _build_filled_skirts — the fill-direction twin of the cut builder
# ──────────────────────────────────────────────────────────────────────
_CAP = 240.0


# REGION RULESETS, phase B: the ``RUNWAY_END_SKIRT_*`` module constants
# ARE the FAA ruleset's values (AC 150/5300-13B §3.16.5), so every test
# below that asserts against them names ``"faa"`` explicitly.  ICAO
# Annex 14 §3.5.10 has NO 61 m near zone — its own behaviour has its own
# twins.  Passing no ruleset resolves to the module default, which is
# ICAO ("everywhere else" is the owner's default).
_FAA = "faa"


# ──────────────────────────────────────────────────────────────────────
# Pass D end-to-end: synthetic-layout harness shared by the emit,
# validator, blast-pad-flank and road-awareness test classes
# ──────────────────────────────────────────────────────────────────────


