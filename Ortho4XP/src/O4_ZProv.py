"""THE Z-PROVENANCE LOG of the vector map (#1323, spec
``docs/specs/incremental-patch-edit-spec.md`` §3A.1).

The vector map writes a node's altitude at exactly three sites (spec F10):
``Vector_Map.insert_node`` (the first producer of an (x, y) wins), and the
two crossing sites in ``Vector_Map.insert_edge``, where a crossing node
takes the crossed chain's ``(1 - beta) * z2 + beta * z3``.  The snap to the
9-decimal grid renumbers the nodes and copies each new node's z from the
first old node that lands on it; the hairline weld deletes nodes.  Nothing
in the vector step reads a node's z for anything else.

This log records, in order, only the TAINTED writes: those whose value
comes from a patch node's ``alt_abs`` directly (``base``) or through a
tainted node (``lin``).  Untainted writes cost nothing.  Replaying the log
with the edited patch's ``alt_abs`` values, by the same Python expression
in the same interpreter, gives the z a full vector step would write for
every tainted node, bit for bit; every other node keeps its z.  That is
what lets a height-only patch edit skip the vector step
(``O4_Patch_Fast_Path``).

Events (JSON lists, in order):

- ``["b", node, [patch, osm_node, dtype], value]`` — ``insert_node`` minted
  ``node`` with the patch node's ``alt_abs``, as stored in an array of
  ``dtype`` (the patch way's altitude array) and widened to a double;
- ``["l", node, beta, a, b]`` — a crossing wrote ``(1 - beta) * A +
  beta * B``; ``a`` / ``b`` is ``["n", id]`` for a tainted parent (its
  value at that moment) or ``["v", value]`` for an untainted one;
- ``["c", node]`` — an untainted value overwrote a tainted node;
- ``["d", node]`` — the node was deleted;
- ``["r", [[new, old], ...]]`` — the snap renumbered the nodes: only the
  new nodes whose z came from a tainted old node are listed, and they are
  the tainted set from then on.
"""
from __future__ import annotations

import json
import os

__all__ = ["ZProvLog", "zprov_file", "read_events", "write_events", "replay"]

#: the format of the file; a different one reads as no log
VERSION = 1


def zprov_file(node_file: str) -> str:
    """The log's path beside the vector step's ``.node`` file."""
    stem = node_file[:-5] if node_file.endswith(".node") else node_file
    return stem + ".zprov.json"


class ZProvLog:
    """The recorder ``Vector_Map`` holds (one per map, the only writer)."""

    __slots__ = ("events", "taint")

    def __init__(self) -> None:
        self.events: list = []
        self.taint: set = set()

    def base(self, node: int, src, value) -> None:
        """``node`` was minted with a patch node's ``alt_abs`` (``src``)."""
        self.events.append(["b", node, list(src), float(value)])
        self.taint.add(node)

    def lin(self, node: int, beta, a: int, za, b: int, zb) -> None:
        """A crossing wrote ``(1 - beta) * za + beta * zb`` into ``node``;
        ``za`` / ``zb`` are the values of ``a`` / ``b`` it read."""
        taint = self.taint
        a_tainted = a in taint
        b_tainted = b in taint
        if a_tainted or b_tainted:
            self.events.append([
                "l", node, float(beta),
                ["n", a] if a_tainted else ["v", float(za)],
                ["n", b] if b_tainted else ["v", float(zb)]])
            taint.add(node)
        elif node in taint:
            self.events.append(["c", node])
            taint.discard(node)

    def dead(self, node: int) -> None:
        """``node`` was deleted from the map."""
        if node in self.taint:
            self.events.append(["d", node])
            self.taint.discard(node)

    def renumber(self, pairs) -> None:
        """The snap's ``(new, old)`` pairs whose old node was tainted and
        supplied the new node's z; they become the tainted set."""
        pairs = [[int(new), int(old)] for new, old in pairs]
        if self.events or pairs:
            self.events.append(["r", pairs])
        self.taint = {new for new, _old in pairs}

    def write(self, path: str) -> None:
        """Write the log (temporary file + ``os.replace``)."""
        write_events(path, self.events)


def write_events(path: str, events) -> None:
    """Write a log's events (temporary file + ``os.replace``)."""
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"version": VERSION, "events": events}, handle,
                  separators=(",", ":"))
    os.replace(temporary, path)


def read_events(path: str):
    """The log's events, or ``None`` when it is missing or not readable."""
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("version") != VERSION:
        return None
    return doc.get("events")


def replay(events, base_value) -> dict:
    """``{node: z}`` of every node tainted at the end of the log.

    ``base_value(src, recorded)`` returns the value of a ``base`` event:
    the edited patch's for an edited patch, else ``recorded``.  The crossing
    expression is the one ``Vector_Map.insert_edge`` evaluates, in the same
    order, so the doubles are the same.  Each ``base`` event takes its new
    value IN PLACE, so ``events`` written back is the log a full vector
    step on the edited patch writes."""
    values: dict = {}
    for event in events:
        kind = event[0]
        if kind == "b":
            event[3] = base_value(event[2], event[3])
            values[event[1]] = event[3]
        elif kind == "l":
            (_kind, node, beta, a, b) = event
            za = values[a[1]] if a[0] == "n" else a[1]
            zb = values[b[1]] if b[0] == "n" else b[1]
            values[node] = (1 - beta) * za + beta * zb
        elif kind in ("c", "d"):
            values.pop(event[1], None)
        elif kind == "r":
            values = {new: values[old] for new, old in event[1]}
        else:
            raise ValueError("unknown z-provenance event %r" % (kind,))
    return values
