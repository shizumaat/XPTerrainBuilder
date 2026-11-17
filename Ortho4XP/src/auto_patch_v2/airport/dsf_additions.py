"""WHAT THIS ENGINE ADDS TO A PACK DSF (spec 2123 §A2 / §B2): a generated
object's placement and a generated road chain, written into a DSFTool
text dump.  ``dsf_write`` EDITS the rows a pack already has; this module
only ADDS rows, and never renumbers a definition the dump declares.

* :func:`add_object` -- one ``OBJECT_DEF`` appended after the last one
  and one ``OBJECT_MSL idx lon lat msl heading`` row (the token order of
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

__all__ = ["Chain", "add_object", "add_network"]


@_dc.dataclass(frozen=True)
class Chain:
    """A road chain: ``junctions`` ``(lon, lat, level)`` in order, one
    road ``subtype`` (the net's virtual type), straight between them."""

    subtype: int
    junctions: tuple[tuple[float, float, int], ...]


def _last_index(lines: list[str], keyword: str) -> int:
    last = -1
    for i, ln in enumerate(lines):
        if ln.startswith(keyword + " "):
            last = i
    return last


def _defs_end(lines: list[str]) -> int:
    """One past the last ``*_DEF`` row (``PROPERTY`` rows when none)."""
    last = max(_last_index(lines, kw) for kw in
               ("TERRAIN_DEF", "OBJECT_DEF", "POLYGON_DEF", "NETWORK_DEF",
                "RASTER_DEF", "PROPERTY"))
    return last + 1


def add_object(text: str, resource: str, lon: float, lat: float, msl: float,
               heading_deg: float) -> tuple[str, int]:
    """``text`` with ``resource`` declared (appended) and placed once at
    ``msl`` metres; returns ``(text, its definition index)``."""
    lines = text.split("\n")
    n_defs = sum(1 for ln in lines if ln.startswith("OBJECT_DEF "))
    at = _last_index(lines, "OBJECT_DEF")
    if at < 0:
        at = _defs_end(lines) - 1
    lines.insert(at + 1, f"OBJECT_DEF {resource}")
    row = f"OBJECT_MSL {n_defs} {lon:.9f} {lat:.9f} {msl:.4f} {heading_deg:.6f}"
    tail = len(lines)
    while tail > 0 and not lines[tail - 1].strip():
        tail -= 1
    lines.insert(tail, row)
    return "\n".join(lines), n_defs


def add_network(text: str, net_def: str, chains: _t.Sequence[Chain]) -> str:
    """``text`` with ``chains`` appended as segments of ``net_def``.  A
    dump that already declares a different network is refused: one
    ``.net`` per DSF (X-Plane's rule)."""
    lines = text.split("\n")
    nets = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("NETWORK_DEF ")]
    if nets and nets != [net_def]:
        raise ValueError(f"the DSF already uses {nets[0]!r}; one network per DSF")
    if not nets:
        lines.insert(_defs_end(lines), f"NETWORK_DEF {net_def}")
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
