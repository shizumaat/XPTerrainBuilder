"""THE SCATTER CLASS — the PREDICATE only (spec
``pack-read-once-fast-spec.md`` §B.2 (2), slice S5a).

A SCATTER resource is one ``.obj`` holding tens of thousands of
disconnected little solids: a hillside of bushes, a tree's leaf clumps,
a car park of parked vehicles, a crowd of standing people.  TNCM's
``HillBush.obj`` is 41,220 of them over 945 m; TFFG's
``Tree1Foliage.obj`` is 139,451 leaf clumps, median plan size 0.44 m,
88.6 % of that airport's placed components.  Every downstream law that
reads a solid — the ε-contact partition, the groups, the LP foot rows,
the cluster pads, every structure reader — pays for each of those
pieces, and none of them can lawfully be admitted by any of those laws
(the smallest admitted structure element on the corpus is a sill plate
18–22 m wide, 17k).

**THIS MODULE CHANGES NOTHING.**  Slice S5a lands the predicate and the
dry census (`tools/pack_scatter_census.py`) and NOTHING in the build
consults it: the wiring is slice S5b, after the owner answers §D's Q1
(may scatter shape the terrain?) and Q2 (what is a piece's seat?).

THE THRESHOLDS ARE LAW VALUES, in ONE table — ``structures.toml``
``[scatter]`` (:class:`auto_patch_v2.law.rebake_schema.Scatter`):

===========================  ====================================
``components_min``           the many-small-components count (64)
``component_diag_max_m``     the per-component plan size (10.0 m)
===========================  ====================================

No number appears in this file.

THE PREDICATE, per RESOURCE, pure, frame-independent (§B.2 (2)) — a
resource is SCATTER when ALL of:

 * it has at least ``components_min`` GENUINE components (the
   thickness-gated ones: ``ResourceCache.genuine``);
 * EVERY genuine component's authored plan-box diagonal is at most
   ``component_diag_max_m``, **or** that component is LINE-SHAPED
   (10bb's reading, imported from :mod:`~auto_patch_v2.airport.line_object`
   and never restated here), so a fence file of posts and wire runs is
   one class with its posts;
 * no triangle is ``HARD`` / ``HARD_DECK``;
 * it is not already a LINE OBJECT (that class keeps its drape).

The PLACEMENT-level exemptions of 14.1 rule 4 — deck family, plate
seat, structure seat, basin member — are a SCREEN fact and belong to
the caller, exactly as they do for the line class
(:func:`line_object.is_line_object`'s own note; applied in
``pack_partition._build_member`` and ``PackPartition.filtered``).

The earliest point the verdict is knowable is ``solid_components`` —
after the parse, which is 2.5 % of the pack stage.  It is a pure
function of the file, so it lives beside the other per-resource
readings and can be carried by the partition cache / the per-pack
store.

FALSE POSITIVES ARE EXPECTED AND NAMED (§B.2 (3)): the box-attachment
discriminator was measured and REFUTED (spec row 13).  LEMD's
``Terminal4_yellow-LEMD11`` is 11,537 T4 roof struts, every one
8.69–8.70 m, and it reads SCATTER.  The class's consequences are
chosen in S5b so that such a member renders where it renders today
(§16g keeps whatever covers a building's footprint with the building);
nothing here decides that.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from . import line_object as _line
from . import obj8 as _obj8

__all__ = ["ScatterReading", "ScatterLaw", "component_diag_m", "read", "is_scatter"]


@_dc.dataclass(frozen=True)
class ScatterLaw:
    """The two numbers :func:`read` needs, for a caller holding no law
    tables (a twin, the census tool).  ``structures.toml``'s own
    ``[scatter]`` table carries the same two attributes and serves
    directly — the :class:`LineLaw` precedent."""

    components_min: int
    component_diag_max_m: float


@_dc.dataclass(frozen=True)
class ScatterReading:
    """One resource's verdict AND the numbers it was read from — the
    census reports these, and a refusal names which clause refused."""

    #: the verdict
    scatter: bool
    #: the clause that decided it ("" when :attr:`scatter` is true)
    reason: str
    #: genuine (thickness-gated) components
    components: int
    #: ...of those, how many are within ``component_diag_max_m``
    components_small: int
    #: ...and how many of the rest are LINE-SHAPED (10bb)
    components_line: int
    #: the largest genuine component's authored plan-box diagonal
    max_diag_m: float
    #: the largest plan-box diagonal among components that are NEITHER
    #: small NOR line-shaped — 0.0 when there is none.  This is the
    #: number a near-threshold review reads.
    max_oversize_diag_m: float
    #: ``HARD`` / ``HARD_DECK`` triangles in the resource
    hard_triangles: int
    #: the resource is already a LINE OBJECT (10bb) — it keeps its drape
    line_object: bool


def component_diag_m(geom: _obj8.ObjGeometry, comp: _obj8.Component) -> float:
    """One component's AUTHORED PLAN-BOX DIAGONAL (metres): the x and z
    extents of its own vertices, never the whole file's."""
    pts = geom.vertices[comp.tris.reshape(-1)]
    if pts.shape[0] == 0:
        return 0.0
    return math.hypot(float(pts[:, 0].max() - pts[:, 0].min()),
                      float(pts[:, 2].max() - pts[:, 2].min()))


def _laws(law: _t.Any) -> tuple[_t.Any, _t.Any]:
    """``(scatter law, rebake law)`` from either a bound
    :class:`~auto_patch_v2.law.model.Law` or the two tables handed in
    directly (a twin)."""
    tables = getattr(law, "tables", None)
    if tables is not None:
        return tables.structures.scatter, tables.structures.rebake
    return law, getattr(law, "rebake", law)


def read(cache: _obj8.ResourceCache, resolved: str, law: _t.Any) -> ScatterReading:
    """THE RESOURCE's reading (module doc): the verdict plus every
    number it was taken from.  ``law`` is the bound law, or a
    :class:`ScatterLaw` carrying ``rebake`` for the line clause.

    ``components_min <= 0`` disables the class (the pre-S5b reading);
    the reading still reports the numbers."""
    sc, rb = _laws(law)
    geom = cache.geometry(resolved)
    comps = cache.genuine(resolved) if geom is not None else []
    n = len(comps)
    small = line = 0
    max_diag = 0.0
    max_over = 0.0
    for c in comps:
        d = component_diag_m(geom, c)
        max_diag = max(max_diag, d)
        if d <= sc.component_diag_max_m:
            small += 1
        elif _line.is_line_shaped(geom, c, rb):
            line += 1
        else:
            max_over = max(max_over, d)
    hard = int((geom.hardness != 0).sum()) if geom is not None else 0
    is_line = bool(comps) and _line.is_line_object(cache, resolved, rb)

    def out(ok: bool, reason: str) -> ScatterReading:
        return ScatterReading(ok, reason, n, small, line, max_diag, max_over,
                              hard, is_line)

    if int(sc.components_min) <= 0:
        return out(False, "the scatter class is disabled (components_min = 0)")
    if geom is None:
        return out(False, "unreadable OBJ8")
    if n < int(sc.components_min):
        return out(False, f"{n} genuine components under components_min")
    if hard:
        return out(False, f"{hard} HARD / HARD_DECK triangles")
    if small + line < n:
        return out(False, f"{n - small - line} component(s) over "
                          f"component_diag_max_m and not line-shaped "
                          f"(largest {max_over:.2f} m)")
    if is_line:
        return out(False, "already a LINE OBJECT (10bb): it keeps its drape")
    return out(True, "")


def is_scatter(cache: _obj8.ResourceCache, resolved: str, law: _t.Any) -> bool:
    """:func:`read`'s verdict alone."""
    return read(cache, resolved, law).scatter
