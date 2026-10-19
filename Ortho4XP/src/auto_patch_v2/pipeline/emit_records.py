"""THE EMIT AND VERIFY RECORDS (stage-cache spec §4b.6, §4b.7, §7; issue
#843 step 9c): ``pipeline/emit_stage.emit`` and
``pipeline/verify_stage.verify`` read or run through
``pipeline/back_cache.record``.

THE EMIT RECORD is :class:`emit_stage.Emitted` — every file body emit
writes, each with its sha256 (re-hashed before a served body is written:
a body that no longer hashes refuses the record), the lines and report
keys, and ``(surf, pub)`` pickled for verify.  Its key names what emit
reads, digested here until the solve and the late stage are records of
their own (9b): the final map, the solved ``z`` and the solution's status
fields, the design report WITHOUT its clocks (every ``*_s`` key — a solve
re-run moves only them, and the sidecar's ``design`` block of a served
record keeps the writer's clocks, RULINGS 2026-10-18d), the constraint set
by the assembly's KEY (RULINGS 18e; with a late stage, the final set's
columnar digest), the strips, the conflicts, the runway yields, the late
stage's cut and stage, the classification's cells, the ``Airport``, the
rebake screen's own key parts and ``Config.feather_m``.  NOT the header
(``cfg.header_extra``): the bodies carry none and :func:`emit_stage.install`
applies it on every write.

THE VERIFY RECORD is :class:`verify_stage.Verdict`, keyed on the emit
record's output digest and the map and ``Airport`` digests (the caps), and
served only while the patch body and the sidecar ON DISK re-hash to the
ones it judged (RULINGS 2026-10-18c (2))."""
from __future__ import annotations

import hashlib
import pickle
import time
import typing as _t

from ..airport import partition_cache as _pcache
from ..airport.rebake_screen import patch_body_sha256
from . import back_cache as _bc
from . import emit_stage as _emit
from . import verify_stage as _verify

__all__ = ["emit_inputs", "emit", "verify"]


def _untimed(value: _t.Any) -> _t.Any:
    """``value`` with every ``*_s`` key (a clock) dropped, recursively."""
    if isinstance(value, dict):
        return {k: _untimed(v) for k, v in value.items()
                if not (isinstance(k, str) and k.endswith("_s"))}
    if isinstance(value, (list, tuple)):
        return [_untimed(v) for v in value]
    return value


def emit_inputs(fc: _t.Any, *, pm, sol, cs, cs_key: str | None, cl, strips, design_rep,
                hard_conflict, yield_records, late_report, lrep, airport, objects_out,
                common: _t.Mapping[str, str], feather_m: float) -> dict[str, str | None]:
    """The emit record's digested inputs (module doc); ``{}`` while the
    cache is off."""
    if not fc.active:
        return {}
    from ..model import constraint_codec as _codec
    dig = fc.digest
    if cs_key is None or late_report is not None:
        t = time.perf_counter()
        cs_d = _codec.digest(cs)
        # the build pays this on a hit too, until the late stage is a record
        fc.report["emit_constraints_digest_s"] = round(time.perf_counter() - t, 4)
    else:
        cs_d = "key:" + cs_key
    kept = None
    part = getattr(airport, "partition", None)
    if objects_out and part is not None:
        kept = _pcache.filed(part.pack_root, airport.icao)
    return {**common,
            "pm": dig(pm),
            "solution": dig((sol.z, sol.status.value, sol.iterations, sol.residual)),
            "design": dig((_untimed(design_rep.as_dict()), design_rep.targets,
                           design_rep.jetway_strip, design_rep.runway_flex)),
            "constraints": cs_d,
            "strips": dig(strips),
            "hard_conflict": dig(hard_conflict),
            "yield_records": dig(yield_records),
            "late": dig(None if late_report is None else
                        _untimed({"cut": late_report["cut"], "stage": late_report["stage"]})),
            "cells": dig(cl.cells),
            "airport": fc.airport_digest(airport),
            "dsf_dump": dig(lrep.dsf_dump_path),
            "rebake": dig((bool(objects_out), kept,
                           _pcache.code_digest() if kept else None)),
            "feather_m": repr(float(feather_m))}


class Emit(_t.NamedTuple):
    """:func:`emit`'s answer: the files written, the record, its output
    digest (``None``: not cached) and ``surf_pub()`` — verify's reads."""

    paths: _t.Any
    pieces: _t.Any
    emitted: _emit.Emitted
    digest: str | None
    surf_pub: _t.Callable[[], tuple]


def emit(fc: _t.Any, inputs: _t.Mapping[str, str | None], **kw: _t.Any) -> Emit:
    """``emit_stage.emit(**kw)`` through the emit record (module doc)."""
    got: list = []

    def record(run: _t.Callable[[], _emit.Emitted]) -> _emit.Emitted:
        g = _bc.record(fc, "emit", inputs, run, check=lambda rec: rec.stale())
        got.append(g)
        return g.value
    if not fc.active:
        fc.bypassed("emit")
    paths, pieces, rec, live = _emit.emit(**kw, record=record if fc.active else None)
    digest = got[0].digest if got and got[0].key is not None else None
    held = [live]

    def surf_pub() -> tuple:
        # a served record's objects are decoded here, by a verify that runs
        if held[0] is None:
            held[0] = pickle.loads(rec.surf_pub)
        return held[0]
    return Emit(paths, pieces, rec, digest, surf_pub)


def verify(fc: _t.Any, em: Emit, *, pm_digest: str | None, airport_digest: str | None,
           **kw: _t.Any) -> dict:
    """``verify_stage.verify(**kw)`` through the verify record (module doc):
    ``surf``/``pub`` come from ``em`` and are decoded only when it runs."""
    judged = (hashlib.sha256(em.emitted.patch.body.encode("utf-8")).hexdigest(),
              hashlib.sha256(em.emitted.patch.sidecar.encode("utf-8")).hexdigest())

    def on_disk(v: _verify.Verdict) -> str | None:
        try:
            now = (patch_body_sha256(em.paths.patch),
                   hashlib.sha256(em.paths.sidecar.read_bytes()).hexdigest())
        except OSError:
            return "body:missing"
        return None if now == v.bodies else "body:disk"

    def record(run: _t.Callable[[], _verify.Verdict]) -> tuple[_verify.Verdict, bool]:
        g = _bc.record(fc, "verify", {"emit": em.digest, "pm": pm_digest,
                                      "airport": airport_digest, "verify": "on"},
                       lambda: run()._replace(bodies=judged), check=on_disk)
        state = fc.report["stages"].get(fc.report_name("verify"), {}).get("state")
        return g.value, state == "hit"
    if not fc.active:
        fc.bypassed("verify")
    return _verify.verify(surf=lambda: em.surf_pub()[0], pub=lambda: em.surf_pub()[1],
                          **kw, record=record if fc.active else None)
