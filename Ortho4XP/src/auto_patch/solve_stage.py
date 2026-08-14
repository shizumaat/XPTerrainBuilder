"""THE STAGE TAG — first-class airside/groundside membership, stamped at
mint (staged-solve round, lane S1b; Fable design ruling 2026-08-13b).

WHY A TAG AND NOT A ROLE TEST
-----------------------------
The staged solve's law is "airside is king, executable": stage A's
constraint system contains ONLY airside variables; stage B solves with
stage-A values immutable.  Making that structural needs one question
answered for every constraint entry that reaches a projection — *which
stage minted you* — and the S1 attribution (`tmp/s1_attribution.md`,
21 couplings) measured that the obvious keys cannot answer it:

* ``sc["role"]`` is STRUCTURALLY BLIND to the live §10 rod interval,
  which reaches the final projection as ``family="rod_interval"`` with
  no ``role`` key at all (coupling 4).  A partition keyed on the role
  literal silently passes a service-corridor rod interval — binding
  ``z_a - z_b`` against an airside endpoint — straight into the
  airside pass.
* The whole unified graph arrives as ONE bare ``{"edges": u_edges}``
  entry (couplings 3 and 6): every service_road / service_junction /
  groundside_pavement within-shape law pair is in the airside pass by
  construction, because the entry carrying them has no role either.
* ``_withhold_road_pair_law`` moves only ``lateral_contiguity.ROAD_ROLES``
  ({service_road, service_junction}) — ``groundside_pavement`` is not in
  it, so a groundside lot's pairs on shared (airside-claimed) nodes were
  enforced in the airside pass.

So membership is stamped WHERE THE ENTRY IS MINTED, by the constructor
that knows what it is building, and every entry reaching a projection
MUST carry it.  An untagged entry is a CONSTRUCTOR DEFECT and raises —
the same never-silent posture as the axes sidecar: a partition that
silently defaults an unknown entry to one side is exactly the class of
blindness this module exists to end.

THE STAGE OF A THING
--------------------
* a SHAPE -> the lawful-airside partition of its role.  ``s.role`` at
  solve time is the VOUCHED role, not a raw literal: the pavement
  scorer's lawful-airside vouching fixpoint (RULINGS 2026-08-12,
  ``G-APRON-AIRSIDE``) has already run and enacted at
  ``pipeline.classify_pavement_v1`` / ``enact_classify``, both far
  above the solve.  ``layout.GROUNDSIDE_ROLES`` is the partition; it is
  imported, never re-spelled (blast.py role-literal hazard).
* a CONSTRUCT over a host surface (adjacent-ground zone, gap-fill
  spine, RESA cut) -> the stage of its HOST, never its own construct
  role.  ``graded_strip`` is not a stage; the surface it grades to is.
* a ROD INTERVAL -> the stage of the rod's owning CHAIN.
* a SEAT -> the stage of its host surface.
* a groundside spine / corridor variable -> stage B, always.

Public surface (frozen for this round):

    STAGE_A, STAGE_B, STAGE_KEY
    stage_of_role(role)          stage_of_shape(shape)
    tag(entry, stage)            stage_of_entry(entry)
    assert_tagged(entries, where)
    split_by_stage(entries, where)
    pair_key(a, b)
    split_edges_by_stage(edges, pair_stage, where)
"""

from __future__ import annotations

#: The airside system: runways, taxiways, junctions, aprons and every
#: construct hosted by one of them.  Stage A solves FIRST and alone.
STAGE_A = "A"
#: The groundside system: service roads/junctions, groundside pavement,
#: tunnel ramps, their corridors, rods, terraces and constructs.  Stage
#: B solves with every stage-A value frozen.
STAGE_B = "B"

#: The entry key.  One spelling, imported by every reader.
STAGE_KEY = "stage"

STAGES = (STAGE_A, STAGE_B)


class UntaggedConstraintError(RuntimeError):
    """A constraint entry reached a projection with no stage tag.

    Never caught in production: the constructor that minted the entry is
    the defect, and a partition that guesses is the blindness this
    module ends.  The message names the mint-side symptom the reader can
    act on (family/role/ref and the entry's key set).
    """


def stage_of_role(role) -> str:
    """The stage of a pavement/terrain ROLE.

    ``layout.GROUNDSIDE_ROLES`` is the partition (imported, never
    re-spelled).  A role that is not groundside is airside — including
    ``None`` and unknown roles, which is the conservative side under
    airside-is-king: a wrong stage-B tag would let groundside law bind
    an airside row, while a wrong stage-A tag only over-constrains
    stage A with its own kind.
    """
    from .layout import GROUNDSIDE_ROLES
    return STAGE_B if role in GROUNDSIDE_ROLES else STAGE_A


def stage_of_shape(shape) -> str:
    """The stage of a layout shape, from its lawful (vouched) role."""
    return stage_of_role(getattr(shape, "role", None))


def stage_of_roles(roles) -> str:
    """The stage of a NODE carrying a set of ring roles.

    AIRSIDE IS KING: a node any airside ring claims is stage A, so a
    service-road mouth vertex on an apron edge is airside data for the
    groundside pass rather than one of its variables (RULINGS
    2026-08-06, the mouth seat).  This is the same rule
    ``solve._receiver_nodes_from_roles`` applies from the other side —
    a receiver node is exactly a stage-B node.
    """
    from .layout import GROUNDSIDE_ROLES
    if not roles:
        return STAGE_A
    return STAGE_B if set(roles) <= set(GROUNDSIDE_ROLES) else STAGE_A


def tag(entry: dict, stage: str) -> dict:
    """Stamp ``entry`` with ``stage`` in place and return it."""
    if stage not in STAGES:
        raise ValueError(f"not a stage: {stage!r}")
    entry[STAGE_KEY] = stage
    return entry


def stage_of_entry(entry) -> str | None:
    return entry.get(STAGE_KEY) if isinstance(entry, dict) else None


def _describe(entry) -> str:
    if not isinstance(entry, dict):
        return f"<{type(entry).__name__}>"
    bits = []
    for k in ("family", "role", "ref", "shape_id"):
        if k in entry:
            bits.append(f"{k}={entry[k]!r}")
    bits.append(f"n_edges={len(entry.get('edges') or ())}")
    bits.append(f"keys={sorted(entry)}")
    return " ".join(bits)


def assert_tagged(entries, where: str) -> None:
    """Every entry carries a valid stage, or raise naming the offenders.

    ``where`` is the projection/call site, so the traceback names both
    the consumer that found the defect and enough of the entry to find
    its constructor.
    """
    bad = [e for e in entries
           if stage_of_entry(e) not in STAGES]
    if not bad:
        return
    lines = "\n".join(f"    {_describe(e)}" for e in bad[:8])
    more = "" if len(bad) <= 8 else f"\n    ... and {len(bad) - 8} more"
    raise UntaggedConstraintError(
        f"{len(bad)} of {len(entries)} constraint entr(y/ies) reached "
        f"{where} with no '{STAGE_KEY}' tag.  Stage membership is stamped "
        f"AT MINT (auto_patch/solve_stage.py); an untagged entry is a "
        f"constructor defect, never a partition default.\n{lines}{more}")


def split_by_stage(entries, where: str):
    """``(stage_A_entries, stage_B_entries)``, asserting full coverage."""
    assert_tagged(entries, where)
    a = [e for e in entries if e[STAGE_KEY] == STAGE_A]
    b = [e for e in entries if e[STAGE_KEY] == STAGE_B]
    return a, b


def pair_key(a, b):
    """The undirected node-pair key the stage map is keyed by."""
    return (a, b) if a <= b else (b, a)


def split_edges_by_stage(edges, pair_stage: dict, where: str):
    """Split a flat ``(a, b, budget)`` edge list by its MINT-TIME stages.

    ``pair_stage`` is ``{pair_key(a, b): stage}``, filled by whichever
    constructor minted each pair.  A pair with no entry is an untagged
    constraint — the unified-graph channel's exact historical failure
    (couplings 3/6: one bare entry carrying every shape's law pairs) —
    so it raises rather than defaulting to a side.

    Edge lists are handed through budget REWRITERS (the terrace joint
    and fan-ramp appliers) that change caps and may drop pairs, so the
    map is keyed by PAIR and never by list position — the same reason
    ``grade_graph.UnifiedGraph.family_by_pair`` is.
    """
    a_edges, b_edges, missing = [], [], []
    for e in edges:
        st = pair_stage.get(pair_key(e[0], e[1]))
        if st == STAGE_B:
            b_edges.append(e)
        elif st == STAGE_A:
            a_edges.append(e)
        else:
            missing.append(e)
    if missing:
        sample = ", ".join(f"({e[0]},{e[1]})" for e in missing[:8])
        raise UntaggedConstraintError(
            f"{len(missing)} of {len(edges)} unified-graph edge(s) reached "
            f"{where} with no mint-time stage (e.g. {sample}).  Every edge "
            f"appended to the unified edge set must register its stage in "
            f"the pair map at ITS OWN mint site (auto_patch/solve_stage.py).")
    return a_edges, b_edges
