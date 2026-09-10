"""THE DESIGN SURFACE'S ROLE AND RULING READERS — split from ``solve/design.py``
by the 1,000-line file law (2026-09-10; three merges in one day pushed it to
1,025 lines).  Pure readers of the law tables: which roles bend, which are
pavement, which bodies carry a datum, which ruling heads are hard / one-way /
pad-flat / pad-level.  No solve state; ``design.py`` re-exports every name so
importers and twins are unchanged.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..law.design_schema import BEND_CLASSES
from ..law.tables import (design as design_law, is_structure_role, is_value_role,
                          pavement_roles as _pavement_roles, zone_class)
from ..model.constraints import Row

__all__ = ['bend_roles', 'pavement_roles', 'bend_class', 'apron_roles', 'taxi_body_roles', 'datum_roles', 'one_way_rulings', 'pad_flat_rulings', 'pad_level_rulings', 'hard_rulings', 'ruling_head', 'is_hard']

def bend_roles(law: Law) -> tuple[str, ...]:
    """The roles whose faces form the SHEETS the bending term shapes: every
    role that is not a STRUCTURE's own surface — the pavement AND the
    graded strip / clearance ground around it, because the blend from the
    design level to the natural terrain happens INSIDE those zones (owner
    08t answer 3) and a blend with no bending term is not a blend."""
    return tuple(r for r in law.tables.precedence.roles
                 if not is_structure_role(law, r))


def pavement_roles(law: Law) -> tuple[str, ...]:
    """The DESIGNED surface itself — every VALUE role that is not a
    structure: the zone ramp measures its distance from here, and a vertex
    of one of these faces never takes a DEM fit (08t answer 1).  ONE
    derivation site, ``law.tables.pavement_roles`` (``constraints.pads``
    reads the same predicate to tell a pad's fronting pavement apart from
    the pad)."""
    return _pavement_roles(law)


def bend_class(law: Law, role: str) -> str:
    """The BENDING CLASS of ``role`` (``design_schema.BEND_CLASSES``, RULINGS
    2026-09-08v): ``runway`` / ``taxi`` for the two named families,
    ``road`` for the road cross-section's roles, ``apron`` for every other
    role that carries its own value, ``strip`` for the rest (the graded
    strip, the clearances, the cuts — the ground the blend happens in)."""
    if role in law.tables.precedence.runway_family.members:
        return "runway"
    if role in law.tables.precedence.taxi_family.members:
        return "taxi"
    if role in law.tables.families["road_cross_section"].roles:
        return "road"
    return "apron" if is_value_role(law, role) else "strip"


def apron_roles(law: Law) -> frozenset[str]:
    """The roles of an APRON BODY — every role the bending term prices at
    ``bend_apron`` (a value role that is not the runway family, the taxi
    family or the road cross-section).  These are the bodies the PER-BODY
    DATUM sits (RULINGS 2026-09-09p (3)); the runway family is excluded
    because the threshold chord and its pins ARE its datum, and a
    structure's own surface is not a body at all."""
    return frozenset(r for r in pavement_roles(law)
                     if bend_class(law, r) == "apron")


def taxi_body_roles(law: Law) -> frozenset[str]:
    """The roles of a TAXI BODY (owner RULINGS 2026-09-10p) — every value
    role the bending term prices at ``bend_taxi``.  A taxi body is formed
    exactly as an apron body is: the connected group of faces of THESE
    roles.  A runway face is never in one (its role is not here), so a
    taxi body may TOUCH a runway without joining it.  NOT a datum body
    since RULINGS 2026-09-10v — kept as the taxi family's own role reader
    (the report and the twins name it)."""
    return frozenset(r for r in pavement_roles(law)
                     if bend_class(law, r) == "taxi")


def datum_roles(law: Law) -> tuple[tuple[str, frozenset[str]], ...]:
    """The role sets the PER-BODY DATUM sits on, each with its class name.

    APRON BODIES ONLY (owner RULINGS 2026-09-10v, replacing 10p).  10p gave
    every TAXI body the same mean row; 10v measured that as too coarse — a
    taxi body is the whole connected taxi NETWORK (CYXY: one 853-vertex
    body), so one mean is an airport-wide level that cannot fix a local
    tilt, and at HECA it raised the taxi curvature the owner is reading.
    The taxi family's level is now its CHAIN'S TREND
    (``constraints/taxi_trend.py``, §8.6) — along the route, not over the
    network.  The runway family stays excluded (its profile and pins are
    its datum)."""
    return (("apron", apron_roles(law)),)


def one_way_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS whose rows are priced ONE-WAY — ``[design]
    one_way_rulings`` (RULINGS 2026-09-09b (2)/(3): the adjacent ground
    follows the pavement edge and never pulls it)."""
    return frozenset(design_law(law).one_way_rulings)


def pad_flat_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS whose rows are priced at ``[design] pad_flat`` —
    the pad's flatness TARGET (owner RULINGS 2026-09-09c): a weight an
    order above the law's, so a pad comes out flat wherever the geometry
    admits a flat solution, and tilts (to at most 1 %, hard) where not."""
    return frozenset(design_law(law).pad_flat_rulings)


def pad_level_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS of a pad's frontage LEVEL rows — ``[design]
    pad_level_rulings`` (owner RULINGS 2026-09-10l, 10k-1 = (A): "Pad
    takes the apron edge level").  A vertex one of these rows GOVERNS
    follows its pavement, so §9b takes it out of every per-body DEM datum
    mean: a pad's own datum (09p (3)) is for a pad that fronts NO
    pavement."""
    return frozenset(design_law(law).pad_level_rulings)


def hard_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS whose rows are HARD CONSTRAINTS of the active set —
    ``[design] hard_rulings`` (RULINGS 2026-09-08v: the runway family's
    transverse, vertical curve K and max grade; the threshold pins are
    already equalities)."""
    return frozenset(design_law(law).hard_rulings)


def ruling_head(row: Row) -> str:
    """The HEAD of a row's ruling — everything before the first
    parenthesis, the key ``[design] hard_rulings`` / ``one_way_rulings``
    name a law by."""
    return row.source.ruling.split(" (")[0].strip()


def is_hard(law_heads: _t.AbstractSet[str], row: Row) -> bool:
    """Whether ``row`` states one of the HARD laws: the head of its ruling
    (everything before the first parenthesis) is one of ``law_heads``."""
    return ruling_head(row) in law_heads


# ── THE SOLVE ───────────────────────────────────────────────────────────
