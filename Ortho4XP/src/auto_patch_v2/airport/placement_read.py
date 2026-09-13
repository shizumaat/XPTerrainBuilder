"""READING A PLAN THIS TREE DID NOT WRITE, and the graded document's
own rings (spec ``object-placement-spec.md`` §4 / §6).

Two readers ``placement_plan`` owns the meaning of and does not have
room for (the 1,000-line law; moved out whole by lane
``v2bridgecontact``, no line changed): the re-seat plan with its
ABUTMENT pairs, and the emitted design surface's object PADS and
structure RIMS.  ``placement_plan`` re-exports both names, so every
caller and every twin reads them where they always were.

NO LAW CONSTANT LIVES HERE.
"""
from __future__ import annotations

import json
import typing as _t

from ..model.rebake import RebakePlan
from . import anchor_rule as _ar

__all__ = ["read_plan", "pads_rims_from_graded", "pads_rims_from_graded_doc",
           "PAD_FACE_ROLE", "RIM_BREAKLINE_KIND"]


def read_plan(path: str) -> tuple[RebakePlan, tuple[tuple[int, int], ...]]:
    """The re-seat plan plus its ABUTMENT pairs (10ay).

    ``RebakePlan.from_dict`` is the ONE reader — a second one is the
    census-wrapper defect at one remove — but a plan written by a tree
    carrying a LATER additive version (8 added ``abutments`` to 7's
    fields, exactly as 7 added ``Part.line`` to 6's) is refused by its
    version check alone.  So the abutments are lifted out here and the
    version is presented as this tree's, which is what "additive" means;
    anything that is NOT purely additive still fails, because the fields
    the reader needs would not be there."""
    d = json.loads(open(path, encoding="utf-8").read())
    abut = tuple((int(a), int(b)) for a, b in d.get("abutments", ()))
    from ..model.rebake import PLAN_VERSION
    if int(d.get("version", 0)) > PLAN_VERSION:
        d = dict(d, version=PLAN_VERSION)
    return RebakePlan.from_dict(d), abut


#: The graded roles §6's class rule reads: the emitted object PADS and the
#: emitted structure RIMS.  One derivation, two callers — the shipped
#: engine path (``auto_patch/engine_v2._place_objects``) and the dry run
#: (``tools/obj8_split_report.surface_from_graded``).  A second copy is the
#: census-wrapper defect: the engine ran for weeks with ``pads=()`` and
#: ``rims=()`` — nothing shipped could ever classify ``building`` or
#: ``basin`` — while the tool, deriving them, classified both.
PAD_FACE_ROLE = "building"
RIM_BREAKLINE_KIND = "structure_rim"


def pads_rims_from_graded_doc(d: _t.Mapping[str, _t.Any]
                              ) -> tuple[tuple[_ar.PadRing, ...],
                                         tuple[_ar.RimRing, ...]]:
    """``(pads, rims)`` from a parsed ``<ICAO>.graded.json`` document: the
    ``building`` faces' rings and the ``structure_rim`` breaklines, each
    as its ``(lat, lon)`` ring.  A ring shorter than 3 kept vertices is
    not a ring and is dropped (the same floor both callers used)."""
    by_id = {v[0]: (v[1], v[2]) for v in d["vertices"]}
    # §14a: the ring carries its HEIGHTS (§24 (1) makes them the apron's)
    z_id = {v[0]: v[3] for v in d["vertices"]}
    pads = tuple(_ar.PadRing(f["ref"],
                             tuple(by_id[i] for i in f["ring"] if i in by_id))
                 for f in d["faces"]
                 if f["role"] == PAD_FACE_ROLE and len(f["ring"]) >= 3)
    rims = tuple(_ar.RimRing(b["ref"],
                             tuple(by_id[i] for i in b["vertices"] if i in by_id),
                             tuple(float(z_id[i]) for i in b["vertices"]
                                   if i in by_id))
                 for b in d["breaklines"]
                 if b["kind"] == RIM_BREAKLINE_KIND and len(b["vertices"]) >= 3)
    return pads, rims


def pads_rims_from_graded(path: str) -> tuple[tuple[_ar.PadRing, ...],
                                              tuple[_ar.RimRing, ...]]:
    """:func:`pads_rims_from_graded_doc` of the file at ``path``."""
    with open(path, encoding="utf-8") as fh:
        return pads_rims_from_graded_doc(json.loads(fh.read()))


