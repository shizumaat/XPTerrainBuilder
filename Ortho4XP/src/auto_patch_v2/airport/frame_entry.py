"""PACK GEOMETRY ENTERS THE AIRPORT FRAME HERE, AND NOWHERE ELSE
(spec §51; RULINGS 2026-09-18d (2) GEML, and the TNCM capture).

TWO LAWS, NEITHER REPLACING THE OTHER.

**Law A — one entry site** (:func:`enter`).  A polygon authored in a
pack's own local frame becomes AIRPORT-FRAME geometry only by having a
placement affine applied to it.  That act is the defect's single
derivation site: the rotation rounds micron slivers into self-touching
rings, and an invalid ring refuses the first union that reads it.  Four
times in the campaign a consumer was repaired instead (OTHH
``_union_rings``, LGAV ``object_cut.valid_polygon``, GEML
``door_wells._union_below``) and the fifth site was found the same day
(TNCM ``wall_corridors._bands_of``).  :func:`enter` is the ONLY place in
``airport/`` and ``planar/`` that applies a placement affine to a
POLYGON, and what it returns is valid, polygonal and non-degenerate by
construction — so no consumer needs a belt (``tests/auto_patch_v2/
test_v2witnessvalid.py`` G1/G3 hold that shut).

**Law B — one union** (:func:`union`).  Validity at entry is not enough:
TNCM's ``cap_u = unary_union(caps)`` threw ``side location conflict at
-557.635 254.363`` on inputs that were ALL valid (``wall_geometry.
_plan_polys`` filters ``is_valid & area``).  GEOS's exact overlay can
refuse valid input.  So the ``_union_rings`` fallback ladder is promoted
to one function that every union OF PLACED PACK GEOMETRY goes through.

WHY THE SNAP IS PART OF LAW A (§46 (4) (a) applied to the input class it
missed).  The placement rotation runs through libm ``sin``/``cos``; the
last ulp differs by platform.  An un-snapped ring that is a self-touch on
one platform is a micro-crossing on another, and ``make_valid`` of the
two differs in TOPOLOGY, not in the last digit.  After the 1 mm snap all
three platforms hold identical doubles and every later step is
platform-stable by §46 (3).  The arithmetic is EXACTLY ``Frame.entry``'s:
``rint(c / q) * q``, half-even — never ``set_precision(mode=
"pointwise")``, whose rounding is GEOS's own.

REJECTED, MEASURED: ``set_precision(grid, mode="valid_output")`` raises
the same ``unable to assign free hole to a shell`` on the GEML ring (it
cannot repair an invalid input) and costs 3.4x.  Snap-only is not enough
either — the snap itself collapses slivers into self-touches, so the
repair must follow it.

EVERY STEP IS ONE VECTORISED C CALL OVER THE WHOLE ARRAY (owner RULINGS
2026-09-14q: a per-geometry ``.is_valid`` property loop is the
``_rim_index`` 137 s class).  Measured, 100,000 five-vertex parts on one
core: affine + snap 0.09 s, ``is_valid`` 0.04 s, ``area`` 0.01 s —
~0.15 s per 10^5 parts, against 0.48 s for the rejected ``valid_output``.
It REPLACES one Python-level ``affine_transform`` call per geometry, so a
witness-heavy pack gets faster, not slower.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from shapely.errors import GEOSException
from shapely.ops import unary_union

__all__ = ["enter", "union", "transform", "quantum", "IDENTITY",
           "rung_counts", "reset_rung_counts", "rung_note"]

#: The affine of a geometry that is ALREADY in the frame — ``enter`` with
#: this matrix is the repair alone (``obj8._transformed``'s old identity
#: ``_place``).  Same shape as ``obj8.placement_affine``'s return:
#: ``[a, b, d, e, xoff, yoff]``.
IDENTITY: tuple[float, float, float, float, float, float] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

#: The standing sliver floor, used when ``q`` is 0 (a synthetic twin
#: frame).  With a quantum the floor is ``q * q`` — one grid cell — and
#: is DERIVED, not a new law key.
_SLIVER_FLOOR_M2 = 1e-9

#: Rounds of (repair, re-snap) ``enter`` will run before it accepts a
#: valid-but-off-grid result.  Measured: 2 is what real geometry needs.
_MAX_REPAIR_ROUNDS = 4

#: Nesting depth ``get_parts`` is unrolled to.  ``make_valid`` returns at
#: most a GeometryCollection of Multi* parts, so 2 is enough; 4 is the
#: paranoid bound and the loop asserts it terminated.
_MAX_PART_DEPTH = 4

#: Law B's fallback ladder, COUNTED per call site: ``site -> [grid rung,
#: buffer rung]``.  Process-global because the unions are spread over
#: ``airport/`` and ``planar/`` and no single report object is in scope
#: at all of them; :func:`rung_note` renders it for whichever report is.
_RUNGS: dict[str, list[int]] = {}


def quantum(law) -> float:
    """THE ONE READ of ``emit.identity.input_quantum_m`` for this
    package — no module keeps a second copy (§51 (6))."""
    from ..law.tables import input_quantum_m
    return float(input_quantum_m(law))


def _apply(mat: _t.Sequence[float], q: float):
    """The coordinate transformation handed to ``shapely.transform``:
    ONE call for the whole array, affine then snap, in place."""
    a, b, d, e, xoff, yoff = (float(v) for v in mat)

    def tf(c: np.ndarray) -> np.ndarray:
        x = c[:, 0]
        y = c[:, 1]
        out = np.empty_like(c)
        out[:, 0] = a * x + b * y + xoff
        out[:, 1] = d * x + e * y + yoff
        if q > 0.0:
            # §46 (4) (a) / Frame.entry: rint is round-half-even, the same
            # arithmetic python's round() performs there.
            np.divide(out, q, out=out)
            np.rint(out, out=out)
            np.multiply(out, q, out=out)
        return out

    return tf


def transform(geom, mat: _t.Sequence[float], q: float = 0.0):
    """Steps (a) and (b) ALONE — the placement affine, and the snap when
    ``q`` > 0 — for placed geometry that carries no validity: LINES and
    POINTS (§51 (4) row 19, out of scope for the repair).

    It exists so those sites do not spell the affine a second time
    (§46's objection to a duplicate snap beside the frame's).  Accepts a
    single geometry or an array; ``None`` passes through.  Called with
    ``q = 0`` it is bit-for-bit what ``affinity.affine_transform`` did.
    """
    if geom is None:
        return None
    return shapely.transform(geom, _apply(mat, q))


def _snap(q: float):
    """The snap ALONE — ``rint(c / q) * q``, §46 (4) (a)'s arithmetic."""

    def tf(c: np.ndarray) -> np.ndarray:
        out = c / q
        np.rint(out, out=out)
        return out * q

    return tf


def enter(geoms: _t.Sequence, mat: _t.Sequence[float], q: float) -> np.ndarray:
    """LAW A.  ``geoms`` (any sequence, ``None`` entries allowed) placed
    into the airport frame by ``mat`` and repaired, as an object array of
    the SAME LENGTH: each entry a valid polygonal geometry, or ``None``.

    In order, each step one C call over the whole array: (a) the affine;
    (b) the snap to ``q`` (skipped, and only this, when ``q`` is 0);
    (c) ``make_valid`` on the invalid subset; (d) polygonal parts only —
    ``make_valid`` of a self-touching sliver also yields LINES, which a
    caller's ``buffer`` would inflate into area; (e) parts at or under
    one grid cell (``q * q``, or 1e-9 with no quantum) dropped.

    A footprint that repairs to nothing IS nothing: its entry is
    ``None``, and every caller NAMES the drop rather than swallowing it.
    """
    arr = np.empty(len(geoms), dtype=object)
    arr[:] = list(geoms)
    out = np.full(arr.shape[0], None, dtype=object)
    live = np.nonzero(~shapely.is_missing(arr))[0]
    if live.size:
        live = live[~shapely.is_empty(arr[live])]
    if not live.size:
        return out

    g = np.asarray(transform(arr[live], mat, q), dtype=object)

    # (c) THE REPAIR, AND THE SNAP HELD ACROSS IT.  ``make_valid`` of a
    # self-touching ring MINTS the crossing node, which is not on the
    # grid — so the repaired subset is re-snapped, and a snap that
    # re-invalidates is repaired again.  Two rounds is what the measured
    # geometry needs; the cap makes the loop total.  Without this G3
    # (idempotence) is false, and a second pass changing anything is
    # exactly the reason a consumer would grow a belt.
    for _ in range(_MAX_REPAIR_ROUNDS):
        bad = ~shapely.is_valid(g)
        if not bad.any():
            break
        fixed = np.asarray(shapely.make_valid(g[bad]), dtype=object)
        if q > 0.0:
            fixed = np.asarray(shapely.transform(fixed, _snap(q)), dtype=object)
        g[bad] = fixed
    else:
        bad = ~shapely.is_valid(g)
        if bad.any():                     # off-grid, but VALID is the law here
            g[bad] = shapely.make_valid(g[bad])

    parts = g
    src = np.arange(g.shape[0])
    for _ in range(_MAX_PART_DEPTH):
        if not (shapely.get_type_id(parts) >= 4).any():
            break
        parts, sub = shapely.get_parts(parts, return_index=True)
        src = src[sub]
    floor = q * q if q > 0.0 else _SLIVER_FLOOR_M2
    keep = (shapely.get_type_id(parts) == 3) & (shapely.area(parts) > floor)
    parts = parts[keep]
    src = src[keep]
    if not parts.size:
        return out

    res = np.full(g.shape[0], None, dtype=object)
    shapely.multipolygons(parts, indices=src, out=res)
    filled = np.nonzero(~shapely.is_missing(res))[0]
    if filled.size:
        # a one-part result comes back as the POLYGON, so the types every
        # consumer already handles do not change under it
        one = filled[shapely.get_num_geometries(res[filled]) == 1]
        if one.size:
            res[one] = shapely.get_geometry(res[one], 0)
    out[live] = res
    return out


def union(parts, site: str | None = None):
    """LAW B.  ``unary_union`` of PLACED PACK GEOMETRY that cannot abort a
    tile: the exact overlay, then on ``GEOSException`` a fixed-precision
    ``union_all(grid_size=1e-6)``, then a union of ``buffer(1e-6)``
    members.  A rung below the first is counted against ``site``.

    GRID-FIRST IS NOT THE STANDARD: a fixed-precision overlay moves every
    intersection node of every union (goldens at five airports) and costs
    2–5x, to cure a throw measured twice in ~10^5 unions.  The fallback is
    platform-stable anyway — identical doubles in, identical exception out
    (§46 (3)).  1e-6 is the value both standing ladders were measured at;
    on 1 mm-aligned inputs it moves only NEW intersection nodes, by
    <= 0.7 um.
    """
    try:
        return unary_union(parts)
    except GEOSException:
        _count(site, 0)
        if _DUMP_DIR:
            _dump(site, parts)
        try:
            return shapely.union_all(list(parts), grid_size=1e-6)
        except GEOSException:
            _count(site, 1)
            arr = np.empty(len(parts), dtype=object)
            arr[:] = list(parts)
            return unary_union(shapely.buffer(arr, 1e-6).tolist())


#: THE OFFENDER DUMP.  ``O4_FRAME_ENTRY_DUMP=<dir>`` writes the operand
#: list of the FIRST union at each site that fell below the exact rung,
#: as a WKB collection — the only way to get a real refusing input out of
#: a 15-minute capture and into a headless twin (§51 (5) T2).  One
#: ``os.environ`` read at import; nothing on the hot path.
_DUMP_DIR = __import__("os").environ.get("O4_FRAME_ENTRY_DUMP") or ""
_DUMPED: set[str] = set()


def _dump(site: str | None, parts) -> None:
    import os
    name = (site or "unnamed").replace("/", "_")
    if name in _DUMPED:
        return
    _DUMPED.add(name)
    try:
        os.makedirs(_DUMP_DIR, exist_ok=True)
        arr = np.empty(len(parts), dtype=object)
        arr[:] = list(parts)
        with open(os.path.join(_DUMP_DIR, f"{name}.wkb"), "wb") as fh:
            fh.write(shapely.to_wkb(shapely.geometrycollections(arr)))
    except Exception as exc:                      # an instrument never fails a build
        print(f"  [frame-entry] offender dump for {name} failed: {exc}")


def _count(site: str | None, rung: int) -> None:
    row = _RUNGS.setdefault(site or "?", [0, 0])
    row[rung] += 1


def rung_counts() -> dict[str, tuple[int, int]]:
    """``site -> (grid-rung unions, buffer-rung unions)`` since the last
    reset.  Zero is the expected reading; a non-zero one names the site
    that would have aborted the tile before §51."""
    return {k: (v[0], v[1]) for k, v in sorted(_RUNGS.items())}


def reset_rung_counts() -> None:
    _RUNGS.clear()


def rung_note() -> str:
    """One report line, or ``""`` when every union took the exact rung."""
    got = [(s, a, b) for s, (a, b) in rung_counts().items() if a or b]
    if not got:
        return ""
    return ("§51 (3) union fallback rungs: "
            + "; ".join(f"{s} grid {a} buffer {b}" for s, a, b in got))
