"""THE AGP GROUP RECORD (#2090; spec ``2090-agp-group-groundside-spec.md``
A1-A3): data only.

A GROUP is two or more on-ground ``.agp`` rows of one pack whose authored
connector floors meet (``airport/agp_ground.joins``, V2's certainty).  The
pack stage (``airport/agp_group``) derives it ONCE, before the bridge
stacks: its members, its joins (each with its votes and the runner-up's),
the PROVISIONAL GOVERNOR (A2: the member nearest the apt.dat airside, when
near enough and every other member twice as far) and each member's chain
step from it.  ``zero_pred`` (A3) is the DEM at the governor's ground point
plus the step: it fixes geometry only; the exact datum is read between the
stages (``constraints/agp_level``).

Rows a group's geometry minted carry its id ``agp:<lowest row>`` in their
``Source.inputs`` (the datum rewrite moves them by one delta).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["AGP_GROUP_PREFIX", "AgpMember", "AgpJoin", "AgpGroup", "group_of_input"]

#: a group id, and the ``Source.inputs`` tag of every row its geometry mints
AGP_GROUP_PREFIX = "agp:"


@_dc.dataclass(frozen=True)
class AgpMember:
    """One member: its pack-stage object id ``row`` (``dsf:obj<index>``),
    the DSF placement ``index``, its ``resource``, its ``GROUND_PT`` in the
    frame and as ``(lat, lon)``, its ground point's plan distance to the
    apt.dat airside (``inf`` with none) and ``step`` its datum minus the
    governor's (``None`` in an unpredicted group)."""

    row: str
    index: int
    resource: str
    ground_xy: tuple[float, float]
    ground_ll: tuple[float, float]
    airside_m: float
    step: float | None = None


@_dc.dataclass(frozen=True)
class AgpJoin:
    """Two members ``a`` / ``b`` (rows) whose floors meet: ``step`` =
    datum_b - datum_a; ``votes`` the winning step's distinct level pairs,
    ``rival`` the runner-up's; ``contact_ll`` the middle of the contact;
    ``stands`` V2's verdict (a refused join is listed only)."""

    a: str
    b: str
    step: float
    votes: int
    rival: int
    contact_ll: tuple[float, float]
    stands: bool = True


@_dc.dataclass(frozen=True)
class AgpGroup:
    """One joined group (module doc).  ``governor`` is a member row or
    ``None`` (unpredicted: ``why`` says so, nothing is graded for it);
    ``dem_gov`` the DEM at the governor's ground point; ``airside`` the
    members that read as airside (A2's reach).  ``deck_joins`` and
    ``plates`` are filled by spec 2090 B1 / C1."""

    id: str
    members: tuple[AgpMember, ...]
    joins: tuple[AgpJoin, ...]
    governor: str | None
    dem_gov: float | None
    why: str = ""
    airside: frozenset[str] = frozenset()
    deck_joins: tuple = ()
    plates: tuple = ()

    def member(self, row: str) -> AgpMember | None:
        return next((m for m in self.members if m.row == row), None)

    def zero_pred(self, row: str) -> float | None:
        """A3: the DEM at the governor's ground point plus ``row``'s chain
        step; ``None`` unpredicted."""
        m = self.member(row)
        if self.governor is None or self.dem_gov is None or m is None or m.step is None \
                or not math.isfinite(self.dem_gov):
            return None
        return float(self.dem_gov) + float(m.step)

    def followers(self) -> tuple[AgpMember, ...]:
        """The members that follow the governor (never it, never airside)."""
        if self.governor is None:
            return ()
        return tuple(m for m in self.members
                     if m.row != self.governor and m.row not in self.airside)


def group_of_input(tag: _t.Any) -> str | None:
    """The group id a ``Source.inputs`` entry names, or ``None``."""
    t = str(tag)
    return t if t.startswith(AGP_GROUP_PREFIX) else None

