"""§16e (3) A BRIDGE IS NAMED BY CONTACT WITH THE DECK'S OWN MODEL
FOOTPRINT (spec ``object-placement-spec.md`` §16e (3) as amended, Fable
2026-09-13; owner RULINGS 2026-09-13v).

WHAT NAMES A BRIDGE, AND WHAT DOES NOT.  Two answers were tried by lane
``v2othhdatums`` and both are REFUTED, measured:

* THE ROW does not name one.  OTHH's ``unit:6`` puts ``Bridge_02``,
  ``Bridge_03`` and ``Bridge_06`` — three bridges 250 m apart — on ONE
  shared-datum row at ONE AGL, so ``deck_signature.family_key`` calls all
  thirty of that unit's members one family; at LEMD the same reading
  would call 171 resources one.
* THE DECK'S RING does not either.  It is a BBOX: ``Bridge_02``'s
  ``CLUTTER_000`` stands inside ``Bridge_06``'s ring.  Read on the
  member's lowest part the cross-bridge carries went 2 -> 3, and on all
  its parts 2 -> 5.

What names a bridge is CONTACT WITH THE DECK'S OWN MODEL FOOTPRINT: the
deck member's mesh projected to plan, triangle by triangle.  A pier or a
clutter body belongs to the deck whose footprint polygon CONTAINS its
plan centroid (or lies within ``tol_m`` of it); where two decks'
footprints both contain it, the deck whose UNDERSIDE is nearest ABOVE
the body's top wins (absolute vertical distance — §16c (4)'s own rest-on
reading).  A body no deck footprint contains has NO bridge family: it
takes the ordinary §16c rest-on ground, is never filtered, and is never
carried by a deck.

The relation is DERIVED ONCE PER PLAN and published per body
(``Body.bridge_of``); ``family_key`` is untouched for every other class.

WHAT THE RELATION IS NOT WIRED TO, AND WHY (lane ``v2bridgecontact``,
OTHH 1.0.326 frame, matched arms through ``v2_rebake_replay plan
--sampler mesh``).  §16e (3)'s other two halves — ONE BRIDGE IS ONE
RIGID CLUSTER, and a body rests only on its own deck or its own piers —
were implemented on top of this relation (the family unioned in
``placement_atom.unit_rigid`` ahead of every other bind, riding the
deck's node where the deck has one; the carrier pool cut to the family)
and BOTH ARMS MOVED THE SECTION'S OWN BARS BACKWARDS.  The code is
DELETED under the attempt cap and the numbers are the attribution:

* arm 1 (family cluster + pool cut to the family): cross-bridge carriers
  by RESOURCE NAME 2 -> 9, per-placement zero spreads over 0.3 m 12 of
  14 -> 17 of 19, ``Bridge_02_CLUTTER_007`` 4.97 -> 6.61 m.
* arm 2 (the family actually unioned — two FOOTED bodies of one member
  are deliberately never unioned by §16c (7), so arm 1's cluster never
  formed at all — and only the DECKS cut out of a family-LESS body's
  pool, which is §16e (3)'s own "never filtered"): cross 2 -> 9 still,
  spreads 12 of 16, worst 4.97 -> 9.66 m.

THE MECHANISM, MEASURED (the distance from every bridge body's plan
centroid to the nearest deck footprint, this module's own polygon):

* THE FAMILY THE CONTACT TEST NAMES IS PARTIAL.  51 to 71 of OTHH's
  ~80-102 bridge bodies fall inside a deck footprint or within 0.5 m;
  the rest are 0.6 … 45 m outside it.  OTHH's bridge CLUTTER runs
  BESIDE the deck plate (parapets, kerbs, lamp masts), not under it.
  A PARTIALLY bound bridge is worse than an unbound one: its named half
  rides one zero and its unnamed half reads its own ground, and the
  per-placement spread the bar measures is across both.
* THE DECKS OVERLAP EACH OTHER IN PLAN.  Bridge_02/03/06 are an
  INTERCHANGE: ``Bridge_03_CLUTTER_000__b1`` stands INSIDE Bridge_02's
  footprint (0.1 m), ``Bridge_02_CLUTTER_001__b3`` and ``_002__b0``
  inside Bridge_06's.  By CONTACT those bodies are that deck's, which is
  the law — and the bar "cross-bridge carriers 0" is stated over the
  pack's ``Bridge_NN`` SPELLING, which the law deliberately does not
  read.  Under the name axis the law's own right answer scores as a
  violation; 66 of 71 published values agree with the name and the five
  that do not are the interchange.

So the relation is DERIVED, PUBLISHED and CENSUSED here and wired to
nothing, and what §16e (3) still needs ruled is (a) whether a body
BESIDE a deck plate is that bridge's (the 0.5 m reach is the spec's own
number and this lane did not change it) and (b) which axis the
cross-bridge bar is read on when contact and name disagree.

NO LAW CONSTANT LIVES HERE: ``tol_m`` is the caller's, from §16e (3)'s
own 0.5 m contact reach.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .rebake_plan import _mpd as _m_per_deg

import math as _math

__all__ = ["DeckPrint", "deck_prints", "bridge_of_point", "CONTACT_M",
           "assign_bodies", "body_bridge",
           "census_bridges", "census_bridges_lines", "bridge_tag"]

#: §16e (3): "centroid-in-polygon or within 0.5 m of it".  The spec's own
#: number, and the only one this module takes.
CONTACT_M = 0.5

#: The footprint index's plan cell.  A SAMPLING RESOLUTION, not a law: it
#: decides which triangles a query looks at and nothing else — every
#: triangle whose cell the query shares is tested exactly.
_CELL_M = 25.0


@_dc.dataclass
class DeckPrint:
    """ONE DECK'S MODEL FOOTPRINT POLYGON — its mesh projected to plan.

    ``tris`` are the deck member's authored triangles as ``(lat, lon)``
    triples; ``under_y`` its UNDERSIDE, the lowest authored ``y`` of its
    own components (§16c (4) reads a carrier's top, and a deck is read
    from beneath: what rides a bridge stands UNDER its deck).

    The ring (``Member.deck_ring``) is this polygon's BBOX and is what
    §16e (3) refutes; nothing here reads it."""

    key: str
    unit: int
    member: int
    under_y: float
    box: tuple[float, float, float, float]
    tris: tuple[tuple[tuple[float, float], tuple[float, float],
                      tuple[float, float]], ...] = ()
    _grid: dict = _dc.field(default_factory=dict, repr=False)
    _ml: float = 1.0
    _mo: float = 1.0

    def index(self) -> None:
        """Bucket the triangles by plan cell (one pass, at construction)."""
        if not self.tris:
            return
        # THE UNMEMOISED reading (``rebake_plan._mpd``, the same formula):
        # ``anchor_rule._m_per_deg`` is QUANTISED per 1e-4 deg of latitude
        # (exact per key since the 13df chip — it used to hold whichever
        # caller touched a key first), so asking it here — before the
        # unit loop — moved every downstream ``authored_offset`` in the
        # airport by ~8 microns and broke the byte-identity of resources
        # this law does not touch (measured, this lane: 94 placements'
        # offsets, 93 fills).  The unmemoised formula stays.
        self._ml, self._mo = _m_per_deg(0.5 * (self.box[0] + self.box[2]))
        c = _CELL_M
        for k, t in enumerate(self.tris):
            i0 = int(min(q[0] for q in t) * self._ml // c)
            i1 = int(max(q[0] for q in t) * self._ml // c)
            j0 = int(min(q[1] for q in t) * self._mo // c)
            j1 = int(max(q[1] for q in t) * self._mo // c)
            if (i1 - i0 + 1) * (j1 - j0 + 1) > 4096:
                self._grid.setdefault(("big",), []).append(k)
                continue
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    self._grid.setdefault((i, j), []).append(k)

    def contains(self, lat: float, lon: float, tol_m: float = CONTACT_M) -> bool:
        """Is this point inside the deck's footprint, or within ``tol_m``
        of it?  Exact point-in-triangle over the deck's own mesh — the
        polygon §16e (3) names, never its bbox."""
        if not self.tris:
            return False
        pad_la = tol_m / self._ml if self._ml else 0.0
        pad_lo = tol_m / self._mo if self._mo else 0.0
        if (lat < self.box[0] - pad_la or lat > self.box[2] + pad_la
                or lon < self.box[1] - pad_lo or lon > self.box[3] + pad_lo):
            return False
        c = _CELL_M
        # THE NEIGHBOURING CELLS TOO, whenever there is a reach to serve:
        # a point ``tol_m`` OUTSIDE the plate can fall in a cell no
        # triangle was bucketed in, and the 0.5 m reach then never ran at
        # all (caught by this module's own twin).  ``tol_m`` is a half
        # metre against a 25 m cell, so one ring of neighbours is exact.
        ci = int(lat * self._ml // c)
        cj = int(lon * self._mo // c)
        keys: list = [("big",)]
        rng = (0,) if tol_m <= 0.0 else (0, -1, 1)
        for di in rng:
            for dj in rng:
                keys.append((ci + di, cj + dj))
        seen: set[int] = set()
        near: list[int] = []
        for k in keys:
            for q in self._grid.get(k, ()):  # noqa: SIM118
                if q not in seen:
                    seen.add(q)
                    near.append(q)
        if not near and tol_m <= 0.0:
            return False
        for q in near:
            if _in_tri(self.tris[q], lat, lon):
                return True
        if tol_m <= 0.0:
            return False
        # the 0.5 m reach: a body whose centroid falls just OUTSIDE the
        # plate (a parapet, a pier head cast a hair proud of it)
        t2 = (tol_m / max(self._ml, 1e-9)) ** 2
        for q in near:
            if _near_tri(self.tris[q], lat, lon, self._ml, self._mo) <= t2:
                return True
        return False


def _in_tri(t, lat: float, lon: float) -> bool:
    (a0, a1), (b0, b1), (c0, c1) = t
    d = (b1 - c1) * (a0 - c0) + (c0 - b0) * (a1 - c1)
    if abs(d) < 1e-18:
        return False
    u = ((b1 - c1) * (lat - c0) + (c0 - b0) * (lon - c1)) / d
    v = ((c1 - a1) * (lat - c0) + (a0 - c0) * (lon - c1)) / d
    return u >= 0.0 and v >= 0.0 and (u + v) <= 1.0


def _near_tri(t, lat: float, lon: float, ml: float, mo: float) -> float:
    """Squared distance from the point to the triangle's edges, in
    DEGREES OF LATITUDE squared (the caller's tolerance is scaled the
    same way), so one comparison serves both axes."""
    best = float("inf")
    k = mo / ml if ml else 1.0
    for i in range(3):
        a, b = t[i], t[(i + 1) % 3]
        ax, ay = a[0], a[1] * k
        bx, by = b[0], b[1] * k
        px, py = lat, lon * k
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        s = 0.0 if den < 1e-24 else max(0.0, min(1.0, ((px - ax) * dx
                                                       + (py - ay) * dy) / den))
        qx, qy = ax + s * dx, ay + s * dy
        best = min(best, (px - qx) ** 2 + (py - qy) ** 2)
    return best


def _latlon(x: float, z: float, lat: float, lon: float,
            heading_deg: float) -> tuple[float, float]:
    """``placement_cut.authored_latlon``'s own two lines, over the
    UNMEMOISED metres-per-degree.

    Identical arithmetic; the only difference is that it does not SEED
    ``anchor_rule._MPD``.  That memo is keyed per 1e-4 deg of latitude
    and keeps whichever exact latitude touched a key first, so a NEW
    call site running before the unit loop hands every later caller in
    the same 11 m band a value it did not compute — 80 of OTHH's
    ``authored_offset``s moved by ~8 microns and 58 placements this law
    does not touch stopped being byte-identical (measured, this lane).
    A footprint polygon judged at 0.5 m does not care about the 1e-5
    m/deg the memo is there to save."""
    h = _math.radians(heading_deg)
    s0, c0 = _math.sin(h), _math.cos(h)
    e = x * c0 - z * s0
    n = -x * s0 - z * c0
    ml, mo = _m_per_deg(lat)
    return (lat + n / ml, lon + e / mo)


def deck_prints(plan: _t.Any, cutter_for: _t.Callable) -> list[DeckPrint]:
    """EVERY DECK'S FOOTPRINT POLYGON, derived ONCE PER PLAN (§16e (3)).

    ``cutter_for(ui, mi, member) -> _LineCutter | None`` hands back the
    cutter already open on that member's file, so a deck is PARSED ONCE
    for the whole stage: the parse is what the plan stage costs (618 of
    OTHH's members parsed twice was 42 s, 11ak), and this pass must add
    none of it.

    A deck member whose file cannot be read contributes no print, and a
    body then has no family — which is §16e (3)'s own answer for a body
    no footprint contains."""
    out: list[DeckPrint] = []
    for ui, u in enumerate(plan.units):
        for mi, m in enumerate(u.members):
            if m.deck_kind not in ("flag", "signature"):
                continue
            cut = cutter_for(ui, mi, m)
            if cut is None or not cut._read():               # noqa: SLF001
                continue
            import numpy as np
            v = cut._geom.vertices                           # noqa: SLF001
            comps = cut._comps                               # noqa: SLF001
            tl = [c.tris for c in comps if len(c.tris)]
            if not tl:
                continue
            tris = np.concatenate(tl)
            ids = np.unique(tris.reshape(-1))
            ids = ids[ids < v.shape[0]]
            ll = {int(i): _latlon(float(v[i, 0]), float(v[i, 2]),
                                  cut.lat, cut.lon, m.heading_deg)
                  for i in ids.tolist()}
            rows = tuple(tuple(ll[int(q)] for q in row)
                         for row in tris.tolist()
                         if all(int(q) in ll for q in row))
            if not rows:
                continue
            las = [q[0] for t in rows for q in t]
            los = [q[1] for t in rows for q in t]
            p = DeckPrint(key=m.resource, unit=ui, member=mi,
                          under_y=float(min(c.min_y for c in comps)),
                          box=(min(las), min(los), max(las), max(los)),
                          tris=rows)
            p.index()
            out.append(p)
    return out


def bridge_of_point(prints: _t.Sequence[DeckPrint], lat: float, lon: float,
                    top_y: "float | None" = None,
                    tol_m: float = CONTACT_M) -> "DeckPrint | None":
    """§16e (3): THE DECK THIS BODY BELONGS TO, or ``None``.

    The prints whose footprint contains the point (or comes within
    ``tol_m``); where more than one does, the one whose UNDERSIDE is
    nearest the body's TOP in absolute vertical distance — §16c (4)'s
    rest-on reading, which is what "the deck it is under" means when two
    decks overlap in plan.  With no top to read, the LOWER underside
    wins (the deck a body between two of them is under)."""
    hits = [p for p in prints if p.contains(lat, lon, tol_m)]
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]
    if top_y is None:
        return min(hits, key=lambda p: (p.under_y, p.key))
    return min(hits, key=lambda p: (round(abs(float(top_y) - p.under_y), 3),
                                    p.key))


def assign_bodies(prints: _t.Sequence[DeckPrint], staged: _t.Sequence,
                  counts: dict) -> None:
    """§16e (3): WHICH BRIDGE IS EACH RAW BODY ON — written into each
    staged member's ``bridge`` list, in place.

    A body BELONGS to the deck whose MODEL FOOTPRINT POLYGON contains its
    plan centroid (or comes within :data:`CONTACT_M`); two containing
    decks are broken by the underside nearest the body's top.  A body no
    footprint contains has no family, which is the answer §16e (3) gives
    it — nothing FILTERS or BINDS on the value (3) is WITHDRAWN, RULINGS
    2026-09-13ae) and it exists to be PUBLISHED and CENSUSED."""
    if not prints:
        return
    from .placement_carrier import hull_of
    for st in staged:
        st.bridge = [""] * len(st.raw)
        for bi in range(len(st.raw)):
            bx = hull_of(st.part_boxes[bi])
            if bx is None:
                continue
            tp = (max(st.part_tops[bi])
                  if bi < len(st.part_tops) and st.part_tops[bi] else None)
            hit = bridge_of_point(prints, 0.5 * (bx[0] + bx[2]),
                                  0.5 * (bx[1] + bx[3]), tp, CONTACT_M)
            if hit is not None:
                st.bridge[bi] = hit.key
                counts["bridge_bodies"] = counts.get("bridge_bodies", 0) + 1


def body_bridge(bridge: _t.Sequence[str], grp: _t.Sequence[int]) -> str:
    """§16e (3): the BRIDGE a WRITTEN body belongs to — the key its raw
    bodies agree on, or ``""`` where they do not (a group the cuts drew
    across a deck's edge belongs to no one bridge, and the relation names
    only what it can name)."""
    keys = {bridge[i] for i in grp if i < len(bridge)}
    keys.discard("")
    return keys.pop() if len(keys) == 1 else ""


# ── the instrument (§16e (3)'s bars) ─────────────────────────────────────

def bridge_tag(resource: str) -> str:
    """The pack's own ``Bridge_NN`` spelling in a resource path, or ``""``.

    THE CENSUS'S AXIS, NEVER THE LAW'S.  §16e (3) exists BECAUSE the name
    does not name a bridge; the bar, though, is stated per bridge
    (``Bridge_02_CLUTTER_007``'s pier spread) and this is how the report
    groups its rows — so it is also an independent check on the derived
    relation, which the report prints as agreement."""
    import re
    hit = re.search(r"(Bridge_\d+)", resource or "")
    return hit.group(1) if hit else ""


def census_bridges(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                   surface=None) -> dict:
    """§16e (3)'s BARS over a written placement plan's own rows — the same
    shape and the same code path every other census in
    ``placement_census`` reads (``plan["splits"]``).

    ``surface(lat, lon) -> z | None`` is the design surface (a mesh
    sampler where the caller has one; ``None`` prints the height bars as
    unreadable rather than guessing).

    The four numbers:

    * ``deck_top`` per bridge — the world height the deck's own body puts
      its authored top at (the datum anchor's ground, ``surface_z``) and
      the LAND under the bridge's own written geometry, so "the deck top
      within 0.5 m of the graded road at each abutment" is read against
      something this report measured and not against a constant.
    * ``spreads`` per PLACEMENT — ``max - min`` of ``surface_z - y_zero``
      over the bodies of one placement.  ``Bridge_02_CLUTTER_007`` is six
      piers of ONE solid and spanned 4.97 m.
    * ``cross`` — bodies whose carrier (``merged_into``) is a file of
      ANOTHER bridge.  BAR 0.
    * ``published`` / ``agree`` — how many bodies carry ``bridge_of``, and
      how many of those agree with the resource's own ``Bridge_NN`` tag.
    """
    by_tag: dict[str, dict] = {}
    cross: list[tuple[str, str, str]] = []
    spreads: list[tuple[float, str, str]] = []
    published = agree = total = 0
    per_placement: dict[str, list[float]] = {}
    file_tag: dict[str, str] = {}
    rows: list[tuple[str, str, _t.Mapping[str, _t.Any]]] = []
    for s in splits:
        res = str((s.get("placement") or {}).get("resource", ""))
        tag = bridge_tag(res)
        for b in s.get("bodies", ()):
            file_tag[str(b.get("new_resource", ""))] = tag
            if tag:
                rows.append((tag, res, b))
    for tag, res, b in rows:
        total += 1
        of = str(b.get("bridge_of") or "")
        if of:
            published += 1
            if bridge_tag(of) == tag:
                agree += 1
        d = by_tag.setdefault(tag, {"bodies": 0, "deck_top": None,
                                    "deck_reason": "", "land": []})
        d["bodies"] += 1
        sz = b.get("surface_z")
        if b.get("class") == "deck" and sz is not None and d["deck_top"] is None:
            d["deck_top"] = float(sz)
            d["deck_reason"] = str(b.get("anchor_reason", ""))
        if sz is not None:
            per_placement.setdefault(tag + "|" + res, []).append(
                float(sz) - float(b.get("y_zero", 0.0)))
        mi = str(b.get("merged_into") or "")
        if mi:
            other = file_tag.get(mi, "")
            if other and other != tag:
                cross.append((tag, str(b.get("new_resource", "")), mi))
        if surface is not None:
            for q in b.get("geom_pts", ()) or ():
                z = surface(float(q[0]), float(q[1]))
                if z is not None:
                    d["land"].append(float(z))
    for key, zs in per_placement.items():
        if len(zs) > 1:
            t, r = key.split("|", 1)
            spreads.append((max(zs) - min(zs), t, r))
    spreads.sort(reverse=True)
    return {"by_tag": by_tag, "cross": cross, "spreads": spreads,
            "published": published, "agree": agree, "total": total}


def census_bridges_lines(c: dict, visual_m: float = 0.5) -> list[str]:
    """The block the report prints (``seat_feet_census`` /
    ``obj8_split_report``)."""
    out = ["§16e (3) THE BRIDGE FAMILY (spec §16e (3), RULINGS 2026-09-13v)"]
    out.append(f"  bodies on a Bridge_NN resource: {c['total']}; "
               f"`bridge_of` published {c['published']}, agreeing with the "
               f"resource's own tag {c['agree']}")
    for tag in sorted(c["by_tag"]):
        d = c["by_tag"][tag]
        land = sorted(q for q in d["land"])
        top = d["deck_top"]
        lo = f"{land[0]:.2f}" if land else "-"
        md = f"{land[len(land) // 2]:.2f}" if land else "-"
        hi = f"{land[-1]:.2f}" if land else "-"
        bar = ""
        if top is not None and land:
            gap = abs(top - land[-1])
            bar = f"  |deck top - highest land| {gap:.2f} m " \
                  f"({'PASS' if gap <= visual_m else 'OVER'} {visual_m:g} m)"
        out.append(f"  {tag}: {d['bodies']} bodies, deck top "
                   f"{'-' if top is None else f'{top:.2f}'}; ground under the "
                   f"bridge's own geometry {lo} / {md} / {hi} m{bar}")
    out.append(f"  per-placement zero spread over 0.3 m: "
               f"{sum(1 for s in c['spreads'] if s[0] > 0.3)} of "
               f"{len(c['spreads'])}")
    for sp, tag, res in c["spreads"][:8]:
        out.append(f"    {sp:6.2f} m  {tag}  {res}")
    out.append(f"  CROSS-BRIDGE carriers (BAR 0): {len(c['cross'])}")
    for tag, mine, theirs in c["cross"][:8]:
        out.append(f"    {tag}: {mine} carried by {theirs}")
    return out
