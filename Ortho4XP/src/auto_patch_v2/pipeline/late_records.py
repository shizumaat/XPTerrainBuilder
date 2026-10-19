"""THE LAST STAGE THROUGH ITS RECORDS (stage-cache spec §4b.5; issue #843
step 9b): per pass ``late.cut.<pass>`` and ``late.solve.<pass>``, the
derive between them going through the prefix's own records (§4b.3).

``late.cut.<n>``: the :class:`~pipeline.late_stage.LateCut` (the cut
classification, its report, the part stations, the pad roads' exits) and
the lines it said.  Keyed on the classification it was handed, the BASE
(the solved map the cut reads: the base solve's :func:`~pipeline.
solve_record.identity`, or the previous pass's late solve), the airport,
the classify rules and the pass's kind.

``late.solve.<n>``: what ``late_stage.late_solve`` returns, stored against
the derive's own products — the final map as the fields it replaced on the
derived map, the stage's row set and ``cs_full`` as DELTAS over the
derived constraint set in the columnar codec (RULINGS 2026-10-18e), the
``Solution`` (``z`` a float64 column) and the rest of the report; the cut
classification and the strips are the cut record's and the derive's own,
re-attached on a hit.  Keyed on the base, the cut's output digest, the
derive's record identities (its map, the assembly's KEY, the strips),
the ``Options`` and the pass's kind.  NEVER SERVED WITHOUT ITS
CERTIFICATE (``pipeline/solve_record``) against ``cs_full``.

A hit says the record's lines again, so the log reads as the cold build's.

:class:`LateRecords` is the object ``late_stage.run_last_stages`` takes as
``records``; with none it runs as it always did."""
from __future__ import annotations

import array as _array
import dataclasses as _dc
import hashlib
import pickle
import time
import typing as _t

from . import back_cache as _bc
from . import solve_record as _sr
from .constraint_records import from_delta, kinds_of, set_delta

__all__ = ["LateRecords", "prefix_identity"]

#: the report keys a late record does not store: re-attached on a hit
_ATTACHED = ("cl", "strips", "cs", "cs_full")
_PREFIX_KEYS = ("pm", "airport", "assembly", "strips", "chain")


def prefix_identity(keys: _t.Mapping[str, str | None] | None) -> str | None:
    """One digest naming a prefix run by its records (``PrefixRecord.keys``);
    ``None`` when the run was not cached."""
    if not keys:
        return None
    return _sr.identity(*(keys.get(k) for k in _PREFIX_KEYS))


class _Teed:
    """An ``out`` that also keeps the lines (a miss says them as it runs)."""

    def __init__(self, out: _t.Callable[[str], None]) -> None:
        self.out, self.lines, self.ran = out, [], False

    def __call__(self, m: str) -> None:
        self.lines.append(m)
        self.out(m)


def _late_codec(pm_d, cs_d, cut, strips) -> _bc.Codec:
    base = kinds_of(cs_d)

    def encode(o) -> tuple[bytes, _t.Callable[[], str]]:
        pm, sol, rep, cert, lines = o
        delta = {f.name: getattr(pm, f.name) for f in _dc.fields(pm)
                 if getattr(pm, f.name) is not getattr(pm_d, f.name)}
        kept = {k: v for k, v in rep.items() if k not in _ATTACHED}
        blob = pickle.dumps({"pm": delta, "z": _array.array("d", sol.z),
                             "sol": _dc.replace(sol, z=()), "report": kept,
                             "cs": set_delta(rep["cs"], base),
                             "cs_full": set_delta(rep["cs_full"], base),
                             "cert": cert, "lines": lines}, protocol=5)
        return blob, lambda: hashlib.sha256(blob).hexdigest()

    def decode(blob: bytes):
        rec = pickle.loads(blob)
        rep = {**rec["report"], "cl": cut.cl, "strips": strips,
               "cs": from_delta(rec["cs"], base), "cs_full": from_delta(rec["cs_full"], base)}
        return (_dc.replace(pm_d, **rec["pm"]) if rec["pm"] else pm_d,
                _dc.replace(rec["sol"], z=tuple(rec["z"])), rep, rec["cert"], rec["lines"])
    return _bc.Codec(encode, decode)


class LateRecords:
    """The last stage's records for one build: ``fc`` the build's cache,
    ``inputs`` what every pass reads besides its own (the airport, the
    classify rules, the ``Options``), ``base`` the base solve's identity,
    ``law`` and ``options`` the solve's."""

    def __init__(self, fc: _t.Any, inputs: _t.Mapping[str, str | None], base: str | None,
                 law: _t.Any, options: _t.Any) -> None:
        self.fc, self.inputs, self.base = fc, dict(inputs), base
        self.law, self.options = law, options
        self.passes = 0
        self._cut: str | None = None

    def cut(self, cl, roads_only: bool, run: _t.Callable[[_t.Callable[[str], None]], _t.Any],
            out: _t.Callable[[str], None]):
        """``run(out) -> LateCut`` through ``late.cut.<pass>``."""
        self.passes += 1
        tee = _Teed(out)
        t = time.perf_counter()

        def fn():
            tee.ran = True
            return run(tee), tee.lines
        got = _bc.record(self.fc, f"late.cut.{self.passes}",
                         {**self.inputs, "cl": self.fc.digest(cl), "base": self.base,
                          "roads_only": str(bool(roads_only))}, fn, code="late_cut")
        self._cut = got.digest
        cut, lines = got.value
        if not tee.ran:
            for m in lines:
                out(m)
            cut = _dc.replace(cut, wall_s=time.perf_counter() - t)
        return cut

    def solve(self, cut, derive: _t.Any, derived: tuple, t_derive: float, roads_only: bool,
              run: _t.Callable[[_t.Callable[[str], None]], tuple],
              out: _t.Callable[[str], None]) -> tuple:
        """``run(out) -> (pm, sol, report)`` through ``late.solve.<pass>``;
        ``derived`` is the derive's ``(pm, cs, strips, hold)`` and
        ``t_derive`` its seconds (a hit's report carries this run's clocks
        for the cut and the derive)."""
        pm_d, cs_d, strips_d, _hold = derived
        ident = prefix_identity(getattr(getattr(derive, "last", None), "keys", None))
        tee = _Teed(out)

        def fn():
            tee.ran = True
            pm, sol, rep = run(tee)
            return pm, sol, rep, _sr.certificate(rep["cs_full"], sol.z, self.law), tee.lines

        def check(o) -> str | None:
            return _sr.refuses(o[3], o[2]["cs_full"], o[1].z, len(o[0].vertices), self.law)
        got = _bc.record(self.fc, f"late.solve.{self.passes}",
                         {**self.inputs, "base": self.base, "cut": self._cut,
                          "derive": ident, "roads_only": str(bool(roads_only))},
                         fn, code="late_solve", codec=_late_codec(pm_d, cs_d, cut, strips_d),
                         check=check, bypass=_sr.bypass_of(self.options))
        pm, sol, rep, _cert, lines = got.value
        if not tee.ran:
            for m in lines:
                out(m)
            rep["wall_s"] = {**rep["wall_s"], "cut": round(cut.wall_s, 2),
                             "derive": round(t_derive, 2)}
        self.base = _sr.identity(ident, got.digest)
        return pm, sol, rep
