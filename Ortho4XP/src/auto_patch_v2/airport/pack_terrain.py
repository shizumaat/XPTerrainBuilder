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
pack's adjustments, unchecked (``auto_patch.drape_stage.TERRAIN``).

The paths are remembered per pack between builds (:func:`encode` /
:func:`decode`, kept by ``drape_stage`` in the answers folder), so the
answer and its Undo work outside a build, where there is no DEM.
"""
from __future__ import annotations

import typing as _t

from .pack_art import MissingDef, count_uses, declared_definitions

__all__ = ["terrain_objects", "encode", "decode", "SEP"]

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
