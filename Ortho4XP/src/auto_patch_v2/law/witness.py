"""THE LAW A CACHED STAGE READ (stage-cache spec §5, issue #843).

A stage-cache entry is keyed on the stage's inputs and code, but not on the
whole law: a law edit the stage never read must not throw its record away.
So while a cached stage runs, the ``Law`` it is handed is a RECORDING PROXY
(:meth:`LawRecorder.law`): every dataclass node of the law is wrapped, and
the attribute PATH of every value the stage reaches is recorded
(``tables.common.roles``, ``tables.rulesets.FAA.runway`` …).  The entry
stores those paths with a digest of the value at each
(:meth:`LawRecorder.record`), and a later read holds only when every path
resolves to a value with the same digest today (:func:`holds`) — the
``dem_witness`` pattern.  The witness never widens a hit: a path not
recorded is one the stage did not read.

WHAT A PATH ENDS AT.  Only dataclass nodes are proxied.  A field holding
anything else — a number, a string, and also a dict, a tuple or a list —
is a LEAF: the whole value is recorded and returned as it is, so no mapping
or sequence is ever disguised (an edit to any role row reads as an edit to
``tables.common.roles``: coarser than one row, never wrong).  A node read
WHOLE — compared, hashed, printed, copied, pickled (a pool worker) or asked
for a method or property, whose own reads the proxy cannot see — records
the node itself as a leaf.  ``Law.ruleset`` is the one property followed:
it records ``ruleset_key`` and continues at ``tables.rulesets.<key>``.

ONE RECORDER, MANY STAGES.  A memo filled while one stage ran and read by a
later one hands the later stage values computed from law it never read
itself (spec §5 "the memo rule").  The build therefore keeps ONE recorder
across its cached stages and a stage's witness is the CUMULATIVE record at
its end; a stage served from cache :meth:`LawRecorder.replay` s its stored
record into the recorder, so the next stage's witness still names it.
Strictly narrower hits than per-stage witnesses, never wider.

The proxy reports its target's class (``isinstance`` and ``dataclasses``
see the real type) and pickles AS ITS TARGET, so nothing a stage stores
carries a proxy across a process or into a cache file.
"""
from __future__ import annotations

import copy
import dataclasses as _dc
import hashlib
import pickle
import typing as _t

__all__ = ["LawRecorder", "holds", "resolve", "value_digest"]

_MISSING = object()


def value_digest(value: _t.Any) -> str:
    """sha256 of ``value`` pickled (protocol 5).  Law values are frozen
    dataclasses, numbers, strings and their tuples / dicts — no set — so
    the bytes are the same in every process."""
    return hashlib.sha256(pickle.dumps(value, protocol=5)).hexdigest()


def resolve(law: _t.Any, path: tuple[str, ...]) -> _t.Any:
    """The value at ``path`` in ``law`` (attributes; a mapping is indexed),
    or a sentinel no value equals when the path no longer resolves."""
    node = law
    for name in path:
        try:
            node = node[name] if isinstance(node, _t.Mapping) else getattr(node, name)
        except (AttributeError, KeyError, TypeError):
            return _MISSING
    return node


def _split(key: str) -> tuple[str, ...]:
    return tuple(key.split(".")) if key else ()


def holds(law: _t.Any, record: _t.Mapping[str, str] | None) -> str | None:
    """``None`` when every recorded path resolves to the recorded digest in
    ``law``; else the first path that does not (the miss's reason)."""
    if record is None:
        return "law:no witness"
    for key, digest in record.items():
        got = resolve(law, _split(key))
        if got is _MISSING or value_digest(got) != digest:
            return f"law:{key or '<whole>'}"
    return None


class LawRecorder:
    """The recording proxy's owner: :meth:`law` hands out the proxy,
    :meth:`record` the paths read so far with their digests."""

    def __init__(self, law: _t.Any) -> None:
        self._law = law
        self._paths: set[tuple[str, ...]] = set()
        self._digests: dict[tuple[str, ...], str] = {}
        self._closed = False
        self._root = _wrap(law, (), self)

    def law(self) -> _t.Any:
        """The recording proxy over the law (one per recorder)."""
        return self._root

    def target(self) -> _t.Any:
        """The real law."""
        return self._law

    def read(self, path: tuple[str, ...]) -> None:
        """Record ``path`` as read (the proxy's one write); nothing once
        :meth:`close` d."""
        if not self._closed:
            self._paths.add(path)

    def close(self) -> None:
        """Stop recording and let the record go (the last cached stage has
        taken its witness); a proxy a memo kept still answers."""
        self._closed = True
        self._paths.clear()
        self._digests.clear()

    def record(self) -> dict[str, str]:
        """``{dotted path: value digest}`` of every leaf read so far, in
        path order.  A path under one read whole is dropped (it is covered)."""
        kept: list[tuple[str, ...]] = []
        whole: set[tuple[str, ...]] = set()
        for p in sorted(self._paths, key=lambda q: (len(q), q)):
            if any(p[:k] in whole for k in range(len(p))):
                continue
            kept.append(p)
            whole.add(p)
        out: dict[str, str] = {}
        for p in sorted(kept):
            d = self._digests.get(p)
            if d is None:
                d = self._digests[p] = value_digest(resolve(self._law, p))
            out[".".join(p)] = d
        return out

    def replay(self, record: _t.Mapping[str, str] | None) -> None:
        """Merge a stored record's paths (a stage served from cache)."""
        for key in record or ():
            self._paths.add(_split(key))


def _wrap(value: _t.Any, path: tuple[str, ...], rec: LawRecorder) -> _t.Any:
    if _dc.is_dataclass(value) and not isinstance(value, type):
        return _proxy_class(type(value))(value, path, rec)
    rec.read(path)
    return value


_CLASSES: dict[type, type] = {}


def _proxy_class(cls: type) -> type:
    """One proxy class per law dataclass, carrying the dataclass's own field
    table so ``dataclasses.fields`` / ``replace`` / ``asdict`` accept it."""
    got = _CLASSES.get(cls)
    if got is None:
        got = type(f"Witnessed{cls.__name__}", (_Node,),
                   {"__slots__": (), "__dataclass_fields__": cls.__dataclass_fields__,
                    "__dataclass_params__": getattr(cls, "__dataclass_params__", None),
                    "_o4_fields": frozenset(f.name for f in _dc.fields(cls))})
        _CLASSES[cls] = got
    return got


class _Node:
    """A recording view of one frozen law dataclass (module doc)."""

    __slots__ = ("_o4_t", "_o4_p", "_o4_r", "_o4_k")
    _o4_fields: frozenset = frozenset()

    def __init__(self, target: _t.Any, path: tuple[str, ...], rec: LawRecorder) -> None:
        object.__setattr__(self, "_o4_t", target)
        object.__setattr__(self, "_o4_p", path)
        object.__setattr__(self, "_o4_r", rec)
        object.__setattr__(self, "_o4_k", {})

    @property                                  # type: ignore[misc]
    def __class__(self) -> type:               # isinstance sees the law's class
        return type(self._o4_t)

    def _o4_whole(self) -> _t.Any:
        self._o4_r.read(self._o4_p)
        return self._o4_t

    def __getattr__(self, name: str) -> _t.Any:
        kids = self._o4_k
        got = kids.get(name, _MISSING)
        if got is not _MISSING:
            return got
        target = self._o4_t
        if name in self._o4_fields:
            got = _wrap(getattr(target, name), self._o4_p + (name,), self._o4_r)
        elif name == "ruleset" and "ruleset_key" in self._o4_fields:
            key = target.ruleset_key
            self._o4_r.read(self._o4_p + ("ruleset_key",))
            got = _wrap(target.ruleset, self._o4_p + ("tables", "rulesets", key),
                        self._o4_r)
        else:
            # a method or a property: its own reads are invisible here
            return getattr(self._o4_whole(), name)
        kids[name] = got
        return got

    def __setattr__(self, name: str, value: _t.Any) -> None:
        raise _dc.FrozenInstanceError(f"cannot assign to field {name!r}")

    def __delattr__(self, name: str) -> None:
        raise _dc.FrozenInstanceError(f"cannot delete field {name!r}")

    def __eq__(self, other: _t.Any) -> bool:
        return self._o4_whole() == (other._o4_whole() if isinstance(other, _Node)
                                    else other)

    def __ne__(self, other: _t.Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self._o4_whole())

    def __repr__(self) -> str:
        return repr(self._o4_whole())

    def __str__(self) -> str:
        return str(self._o4_whole())

    def __bool__(self) -> bool:
        return bool(self._o4_whole())

    def __reduce_ex__(self, protocol: int) -> _t.Any:
        return _identity, (self._o4_whole(),)

    def __copy__(self) -> _t.Any:
        return self._o4_whole()

    def __deepcopy__(self, memo: dict) -> _t.Any:
        return copy.deepcopy(self._o4_whole(), memo)


def _identity(value: _t.Any) -> _t.Any:
    return value
