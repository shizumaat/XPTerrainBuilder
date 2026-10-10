"""The FREE DATUM of a held block (issue #223 round 5; owner 2026-10-02,
RULINGS 2026-10-02ah (1) and the owner's addendum on the reach band).

The datum column is an unknown of the stage-1 solve: the hard two-way
welds (contact = D), the pad's own flat rows and the apron's caps and
anchors decide it jointly, a SOFT preference pulls it toward the apron's
own frontage level (the contacts' pass-1a median), and its hard BOUND is
the INTERSECTION of its frontage contacts' reach bands.  These twins read
``constraints/no_step.hold_interval`` through ``hold_pass`` on the
flat-pad fixture (``test_flatpad128v3``)."""
from __future__ import annotations

import math

import numpy as np

from auto_patch_v2.constraints.no_step import hold_pass
from auto_patch_v2.constraints.platform import HOLD_DATUM_RULING, HOLD_RULING
from auto_patch_v2.solve.design_roles import hard_rulings, pad_flat_rulings
from auto_patch_v2.model.constraints import REACH_GENERATOR, Band, ConstraintSet, Source
from auto_patch_v2.solve import solve_design
from test_flatpad128v3 import _arm, built, law  # noqa: F401


def _datum_rows(hp):
    return [r for r in hp.result.rows if isinstance(r, Band)
            and r.source.ruling.split(" (")[0].strip() in (HOLD_RULING, HOLD_DATUM_RULING)]


def test_one_datum_welds_every_contact_and_the_preference_is_soft(law, built):
    """A block whose frontage the apron CAN meet at one level (this fixture:
    the contacts' pass-1a spread is under the apron's cap over the frontage)
    solves to ONE D with every weld held, the datum equal to the solved
    column (no pin to disagree with), and the preference toward the median
    is a SOFT row — its head in no hard register."""
    from auto_patch_v2.constraints.platform import platform_records
    from auto_patch_v2.model.platform import datum_vertices
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    assert HOLD_DATUM_RULING not in hard_rulings(lw)
    assert HOLD_DATUM_RULING not in pad_flat_rulings(lw)      # stage 1 keeps it
    hp = hold_pass(pm, lw)
    sol, _rep = solve_design(pm, cs, lw, hold=hp)
    z = np.asarray(sol.z, float)
    tol = float(lw.tables.emit.design.hard_tol_m)
    pref = [r for r in _datum_rows(hp)
            if r.source.ruling.split(" (")[0].strip() == HOLD_DATUM_RULING]
    assert pref and all(r.lo == r.hi for r in pref)          # a zero-width preference
    recs = {r["ref"]: r for r in platform_records(pm, lw, z) if r.get("datum") is not None}
    assert recs
    for ref, rec in recs.items():
        dv = datum_vertices(pm, lw)[ref]
        assert abs(rec["datum"] - float(z[dv])) <= 1e-3          # datum == solved column
        assert rec["released"] == 0 and not rec["needs_split"], rec
        assert rec["welded"] == rec["held_contacts"] >= 1
        assert rec["datum_median"] is not None


def test_the_datum_bound_is_the_intersection_of_the_contacts_reach_bands(law, built):
    """Owner addendum 2026-10-02: D is bounded by ∩ (reach band of each
    airside frontage contact) — the SAME ``Band`` rows the apron vertices
    obey, read off the constraint set — so a median-first choice cannot
    come back.  Give the fixture's contacts reach bands and the derived
    bound is exactly their max-lo / min-hi; an empty intersection marks
    the block ``needs_split`` by definition."""
    from auto_patch_v2.model.platform import HELD, datum_vertices
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    hp0 = hold_pass(pm, lw)
    solve_design(pm, cs, lw, hold=hp0)
    (ref, blk), = [(r, b) for r, b in hp0.result.blocks.items()][:1]
    from auto_patch_v2.constraints.pads import airside_vertices
    air = airside_vertices(pm, lw)
    contacts = [c for c in blk["weld"] if c in air][:4]
    assert len(contacts) >= 2
    src = Source(REACH_GENERATOR, "reach band: twin", ())
    bands = [Band(c, 100.0 + i, 110.0 - i, src) for i, c in enumerate(contacts)]
    lo, hi = max(b.lo for b in bands), min(b.hi for b in bands)
    hp = hold_pass(pm, lw)
    solve_design(pm, ConstraintSet.from_rows([*cs.rows(), *bands]), lw, hold=hp)
    dv = datum_vertices(pm, lw)[ref]
    bound = [r for r in _datum_rows(hp) if r.v == dv and "reach" in r.source.inputs]
    assert len(bound) == 1
    assert bound[0].lo == lo and bound[0].hi == hi
    assert HELD[ref]["reach_isect"] == [round(lo, 3), round(hi, 3)]
    assert not HELD[ref]["reach_isect_empty"]
    # an EMPTY intersection: needs_split by definition, no bound row minted
    bands2 = [Band(contacts[0], 105.0, 110.0, src), Band(contacts[1], 90.0, 100.0, src)]
    hp2 = hold_pass(pm, lw)
    solve_design(pm, ConstraintSet.from_rows([*cs.rows(), *bands2]), lw, hold=hp2)
    assert HELD[ref]["reach_isect_empty"]
    assert not [r for r in _datum_rows(hp2) if r.v == dv and "reach" in r.source.inputs]
    assert math.isfinite(HELD[ref]["reach_isect"][0]) or HELD[ref]["reach_isect"][0] is not None
    # spec §57 (3) (ii-e): a reach intersection that CUTS NOTHING of the
    # pair-graph interval states no Band (a row with a cost and no law —
    # measured at KCLT: 580 solve-owned movers from Bands binding nowhere);
    # the read stays in the record
    assert hp.result.stats["datum_reach_bands"] == 1
    wide = [Band(c, -1.0e4, 1.0e4, src) for c in contacts]
    hp3 = hold_pass(pm, lw)
    solve_design(pm, ConstraintSet.from_rows([*cs.rows(), *wide]), lw, hold=hp3)
    assert not [r for r in _datum_rows(hp3) if r.v == dv and "reach" in r.source.inputs]
    assert hp3.result.stats["datum_reach_bands"] == 0
    assert HELD[ref]["reach_isect"] == [-1.0e4, 1.0e4]
