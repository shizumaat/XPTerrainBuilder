"""Constraint ROWS (plan §1 row 5, §2) — the only vocabulary between the
law and the solver.

A generator (M2, ``constraints/``) is a pure function ``(planar, law,
inputs) -> rows``; the solver stacks rows.  Every row carries a
:class:`Source` naming the generator, the ruling id it serves and the
input ids it read, so an infeasibility is diagnosed as ``(constraint,
source)`` by the solver itself (plan §2: "who minted the contradiction").
No row ever holds a value the law did not state or an input did not
carry — a backfilled value is the R1.3 class v2 forbids.

All variables are planar-map vertex ids; ``z`` is metres.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Source", "Pin", "Diff", "Flat", "Band", "Offset", "Linear",
           "Row", "ConstraintSet"]


@_dc.dataclass(frozen=True)
class Source:
    """Who minted a row.  ``generator`` is the constraints module function
    (e.g. ``runway_profile``), ``ruling`` the RULINGS id (e.g.
    ``2026-08-27``) or law family key, ``inputs`` the input ids (apt.dat
    row ids, OSM way ids, face ids, breakline ids)."""

    generator: str
    ruling: str
    inputs: tuple[str, ...] = ()


@_dc.dataclass(frozen=True)
class Pin:
    """``z[v] == z`` — a hard value: CIFP threshold (RULINGS :511-516),
    tile-seam DEM pin, declared basin floor, deck top."""

    v: int
    z: float
    source: Source


@_dc.dataclass(frozen=True)
class Diff:
    """``-cap * d <= z[a] - z[b] <= cap * d`` — a grade cap over a
    planar distance ``d`` (metres) between two vertices: longitudinal
    along breaklines, transverse across faces, direct-distance no-step
    pairs (RULINGS 2026-08-27).  ``cap`` is a grade fraction from the
    law tables; a rate law (grade change per metre) is two ``Diff`` rows
    on consecutive chords composed by the generator."""

    a: int
    b: int
    cap: float
    d: float
    source: Source

    @property
    def bound_m(self) -> float:
        """The allowed |Δz|."""
        return self.cap * self.d


@_dc.dataclass(frozen=True)
class Flat:
    """``z[v_i] == z[v_j]`` for all ``v`` in ``group`` — a rigid flat
    surface (building pad, deck plate, wall top: RULINGS 2026-09-01c "one
    corridor-top value")."""

    group: tuple[int, ...]
    source: Source


@_dc.dataclass(frozen=True)
class Band:
    """``lo <= z[v] <= hi`` — adjacent-ground zones 1-2 toward the DEM
    (RULINGS 2026-08-01), tunnel datum floors, materiality windows.
    ``None`` = unbounded on that side."""

    v: int
    lo: float | None
    hi: float | None
    source: Source


@_dc.dataclass(frozen=True)
class Offset:
    """``z[a] - z[b] >= min_delta`` — deck clearance above a ramp
    (``structures.bridge.clearance_m``), the mouth wall above the mouth
    node (``structures.tunnel.bore_datum_m``, RULINGS 2026-09-03b)."""

    a: int
    b: int
    min_delta: float
    source: Source


@_dc.dataclass(frozen=True)
class Linear:
    """``lo <= Σ c_i · z[v_i] <= hi`` — the general linear row (M2
    extension of the M0 vocabulary, additive).  Two laws need more than
    two vertices: a RATE law (second difference along a chain, RULINGS
    2026-08-27 clause 2 / strip_arc / raoa) is a three-term row, and a
    TRANSECT (the transverse law's cross-section, owner 2026-08-21) reads
    two ring-edge INTERPOLATIONS, four terms.  ``terms`` is
    ``((vertex, coefficient), ...)``; ``None`` = unbounded on that side.
    A generator states the row in the law's own units (metres of Δz);
    the assembler stacks it unchanged."""

    terms: tuple[tuple[int, float], ...]
    lo: float | None
    hi: float | None
    source: Source


Row = _t.Union[Pin, Diff, Flat, Band, Offset, Linear]


@_dc.dataclass(frozen=True)
class ConstraintSet:
    """All rows for one solve, by kind, immutable once built.

    ``to_sparse()`` CONTRACT (implemented in M2 by ``solve/assemble``;
    documented here so generators and the solver agree):

    * variables are the planar-map vertex ids ``0..n-1`` in id order;
    * returns ``(A_eq, b_eq, A_ub, b_ub, lo, hi)`` where
      ``A_eq z = b_eq`` holds every ``Pin`` (one row, coefficient 1) and
      every ``Flat`` (``len(group) - 1`` rows ``z[g0] - z[gi] = 0``);
      ``A_ub z <= b_ub`` holds every ``Diff`` as TWO rows
      (``z[a] - z[b] <= cap*d`` and ``z[b] - z[a] <= cap*d``) and every
      ``Offset`` as ONE row (``z[b] - z[a] <= -min_delta``);
      ``lo`` / ``hi`` are the per-variable bounds from ``Band`` rows
      (``-inf`` / ``+inf`` where none; the tightest wins when several);
      every ``Linear`` row lands in ``A_ub`` as one row per finite side
      (``Σ c z <= hi`` and ``-Σ c z <= -lo``);
    * rows keep their order within kind, so row index -> ``Row`` is a
      stable map the solver's IIS uses to name sources;
    * scipy CSR, float64; no dense matrix is ever formed.
    """

    pins: tuple[Pin, ...] = ()
    diffs: tuple[Diff, ...] = ()
    flats: tuple[Flat, ...] = ()
    bands: tuple[Band, ...] = ()
    offsets: tuple[Offset, ...] = ()
    linears: tuple[Linear, ...] = ()

    @classmethod
    def from_rows(cls, rows: _t.Iterable[Row]) -> "ConstraintSet":
        """Rows by kind, order preserved within kind."""
        kinds: dict[type, list] = {Pin: [], Diff: [], Flat: [], Band: [],
                                   Offset: [], Linear: []}
        for r in rows:
            try:
                kinds[type(r)].append(r)
            except KeyError:
                raise TypeError(f"not a constraint row: {r!r}") from None
        return cls(tuple(kinds[Pin]), tuple(kinds[Diff]), tuple(kinds[Flat]),
                   tuple(kinds[Band]), tuple(kinds[Offset]), tuple(kinds[Linear]))

    def counts(self) -> dict[str, int]:
        """Row counts per kind (the build log's one-line summary)."""
        return {"pins": len(self.pins), "diffs": len(self.diffs),
                "flats": len(self.flats), "bands": len(self.bands),
                "offsets": len(self.offsets), "linears": len(self.linears)}

    def rows(self) -> tuple[Row, ...]:
        """Every row, pins first, in the ``to_sparse`` order."""
        return (*self.pins, *self.flats, *self.diffs, *self.offsets,
                *self.linears, *self.bands)

    def vertices(self) -> frozenset[int]:
        """Every vertex any row touches."""
        out: set[int] = set()
        for p in self.pins:
            out.add(p.v)
        for d in self.diffs:
            out.update((d.a, d.b))
        for f in self.flats:
            out.update(f.group)
        for b in self.bands:
            out.add(b.v)
        for o in self.offsets:
            out.update((o.a, o.b))
        for ln in self.linears:
            out.update(v for v, _c in ln.terms)
        return frozenset(out)

    def by_generator(self) -> dict[str, int]:
        """Row counts per generator (the attribution summary)."""
        acc: dict[str, int] = {}
        for r in self.rows():
            acc[r.source.generator] = acc.get(r.source.generator, 0) + 1
        return acc

    def merged(self, other: "ConstraintSet") -> "ConstraintSet":
        """Concatenate two sets (generators compose by union)."""
        return ConstraintSet(
            pins=self.pins + other.pins, diffs=self.diffs + other.diffs,
            flats=self.flats + other.flats, bands=self.bands + other.bands,
            offsets=self.offsets + other.offsets,
            linears=self.linears + other.linears)

    def to_sparse(self) -> _t.Any:
        """See the class docstring.  The implementation is
        ``solve.assemble.to_sparse(cs, n)`` (it needs scipy, which the
        model never imports); this method only names it."""
        raise NotImplementedError(
            "use auto_patch_v2.solve.assemble.to_sparse(constraints, n)")
