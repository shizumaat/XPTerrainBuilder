# OrthoStudio XP, Copyright (C) 2026 radioharris. Free software under the GNU GPL: see LICENSE.
# Additional terms (GPL v3 section 7) apply to radioharris's material in this file: see NOTICE.
#
# Ported from OrthoStudio XP (https://github.com/radioharris/orthostudio-xp),
# src/orthostudio/numtext.py at 7c028d82dcc59a27296972973aa0663ef37efddc.
# Modified for XPTerrainBuilder, 2026-10-17 (RULINGS 2026-10-17c): module
# renamed, type annotations dropped, write_rows (the chunked formatter the
# .mesh / .node writers share) added.  LICENSE here is
# Ortho4XP/Licence/gpl.txt; NOTICE is Ortho4XP/THIRD_PARTY/orthostudio-xp/NOTICE.
"""The whitespace-separated numbers of a text, parsed and written fast on every system.

``np.fromstring(text, sep=" ")`` parses with the C library's ``strtod`` and
``strtoll``, slow on Windows: the vertices of a ZL16 mesh took 1.15 s on a
Windows runner against 0.40 s on a Linux one (OrthoStudio XP, 2026-09-15).
Python's own parsing of the split tokens took 0.32 s there, with the same
numbers bit for bit (it rounds correctly, like the C libraries of macOS and
Linux); elsewhere ``np.fromstring`` stays, 4 to 5 times faster than
splitting for integers.
"""

import os

import numpy as np

__all__ = ["SPLIT_TOKENS", "WRITE_CHUNK_ROWS", "parse_numbers", "write_rows"]

#: Whether :func:`parse_numbers` splits the text and parses the tokens
#: (Windows) rather than handing it to ``np.fromstring``.
SPLIT_TOKENS = os.name == "nt"


def parse_numbers(text, dtype=np.float64, *, split=None):
    """The numbers of ``text``, separated by any whitespace, as a flat array
    of ``dtype``.

    ``ValueError`` for a token that is not a number, both ways (an integer
    ``dtype`` refuses ``"1.5"`` too).  The callers check the count against
    the text's own header.  ``split`` chooses the way (:data:`SPLIT_TOKENS`
    by default)."""
    if not (SPLIT_TOKENS if split is None else split):
        return np.fromstring(text, dtype=dtype, sep=" ")
    return np.array(text.split(), dtype=dtype)


#: Rows formatted per ``%`` operation by :func:`write_rows`.
WRITE_CHUNK_ROWS = 65536


def write_rows(handle, row_format, table):
    """Write every row of the 2-D ``table`` as ``row_format % tuple(row)``.

    Exactly the text a per-row ``row_format % tuple(row)`` writes (the same
    CPython float formatting), assembled one ``%`` per chunk of rows: about
    twice as fast as formatting each value and joining (2.4 s -> 1.1 s for
    1.3 M mesh vertices, 2026-10-17)."""
    rows = table.shape[0]
    for start in range(0, rows, WRITE_CHUNK_ROWS):
        chunk = table[start:start + WRITE_CHUNK_ROWS]
        handle.write((row_format * len(chunk)) % tuple(chunk.ravel().tolist()))
