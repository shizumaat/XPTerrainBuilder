"""THE ROAD NETWORK OF A DSF: its segments, as a DSFTool text dump spells
them (spec ``docs/specs/2123.md`` B1 (c) / B5).

:func:`read_segments` reads every ``BEGIN_SEGMENT`` .. ``END_SEGMENT``
chain of a dump with a point inside a lon/lat box -- its network
definition, subtype and points, the two end junctions carrying their
stacking LEVEL (X-Plane's "0 on the ground, 1, 2 ... for overpasses"),
shape points ``None`` -- and the ``sim/exclude_net`` boxes the dump
declares.  Read by ``planar/road_bridge_pack`` (does the pack already draw
a mapped road bridge?) and by ``tools/drawn_site_roads`` (the roads
X-Plane draws at a site).  Pure: reads one file, writes nothing.
"""
from __future__ import annotations

import re

__all__ = ["read_segments"]

_EXCL = re.compile(r"^PROPERTY\s+sim/exclude_net\s+([-\d.]+)/([-\d.]+)/([-\d.]+)/([-\d.]+)")


def read_segments(text_path: str, box) -> tuple[list, list]:
    """``(segments, exclusion boxes)`` of a DSFTool dump: each segment
    ``(net, subtype, [(lon, lat, level), ...])`` with any point inside
    ``box`` ``(w, s, e, n)``; the boxes ``(w, s, e, n)`` of its
    ``sim/exclude_net`` rows."""
    w, s, e, n = box
    nets, segs, excl = [], [], []
    cur = None
    with open(text_path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if ln.startswith("NETWORK_DEF "):
                nets.append(ln.split(None, 1)[1].strip())
            elif ln.startswith("PROPERTY sim/exclude_net"):
                m = _EXCL.match(ln)
                if m:
                    excl.append(tuple(float(v) for v in m.groups()))
            elif ln.startswith("BEGIN_SEGMENT"):
                t = ln.split()
                cur = (int(t[1]), int(t[2]), [(float(t[4]), float(t[5]), float(t[6]))])
            elif ln.startswith("SHAPE_POINT") and cur is not None:
                t = ln.split()
                cur[2].append((float(t[1]), float(t[2]), None))
            elif ln.startswith("END_SEGMENT") and cur is not None:
                t = ln.split()
                cur[2].append((float(t[2]), float(t[3]), float(t[4])))
                if any(w <= p[0] <= e and s <= p[1] <= n for p in cur[2]):
                    net = nets[cur[0]] if cur[0] < len(nets) else "?"
                    segs.append((net, cur[1], cur[2]))
                cur = None
    return segs, excl
