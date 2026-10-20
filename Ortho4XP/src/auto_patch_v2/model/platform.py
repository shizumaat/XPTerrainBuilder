"""THE UNIT-PAD PLATFORM VERDICTS — their record type and the readers of a
map's held platforms (unit-platform spec, owner RULINGS 2026-09-28a).

In the ``model`` layer so every consumer may read it (issue #104, the
reds84 pattern of ``model/hard_plane``): ``planar/platform`` MINTS the
verdicts into the map's registries (``model.registries``; issue #841
deleted the module globals ``PLATFORMS`` / ``HELD`` / ``LANDINGS`` /
``LANDING_RUNOUTS`` / ``PLATEAUS`` that stood here),
``pipeline/publication`` publishes them, ``constraints/platform`` reads
the refused ones — and ``constraints`` may not import ``planar``
(``tests/auto_patch_v2/test_model.py::test_dependency_direction``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["structure_vertices", "Platform", "LANDING_SEP",
           "is_landing_ref", "plateau_vertices",
           "HOLD_REPORT_KEYS", "hold_report",
           "install_hold_report",
           "datum_vertices", "stage_air_vertices",
           "HOLD_RULING", "HOLD_DATUM_RULING", "FILL_KINDS", "fill_levels"]

#: The head of the FRONTAGE HOLD rows (flat-pad spec §1 (2); RULINGS
#: 2026-09-30f / 30r): a held block's welded contact at the block's datum.
#: Minted by ``constraints/platform`` (which re-exports it); here so the
#: stage split (``solve/design_stage``, spec §61 (11)) may read it too —
#: ``solve`` may not import ``constraints``.
HOLD_RULING = "structures.building_pad frontage_hold"
#: The head of the block DATUM's own row (owner 2026-10-02 round 5, RULINGS
#: 2026-10-02ah (1) restated: "the pad must be seated flat at a level the
#: apron can meet"): a SOFT preference — in no hard register, priced at the
#: law's weight — pulling the free datum column toward the apron's own
#: frontage level (the contacts' pass-1a median).  The welds (contact = D),
#: the pad's flat rows and the apron's caps are the hard set that decides D
#: jointly; a weld is released only when no single D serves the block
HOLD_DATUM_RULING = "structures.building_pad frontage_hold datum"


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


#: flat-pad spec §1 (2) / §2 (owner RULINGS 2026-09-30f, 30r): a map's
#: HELD platform refs (``PlanarMap.registries.held``; one per flat block, a
#: one-block unit keeps its own ref) -> ``{"unit", "k", "blocks",
#: "datum_pred", "verdict"}`` — their welded frontage is held at the
#: block's flat datum in stage 1 (``constraints/platform.
#: frontage_hold_rows``).  Minted by ``planar/platform.platform_split``;
#: ``[building_pad] frontage_hold`` off leaves it empty.
#:
#: The per-block REPORT ``constraints/no_step.hold_interval`` writes into
#: that record during stage 1 — scalars and lat/lon keys, no vertex id, so
#: the record means the same on every map of one build.  Stage 1 runs on the
#: ribbon-free map with ITS OWN registries (``pipeline/stage_one_map``) and
#: the last stage re-mints the held record; :func:`hold_report` /
#: :func:`install_hold_report` carry these keys across both, so the sidecar's
#: ``platforms[]`` (and the frontage warning, spec §56 (3)) read them.
HOLD_REPORT_KEYS = ("reach_band", "reach_band0", "reach_width_m", "reach_gap_m",
                    "reach_gap0_m", "reach_empty", "reach_eval", "reach_unreached",
                    "datum_chosen", "reach_isect", "reach_isect_empty",
                    "reach_lo_binding", "reach_hi_binding",
                    "reach_bands_contacts", "misfit_m", "weld_widened")


def hold_report(held: "_t.Mapping[str, dict]") -> dict[str, dict]:
    """``{held ref: its report keys}`` (:data:`HOLD_REPORT_KEYS`) off
    ``held`` (a map's ``registries.held``) — a deep copy."""
    import copy
    out = {r: {k: copy.deepcopy(h[k]) for k in HOLD_REPORT_KEYS if k in h}
           for r, h in held.items()}
    return {r: d for r, d in out.items() if d}


def install_hold_report(held: "dict[str, dict]",
                        report: "_t.Mapping[str, dict]") -> int:
    """``report`` (:func:`hold_report`) into ``held`` (a map's
    ``registries.held``), by ref; a ref ``held`` does not hold is skipped.
    Returns the refs written."""
    import copy
    n = 0
    for r, d in report.items():
        if r in held:
            held[r].update(copy.deepcopy(dict(d)))
            n += 1
    return n


#: owner RULINGS 2026-10-03e (#290): a map's RAMP LANDINGS of a unit's
#: viaduct (``registries.landings``) — ``<unit ref>/landing<k>`` (its collar
#: ``.../landing<k>#collar``) -> ``{"block", "y", "deck", "area_m2"}``: a
#: flat groundside pad held in stage 2 at the block's datum + the deck's
#: authored ``y`` there (``constraints/platform.landing_rows``).  Minted by
#: ``planar/landing.landing_regions`` from ``platform_split``.  The
#: spelling is NOT a block's (``model.planar.block_of`` reads ``/b<k>``):
#: a landing is never a block of its unit.  Its LANDING RUN-OUTS (issue
#: #711, ``registries.landing_runouts``: ``runout:<landing ref>`` -> the
#: strip) are minted by ``planar/landing_runout`` and held in stage 2 by
#: ``constraints/ramp_runout.landing_runout_rows``.
#:
#: The landing ref's separator (``<unit ref>/landing<k>``).
LANDING_SEP = "/landing"


def is_landing_ref(ref: object) -> bool:
    """Is this face ref a viaduct ramp LANDING (platform or collar)?"""
    from .planar import pad_base_ref
    r = pad_base_ref(ref)
    i = r.rfind(LANDING_SEP)
    return i > 0 and r[i + len(LANDING_SEP):].isdigit()


#: the landing kinds that are PAD FILLS (``planar/pad_fill``, RULINGS
#: 2026-10-19ap / 10-20d): a plate riding a block, a viaduct's ground prints
FILL_KINDS = ("plate", "piers")


def fill_levels(planar: _t.Any, kinds: "_t.Collection[str] | None" = None
                ) -> dict[str, dict[str, _t.Any]]:
    """``{landing ref: {"block", "y", "z_hi", "vertices"}}`` for every
    landing of ``kinds`` (``None``: every landing — a deck's, and the pad
    fills of :data:`FILL_KINDS`) — RULINGS 2026-10-20d R3 (spec
    ``road-edge-drop-spec.md``).  ``z_hi`` is the HIGHEST level the
    solve may hold the fill at, the run-out's own estimate
    (``planar/landing_runout``): the block's predicted datum + its widest
    reach band + the fill's ``y``; ``vertices`` the fill platform's own
    ring vertices (never its collar's)."""
    reg = planar.registries
    out: dict[str, dict[str, _t.Any]] = {}
    for ref, rec in reg.landings.items():
        if kinds is not None and rec.get("kind", "deck") not in kinds:
            continue
        hb = reg.held.get(rec["block"]) or {}
        if hb.get("datum_pred") is None:
            continue
        sr = hb.get("samples_reach")
        reach = max((float(r) for r in (sr if sr is not None else ())), default=0.0)
        out[ref] = {"block": rec["block"], "y": float(rec["y"]),
                    "z_hi": float(hb["datum_pred"]) + reach + float(rec["y"]),
                    "vertices": set()}
    if not out:
        return out
    for f in planar.faces.values():
        rec = out.get(str(f.ref))
        if rec is not None:
            for cyc in (f.ring, *f.holes):
                rec["vertices"].update(planar.ring_vertices(cyc))
    return out


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
    from .planar import plane_origin_ref, platform_ref_of
    roles = airside_stage_roles(law)
    court = courtyard_faces(planar, law)
    out: set[int] = set()
    for f in planar.faces.values():
        if f.role not in roles or f.id in court:
            continue
        r = platform_ref_of(f.ref)
        if plane_origin_ref(r) != r:
            # A LOWER LEVEL (owner RULINGS 2026-10-19ai, ``planar/low_level``)
            # stands a storey under the airside: a stage-2 pad on its own
            # ground, banded to its block's datum (base-profile spec C14) —
            # MEASURED KATL: in stage 1 its own-ground row was a conforming
            # row stage 1 refuses, and bending alone set it 2 m over its ground
            continue
        for ring in (f.ring, *f.holes):
            out.update(planar.ring_vertices(ring))
    return out


def structure_vertices(planar: _t.Any, law: _t.Any) -> set[int]:
    """THE VERTICES A VALUE-CARRYING STRUCTURE FACE CARRIES (``precedence.toml``
    ``structure = true`` AND ``value = true``: a wall-corridor / door /
    tunnel / garage ramp) — ONE derivation.  Such a vertex stands at the
    ramp's own graded level: where the ramp is cut INTO a pad it is no point
    of the pad's plane, and the pad's edge from it to the pad's own rim is
    the WALL — a declared step, never a grade.

    A VOID structure face (``value = false``: the ``retaining_wall`` whose
    exterior ring IS the wall's top rim, a trench) carries no level of its
    own — its rim is flush with the surface it sits in (owner RULINGS
    2026-09-10an) — so a rim vertex on a pad STAYS a point of the pad's
    plane, at the pad's level.  MEASURED at three OTHH ramp portals (lane
    pads65): read by role ``structure`` alone, 28 wall-top rim vertices left
    the flat set and fell up to 1.35 m (four under the ramp's top) while a
    1 % pad ceiling and the pavement caps were stated over the 0.5-1.1 m
    wall chord against the ramp's pin (31 stage-2 hard conflicts).  Until
    spec §56 (3) the collar face between pad and ramp kept those rows out as
    a bank.

    Read by the datum column (:func:`datum_vertices`), the flat set
    (``constraints.platform``), the pad's plate rows
    (``constraints.pads._pad_groups``) and the pavement fallback
    (``constraints.pavement_cap``)."""
    from ..law.tables import is_structure_role, is_value_role
    out: set[int] = set()
    for f in planar.faces.values():
        if is_structure_role(law, f.role) and is_value_role(law, f.role):
            for ring in (f.ring, *f.holes):
                out.update(planar.ring_vertices(ring))
    return out


def datum_vertices(planar: _t.Any, law: _t.Any,
                   air: "_t.AbstractSet[int] | None" = None) -> dict[str, int]:
    """``{held ref: its datum vertex}`` over the map's held platforms
    (``planar.registries.held``) — THE FRONTAGE
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
    infeasible stage-1 set) — and never a vertex a structure RAMP carries
    (:func:`structure_vertices`: its level is the ramp's own law, and a
    datum column on it seats the whole pad at the ramp).  A pad with no
    such vertex of its own has no datum column and is not held.  ONE derivation: the stage split
    (``solve/design_roles.airside_stage_vertices``) and the hold rows read
    the same vertex."""
    held = planar.registries.held
    if not held:
        return {}
    if air is None:
        air = stage_air_vertices(planar, law)
    own: dict[str, set[int]] = {}
    struct = structure_vertices(planar, law)
    for f in planar.faces.values():
        r = str(f.ref)
        if r in held:
            vs = own.setdefault(r, set())
            for ring in (f.ring, *f.holes):
                vs.update(planar.ring_vertices(ring))
    out: dict[str, int] = {}
    for ref in sorted(held):
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
