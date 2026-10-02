"""THE PLANE PADS AND THEIR DECLARED RISERS — their record types and the
last arrangement's registries (base-profile spec §2 (1)/(3); owner
RULINGS 2026-10-01f, 10-01k Q2/Q3/Q4/Q5; issues #162 / #163).

ONE registry per record, in the ``model`` layer so every consumer may read
it (issue #104, the ``model/hard_plane`` / ``model/pad_terrace`` pattern):
``planar/plane_pads`` MINTS them, ``pipeline/publication`` publishes them,
``constraints/platform`` mints the §2 (1) plane-offset row off them — and
``constraints`` may not import ``planar``
(``tests/auto_patch_v2/test_model.py::test_dependency_direction``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["PlanePad", "BaseStep", "PLANE_PADS", "BASE_STEPS",
           "plane_pads_of_unit", "origin_ref_of", "plane_pad_column"]


@_dc.dataclass(frozen=True)
class PlanePad:
    """One minted plane pad of one unit (§2 (1)).

    ``ref`` is ``model.planar.plane_ref(unit, k)``; ``k`` 0 is the ORIGIN
    PLANE ``p0``, which keeps today's datum law exactly (the unit's
    ``plan_unit_datums`` median / ``hold_interval`` ``D_b`` — airside is
    king).  Every other plane is PINNED to it by one hard row
    ``z_{D_k} - z_{D_0} = dy_m`` (``constraints/platform.plane_offset_rows``).

    ``gradient`` is the SLOPED verdict's own base gradient in the planar
    frame, ``(dz/dx, dz/dy)`` m/m (10-01k Q5: a sloped pad carries the
    object's own grade with no 1.5 % clamp), ``None`` for a flat plane.
    """

    ref: str
    unit: str
    k: int
    #: the authored offset from the origin plane, ``y_k - y_0`` (0 at p0)
    dy_m: float
    #: the plane's own authored height, for the report line
    y_m: float
    area_m2: float
    #: 10-01k Q5 / §2 (2): the carried base gradient of a SLOPED pad
    gradient: "tuple[float, float] | None" = None
    #: the composed base verdict the pad was minted under
    verdict: str = ""

    def to_dict(self) -> dict[str, _t.Any]:
        d = _dc.asdict(self)
        d["gradient"] = None if self.gradient is None else list(self.gradient)
        return d


@_dc.dataclass(frozen=True)
class BaseStep:
    """One DECLARED riser between two plane pads of one unit (§2 (3)).

    ``declared_step_m`` is the OBJECT'S OWN authored height difference —
    never a measured step.  The census prices the EMITTED step against it
    through the ``base_step`` ``terrace_joints`` record
    (``tools/check_grade.BASE_STEP_JOINT_KIND``, ``terrace_actual_step``),
    and the pair itself holds the registered ``base_plane_step`` exemption
    (``check_grade.STEP_EXEMPTIONS``, ruling 10-01f).

    ``line`` is the riser line in frame metres — the LOWER plane's own rim
    facing the upper one, which the strip of ``min_distinct_spacing_m`` is
    centred on; ``strip_m2`` the area that strip took out of the two pads
    (Q2: the riser is the steepest cell the mesh admits, never a 1:3
    bank).
    """

    unit: str
    lower_ref: str
    upper_ref: str
    #: the plane indices of the pair (lower, upper)
    lower_k: int
    upper_k: int
    declared_step_m: float
    strip_m2: float
    strip_width_m: float
    line: tuple[tuple[tuple[float, float], ...], ...] = ()

    def to_dict(self) -> dict[str, _t.Any]:
        return {"unit": self.unit, "lower_ref": self.lower_ref,
                "upper_ref": self.upper_ref, "lower_k": self.lower_k,
                "upper_k": self.upper_k,
                "declared_step_m": round(float(self.declared_step_m), 4),
                "strip_m2": round(float(self.strip_m2), 2),
                "strip_width_m": round(float(self.strip_width_m), 3)}


#: The last arrangement's minted plane pads, ``{ref: PlanePad}`` (the
#: ``model.platform.HELD`` pattern: read back by the publication, the
#: constraints and the census).  Empty where no unit read STEPPED or
#: SLOPED — which is every airport with no stepped building in its pack,
#: and is why nothing in a layout without one can change.
PLANE_PADS: dict[str, PlanePad] = {}

#: The last arrangement's declared risers (§2 (3)).
BASE_STEPS: list[BaseStep] = []


def plane_pads_of_unit(unit: str) -> list[PlanePad]:
    """Every minted plane pad of ``unit``, origin plane first."""
    return sorted((p for p in PLANE_PADS.values() if p.unit == unit),
                  key=lambda p: p.k)


def origin_ref_of(unit: str) -> "str | None":
    """The ORIGIN plane pad's ref of ``unit`` (``p0``, §1 (3)), else
    ``None`` — the one lookup the offset row and the seat both take, so
    neither re-derives "which pad is p0"."""
    for p in PLANE_PADS.values():
        if p.unit == unit and p.k == 0:
            return p.ref
    return None


def plane_pad_column(planar: _t.Any, ref: str) -> "int | None":
    """THE REPRESENTATIVE COLUMN of a plane pad -- one vertex of its own
    faces, the LOWEST id (``model.platform.datum_vertex_of``'s own
    deterministic rule, spelled for a ref that is not in
    :data:`model.platform.HELD`).

    WHY IT EXISTS (owner RULINGS 2026-10-02m (E)).  §2 (1) pins plane
    ``k`` to ``p0`` with ONE hard ``Diff`` between "the two datum
    columns", and PR #196 read both through ``model.platform.
    datum_vertices``, which covers only the blocks whose COLLAR shares a
    vertex with a stage-1 face -- i.e. only pads with WELDED AIRSIDE
    FRONTAGE.  A non-origin plane pad is INTERIOR to its unit by
    construction (``planar/plane_pads`` holds it off the unit's rim so no
    airside vertex can move, 10-02m (C)), so it never has such a collar
    and the lookup returned ``None``: 0 pins minted at HECA,
    ``no_datum_column`` 22, and the two pads then solved to the same
    level -- the 5.00 / 3.66 m declared risers emitted 0.00.

    The pin needs a column, not a FRONTAGE: the plane pad is a pad, so
    the pad law already ties its own vertices into one flat level
    (``constraints/pads.pad_flats``), and fixing ONE of them fixes the
    pad.  Falling back to the pad's own lowest-id vertex is therefore the
    whole fix, and it cannot fail for a pad that has faces at all."""
    vs: set[int] = set()
    for f in getattr(planar, "faces", {}).values():
        if str(getattr(f, "ref", "")) != ref:
            continue
        for ring in (f.ring, *f.holes):
            vs.update(planar.ring_vertices(ring))
    return min(vs) if vs else None
