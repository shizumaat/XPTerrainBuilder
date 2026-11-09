"""DUPLICATE AND STACKED DRAPED PLACEMENTS in a pack DSF (issue #1975,
#1978).

Measured (2026-11-09, DSFTool): an airport pack's tile DSF placed one
line definition 128,630 times, 128,530 of them two-point segments
0.11-0.32 m long piled on the tile boundary — 128,523 exact repeats of
another placement.  X-Plane draws every one of them whenever that spot is
in view: the frame rate fell "from certain angles", and removing them by
hand fixed it in the sim.

THE CHECK, on the DSFTool text dump (one ``BEGIN_POLYGON`` ...
``END_POLYGON`` block is one placement), for the DRAPED kinds only —
lines (``.lin``) and draped polygons (``.pol``), where a second copy is
pure overdraw:

* EXACT DUPLICATE — a block identical to an earlier one: the same
  definition, parameter and windings, coordinate for coordinate as
  printed.  Never authored on purpose (a WED export artifact); the FIRST
  stays.
* STACKED SLIVER — a line under :data:`SLIVER_M` across (its points and
  bezier handles) in a spot where its definition starts at least
  :data:`STACK_MIN` placements: a pile, not a marking.

THE THRESHOLDS, from the census of every installed airport pack (1,086
packs, 2,254 tile DSFs, ``tools/pack_health_census.py``, lane l1978,
2026-11-09; exact repeats in 258 packs): the densest LEGITIMATE
spot holds 90 starts of one line definition (taxi-sign borders); the
pile that dropped the frame rate holds 128,530 — :data:`STACK_MIN` sits
an order of magnitude above the first and two below the second.  Short
lines away from a pile are a continuum (422 under 0.5 m, 353 more in
0.5-0.6 m, rising) — dashes an author drew — and are never touched.
Duplicated forests, facades and object strings (1,013 / 456 / 52
blocks) draw extra 3D objects rather than overdraw, and are left to the
user's "Optimise pack" (#1707) like duplicate objects.

THE REPAIR is :func:`repair_text`: the blocks leave the dump that
``dsf_write.write_pack`` encodes, on every write from the pristine
``.anchor_bak`` — the vendor file is kept, and Restore originals puts it
back.
"""
from __future__ import annotations

import math
import os
import typing as _t
from collections import Counter

__all__ = ["SLIVER_M", "STACK_MIN", "DRAPED", "Report", "scan",
           "repair_text"]

#: a line whose whole extent is under this is a sliver
SLIVER_M = 0.5
#: a spot (~10 m, :func:`_cell`) where one definition starts this many
#: placements is a pile
STACK_MIN = 1000
#: the polygon kinds a repeat of which is overdraw
DRAPED = (".lin", ".pol")
_M_PER_DEG_LAT = 110_540.0
_M_PER_DEG_LON_EQ = 111_320.0


class Report(_t.NamedTuple):
    """What :func:`scan` found: the block ordinals to drop, the counts
    per reason (``duplicates``, ``stacked`` slivers), per
    definition path, and the busiest spot (lat, lon, blocks dropped
    there) — ``()`` when nothing is."""

    drop: frozenset
    duplicates: int
    stacked: int
    by_def: dict
    site: tuple

    @property
    def dropped(self) -> int:
        return len(self.drop)


def _extent_m(rows: _t.Sequence[str]) -> float:
    """The diagonal, in metres, of the box holding every coordinate pair
    of a block's ``POLYGON_POINT`` rows (a bezier row's handle too)."""
    lons: list[float] = []
    lats: list[float] = []
    for r in rows:
        toks = r.split()
        if toks[:1] != ["POLYGON_POINT"]:
            continue
        nums = toks[1:]
        pairs = 2 if len(nums) >= 4 else 1
        try:
            for k in range(pairs):
                lons.append(float(nums[2 * k]))
                lats.append(float(nums[2 * k + 1]))
        except (IndexError, ValueError):
            return math.inf
    if not lons:
        return math.inf
    lat0 = math.radians(sum(lats) / len(lats))
    dx = (max(lons) - min(lons)) * _M_PER_DEG_LON_EQ * math.cos(lat0)
    dy = (max(lats) - min(lats)) * _M_PER_DEG_LAT
    return math.hypot(dx, dy)


def _blocks(lines: _t.Sequence[str]):
    """``(ordinal, def index, head row, body rows)`` per polygon block."""
    n = -1
    head: str | None = None
    body: list[str] = []
    for raw in lines:
        s = raw.strip()
        if s.startswith("BEGIN_POLYGON"):
            n += 1
            head, body = s, []
        elif s.startswith("END_POLYGON"):
            if head is not None:
                toks = head.split()
                try:
                    idx = int(toks[1])
                except (IndexError, ValueError):
                    idx = -1
                yield n, idx, head, body
            head = None
        elif head is not None and s:
            body.append(s)


def _first_point(rows: _t.Sequence[str]) -> tuple[float, float] | None:
    for r in rows:
        toks = r.split()
        if toks[:1] == ["POLYGON_POINT"] and len(toks) >= 3:
            try:
                return float(toks[2]), float(toks[1])
            except ValueError:
                return None
    return None


def _cell(p: tuple[float, float] | None) -> tuple | None:
    """The ~10 m spot (4 decimals of a degree) a block starts in."""
    return None if p is None else (round(p[0], 4), round(p[1], 4))


def scan(lines: _t.Sequence[str]) -> Report:
    """The duplicate and stacked draped blocks of a dump's ``lines``."""
    defs = [ln.strip()[len("POLYGON_DEF "):] for ln in lines
            if ln.startswith("POLYGON_DEF ")]
    kind = [os.path.splitext(d)[1].lower() for d in defs]
    blocks = [(n, idx, head, body, _cell(_first_point(body)))
              for n, idx, head, body in _blocks(lines)
              if 0 <= idx < len(defs) and kind[idx] in DRAPED]
    starts = Counter((idx, c) for _n, idx, _h, _b, c in blocks)
    seen: set = set()
    drop: set[int] = set()
    dup = degen = 0
    by_def: Counter = Counter()
    cells: Counter = Counter()
    for n, idx, head, body, c in blocks:
        key = (head, tuple(body))
        if key in seen:
            dup += 1
        else:
            seen.add(key)
            if not (kind[idx] == ".lin" and starts[(idx, c)] >= STACK_MIN
                    and _extent_m(body) < SLIVER_M):
                continue
            degen += 1
        drop.add(n)
        by_def[defs[idx]] += 1
        if c is not None:
            cells[c] += 1
    site = ()
    if cells:
        (lat, lon), count = cells.most_common(1)[0]
        site = (lat, lon, count)
    return Report(frozenset(drop), dup, degen, dict(by_def), site)


def repair_text(text: str) -> tuple[str, Report]:
    """``text`` (a DSFTool dump) without the blocks :func:`scan` finds,
    every other byte as it was; and the report."""
    lines = text.splitlines(keepends=True)
    rep = scan(lines)
    if not rep.drop:
        return text, rep
    out: list[str] = []
    n = -1
    skipping = False
    for raw in lines:
        s = raw.lstrip()
        if s.startswith("BEGIN_POLYGON"):
            n += 1
            skipping = n in rep.drop
        if not skipping:
            out.append(raw)
        if s.startswith("END_POLYGON"):
            skipping = False
    return "".join(out), rep
