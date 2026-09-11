"""THE ABUTMENT GROUP (owner RULINGS 2026-09-10ay; gated 2026-09-11a;
spec ``othh-seat-artefacts-spec.md`` §17) — lifted out of
``emit/clusters.py`` under the 1,000-line file law.

One function, ``groups``: over the seat's bodies and the plan's
AUTHORED-FRAME ABUTMENTS, which bodies take another body's ground and
which ground that is.  It reads only what it is passed (the plan, the
parts by body, the bodies' measured grounds) — no mesh, no environment.
"""
from __future__ import annotations

import statistics
import typing as _t

from ..model.rebake import RebakePlan

__all__ = ["groups"]


class _UF:
    """Union-find over body ids (the seat's own is private to it)."""

    def __init__(self, ids: _t.Iterable[int]) -> None:
        self.p = {i: i for i in ids}

    def find(self, a: int) -> int:
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def groups(plan_: RebakePlan, rb, ps: _t.Mapping[int, _t.Any],
           members_of: _t.Mapping[int, _t.Sequence[int]],
           cluster_of: _t.Mapping[int, int],
           line_body_ks: _t.Collection[int], orphan_ks: _t.Collection[int],
           facility: _t.Collection[int], attached: _t.Collection[int],
           grounds_of: _t.Mapping[int, _t.Sequence[float]],
           lows_of: _t.Mapping[int, _t.Sequence[float]],
           plan_area: _t.Callable[[_t.Sequence[int], _t.Mapping[int, _t.Any]], float],
           ) -> tuple[dict[int, int], dict[int, float], int]:
    """``(group_of, group_ground, pairs refused)`` — see the module doc
    and the block comment below."""
    # ── THE ABUTMENT GROUP (owner RULINGS 2026-09-10ay; spec §17) ──────
    # In a SHARED-DATUM pack the authored relation between two placements
    # is exact, so bodies of one ANCHOR PLANE that ABUT in the AUTHORED
    # frame — plan footprints overlapping, authored z within
    # ``plate_gap_max_m``, no ε-contact edge (``plan.abutments``, read at
    # plan time by ``airport/contact.py``) — form ONE GROUP with ONE
    # delta: THE SENIOR BODY'S (most measured feet, then largest
    # footprint).  LEMD's T4 departures viaduct is 58 components in 32
    # bodies, each on its own piers, deltas +18.44 … +27.71, standing
    # over the terminal (one body, 558 parts, +20.94) whose kerb it was
    # authored to run 2.24 m under.  Grouped, the deck stays at the kerb
    # and its ramp ends BURY where the ground is higher — lawful (10ay:
    # "allow either end to be submerged … and the ground will join it").
    #
    # A body is OUT of the class when a rule already governs its
    # elevation: a LINE body (10bb rule 2 — bodies that abut only through
    # a line object never group), an ORPHAN, a STRUCTURE-seated body (a
    # deck / plate / basin, 14.1 rule 4 — this is what keeps OTHH's decks
    # where their abutment law puts them) and a FACILITY (05p: the
    # terrain adapts to it, it is never seated).
    #
    # THE GATE (owner RULINGS 2026-09-11a; spec §17.5): ACROSS PLACEMENTS
    # the junior must be an ELEVATED DECK — a body every one of whose
    # members carries a plate on PIERS (``Member.elevated_deck``,
    # ``airport/deck_signature.elevated_deck``).  BUILDINGS NEVER GROUP
    # WITH BUILDINGS: each seats on its own feet (10i).  Round 1's
    # general rule fixed the viaduct and then pulled 7 of LEMD's
    # OldTerminal buildings one hop toward a larger neighbour (feet over
    # 3 m: 14 → 23) and made OTHH's 19-part Fire Fuel body junior to the
    # 543-part flat fuel farm, losing its −1.13 m delta.  A body seats on
    # its own feet unless it has no feet of its own to stand on — which
    # is what a deck on piers, authored to meet a kerb, is.
    group_of: dict[int, int] = {}
    group_ground: dict[int, float] = {}
    n_group_refused = 0
    if plan_.abutments:
        def _eligible(k: int) -> bool:
            return (k not in line_body_ks and k not in orphan_ks and k not in facility
                    and not any(pid in attached for pid in members_of[k]))
        # A PLACEMENT'S OWN abutments CHAIN; ACROSS placements the
        # abutment is ONE HOP to the senior.  10i rule 1 already makes one
        # placement's TOUCHING set one body; 10ay's authored frame extends
        # that to its separated components, so the viaduct's 32 deck
        # sections are one thing before they meet the terminal at all —
        # and then that one thing takes the terminal's delta.
        #
        # The full transitive closure was measured first and REFUTED: it
        # swept LEMD's OldTerminal facades — placement abutting placement
        # abutting placement — into single groups and put 36 placements'
        # feet over 3 m off their ground against 14 at base (`T2SL4`
        # +8.27, `LEMD38` +7.17, `LEMD84` +6.10, not a deck among them).
        # One hop with NO intra-placement chain was measured too: 16 over
        # 3 m, but the viaduct came apart again (27 of its 32 bodies
        # ungrouped, deltas +18.44 … +23.56), which is the site itself.
        def _deck_share(pids: _t.Iterable[int]) -> float:
            """The share of a body's / chain's PLAN AREA carried by parts
            of ELEVATED-DECK resources (11a).  A share, not "every
            member": contact welds a kerb or a parking slab of another
            resource onto a deck body (LEMD's viaduct carries parts of
            ``LEMD02`` / ``LEMD20`` / ``PKT4``), while a BUILDING body
            has no deck part in it at all."""
            tot = deck = 0.0
            for pid in pids:
                p = ps[pid]
                a = float(p.part.area_m2) or 1.0
                tot += a
                u, i = p.key
                if plan_.units[u].members[i].elevated_deck:
                    deck += a
            return deck / tot if tot > 0 else 0.0

        def _deck_body(k: int) -> bool:
            return _deck_share(members_of[k]) >= rb.abutment_deck_share_min
        own = _UF(list(members_of))
        cross: list[tuple[int, int]] = []
        deck_ks: dict[int, bool] = {}
        for a, b in plan_.abutments:
            ka, kb = cluster_of.get(a), cluster_of.get(b)
            if ka is None or kb is None or ka == kb:
                continue
            if not (_eligible(ka) and _eligible(kb)):
                n_group_refused += 1
                continue
            if ps[a].key == ps[b].key:
                own.union(ka, kb)
                continue
            # ACROSS PLACEMENTS: one side must be an ELEVATED DECK, and
            # only THAT side may end up the junior (checked again below,
            # once the chains and their footprints are known)
            for k in (ka, kb):
                if k not in deck_ks:
                    deck_ks[k] = _deck_body(k)
            if not (deck_ks[ka] or deck_ks[kb]):
                n_group_refused += 1
                continue
            cross.append((ka, kb))
        chain_of = {k: own.find(k) for k in members_of}
        chain_parts: dict[int, list[int]] = {}
        for k, c in chain_of.items():
            chain_parts.setdefault(c, []).extend(members_of[k])
        area_of = {c: plan_area(pids, ps) for c, pids in chain_parts.items()}
        chain_members_pre: dict[int, list[int]] = {}
        for k, c in chain_of.items():
            chain_members_pre.setdefault(c, []).append(k)
        abuts: dict[int, set[int]] = {}
        for ka, kb in cross:
            ca, cb = chain_of[ka], chain_of[kb]
            if ca == cb:
                continue
            abuts.setdefault(ca, set()).add(cb)
            abuts.setdefault(cb, set()).add(ca)
        # a CHAIN is a JUNIOR of the LARGEST chain it abuts, and only when
        # that one is strictly larger (a tie is two peers and no group);
        # a junior never founds a group of its own — one hop, never two
        # a CHAIN is an elevated deck when every body in it is one
        deck_chain = {c: _deck_share(chain_parts[c]) >= rb.abutment_deck_share_min
                      for c in chain_members_pre}
        senior_of: dict[int, int] = {}
        for c, ns in abuts.items():
            best = max(ns, key=lambda n: (area_of[n], -n))
            if area_of[best] <= area_of[c]:
                continue
            if not deck_chain[c]:
                # the junior is a BUILDING (11a): it seats on its own feet
                n_group_refused += 1
                continue
            senior_of[c] = best
        chain_members = chain_members_pre
        groups_by_senior: dict[int, list[int]] = {}
        for c, s in senior_of.items():
            if s in senior_of:
                continue
            g = groups_by_senior.setdefault(s, list(chain_members[s]))
            g.extend(chain_members[c])
        # a chain of several bodies with no cross abutment at all is still
        # ONE group: the placement's own separated components, one delta
        for c, kss in chain_members.items():
            if len(kss) > 1 and c not in senior_of and c not in groups_by_senior:
                groups_by_senior[c] = list(kss)
        for sc, ks in groups_by_senior.items():
            if len(ks) < 2:
                continue
            # THE SENIOR (10ay: "most feet / largest footprint: the
            # terminal"): the LARGEST PLAN FOOTPRINT first, then the most
            # measured feet, then the lowest body id — read over THE
            # SENIOR CHAIN's OWN bodies (``sc``), never over the whole
            # group.  The ground a junior takes is THE SENIOR'S; reading
            # it over the group made it depend on which OTHER juniors
            # happened to join, and 11a's gate (which removes the
            # building juniors) moved LEMD's viaduct 6.77 m by that alone.
            order = sorted(chain_members[sc],
                           key=lambda k: (-plan_area(members_of[k], ps),
                                          -len(grounds_of.get(k, ())), k))
            senior = next((k for k in order if grounds_of.get(k)), None)
            if senior is None:
                continue
            gs_s = grounds_of[senior]
            skirted_s = all(plan_.units[ps[pid].key[0]].members[ps[pid].key[1]].skirted
                            for pid in members_of[senior])
            lows_s = lows_of.get(senior, ())
            gm = float(min(lows_s)) if skirted_s and lows_s else float(statistics.median(gs_s))
            for k in ks:
                group_of[k] = senior
                group_ground[k] = gm
    return group_of, group_ground, n_group_refused
