"""§16g (10) (4) AMENDED — A SPANNING SHEET CHAINS (owner RULINGS
2026-09-27a (1), issue #69; Q-69 option (b)).

Owner: parts of one pack terminal joined by a continuous roof / floor
SHEET that overlaps BOTH bodies' footprints are ONE §16g unit (one pad) —
18t "separation only by clear space".  A canopy touching ONE body links
nothing (14ah still holds for it).

14ah made every thin body (under ``chain_min_height_m``) a LEAF that never
links two walled bodies.  MEASURED (lane ``outlinebisect``): once
``contact.solid_height`` read sheets correctly, OTHH's terminal — one
building to a pilot, its parts joined only by roof and floor sheets
(``OTHH_Terminal_Base_1``, ``OTHH_Terminal_Interior_1``) — fell from ONE
484,538 m2 cluster pad into pieces (39,598 m2 at the site
25.2599127, 51.6149444).

THE RULE, ONE DERIVATION, asked by both chain sites
(``placement_family.plan_clusters`` — the design surface's clusters — and
``footprint_unit.plan_units_and_connectors`` — the object stage's units;
§16g (9) ONE POPULATION):

* a LEAF that is not a deck (``member_is_deck``: its own datum law, §16e)
  and stands OFF the ground — no component with ground feet — is a SHEET
  candidate.  A FOOTED leaf (a paving / ground slab two buildings stand
  on) is not: the buildings on it are still separated by clear space
  (18t), and it is exactly the class 14ah measured over-chaining HECA's
  T3 district (``floor_more_yellow``, ``T3_concrete_Yellow``,
  ``concrete_3``: one 9,334-body cluster).  MEASURED on the OTHH main
  partition (sheetchain, fraction 0.5): every non-deck leaf 59 pads, site
  pad 504,448 m2; elevated leaves only 61 pads, site pad 484,190 m2 (the
  othhjunction figure 484,538); HECA every leaf 93 pads (fourteen 34 m2
  slivers minted by ground slabs), elevated only 79;
* it LINKS every walled body whose footprint it OVERLAPS by at least
  ``[placement] sheet_chain_min_fraction`` of the SMALLER of the two
  footprints (overlap, not touch: a sheet resting against a wall's face
  shares an edge, not ground);
* it links only where it overlaps TWO or more walled bodies; then the
  sheet itself JOINS the unit it made (it is the part that joins them).
  Over one body — a canopy, an awning — it links nothing and stays a leaf.

Name-free: nothing here reads a resource name."""
from __future__ import annotations

import typing as _t

import shapely

from .contents import _poly

__all__ = ["sheet_links", "merge_by_sheets"]


def sheet_links(shims: _t.Sequence[_t.Any], walled_ix: _t.Sequence[int],
                leaves: _t.Sequence[int], min_fraction: float,
                *, is_deck: _t.Callable[[int], bool],
                is_footed: _t.Callable[[int], bool], ml: float, mo: float,
                counts: "dict | None" = None, prefix: str = "",
                fractions: "list | None" = None
                ) -> list[tuple[int, tuple[int, ...]]]:
    """``[(sheet shim index, (walled shim indices it links, sorted))]`` —
    only sheets that link TWO or more walled bodies, in shim order.

    ``fractions`` (a list) receives every ``(sheet, body, fraction)`` the
    overlap reading computed (the measuring hook; the rule never reads
    it).  0 ``min_fraction`` disarms."""
    if min_fraction <= 0.0 or len(walled_ix) < 2 or not leaves:
        return []
    polys: list = []
    owners: list[int] = []
    for i in walled_ix:
        g = _poly(shims[i].rings, shims[i].part_boxes, ml, mo)
        if g is not None and not g.is_empty and g.area > 0.0:
            polys.append(g)
            owners.append(i)
    if len(polys) < 2:
        return []
    tree = shapely.STRtree(polys)
    out: list[tuple[int, tuple[int, ...]]] = []
    n_single = n_deck = n_footed = 0
    for i in leaves:
        if is_deck(i):
            n_deck += 1
            continue
        if is_footed(i):
            n_footed += 1
            continue
        g = _poly(shims[i].rings, shims[i].part_boxes, ml, mo)
        if g is None or g.is_empty or g.area <= 0.0:
            continue
        hit = []
        for j in sorted(int(x) for x in tree.query(g, predicate="intersects")):
            ov = polys[j].intersection(g).area
            if ov <= 0.0:
                continue
            f = ov / min(g.area, polys[j].area)
            if fractions is not None:
                fractions.append((i, owners[j], f))
            if f >= min_fraction:
                hit.append(owners[j])
        if len(hit) >= 2:
            out.append((i, tuple(sorted(hit))))
        elif hit:
            n_single += 1
    if counts is not None:
        counts[prefix + "sheet_links"] = len(out)
        counts[prefix + "sheet_link_bodies"] = sum(len(b) for _s, b in out)
        counts[prefix + "sheet_over_one_body"] = n_single
        counts[prefix + "sheet_refused_deck"] = n_deck
        counts[prefix + "sheet_refused_footed"] = n_footed
    return out


def merge_by_sheets(chains: _t.Sequence[_t.Sequence[int]],
                    links: _t.Sequence[tuple[int, _t.Sequence[int]]],
                    adj: "dict[int, set[int]] | None" = None
                    ) -> list[list[int]]:
    """The walled ``chains`` (lists of shim indices) with every sheet link
    applied: chains holding bodies one sheet links become ONE chain, and
    the sheet joins it.  A linked body in no chain (a walled singleton the
    caller dropped) enters as its own chain first.  ``adj`` (the contact
    edges, mutated) gains sheet <-> body edges so a later reading of the
    chain's graph (§16g (10) (1)'s floor split) sees the link.

    Deterministic: the output is sorted members, chains ordered by their
    smallest member."""
    if not links:
        return [list(c) for c in chains]
    par: dict[int, int] = {}

    def find(a: int) -> int:
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[max(ra, rb)] = min(ra, rb)

    for cl in chains:
        for k in cl[1:]:
            union(cl[0], k)
        if cl:
            find(cl[0])
    for s, bodies in links:
        for b in bodies:
            union(s, b)
            if adj is not None:
                adj.setdefault(s, set()).add(b)
                adj.setdefault(b, set()).add(s)
    groups: dict[int, list[int]] = {}
    for i in list(par):
        groups.setdefault(find(i), []).append(i)
    return sorted((sorted(v) for v in groups.values()), key=lambda v: v[0])
