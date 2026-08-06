"""THE CONSTANT-DEM ORACLE — the build oracle with no terrain confound.

OWNER LAW (RULINGS 2026-08-05, "there is no lawful-infeasible ground" +
its sharpening): *DEM is a SEED, nothing more.  It seats things within
their feasible bands; it never shapes a band.*  The direct consequence is
an oracle no real-terrain build can give:

    Build a REAL airport's geometry against a CONSTANT DEM and the
    surface must be perfectly lawful.  There is no terrain signal, so
    every emitted violation is a law, solver or instrument defect with
    nothing to blame it on.

TWO SYNTHETIC WORLDS, and they are not interchangeable — the pair is the
instrument:

* ``PLATEAU`` (DEM ≡ −500 m, owner ruling 2026-08-06): the ground is a
  giant plateau *below* everything.  Every free value is seated at the
  FLOOR of its feasible band.
* ``CANYON`` (DEM ≡ 10 000 m): the ground is high above everything.
  Every free value is seated at the CEILING of its band.

THREE ASSERTIONS the oracle makes, in ascending power:

1. **COMPLIANCE** — zero law-true rows in BOTH worlds.  Necessary, and
   the weakest of the three: a surface can be lawful and still be
   authored by something other than the law.
2. **EXTREME-SEATING SATURATION** — in each world every free node sits at
   the band edge nearest its seed.  A node that is NOT saturated in the
   flat world is being pulled by something that is not the seed: a hidden
   authority.  That is the defect class the oracle exists to catch and
   the one plain compliance cannot see.
3. **THE BAND-WIDTH FIELD** — the per-node difference
   ``canyon(node) - plateau(node)`` IS the width of the feasible band the
   law grants at that node.  Emitted as a diagnostic artifact, it is the
   direct empirical map of the corridor, per node, and it is CHECKED
   against the analytic band by :func:`band_agreement_report` (the two
   independent suppliers of one quantity, agreement reported within
   materiality — RULINGS 2026-08-06 binding point 4).  A node whose
   measured width is 0 is PINNED; one whose width disagrees with the
   analytic band is a law/solver disagreement with an exact address.

WHY A SUBSTITUTED SOURCE AND NOT A LAW GATE.  This is an explicit
DEM-source substitution handed to ``build_airport_pavement(tile_dem=...)``
— the same seam Ortho4XP's own ``tile.dem`` uses.  No law changes, no
environment flag alters a rule; the only difference between an oracle
build and a production build is which surface answers ``alt()``.

THE ALL-ZERO REFUSAL STAYS.  ``elevation._load_airport_dem`` refuses a
disk-composed surface that samples zero everywhere, because that means the
base raster is ABSENT (the measurement trap that reported an 85 m error as
real geometry).  That guard is about missing data and is untouched: it
lives in the disk-load branch, while an oracle DEM arrives as
``override_dem`` and is returned before it.  Constant data is not absent
data — but it must be handed over EXPLICITLY, which is exactly what this
module makes callers do.

THE LOW EXTREME IS −500 m (owner ruling 2026-08-06), superseding the
"DEM ≡ 0" letter of the constant-DEM invariant.  It is below every CIFP
value, so floor-seating is GUARANTEED everywhere rather than merely
likely, and below-sea-level handling is exercised for free.  The DEM ≡ 1 m
interim this module used to carry was an unruled dodge around the loader's
all-zero guard — a guard the oracle never reaches, because an oracle DEM
is an ``override_dem`` — and the ruling RETIRES it.  Nothing about the low
world may be inferred from the sign of its elevation: a synthetic constant
is a VALUE, and the only sentinel it may never be is ``nodata``
(:data:`NODATA_SENTINEL`), which :class:`ConstantDEM` refuses outright
because every ``v == dem.nodata`` check in the tree would read that world
as absent data.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

__all__ = [
    "ConstantDEM", "PLATEAU_ELEVATION_M", "CANYON_ELEVATION_M",
    "SEED_SPAN_M", "NODATA_SENTINEL", "seed_span_m",
    "plateau_dem", "canyon_dem", "band_width_field",
    "saturation_report", "saturation_summary", "SaturationRow",
    "band_agreement_report", "BAND_AGREEMENT_MATERIALITY_M",
]

#: The DEM no-data sentinel every reader in the tree compares against
#: (``seam_anchors``, ``tile_cut``, ``runway_redistribute``,
#: ``runway_regrade`` all do ``v == dem.nodata``).  A synthetic world AT
#: this value would be read as ABSENT data by all of them, so it is the
#: one constant :class:`ConstantDEM` refuses.  Nothing else about a
#: synthetic constant's sign or magnitude is constrained.
NODATA_SENTINEL = -32768

#: The two worlds.
#:
#: THE LOW EXTREME IS −500 m (owner ruling 2026-08-06): "to effectively
#: exercise the intention of the extreme low DEM … no particular need for
#: zero, negative is better."  It sits BELOW EVERY CIFP VALUE, so
#: floor-seating is guaranteed everywhere instead of merely likely, and
#: below-sea-level handling is exercised for free.
#:
#: This supersedes the old ``1.0``.  That value existed only to dodge the
#: loader's all-zero refusal ("a literal zero is indistinguishable from no
#: data") — a dodge the ruling calls out as unruled and RETIRES, because
#: the oracle never reaches that guard: its DEM arrives as ``override_dem``
#: and is returned before the disk-compose branch that carries it.
#:
#: Both worlds are far outside any real airport elevation, so a leaked
#: real sample is obvious in either.
PLATEAU_ELEVATION_M = -500.0
CANYON_ELEVATION_M = 10000.0

#: THE ANALYTIC ENVELOPE of the band-width field, DERIVED from the pair —
#: never a literal.  ``canyon(node) - plateau(node)`` is a seated
#: difference, so it lies in ``[0, SEED_SPAN_M]``: below 0 the high world
#: seated under the low one (non-monotone in the seed), above the span the
#: surface moved FURTHER than the seed did (an amplifying authority).
#:
#: It used to be the unwritten ``[0, 9999]`` of the 1 m / 10 000 m pair,
#: which quietly assumed a NON-NEGATIVE low world.  With the low extreme
#: at −500 m the envelope is ``[0, 10500]``, and any instrument that
#: hard-codes either end is wrong the moment the owner re-rules a world —
#: so read it from here, or from :func:`seed_span_m` for an explicit pair.
SEED_SPAN_M = CANYON_ELEVATION_M - PLATEAU_ELEVATION_M


def seed_span_m(plateau_m: float = PLATEAU_ELEVATION_M,
                canyon_m: float = CANYON_ELEVATION_M) -> float:
    """The seed swing between two worlds — the band-width field's upper
    envelope.  Explicit so a runner driving a non-default ``--worlds``
    pair reports ITS OWN envelope rather than the module default's."""
    return float(canyon_m) - float(plateau_m)


def _world_label_for(elevation_m: float) -> str:
    """``"plateau"`` / ``"canyon"`` for the two ruled worlds, else
    ``"constant"``.  A label, never a rule: nothing branches on it, and in
    particular the SIGN of the constant means nothing — the low world is
    the ruled −500 m, and a build at any other constant is still a
    perfectly legal synthetic world with no special seating claim."""
    if elevation_m == PLATEAU_ELEVATION_M:
        return "plateau"
    if elevation_m == CANYON_ELEVATION_M:
        return "canyon"
    return "constant"


class ConstantDEM:
    """A DEM that answers one elevation everywhere.

    Implements the surface of ``O4_DEM_Utils.DEM`` that ``auto_patch``
    actually consumes — measured by grep, not guessed: ``alt`` (26 call
    sites), ``alt_strict``, ``alt_vec``, ``alt_dem`` +
    ``nxdem``/``nydem``/``x0``/``x1``/``y0``/``y1`` (the OLS raster
    reader), ``nodata``, and the ``lat``/``lon``/``elevation_level``
    identity fields.

    ``nxdem``/``nydem`` default to a 2x2 raster: large enough that the
    raster consumers do not bail, small enough to cost nothing.

    THE ONE REFUSED VALUE.  ``elevation_m`` may be any finite number —
    negative included, which is the point of the −500 m low world — EXCEPT
    :data:`NODATA_SENTINEL`.  Four readers in the tree branch on
    ``v == dem.nodata`` (``seam_anchors``, ``tile_cut``,
    ``runway_redistribute``, ``runway_regrade``), so a synthetic world at
    the sentinel would be read as ABSENT DATA by all of them and the build
    would silently measure a different world than the one requested.  That
    collision was unreachable while the low world was a small POSITIVE
    constant; allowing negatives opens it, so it is closed here, loudly,
    at the one place every synthetic DEM is constructed.

    ``is_synthetic`` marks the object for any caller that needs to say
    "this build's surface was SUBSTITUTED, not loaded" in a report — the
    explicitness the owner's ruling asks for, carried by the object itself
    rather than reconstructed from a flag somewhere up the call stack.
    """

    #: Every instance is a substituted surface, never loaded data.
    is_synthetic = True

    def __init__(self, elevation_m: float,
                 lat: int = 0, lon: int = 0, n: int = 2,
                 world_label: str = ""):
        elevation_m = float(elevation_m)
        if elevation_m != elevation_m or elevation_m in (
                float("inf"), float("-inf")):
            raise ValueError(
                f"a synthetic constant DEM must be a finite elevation, got "
                f"{elevation_m!r}")
        if elevation_m == float(NODATA_SENTINEL):
            raise ValueError(
                f"REFUSING a synthetic DEM at {NODATA_SENTINEL} m: that is "
                f"the NO-DATA SENTINEL every DEM reader in the tree compares "
                f"against (v == dem.nodata in seam_anchors, tile_cut, "
                f"runway_redistribute, runway_regrade).  A world at this "
                f"value would be read as ABSENT data, not as constant data, "
                f"and the build would silently measure a different world.  "
                f"Any other finite constant is legal, negatives included "
                f"(the ruled low world is {PLATEAU_ELEVATION_M:g} m).")
        self.elevation_m = elevation_m
        self.lat = int(lat)
        self.lon = int(lon)
        self.elevation_level = 0
        self.world_label = world_label or _world_label_for(self.elevation_m)
        self.source_path = (f"<constant-dem {self.elevation_m:g} m "
                            f"[{self.world_label}]>")
        self.baked_query_active = False
        self.nodata = NODATA_SENTINEL
        self.nxdem = int(n)
        self.nydem = int(n)
        self.x0, self.x1 = 0.0, 1.0
        self.y0, self.y1 = 0.0, 1.0
        self.subdems = tuple()
        try:
            import numpy as _np
            self.alt_dem = _np.full((self.nydem, self.nxdem),
                                    self.elevation_m, dtype="float32")
        except Exception:                            # pragma: no cover
            self.alt_dem = None

    # ── the sampling surface ──────────────────────────────────────────
    def alt(self, xy) -> float:
        return self.elevation_m

    def alt_strict(self, xy) -> float:
        return self.elevation_m

    def alt_vec(self, x, y=None):
        try:
            import numpy as _np
            arr = _np.asarray(x)
            return _np.full(arr.shape[:1] or (1,), self.elevation_m,
                            dtype="float64")
        except Exception:                            # pragma: no cover
            return [self.elevation_m]

    def get(self, *a, **kw) -> float:
        return self.elevation_m

    def __repr__(self) -> str:                       # pragma: no cover
        return (f"ConstantDEM({self.elevation_m:g} m, "
                f"{self.world_label}, synthetic)")


def plateau_dem(lat: int = 0, lon: int = 0) -> ConstantDEM:
    """The LOW world (−500 m, owner ruling 2026-08-06): everything seats at
    the FLOOR of its band.  Below every CIFP value, so the floor-seating is
    guaranteed rather than merely likely."""
    return ConstantDEM(PLATEAU_ELEVATION_M, lat, lon, world_label="plateau")


def canyon_dem(lat: int = 0, lon: int = 0) -> ConstantDEM:
    """The HIGH world: everything seats at the CEILING of its band."""
    return ConstantDEM(CANYON_ELEVATION_M, lat, lon, world_label="canyon")


# ── the two derived instruments ───────────────────────────────────────

def node_author(shape) -> str:
    """``"role/ref"`` — WHO wrote this shape's vertices.

    The band-width join's author key.  ``role`` alone is too coarse: a
    ``graded_strip`` minted as a ``runway_end_skirt`` and one minted by
    the adjacent-ground march are different authors under different law,
    and they share coordinates wherever they abut.
    """
    return f"{getattr(shape, 'role', '?')}/{getattr(shape, 'ref', '') or ''}"


def _node_values(layout) -> dict:
    """``{(author, x, y) rounded: elevation}`` over every value-carrying
    vertex of a layout, keyed on the AUTHOR plus the metre-frame
    coordinate so the two worlds' node sets can be joined by IDENTITY
    (they are the same geometry: the DEM is a seed, so a constant DEM
    cannot move a vertex in plan).

    THE AUTHOR IS PART OF THE KEY (fix 2026-08-05, fix-lane-2 evidence in
    ``scratchpad/fix2/who/``).  It used to be ``{(x, y): elevation}``, so
    at any coordinate two shapes share — and abutting surfaces share
    coordinates by construction, that is what welding IS — the LAST shape
    iterated won.  Shape order and shape COUNT differ between the two
    worlds, so the same key could be written by a ``runway_end_skirt`` in
    one world and by ``adjacent_ground`` / ``resa`` / ``apron`` in the
    other, and the "band width" reported at that node was the difference
    between TWO DIFFERENT SURFACES.  Measured: 9 of the 95 negative-width
    rows were cross-family joins — a negative width is supposed to be
    impossible-on-its-face evidence of a non-monotone seating, and nine of
    them were the instrument describing two populations at once.

    Rounded to the millimetre — the canonical registry's own resolution is
    far coarser (0.5 m), so a millimetre key never merges two real nodes
    and never splits one.
    """
    out: dict = {}
    for shape in getattr(layout, "shapes", ()) or ():
        poly = getattr(shape, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        try:
            ring = list(poly.exterior.coords)
        except Exception:                            # pragma: no cover
            continue
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        alts = shape.node_altitudes
        if alts is not None:
            vals = [None if a is None else float(a) for a in alts]
        elif shape.altitude is not None:
            vals = [float(shape.altitude)] * len(ring)
        else:
            continue
        author = node_author(shape)
        for (x, y), v in zip(ring, vals):
            if v is None:
                continue
            out[(author, round(float(x), 3), round(float(y), 3))] = v
    return out


def band_width_field(plateau_layout, canyon_layout) -> dict:
    """ASSERTION 3's artifact: ``{(author, x, y): canyon - plateau}``.

    The per-node difference between the two worlds is the WIDTH of the
    feasible band the law grants at that node — the direct empirical map
    of the corridor, measurable against the analytic bands.

    A width of 0 means the node is PINNED (an authority, a weld, a
    threshold): it has no freedom, and no seed can move it.  A NEGATIVE
    width is a defect on its face — the high world seated a node BELOW the
    low world, which no monotone seating can do.

    SAME AUTHOR ON BOTH SIDES.  The key carries ``role/ref`` (see
    :func:`_node_values`): differencing a ``runway_end_skirt`` vertex in
    one world against the ``apron`` vertex that shares its coordinate in
    the other is two instruments on one assumed population, and it minted
    9 of the 95 negative widths this artifact reported.  A coordinate that
    two surfaces share now yields one row PER SURFACE, which is the honest
    answer: they are two nodes with two bands.
    """
    lo = _node_values(plateau_layout)
    hi = _node_values(canyon_layout)
    return {k: hi[k] - lo[k] for k in lo.keys() & hi.keys()}


class SaturationRow:
    """One node's seating verdict in one world.

    ``xy`` is the metre-frame coordinate; ``author`` is the ``role/ref``
    that wrote it.  THE AUTHOR IS THE POINT — assertion 2 exists to name
    what is holding an unsaturated node, and a bare coordinate names
    nothing.  Two surfaces welded at one coordinate are two rows.
    """

    __slots__ = ("xy", "author", "value", "floor", "ceil", "world",
                 "saturated", "off_edge_m")

    def __init__(self, xy, value, floor, ceil, world, author=""):
        self.xy = xy
        self.author = author
        self.value = float(value)
        self.floor = floor
        self.ceil = ceil
        self.world = world
        edge = floor if world == "plateau" else ceil
        if edge is None:
            self.off_edge_m = 0.0
            self.saturated = True
        else:
            self.off_edge_m = self.value - float(edge)
            self.saturated = abs(self.off_edge_m) <= 1e-6

    def as_dict(self) -> dict:
        return {"author": self.author, "x": self.xy[0], "y": self.xy[1],
                "value_m": round(self.value, 4),
                "floor": (None if self.floor is None
                          else round(float(self.floor), 4)),
                "ceil": (None if self.ceil is None
                         else round(float(self.ceil), 4)),
                "world": self.world,
                "off_edge_m": round(self.off_edge_m, 4)}

    def __repr__(self) -> str:                       # pragma: no cover
        return (f"SaturationRow({self.author}@{self.xy}, "
                f"v={self.value:.3f}, [{self.floor}, {self.ceil}], "
                f"{self.world}, sat={self.saturated})")


def saturation_report(layout, world: str, band_of,
                      tol_m: float = 1e-6,
                      coverage_out: Optional[dict] = None) -> list:
    """ASSERTION 2: every free node must sit at the band edge nearest its
    seed.

    ``band_of((x, y)) -> (floor, ceil) | None`` supplies the ANALYTIC band
    at a node — ``None`` for "no band here" (the node is off the network
    and only its within-shape law governs it), and ``None`` on either side
    for "unbounded in that direction".  Returns the rows that are NOT
    saturated: the nodes something other than the seed is holding, each
    naming its AUTHOR.  An empty list is the pass.

    ``world`` is ``"plateau"`` (seed below ⇒ expect the FLOOR) or
    ``"canyon"`` (seed above ⇒ expect the CEILING).

    THE KEY BUG THIS FIXES (fix cycle 2 item 3, verdict (d) BROKEN
    INSTRUMENT).  ``_node_values`` was re-keyed from ``(x, y)`` to
    ``(author, x, y)`` when the band-width join was fixed to stop crossing
    authors — and this reader kept passing its key STRAIGHT to
    ``band_of``.  Every supplier is coordinate-keyed (the engine's own
    ``reach_band_unified`` contract is literally ``band(x, y)``), so every
    lookup missed, every node was skipped as "no band", and the reader
    returned ``[]``.

    ``[]`` is also what a PASS looks like.  So assertion 2 read as a clean
    pass on every airport in the campaign while evaluating nothing at all —
    which is why the re-baseline had to record it as NOT EVALUATED rather
    than as a result.  The reader now splits the key: the coordinate goes
    to the supplier, the author goes into the row.

    ``coverage_out`` — an out-dict that receives ``{"nodes", "with_band",
    "no_band", "unsaturated"}``, the DENOMINATOR of this report.  Without
    it the return value alone cannot tell "every node was checked and all
    were saturated" from "the supplier answered ``None`` at every node and
    nothing was checked", and those two look identical (``[]``) — the same
    shape as the key-shape bug above, one supplier further out.  The
    reader does not adjudicate the difference; it reports the counts and
    lets the caller (``tools/harness/oracle.py``) decide.
    """
    if world not in ("plateau", "canyon"):
        raise ValueError(f"world must be plateau|canyon, got {world!r}")
    unsaturated = []
    n_nodes = n_band = 0
    for key, value in _node_values(layout).items():
        author, x, y = key
        xy = (x, y)
        n_nodes += 1
        band = band_of(xy)
        if band is None:
            continue
        n_band += 1
        floor, ceil = band
        row = SaturationRow(xy, value, floor, ceil, world, author)
        if not row.saturated:
            unsaturated.append(row)
    unsaturated.sort(key=lambda r: -abs(r.off_edge_m))
    if coverage_out is not None:
        coverage_out.update({"nodes": n_nodes, "with_band": n_band,
                             "no_band": n_nodes - n_band,
                             "unsaturated": len(unsaturated)})
    return unsaturated


def saturation_summary(rows, top: int = 10) -> dict:
    """Group an unsaturated-row list BY AUTHOR — assertion 2's verdict.

    "Every unsaturated free node's author named" is the contract; a count
    without authors says a hidden authority exists but not whose it is,
    which is the shape of every attribution round this campaign has had to
    repeat.  Authors are ranked by worst |off_edge_m|, not by count: one
    node 9 900 m off its ceiling is the finding, a thousand at 0.02 m is
    the floor noise.
    """
    by_author: dict = {}
    for r in rows:
        slot = by_author.setdefault(r.author, {"author": r.author, "n": 0,
                                               "worst_off_edge_m": 0.0,
                                               "worst_xy": None})
        slot["n"] += 1
        if abs(r.off_edge_m) > abs(slot["worst_off_edge_m"]):
            slot["worst_off_edge_m"] = round(r.off_edge_m, 4)
            slot["worst_xy"] = [round(r.xy[0], 2), round(r.xy[1], 2)]
    ranked = sorted(by_author.values(),
                    key=lambda a: -abs(a["worst_off_edge_m"]))
    return {"unsaturated": len(rows), "authors": len(ranked),
            "by_author": ranked[:top],
            "worst_rows": [r.as_dict() for r in rows[:top]]}


def band_width_summary(field: dict, span_m: Optional[float] = None) -> dict:
    """Report shape of a ``band_width_field`` — for the artifact header.

    ``span_m`` is the ANALYTIC ENVELOPE's upper end: the seed swing between
    the two worlds that produced ``field`` (:func:`seed_span_m`; default
    :data:`SEED_SPAN_M`, the module's own pair).  A seated difference lies
    in ``[0, span_m]``, and both ends are findings:

    * below 0 — the high world seated a node UNDER the low world, which no
      monotone seating can do;
    * above the span — the surface moved FURTHER than its seed did, i.e.
      something amplified the seed instead of being seeded by it.

    THE ENVELOPE IS DERIVED, NEVER A LITERAL (fix, cycle 7.5).  It used to
    be the unwritten ``[0, 9999]`` of the 1 m / 10 000 m pair — an
    assumption that the low world is NON-NEGATIVE, invisible because it was
    never spelled anywhere.  With the ruled −500 m low world the envelope
    is ``[0, 10500]``, and a runner on a custom ``--worlds`` pair gets its
    own.  ``span_m`` is reported beside the counts so a later reader can
    see which envelope the numbers were judged in (frame stamps, RULINGS
    2026-08-06 "Instrument truth is law" §3).
    """
    span = float(SEED_SPAN_M if span_m is None else span_m)
    if not field:
        return {"nodes": 0, "seed_span_m": span,
                "envelope_m": [0.0, span]}
    widths = sorted(field.values())
    n = len(widths)
    negative = [w for w in widths if w < -1e-6]
    pinned = [w for w in widths if abs(w) <= 1e-6]
    over_span = [w for w in widths if w > span + 1e-6]
    return {
        "nodes": n,
        "pinned": len(pinned),
        "negative": len(negative),
        "over_span": len(over_span),
        "seed_span_m": span,
        "envelope_m": [0.0, span],
        "min": widths[0],
        "p50": widths[n // 2],
        "max": widths[-1],
        "mean": math.fsum(widths) / n,
    }


#: Materiality for the band-width agreement (Task 5 / binding point 4).
#: The campaign's standing elevation-class materiality floor (Ortho4XP/
#: CLAUDE.md convergence guards: "default 0.01 m for elevation classes"); a
#: residual below it is reported as agreement-with-residual, never chased.
BAND_AGREEMENT_MATERIALITY_M = 0.01


def band_agreement_report(field: dict, band_of,
                          materiality_m: float = BAND_AGREEMENT_MATERIALITY_M,
                          top: int = 10) -> dict:
    """ASSERTION 3's second half: the TWO SUPPLIERS of one quantity, compared.

    Owner law binding point 4 (RULINGS 2026-08-06, "Instrument truth is
    law"): *two independent instruments per load-bearing quantity,
    agreement asserted within materiality*.  The band width at a node has
    exactly two suppliers in this tree and they share no code:

      * MEASURED — ``band_width_field``: ``canyon(node) − plateau(node)``,
        the two builds differenced.  Empirical; it knows only what the
        solver did.
      * ANALYTIC — ``building_feasibility.reach_band_unified``:
        ``ceiling − floor`` from the cap-Dijkstra over the unified grade
        graph.  Derived from anchors, caps and geometry alone; it knows
        only what the law grants.

    ``constant_dem``'s own module docstring has stated the comparison as
    the design since the module was written ("one whose width disagrees
    with the analytic band is a law/solver disagreement with an exact
    address") and nothing implemented it.  This is that function.

    IT IS A REPORT, NOT A GATE.  A disagreement is an ADDRESS to go read,
    not a verdict about who is wrong: the measured width can fall short of
    the analytic one for lawful reasons (a node pinned by a within-shape
    rule the route band does not carry), and the analytic band can be
    ``None`` or half-open where the reader has no coverage.  Those cases
    are COUNTED SEPARATELY and never folded into the disagreement count —
    a catch-all bucket labelled with a cause is the defect this sweep
    exists to remove.

    ``field`` is a :func:`band_width_field` result (keys ``(author, x,
    y)``); ``band_of((x, y)) -> (floor, ceiling) | None`` is the analytic
    supplier, the same adapter :func:`saturation_report` takes.  Returns
    counts + the worst ``top`` disagreements, each carrying its AUTHOR and
    coordinate — the exact address.
    """
    rows = []
    n_cmp = n_no_band = n_unbounded = 0
    for (author, x, y), measured in field.items():
        band = band_of((x, y))
        if band is None:
            n_no_band += 1
            continue
        floor, ceil = band
        if floor is None or ceil is None:
            n_unbounded += 1
            continue
        analytic = float(ceil) - float(floor)
        n_cmp += 1
        delta = float(measured) - analytic
        if abs(delta) > materiality_m:
            rows.append({"author": author, "x": x, "y": y,
                         "measured_width_m": round(float(measured), 4),
                         "analytic_width_m": round(analytic, 4),
                         "delta_m": round(delta, 4)})
    rows.sort(key=lambda r: -abs(r["delta_m"]))
    return {
        "materiality_m": float(materiality_m),
        "nodes": len(field),
        "compared": n_cmp,
        "no_analytic_band": n_no_band,
        "analytic_band_half_open": n_unbounded,
        "disagreements": len(rows),
        "max_abs_delta_m": (round(abs(rows[0]["delta_m"]), 4) if rows
                            else 0.0),
        "worst": rows[:top],
    }


def write_band_width_artifact(field: dict, path,
                              extra: Optional[dict] = None,
                              span_m: Optional[float] = None) -> None:
    """Persist the band-width field as JSON beside a build."""
    import json
    from pathlib import Path
    doc = {
        "summary": band_width_summary(field, span_m),
        # ``author`` is part of the identity, not decoration: it is what
        # makes each row a difference of ONE surface against itself.
        "nodes": [{"author": a, "x": x, "y": y,
                   "band_width_m": round(w, 6)}
                  for (a, x, y), w in sorted(field.items())],
    }
    if extra:
        doc.update(extra)
    Path(path).write_text(json.dumps(doc, indent=1))


def constant_dem_worlds(lat: int = 0, lon: int = 0) -> Iterable:
    """``[("plateau", dem), ("canyon", dem)]`` — the pair, in the order the
    oracle reports them (low first: −500 m, then 10 000 m)."""
    return [("plateau", plateau_dem(lat, lon)),
            ("canyon", canyon_dem(lat, lon))]
