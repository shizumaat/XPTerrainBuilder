"""THE EMIT AND VERIFY RECORDS (stage-cache spec §4b.6, §4b.7, §7; issue
#843 step 9c): ``pipeline/emit_stage.emit`` and
``pipeline/verify_stage.verify`` read or run through
``pipeline/back_cache.record``.

THE EMIT RECORD is :class:`emit_stage.Emitted` — every file body emit
writes, each with its sha256 (re-hashed before a served body is written:
a body that no longer hashes refuses the record), the lines and report
keys, and ``(surf, pub)`` pickled for verify.  Its key names what emit
reads (spec §4b.6): the final map, the solved ``z``, the design report
(with ``hard_conflict``, ``runway_flex``, ``hold_report``) and the final
constraint set BY THE RECORDS that made them — the solve record's key and
output digest, chained with the last late solve record's when the build
has a late stage (:func:`final_identity`; the strips are in both keys) —
and directly the runway yields, the classification's cells, the
``Airport``, the rebake screen's own key parts and ``Config.feather_m``.
A design report served by the solve record carries the writer's clocks,
so a full hit is byte-identical (RULINGS 2026-10-18d).  NOT the header
(``cfg.header_extra``): the bodies carry none and :func:`emit_stage.install`
applies it on every write.

THE VERIFY RECORD is :class:`verify_stage.Verdict`, keyed on the emit
record's output digest, the final map's identity and the ``Airport``
digest (the caps), and
served only while the patch body and the sidecar ON DISK re-hash to the
ones it judged (RULINGS 2026-10-18c (2))."""
from __future__ import annotations

import hashlib
import pickle
import typing as _t

from ..airport import partition_cache as _pcache
from ..airport.rebake_screen import patch_body_sha256
from . import back_cache as _bc
from . import emit_stage as _emit
from . import solve_record as _sr
from . import verify_stage as _verify

__all__ = ["final_identity", "emit_inputs", "emit", "verify"]


def final_identity(solved: _bc.Got, late: _t.Any = None) -> str | None:
    """One digest naming the final map, ``z``, design report and constraint
    set: the solve record by its KEY and output digest, chained with the
    last late solve record's identity (``late`` the build's
    ``late_records.LateRecords``; ``None`` with no late stage).  ``None``
    when either was not cached — the emit is then not cached either
    (``bypass: undigested``)."""
    return _sr.identity(_sr.identity(solved.key, solved.digest),
                        "none" if late is None else late.final)


def emit_inputs(fc: _t.Any, *, final: str | None, cl, yield_records, lrep, airport,
                objects_out, common: _t.Mapping[str, str],
                feather_m: float) -> dict[str, str | None]:
    """The emit record's digested inputs (module doc); ``final`` is
    :func:`final_identity`; ``{}`` while the cache is off."""
    if not fc.active:
        return {}
    dig = fc.digest
    kept = None
    part = getattr(airport, "partition", None)
    if objects_out and part is not None:
        kept = _pcache.filed(part.pack_root, airport.icao)
    return {**common,
            "final": final,
            "yield_records": dig(yield_records),
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
