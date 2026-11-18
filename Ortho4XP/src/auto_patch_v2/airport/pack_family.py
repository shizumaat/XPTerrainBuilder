"""ARE TWO SCENERY PACKS PARTS OF ONE LARGER PACKAGE? (issue #2145, RULINGS 17s)

Owner (2026-11-17T23:21Z): "if both packages are part of the same larger
package, e.g. simHeaven, assume that's intentional and don't warn about
it, just keep both."

THE WITNESS — the folder names' shared leading words name one product.
A pack's name is read as its words (letters and digits, lower case; a
bare number or a single character is an ordering mark — ``1-``, ``0_``,
``_A_``, ``x_`` — and is skipped).  Two packs are one family when their
names begin with the same words AND no airport pack outside the pair
begins with those words: the shared words then name this one product
(a vendor's airport + overlays + city set, one simHeaven region), not a
publisher or a sorting prefix several airports carry (a publisher's
name, or a user's own ``<country> - 100_airport -`` scheme).

Why the name, not the other witnesses: pack metadata carries no author
(apt.dat, library.txt and the DSF properties have no publisher field
most packs fill), and install time fails for a family updated piecewise
(simHeaven regions installed months apart).  The name is what every
installer and every family keeps.

Limits, by design: a family the user renamed apart (no shared leading
words) is not seen as one, so it is asked about; in a folder with one
airport under a shared sorting prefix, that prefix reads as a product
(both packs are then kept — the owner's "assume intentional").
Nothing here names a pack.
"""
from __future__ import annotations

import re
import typing as _t

__all__ = ["words", "shared_lead", "same_family"]

_WORD = re.compile(r"[a-z0-9]+")


def words(name: str) -> tuple[str, ...]:
    """The name's words, ordering marks skipped (module doc)."""
    return tuple(w for w in _WORD.findall(name.lower())
                 if len(w) > 1 and not w.isdigit())


def shared_lead(a: str, b: str) -> tuple[str, ...]:
    """The leading words both names begin with."""
    out = []
    for x, y in zip(words(a), words(b), strict=False):
        if x != y:
            break
        out.append(x)
    return tuple(out)


def same_family(a: str, b: str, names: _t.Iterable[str],
                is_airport: _t.Callable[[str], bool]) -> bool:
    """True when packs ``a`` and ``b`` are one larger package (module doc):
    ``names`` is every pack in the scenery folder, ``is_airport`` says
    whether a pack (by name) carries a runway; it is asked only of the
    packs whose names begin with the shared words."""
    lead = shared_lead(a, b)
    if not lead:
        return False
    n = len(lead)
    return not any(words(o)[:n] == lead and is_airport(o)
                   for o in names if o not in (a, b))
