"""THE NETWORK BUFFER READ NEAR ONE SHAPE (#2206): ``face.difference(
lines.buffer(r))`` without buffering the whole network.

A difference reads its second operand only inside the first's envelope
(GEOS clips it there).  :class:`NearBuffer` buffers only the network's
parts (the noded union's components, kept WHOLE and in their order, so
each one's offset curve is the one the whole buffer builds) that reach a
window round the shape, and grows that set until no left-out part comes
within reach of a buffer edge inside the window — so every edge GEOS
reads there, nodes included, is the whole buffer's edge.  HECA's taxi
shoulder join buffered its whole road network once per reach (105 calls,
139 s); this reads a few hundred metres of it.

Exactness is a replay twin, not a proof: the whole buffer's and this
one's differences are compared byte for byte
(``tests/auto_patch_v2/test_near_buffer.py``).  ``geom`` imports nothing of v2.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import MultiLineString
from shapely.strtree import STRtree

__all__ = ["NearBuffer"]

#: metres beyond the reach a left-out part must stand: offset vertices sit
#: at the reach to rounding, arc chords inside it
_SLACK_M = 1.0


class NearBuffer:
    """The noded union ``lines`` (a LineString / MultiLineString), read by
    :meth:`minus` near one shape at a time."""

    def __init__(self, lines) -> None:
        self.parts = np.asarray(shapely.get_parts(lines), dtype=object)
        self.tree = STRtree(self.parts)

    def minus(self, face, reach: float, valid):
        """``face.difference(valid(lines.buffer(reach)))`` read on the
        parts near ``face``.  ``valid`` is the caller's operand repair,
        applied to the buffer as it applied it to the whole one."""
        x0, y0, x1, y1 = face.bounds
        grow = max(x1 - x0, y1 - y0) + _SLACK_M
        window = shapely.box(x0 - grow, y0 - grow, x1 + grow, y1 + grow)
        keep = set(self.tree.query(window, predicate="dwithin",
                                   distance=reach + _SLACK_M).tolist())
        if not keep:            # nothing reaches the window: any far operand
            far = shapely.box(x1 + 3 * grow, y1 + 3 * grow, x1 + 4 * grow, y1 + 4 * grow)
            return face.difference(far)
        while True:
            buf = valid(MultiLineString(list(self.parts[sorted(keep)])).buffer(reach))
            more = self._reaching(buf, window, reach) - keep
            if not more:
                return face.difference(buf)
            keep |= more

    def _reaching(self, buf, window, reach: float) -> set:
        """The parts within reach of an edge of ``buf`` inside ``window``."""
        rings = shapely.get_rings(shapely.get_parts(buf))
        segs = []
        for ring in rings:
            cs = shapely.get_coordinates(ring)
            segs.append(np.stack([cs[:-1], cs[1:]], axis=1))
        if not segs:
            return set()
        segs = np.concatenate(segs)
        lines = shapely.linestrings(segs)
        lines = lines[shapely.intersects(lines, window)]
        if not len(lines):
            return set()
        _src, hit = self.tree.query(lines, predicate="dwithin",
                                    distance=reach + _SLACK_M)
        return set(hit.tolist())
