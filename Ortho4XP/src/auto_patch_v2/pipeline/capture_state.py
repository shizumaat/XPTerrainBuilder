"""THE CAPTURE STATE — the REGISTRIES the planar stage fills and a LATER
stage reads, carried WITH a capture so a late stage replay solves the
BUILD's problem and not a different one (issues #208, #224).

WHAT THE DEFECT WAS.  ``tools/v2_solve_replay.py --capture`` pickles the
``Airport``, the ``Classification``, the ``PlanarMap`` and the
``ShapeStage`` — every value the build hands from one stage to the next
*as data*.  Until issue #841 seven of the planar stage's products were not
handed as data at all: they were MODULE GLOBALS that the planar stage
FILLED and the constraint generators READ.  A ``--replay --from
classify|planar`` re-ran ``planar/build.build``, which refilled them, so
it was faithful by accident.  A ``--replay --from shapes|constraints``
was not, so every generator that read one read an EMPTY registry and the
replay assembled a DIFFERENT LP from the build's:

* #208, measured at HECA on one capture and one tree: §5a relaxed **822**
  rows from ``--from constraints`` against **108** from ``--from
  planar``.  At CYXY/KASE the same capture's emit lost the ``strips 0,
  strips_disarmed_held 2`` reading — ``constraints/jetway_strip.py``
  disarms the strip on a HELD block, and with the held registry empty no
  block is held, so the replay ARMED two strips the build never armed.
* #224, measured at KCLT against ``sw1005_KCLT``: **65,212** rows from
  ``--from shapes|constraints`` against the build's **49,981** (columns
  8,934 vs 8,876) on an IDENTICAL vertex set of 22,263 — the difference
  is in the rows, not the map, which is exactly this class.

THE RECORD (stage-cache spec §10 steps 1-2, issues #840 / #841).  The
registries are ONE typed record, ``model.registries.Registries``: the
arrangement builds it, the map carries it (``PlanarMap.registries``) and
every reader takes it off the map it is handed — no module global is left.
This module is the record's STAGE-BOUNDARY form: :func:`collect` snapshots
a map's record as ``{"version", "fields"}`` (what ``--capture`` and the
``--solved-out`` dump pickle), :func:`install` writes such a snapshot back
into a map's record, and a capture that does not carry a field the
current tree declares REFUSES the late resume BY FIELD NAME
(:func:`missing`, :func:`refusal`) instead of solving a different problem.
It lives in ``pipeline/`` because ``pipeline`` owns the stage order; a
second copy of the field list in each tool is the census-wrapper defect
(RULINGS ``7e90032``).

THE CONSUMER CENSUS (owner ruling, RULINGS ``2026-08-30l`` — every pass
that reads the affected state, ruled in ONE table):

===================================  =============================  ==========================================================
registry                             written by (stage)             read by                             verdict
===================================  =============================  ==========================================================
``registries.held``                  ``planar/platform``,           ``constraints/{platform,no_step,     CARRIED
                                     ``planar/pad_cut``             jetway_strip}``, ``model/platform``
                                                                    (``datum_vertices``: the solve
                                                                    stage split and the hold rows)
``registries.plateaus``              ``planar/pad_cut``             ``constraints/platform``             CARRIED
``registries.landings``              ``planar/landing``             ``constraints/{platform,pads}``,     CARRIED
                                                                    ``pipeline/publication``
``registries.landing_runouts``       ``planar/landing_runout``      ``constraints/{ramp_runout,          CARRIED
                                                                    platform}``
``registries.platforms``             ``planar/platform``            ``constraints/platform``,            CARRIED
                                                                    ``pipeline/publication``
``registries.terraces``              ``planar/pad_terrace``         ``constraints/pad_fronting``,        CARRIED
                                                                    ``planar/build`` (``pad_terraces``)
``registries.pad_airside``           ``planar/overlay``,            ``pipeline/publication``             CARRIED (was
                                     ``planar/ribbons``                                                 carried alone,
                                                                                                        RULINGS
                                                                                                        2026-09-16b)
``planar.pad_blocks.BLOCK_PLANS``    ``planar/platform``            ``tools/v2_solve_replay.pad_read``   NOT CARRIED: its one
                                                                                                        reader REFUSES on a
                                                                                                        late resume already
                                                                                                        (``--pad-read`` needs
                                                                                                        ``--from classify|
                                                                                                        planar``)
``classify.evidence.CLUSTER_PADS``   ``classify/evidence``          ``tools/v2_solve_replay``            NOT CARRIED: printed
                                                                    (``--from classify``),               by the arm that just
                                                                    ``tools/pad_airside_arm``            re-ran classify
``planar.platform.MERGE_READ``       ``planar/platform``            ``planar/overlay``                   NOT CARRIED: written
                                                                                                        and read INSIDE the
                                                                                                        planar stage
``planar.cluster.WHY``,              their own module               their own module                     NOT CARRIED:
``planar.structure_deck.``                                                                              diagnostics, same
``LAST_DECK_WITNESS``,                                                                                   stage
``constraints/*.STATS``
``airport.anchor_rule._PAD_BOXES``,  on demand                      on demand                            NOT CARRIED: MEMOS
``constraints/*._CACHE``,                                                                               keyed on their input
``_MEMO``, ``routes._CACHE``, ...                                                                        — they recompute
``solve.feasibility.``               after the registries           ``pipeline/publication``             NOT CARRIED: produced
``HARD_CONFLICT``,                                                                                      BY the replay's own
``constraints.cluster_pad.``                                                                            solve, not before it
``{YIELDED,REFERENCE,DERIVED,
OFFSET_SPREAD,TOUCHING_STEPS}``,
``constraints.no_step.RUNWAY_FLEX``
===================================  =============================  ==========================================================

Twins: ``tests/test_v2_capture_state.py``,
``tests/auto_patch_v2/test_stage_registries.py``.  Offline and synthetic —
no corpus, no network.
"""
from __future__ import annotations

import copy
import dataclasses as _dc
import typing as _t
from collections.abc import Mapping as _Mapping

from ..model.registries import FIELDS as _FIELDS, Registries

__all__ = ["CAPTURE_STATE_KEY", "CAPTURE_STATE_VERSION", "Registry", "planar_stage",
           "REGISTRIES", "collect", "install", "missing", "unknown",
           "refusal", "clear", "line"]

#: The key the state is RECORDED under, in the ``--capture`` pickle and in
#: the ``--solved-out`` pickle (the tool writes no second spelling).
CAPTURE_STATE_KEY = "capture_state"

#: The record's version.  Bumped when a FIELD's meaning changes (a field
#: ADDED or REMOVED needs no bump: :func:`missing` / :func:`unknown` read
#: the field set itself, which is the honest comparison).  A capture from
#: a LATER version refuses, because this tree cannot know what its fields
#: mean.  The fields kept their names and contents when the module globals
#: became ``model.registries.Registries`` (#841), so the version stands.
CAPTURE_STATE_VERSION = 1


@_dc.dataclass(frozen=True)
class Registry:
    """One field of the capture state: which stage fills it and which
    passes read it (the refusal quotes both, so a lane reading the message
    knows what the replay would have got wrong)."""

    field: str
    filled_by: str
    read_by: tuple[str, ...]


#: THE DECLARED CAPTURE STATE — the ``CARRIED`` rows of the module's
#: census table, in the order the planar stage fills them (the
#: ``Registries`` field order).
REGISTRIES: tuple[Registry, ...] = (
    Registry("held",
             "planar/platform.py + planar/pad_cut.py (the planar stage)",
             ("constraints/platform.py (the hold rows, the block datum Band)",
              "constraints/no_step.py (the plateau vertices, the pair graph)",
              "constraints/jetway_strip.py (the strip is DISARMED on a held block)",
              "model/platform.py (datum_vertices: the solve's stage split, the hold rows)")),
    Registry("plateaus",
             "planar/pad_cut.py (the planar stage)",
             ("constraints/platform.py (the stand-line plateau)",)),
    Registry("landings",
             "planar/landing.py via planar/platform.py (the planar stage)",
             ("constraints/platform.py (the landing level rows, RULINGS 2026-10-03e)",
              "constraints/pads.py (the DEM-datum withdrawal)",
              "pipeline/publication.py (the sidecar's landings; found by "
              "the #840 census)")),
    Registry("landing_runouts",
             "planar/landing_runout.py via planar/landing.py (the planar stage)",
             ("constraints/ramp_runout.py (the run-out's level rows, #711)",
              "constraints/platform.py (the collar banks the run-out's sides)",
              "planar/landing.py (landing_cut: the lot cut, the strip's region)")),
    Registry("platforms",
             "planar/platform.py (the planar stage)",
             ("constraints/platform.py (the refused platforms)",
              "pipeline/publication.py (the sidecar's platform_why)")),
    Registry("terraces",
             "planar/pad_terrace.py (the planar stage)",
             ("constraints/pad_fronting.py (the declared terrace's bound)",
              "planar/build.py (PlanarMap.pad_terraces, terrace_joints_ll)")),
    Registry("pad_airside",
             "planar/overlay.py + planar/ribbons.py (the arrangement, the planar stage)",
             ("pipeline/publication.py (the sidecar's pad_airside_renode)",)),
)

_BY_FIELD = {r.field: r for r in REGISTRIES}
assert tuple(_BY_FIELD) == _FIELDS, "capture_state.REGISTRIES != model.registries.FIELDS"


def _snapshot(obj: _t.Any) -> _t.Any:
    """A DEEP copy: the constraint generators MUTATE what they read
    (``constraints/platform.py`` writes ``held[ref]["near_miss_contacts"]``),
    so a shallow snapshot would let one replay arm edit the next arm's
    state through the capture."""
    return copy.deepcopy(obj)


def _restore(live: _t.Any, value: _t.Any) -> None:
    """``value`` into the record's container ``live`` IN PLACE (every
    ``dataclasses.replace`` of a map shares its record, so the container
    itself is the shared one)."""
    value = _snapshot(value)
    live.clear()
    if isinstance(live, dict):
        live.update(value)
    elif isinstance(live, list):
        live.extend(value)
    else:                                  # pragma: no cover - declared types
        raise TypeError(f"capture state: {type(live).__name__} is not a "
                        f"registry this record knows how to restore")


def collect(reg: Registries) -> dict[str, _t.Any]:
    """THE STATE AT THIS STAGE BOUNDARY: ``{"version", "fields"}`` — a deep
    snapshot of ``reg`` (a map's ``registries``).

    Called by ``--capture`` AFTER the shape stage and by the replay's
    ``--solved-out`` dump — in both cases BEFORE any constraint generator
    has mutated the record, which is what makes it the build's own state
    entering ``shape_constraints``."""
    fields = {f: _snapshot(getattr(reg, f)) for f in _FIELDS}
    return {"version": CAPTURE_STATE_VERSION, "fields": fields}


def planar_stage(airport: _t.Any, classification: _t.Any, law: _t.Any,
                 **kw: _t.Any) -> tuple[_t.Any, _t.Any, dict[str, _t.Any]]:
    """THE PLANAR STAGE WITH ITS RECORD: ``(pm, pstats, state)`` (stage-cache
    spec §10 step 1, issue #840).  ``planar/build.build`` (``kw`` passed
    through) fills ``pm.registries``; ``state`` is :func:`collect` of it at
    its return — the stage's output as DATA, which the build then
    :func:`install` s into the map explicitly before the shape stage, so a
    stage served from a record and a stage run here enter the shape stage
    with the same registries by construction."""
    from ..planar.build import build as _build_planar
    pm, pstats = _build_planar(airport, classification, law, **kw)
    return pm, pstats, collect(pm.registries)


def _fields(state: _t.Mapping[str, _t.Any] | None) -> dict[str, _t.Any]:
    if not state:
        return {}
    got = state.get("fields")
    return dict(got) if isinstance(got, _Mapping) else {}


def version_of(state: _t.Mapping[str, _t.Any] | None) -> int | None:
    """The record's version, or ``None`` for a pickle carrying none."""
    if not state:
        return None
    v = state.get("version")
    return int(v) if isinstance(v, int) else None


def missing(state: _t.Mapping[str, _t.Any] | None) -> tuple[str, ...]:
    """The declared fields this record does NOT carry — every field when
    the record is absent."""
    got = _fields(state)
    return tuple(r.field for r in REGISTRIES if r.field not in got)


def unknown(state: _t.Mapping[str, _t.Any] | None) -> tuple[str, ...]:
    """The record's fields this tree does not declare — a capture from a
    tree that carried a registry since removed.  Reported, never fatal:
    no pass reads them."""
    return tuple(sorted(f for f in _fields(state) if f not in _BY_FIELD))


def install(reg: Registries, state: _t.Mapping[str, _t.Any] | None) -> tuple[str, ...]:
    """Install every field of ``state`` into ``reg`` (a map's
    ``registries``) and return the field names installed, in declaration
    order.

    Refuses a record from a LATER :data:`CAPTURE_STATE_VERSION` (this tree
    cannot know what its fields mean).  Does NOT refuse a record missing a
    field — that is :func:`missing`'s verdict, which the caller asks for
    where the stage needs it, so a resume that re-derives the registries
    itself (``--from classify|planar``) is not refused for a record it
    does not need."""
    v = version_of(state)
    if v is not None and v > CAPTURE_STATE_VERSION:
        raise ValueError(
            f"capture state version {v} is NEWER than this tree's "
            f"{CAPTURE_STATE_VERSION}: its fields' meaning is unknown here. "
            f"Re-capture with this tree, or replay with the tree that wrote it.")
    got = _fields(state)
    done: list[str] = []
    for r in REGISTRIES:
        if r.field not in got:
            continue
        _restore(getattr(reg, r.field), got[r.field])
        done.append(r.field)
    return tuple(done)


def clear(reg: Registries) -> tuple[str, ...]:
    """Empty every field of ``reg`` — what a map pickled before the record
    existed reads, and the arm the twins measure the defect in."""
    for f in _FIELDS:
        getattr(reg, f).clear()
    return _FIELDS


def refusal(icao: str, stage: str, source: str, gone: _t.Sequence[str],
            recapture: str) -> str:
    """THE REFUSAL, naming every absent field, the stage that fills it and
    the passes that read it (issues #208 / #224) — so the message says
    what the replay would have solved instead, not just that it stopped."""
    lines = [f"[{icao}] REFUSED: --from {stage} off {source} would solve a "
             f"DIFFERENT problem from the build — this record carries no "
             f"{', '.join(gone)}."]
    for f in gone:
        r = _BY_FIELD.get(f)
        if r is None:                      # pragma: no cover - declared set
            continue
        lines.append(f"  {f} (PlanarMap.registries.{f}) is filled by {r.filled_by} "
                     f"and read by: " + "; ".join(r.read_by))
    lines.append("  A registry the capture does not carry is EMPTY in this "
                 "process, and every pass above then reads it empty: issues "
                 "#208 (HECA §5a relaxed 822 rows against 108) and #224 "
                 "(KCLT 65,212 rows against the build's 49,981).  "
                 "--from classify|planar re-derives them and is faithful.")
    lines.append(f"  {recapture}")
    return "\n".join(lines)


def line(icao: str, installed: _t.Sequence[str],
         state: _t.Mapping[str, _t.Any] | None, reg: Registries) -> str:
    """The one loud line a replay prints for the state it installed into
    ``reg``."""
    if not installed:
        return (f"[{icao}] capture state: none installed (the registries are "
                f"the map's own)")
    sizes = [f"{f} {len(getattr(reg, f))}" for f in installed]
    extra = unknown(state)
    return (f"[{icao}] capture state v{version_of(state)} installed: "
            + ", ".join(sizes)
            + (f"; {len(extra)} field(s) this tree does not declare, ignored: "
               + ", ".join(extra) if extra else ""))
