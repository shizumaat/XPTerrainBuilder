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

__all__ = ["Platform", "PLATFORMS", "HELD", "LANDINGS", "LANDING_SEP",
           "is_landing_ref", "PLATEAUS", "plateau_vertices",
           "HOLD_REPORT_KEYS", "hold_report",
           "install_hold_report",
           "datum_vertices", "stage_air_vertices"]


@_dc.dataclass(frozen=True)
class Platform:
    """One unit pad's platform verdict at the arrangement."""

    ref: str
    pad_m2: float
    welded_samples: int
    #: the welded rim's relief at the mint (DEM, against the tilt-bounded
    #: frontage plane) — a report; ``None`` without a DEM
    relief_m: "float | None" = None
    #: ``""`` when minted, else why not (``"draped_facade"``)
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

#: The per-block REPORT ``constraints/no_step.hold_interval`` writes into
#: :data:`HELD` during stage 1 — scalars and lat/lon keys, no vertex id, so
#: the record means the same on every map of one build.  Stage 1 runs on the
#: ribbon-free map under ITS OWN registries (``pipeline/stage_one_map``) and
#: the last stage re-mints :data:`HELD`; :func:`hold_report` /
#: :func:`install_hold_report` carry these keys across both, so the sidecar's
#: ``platforms[]`` (and the frontage warning, spec §56 (3)) read them.
HOLD_REPORT_KEYS = ("reach_band", "reach_band0", "reach_width_m", "reach_gap_m",
                    "reach_gap0_m", "reach_empty", "reach_eval", "reach_unreached",
                    "datum_chosen", "reach_isect", "reach_isect_empty",
                    "reach_lo_binding", "reach_hi_binding",
                    "reach_bands_contacts", "misfit_m", "weld_widened")


def hold_report(held: "_t.Mapping[str, dict] | None" = None) -> dict[str, dict]:
    """``{held ref: its report keys}`` (:data:`HOLD_REPORT_KEYS`) off
    ``held`` (default: the live :data:`HELD`) — a deep copy."""
    import copy
    src = HELD if held is None else held
    out = {r: {k: copy.deepcopy(h[k]) for k in HOLD_REPORT_KEYS if k in h}
           for r, h in src.items()}
    return {r: d for r, d in out.items() if d}


def install_hold_report(report: "_t.Mapping[str, dict]") -> int:
    """``report`` (:func:`hold_report`) into the live :data:`HELD`, by ref;
    a ref the live registry does not hold is skipped.  Returns the refs
    written."""
    import copy
    n = 0
    for r, d in report.items():
        if r in HELD:
            HELD[r].update(copy.deepcopy(dict(d)))
            n += 1
    return n


#: owner RULINGS 2026-10-03e (#290): the last arrangement's RAMP LANDINGS
#: of a unit's viaduct — ``<unit ref>/landing<k>`` (its collar
#: ``.../landing<k>#collar``) -> ``{"block", "y", "deck", "area_m2"}``: a
#: flat groundside pad held in stage 2 at the block's datum + the deck's
#: authored ``y`` there (``constraints/platform.landing_rows``).  Minted by
#: ``planar/landing.landing_regions`` from ``platform_split``.  The
#: spelling is NOT a block's (``model.planar.block_of`` reads ``/b<k>``):
#: a landing is never a block of its unit.
LANDINGS: dict[str, dict[str, _t.Any]] = {}

#: the landing ref's separator (``<unit ref>/landing<k>``)
LANDING_SEP = "/landing"


def is_landing_ref(ref: object) -> bool:
    """Is this face ref a viaduct ramp LANDING (platform or collar)?"""
    from .planar import pad_base_ref
    r = pad_base_ref(ref)
    i = r.rfind(LANDING_SEP)
    return i > 0 and r[i + len(LANDING_SEP):].isdigit()


#: flat-pad spec v2 §3: the last arrangement's PLATEAUS — held block ref ->
#: ``{"source", "area_m2", "apron_refs", "riders", "startups"}`` (minted by
#: ``planar/pad_cut.plateau_cut``; empty without a held block or a stand).
PLATEAUS: dict[str, dict[str, _t.Any]] = {}


def plateau_vertices(planar: _t.Any, law: _t.Any = None) -> dict[str, set[int]]:
    """``{held block ref: every vertex of its PLATEAU apron pieces}`` (spec
    v2 §3: the plateau joins the block's hold set) — read off the face
    refs (``model.planar.PLATEAU_MARK``), ONE accessor."""
    from .planar import plateau_block_of
    out: dict[str, set[int]] = {}
    for f in planar.faces.values():
        b = plateau_block_of(f.ref)
        if b is None:
            continue
        vs = out.setdefault(b, set())
        for ring in (f.ring, *f.holes):
            vs.update(planar.ring_vertices(ring))
    return out


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
    """``{held ref: its datum vertex}`` over :data:`HELD` — THE FRONTAGE
    DATUM COLUMN of a held pad or block (flat-pad spec §1 (2), v2 §4; spec
    §56 (3): ONE rule for every held ref, there is no collar).  Only a pad
    whose face shares a vertex with a stage-1 face (a block with no welded
    frontage has nothing to hold: it keeps the plate's own rows, MEASURED
    on the HECA replay — ``building121`` / ``281`` / ``5`` read frontage at
    the mint through a sliver the arrangement did not weld, and a datum
    column with no hold row sat on one vertex's DEM).

    The column is one of the pad's OWN vertices, never a weld — the one
    FARTHEST from its welded rim (ties: lowest id), so no pad row reaching
    an airside vertex (a ceiling pair over a rim edge) is pulled into stage
    1 through it (measured HECA: a rim datum made two §20 pads' ceilings an
    infeasible stage-1 set) — and never a vertex a STRUCTURE face carries (a
    ramp's top, a trench rim: its level is the structure's own law, and a
    datum column on it seats the whole pad at the structure).  A pad with no
    such vertex of its own has no datum column and is not held.  ONE derivation: the stage split
    (``solve/design_roles.airside_stage_vertices``) and the hold rows read
    the same vertex."""
    if not HELD:
        return {}
    if air is None:
        air = stage_air_vertices(planar, law)
    from ..law.tables import is_structure_role
    own: dict[str, set[int]] = {}
    struct: set[int] = set()
    for f in planar.faces.values():
        r = str(f.ref)
        if r in HELD:
            vs = own.setdefault(r, set())
            for ring in (f.ring, *f.holes):
                vs.update(planar.ring_vertices(ring))
        elif is_structure_role(law, f.role):
            for ring in (f.ring, *f.holes):
                struct.update(planar.ring_vertices(ring))
    out: dict[str, int] = {}
    for ref in sorted(HELD):
        vs = own.get(ref, set())
        weld = vs & set(air)
        inner = sorted(vs - weld - struct)
        if not weld or not inner:
            continue
        wx = [planar.vertices[v].xy for v in weld]

        def _far(v: int) -> tuple[float, int]:
            x, y = planar.vertices[v].xy
            return (-min((x - a) ** 2 + (y - b) ** 2 for a, b in wx), v)
        out[ref] = min(inner, key=_far)
    return out
