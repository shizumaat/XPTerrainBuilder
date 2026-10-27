"""Coordinates typed into the map search field (issue #1317).

The search field's ONE coordinate rule, shared by the Qt window
(in-process) and the macOS app (``Sources/SceneryKit/CoordinateQuery.swift``,
the Swift half), twinned on ``tests/fixtures/latlon_search_cases.json``.

:func:`classify` reads the text as

* a TILE KEY -- two signed integers run together, ``+49+002`` or
  ``-34+151`` -- which selects that tile, as it always has; or
* a POINT -- a latitude and a longitude, which the map centres at ZL 19
  under a reticle.  Accepted:

  - decimal degrees, with or without a comma, signed:
    ``49.0127, 2.5582``  ``-33.94 151.18``
  - a hemisphere letter as prefix or suffix: ``N49.01 E2.55``,
    ``33.94S 151.18E``; with letters the order may be lon first;
  - degrees, minutes, seconds: ``49°00'45.6"N 2°33'29.4"E``, also
    ``49 0 45.6 N 2 33 29.4 E`` and the typographic marks
    (``′ ″ ’ ” º``);
  - degrees and decimal minutes: ``49°00.76'N 2°33.49'E``.

Anything else -- out-of-range values (|lat| > 90, |lon| > 180, minutes or
seconds >= 60), letters other than N/S/E/W, a sign AND a hemisphere -- is
not a coordinate, and the text goes on to the airport search.
"""

import re
from typing import List, Optional, Tuple

__all__ = ["classify", "parse_point", "parse_tile_key", "ZOOM_LEVEL"]

#: The slippy zoom a point search centres at.
ZOOM_LEVEL = 19

_TILE_KEY = re.compile(r"^([+-]\d{1,2})([+-]\d{1,3})$", re.ASCII)

# Typographic marks folded to the ASCII ones the grammar reads.
_FOLD = {
    "\u00ba": "\u00b0",  # masculine ordinal, typed for a degree sign
    "\u2032": "'", "\u2019": "'", "\u2018": "'", "\u00b4": "'", "`": "'",
    "\u2033": '"', "\u201d": '"', "\u201c": '"', "''": '"',
    # Spaces pasted from web pages (no-break, thin, narrow no-break).
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",
}

_TOKEN = re.compile(
    r"\s*(?:(?P<num>[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?P<mark>[\u00b0'\"])?"
    r"|(?P<hemi>[NSEW])|(?P<comma>[,;]))",
    re.ASCII,
)

_MARKS = ("\u00b0", "'", '"')


def parse_tile_key(text: str) -> Optional[Tuple[int, int]]:
    """``(lat, lon)`` of a tile key like ``+49+002``, or None."""
    match = _TILE_KEY.match((text or "").strip())
    if not match:
        return None
    lat, lon = int(match.group(1)), int(match.group(2))
    if -90 <= lat <= 89 and -180 <= lon <= 179:
        return (lat, lon)
    return None


def _tokens(text: str) -> Optional[List[tuple]]:
    """The text as ``("num", value_text, mark)``, ``("hemi", letter)`` and
    ``("comma",)`` tokens, or None when anything else is in it."""
    for old, new in _FOLD.items():
        text = text.replace(old, new)
    text = text.upper().strip()
    out, pos = [], 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            if text[pos:].strip() == "":
                break
            return None
        if match.group("num") is not None:
            out.append(("num", match.group("num"), match.group("mark")))
        elif match.group("hemi"):
            out.append(("hemi", match.group("hemi")))
        else:
            out.append(("comma",))
        pos = match.end()
    return out


def _groups(tokens: List[tuple]) -> Optional[List[dict]]:
    """Split the tokens into coordinate halves: a comma ends one, a
    hemisphere letter after numbers ends one (suffix) or starts the next
    (when the halves are prefixed), a signed number or a degree mark
    after numbers starts the next.  One unbroken run of 2, 4 or 6 bare
    numbers is cut in half."""
    groups: List[dict] = []
    cur = {"prefix": None, "suffix": None, "nums": []}

    def close():
        groups.append(cur)
        return {"prefix": None, "suffix": None, "nums": []}

    for tok in tokens:
        if tok[0] == "comma":
            if cur["nums"]:
                cur = close()
            elif cur["prefix"] or not groups or groups[-1]["suffix"] is None:
                return None  # a comma right after a suffix letter is fine
        elif tok[0] == "hemi":
            if cur["nums"]:
                if cur["prefix"]:
                    cur = close()
                    cur["prefix"] = tok[1]
                else:
                    cur["suffix"] = tok[1]
                    cur = close()
            elif cur["prefix"]:
                return None
            else:
                cur["prefix"] = tok[1]
        else:
            _, value, mark = tok
            last = cur["nums"][-1] if cur["nums"] else None
            if last is not None and (value[0] in "+-" or mark == _MARKS[0]
                                     or last[1] == _MARKS[2]):
                cur = close()
            cur["nums"].append((value, mark))
    if cur["nums"]:
        groups.append(cur)
    elif cur["prefix"]:
        return None
    if len(groups) == 1:
        only = groups[0]
        nums = only["nums"]
        if len(nums) in (2, 4, 6) and all(m is None for _, m in nums):
            half = len(nums) // 2
            groups = [{"prefix": only["prefix"], "suffix": None,
                       "nums": nums[:half]},
                      {"prefix": None, "suffix": only["suffix"],
                       "nums": nums[half:]}]
    return groups if len(groups) == 2 else None


def _value(group: dict) -> Optional[Tuple[float, Optional[str]]]:
    """``(signed degrees, axis)`` of one half, axis "lat"/"lon"/None."""
    nums = group["nums"]
    if not 1 <= len(nums) <= 3 or (group["prefix"] and group["suffix"]):
        return None
    for i, (_, mark) in enumerate(nums):
        if mark is not None and mark != _MARKS[i]:
            return None
    parts = [float(v) for v, _ in nums]
    negative = nums[0][0].startswith("-")
    if any(v[0] in "+-" for v, _ in nums[1:]):
        return None
    for i, v in enumerate(parts[1:], start=1):
        if v >= 60:
            return None
        if i < len(parts) - 1 and v != int(v):
            return None  # decimal minutes then seconds
    if len(parts) > 1 and parts[0] != int(parts[0]):
        return None  # decimal degrees then minutes
    degrees = abs(parts[0]) + sum(v / 60 ** i for i, v in
                                  enumerate(parts[1:], start=1))
    hemi = group["prefix"] or group["suffix"]
    if hemi and nums[0][0][0] in "+-":
        return None
    if negative or hemi in ("S", "W"):
        degrees = -degrees
    axis = {"N": "lat", "S": "lat", "E": "lon", "W": "lon"}.get(hemi)
    return (degrees, axis)


def parse_point(text: str) -> Optional[Tuple[float, float]]:
    """``(lat, lon)`` in decimal degrees of a typed coordinate, or None."""
    tokens = _tokens(text or "")
    if not tokens:
        return None
    groups = _groups(tokens)
    if groups is None:
        return None
    halves = [_value(g) for g in groups]
    if None in halves:
        return None
    (a, axis_a), (b, axis_b) = halves
    if axis_a == "lon" or axis_b == "lat":
        if axis_a == "lat" or axis_b == "lon":
            return None
        a, b = b, a
    elif axis_a is not None and axis_a == axis_b:
        return None
    if abs(a) > 90 or abs(b) > 180:
        return None
    return (a, b)


def classify(text: str):
    """``("tile", (lat, lon))`` for a tile key (it wins),
    ``("point", (lat, lon))`` for a coordinate, else None."""
    tile = parse_tile_key(text)
    if tile is not None:
        return ("tile", tile)
    point = parse_point(text)
    if point is not None:
        return ("point", point)
    return None
