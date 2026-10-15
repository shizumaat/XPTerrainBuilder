"""The patch editor's edit operations (spec patch-editor-20261015 §3).

Pure functions over a small document type, no I/O: every operation takes a
:class:`PatchDoc` and returns a NEW one (the caller keeps the old one for
undo).  The Qt editor calls these directly; the Mac app's
``SceneryKit/PatchDocument.swift`` implements the same rules, and both run
the shared twin ``tests/fixtures/patch_edit_ops.json`` so they cannot drift.

THE RULES (§3.1-§3.3):

* Operations: :func:`move`, :func:`set_position`, :func:`set_alt`,
  :func:`offset_alt`, :func:`delete_nodes`, :func:`insert_on_edge`.
* Topology (§3.2): a deleted node leaves every way.  After any operation,
  consecutive duplicate refs collapse (cyclically on a closed way, whose
  ``refs`` repeat the first node last); a closed way left with fewer than 3
  distinct nodes, or an open way with fewer than 2, is removed in the same
  step.  Nodes a removed way leaves behind are kept (untouched geometry is
  never changed).
* Snap (§3.3, owner A10): only :func:`move` and :func:`set_position` snap,
  and only the node(s) being moved.  A moved node that ends STRICTLY closer
  than ``min_distinct_spacing_m`` to a node that was not moved merges INTO
  it: the other node survives with its position and elevation, refs are
  replaced, the topology rules apply.  Nearest wins; an exact tie is broken
  by the engine's :func:`survivor_key` (the lowest key survives, as in
  ``merge_sub_spacing``).  Distance is metric on the engine's own local
  plane (``osm_adapter._local_metres``) at the document's ``origin``.
  Nothing else merges — inserts, elevation edits and deletes never do.

The spacing and the identity precision are the law's
(``emit.identity.min_distinct_spacing_m`` / ``coordinate_dp``): ``patch_load``
serves them and :func:`law_identity` reads them; nothing here spells them.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from auto_patch_v2.emit.osm_adapter import _local_metres, survivor_key

__all__ = ["Node", "Way", "PatchDoc", "law_identity", "origin_of",
           "move", "set_position", "set_alt", "offset_alt", "delete_nodes",
           "insert_on_edge", "next_node_id", "apply_op"]


#: One node: ``(id, lat, lon, alt or None)`` — the §2 wire shape.
Node = _t.Tuple[int, float, float, _t.Optional[float]]


@_dc.dataclass(frozen=True)
class Way:
    """A way: its id, its node refs (a closed way repeats the first ref
    last) and its tags, written back unchanged."""

    id: int
    refs: tuple[int, ...]
    tags: _t.Mapping[str, str] = _dc.field(default_factory=dict)

    @property
    def closed(self) -> bool:
        return len(self.refs) >= 2 and self.refs[0] == self.refs[-1]


@_dc.dataclass(frozen=True)
class PatchDoc:
    """The edited patch: nodes keyed by id (insertion order is the file's
    order), ways in file order, and the law's identity frame.

    ``origin`` ``(lat, lon)`` is where the local plane snapping measures in
    is taken: the centre of the bbox of the nodes AS LOADED
    (:func:`origin_of`), fixed for the document's lifetime so an edit never
    moves the frame.
    """

    nodes: _t.Mapping[int, Node]
    ways: tuple[Way, ...]
    min_distinct_spacing_m: float
    identity_dp: int
    origin: tuple[float, float]

    @classmethod
    def from_wire(cls, nodes: _t.Iterable[_t.Sequence], ways: _t.Iterable[_t.Mapping],
                  min_distinct_spacing_m: float, identity_dp: int,
                  origin: _t.Sequence[float] | None = None) -> "PatchDoc":
        """From the §2 wire lists (``[id, lat, lon, alt|null]`` and
        ``{id, refs, tags}``)."""
        table = {int(n[0]): _node(n) for n in nodes}
        doc_ways = tuple(Way(int(w["id"]), tuple(int(r) for r in w["refs"]),
                             dict(w.get("tags") or {})) for w in ways)
        if origin is None:
            origin = origin_of(table.values())
        return cls(table, doc_ways, float(min_distinct_spacing_m),
                   int(identity_dp), (float(origin[0]), float(origin[1])))

    def to_wire(self) -> dict:
        """``{"nodes": [[id, lat, lon, alt|null]…], "ways": [{id, refs,
        tags}…]}`` — the §2 shape ``patch_save`` takes."""
        return {"nodes": [list(n) for n in self.nodes.values()],
                "ways": [{"id": w.id, "refs": list(w.refs), "tags": dict(w.tags)}
                         for w in self.ways]}


def _node(n: _t.Sequence) -> Node:
    alt = n[3] if len(n) > 3 else None
    return (int(n[0]), float(n[1]), float(n[2]),
            None if alt is None else float(alt))


def law_identity() -> tuple[float, int]:
    """``(min_distinct_spacing_m, coordinate_dp)`` from the checked-in law
    table — what ``patch_load`` serves as ``min_distinct_spacing_m`` /
    ``identity_dp``."""
    from auto_patch_v2.law.tables import load_default
    identity = load_default().tables.emit.identity
    return float(identity.min_distinct_spacing_m), int(identity.coordinate_dp)


def origin_of(nodes: _t.Iterable[Node]) -> tuple[float, float]:
    """The centre of the nodes' bbox — ``((min lat + max lat) / 2, (min lon
    + max lon) / 2)``; ``(0, 0)`` for no nodes."""
    nodes = list(nodes)
    if not nodes:
        return (0.0, 0.0)
    lats = [n[1] for n in nodes]
    lons = [n[2] for n in nodes]
    return ((min(lats) + max(lats)) / 2.0, (min(lons) + max(lons)) / 2.0)


# ─── topology (§3.2) ───────────────────────────────────────────────────────

def _tidy(refs: _t.Sequence[int], closed: bool) -> tuple[int, ...] | None:
    """Collapse consecutive duplicates; ``None`` when the way falls below
    3 distinct nodes (closed) or 2 (open)."""
    seq = list(refs[:-1]) if closed else list(refs)
    out: list[int] = []
    for r in seq:
        if not out or out[-1] != r:
            out.append(r)
    if closed:
        while len(out) > 1 and out[-1] == out[0]:
            out.pop()
        if len(set(out)) < 3:
            return None
        return tuple(out + [out[0]])
    if len(set(out)) < 2:
        return None
    return tuple(out)


def _rewrite_ways(ways: _t.Iterable[Way], remap: _t.Mapping[int, int],
                  dropped: _t.AbstractSet[int]) -> tuple[Way, ...]:
    """Replace refs per ``remap``, drop refs in ``dropped``, then apply the
    topology rules to every way that changed."""
    out: list[Way] = []
    for w in ways:
        refs = [remap.get(r, r) for r in w.refs if r not in dropped]
        if tuple(refs) == w.refs:
            out.append(w)
            continue
        closed = w.closed
        if closed and refs and refs[0] != refs[-1]:
            refs.append(refs[0])     # the closing ref itself was dropped
        tidy = _tidy(refs, closed) if refs else None
        if tidy is not None:
            out.append(_dc.replace(w, refs=tidy))
    return tuple(out)


# ─── snap (§3.3) ───────────────────────────────────────────────────────────

def _snap_target(doc: PatchDoc, node: Node, moved: _t.AbstractSet[int]) -> int | None:
    """The non-moved node *node* merges into, or ``None``."""
    m_lat, m_lon = _local_metres(doc.origin)
    best: tuple[float, tuple[float, float], int] | None = None
    for other in doc.nodes.values():
        if other[0] in moved:
            continue
        d = math.hypot((other[1] - node[1]) * m_lat, (other[2] - node[2]) * m_lon)
        if d >= doc.min_distinct_spacing_m:
            continue
        cand = (d, survivor_key((other[1], other[2]), doc.identity_dp), other[0])
        if best is None or cand[:2] < best[:2]:
            best = cand
    return None if best is None else best[2]


def _place(doc: PatchDoc, placed: _t.Mapping[int, tuple[float, float]]) -> PatchDoc:
    """Set the positions in *placed*, then snap each moved node (in the
    order given) onto its nearest non-moved neighbour."""
    nodes = dict(doc.nodes)
    for nid, (lat, lon) in placed.items():
        old = nodes[nid]
        nodes[nid] = (nid, float(lat), float(lon), old[3])
    doc = _dc.replace(doc, nodes=nodes)
    moved = set(placed)
    remap: dict[int, int] = {}
    for nid in placed:
        target = _snap_target(doc, nodes[nid], moved)
        if target is not None:
            remap[nid] = target
    if not remap:
        return doc
    for nid in remap:
        del nodes[nid]
    return _dc.replace(doc, nodes=nodes, ways=_rewrite_ways(doc.ways, remap, set()))


def _known(doc: PatchDoc, ids: _t.Iterable[int]) -> list[int]:
    out = []
    for i in ids:
        i = int(i)
        if i not in doc.nodes:
            raise KeyError(f"node {i} is not in the patch")
        if i not in out:
            out.append(i)
    return out


# ─── operations (§3.1) ─────────────────────────────────────────────────────

def move(doc: PatchDoc, ids: _t.Iterable[int], dlat: float, dlon: float) -> PatchDoc:
    """Move the nodes by ``(dlat, dlon)`` degrees; snaps (§3.3)."""
    ids = _known(doc, ids)
    return _place(doc, {i: (doc.nodes[i][1] + float(dlat), doc.nodes[i][2] + float(dlon))
                        for i in ids})


def set_position(doc: PatchDoc, id: int, lat: float, lon: float) -> PatchDoc:
    """Put one node at ``(lat, lon)``; snaps (§3.3)."""
    (i,) = _known(doc, [id])
    return _place(doc, {i: (float(lat), float(lon))})


def set_alt(doc: PatchDoc, ids: _t.Iterable[int], alt: float | None) -> PatchDoc:
    """Set the nodes' elevation (metres MSL; ``None`` clears it).  Never
    snaps."""
    nodes = dict(doc.nodes)
    for i in _known(doc, ids):
        n = nodes[i]
        nodes[i] = (n[0], n[1], n[2], None if alt is None else float(alt))
    return _dc.replace(doc, nodes=nodes)


def offset_alt(doc: PatchDoc, ids: _t.Iterable[int], d: float) -> PatchDoc:
    """Add ``d`` metres to the nodes' elevation; a node with no elevation
    keeps none.  Never snaps."""
    nodes = dict(doc.nodes)
    for i in _known(doc, ids):
        n = nodes[i]
        if n[3] is not None:
            nodes[i] = (n[0], n[1], n[2], n[3] + float(d))
    return _dc.replace(doc, nodes=nodes)


def delete_nodes(doc: PatchDoc, ids: _t.Iterable[int]) -> PatchDoc:
    """Remove the nodes from the document and from every way (§3.2)."""
    gone = set(_known(doc, ids))
    nodes = {k: v for k, v in doc.nodes.items() if k not in gone}
    return _dc.replace(doc, nodes=nodes, ways=_rewrite_ways(doc.ways, {}, gone))


def next_node_id(doc: PatchDoc) -> int:
    """The id a new node gets: one below the document's minimum id (and
    never above -1 — patch ids are negative)."""
    return min([0, *doc.nodes]) - 1


def insert_on_edge(doc: PatchDoc, a: int, b: int, id: int | None = None) -> PatchDoc:
    """Insert a node at the midpoint of edge ``a``-``b`` — alt the mean of
    the ends, ``None`` if either has none — into EVERY way in which ``a``
    and ``b`` are consecutive in either direction (shared edges stay
    welded).  ``id`` defaults to :func:`next_node_id`.  Never snaps."""
    if int(a) == int(b):
        raise ValueError(f"an edge needs two nodes, got {a} twice")
    a, b = _known(doc, [a, b])
    na, nb = doc.nodes[a], doc.nodes[b]
    new_id = next_node_id(doc) if id is None else int(id)
    if new_id in doc.nodes:
        raise ValueError(f"node {new_id} already exists")
    alt = None if na[3] is None or nb[3] is None else (na[3] + nb[3]) / 2.0
    ways: list[Way] = []
    hit = False
    for w in doc.ways:
        refs: list[int] = []
        for i, r in enumerate(w.refs):
            refs.append(r)
            nxt = w.refs[i + 1] if i + 1 < len(w.refs) else None
            if nxt is not None and {r, nxt} == {a, b}:
                refs.append(new_id)
                hit = True
        ways.append(w if len(refs) == len(w.refs) else _dc.replace(w, refs=tuple(refs)))
    if not hit:
        raise ValueError(f"nodes {a} and {b} are not an edge of any way")
    nodes = dict(doc.nodes)
    nodes[new_id] = (new_id, (na[1] + nb[1]) / 2.0, (na[2] + nb[2]) / 2.0, alt)
    return _dc.replace(doc, nodes=nodes, ways=tuple(ways))


_OPS: dict[str, _t.Callable[..., PatchDoc]] = {
    "move": move, "set_position": set_position, "set_alt": set_alt,
    "offset_alt": offset_alt, "delete_nodes": delete_nodes,
    "insert_on_edge": insert_on_edge,
}


def apply_op(doc: PatchDoc, op: str, args: _t.Mapping[str, _t.Any]) -> PatchDoc:
    """Apply one ``{op, args}`` record (the twin fixture's shape)."""
    try:
        fn = _OPS[op]
    except KeyError:
        raise ValueError(f"unknown edit operation {op!r}") from None
    return fn(doc, **args)
