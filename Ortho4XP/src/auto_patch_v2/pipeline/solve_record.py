"""THE SOLVE'S RECORD AND ITS CERTIFICATE (stage-cache spec §4b.4, §4b.5;
issue #843 step 9b).

ONE record, ``solve``: the base solve's :class:`Solved` — the
``Solution`` (``z`` stored as a float64 column, exact bits), the whole
``DesignReport`` (it carries the three former side channels
``hard_conflict``, ``runway_flex`` and ``hold_report`` since step 6, and
``pin_yield``), the LP dims, the taxi trend's second-pass report the build
writes into ``lrep.taxi_trend`` and the ribbon-free stage-one report.  Its
key names the prefix by its records (the shape stage's output digest, the
assembly by KEY — RULINGS 2026-10-18e — the strips' output digest), the
ribbon-free prefix's the same way, and the ``Options``.  The hold binding
(``HoldPass``) is a solve INPUT, never a record (spec §4b.3): its arguments
are the map, the law and the airport, already in the key.  The map's held
registry after the solve is a field (:attr:`Solved.held`), installed on a
hit.

NEVER SERVED WITHOUT ITS CERTIFICATE.  A record is served only when, on
the cached ``z`` against the constraint set the build holds NOW: (2)
``solve.design_report.residual`` equals the one recorded at the write
field for field, bit for bit; (3) ``z`` has one finite value per vertex of
the map; (4) the same residual over the HARD rows alone (``[design]
hard_rulings``) equals its recorded value.  The recorded residual is taken
against the set the CALLER handed the solve, not ``Solution.residual``: a
staged solve certifies against the set it rewrote between its stages.
Any failure refuses the record (``refused: certificate: <what>``) and the
solve runs.

Not cached when ``Options.time_limit_s`` is set (``bypass: time_limit``):
a time-limited answer is a function of the clock.

:func:`identity` is what a later stage names a solve (or a late solve) by:
the record's output digest chained with the identity of the map it
solved."""
from __future__ import annotations

import array as _array
import dataclasses as _dc
import hashlib
import math
import pickle
import typing as _t

from ..model.constraints import ConstraintSet
from ..solve.design_report import residual
from ..solve.design_roles import hard_rulings, is_hard
from . import back_cache as _bc

__all__ = ["Solved", "certificate", "refuses", "solve_stage", "identity", "bypass_of"]


class Solved(_t.NamedTuple):
    """The base solve's record (module doc)."""

    sol: _t.Any
    design: _t.Any
    size: dict
    second_pass: dict
    stage_one_report: dict | None
    certificate: tuple
    #: the map's ``registries.held`` after the solve, WHOLE: the solve writes
    #: the hold keys (``model.platform.HOLD_REPORT_KEYS``) AND the per-pad
    #: contact lists (``hold_contacts``, ``residual``, ``near_miss_contacts``,
    #: ``welded_total``) that ``publication.platform_records`` reads
    held: dict


def _fields(res) -> tuple:
    return tuple(float(getattr(res, f.name)) for f in _dc.fields(res))


def certificate(cs: ConstraintSet, z: _t.Sequence[float], law) -> tuple:
    """``(residual over every row, residual over the hard rows)`` of ``cs``
    at ``z`` as float tuples (``()`` with no ``z``)."""
    if not z:
        return ()
    import numpy as np
    zz = np.asarray(z, dtype=float)
    heads = hard_rulings(law)
    hard = ConstraintSet.from_rows(r for r in cs.rows() if is_hard(heads, r))
    return _fields(residual(cs, zz, 0.0)), _fields(residual(hard, zz, 0.0))


def refuses(cert: tuple, cs: ConstraintSet, z: _t.Sequence[float], n: int, law) -> str | None:
    """Why a record whose recorded certificate is ``cert`` may not be served
    for ``cs`` on a map of ``n`` vertices (``None``: it holds)."""
    if len(z) != n:
        return f"certificate: z has {len(z)} values for {n} vertices"
    if not all(math.isfinite(v) for v in z):
        return "certificate: z not finite"
    now = certificate(cs, z, law)
    if not cert or not now:
        return None if cert == now else "certificate: residual"
    if now[0] != cert[0]:
        return "certificate: residual"
    if now[1] != cert[1]:
        return "certificate: hard rows"
    return None


def _encode(s: Solved) -> tuple[bytes, _t.Callable[[], str]]:
    z = _array.array("d", s.sol.z)
    blob = pickle.dumps((z, s._replace(sol=_dc.replace(s.sol, z=()))), protocol=5)
    return blob, lambda: hashlib.sha256(blob).hexdigest()


def _decode(blob: bytes) -> Solved:
    z, s = pickle.loads(blob)
    return s._replace(sol=_dc.replace(s.sol, z=tuple(z)))


#: The solve record's codec: ``z`` as one float64 column, the rest pickled.
SOLVED_CODEC = _bc.Codec(_encode, _decode)


def bypass_of(options) -> str | None:
    """Why a solve under ``options`` is not cached (``None``: it is)."""
    return "time_limit" if getattr(options, "time_limit_s", None) is not None else None


def solve_stage(fc: _t.Any, inputs: _t.Mapping[str, str | None],
                run: _t.Callable[[], tuple], *, cs: ConstraintSet, n: int, law,
                options, held: dict) -> _bc.Got:
    """``run() -> (sol, design, size, second_pass, stage_one_report)`` — the
    base solve — through the ``solve`` record (module doc); ``cs`` is the
    set the solve is handed, ``n`` the map's vertex count, ``held`` the
    map's ``registries.held`` (the solve writes it; a hit installs the
    record's)."""
    import copy
    ran = []

    def fn() -> Solved:
        ran.append(True)
        sol, design, size, second, s1 = run()
        return Solved(sol, design, dict(size), dict(second), s1,
                      certificate(cs, sol.z, law), copy.deepcopy(held))
    got = _bc.record(fc, "solve", inputs, fn, codec=SOLVED_CODEC,
                     check=lambda s: refuses(s.certificate, cs, s.sol.z, n, law),
                     bypass=bypass_of(options))
    if not ran:
        held.clear()
        held.update(copy.deepcopy(got.value.held))
    return got


def identity(*parts: str | None) -> str | None:
    """One digest naming a solved map by ``parts`` (``None`` when any is)."""
    if any(p is None for p in parts):
        return None
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode())
        h.update(b"\0")
    return h.hexdigest()
