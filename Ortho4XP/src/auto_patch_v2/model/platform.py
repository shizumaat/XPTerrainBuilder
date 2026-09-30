"""THE UNIT-PAD PLATFORM VERDICTS — their record type and the last
arrangement's registry (unit-platform spec, owner RULINGS 2026-09-28a).

ONE registry, in the ``model`` layer so every consumer may read it (issue
#104, the reds84 pattern of ``model/hard_plane``): ``planar/platform``
MINTS the verdicts (and re-exports these names), ``pipeline/publication``
publishes them, ``constraints/platform`` reads the refused ones — and
``constraints`` may not import ``planar`` (``tests/auto_patch_v2/
test_model.py::test_dependency_direction``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Platform", "PLATFORMS", "HELD", "held_platform_vertices",
           "datum_vertex_of", "datum_vertices", "stage_air_vertices"]


@_dc.dataclass(frozen=True)
class Platform:
    """One unit pad's platform verdict at the arrangement."""

    ref: str
    collar_m: float
    pad_m2: float
    platform_m2: float
    welded_samples: int
    #: the welded rim's relief at the mint (DEM, against the tilt-bounded
    #: frontage plane) that set C; ``None`` without a DEM
    relief_m: "float | None" = None
    #: ``""`` when minted, else why not (``"eroded_away"``,
    #: ``"under_min_area"``)
    refused: str = ""

    def to_dict(self) -> dict[str, _t.Any]:
        return _dc.asdict(self)


#: The last arrangement's platform verdicts (the ``pad_terrace.TERRACES``
#: pattern: read back by the publication and the census).
PLATFORMS: list[Platform] = []


#: flat-pad spec §1 (2) / §2 (owner RULINGS 2026-09-30f, 30r): the last
#: arrangement's HELD platform refs (one per flat block; a one-block unit
#: keeps its own ref) -> ``{"unit", "k", "blocks", "datum_pred", "verdict"}``
#: — their welded frontage is held at the block's flat datum in stage 1
#: (``constraints/platform.frontage_hold_rows``).  Minted by
#: ``planar/platform.platform_split``; ``[building_pad] frontage_hold``
#: off leaves it empty.
HELD: dict[str, dict[str, _t.Any]] = {}


def held_platform_vertices(planar: _t.Any, ref: str) -> list[int]:
    """Every vertex of the PLATFORM faces of ``ref`` (rings and holes; the
    collar excluded) — sorted."""
    out: set[int] = set()
    for f in planar.faces.values():
        if str(f.ref) != ref:
            continue
        for ring in (f.ring, *f.holes):
            out.update(planar.ring_vertices(ring))
    return sorted(out)


def datum_vertex_of(planar: _t.Any, ref: str) -> "int | None":
    """THE FRONTAGE DATUM COLUMN of a held block (spec §1 (2)): ONE vertex
    of its platform — the lowest id, a deterministic choice — carries the
    block's flat level as a stage-1 unknown; every other platform vertex is
    held to it in stage 2.  ONE derivation: the stage split
    (``solve/design_roles.airside_stage_vertices``) and the hold rows read
    the same vertex."""
    vs = held_platform_vertices(planar, ref)
    return vs[0] if vs else None


def stage_air_vertices(planar: _t.Any, law: _t.Any) -> set[int]:
    """Every vertex of a §20b stage-1 face (``law.tables.
    airside_stage_roles``, rings and holes; a courtyard island excluded,
    ``model.islands``) — the body of ``solve/design_roles.
    airside_stage_vertices`` before the datum columns join it (one
    derivation, read here so the constraints may ask it too)."""
    from ..law.tables import airside_stage_roles
    from .islands import courtyard_faces
    roles = airside_stage_roles(law)
    court = courtyard_faces(planar, law)
    out: set[int] = set()
    for f in planar.faces.values():
        if f.role not in roles or f.id in court:
            continue
        for ring in (f.ring, *f.holes):
            out.update(planar.ring_vertices(ring))
    return out


def datum_vertices(planar: _t.Any, law: _t.Any,
                   air: "_t.AbstractSet[int] | None" = None) -> dict[str, int]:
    """``{held ref: its datum vertex}`` over :data:`HELD` — only the blocks
    whose COLLAR shares a vertex with a stage-1 face (a block with no
    welded frontage has nothing to hold: it keeps the plate's own rows,
    MEASURED on the HECA replay — ``building121`` / ``281`` / ``5`` read
    frontage at the mint through a sliver the arrangement did not weld,
    and a datum column with no hold row sat on one vertex's DEM)."""
    if not HELD:
        return {}
    if air is None:
        air = stage_air_vertices(planar, law)
    col: dict[str, set[int]] = {}
    for f in planar.faces.values():
        r = str(f.ref)
        if r.endswith("#collar") and r[:-len("#collar")] in HELD:
            vs = col.setdefault(r[:-len("#collar")], set())
            for ring in (f.ring, *f.holes):
                vs.update(planar.ring_vertices(ring))
    out: dict[str, int] = {}
    for ref in sorted(HELD):
        if not (col.get(ref, set()) & air):
            continue
        v = datum_vertex_of(planar, ref)
        if v is not None:
            out[ref] = v
    return out
