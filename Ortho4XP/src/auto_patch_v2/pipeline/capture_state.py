"""THE CAPTURE STATE — the MODULE REGISTRIES a stage fills and a LATER
stage reads, carried WITH a capture so a late stage replay solves the
BUILD's problem and not a different one (issues #208, #224).

WHAT THE DEFECT WAS.  ``tools/v2_solve_replay.py --capture`` pickles the
``Airport``, the ``Classification``, the ``PlanarMap`` and the
``ShapeStage`` — every value the build hands from one stage to the next
*as data*.  Four of the build's stage products are not handed as data at
all: they are MODULE GLOBALS that the planar stage FILLS and the
constraint generators READ (the table below).  A ``--replay --from
classify|planar`` re-runs ``planar/build.build``, which refills them, so
it is faithful by accident.  A ``--replay --from shapes|constraints``
does not, so every generator that reads one read an EMPTY registry and
the replay assembled a DIFFERENT LP from the build's:

* #208, measured at HECA on one capture and one tree: §5a relaxed **822**
  rows from ``--from constraints`` against **108** from ``--from
  planar``.  At CYXY/KASE the same capture's emit lost the ``strips 0,
  strips_disarmed_held 2`` reading — ``constraints/jetway_strip.py``
  disarms the strip on a HELD block, and with :data:`HELD` empty no block
  is held, so the replay ARMED two strips the build never armed.
* #224, measured at KCLT against ``sw1005_KCLT``: **65,212** rows from
  ``--from shapes|constraints`` against the build's **49,981** (columns
  8,934 vs 8,876) on an IDENTICAL vertex set of 22,263 — the difference
  is in the rows, not the map, which is exactly this class.

THE SHAPE OF THE FIX (and why it is here rather than in the tool).  ONE
record with EXPLICIT, VERSIONED fields, derived ONCE, beside the stage
products the capture already carries; the tool collects it at the stage
boundary and installs it on resume.  A capture that does not carry a
field the current tree declares REFUSES the late resume BY FIELD NAME
(:func:`missing`, :func:`refusal`) instead of solving a different
problem — the ``2026-09-12u`` groups rule and the ``PAD_AIRSIDE`` rule
applied to the whole class at once.  It lives in ``pipeline/`` because
the registries span ``model/``, ``planar/`` and ``constraints/`` and
``pipeline`` is the layer that already owns the stage order; a second
copy of the list in each tool is the census-wrapper defect (RULINGS
``7e90032``).

THE CONSUMER CENSUS (owner ruling, RULINGS ``2026-08-30l`` — every pass
that reads the affected state, ruled in ONE table).  Module-level
mutable globals of ``auto_patch_v2``, by who writes and who reads:

===================================  =============================  ==========================================================
registry                             written by (stage)             read by                             verdict
===================================  =============================  ==========================================================
``model.platform.HELD``              ``planar/platform``,           ``constraints/{platform,no_step,     CARRIED
                                     ``planar/pad_cut``             jetway_strip}``, ``model/platform``
``model.platform.PLATEAUS``          ``planar/pad_cut``             ``constraints/platform``             CARRIED
``model.platform.LANDINGS``          ``planar/landing``             ``constraints/{platform,pads}``      CARRIED
``model.platform.PLATFORMS``         ``planar/platform``            ``constraints/platform``,            CARRIED
                                                                    ``pipeline/publication``
``model.pad_terrace.TERRACES``       ``planar/pad_terrace``,        ``constraints/pad_fronting``,        CARRIED
                                     ``planar/overlay``             ``pipeline/publication``
``planar.overlay.PAD_AIRSIDE``       ``planar/overlay``             ``pipeline/publication``             CARRIED (was
                                                                                                        carried alone,
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
``classify.road_absorb.ROADS_ABSORBED``  ``classify/road_absorb``    ``pipeline/publication``             NOT CARRIED: like
/ ``ROADS_KEPT`` (§56 (2) 7)                                         (``cluster_pads[].roads_absorbed``)  ``CLUSTER_PADS`` —
                                                                                                        filled by classify,
                                                                                                        so the two sidecar
                                                                                                        keys are EMPTY on a
                                                                                                        resume after it
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

Twins: ``tests/test_v2_capture_state.py``.  Offline and synthetic — no
corpus, no network.
"""
from __future__ import annotations

import copy
import dataclasses as _dc
import importlib
import typing as _t
from collections.abc import Mapping as _Mapping

__all__ = ["CAPTURE_STATE_KEY", "CAPTURE_STATE_VERSION", "Registry",
           "REGISTRIES", "collect", "install", "missing", "unknown",
           "refusal", "clear", "line"]

#: The key the state is RECORDED under, in the ``--capture`` pickle and in
#: the ``--solved-out`` pickle (the tool writes no second spelling).
CAPTURE_STATE_KEY = "capture_state"

#: The record's version.  Bumped when a FIELD's meaning changes (a field
#: ADDED or REMOVED needs no bump: :func:`missing` / :func:`unknown` read
#: the field set itself, which is the honest comparison).  A capture from
#: a LATER version refuses, because this tree cannot know what its fields
#: mean.
CAPTURE_STATE_VERSION = 1


@_dc.dataclass(frozen=True)
class Registry:
    """One module registry of the capture state: where it lives, which
    stage fills it, and which passes read it (the refusal quotes both, so
    a lane reading the message knows what the replay would have got
    wrong)."""

    field: str
    module: str
    attr: str
    filled_by: str
    read_by: tuple[str, ...]

    def live(self) -> _t.Any:
        """The live object, or ``None`` where this tree has neither the
        module nor the attribute (a registry a later tree removed)."""
        try:
            mod = importlib.import_module(self.module)
        except ImportError:
            return None
        return getattr(mod, self.attr, None)


#: THE DECLARED CAPTURE STATE — the ``CARRIED`` rows of the module's
#: census table, in the order the planar stage fills them.
REGISTRIES: tuple[Registry, ...] = (
    Registry("held", "auto_patch_v2.model.platform", "HELD",
             "planar/platform.py + planar/pad_cut.py (the planar stage)",
             ("constraints/platform.py (the hold rows, the block datum Band)",
              "constraints/no_step.py (the plateau vertices, the pair graph)",
              "constraints/jetway_strip.py (the strip is DISARMED on a held block)",
              "model/platform.py (datum_vertices, plateau_vertices)")),
    Registry("plateaus", "auto_patch_v2.model.platform", "PLATEAUS",
             "planar/pad_cut.py (the planar stage)",
             ("constraints/platform.py (the stand-line plateau)",)),
    Registry("landings", "auto_patch_v2.model.platform", "LANDINGS",
             "planar/landing.py via planar/platform.py (the planar stage)",
             ("constraints/platform.py (the landing level rows, RULINGS 2026-10-03e)",
              "constraints/pads.py (the DEM-datum withdrawal)")),
    Registry("platforms", "auto_patch_v2.model.platform", "PLATFORMS",
             "planar/platform.py (the planar stage)",
             ("constraints/platform.py (the refused platforms)",
              "pipeline/publication.py (the sidecar's platform_why)")),
    Registry("terraces", "auto_patch_v2.model.pad_terrace", "TERRACES",
             "planar/pad_terrace.py + planar/overlay.py (the planar stage)",
             ("constraints/pad_fronting.py (the declared terrace's bound)",
              "pipeline/publication.py (terrace_joints_ll, pad_terraces)")),
    Registry("pad_airside", "auto_patch_v2.planar.overlay", "PAD_AIRSIDE",
             "planar/overlay.py (the arrangement, the planar stage)",
             ("pipeline/publication.py (the sidecar's pad_airside_renode)",)),
)

_BY_FIELD = {r.field: r for r in REGISTRIES}


def _snapshot(obj: _t.Any) -> _t.Any:
    """A DEEP copy: the constraint generators MUTATE what they read
    (``constraints/platform.py`` writes ``HELD[ref]["near_miss_contacts"]``),
    so a shallow snapshot would let one replay arm edit the next arm's
    state through the capture."""
    return copy.deepcopy(obj)


def _restore(live: _t.Any, value: _t.Any) -> None:
    """``value`` into ``live`` IN PLACE.  Every reader did ``from ..model.
    platform import HELD`` at import time, so the registry object itself
    is the shared one — rebinding the module attribute would leave every
    importer on the empty original."""
    value = _snapshot(value)
    live.clear()
    if isinstance(live, dict):
        live.update(value)
    elif isinstance(live, list):
        live.extend(value)
    elif isinstance(live, set):
        live.update(value)
    else:                                  # pragma: no cover - declared types
        raise TypeError(f"capture state: {type(live).__name__} is not a "
                        f"registry this record knows how to restore")


def collect() -> dict[str, _t.Any]:
    """THE STATE AT THIS STAGE BOUNDARY: ``{"version", "fields"}``.

    Called by ``--capture`` AFTER the shape stage and by the replay's
    ``--solved-out`` dump — in both cases BEFORE any constraint generator
    has mutated a registry, which is what makes the record the build's own
    state entering ``shape_constraints``."""
    fields = {r.field: _snapshot(live) for r in REGISTRIES
              if (live := r.live()) is not None}
    return {"version": CAPTURE_STATE_VERSION, "fields": fields}


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
    the record is absent.  A field whose registry this tree no longer has
    is not missing: nothing reads it."""
    got = _fields(state)
    return tuple(r.field for r in REGISTRIES
                 if r.live() is not None and r.field not in got)


def unknown(state: _t.Mapping[str, _t.Any] | None) -> tuple[str, ...]:
    """The record's fields this tree does not declare — a capture from a
    tree that carried a registry since removed.  Reported, never fatal:
    no pass reads them."""
    return tuple(sorted(f for f in _fields(state) if f not in _BY_FIELD))


def install(state: _t.Mapping[str, _t.Any] | None) -> tuple[str, ...]:
    """Install every field of ``state`` into its live registry and return
    the field names installed, in declaration order.

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
        live = r.live()
        if live is None:                   # this tree dropped the registry
            continue
        _restore(live, got[r.field])
        done.append(r.field)
    return tuple(done)


def clear() -> tuple[str, ...]:
    """Empty every declared registry — what a FRESH process has, and the
    arm the twins measure the defect in."""
    done: list[str] = []
    for r in REGISTRIES:
        live = r.live()
        if live is not None:
            live.clear()
            done.append(r.field)
    return tuple(done)


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
        lines.append(f"  {f} ({r.module}.{r.attr}) is filled by {r.filled_by} "
                     f"and read by: " + "; ".join(r.read_by))
    lines.append("  A registry the capture does not carry is EMPTY in this "
                 "process, and every pass above then reads it empty: issues "
                 "#208 (HECA §5a relaxed 822 rows against 108) and #224 "
                 "(KCLT 65,212 rows against the build's 49,981).  "
                 "--from classify|planar re-derives them and is faithful.")
    lines.append(f"  {recapture}")
    return "\n".join(lines)


def line(icao: str, installed: _t.Sequence[str],
         state: _t.Mapping[str, _t.Any] | None) -> str:
    """The one loud line a replay prints for the state it installed."""
    if not installed:
        return (f"[{icao}] capture state: none installed (the registries are "
                f"this process's own)")
    sizes = []
    for f in installed:
        r = _BY_FIELD[f]
        live = r.live()
        sizes.append(f"{f} {len(live) if live is not None else 0}")
    extra = unknown(state)
    return (f"[{icao}] capture state v{version_of(state)} installed: "
            + ", ".join(sizes)
            + (f"; {len(extra)} field(s) this tree does not declare, ignored: "
               + ", ".join(extra) if extra else ""))
