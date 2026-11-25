"""TERRAIN OBJECTS A PACK MAY HIDE (owner RULINGS 2026-11-13i (3), #2036 (c)).

Owner (2026-11-13T04:40Z): "Yes give the option for the user to hide it
when we have quality elevation data that closely models the object area,
off by default."  The witness is the build's: ``terrain_model`` marks a
model ``hideable`` when quality elevation covers it and its top follows
that ground closely, and its seat record carries the flag
(``terrain_model.hideable_paths``).  This module turns those resources
into the definitions of a pack DSF dump the hiding leaves out -- the same
omission as the draped photos' (``pack_art.MissingDef``, kind ``object``;
``dsf_write.write_pack(drapes=)``), offered as the row ``terrain`` of the
pack's adjustments, unchecked (``TERRAIN`` of the drape stage).

The paths are remembered per pack between builds (:func:`encode` /
:func:`decode`, kept by ``drape_stage`` in the answers folder), so the
answer and its Undo work outside a build, where there is no DEM.
"""
from __future__ import annotations

import typing as _t

from .pack_art import MissingDef, count_uses, declared_definitions

__all__ = ["terrain_objects", "encode", "decode", "SEP", "HIDE", "KEEP",
           "encode_answers", "decode_answers", "offered", "object_rows", "answers_for"]

#: a per-object answer (#2272): hide an object the build did not offer,
#: keep one it did
HIDE = "hide"
KEEP = "keep"
#: the separator of a per-object answer's word and path
_TAB = "\t"

#: the separator of a remembered path list (never in a DSF resource path)
SEP = "\n"


def terrain_objects(source: str | _t.Iterable[str],
                    paths: _t.Iterable[str]) -> tuple[MissingDef, ...]:
    """The ``OBJECT_DEF`` definitions of a dump (path or rows) naming one
    of ``paths``, each with the rows that place it; ``()`` for none."""
    want = {str(p) for p in paths or () if p}
    if not want:
        return ()
    if not isinstance(source, str):
        source = list(source)
    defs = [(i, p) for i, p in enumerate(declared_definitions(source)["object"])
            if p in want]
    if not defs:
        return ()
    uses = count_uses(source, {("object", i) for i, _p in defs})
    return tuple(MissingDef("object", i, p, uses.get(("object", i), 0))
                 for i, p in defs)


def encode(paths: _t.Iterable[str]) -> str:
    """A path list as one remembered value (sorted, no blanks)."""
    return SEP.join(sorted({str(p) for p in paths if p and SEP not in str(p)}))


def decode(value: str) -> tuple[str, ...]:
    """The paths of a remembered value."""
    return tuple(p for p in (value or "").split(SEP) if p)


def encode_answers(answers: _t.Mapping[str, str]) -> str:
    """Per-object answers (path -> :data:`HIDE` | :data:`KEEP`) as one
    remembered value (sorted; ``""`` for none)."""
    return SEP.join(f"{a}{_TAB}{p}" for p, a in sorted(answers.items())
                    if a in (HIDE, KEEP) and p and SEP not in p and _TAB not in p)


def decode_answers(value: str) -> dict[str, str]:
    """The per-object answers of a remembered value."""
    out = {}
    for line in (value or "").split(SEP):
        a, _sep, p = line.partition(_TAB)
        if p and a in (HIDE, KEEP):
            out[p] = a
    return out


def offered(found: _t.Iterable[str], answers: _t.Mapping[str, str]) -> tuple[str, ...]:
    """THE SET THE ROW HIDES (#2272): the build's offer (``found``, the
    objects quality elevation models) less those the user keeps, plus
    those the user hides (sorted)."""
    out = {str(p) for p in found or () if answers.get(str(p)) != KEEP}
    out |= {p for p, a in answers.items() if a == HIDE}
    return tuple(sorted(out))


def object_rows(models: _t.Iterable[str], found: _t.Iterable[str],
                answers: _t.Mapping[str, str]) -> list[dict]:
    """The terrain row's ``objects`` (#2272): every object the build
    recognised (``models``) or offered, each ``hideable`` (offered) and
    ``hidden`` (in :func:`offered`)."""
    found = {str(p) for p in found or ()}
    hide = set(offered(found, answers))
    every = sorted({str(p) for p in models or ()} | found | hide)
    return [{"path": p, "hideable": p in found, "hidden": p in hide} for p in every]


def answers_for(ticks: _t.Mapping[str, bool], found: _t.Iterable[str]) -> dict[str, str]:
    """The per-object answers a set of ticks (path -> hidden) records: a
    tick that differs from the build's offer is an answer, one that
    agrees is none."""
    found = {str(p) for p in found or ()}
    return {str(p): (HIDE if on else KEEP) for p, on in ticks.items()
            if bool(on) != (str(p) in found)}
