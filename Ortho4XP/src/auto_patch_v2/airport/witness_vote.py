"""THE WITNESS VOTE — one rule for every terrain question (#1359; owner
RULINGS 2026-10-26q; spec ``docs/specs/multi-source-terrain-spec.md`` §4).

Each source answers a question at a site with a :class:`Vote` (a value and
its sigma, or a one-sided bound) or an :class:`Abstain` naming why.
:func:`decide`:

1. groups the votes into clusters, each seeded by its most senior
   unclustered vote; a vote joins a cluster when it agrees with EVERY
   member (``|a - b| <= k * sqrt(sa^2 + sb^2)``; a bound agrees with a
   value on its side of it);
2. the cluster with the most members wins when it has at least two and
   more than any other; its answer is its most senior member's value (a
   survey is never averaged with a coarse source);
3. a tie goes to seniority (the first cluster), flagged ``tie``;
4. one vote alone is ``uncorroborated``;
5. no votes: no answer, today's law stands.

A losing vote YIELDS only when it disagrees with every winning member (the
ruling's "a source that disagrees with the imagery and layout yields"); a
loser that agrees with one winner is ``unresolved`` — not overridden.
Pure: deterministic from its inputs.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["Vote", "Abstain", "decide"]


@_dc.dataclass(frozen=True)
class Vote:
    """A source's answer: ``value`` ± ``sigma``; or, with ``bound`` set to
    ``"min"`` / ``"max"``, "the answer is at least / at most ``value``"."""

    source: str
    value: float
    sigma: float
    bound: str = ""
    note: str = ""


@_dc.dataclass(frozen=True)
class Abstain:
    """A source that does not answer, and why."""

    source: str
    reason: str


@_dc.dataclass(frozen=True)
class Decision:
    """The vote's outcome (module docstring)."""

    answer: float | None
    winners: tuple[str, ...]
    yielders: tuple[str, ...]
    unresolved: tuple[str, ...]
    status: str                      # majority | tie | uncorroborated | none

    def record(self, votes: _t.Sequence[Vote | Abstain]) -> dict:
        """The published record of this decision and every input."""
        return {
            "answer": None if self.answer is None else round(self.answer, 3),
            "status": self.status, "winners": list(self.winners),
            "yielders": list(self.yielders), "unresolved": list(self.unresolved),
            "votes": [({"source": v.source, "value": round(v.value, 3),
                        "sigma": round(v.sigma, 3), "bound": v.bound, "note": v.note}
                       if isinstance(v, Vote) else
                       {"source": v.source, "abstain": v.reason}) for v in votes],
        }


def agree(a: Vote, b: Vote, k: float) -> bool:
    """Whether two votes agree (module docstring, step 1)."""
    tol = k * math.hypot(a.sigma, b.sigma)
    if a.bound and b.bound:
        return True                          # two bounds never contradict here
    if a.bound or b.bound:
        bd, pt = (a, b) if a.bound else (b, a)
        return pt.value >= bd.value - tol if bd.bound == "min" else pt.value <= bd.value + tol
    return abs(a.value - b.value) <= tol


def decide(votes: _t.Sequence[Vote | Abstain], seniority: _t.Sequence[str],
           k: float) -> Decision:
    """The rule (module docstring); ``seniority`` lists sources most senior
    first (a source absent from it ranks last, in input order)."""
    rank = {s: i for i, s in enumerate(seniority)}
    cast = sorted((v for v in votes if isinstance(v, Vote)),
                  key=lambda v: (rank.get(v.source, len(rank)), bool(v.bound)))
    if not cast:
        return Decision(None, (), (), (), "none")
    clusters: list[list[Vote]] = []
    for v in cast:
        for c in clusters:
            if all(agree(v, m, k) for m in c):
                c.append(v)
                break
        else:
            clusters.append([v])
    best = max(len(c) for c in clusters)
    tops = [c for c in clusters if len(c) == best]
    win = tops[0]
    if best < 2:
        status = "uncorroborated" if len(cast) == 1 else "tie"
    else:
        status = "majority" if len(tops) == 1 else "tie"
    point = next((m for m in win if not m.bound), None)
    answer = point.value if point is not None else None
    if len(cast) > 1 and best < 2:
        # every vote alone: nobody corroborates anybody — no yielding
        return Decision(answer, tuple(m.source for m in win), (),
                        tuple(v.source for v in cast if v not in win), status)
    losers = [v for v in cast if v not in win]
    yielders = tuple(v.source for v in losers if not any(agree(v, m, k) for m in win))
    unresolved = tuple(v.source for v in losers if v.source not in yielders)
    return Decision(answer, tuple(m.source for m in win), yielders, unresolved, status)
