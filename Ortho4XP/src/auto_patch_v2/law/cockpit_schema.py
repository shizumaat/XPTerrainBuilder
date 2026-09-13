"""THE COCKPIT FRAME's schema (owner RULINGS 2026-09-12x/12y;
``design-surface-spec.md`` §31, ``object-placement-spec.md`` §17).

Beside ``model.py`` rather than in it, for the same reason
``terrace_schema`` / ``rebake_schema`` / ``flat_site_schema`` are: the
1,000-line file law (``tests/auto_patch_v2/test_model.py``).  Re-exported
through ``model``, so every importer is unchanged.

NO NUMERIC VALUE LIVES HERE — the three numbers are ``emit.toml
[cockpit]`` and nothing else (``test_law_tables.test_no_numeric_literal_
in_law_python``).  Even the docstrings below name the KEYS, never their
values, because a number written twice is a number that can disagree with
itself.
"""
from __future__ import annotations

import collections.abc as _abc
import dataclasses as _dc

__all__ = ["Cockpit", "COCKPIT_CLASSES", "check_cockpit", "value_at"]


def value_at(tables: object, dotted: str):
    """The VALUE a dotted law path names in ``tables``, or ``None``.

    ``model.resolves``'s sibling, for a key that REFERENCES another law
    value instead of copying it (``emit.cockpit.cliff_grade`` ->
    ``emit.design.bank_slope``, §31 (7) / RULINGS 2026-09-12af: one law,
    one number, no second copy to drift).  Duck-typed over dataclasses and
    mappings so this module still imports nothing from ``model``."""
    obj: object = tables
    for part in str(dotted).split("."):
        if isinstance(obj, _abc.Mapping):
            if part not in obj:
                return None
            obj = obj[part]
        elif _dc.is_dataclass(obj) and hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return None
    return obj


#: §31 (6): the COCKPIT classes a law family may declare.
#:
#: ``step``        a HEIGHT DISCONTINUITY between neighbours (a step,
#:                 joint, tear, stacked node, a vertex standing off its
#:                 neighbour's foot).  Priced at ``motion_step_m`` where
#:                 BOTH sides are rolled-on roles — the aircraft feels it
#:                 — and at ``visual_m`` off them.
#: ``grade_break`` a RATE-OF-CHANGE law (the arc / curve rates): §31 (1)'s
#:                 "a grade break the runway/taxi laws forbid".  A row on
#:                 rolled-on roles is CRITICAL motion by its own law's
#:                 bound; there is no second threshold to apply.
#: ``grade``       a SLOPE excess.  Not one of §31 (1)'s visual shapes
#:                 (cut, rise, seam, float, burial, terrace) and not a
#:                 step: REPORT.
#: ``keepout``     the family measures a thing's PRESENCE in a region,
#:                 not a height at all: REPORT.
#: ``sentinel``    the family measures a value that is NOT GEOMETRY at all —
#:                 a no-data marker or a homogeneous least-squares block's
#:                 0.0 that reached the product (RULINGS 2026-09-13, lane
#:                 ``v2zerocrater``: KCLT's 20 apron vertices at 0.00 over
#:                 217 m ground).  CRITICAL unconditionally: there is no
#:                 threshold to price it against and no view test to pass —
#:                 a hole in the design surface is critical wherever it is.
COCKPIT_CLASSES: tuple[str, ...] = ("step", "grade_break", "grade", "keepout",
                                    "sentinel")


@_dc.dataclass(frozen=True)
class Cockpit:
    """``emit.toml [cockpit]`` — the READING RULE, not a law that moves a
    row.  Every census family measures what it always measured; these
    three numbers say which of its rows the pilot feels, which he sees,
    and which are report."""

    #: §31 (1) MOTION.  A step or ridge over this between welded
    #: neighbours where BOTH sides are surfaces the aircraft rolls on
    #: (the runway family, the taxi family, the apron and its stands —
    #: read from ``precedence.toml``, never a literal list) is CRITICAL.
    motion_step_m: float

    #: §31 (1) VISUAL.  Off those surfaces a cut, rise, seam, float,
    #: burial or terrace under this is invisible to the pilot: REPORTED,
    #: never a gate.  Over it, and in view, it is a defect.
    visual_m: float

    #: §31 (2) THE APPROACH CORRIDOR's LENGTH, in KILOMETRES: how far
    #: beyond each runway threshold, along the extended centreline, the
    #: pilot reads the terrain on final and climb-out.
    approach_km: float

    #: §31 (2) THE APPROACH CORRIDOR's lateral HALF-WIDTH, in METRES
    #: (owner RULINGS 2026-09-12al).  With ``approach_km`` it IS the
    #: corridor — one derivation (``law/approach_corridor.py``), read by
    #: the cockpit block's "in view" test and by §29 (1)'s mouth gate
    #: alike.  A defect outside the airport boundary and outside every
    #: corridor is not seen from an arriving or departing aircraft: a
    #: REPORT, and for a tunnel mouth, raw DEM.
    approach_half_width_m: float

    #: §31 (7) THE CLIFF (RULINGS 2026-09-12af), as a DOTTED LAW PATH, not
    #: a number: a spanned step-family row whose implied grade exceeds the
    #: value this names is a CUT or a RISE, not a slope, and returns to the
    #: bucket it would have had welded.  It points at the design surface's
    #: own bank slope so the two can never drift apart;
    #: ``tables.cliff_grade`` resolves it and the loader refuses a path
    #: that does not name a grade in (0, 1].
    cliff_grade: str

    #: THE SENTINEL FLOOR (RULINGS 2026-09-13, lane ``v2zerocrater``): how
    #: far under the patch's OWN 5th-percentile emitted elevation a vertex
    #: must sit before it is read as a SENTINEL rather than as geometry.
    #: The ``sentinel_elevation`` family's parameter; patch-intrinsic
    #: because the census has no DEM, and measured from a ROBUST floor
    #: because the crater IS the minimum.
    #: §29 (7) THE RUNWAY LATERAL BAND's half-width, in METRES (Fable
    #: 2026-09-13; owner RULINGS 2026-09-13bm (ii)).  The approach
    #: corridor runs BEYOND each threshold and never BESIDE the runway,
    #: so a portal 192 m abeam runway 16R/34L at mid-length — in a
    #: landing pilot's plain view — stood outside every region the mouth
    #: gate had.  The third term is each runway's AXIS grown by this,
    #: built by the SAME ``law/approach_corridor.py`` derivation and read
    #: by the SAME two consumers.  Design: 250 m, the width a pilot on
    #: the runway reads.
    runway_view_half_width_m: float = 250.0

    sentinel_drop_m: float = 50.0


def check_cockpit(cockpit: Cockpit, families, error: type,
                  tables: object = None) -> None:
    """The frame's own cross-file rules.

    * the two thresholds are an ORDER, not two independent numbers — the
      motion threshold is the tighter one BY CONSTRUCTION (what the
      aircraft feels is finer than what the pilot sees), and a table that
      inverted them would silently class every motion row as visual-only;
    * the approach range is a real distance;
    * ``cliff_grade`` is a dotted law path that resolves, in ``tables``, to
      a real grade in (0, 1] and over the motion threshold;
    * EVERY law family states its cockpit class.  A family with none would
      classify silently as REPORT and the owner would never see its rows —
      the census-wrapper defect wearing a reading rule's hat.
    """
    if not 0.0 < cockpit.motion_step_m < cockpit.visual_m:
        raise error(
            f"emit.cockpit: motion_step_m {cockpit.motion_step_m} must be "
            f"> 0 and STRICTLY under visual_m {cockpit.visual_m} (§31 (1): "
            f"the motion threshold is the tighter of the two)")
    if cockpit.approach_km <= 0.0:
        raise error(f"emit.cockpit: approach_km {cockpit.approach_km} must "
                    f"be > 0 (§31 (2): the range a pilot sees on final)")
    if cockpit.approach_half_width_m <= 0.0:
        raise error(
            f"emit.cockpit: approach_half_width_m "
            f"{cockpit.approach_half_width_m} must be > 0 (§31 (2): the "
            f"approach corridor has a width — a zero half-width is a line "
            f"no mouth and no row can stand in)")
    if cockpit.approach_half_width_m >= cockpit.approach_km * 1000.0:
        raise error(
            f"emit.cockpit: approach_half_width_m "
            f"{cockpit.approach_half_width_m} is not under approach_km "
            f"{cockpit.approach_km} (§31 (2): the corridor is what a pilot "
            f"sees AHEAD — a half-width at or over its length is the disc "
            f"the ruling retired, wearing a corridor's name)")
    if cockpit.runway_view_half_width_m <= 0.0:
        raise error(
            f"emit.cockpit: runway_view_half_width_m "
            f"{cockpit.runway_view_half_width_m} must be > 0 (§29 (7): the "
            f"runway lateral band has a width — a zero half-width is a "
            f"line no mouth can stand in)")
    if cockpit.runway_view_half_width_m >= cockpit.approach_half_width_m:
        raise error(
            f"emit.cockpit: runway_view_half_width_m "
            f"{cockpit.runway_view_half_width_m} is not under "
            f"approach_half_width_m {cockpit.approach_half_width_m} "
            f"(§29 (7): the band is what a pilot reads BESIDE the runway, "
            f"a narrower thing than the corridor ahead of it — a band at "
            f"or over the corridor's half-width is the retired disc again)")
    cliff_grade = value_at(tables, cockpit.cliff_grade)
    if not isinstance(cliff_grade, (int, float)):
        raise error(
            f"emit.cockpit: cliff_grade {cockpit.cliff_grade!r} does not "
            f"name a value in the loaded tables (§31 (7): it is a dotted "
            f"law path — the design surface's own bank slope — never a "
            f"second copy of the number)")
    if not 0.0 < float(cliff_grade) <= 1.0:
        raise error(
            f"emit.cockpit: cliff_grade {cockpit.cliff_grade!r} resolves to "
            f"{cliff_grade}, not a grade in (0, 1] (§31 (7))")
    if float(cliff_grade) <= cockpit.motion_step_m:
        raise error(
            f"emit.cockpit: cliff_grade resolves to {cliff_grade}, at or "
            f"under motion_step_m {cockpit.motion_step_m} — the cliff "
            f"escape would swallow every spanned row (§31 (7))")
    for key, fam in families.items():
        if fam.cockpit not in COCKPIT_CLASSES:
            raise error(
                f"families.{key}.cockpit: {fam.cockpit!r} is not one of "
                f"{sorted(COCKPIT_CLASSES)} (§31 (6): every family states "
                f"what KIND of thing its rows are)")
