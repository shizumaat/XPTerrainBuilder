"""The columnar :class:`ConstraintSet` codec (stage-cache spec §4c).

A stage-cache record stores constraint rows as COLUMNS, not as pickled
row objects: per row kind, int32 vertex columns, float64 value columns
(``None`` as NaN plus a mask column), int32 indices into one per-record
string table and one ``Source`` table, and length columns for the ragged
fields (``Flat.group``, ``Linear.terms``, the tuple ``follows``,
``Source.inputs``).  Every column is a flat ``array.array``; the record
pickles at protocol 5 with the columns as out-of-band buffers, and its
digest is sha256 over the columns in the fixed order of :data:`LAYOUT`.

The round trip is exact: float64 bits are kept, ``decode(encode(cs)) ==
cs`` by value.  Row identity is NOT kept (equal ``Source`` values come
back as one shared object); no reader keys a row by ``id()`` (spec §8 T6).
A value outside a field's declared type (a list where a tuple is
declared, a string where a number is) is refused at encode — the codec
never silently changes a row; a number of another numeric type comes
back as the equal Python number.

The model package imports no numpy (``tests/auto_patch_v2/test_model.py``),
so the columns are the standard library's ``array``.
"""
from __future__ import annotations

import array as _array
import dataclasses as _dc
import hashlib as _hashlib
import itertools as _it
import math as _math
import operator as _op
import pickle as _pickle
import sys as _sys

from .constraints import (Band, ConstraintSet, Diff, Flat, Linear, Offset, Pin,
                          Source)

__all__ = ["CODEC_VERSION", "LAYOUT", "ColumnarSet", "encode", "decode",
           "digest"]

#: Bumped when the column layout changes; it opens every digest.
CODEC_VERSION = 1

#: Per row kind, its ``ConstraintSet`` field and ``(row field, codec kind)``
#: in the dataclass's own field order (checked at import).  Codec kinds:
#: ``int`` int32; ``float`` float64; ``optfloat`` float64 + ``.none`` mask;
#: ``optstr`` string index, -1 for ``None``; ``src`` ``Source`` index;
#: ``ints`` ragged int tuple (``.len`` + values); ``terms`` ragged
#: ``(vertex, coefficient)`` pairs; ``follows`` ``None`` / int / int tuple.
LAYOUT: tuple[tuple[type, str, tuple[tuple[str, str], ...]], ...] = (
    (Pin, "pins", (("v", "int"), ("z", "float"), ("source", "src"))),
    (Diff, "diffs", (("a", "int"), ("b", "int"), ("cap", "float"), ("d", "float"),
                     ("source", "src"), ("soft", "optstr"), ("ceiling", "optfloat"),
                     ("follows", "follows"), ("rel", "float"))),
    (Flat, "flats", (("group", "ints"), ("source", "src"))),
    (Band, "bands", (("v", "int"), ("lo", "optfloat"), ("hi", "optfloat"),
                     ("source", "src"))),
    (Offset, "offsets", (("a", "int"), ("b", "int"), ("min_delta", "float"),
                         ("source", "src"))),
    (Linear, "linears", (("terms", "terms"), ("lo", "optfloat"), ("hi", "optfloat"),
                         ("source", "src"), ("soft", "optstr"),
                         ("ceiling", "optfloat"), ("follows", "follows"))),
)

for _cls, _attr, _fields in LAYOUT:          # a new row field fails loud here
    assert tuple(f.name for f in _dc.fields(_cls)) == tuple(n for n, _k in _fields), _cls
assert _array.array("i").itemsize == 4 and _array.array("d").itemsize == 8

_INT, _FLT, _BYTE, _SBYTE = "i", "d", "B", "b"
_NONE = type(None)


class ColumnarSet:
    """An encoded ``ConstraintSet``: named columns in a fixed order.
    ``digest()`` is the record's output digest; pickling at protocol 5
    passes every column as a ``PickleBuffer`` (out of band when the
    pickler has a ``buffer_callback``)."""

    __slots__ = ("columns", "_digest")

    def __init__(self, columns: dict[str, _array.array]):
        self.columns = columns
        self._digest: str | None = None

    def digest(self) -> str:
        """sha256 over the codec version and every column, in order."""
        if self._digest is None:
            h = _hashlib.sha256(f"constraint_codec/{CODEC_VERSION}".encode())
            for name, col in self.columns.items():
                h.update(f"\0{name}\0{col.typecode}\0{len(col)}\0".encode())
                h.update(_le_bytes(col))
            self._digest = h.hexdigest()
        return self._digest

    def nbytes(self) -> int:
        """The columns' size in bytes (the record's payload before zlib)."""
        return sum(len(c) * c.itemsize for c in self.columns.values())

    def __eq__(self, other) -> bool:
        return isinstance(other, ColumnarSet) and self.digest() == other.digest()

    def __hash__(self) -> int:
        return hash(self.digest())

    def __reduce_ex__(self, protocol):
        names = tuple(self.columns)
        codes = tuple(c.typecode for c in self.columns.values())
        if protocol >= 5:
            bufs = tuple(_pickle.PickleBuffer(c) for c in self.columns.values())
        else:
            bufs = tuple(c.tobytes() for c in self.columns.values())
        return (_rebuild, (names, codes, bufs))


def _rebuild(names, codes, bufs) -> ColumnarSet:
    cols = {}
    for name, code, buf in zip(names, codes, bufs):
        col = _array.array(code)
        col.frombytes(buf)
        cols[name] = col
    return ColumnarSet(cols)


def _le_bytes(col: _array.array):
    """The column's bytes, little-endian on every host (one digest on
    every platform the engine ships for)."""
    if _sys.byteorder == "little" or col.itemsize == 1:
        return memoryview(col)
    swapped = _array.array(col.typecode, col)
    swapped.byteswap()
    return memoryview(swapped)


# --------------------------------------------------------------------- encode

def _check(field: str, col, allowed: set) -> None:
    """Refuse a value outside the field's declared types.  Numeric
    columns are not checked: ``array`` refuses what is not a number, and
    a number of another type (a bool, a numpy scalar, an int ``z``) comes
    back as the Python ``int`` / ``float`` equal to it, with an equal hash
    — the round trip is by value.  Tuples are checked: a list would come
    back a tuple, which is not equal to it."""
    bad = set(map(type, col)) - allowed
    if bad:
        raise TypeError(f"constraint_codec: {field} holds "
                        f"{sorted(t.__name__ for t in bad)}")


class _Tables:
    """The per-record string and ``Source`` tables, filled while encoding."""

    def __init__(self):
        self.strings: dict[str, int] = {}
        self.src_by_id: dict[int, int] = {}
        self.src_by_value: dict[Source, int] = {}
        self.sources: list[Source] = []

    def string(self, s: str) -> int:
        i = self.strings.get(s)
        if i is None:
            i = self.strings[s] = len(self.strings)
        return i

    def source_indices(self, col) -> list[int]:
        """One table index per row.  A ``Source`` object shared by many
        rows is looked up by value once, at its first row."""
        ids = list(map(id, col))
        first = dict(zip(ids, col))                 # one object per id
        by_id, by_value = self.src_by_id, self.src_by_value
        fresh = [s for k, s in first.items() if k not in by_id]
        _check("source", fresh, {Source})
        for s in fresh:
            i = by_value.get(s)
            if i is None:
                i = by_value[s] = len(self.sources)
                self.sources.append(s)
            by_id[id(s)] = i
        return list(map(by_id.__getitem__, ids))

    def columns(self) -> dict[str, _array.array]:
        """The ``Source`` table and then the string table, as columns."""
        srcs = self.sources
        _check("source.inputs", [s.inputs for s in srcs], {tuple})
        inputs = list(_it.chain.from_iterable(s.inputs for s in srcs))
        _check("source", [s.generator for s in srcs] + [s.ruling for s in srcs]
               + inputs, {str})
        cols = {"src.generator": _array.array(_INT, [self.string(s.generator) for s in srcs]),
                "src.ruling": _array.array(_INT, [self.string(s.ruling) for s in srcs]),
                "src.inputs.len": _array.array(_INT, [len(s.inputs) for s in srcs]),
                "src.inputs": _array.array(_INT, map(self.string, inputs))}
        utf8 = [s.encode("utf-8") for s in self.strings]
        cols["str.len"] = _array.array(_INT, map(len, utf8))
        cols["str.utf8"] = _array.array(_BYTE, b"".join(utf8))
        return cols


def _enc_optfloat(name: str, col) -> dict:
    if None not in col:
        return {name: _array.array(_FLT, col),
                name + ".none": _array.array(_BYTE, bytes(len(col)))}
    return {name: _array.array(_FLT, [_math.nan if x is None else x for x in col]),
            name + ".none": _array.array(_BYTE, [x is None for x in col])}


def _enc_ints(name: str, col) -> dict:
    _check(name, col, {tuple})
    flat = list(_it.chain.from_iterable(col))
    return {name + ".len": _array.array(_INT, map(len, col)),
            name: _array.array(_INT, flat)}


def _enc_terms(name: str, col) -> dict:
    _check(name, col, {tuple})
    pairs = list(_it.chain.from_iterable(col))
    _check(name, pairs, {tuple})
    if pairs and set(map(len, pairs)) != {2}:
        raise TypeError(f"constraint_codec: {name} holds a term that is not a pair")
    vs, cs = (list(map(_op.itemgetter(0), pairs)), list(map(_op.itemgetter(1), pairs)))
    return {name + ".len": _array.array(_INT, map(len, col)),
            name + ".v": _array.array(_INT, vs), name + ".c": _array.array(_FLT, cs)}


def _enc_follows(name: str, col) -> dict:
    """Tag 0 ``None``, 1 a vertex, 2 a vertex tuple; ``.len`` and the
    vertices as a ragged column."""
    if col.count(None) == len(col):
        return {name + ".tag": _array.array(_SBYTE, bytes(len(col))),
                name + ".len": _array.array(_INT, bytes(4 * len(col))),
                name: _array.array(_INT)}
    _check(name, col, {int, tuple, _NONE})
    tags = [0 if x is None else 1 if type(x) is int else 2 for x in col]
    lens = [len(x) if t == 2 else t for t, x in zip(tags, col)]     # tag 0/1 = length
    flat = list(_it.chain.from_iterable((x,) if t == 1 else x
                                        for t, x in zip(tags, col) if t))
    return {name + ".tag": _array.array(_SBYTE, tags),
            name + ".len": _array.array(_INT, lens), name: _array.array(_INT, flat)}


def _encode_field(name: str, kind: str, col, tables: _Tables) -> dict:
    if kind == "int":
        return {name: _array.array(_INT, col)}
    if kind == "float":
        return {name: _array.array(_FLT, col)}
    if kind == "optstr":
        if col.count(None) == len(col):
            return {name: _array.array(_INT, [-1]) * len(col)}
        _check(name, col, {str, _NONE})
        return {name: _array.array(_INT, [-1 if x is None else tables.string(x)
                                          for x in col])}
    if kind == "src":
        return {name: _array.array(_INT, tables.source_indices(col))}
    return {"optfloat": _enc_optfloat, "ints": _enc_ints, "terms": _enc_terms,
            "follows": _enc_follows}[kind](name, col)


def encode(cs: ConstraintSet) -> ColumnarSet:
    """``cs`` as columns.  Raises ``TypeError`` on a row or value the
    layout does not declare."""
    tables, cols = _Tables(), {}
    for cls, attr, fields in LAYOUT:
        rows = getattr(cs, attr)
        _check(attr, (rows,), {tuple})
        _check(attr, rows, {cls})
        cols[f"{attr}.n"] = _array.array(_INT, [len(rows)])
        names = [n for n, _k in fields]
        get = _op.attrgetter(*names)
        columns = list(zip(*map(get, rows))) if rows else [()] * len(names)
        for (name, kind), col in zip(fields, columns):
            cols.update(_encode_field(f"{attr}.{name}", kind, col, tables))
    cols.update(tables.columns())
    return ColumnarSet(cols)


def digest(cs: ConstraintSet) -> str:
    """The columnar digest of ``cs`` (the stage-cache output digest)."""
    return encode(cs).digest()


# --------------------------------------------------------------------- decode

def _ragged(lengths, values) -> list[tuple]:
    out, at = [], 0
    for n in lengths:
        out.append(tuple(values[at:at + n]))
        at += n
    return out


def _decode_field(cols: dict, name: str, kind: str, strings: list, sources: list) -> list:
    if kind in ("int", "float"):
        return cols[name].tolist()
    if kind == "optfloat":
        vals, none = cols[name].tolist(), cols[name + ".none"]
        if any(none):
            return [None if m else x for x, m in zip(vals, none)]
        return vals
    if kind == "optstr":
        idx = cols[name]
        if idx.count(-1) == len(idx):
            return [None] * len(idx)
        return [None if i < 0 else strings[i] for i in idx]
    if kind == "src":
        return list(map(sources.__getitem__, cols[name]))
    if kind == "ints":
        return _ragged(cols[name + ".len"], cols[name].tolist())
    if kind == "terms":
        pairs = list(zip(cols[name + ".v"].tolist(), cols[name + ".c"].tolist()))
        return _ragged(cols[name + ".len"], pairs)
    if kind == "follows":
        tags = cols[name + ".tag"]
        if not any(tags):
            return [None] * len(tags)
        flat, out, at = cols[name].tolist(), [], 0
        for tag, n in zip(tags, cols[name + ".len"]):
            out.append(None if tag == 0 else flat[at] if tag == 1
                       else tuple(flat[at:at + n]))
            at += n
        return out
    raise AssertionError(kind)                  # pragma: no cover - LAYOUT is closed


def _make_rows(cls: type, names: list[str], columns: list[list]) -> tuple:
    """Rows built without the frozen ``__init__``: one ``__dict__`` per
    row, the state ``pickle`` itself restores (the row dataclasses have
    no ``__post_init__``)."""
    new, out = object.__new__, []
    for vals in zip(*columns):
        row = new(cls)
        row.__dict__.update(zip(names, vals))
        out.append(row)
    return tuple(out)


def decode(enc: ColumnarSet) -> ConstraintSet:
    """The ``ConstraintSet`` ``enc`` was encoded from (equal by value)."""
    cols = enc.columns
    raw = cols["str.utf8"].tobytes()
    strings, at = [], 0
    for n in cols["str.len"]:
        strings.append(raw[at:at + n].decode("utf-8"))
        at += n
    inputs = _ragged(cols["src.inputs.len"], [strings[i] for i in cols["src.inputs"]])
    sources = [Source(strings[g], strings[r], ins) for g, r, ins in
               zip(cols["src.generator"], cols["src.ruling"], inputs)]
    kinds = {}
    for cls, attr, fields in LAYOUT:
        if not cols[f"{attr}.n"][0]:
            kinds[attr] = ()
            continue
        names = [n for n, _k in fields]
        kinds[attr] = _make_rows(cls, names, [
            _decode_field(cols, f"{attr}.{n}", k, strings, sources) for n, k in fields])
    return ConstraintSet(**kinds)
