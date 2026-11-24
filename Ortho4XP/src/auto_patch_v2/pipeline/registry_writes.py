"""WHAT A CACHED STAGE WROTE INTO THE MAP'S REGISTRIES (#2206 D1).

A constraint generator returns rows and ALSO writes into
``pm.registries`` (``constraints/platform`` puts ``hold_contacts``,
``welded_total``, ``near_miss_contacts`` and ``plateau_vertices`` on the
``held`` records).  A record that stored only the rows served a map without
those writes: the solve re-ran on it and every pad read ``residual`` with
no contacts.  So a record carries its stage's writes as a DELTA, by record
key (a later generator's writes to the same pad survive), and a hit
installs them.

:func:`fingerprint` before the stage, :func:`writes_since` after it,
:func:`install` on a hit.  Values are compared by their pickles, so an
array-valued entry compares whole."""
from __future__ import annotations

import copy
import pickle
import typing as _t

from ..model.registries import FIELDS

__all__ = ["fingerprint", "writes_since", "install"]


def _bytes(value: _t.Any) -> bytes:
    return pickle.dumps(value, protocol=5)


def _entry(value: _t.Any) -> _t.Any:
    if isinstance(value, dict):
        return {k: _bytes(v) for k, v in value.items()}
    return _bytes(value)


def fingerprint(reg: _t.Any) -> dict[str, _t.Any]:
    """Every registry field's state, comparable by :func:`writes_since`."""
    out: dict[str, _t.Any] = {}
    for name in FIELDS:
        now = getattr(reg, name)
        out[name] = ({r: _entry(v) for r, v in now.items()} if isinstance(now, dict)
                     else _bytes(now))
    return out


def _dict_delta(now: dict, old: dict) -> dict | None:
    patch: dict = {}
    whole: dict = {}
    for ref, value in now.items():
        was, cur = old.get(ref), _entry(value)
        if was == cur:
            continue
        if isinstance(was, dict) and isinstance(cur, dict):
            patch[ref] = ({k: value[k] for k, b in cur.items() if was.get(k) != b},
                          [k for k in was if k not in cur])
        else:
            whole[ref] = value
    gone = [ref for ref in old if ref not in now]
    if not (patch or whole or gone):
        return None
    return copy.deepcopy({"patch": patch, "whole": whole, "gone": gone})


def writes_since(reg: _t.Any, before: _t.Mapping[str, _t.Any]) -> dict[str, _t.Any]:
    """What was written into ``reg`` since ``before`` (``{}``: nothing),
    detached from the live registries."""
    out: dict[str, _t.Any] = {}
    for name in FIELDS:
        now, old = getattr(reg, name), before[name]
        if isinstance(now, dict) and isinstance(old, dict):
            delta = _dict_delta(now, old)
            if delta is not None:
                out[name] = delta
        elif _bytes(now) != old:
            out[name] = {"value": copy.deepcopy(now)}
    return out


def install(reg: _t.Any, writes: _t.Mapping[str, _t.Any]) -> None:
    """Put a record's :func:`writes_since` into ``reg``, in place."""
    for name, delta in writes.items():
        live = getattr(reg, name)
        if "value" in delta:
            live[:] = copy.deepcopy(delta["value"])
            continue
        for ref, (sets, drops) in delta["patch"].items():
            live[ref].update(copy.deepcopy(sets))
            for k in drops:
                live[ref].pop(k, None)
        live.update(copy.deepcopy(delta["whole"]))
        for ref in delta["gone"]:
            live.pop(ref, None)
