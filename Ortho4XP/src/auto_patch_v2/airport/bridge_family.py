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
           "assign_bodies", "body_bridge", "Viaduct", "unit_viaducts", "frame_of", "viaduct_units",
           "ground_plate_on_relief",
           "deck_components", "viaduct_of",
           "landing_pieces",
           "census_bridges", "census_bridges_lines", "bridge_tag"]

#: §16e (3): "centroid-in-polygon or within 0.5 m of it".  The spec's own
#: number, and the only one this module takes.
CONTACT_M = 0.5

#: The footprint index's plan cell.  A SAMPLING RESOLUTION, not a law: it
#: decides which triangles a query looks at and nothing else — every
#: triangle whose cell the query shares is tested exactly.
_CELL_M = 25.0

#: :meth:`DeckPrint.contains_many`'s candidate-box margin, in degrees
#: (~0.1 mm): far above the barycentric test's rounding at a few 1e-14
#: degrees, so no triangle :meth:`DeckPrint.contains` accepts is missed.
_BOX_EPS_DEG = 1e-9


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
    #: issue #290: the AUTHORED ``y`` of each triangle's three vertices,
    #: parallel to ``tris`` — what :meth:`top_at` reads the deck SURFACE
    #: height at a plan point from (a ramp deck is not one height).
    #: Empty for a print built without heights; :meth:`top_at` then
    #: reads None.
    ys: tuple[tuple[float, float, float], ...] = ()
    _grid: dict = _dc.field(default_factory=dict, repr=False)
    #: issue #1179: :func:`deck_components`'s memo, per gap
    _pieces: dict = _dc.field(default_factory=dict, repr=False)
    #: issue #1213: :meth:`contains_many`'s triangle-box tree, built once
    _boxes: list = _dc.field(default_factory=list, repr=False)
    #: issue #1213: each triangle's cell range (None: ``"big"``), as indexed
    _cells: list = _dc.field(default_factory=list, repr=False)
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
                self._cells.append(None)
                continue
            self._cells.append((i0, i1, j0, j1))
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    self._grid.setdefault((i, j), []).append(k)

    def contains(self, lat: float, lon: float, tol_m: float = CONTACT_M) -> bool:
        """Is this point inside the deck's footprint, or within ``tol_m``
        of it?  Exact point-in-triangle over the deck's own mesh — the
        polygon §16e (3) names, never its bbox."""
        if not self.tris or self._off_box(lat, lon, tol_m):
            return False
        return self._contains_near(lat, lon, tol_m,
                                   self._near(lat, lon, tol_m))

    def contains_many(self, lats: _t.Sequence[float], lons: _t.Sequence[float],
                      tol_m: float = CONTACT_M) -> list[bool]:
        """:meth:`contains` for a batch of points — the SAME booleans
        (issue #1213: KMCI's 77 k part centres against 49 deck prints, one
        Python cell walk each, ran 25+ min); see :meth:`_near_many`."""
        out = [False] * len(lats)
        for i, near in self._near_many(lats, lons, tol_m).items():
            out[i] = self._contains_near(float(lats[i]), float(lons[i]),
                                         tol_m, near)
        return out

    def _off_box(self, lat: float, lon: float, reach_m: float) -> bool:
        pad_la = reach_m / self._ml if self._ml else 0.0
        pad_lo = reach_m / self._mo if self._mo else 0.0
        return (lat < self.box[0] - pad_la or lat > self.box[2] + pad_la
                or lon < self.box[1] - pad_lo or lon > self.box[3] + pad_lo)

    def _keys(self, lat: float, lon: float, reach_m: float) -> list:
        """The grid keys a query at the point walks, in walk order.

        THE NEIGHBOURING CELLS TOO, whenever there is a reach to serve: a
        point ``reach_m`` OUTSIDE the plate can fall in a cell no triangle
        was bucketed in, and the 0.5 m reach then never ran at all (caught
        by this module's own twin).  The reach is a half metre against a
        25 m cell, so one ring of neighbours is exact."""
        c = _CELL_M
        ci = int(lat * self._ml // c)
        cj = int(lon * self._mo // c)
        rng = (0,) if reach_m <= 0.0 else (0, -1, 1)
        return [("big",)] + [(ci + di, cj + dj) for di in rng for dj in rng]

    def _near(self, lat: float, lon: float, reach_m: float) -> list[int]:
        """The triangles of the point's cells, in walk order, once each."""
        seen: set[int] = set()
        near: list[int] = []
        for k in self._keys(lat, lon, reach_m):
            for q in self._grid.get(k, ()):  # noqa: SIM118
                if q not in seen:
                    seen.add(q)
                    near.append(q)
        return near

    def _near_many(self, lats: _t.Sequence[float], lons: _t.Sequence[float],
                   reach_m: float) -> dict[int, list[int]]:
        """issue #1213: :meth:`_near` for a batch, cut to the triangles
        that can answer — ``{point index: triangles}`` for every point on
        the padded box.  ONE STRtree query over the triangles' plan boxes,
        each padded by ``reach_m`` and :data:`_BOX_EPS_DEG` (the
        barycentric rounding), yields a superset of every triangle that
        holds the point or comes within the reach of it; each point keeps
        those of its candidates :meth:`_near` walks, IN ITS WALK ORDER
        (``top_at``'s reach breaks a tie by that order), so the answer is
        the per-point one triangle for triangle."""
        n = len(lats)
        if not self.tris or not n:
            return {}
        if len(self._cells) != len(self.tris):            # never indexed
            return {i: self._near(float(lats[i]), float(lons[i]), reach_m)
                    for i in range(n)
                    if not self._off_box(float(lats[i]), float(lons[i]),
                                         reach_m)}
        import numpy as np
        import shapely
        la = np.asarray(lats, dtype=float)
        lo = np.asarray(lons, dtype=float)
        pad_la = reach_m / self._ml if self._ml else 0.0
        pad_lo = reach_m / self._mo if self._mo else 0.0
        live = np.nonzero(~((la < self.box[0] - pad_la)
                            | (la > self.box[2] + pad_la)
                            | (lo < self.box[1] - pad_lo)
                            | (lo > self.box[3] + pad_lo)))[0]
        out: dict[int, list[int]] = {int(i): [] for i in live.tolist()}
        if not live.size:
            return out
        if not self._boxes:
            t = np.asarray(self.tris, dtype=float)          # (n, 3, 2)
            self._boxes.append(shapely.STRtree(shapely.box(
                t[:, :, 1].min(axis=1), t[:, :, 0].min(axis=1),
                t[:, :, 1].max(axis=1), t[:, :, 0].max(axis=1))))
        r = max(reach_m, 0.0)
        e_la = (r / self._ml if self._ml else 0.0) + _BOX_EPS_DEG
        e_lo = (r / self._mo if self._mo else 0.0) + _BOX_EPS_DEG
        qi, ti = self._boxes[0].query(shapely.box(
            lo[live] - e_lo, la[live] - e_la, lo[live] + e_lo, la[live] + e_la))
        for i, q in zip(live[qi].tolist(), ti.tolist(), strict=True):
            out[i].append(q)
        for i, qs in out.items():
            keys = self._keys(float(lats[i]), float(lons[i]), reach_m)
            ranked = []
            for q in qs:
                rk = self._walk_rank(q, keys)
                if rk is not None:
                    ranked.append((rk, q))
            ranked.sort()
            out[i] = [q for _r, q in ranked]
        return out

    def _walk_rank(self, q: int, keys: list) -> "int | None":
        """The first of ``keys`` whose cell bucket holds triangle ``q``."""
        cr = self._cells[q]
        if cr is None:
            return 0
        i0, i1, j0, j1 = cr
        for r, k in enumerate(keys[1:], 1):
            if i0 <= k[0] <= i1 and j0 <= k[1] <= j1:
                return r
        return None

    def _contains_near(self, lat: float, lon: float, tol_m: float,
                       near: _t.Sequence[int]) -> bool:
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

    def top_at(self, lat: float, lon: float,
               reach_m: float = 0.0) -> "float | None":
        """issue #290: the deck's authored SURFACE height at a plan point
        — the highest of its own triangles containing the point,
        interpolated inside each (a ramp is sampled where it is, a
        stacked crossing reads its top).  A point OUTSIDE every triangle
        but within ``reach_m`` of one (a parapet or lamp post set on the
        deck's edge) reads that nearest triangle's nearest vertex.
        ``None`` beyond it, or for a print with no heights."""
        if (not self.tris or len(self.ys) != len(self.tris)
                or self._off_box(lat, lon, reach_m)):
            return None
        return self._top_near(lat, lon, reach_m, self._near(lat, lon, reach_m))

    def top_at_many(self, lats: _t.Sequence[float], lons: _t.Sequence[float],
                    reach_m: float = 0.0) -> "list[float | None]":
        """:meth:`top_at` for a batch of points, value for value (issue
        #1213; :meth:`_near_many`)."""
        out: "list[float | None]" = [None] * len(lats)
        if not self.tris or len(self.ys) != len(self.tris):
            return out
        for i, near in self._near_many(lats, lons, reach_m).items():
            out[i] = self._top_near(float(lats[i]), float(lons[i]), reach_m,
                                    near)
        return out

    def _top_near(self, lat: float, lon: float, reach_m: float,
                  near: _t.Sequence[int]) -> "float | None":
        best: "float | None" = None
        for q in near:
            w = _bary(self.tris[q], lat, lon)
            if w is None:
                continue
            y = sum(wi * yi for wi, yi in zip(w, self.ys[q]))
            if best is None or y > best:
                best = y
        if best is not None or reach_m <= 0.0:
            return best
        # the nearest EDGE point within reach, its height interpolated
        # along that edge (a 600 m road triangle's nearest VERTEX can be
        # 100 m down the ramp)
        t2 = (reach_m / max(self._ml, 1e-9)) ** 2
        k = self._mo / self._ml if self._ml else 1.0
        cand = None
        for q in near:
            t, ys = self.tris[q], self.ys[q]
            for i in range(3):
                a, b = t[i], t[(i + 1) % 3]
                dx, dy = b[0] - a[0], (b[1] - a[1]) * k
                den = dx * dx + dy * dy
                s = 0.0 if den < 1e-24 else max(0.0, min(1.0, (
                    (lat - a[0]) * dx + (lon - a[1]) * k * dy) / den))
                d = ((lat - a[0] - s * dx) ** 2
                     + ((lon - a[1]) * k - s * dy) ** 2)
                if d <= t2 and (cand is None or d < cand[0]):
                    cand = (d, ys[i] + s * (ys[(i + 1) % 3] - ys[i]))
        return None if cand is None else cand[1]


def _bary(t, lat: float, lon: float) -> "tuple[float, float, float] | None":
    """Barycentric weights of the point in plan triangle ``t``, or None
    outside it (``_in_tri``'s own arithmetic)."""
    (a0, a1), (b0, b1), (c0, c1) = t
    d = (b1 - c1) * (a0 - c0) + (c0 - b0) * (a1 - c1)
    if abs(d) < 1e-18:
        return None
    u = ((b1 - c1) * (lat - c0) + (c0 - b0) * (lon - c1)) / d
    v = ((c1 - a1) * (lat - c0) + (a0 - c0) * (lon - c1)) / d
    if u < 0.0 or v < 0.0 or u + v > 1.0:
        return None
    return (u, v, 1.0 - u - v)


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
            kept = [row for row in tris.tolist()
                    if all(int(q) in ll for q in row)]
            rows = tuple(tuple(ll[int(q)] for q in row) for row in kept)
            if not rows:
                continue
            ys = tuple(tuple(float(v[int(q), 1]) for q in row) for row in kept)
            las = [q[0] for t in rows for q in t]
            los = [q[1] for t in rows for q in t]
            p = DeckPrint(key=m.resource, unit=ui, member=mi,
                          under_y=float(min(c.min_y for c in comps)),
                          box=(min(las), min(los), max(las), max(los)),
                          tris=rows, ys=ys)
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
    return _pick_bridge([p for p in prints if p.contains(lat, lon, tol_m)],
                        top_y)


def _pick_bridge(hits: _t.Sequence[DeckPrint],
                 top_y: "float | None") -> "DeckPrint | None":
    """:func:`bridge_of_point`'s choice among the prints that hold the
    point (in ``prints`` order)."""
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
    # issue #1213: every body centre of the call in ONE batch per print
    # (:meth:`DeckPrint.contains_many`), then :func:`bridge_of_point`'s pick
    at: list = []
    for st in staged:
        st.bridge = [""] * len(st.raw)
        for bi in range(len(st.raw)):
            bx = hull_of(st.part_boxes[bi])
            if bx is None:
                continue
            tp = (max(st.part_tops[bi])
                  if bi < len(st.part_tops) and st.part_tops[bi] else None)
            at.append((st, bi, 0.5 * (bx[0] + bx[2]), 0.5 * (bx[1] + bx[3]),
                       tp))
    if not at:
        return
    las, los = [e[2] for e in at], [e[3] for e in at]
    held = [p.contains_many(las, los, CONTACT_M) for p in prints]
    for i, (st, bi, _la, _lo, tp) in enumerate(at):
        hit = _pick_bridge([p for p, h in zip(prints, held, strict=True) if h[i]], tp)
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


# ── owner RULINGS 2026-10-03e (#290): A UNIT'S VIADUCT ──────────────────

@_dc.dataclass(frozen=True)
class Viaduct:
    """A deck that is a MEMBER of a terminal unit (owner RULINGS
    2026-10-03e): the whole viaduct — deck, piers, sidewalks, railings,
    signs, kerbs — rides the unit's level as ONE rigid unit.

    ``uid`` / ``zero`` / ``where`` / ``src`` are the plan-wide §16g seat
    row of the unit (``footprint_unit.plan_wide_seats``) the deck's own
    model footprint stands in; ``voters`` the parts of that unit (of
    members sharing the deck's placement origin and heading) whose plan
    centre lies inside the footprint — the piers and sidewalks that make
    the deck the unit's."""

    deck: str
    unit: int
    member: int
    uid: str
    zero: float
    where: str
    src: str
    voters: int
    #: the deck's placement frame ``(lat, lon, heading)`` — what a piece
    #: BESIDE the plate must share to be the viaduct's (:func:`frame_of`)
    frame: tuple = ()
    #: issue #1179: the deck RESOURCE the viaduct is a connected piece of
    #: (``deck`` is that piece's key — the resource itself where the
    #: resource's footprint is ONE connected structure)
    resource: str = ""
    #: issue #1179: the viaduct's own footprint — ONE connected component
    #: of the deck's model footprint (:func:`deck_components`)
    print: _t.Any = _dc.field(default=None, compare=False, repr=False)
    #: the component is the WHOLE deck footprint: every body of the
    #: resource is the viaduct's without asking where it stands
    whole: bool = True


def frame_of(m: _t.Any) -> "tuple | None":
    """A member's PLACEMENT FRAME — its pack row's origin and heading —
    or None for a plan written without origins."""
    org = getattr(m, "origin", None)
    if org is None:
        return None
    return (round(float(org[0]), 9), round(float(org[1]), 9),
            round(float(getattr(m, "heading_deg", 0.0)), 6))


def unit_viaducts(prints: _t.Sequence[DeckPrint], plan: _t.Any,
                  plan_wide: _t.Mapping[int, tuple],
                  counts: "dict | None" = None, *,
                  surface: "_t.Callable[[float, float], float | None] | None"
                  = None, bar_m: float = 0.0) -> dict[str, Viaduct]:
    """owner RULINGS 2026-10-03e: WHICH DECKS ARE A UNIT'S — derived ONCE
    PER PLAN, keyed by the deck's resource.

    A deck is a unit member where parts of a §16g plan-wide unit, authored
    in members that SHARE THE DECK'S PLACEMENT ORIGIN AND HEADING (one
    pack row, one authored frame), stand inside the deck's own model
    footprint (:meth:`DeckPrint.contains`, §16e (3)'s contact reach) AND
    that unit holds parts OUTSIDE the footprint too — it is a terminal
    with a viaduct, not a bridge whose own piers chained into a unit of
    their own.  The unit is the plurality of those parts (ties: the lower
    unit id).  A deck no such unit claims is FREE-STANDING and keeps 2026-
    09-30g (3) — it is not in the result.

    A plan without placement origins (``Member.origin`` None, version
    < 12) names no viaduct: shared origin is the ruling's own evidence.

    owner RULINGS 2026-10-20av (#1179): with ``surface`` (the placement
    ground) and ``bar_m`` (the visibility bar) a claimed piece that is a
    GROUND PLATE ON REAL RELIEF (:func:`ground_plate_on_relief`) is no
    viaduct — it is free-standing and keeps 2026-09-30g (3)."""
    out: dict[str, Viaduct] = {}
    if not prints or not plan_wide:
        return out
    rows: dict[str, tuple] = {}
    for r in plan_wide.values():
        rows.setdefault(r[0], r)
    for key, (uid, voters, frame, p) in sorted(viaduct_units(
            prints, plan, lambda q: (plan_wide.get(q.pid) or ("",))[0],
            counts).items()):
        if surface is not None and ground_plate_on_relief(p, surface,
                                                          bar_m):
            if counts is not None:
                counts["viaduct_ground_plates_free_standing"] = \
                    counts.get("viaduct_ground_plates_free_standing", 0) + 1
            continue
        row = rows[uid]
        res = key.split(_PIECE, 1)[0]
        out[key] = Viaduct(key, p.unit, p.member, uid, float(row[1]),
                           str(row[2]), str(row[3]), voters, frame,
                           res, p, key == res)
    return out


def ground_plate_on_relief(p: DeckPrint,
                           surface: _t.Callable[[float, float], "float | None"],
                           bar_m: float) -> bool:
    """owner RULINGS 2026-10-20av (#1179): A GROUND PLATE ON REAL RELIEF
    IS FREE-STANDING, NOT A VIADUCT.

    True where the piece is a PLATE AT THE GROUND — its authored surface
    never rises above its placement's ground (highest ``y`` within
    ``bar_m`` of 0 or below it: a sheet laid on, or draped down over, the
    terrain from its datum, never a deck held up on piers) — AND the
    ground under its footprint (``surface`` at its vertices) varies by
    more than ``bar_m``: no one level seats it, so each piece on it stands
    on its own ground.  A print without heights, or with no ground read
    under it, is no plate.

    MEASURED (LFLL plan replay): the ground sheets a unit claimed author
    ``y`` from 0 down to -10 m (terrain draped from the pack's datum); the
    decks a unit rightly carries (#290's ramp, terminal floors at +4 m,
    concourse roofs) all rise metres above 0."""
    if bar_m <= 0.0 or not p.tris or len(p.ys) != len(p.tris):
        return False
    if max(y for t in p.ys for y in t) > bar_m:
        return False
    gz = [g for t in p.tris for q in t
          for g in (surface(float(q[0]), float(q[1])),) if g is not None]
    return bool(gz) and max(gz) - min(gz) > bar_m


#: issue #1179: how a connected piece of a deck footprint is keyed —
#: ``<resource>#<k>``; a footprint that is ONE piece keeps its resource
_PIECE = "#"


def deck_components(p: DeckPrint, gap_m: float = CONTACT_M
                    ) -> list[DeckPrint]:
    """issue #1179 (owner RULINGS 2026-10-03e read with 2026-09-13bo): a
    VIADUCT IS ONE CONNECTED DECK STRUCTURE, NOT A RESOURCE.

    The deck's model footprint split into its CONNECTED pieces —
    triangles chained where they come within ``gap_m`` of each other in
    plan (§16e (3)'s contact reach).  A pack that authors one resource
    across the whole airport (tyres, carts, masts, ground plates under a
    shared datum) is many structures separated by open ground, and each
    is claimed — or not — on its own.  A footprint that is ONE piece is
    returned as itself (key unchanged); otherwise piece ``k`` is keyed
    ``<resource>#<k>`` in the order of its first triangle.  Memoised on
    the print."""
    memo = p._pieces.get(gap_m)                              # noqa: SLF001
    if memo is not None:
        return memo
    n = len(p.tris)
    lab = _touch_components(p, float(gap_m)) if n > 1 else [0] * n
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(lab[i], []).append(i)
    if len(groups) <= 1:
        out = [p]
    else:
        out = []
        for k, idx in enumerate(sorted(groups.values(), key=lambda g: g[0])):
            tris = tuple(p.tris[i] for i in idx)
            ys = (tuple(p.ys[i] for i in idx)
                  if len(p.ys) == len(p.tris) else ())
            las = [q[0] for t in tris for q in t]
            los = [q[1] for t in tris for q in t]
            c = DeckPrint(key=f"{p.key}{_PIECE}{k}", unit=p.unit,
                          member=p.member,
                          under_y=(min(y for t in ys for y in t) if ys
                                   else p.under_y),
                          box=(min(las), min(los), max(las), max(los)),
                          tris=tris, ys=ys)
            c.index()
            out.append(c)
    p._pieces[gap_m] = out                                   # noqa: SLF001
    return out


def _first_per_key(key, k: int):
    """Indices of the first ``k`` entries (in order) of each distinct
    ``key`` value."""
    import numpy as np
    order = np.argsort(key, kind="stable")
    ks = key[order]
    start = np.r_[0, np.nonzero(ks[1:] != ks[:-1])[0] + 1]
    rank = np.arange(ks.size) - np.repeat(start, np.diff(np.r_[start, ks.size]))
    return np.sort(order[rank < k])


def _touch_components(p: DeckPrint, gap_m: float) -> list[int]:
    """The component label of each triangle of ``p`` — triangles chained
    where they come within ``gap_m`` in plan (GEOS ``dwithin``, the
    predicate :func:`deck_components` always read).

    issue #1213: the SAME PARTITION as testing every pair, at a fraction
    of the cost (KMCI's 325 k-triangle steel frame: 373 M box-near pairs,
    222 s).  Triangles sharing a vertex (the same plan coordinate) touch,
    so they are chained first with no test.  The box-near pairs are then
    read in source CHUNKS, and a pair is tested only while its two
    triangles are still in different components — one pair per component
    pair in the first round (4, 16, ... after), the components re-read
    after each round's unions — so
    a pair is skipped only once its answer can no longer change the
    partition."""
    import numpy as np
    import shapely
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(p.tris)
    ml, mo = p._ml, p._mo                                    # noqa: SLF001
    xy = np.array([[(q[0] * ml, q[1] * mo) for q in t] for t in p.tris],
                  dtype=float)
    u, vid = np.unique(xy.reshape(-1, 2), axis=0, return_inverse=True)
    m = len(u)
    g = coo_matrix((np.ones(3 * n, dtype=np.int8),
                    (np.repeat(np.arange(n), 3), n + vid.reshape(-1))),
                   shape=(n + m, n + m))
    lab0 = connected_components(g, directed=False)[1][:n]   # shared vertex
    parent = np.arange(int(lab0.max()) + 1)
    geo = shapely.polygons(np.concatenate([xy, xy[:, :1]], axis=1))
    tree = shapely.STRtree(geo)
    shapely.prepare(geo)
    r = gap_m + 1e-3                     # a millimetre over: a superset
    lo, hi = xy.min(axis=1), xy.max(axis=1)
    boxes = shapely.box(lo[:, 0] - r, lo[:, 1] - r, hi[:, 0] + r, hi[:, 1] + r)

    def _flat(par: np.ndarray) -> np.ndarray:
        while True:
            nxt = par[par]
            if np.array_equal(nxt, par):
                return par
            par = nxt
    step = 4096
    for c0 in range(0, n, step):
        qa, qb = tree.query(boxes[c0:c0 + step])
        qa = qa + c0
        keep = qa < qb
        qa, qb = qa[keep], qb[keep]
        k_max = 1
        while qa.size:
            parent = _flat(parent)
            ra, rb = parent[lab0[qa]], parent[lab0[qb]]
            live = ra != rb
            qa, qb, ra, rb = qa[live], qb[live], ra[live], rb[live]
            if not qa.size:
                break
            lo_r, hi_r = np.minimum(ra, rb), np.maximum(ra, rb)
            first = _first_per_key(lo_r * (len(parent) + 1) + hi_r, k_max)
            k_max *= 4
            # the tree's own reading: the SOURCE geometry prepared, either
            # way round (a polygon collapsed to a point reads no distance)
            ta, tb = geo[qa[first]], geo[qb[first]]
            hit = (shapely.dwithin(ta, tb, gap_m)
                   | shapely.dwithin(tb, ta, gap_m))
            for x, y in zip(lo_r[first][hit].tolist(),
                            hi_r[first][hit].tolist(), strict=True):
                while parent[x] != x:
                    x = parent[x]
                while parent[y] != y:
                    y = parent[y]
                if x != y:
                    parent[max(x, y)] = min(x, y)
            done = np.ones(qa.size, dtype=bool)
            done[first] = False
            qa, qb = qa[done], qb[done]
    return _flat(parent)[lab0].tolist()


def viaduct_of(vias: "_t.Sequence[Viaduct] | None",
               parts: _t.Sequence[_t.Any]) -> "Viaduct | None":
    """issue #1179: WHICH of a deck resource's claimed viaducts a body is
    a piece of — the WHOLE-footprint viaduct outright (one connected
    structure: every body of the resource is it), otherwise the first
    (by key) connected piece whose footprint holds one of the body's
    parts' plan centres (§16e (3)'s contact reach).  None: the body
    stands on open ground away from every claimed piece and keeps its
    own seat."""
    for v in vias or ():
        if v.whole or v.print is None:
            return v
        if any(v.print.contains_many([float(q.lat) for q in parts],
                                     [float(q.lon) for q in parts])):
            return v
    return None


def viaduct_units(prints: _t.Sequence[DeckPrint], plan: _t.Any,
                  key_of: _t.Callable[[_t.Any], "str | None"],
                  counts: "dict | None" = None
                  ) -> dict[str, tuple[str, int, tuple, DeckPrint]]:
    """THE ONE DERIVATION of owner RULINGS 2026-10-03e's relation — which
    unit a deck belongs to — over any reading of "unit": ``key_of(part)``
    names the unit a pack part stands in (the object stage: its §16g
    plan-wide seat row; the planar stage: the held platform BLOCK its
    centre stands on, ``planar.landing``), ``None``/``""`` for none.

    ``{deck key: (unit key, voters, deck frame, print)}``: the plurality
    (ties: the lower key) of the parts of members SHARING THE DECK'S
    PLACEMENT FRAME whose plan centre lies inside the deck's model
    footprint, kept only where that unit holds parts OUTSIDE the footprint
    too.  Every other deck is FREE-STANDING and absent."""
    out: dict[str, tuple[str, int, tuple, DeckPrint]] = {}
    if not prints:
        return out
    total: dict[str, int] = {}
    #: the keyed part centres per authored FRAME (a deck reads only its
    #: own frame's), in plan order
    keyed: dict[tuple, list] = {}
    for ui, u in enumerate(plan.units):
        for mi, mm in enumerate(u.members):
            fr = frame_of(mm)
            for q in mm.parts:
                k = key_of(q)
                if not k:
                    continue
                total[k] = total.get(k, 0) + 1
                b = q.box
                keyed.setdefault(fr, []).append(
                    ((ui, mi), 0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3]), k))
    from ..model import pulse as _pulse
    for p in _pulse.each(prints, "viaducts: deck footprints", "decks"):
        frame = frame_of(plan.units[p.unit].members[p.member])
        if frame is None:
            continue
        own = [e for e in keyed.get(frame, ()) if e[0] != (p.unit, p.member)]
        hit = p.contains_many([e[1] for e in own], [e[2] for e in own])
        inside = [e[1:] for e, h in zip(own, hit, strict=True) if h]
        # issue #1179: each CONNECTED piece of the footprint is claimed on
        # its own — the votes are the parts inside THAT piece
        pieces = deck_components(p) if inside else [p]
        for c in pieces:
            votes: dict[str, int] = {}
            on = ([True] * len(inside) if c is p else
                  c.contains_many([e[0] for e in inside],
                                  [e[1] for e in inside]))
            for (_la, _lo, k), h in zip(inside, on, strict=True):
                if h:
                    votes[k] = votes.get(k, 0) + 1
            votes = {k: v for k, v in votes.items() if total.get(k, 0) > v}
            if not votes:
                if counts is not None:
                    counts["viaduct_decks_free_standing"] = \
                        counts.get("viaduct_decks_free_standing", 0) + 1
                continue
            k = min(votes, key=lambda x: (-votes[x], x))
            out[c.key] = (k, votes[k], frame, c)
            if counts is not None:
                counts["viaduct_decks_of_a_unit"] = \
                    counts.get("viaduct_decks_of_a_unit", 0) + 1
    return out


def landing_pieces(p: DeckPrint, band_m: float
                   ) -> list[tuple[tuple[tuple[float, float], ...], float]]:
    """owner RULINGS 2026-10-03e: THE RAMP LANDINGS of a deck — every
    triangle of its model footprint CLIPPED to where the deck's authored
    surface stands within ``band_m`` of its lowest ``y`` (a ramp end; a
    long ramp triangle contributes its low sliver), as ``(lat/lon ring,
    LOWEST authored y of the piece)`` — the landing's foot.  The caller unions the pieces in its
    own plan frame into the landings."""
    if not p.tris or len(p.ys) != len(p.tris):
        return []
    lo = min(y for t in p.ys for y in t)
    cut = lo + float(band_m)
    out = []
    for t, ys in zip(p.tris, p.ys):
        if min(ys) > cut:
            continue
        pts: list = []
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            ya, yb = ys[i], ys[(i + 1) % 3]
            if ya <= cut:
                pts.append((a[0], a[1], ya))
            if (ya <= cut) != (yb <= cut) and yb != ya:
                f = (cut - ya) / (yb - ya)
                pts.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]),
                            cut))
        if len(pts) >= 3:
            out.append((tuple((q[0], q[1]) for q in pts),
                        min(q[2] for q in pts)))
    return out


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
