"""THE RUNWAY CROWN MINIMUM BINDS — generation-binding twin + validator.

Owner ruling ``docs/RULINGS.md`` 2026-08-05 (commit d48bc0a), which
answers standing open question Q5 for one family:

    "RUNWAY CROWNS: generated and bound (this answers open question Q5
     for runways — the crown minimum BINDS on runways; taxiway/apron
     crowns stay recorded-unbound with citations)."

Citations: FAA AC 150/5300-13 Table 3-6 line S-1 and §4.14.2 item 1a
(1.0 % cross-slope minimum); ICAO Annex 14 §3.1.19 (the runway transverse
"should not … be less than 1 per cent except at runway or taxiway
intersections").

WHAT WAS UNBOUND, AND WHY THAT MATTERED.  The crown was GENERATED —
``crown.runway_crown_drop_m`` has always shed the runway edge — but the
minimum was asserted by nothing.  Two independent numbers
(``config.RUNWAY_CROWN_TRANSVERSE`` and the rulesets'
``runway_transverse_min``) happened to both read 0.010, and no instrument
compared them; either could have moved and left every runway crowned
below its own mandated floor with only a code read to notice.  The emit
grid could do it on its own: a 22.4 m half-width crowned to 0.224 m,
rounded to 0.22 m, and realised 0.98 %.
"""
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


_RULESETS = ("faa", "icao")


# ── THE SCOPE THE OWNER RULED ───────────────────────────────────────


# ── THE GENERATION SIDE — the rate comes FROM the law ───────────────


# ══════════════════════════════════════════════════════════════════════
# THE VALIDATOR HALF — the crown's CENSUS READER (S7 escalation, ruled
# 2026-08-14)
# ══════════════════════════════════════════════════════════════════════
# UNTIL NOW THIS FILE WAS THE WHOLE STORY, and that was the gap: the
# minimum was bound ONLY where it is generated.  S7 measured a runway
# emitted dead flat against a declared 0.30 m crown drop censusing ZERO
# rows — the within-shape law re-centres each pair's budget on the
# DESIGNED crown (``grade_law.crown_pair_offset``) and then judges the
# residue against the runway's own transverse CAP, and a 1 % crown sits
# inside a 1.5 % cap by construction.  With the 2026-08-14 clarification
# naming the runway crown as one of the three surviving drainage laws,
# it was a law we could not see.  ``check_grade._check_runway_crown`` is
# the reader; these are its twins, both directions.
#
# HOW THE CROWN IS EMITTED (and so what the reader compares): the runway
# RING carries the crowned surface ``z' − drop`` and the ridge is a
# separate ``o4_feature=crown_spine`` breakline at ``z'``.  The declared
# per-node drop is the axes sidecar's ``crown_drops`` — the SAME field
# the solver built to, which is what lets the reader honour the law's
# own relaxations (rail continuity, the tile-seam taper) instead of
# reporting them as defects.

def _law_reader():
    import importlib.util as _ilu
    root = Path(__file__).resolve().parents[1]
    spec = _ilu.spec_from_file_location(
        "s8_crown_check_grade", root / "tools" / "check_grade.py")
    mod = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


#: The fixture runway: 60 m wide (half-width 30 m, code F), 200 m of it.
_RW_HALF_W = 30.0
_RW_LEN = 200.0
_RW_Z = 100.0


def test_the_crown_family_is_registered():
    """A check ``run_checks`` emits and the register does not name is the
    census-wrapper defect; ``tests/test_harness.py`` asserts the register
    against the emission, and this pins the key the reports quote."""
    cg = _law_reader()
    assert "runway_crown" in {k for k, _t, _b in cg.LAW_FAMILIES}
    assert cg._CROWN_OUT_OF_SCOPE in cg.OUT_OF_SCOPE_CLASSES


def test_the_reader_honours_the_laws_own_relaxations(tmp_path):
    """A node whose drop the law LOWERED (rail continuity, the tile-seam
    taper) is judged at the drop it was given, not at ``rate ×
    half_width`` — which is why the reader reads the declared field
    rather than re-deriving the rate."""
    from conftest import write_synthetic_patch, synthetic_patch_ll
    cg = _law_reader()
    ring = [(-_RW_HALF_W, 0.0, _RW_Z - 0.05), (_RW_HALF_W, 0.0, _RW_Z - 0.05),
            (_RW_HALF_W, _RW_LEN, _RW_Z - 0.05),
            (-_RW_HALF_W, _RW_LEN, _RW_Z - 0.05)]
    osm = write_synthetic_patch(
        tmp_path,
        [{"role": "runway", "ref": "09/27", "ring": ring},
         {"role": "", "closed": False, "o4_feature": "crown_spine",
          "ring": [(0.0, y, _RW_Z) for y in (0.0, 100.0, _RW_LEN)]}],
        sidecar={"ruleset": "icao",
                 "crown_drops": [list(synthetic_patch_ll(x, y)) + [0.05]
                                 for (x, y, _z) in ring]})
    fam = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    assert fam["runway_crown"] == [], (
        "a relaxed 0.05 m declared drop, realised exactly, is lawful — "
        "re-deriving rate x half_width would report the law's own "
        "relaxation as a defect")


