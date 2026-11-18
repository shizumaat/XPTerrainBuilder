"""TWO INSTALLED PACKS THAT DEFINE THE SAME AIRPORT (issue #2145, RULINGS 17s).

Owner (2026-11-17T23:37Z): "if there are two packages for the same
airport installed, ask if the user would like to disable the lower one
since it's scenery may overlap."

X-Plane takes an airport's layout from the FIRST pack in
``scenery_packs.ini`` whose ``Earth nav data/apt.dat`` defines it; the
lower pack's DSF objects still draw.  :func:`duplicates` reads the packs'
airport idents and names each pair that shares one:

* the pair's packs are ordered by the ini — ``upper`` first, ``lower``
  the one offered to be disabled;
* two packs of one larger package (``pack_family.same_family``) are
  exempt: never a pair;
* a pack the ini does not list has no known place, so the pair is a
  report (``lower == ""``, ``unlisted`` names it), never an offer.

The answers (:data:`STORE`, per :func:`pair_key`): ``"disable"`` (the
lower pack was disabled) or ``"keep"`` (No — never asked again); no
answer (Not now) asks again.  Nothing here names an airport or a pack.
"""
from __future__ import annotations

import os
import typing as _t
from dataclasses import dataclass

from . import pack_choice as _PC

__all__ = ["DISABLE", "KEEP", "STORE", "Duplicate", "duplicates", "pair_key",
           "parse_key"]

#: the answer that disabled the lower pack
DISABLE = "disable"
#: the answer that keeps both packs enabled (never asked again)
KEEP = "keep"
#: the key segment that marks a same-airport pair (no pack name holds a
#: path separator, so a key with it is never a structure pair's)
_MARK = "same airport"

STORE = _PC.Store(_PC.DUPLICATE_AIRPORT_CHOICES, lambda v: v in (DISABLE, KEEP))


@dataclass(frozen=True)
class Duplicate:
    """Two packs defining the same airport idents: ``packs`` upper first
    (by the ini; alphabetical when one is unlisted), ``lower`` the pack
    to offer ("" when the ini cannot say), ``unlisted`` the pair's packs
    the ini does not list."""
    packs: tuple[str, str]
    idents: tuple[str, ...]
    lower: str
    unlisted: tuple[str, ...]


def duplicates(idents: _t.Mapping[str, _t.Collection[str]],
               order: _t.Sequence[str],
               same_family: _t.Callable[[str, str], bool]) -> list[Duplicate]:
    """Every pair of packs in ``idents`` (pack name -> its airport idents)
    sharing an ident, one family excepted; ``order`` is the ini's enabled
    rows, highest priority first (module doc)."""
    rank = {name: i for i, name in enumerate(order)}
    names = sorted(idents)
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = tuple(sorted(set(idents[a]) & set(idents[b])))
            if not shared or same_family(a, b):
                continue
            unlisted = tuple(n for n in (a, b) if n not in rank)
            if unlisted:
                out.append(Duplicate((a, b), shared, "", unlisted))
                continue
            upper, lower = sorted((a, b), key=rank.__getitem__)
            out.append(Duplicate((upper, lower), shared, lower, ()))
    return out


def pair_key(scenery_dir: str, a: str, b: str) -> str:
    """The store's key of a same-airport pair (order-free)."""
    x, y = sorted((a, b))
    return os.path.join(os.path.abspath(scenery_dir), _MARK, f"{x} | {y}")


def parse_key(key: str) -> tuple[str, str, str] | None:
    """``(scenery_dir, a, b)`` of a :func:`pair_key`, ``None`` for any
    other key."""
    head, tail = os.path.split(key or "")
    scenery, mark = os.path.split(head)
    names = tail.split(" | ")
    if mark != _MARK or len(names) != 2 or not scenery:
        return None
    return scenery, names[0], names[1]
