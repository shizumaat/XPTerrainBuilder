"""MALFORMED ``LIGHT_*`` RECORDS in a pack object (issue #1954, #1978).

Measured (owner sim bisect, 2026-11-07): an airport pack object whose
``LIGHT_SPILL_CUSTOM`` row carries 7 numbers instead of 12 — the size,
the three direction values and the cone are missing — makes X-Plane 12
read garbage for the radius, and the light washes the whole valley and
the tree tops white.  Completing the row (a size, a straight-down cone)
in the object removed it entirely.

THE CHECK is the OBJ8 specification's arity per keyword
(https://developer.x-plane.com/article/obj8-file-format-specification/;
the same table the patch build's ``obj8_reader`` reads positions with)::

    LIGHT_NAMED        <name> <x> <y> <z>
    LIGHT_PARAM        <name> <x> <y> <z> [<additional params>]
    LIGHT_CUSTOM       <x> <y> <z> <r> <g> <b> <a> <s> <s1> <t1> <s2> <t2> <dataref>
    LIGHT_SPILL_CUSTOM <x> <y> <z> <r> <g> <b> <a> <s> <dx> <dy> <dz> <semi> <dataref>
    LIGHTS             <offset> <count>

A ``#`` token starts a comment.  A record is MALFORMED when it is SHORT:
a field it needs is missing (:data:`MIN_TOKENS`; a custom light's 12
numbers must all be there), so X-Plane reads it from beyond the line —
the garbage radius above.  Only that: the census of every installed
pack (``tools/pack_health_census.py``, lane l1978, 2026-11-09: 4,177
packs, 48,477 objects with a light) found 232 short records in 16 packs,
and left alone 2,065 records with EXTRA tokens (``LIGHT_NAMED
full_custom_halo_night x y z 1 0 0`` — parameters the keyword does not
take, which X-Plane does not read) and 3,565 custom lights with no
dataref after their 12 numbers: shipping packs, lit as their authors
saw them.  A number spelled oddly (``2,15``, ``--0.3``) is read by
X-Plane as a number and is not touched either.

THE REPAIR (owner 2026-11-07, #1954: "a LIGHT_SPILL_CUSTOM with 7 numbers
before the dataref gets a default size and a straight-down cone in our
copy; drop it if a record can't be completed"):

* a spill light missing its size, direction and cone (7 numbers) gets the
  size of a well-formed spill of the SAME colour in the same object (the
  same fixture), else :data:`DEFAULT_SPILL_SIZE_M`, and the straight-down
  cone :data:`DOWN_CONE`;
* one missing only its direction and cone (8 numbers) gets the cone;
* every other malformed record is DROPPED.

Both hand repairs the owner confirmed in the sim are what this writes
(LFKC ``feuerwehr_1.obj``: size 20 from its same-colour sibling;
``lampe.obj``: no sibling, size 15).  The vendor file is never written:
the repair is applied to OUR copy (``pack_health.objects``) and to the
split bodies (``obj8_split``), which are written from it.
"""
from __future__ import annotations

import typing as _t

__all__ = ["DEFAULT_SPILL_SIZE_M", "DOWN_CONE", "MIN_TOKENS",
           "check_lines", "repair_lines"]

#: the size a completed spill light gets when no same-colour sibling
#: gives one (the owner's LFKC ``lampe.obj`` repair, 2026-11-07)
DEFAULT_SPILL_SIZE_M = 15.0
#: dx dy dz semi — straight down, a 60° half-angle (cos = 0.5)
DOWN_CONE = (0.0, -1.0, 0.0, 0.5)

#: keyword -> the fewest tokens (the keyword included) that carry every
#: field it reads: the name and position; the 12 numbers of a custom
#: light (its dataref, the last field, X-Plane reads as text and an
#: absent one as none — :data:`_NUMBERED` counts the numbers); the offset
#: and count
MIN_TOKENS: dict[str, int] = {
    "LIGHT_NAMED": 5,
    "LIGHT_PARAM": 5,
    "LIGHT_CUSTOM": 13,
    "LIGHT_SPILL_CUSTOM": 13,
    "LIGHTS": 3,
}
#: the keywords whose fields before the dataref are all numbers
_NUMBERED = frozenset({"LIGHT_CUSTOM", "LIGHT_SPILL_CUSTOM"})


class _Finding(_t.NamedTuple):
    """One malformed record: its 0-based line, keyword, token count and
    what the repair does (``"completed"`` | ``"dropped"``)."""

    line: int
    keyword: str
    tokens: int
    action: str


def _tokens(line: str) -> list[str]:
    toks = line.split()
    for i, t in enumerate(toks):
        if t.startswith("#"):
            return toks[:i]
    return toks


def _number(tok: str) -> bool:
    try:
        float(tok)
    except ValueError:
        return False
    return True


def _leading_numbers(toks: _t.Sequence[str]) -> int:
    n = 0
    for t in toks[1:]:
        if not _number(t):
            break
        n += 1
    return n


def _well_formed(toks: _t.Sequence[str]) -> bool:
    need = MIN_TOKENS[toks[0]]
    if toks[0] in _NUMBERED:
        return _leading_numbers(toks) >= need - 1
    return len(toks) >= need


def _spill_numbers(toks: _t.Sequence[str]) -> int:
    """How many numbers a spill row carries before a non-number (its
    dataref); -1 when the row does not end in one."""
    n = _leading_numbers(toks)
    return n if 1 + n == len(toks) - 1 else -1


def _sibling_sizes(lines: _t.Sequence[str]) -> dict[tuple[str, ...], float]:
    """``{(r, g, b): size}`` of the object's well-formed spill lights (the
    first of each colour)."""
    out: dict[tuple[str, ...], float] = {}
    for ln in lines:
        toks = _tokens(ln)
        if (toks[:1] == ["LIGHT_SPILL_CUSTOM"] and _well_formed(toks)
                and _number(toks[8])):
            out.setdefault(tuple(toks[4:7]), float(toks[8]))
    return out


def _completed(toks: _t.Sequence[str], sizes: _t.Mapping) -> list[str] | None:
    """A spill row with its missing tail filled in, or ``None``."""
    if toks[0] != "LIGHT_SPILL_CUSTOM":
        return None
    n = _spill_numbers(toks)
    nums, ref = list(toks[1:1 + n]), toks[-1]
    if n == 7:
        size = sizes.get(tuple(nums[3:6]), DEFAULT_SPILL_SIZE_M)
        nums.append(f"{size:g}")
    elif n != 8:
        return None
    nums += [f"{v:g}" for v in DOWN_CONE]
    return [toks[0], *nums, ref]


def check_lines(lines: _t.Sequence[str]) -> list[_Finding]:
    """Every malformed ``LIGHT_*`` record of an object's ``lines``."""
    out: list[_Finding] = []
    sizes: dict | None = None
    for i, ln in enumerate(lines):
        if "LIGHT" not in ln:
            continue
        toks = _tokens(ln)
        if not toks or toks[0] not in MIN_TOKENS or _well_formed(toks):
            continue
        if sizes is None:
            sizes = _sibling_sizes(lines)
        fixed = _completed(toks, sizes)
        out.append(_Finding(i, toks[0], len(toks),
                           "completed" if fixed else "dropped"))
    return out


def repair_lines(lines: _t.Sequence[str]) -> tuple[list[str], list[_Finding]]:
    """``lines`` with every malformed record completed or dropped (a
    line ending — ``\\r`` — is kept), and the findings.  A well-formed
    object comes back unchanged, line for line."""
    found = check_lines(lines)
    if not found:
        return list(lines), []
    sizes = _sibling_sizes(lines)
    out = list(lines)
    for f in sorted(found, key=lambda f: -f.line):
        raw = out[f.line]
        lead = raw[:len(raw) - len(raw.lstrip())]
        eol = "\r" if raw.endswith("\r") else ""
        fixed = _completed(_tokens(raw), sizes)
        if fixed is None:
            del out[f.line]
        else:
            out[f.line] = lead + " ".join(fixed) + eol
    return out, found
