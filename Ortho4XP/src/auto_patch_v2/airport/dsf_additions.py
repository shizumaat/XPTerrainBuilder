"""WHAT THIS ENGINE ADDS TO A PACK DSF (spec 2123 §A2 / §B2): a generated
object's placement and a generated road chain, written into a DSFTool
text dump.  ``dsf_write`` EDITS the rows a pack already has; this module
only ADDS rows, and never renumbers a definition the dump declares.

* :func:`def_insert_at` -- where a new definition goes: in DSFTool's
  dump order (:data:`DEF_ORDER`), so a round trip lists it where it was
  written;
* :func:`add_object` -- one ``OBJECT_DEF`` appended after the last one
  and one ``OBJECT_MSL idx lon lat msl heading`` row (:func:`add_objects`
  places many in one pass, reusing a definition the dump declares) (the token order of
  ``dsf_write._guest_row``; a DSFTool dump spells it so: LFLB's
  ``OBJECT_MSL 1017 5.870424678 45.627386130 500.000000000 0.000000``);
* :func:`add_network` -- a ``NETWORK_DEF`` (a DSF holds one) and one
  segment per consecutive pair of junctions of each :class:`Chain`::

      BEGIN_SEGMENT <net> <subtype> <node> <lon> <lat> <level>
      SHAPE_POINT <lon> <lat> 0
      END_SEGMENT <node> <lon> <lat> <level>

  The third coordinate of a JUNCTION is its stacking level (X-Plane's
  "DSF Usage" page: for draped road types the elevation is a stacking
  layer, 0 on the ground, 1, 2 ... for overpasses); a shape point carries
  0 (simHeaven's +59+017 roads: 655,405 of 655,405 shape points are 0).
  Junction ids continue after the dump's largest (the encoder renumbers
  them anyway -- ``dsf_write`` measured LEMD 249 -> 243).

Build-time impact: string edits, microseconds.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Chain", "DEF_ORDER", "add_object", "add_objects", "add_network",
           "def_insert_at"]


@_dc.dataclass(frozen=True)
class Chain:
    """A road chain: ``junctions`` ``(lon, lat, level)`` in order, one
    road ``subtype`` (the net's virtual type), straight between them."""

    subtype: int
    junctions: tuple[tuple[float, float, int], ...]


#: The order DSFTool prints the definition lists in, whatever order the
#: text it encoded gave them (each list is its own atom; measured
#: DSFTool 2.4.0-b1, 2026-11-26: a text declaring NETWORK_DEF, OBJECT_DEF,
#: TERRAIN_DEF in that order dumps TERRAIN_DEF, OBJECT_DEF, POLYGON_DEF,
#: NETWORK_DEF).  A definition added anywhere else is a structural-row
#: change to the round-trip verifier (#2291: CYYZ's new tree
#: ``POLYGON_DEF``s written after its ``NETWORK_DEF``).
DEF_ORDER = ("TERRAIN_DEF", "OBJECT_DEF", "POLYGON_DEF", "NETWORK_DEF",
             "RASTER_DEF")


def _keyword(line: str) -> str:
    return line.split(None, 1)[0] if line.strip() else ""


def def_insert_at(lines: _t.Sequence[str], keyword: str) -> int:
    """The line index a new ``keyword`` definition (one of
    :data:`DEF_ORDER`) is inserted at so the text lists its definitions
    as DSFTool dumps them: one past the last row of ``keyword`` or of a
    kind before it, else at the first row of a kind after it, else one
    past the last ``PROPERTY`` row.  Never renumbers a definition."""
    rank = DEF_ORDER.index(keyword)
    after = before = prop = -1
    for i, ln in enumerate(lines):
        kw = _keyword(ln)
        if kw in DEF_ORDER:
            if DEF_ORDER.index(kw) <= rank:
                after = i
            elif before < 0:
                before = i
        elif kw == "PROPERTY":
            prop = i
    if after >= 0:
        return after + 1
    return before if before >= 0 else prop + 1


def add_object(text: str, resource: str, lon: float, lat: float, msl: float,
               heading_deg: float) -> tuple[str, int]:
    """``text`` with ``resource`` declared (appended) and placed once at
    ``msl`` metres; returns ``(text, its definition index)``."""
    text, idx = add_objects(text, [(resource, lon, lat, msl, heading_deg)], reuse=False)
    return text, idx[0]


def add_objects(text: str, rows: _t.Sequence[tuple[str, float, float, float, float]],
                reuse: bool = True) -> tuple[str, list[int]]:
    """``text`` with every ``(resource, lon, lat, msl, heading)`` of ``rows``
    placed as an ``OBJECT_MSL`` row; a resource the dump already declares
    keeps its definition when ``reuse``, any other is declared once
    (appended).  Returns ``(text, each row's definition index)``."""
    lines = text.split("\n")
    defs = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("OBJECT_DEF ")]
    at = def_insert_at(lines, "OBJECT_DEF")
    known = {d: i for i, d in enumerate(defs)} if reuse else {}
    new: list[str] = []
    idx: list[int] = []
    for res, *_ in rows:
        if res not in known:
            known[res] = len(defs) + len(new)
            new.append(res)
        idx.append(known[res])
    lines[at:at] = [f"OBJECT_DEF {r}" for r in new]
    tail = len(lines)
    while tail > 0 and not lines[tail - 1].strip():
        tail -= 1
    lines[tail:tail] = [f"OBJECT_MSL {i} {lon:.9f} {lat:.9f} {msl:.4f} {hdg:.6f}"
                        for i, (_r, lon, lat, msl, hdg) in zip(idx, rows, strict=True)]
    return "\n".join(lines), idx


def add_network(text: str, net_def: str, chains: _t.Sequence[Chain]) -> str:
    """``text`` with ``chains`` appended as segments of ``net_def``.  A
    dump that already declares a different network is refused: one
    ``.net`` per DSF (X-Plane's rule)."""
    lines = text.split("\n")
    nets = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("NETWORK_DEF ")]
    if nets and nets != [net_def]:
        raise ValueError(f"the DSF already uses {nets[0]!r}; one network per DSF")
    if not nets:
        lines.insert(def_insert_at(lines, "NETWORK_DEF"), f"NETWORK_DEF {net_def}")
    node = 0
    for ln in lines:
        t = ln.split()
        if t[:1] == ["BEGIN_SEGMENT"] and len(t) >= 4:
            node = max(node, int(t[3]))
        elif t[:1] == ["END_SEGMENT"] and len(t) >= 2:
            node = max(node, int(t[1]))
    seg: list[str] = []
    for ch in chains:
        ids = list(range(node + 1, node + 1 + len(ch.junctions)))
        node += len(ch.junctions)
        pairs = list(zip(ch.junctions, ids, strict=True))
        for (a, ia), (b, ib) in zip(pairs[:-1], pairs[1:], strict=True):
            seg.append(f"BEGIN_SEGMENT 0 {ch.subtype} {ia} {a[0]:.9f} {a[1]:.9f} {float(a[2]):.9f}")
            seg.append(f"END_SEGMENT {ib} {b[0]:.9f} {b[1]:.9f} {float(b[2]):.9f}")
    tail = len(lines)
    while tail > 0 and not lines[tail - 1].strip():
        tail -= 1
    lines[tail:tail] = seg
    return "\n".join(lines)
