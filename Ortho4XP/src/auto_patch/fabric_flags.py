"""THE FABRIC MODEL Phase B — the FLAG REGISTRY (W2 + W3).

Charter: ``docs/specs/fabric-phase-b-spec.md`` W2/W3, executed as the
owner's BATCH PLAN — every change lands behind its own named DEFAULT-ON
flag, all of them at once, and bisection is the safety net.  The rule the
owner stated: *a change that is not individually disable-able is a
defect*.  So this module is the one place the flags exist, and every
consumer asks it rather than reading ``os.environ`` on its own — a flag
spelled at its call site is a flag no registry twin can find.

HOW A FLAG BEHAVES
------------------
Every entry is DEFAULT-ON (``"1"``).  Setting its environment variable to
``"0"`` restores the pre-W2 behaviour of THAT ONE CHANGE and nothing
else; the OFF arm of a flag is byte-identical to the tree before its
commit (that is the per-flag identity twin the batch plan requires).
Anything other than ``"0"`` is ON, so a typo fails safe *towards the new
default* rather than silently reverting production.

WHY EACH FLAG EXISTS — the retire/flip ledger, machine-readably
---------------------------------------------------------------
``item`` names the row in ``docs/specs/fabric-model-reg-set.md`` §5.1
(T1…T8) or ``docs/RULINGS.md`` 2026-08-08 reg-set ruling it executes, so
a reader can go from a build's log line to the authority that ordered the
change without a search.

NOT IN W2 (recorded here so their absence is a decision, not an
oversight).  Reg-set §5.1 also retires **T6** (the adjacent-ground
DAYLIGHT slope limit, ``ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT`` /
``grade_law.adjacent_ground_supported_depths``) and **T7** (the flat
lateral clearance shadow, ``CLEARANCE_LATERAL_MAX_SLOPE`` /
``clearance.emit_surface_clearance_cuts`` pass A3).  Neither is a band, a
ring, a wall or a feather — T6 is a SUPPORT limiter that still governs
the reg strip bands this round KEEPS, and T7 is a clearance CUT, not
shaped ground — so both sit outside W2's charter sentence ("non-reg
adjacent-ground bands/rings/walls/feather everywhere") and are left for
the round that owns them.  Retiring T6 while FAA strip bands still emit
would remove the knife-slot guard from geometry that is still dense.
"""

from __future__ import annotations

import os
import dataclasses as _dc

__all__ = [
    "Flag",
    "FLAGS",
    "FLAG_INDEX",
    "on",
    "off",
    "registry_report",
]


@_dc.dataclass(frozen=True)
class Flag:
    """One named, default-ON W2/W3 change.

    ``env`` is the environment variable; ``what`` says what setting it to
    ``"0"`` puts back; ``item`` cites the authority row that ordered it.
    """

    env: str
    what: str
    item: str
    default: str = "1"

    def __post_init__(self):
        # NAMESPACED ``O4_FABRIC_W*`` on purpose: ``O4_W2_BANDS`` is an
        # UNRELATED 2026-06 dev flag (the clean-bands solver work, whose
        # own "W2" is a different workstream entirely), and a build log
        # showing two different W2s side by side is a log nobody can
        # read.  The prefix is also what makes the registry's
        # "every Phase-B flag in source is registered" audit exact.
        if not self.env.startswith(("O4_FABRIC_W2_", "O4_FABRIC_W3_")):
            raise ValueError(
                f"{self.env!r}: a Phase-B flag is named O4_FABRIC_W2_* or "
                f"O4_FABRIC_W3_* so a build log can be read without this "
                f"file, and so the audit cannot collide with O4_W2_BANDS")
        if self.default != "1":
            raise ValueError(
                f"{self.env!r}: every Phase-B flag is DEFAULT-ON (the batch "
                f"plan lands the world and bisects backwards)")


FLAGS = (
    # ── W2 · the emission switch ──────────────────────────────────────
    Flag(env="O4_FABRIC_W2_SPARSE_ALL",
         what="sparse lawful emission is scoped back to the two declared "
              "Phase-A proof clusters (HECA -10447, the CYXY hillside "
              "group) instead of every pavement and pad",
         item="fabric-phase-b-spec.md W2 — 'the validated gate, "
              "generalized'; the Phase A mechanics verbatim"),
    Flag(env="O4_FABRIC_W2_RETIRE_STATIONING",
         what="the generic 60 m stationing pass (conformance."
              "densify_long_edges) runs on sparse shapes again",
         item="reg-set §5.1 T8 — stationing density beyond the adequate "
              "spine/curve floor; no standard specifies vertex density"),
    Flag(env="O4_FABRIC_W2_RETIRE_FANS",
         what="apron fan zones are planned, split and panelised again",
         item="reg-set §5.1 T1 + RULINGS 2026-08-08 THE FABRIC MODEL "
              "scope answer 1 — 'Fan zones RETIRE OUTRIGHT'"),
    Flag(env="O4_FABRIC_W2_RETIRE_APRON_SURROUND",
         what="the apron 3 m shoulder band (1-3 % down) and its "
              "beyond-shoulder continuation govern apron surrounds again, "
              "and apron hosts are banded again",
         item="reg-set §5.1 T2/T3 + RULINGS 2026-08-08 reg-set ruling 4 — "
              "RETIRE OUTRIGHT; AC ¶5.9.2 is a Recommended Practice and "
              "ICAO governs nothing beyond an apron edge.  The ¶5.9.1 "
              "edge DROP-OFF Standard and the ¶4.14.2 item-4 lip are KEPT "
              "(reg-set §5.1's closing paragraph)"),
    Flag(env="O4_FABRIC_W2_RETIRE_APRON_EDGE_WALLS",
         what="the apron-edge retaining-wall family emits again",
         item="reg-set §5.1 T4 + reg-set ruling 4 — pure design; under "
              "the drape the raw DEM meets the apron edge"),
    Flag(env="O4_FABRIC_W2_RETIRE_SERVICE_SHADOW",
         what="the 15 m cut-only flat shadow beside service roads and "
              "service junctions governs again",
         item="reg-set §5.1 T5 — STANDARDS.md states it outright: "
              "'design choice, NOT an AASHTO mandate'"),
    # ── W2 · the two pending-flip consumers (config.RULESET_W2_FLIPS) ──
    Flag(env="O4_FABRIC_W2_ICAO_STRIP_AUTHORITY",
         what="the runway graded-strip band reads the blended live field "
              "(mandatory 1.5 % fall on BOTH rulesets) instead of each "
              "authority's own mandate",
         item="RULINGS 2026-08-08 reg-set ruling 1 (PROVISIONAL) — the "
              "ICAO ruleset DROPS the mandatory-DOWN graded strip; the "
              "FAA form is unchanged.  Gate-revertable for the owner's "
              "sim look, which is why the flag is named in the ruling"),
    Flag(env="O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY",
         what="the taxiway/taxilane/apron edge lip reads the RUNWAY lip "
              "family (3 m at 3-5 %) on every ruleset again",
         item="reg-set finding F-10 + F-3 — the FAA states TWO lip "
              "families (¶4.14.2 item 4: 4.5-5.5 % at a taxiway/apron "
              "edge); ICAO states NO taxiway lip at all"),
    # ── W3 · the freeze, redesigned with its geometry ─────────────────
    Flag(env="O4_FABRIC_W3_FGP_HARD_CAT",
         what="the late final_grade_projection hardens with NO seeder "
              "record again (the 9,838 unattributed nodes)",
         item="fabric-phase-b-spec.md W3 — 'the agreement gate gains a "
              "seeder record (hard_cat, instrument truth)'; pin "
              "attribution 5f4924c named the channel"),
)

FLAG_INDEX = {f.env: f for f in FLAGS}
if len(FLAG_INDEX) != len(FLAGS):                          # pragma: no cover
    raise RuntimeError("duplicate Phase-B flag name")


def on(env: str) -> bool:
    """True iff the named Phase-B change is ACTIVE (the default).

    Raises for an unregistered name: a flag consulted but never declared
    is exactly the flag the registry twin cannot audit.
    """
    flag = FLAG_INDEX.get(env)
    if flag is None:
        raise KeyError(
            f"{env!r} is not a registered Phase-B flag "
            f"(known: {sorted(FLAG_INDEX)})")
    return os.environ.get(env, flag.default) != "0"


def off(env: str) -> bool:
    """True iff the named change is DISABLED — the readable negation."""
    return not on(env)


def registry_report() -> str:
    """One transcript line naming every flag that is NOT at its default,
    or ``""`` when the build is the plain W2/W3 world.

    A build whose numbers are quoted anywhere must be able to say which
    world it was: a disabled flag that leaves no trace in the log is the
    A/B arm nobody can reconstruct.
    """
    disabled = [f.env for f in FLAGS if off(f.env)]
    if not disabled:
        return ""
    return ("  [fabric-flags] NON-DEFAULT build — disabled: "
            + ", ".join(disabled))
