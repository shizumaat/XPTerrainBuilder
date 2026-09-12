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

import dataclasses as _dc

__all__ = ["Cockpit", "COCKPIT_CLASSES", "check_cockpit"]


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
COCKPIT_CLASSES: tuple[str, ...] = ("step", "grade_break", "grade", "keepout")


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

    #: §31 (2) the APPROACH range, in KILOMETRES: the terrain a pilot sees
    #: on final and climb-out.  A visual defect outside the airport
    #: boundary and farther than this from every runway axis is a REPORT.
    approach_km: float


def check_cockpit(cockpit: Cockpit, families, error: type) -> None:
    """The frame's own cross-file rules.

    * the two thresholds are an ORDER, not two independent numbers — the
      motion threshold is the tighter one BY CONSTRUCTION (what the
      aircraft feels is finer than what the pilot sees), and a table that
      inverted them would silently class every motion row as visual-only;
    * the approach range is a real distance;
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
    for key, fam in families.items():
        if fam.cockpit not in COCKPIT_CLASSES:
            raise error(
                f"families.{key}.cockpit: {fam.cockpit!r} is not one of "
                f"{sorted(COCKPIT_CLASSES)} (§31 (6): every family states "
                f"what KIND of thing its rows are)")
