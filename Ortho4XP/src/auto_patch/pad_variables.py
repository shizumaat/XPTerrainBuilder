"""PADS AS BAND-BOUNDED VARIABLES — the seat is chosen UNDER the narrowing
(spec ``docs/specs/pads-as-band-variables-spec.md``; owner rulings RULINGS
2026-08-27 late, "pads move within their band" and "GRADE LAW OUTRANKS
SHARED-DATUM PRESERVATION — PACK GROUPS SPLIT WHEN THEY MUST").

OWNER'S WORDS: *"why anchor the building pads at all, but allow them to
move — within their band — to accommodate the ideal pavement grade?"* and,
for pack groups: *"if necessary we split the objects and seat them
individually rather than violate grade law."*

WHAT THIS MODULE IS.  The DOMAIN arithmetic and the GROUP arithmetic,
nothing else — no band, no solver, no geometry builder.  It is deliberately
a set of pure functions over intervals plus two small stores, so the twins
can state the law without a layout, a graph or a build; the one production
consumer is ``elevation_per_surface/route_profile/anchors.py ::
build_building_seats``, which owns the band, the rings and the coupling.

THE FOUNDING REFUTATION (spec §0).  Feeding PLACED seats back into the
unified law band added +4,069 adjudicated rows at SPJC and reproduced at
HECA — because a rigid pre-committed seat contradicts the narrowing
computed after it.  The conclusion recorded in ``config.BAND_SEAT_ANCHORS``
was "seats must be CHOSEN UNDER the narrowing, one joint pass".  This
module is the domain half of that pass:

  * a derived airside pad is ONE FLAT VARIABLE, and because it is FLAT its
    domain is the INTERSECTION of the narrowed band intervals over its RING
    VERTICES — one value must be lawful at EVERY vertex (§1.1);
  * an EMPTY domain is not a band to clamp into: it is two laws
    contradicting each other at a named site, and it feeds the EXISTING
    ``law_band_contradictions`` ledger under the Amendment-1 report-first
    mechanics (§1.4) — one ledger, never a second one;
  * a shared-datum PACK GROUP is ONE variable whose domain is the
    intersection of its members' domains shifted by their AUTHORED OFFSETS;
    accommodation is PREFERRED and never an authority, so a group whose
    intersection is empty — or whose optimum leaves a member over cap —
    SPLITS, loudly, into the ``pack_group_splits`` ledger (§1.3).

NOTHING HERE ADJUDICATES.  ``pack_group_splits`` is EVIDENCE (§1.7, the
contradiction-ledger precedent): the census prints the count and the worst
site and the existing frontage / no-step / within-shape families price the
result.  A split is not a violation and must never be counted as one.
"""
from __future__ import annotations

__all__ = [
    "PAD_LAW_TOL_M", "PACK_GROUP_SPLIT_STORE",
    "pads_band_variables_enabled",
    "ring_domain", "ring_domain_detail", "domain_empty", "clamp_into",
    "publish_pack_group_splits", "publish_pad_variable_provenance",
    "record_pad_domain_contradiction",
    "PackGroupOutcome", "solve_pack_groups",
    "pack_group_splits", "format_pack_group_splits",
    "proximity_components",
]

#: The materiality floor every comparison in this module uses (CLAUDE.md
#: convergence guards; the same 0.01 m the band inversion law uses).  An
#: interval crossed by less than this is PASS-with-residual, never a
#: contradiction and never a forced split.
PAD_LAW_TOL_M = 0.01

#: Where the SPLIT LEDGER lives on the layout.  Evidence, published into
#: the ``.axes.json`` sidecar beside ``law_band_contradictions``.
PACK_GROUP_SPLIT_STORE = "_pack_group_splits"

_INF = float("inf")


def pads_band_variables_enabled() -> bool:
    """``O4_PADS_BAND_VARIABLES`` (spec §1.5), default ON.

    Read at CALL TIME, never captured at import: the harness arms flags per
    build and a module-level capture would make an OFF arm depend on import
    order (the trap the band lane hit)."""
    try:
        from auto_patch.config import PADS_BAND_VARIABLES
    except Exception:                                      # pragma: no cover
        return True
    return bool(PADS_BAND_VARIABLES)


# ══════════════════════════════════════════════════════════════════════
# §1.1 — THE PAD DOMAIN
# ══════════════════════════════════════════════════════════════════════

def ring_domain(ring, band):
    """``(lo, hi, sampled)`` — THE DOMAIN OF ONE DERIVED PAD (spec §1.1).

    ``ring`` — the pad's OPEN ring, in local metres.
    ``band`` — the band of record, callable ``(x, y) -> (floor, ceiling)``
    or ``None`` off-network.

    THE INTERSECTION, and the reason it is an intersection: **the pad is
    flat**.  One value has to be lawful at every ring vertex, so the domain
    ceiling is the MINIMUM of the vertices' ceilings and the domain floor
    is the MAXIMUM of their floors.  This is the same arithmetic
    ``_seat_node_band`` already performs at the pad's registered CONTACT
    nodes; the difference the spec makes is that it is now THE domain
    rather than a consistency check applied to a seat already chosen from
    somewhere else (the frontage box, the ring median).

    ``sampled`` is the number of ring vertices the band answered for.
    ``sampled == 0`` ⇒ off-network, and the honest interval is
    ``(-inf, +inf)`` — "this band says nothing here", which a caller must
    distinguish from "this band says nothing is lawful here".
    """
    d = ring_domain_detail(ring, band)
    return d["lo"], d["hi"], d["sampled"]


def ring_domain_detail(ring, band):
    """:func:`ring_domain`, plus WHICH ring vertex binds each side.

    The binding vertex is the provenance §1.6 publishes ("the binding
    constraints at the optimum"), and it is free here: the intersection
    already visits every vertex, so recording the argmax floor and the
    argmin ceiling costs two comparisons and never a second sweep
    (single-pass principle)."""
    lo, hi, sampled = -_INF, _INF, 0
    lo_at = hi_at = None
    if band is None:
        return {"lo": lo, "hi": hi, "sampled": 0,
                "floor_vertex": None, "ceiling_vertex": None}
    for (x, y) in ring or ():
        b = band(x, y)
        if b is None:
            continue
        f, c = float(b[0]), float(b[1])
        if f > lo:
            lo, lo_at = f, (float(x), float(y))
        if c < hi:
            hi, hi_at = c, (float(x), float(y))
        sampled += 1
    if not sampled:
        return {"lo": -_INF, "hi": _INF, "sampled": 0,
                "floor_vertex": None, "ceiling_vertex": None}
    return {"lo": lo, "hi": hi, "sampled": sampled,
            "floor_vertex": lo_at, "ceiling_vertex": hi_at}


def domain_empty(lo, hi, tol=PAD_LAW_TOL_M) -> bool:
    """``True`` when the interval admits NO value beyond the materiality
    floor.  ``lo > hi`` by less than ``tol`` is PASS-with-residual."""
    try:
        return (float(lo) - float(hi)) > float(tol)
    except (TypeError, ValueError):                        # pragma: no cover
        return False


def clamp_into(value, lo, hi):
    """``value`` moved the shortest distance into ``[lo, hi]``.

    On an INVERTED interval the ceiling wins, which is the standing
    disposition of ``_merge_rigid_units``: the lowest ceiling is the
    highest level every member's frontage can actually grade to, and
    seating above it is unreachable by construction."""
    lo, hi = float(lo), float(hi)
    v = float(value)
    if lo > hi:
        return hi
    return min(max(v, lo), hi)


# ══════════════════════════════════════════════════════════════════════
# §1.4 — AN EMPTY PAD DOMAIN IS A law_band_contradictions ENTRY
# ══════════════════════════════════════════════════════════════════════

def record_pad_domain_contradiction(layout, *, ref, ll, lo, hi,
                                    sampled=0, kept=None):
    """One row into the EXISTING ``law_band_contradictions`` ledger.

    Spec §1.4: "EMPTY PAD DOMAIN = a ``law_band_contradictions`` entry (the
    Amendment-1 report-first mechanics, same ledger, same ship-gate
    promotion path)."  SAME LEDGER — a second store would be a second
    instrument, and the ship-gate ruling that promotes report-first to
    refusal has to see one accumulated population, not two.

    The row carries ``source: "pad_domain"`` so a reader can tell a pad
    whose FLATNESS could not be satisfied from a node whose two band
    directions crossed; ``deficit_m`` is spelled exactly as the band's own
    rows spell it, because that is the key the ledger sorts on.

    Returns the row (also stored), or ``None`` when the layout refuses the
    attribute (a frozen test double).
    """
    from auto_patch.law_band import CONTRADICTION_STORE
    lo, hi = float(lo), float(hi)
    key = (("pad", str(ref)) if not ll
           else (round(float(ll[0]), 11), round(float(ll[1]), 11)))
    row = {
        "source": "pad_domain",
        "pad": str(ref),
        "ll": ([float(ll[0]), float(ll[1])] if ll else None),
        "floor": lo, "ceiling": hi,
        "deficit_m": round(lo - hi, 6),
        "ring_vertices_sampled": int(sampled),
        "healed": "pre_spec_box",
        "kept_seat_m": (None if kept is None else float(kept)),
    }
    store = dict(getattr(layout, CONTRADICTION_STORE, None) or {})
    prev = store.get(key)
    if prev is None or float(prev.get("deficit_m") or 0.0) < row["deficit_m"]:
        store[key] = row
    try:
        setattr(layout, CONTRADICTION_STORE, store)
    except AttributeError:                                 # pragma: no cover
        return None
    return row


# ══════════════════════════════════════════════════════════════════════
# §1.3 — AUTHORED-DATUM GROUPS: ACCOMMODATE, ELSE SPLIT
# ══════════════════════════════════════════════════════════════════════

class PackGroupOutcome:
    """What ``solve_pack_groups`` decided, per group.

    ``values`` — ``{member: level}`` for every member of every group.
    ``pieces`` — ``[[member, ...], ...]``; ONE piece = the group stayed
    whole and its authored offsets are preserved exactly.
    ``rows``   — the ledger rows (empty when nothing split).
    """

    __slots__ = ("values", "pieces", "rows", "whole", "split")

    def __init__(self):
        self.values: dict = {}
        self.pieces: dict = {}
        self.rows: list = []
        self.whole = 0
        self.split = 0


def proximity_components(members, polygons, tol=1e-9):
    """Connected components of ``members`` under "footprints touch".

    The relation is the docket-B facility rule (basin-group-seat §2.1, "one
    connected body = one facility") applied to the SPLIT: the first thing a
    group gives up is its long-range datum, not its local geometry, so the
    sub-bodies are the connected components of the member footprints and
    NOT a distance dial anyone has to choose.  A member with no polygon is
    its own component (nothing is known to touch it).
    """
    ms = list(members)
    idx = {m: k for k, m in enumerate(ms)}
    parent = list(range(len(ms)))

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(len(ms)):
        pi = (polygons or {}).get(ms[i])
        if pi is None or getattr(pi, "is_empty", True):
            continue
        for j in range(i + 1, len(ms)):
            pj = (polygons or {}).get(ms[j])
            if pj is None or getattr(pj, "is_empty", True):
                continue
            try:
                if pi.distance(pj) <= tol:
                    _union(i, j)
            except Exception:                              # pragma: no cover
                continue
    comps: dict = {}
    for k, m in enumerate(ms):
        comps.setdefault(_find(idx[m]), []).append(m)
    return [comps[r] for r in sorted(comps)]


def _group_interval(members, domains, offsets):
    """``(lo, hi)`` of the GROUP variable ``g``: every member sits at
    ``g + offset[m]``, so ``g`` must satisfy every member's domain shifted
    DOWN by that member's authored offset."""
    lo, hi = -_INF, _INF
    for m in members:
        d = domains.get(m)
        if d is None:
            continue
        off = float((offsets or {}).get(m, 0.0))
        lo = max(lo, float(d[0]) - off)
        hi = min(hi, float(d[1]) - off)
    return lo, hi


def _group_target(members, targets, offsets, weights):
    """The group's preferred ``g`` — the WEIGHT-weighted mean of the
    members' own preferred values, de-shifted by their authored offsets.

    Area weighting for the same reason ``_merge_rigid_units`` uses it: a
    shed authored 0.4 m off a terminal must not drag the terminal."""
    wsum = vsum = 0.0
    for m in members:
        t = targets.get(m)
        if t is None:
            continue
        w = max(float((weights or {}).get(m, 1.0)), 1e-9)
        wsum += w
        vsum += w * (float(t) - float((offsets or {}).get(m, 0.0)))
    if wsum <= 0.0:
        return None
    return vsum / wsum


def solve_pack_groups(groups, domains, targets, *, offsets=None,
                      weights=None, polygons=None, over_cap=None,
                      tol=PAD_LAW_TOL_M):
    """ACCOMMODATE, ELSE SPLIT — the owner's ruling, executable (spec §1.3).

    ``groups``  — ``[{"key": str, "members": [m, ...]}, ...]``.
    ``domains`` — ``{m: (lo, hi)}``, each member's own narrowed domain.
    ``targets`` — ``{m: value}``, each member's own preferred level.
    ``offsets`` — ``{m: authored offset}`` from the group's shared datum.
    ``weights`` — ``{m: footprint area}`` (area weighting, see above).
    ``polygons``— ``{m: shapely polygon}``, for the sub-body split only.
    ``over_cap``— ``callable({m: level}) -> [row, ...]``.  THE GRADE LAW,
                  supplied by the caller because this module owns no law:
                  it returns the rows a candidate assignment leaves over
                  cap (frontage / no-step).  ``None`` ⇒ the domain test is
                  the whole test.

    THE ORDER IS THE RULING'S ORDER, and it matters:

      1. the group's intersection is computed and, if it is non-empty, the
         group optimum is taken inside it — **a lawful accommodation is
         PREFERRED**;
      2. that optimum is then priced by ``over_cap``.  Pack-relationship
         preservation is the TIEBREAKER among lawful placements, never the
         authority, so a group optimum that leaves ANY member's law over
         cap is not "the best available" — it is a SPLIT;
      3. the split goes to SUB-BODIES BY CONNECTED PROXIMITY FIRST, each
         piece re-solved in its own domain, and only then to INDIVIDUAL
         PADS.  Authored offsets are preserved WITHIN each surviving piece.

    Every split is LOUD: the returned rows name the group, its members, the
    violating rows that forced it and the pieces chosen.
    """
    out = PackGroupOutcome()
    offsets = offsets or {}
    weights = weights or {}

    def _try(members):
        """``(values, forcing_rows)`` — ``forcing_rows`` empty ⇒ lawful."""
        lo, hi = _group_interval(members, domains, offsets)
        if domain_empty(lo, hi, tol):
            return None, [{"why": "empty_intersection",
                           "members": list(members),
                           "group_floor": lo, "group_ceiling": hi,
                           "deficit_m": round(lo - hi, 6)}]
        g = _group_target(members, targets, offsets, weights)
        if g is None:
            g = hi if lo > hi else lo
        g = clamp_into(g, lo, hi)
        vals = {m: g + float(offsets.get(m, 0.0)) for m in members}
        rows = list(over_cap(vals) or ()) if over_cap is not None else []
        return vals, rows

    for grp in groups or ():
        members = [m for m in (grp.get("members") or ())]
        key = str(grp.get("key") or "?")
        if len(members) < 2:
            # Not a group: one member is its own variable and the ordinary
            # per-pad path already governs it.  Recorded as WHOLE (there is
            # nothing to shear) so the ledger's denominator is honest.
            for m in members:
                d = domains.get(m)
                t = targets.get(m)
                if d is not None and t is not None:
                    out.values[m] = clamp_into(t, d[0], d[1])
            if members:
                out.pieces[key] = [list(members)]
                out.whole += 1
            continue

        vals, rows = _try(members)
        if not rows:
            out.values.update(vals)
            out.pieces[key] = [list(members)]
            out.whole += 1
            continue

        # ── THE SPLIT.  Sub-bodies by connected proximity FIRST. ────────
        forcing = rows
        comps = proximity_components(members, polygons)
        stage = "sub_bodies"
        if len(comps) < 2:
            # Every member touches every other through the chain — there
            # are no sub-bodies to fall back to, so the ruling's LAST
            # resort is the only one left.
            comps = [[m] for m in members]
            stage = "individual"
        pieces: list = []
        piece_rows: list = []
        for comp in comps:
            cvals, crows = _try(comp)
            if crows and len(comp) > 1:
                # A sub-body that is still unlawful goes all the way down —
                # "individual pads last" is per piece, not per group.
                piece_rows.extend(crows)
                for m in comp:
                    d, t = domains.get(m), targets.get(m)
                    if d is not None and t is not None:
                        out.values[m] = clamp_into(t, d[0], d[1])
                    pieces.append([m])
                stage = "individual"
                continue
            if cvals is None:                              # pragma: no cover
                for m in comp:
                    d, t = domains.get(m), targets.get(m)
                    if d is not None and t is not None:
                        out.values[m] = clamp_into(t, d[0], d[1])
                    pieces.append([m])
                stage = "individual"
                continue
            out.values.update(cvals)
            pieces.append(list(comp))
        out.pieces[key] = pieces
        out.split += 1
        worst = 0.0
        for r in list(forcing) + list(piece_rows):
            try:
                worst = max(worst, abs(float(r.get("deficit_m")
                                             or r.get("excess_m") or 0.0)))
            except (TypeError, ValueError):                # pragma: no cover
                continue
        out.rows.append({
            "group": key,
            "members": [str(m) for m in members],
            "stage": stage,
            "pieces": [[str(m) for m in p] for p in pieces],
            "forcing_rows": list(forcing) + list(piece_rows),
            "worst_m": round(float(worst), 6),
        })
    return out


# ══════════════════════════════════════════════════════════════════════
# §1.6 — PROVENANCE: THE PER-PAD PUBLICATION EXTENDS pad_binding_routes
# ══════════════════════════════════════════════════════════════════════

#: The container ``pad_binding_routes`` is published in — the 2026-08-27
#: chip round's key.  EXTEND, NEVER FORK (owner ruling RULINGS 7e90032):
#: "why is this pad here" must stay ONE file read, and a second per-pad
#: key beside it is the fork that makes it two.
PAD_BINDING_ROUTES_STORE = "_pad_binding_routes"


def publish_pad_variable_provenance(layout, records, *, nodespace=None):
    """MERGE the pad-variable provenance into ``pad_binding_routes``.

    ``records`` — ``[{"pad": ref, "domain": [lo, hi], "solved_m": v,
    "binding": {...}}, ...]``.

    A MERGE and not an assignment, deliberately.  The container is keyed
    per pad and has more than one producer: the binding-ROUTE capture
    publishes the recorded route that bound the seat, and this publishes
    the DOMAIN the seat was chosen from and what binds it at the optimum.
    Both answer "why is this pad here" and both belong on the same record;
    an assignment would make whichever ran second delete the other's
    answer.  Records are joined by ``pad`` — the ref, which is the
    identity both producers already carry.

    ``nodespace`` is only ADOPTED when the container has none: the route
    capture's stamp is the stronger claim (it is the node space the routes'
    node ids live in), and the domains are stamped in no node space at all
    — they are intervals in metres.
    """
    container = getattr(layout, PAD_BINDING_ROUTES_STORE, None)
    if not isinstance(container, dict):
        container = {"nodespace": None, "records": []}
    rows = list(container.get("records") or ())
    by_ref = {}
    for r in rows:
        if isinstance(r, dict) and r.get("pad") is not None:
            by_ref.setdefault(str(r["pad"]), r)
    for rec in records or ():
        ref = str(rec.get("pad"))
        prev = by_ref.get(ref)
        if prev is None:
            rows.append(dict(rec))
            by_ref[ref] = rows[-1]
        else:
            prev.update(rec)
    container = {
        "nodespace": (container.get("nodespace")
                      if container.get("nodespace") is not None
                      else nodespace),
        "records": rows,
    }
    try:
        setattr(layout, PAD_BINDING_ROUTES_STORE, container)
    except AttributeError:                                 # pragma: no cover
        pass
    return container


def pack_group_splits(layout) -> list:
    """The published split rows, worst first."""
    rows = list(getattr(layout, PACK_GROUP_SPLIT_STORE, None) or ())
    rows.sort(key=lambda r: -float(r.get("worst_m") or 0.0))
    return rows


def publish_pack_group_splits(layout, rows) -> list:
    rows = list(rows or ())
    try:
        setattr(layout, PACK_GROUP_SPLIT_STORE, rows)
    except AttributeError:                                 # pragma: no cover
        pass
    return rows


def refuse_on_empty_pad_domains(layout, rows, icao=""):
    """The pad-domain half of the §1.4 TWO MODES (spec §2, "refuse arm
    raises").

    ``O4_BAND_LAW_REFUSE=0`` (the shipped pre-ship default) — the rows are
    already in ``law_band_contradictions`` and the pad already kept its
    pre-spec box; nothing happens here.  ``=1`` (the diagnostic /
    ship-gate arm) — the SAME sites raise, before any patch is written,
    naming each pad and its inverted interval.

    ONE ledger, one promotion path: this is deliberately the same flag the
    band's own inverted intervals answer to, because the ship-gate ruling
    is made on ONE accumulated population.
    """
    if not rows:
        return 0
    try:
        from auto_patch.config import BAND_LAW_REFUSE
    except Exception:                                      # pragma: no cover
        return 0
    if not BAND_LAW_REFUSE:
        return 0
    from auto_patch.law_band import LawBandRefusal
    lines = [
        f"    pad {r[0]}: floor {r[1]:.3f} > ceiling {r[2]:.3f} (empty by "
        f"{r[1] - r[2]:.3f} m) over {r[3]} ring vertex(es)"
        for r in rows[:20]]
    raise LawBandRefusal(
        f"[pad-vars] {icao}: {len(rows)} derived pad(s) have an EMPTY "
        f"DOMAIN (spec pads-as-band-variables §1.4) — no single level is "
        f"lawful at every ring vertex of a pad that must be FLAT.  Under "
        f"feasibility-is-guaranteed that is a defect in the DATA or the "
        f"LAW at a NAMED site, never a property of the ground.\n"
        + "\n".join(lines)
        + "\n    O4_BAND_LAW_REFUSE=0 reports these and continues, which "
          "is the shipped pre-ship arm.")


def format_pack_group_splits(icao, rows, *, limit=20) -> str:
    """The LOUD line spec §1.3 requires — count, worst site, then the
    groups themselves.

    A split visibly shears authored pack geometry, so the owner reviews
    each one; the ledger is also a BAD-PACK DETECTOR (a flat-plane-authored
    pack on a hill reads as a many-way split), which is why the piece count
    is on the headline."""
    rows = list(rows or ())
    if not rows:
        return (f"  [pack-split] {icao}: every authored-datum pack group "
                f"ACCOMMODATED — no group was split, so every authored "
                f"vertical relationship survives (the preferred outcome, "
                f"spec pads-as-band-variables §1.3)")
    worst = rows[0]
    lines = []
    for r in rows[:limit]:
        why = {row.get("why") for row in (r.get("forcing_rows") or ())}
        lines.append(
            f"    group {r['group']}: {len(r['members'])} member(s) SPLIT "
            f"into {len(r.get('pieces') or ())} piece(s) at stage "
            f"{r.get('stage')} — forced by "
            f"{len(r.get('forcing_rows') or ())} row(s) "
            f"({', '.join(sorted(w for w in why if w)) or 'over_cap'}), "
            f"worst {r.get('worst_m')} m\n"
            f"      members: {', '.join(r['members'][:12])}"
            f"{' ...' if len(r['members']) > 12 else ''}\n"
            f"      pieces:  "
            + " | ".join("{" + ", ".join(p[:6])
                         + (" ..." if len(p) > 6 else "") + "}"
                         for p in (r.get("pieces") or ())[:8]))
    more = "" if len(rows) <= limit else f"\n    ... and {len(rows) - limit} more"
    return (
        f"  [pack-split] {icao}: {len(rows)} authored-datum pack group(s) "
        f"SPLIT because no single datum satisfied grade law — GRADE LAW "
        f"OUTRANKS SHARED-DATUM PRESERVATION (owner ruling RULINGS "
        f"2026-08-27 late).  Worst site: group {worst['group']} at "
        f"{worst.get('worst_m')} m.  A split SHEARS authored geometry: the "
        f"owner reviews each one, and a flat-plane-authored pack on a hill "
        f"reads here as a many-way split.\n" + "\n".join(lines) + more)
