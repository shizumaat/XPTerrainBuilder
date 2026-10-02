"""Filter local OpenStreetMap extracts into Overpass-equivalent OSM XML.

This module is the filtering half of the OSM regional-extracts feature
(spec: ``docs/specs/osm-regional-extracts-spec.md`` section 5).  Given one
or more local extract files (Geofabrik ``.osm.pbf`` snapshots, or ``.osm`` /
``.osm.bz2`` XML), it reproduces the byte-level result of the Overpass query

    (statement1(bbox); statement2(bbox); ...); (._; >>;); out meta;

so the output can be handed to ``OSM_layer.update_dicosm`` at the single
``get_overpass_data`` call site with no other pipeline change.

Design
------
The Overpass semantics we mirror are:

* **Selection** — an element is selected when its type matches a statement
  prefix (``node`` / ``way`` / ``rel``), its tags match that statement (the
  key is present; the value is equal when the statement carries one; several
  statements are OR-ed), AND its geometry touches the bbox: a node by its own
  coordinates, a way by any of its nodes, a relation by any member node or by
  any member way that itself touches the bbox.
* **Downward closure** (Overpass ``>>``) — every selected relation drags in
  its member ways and member nodes, and every included way drags in all of
  its nodes, *even when those lie outside the bbox*.  Nested relation members
  are ignored, matching the downstream consumer which also ignores
  relation-in-relation members.

Passes and memory discipline
----------------------------
Each extract file is read three times with a light ``osmium.SimpleHandler``.
Only bbox-scoped and closure-scoped identifiers are held in Python; whole
country files are never materialised:

1. selection pass — records which node ids fall inside the bbox, which way
   ids touch it, the ids of directly selected ways/nodes, and the selected
   relations (their members and tags).  Because OSM files stream nodes, then
   ways, then relations, membership of earlier types is already known when a
   later type is examined.
2. way-gather pass — for every needed way (selected or pulled in by a
   relation) stores its node refs and tags, and grows the needed-node set.
3. node-gather pass — for every needed node stores its coordinates and tags.

Node coordinates are read straight off the node objects, so no on-disk node
location index is required.

Missing referenced nodes
------------------------
``OSM_layer.update_dicosm`` resolves each ``<nd ref=...>`` through a strict
dictionary lookup and raises if the node was never emitted.  A way whose
nodes are not all present in its extract file is therefore DROPPED rather
than emitted with dangling refs (Geofabrik's complete-ways extracts make
this vanishingly rare).  Relation members that point at a dropped or absent
way are left in place: the consumer tolerates missing way members.

Elements are deduplicated by ``(type, id)`` across the extract files, first
file wins.
"""

from __future__ import annotations

import errno
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import osmium

import O4_External_Writes as EXTWRITE


class ExtractFilterError(Exception):
    """An extract file could not be read or filtered."""


# ---------------------------------------------------------------------------
# WHERE A CUTTER'S TEMPORARY LIVES (#159)
# ---------------------------------------------------------------------------
# Every cutter here writes its output to a temporary and then moves it into
# place, so a crashed cut can never leave a plausible-looking clip.  Until
# 2026-10-02 that temporary was cut BESIDE THE DESTINATION — i.e. inside the
# shared data repo, which is where the clip cache lives — and NEITHER writer
# passes the harness's Python-level write guard: ``osmium extract`` is a
# CHILD PROCESS and ``osmium.SimpleWriter`` is a C extension holding its own
# file handle.  Lane tx154 measured the consequence: a 10.5 MB
# ``clip_+030-0095_….tmp-52850-….osm.pbf`` landed in the shared
# ``OSM_data/_regional_extracts/clips/`` with the guard armed, and the
# Python ``os.remove`` that would have cleaned it up was then the ONLY call
# the guard saw — so it refused the cleanup and kept the 10.5 MB.  Eight
# older strays (2026-08-11 … 09-01, ~100 MB) show the hole predates it.
#
# So the temporary goes under a LANE-LOCAL scratch directory (the engine's
# own ``tmp`` product dir) and only the FINAL MOVE targets the destination.
# That move is ``os.replace``, which IS a Python call, so an armed guard
# refuses it at the call and an armed run leaves ZERO files in the shared
# clips directory.  Belt to that brace: the osmium launcher DECLARES its
# output path before it spawns (``O4_External_Writes``), so under an armed
# guard the child is never started at all.

#: Scratch directory name prefix for one cut's temporaries.  A whole
#: directory, not a sibling file: the parts of a multi-extract cut then
#: share one tree that a single ``rmtree`` removes on every exit path.
_CUT_SCRATCH_PREFIX = "o4_osm_clip_cut-"

#: Basename of the cut's stderr capture inside the scratch directory.
_CUT_STDERR_NAME = "osmium.stderr"

#: How a cut part is named inside the scratch directory.  The suffix must
#: stay format-recognizable: both writers infer the format from the name.
_CUT_PART_TEMPLATE = "part%d.osm.pbf"

#: How the IN-PROCESS C-extension writer is NAMED when its destination is
#: declared to an armed shared-repo write guard (#159).  It is not a child
#: process, but it is the same blindness: ``osmium.SimpleWriter`` holds its
#: own file handle, so no patched ``builtins.open`` ever sees its bytes —
#: the GDAL class of RULINGS 2026-09-30bw.
_PYOSMIUM_WRITER_NAME = "osmium.SimpleWriter"


def _engine_temporary_root() -> Optional[str]:
    """The engine's own lane-local ``tmp`` product directory, or ``None``.

    Asked at call time, never cached: ``O4_File_Names.Tmp_dir`` is empty
    until ``_apply_data_root`` runs and a lane may re-root mid-process.
    The import is guarded because this module is also loaded standalone by
    its own tests and by ``auto_patch_v2``'s OSM adapter.
    """
    try:
        import O4_File_Names as FNAMES
    except Exception:
        return None
    root = getattr(FNAMES, "Tmp_dir", "") or ""
    if not root:
        return None
    try:
        os.makedirs(root, exist_ok=True)
    except OSError:
        return None
    return root if os.path.isdir(root) else None


def _make_cut_scratch(temporary_directory: Optional[str] = None) -> str:
    """A fresh scratch directory for one cut's temporaries.

    ``temporary_directory`` names the root explicitly (the twins pass a
    ``tmp_path``); otherwise the engine's lane-local ``tmp`` dir, and the
    platform temp dir when the engine has no data root yet.  NEVER the
    destination's directory — that is the whole point (see the section
    comment above).
    """
    root = temporary_directory or _engine_temporary_root()
    try:
        if root:
            os.makedirs(root, exist_ok=True)
        return tempfile.mkdtemp(prefix=_CUT_SCRATCH_PREFIX, dir=root or None)
    except OSError as e:
        raise ExtractFilterError(
            "could not create a clip-cut scratch directory under "
            + str(root or tempfile.gettempdir()) + ": " + str(e)) from e


def _discard_cut_scratch(scratch: Optional[str]) -> None:
    """Remove a scratch directory and everything in it, never raising."""
    if scratch:
        shutil.rmtree(scratch, ignore_errors=True)


# --- WHY THE REPLACE RETRIES ON WINDOWS (#205) -----------------------------
#
# POSIX ``rename`` replaces a destination even while another process holds
# it open.  Windows ``MoveFileEx(..., MOVEFILE_REPLACE_EXISTING)`` does not:
# it fails with ERROR_ACCESS_DENIED (5) or ERROR_SHARING_VIOLATION (32) when
# the destination has an open handle.  Two cutters racing the same clip both
# stage to a thread-unique name (correct, and what the #159-era work fixed)
# and then both replace onto the SAME destination, so the loser can meet a
# destination that is momentarily held — by the winner's own just-closed
# write or its cleanup, or by the scanner/indexer Windows runs over a freshly
# created file.  Neither holder lasts: the condition is transient by nature,
# so the remedy is a bounded retry around the one move site, and each attempt
# is still ONE atomic replace, so the guarantee the 2026-07-23 field failure
# bought is unchanged.
#
# Measured as the single windows-latest failure of PR #202 (run 36974952001):
# ``[WinError 5] Access is denied: 'clip.osm.pbf.tmp-600-1304.osm.pbf' ->
# 'clip.osm.pbf'`` — the EXDEV staging move, because a GitHub Windows runner
# has the workspace on ``D:`` and ``TEMP`` on ``C:``.  The same class reaches
# users: any Windows machine whose scenery lives on a different drive from
# ``TEMP`` takes the cross-volume branch on EVERY cut.
#
# NOT attempted here, and REPORTED rather than decided (#205): making
# ``_make_cut_scratch`` prefer a scratch root on the DESTINATION's volume so
# the cross-volume branch is not the Windows default at all.  The section
# comment above deliberately forbids the destination's own directory for the
# shared-repo-guard reason, so "same volume, not same directory" is a
# guard-law question for the owner, not a free change.

#: Windows error codes for "the destination is held by someone else".  Both
#: are transient; neither says the move is wrong.
_WINDOWS_HELD_DESTINATION_ERRORS = (5, 32)
#: Attempts at the atomic replace, the first one included.
_REPLACE_ATTEMPTS = 6
#: Backoff before the second attempt, doubling up to the cap: the whole
#: bound is 0.05 + 0.1 + 0.2 + 0.4 + 0.8 = 1.55 s, a holder's lifetime and
#: nothing like the minutes of osmium work the move would throw away.
_REPLACE_FIRST_BACKOFF_S = 0.05
_REPLACE_MAX_BACKOFF_S = 0.8
#: Only Windows can refuse a replace for a held destination, so only there
#: is a retry anything but a swallowed error.  A module-level flag, not an
#: inline ``sys.platform`` test, so the twins can exercise the Windows path
#: on the runner they have.
_RETRY_HELD_DESTINATION = sys.platform == "win32"


def _replace_retrying_a_held_destination(source: str, destination: str) -> None:
    """``os.replace(source, destination)``, retrying a HELD destination.

    Windows only (see the section comment above): a replace that fails
    because the destination has an open handle is retried with a bounded,
    doubling backoff and then raised.  Every other failure — EXDEV, a
    missing source, a shared-repo write guard's refusal — raises on the
    FIRST attempt, unchanged: a retry loop must never wait out a refusal.
    """
    backoff = _REPLACE_FIRST_BACKOFF_S
    for attempt in range(1, _REPLACE_ATTEMPTS + 1):
        try:
            os.replace(source, destination)
            return
        except OSError as e:
            held = getattr(e, "winerror", None) in (
                _WINDOWS_HELD_DESTINATION_ERRORS)
            if (not _RETRY_HELD_DESTINATION or not held
                    or attempt == _REPLACE_ATTEMPTS):
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, _REPLACE_MAX_BACKOFF_S)


def _move_into_place(temporary_path: str, output_path: str) -> None:
    """Move a finished cut onto its destination, atomically where it can.

    ``os.replace`` is atomic and is a PYTHON call, so an armed shared-repo
    write guard refuses it here — which is exactly what must happen when
    the destination is the shared corpus and nothing authorised the write.

    Across filesystems ``os.replace`` cannot work (``EXDEV``), so the data
    is copied through a temporary IN THE DESTINATION DIRECTORY and the last
    step is still an atomic replace.  That copy's ``open(..., "wb")`` is a
    Python write too, so the guard refuses it the same way; and the
    temporary is removed on every exit path.

    Both replaces go through :func:`_replace_retrying_a_held_destination`,
    which on Windows alone retries the one failure concurrent cutters
    cause (#205).
    """
    try:
        _replace_retrying_a_held_destination(temporary_path, output_path)
        return
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
    staged = "%s.tmp-%d-%d.osm.pbf" % (
        output_path, os.getpid(), threading.get_ident())
    try:
        shutil.copyfile(temporary_path, staged)
        _replace_retrying_a_held_destination(staged, output_path)
    finally:
        for leftover in (staged, temporary_path):
            try:
                os.remove(leftover)
            except OSError:
                pass


# A tag matcher is ``(key, value_or_None)``: value None means key-existence.
_Matcher = Tuple[str, Optional[str]]
_Matchers = Dict[str, List[_Matcher]]

# Local per-file collections handed to the serializer.
_NodeData = Tuple[float, float, List[Tuple[str, str]]]  # (lat, lon, tags)
_WayData = Tuple[List[int], List[Tuple[str, str]]]  # (node refs, tags)
_RelData = Tuple[List[Tuple[str, int, str]], List[Tuple[str, str]]]  # (members, tags)


def _parse_statements(statements: Iterable[str]) -> _Matchers:
    """Turn Overpass statement strings into per-type tag matchers.

    Parses exactly the way ``O4_OSM_Utils`` does: ``statement.split('"')``
    yields ``items``; ``items[0]`` prefixes the element type, ``items[1]`` is
    the key, and ``items[3]`` (when present) is the required value.  A
    statement without a value part is a key-existence match.
    """
    matchers: _Matchers = {"node": [], "way": [], "relation": []}
    for statement in statements:
        items = statement.split('"')
        prefix = items[0]
        if prefix.startswith("node"):
            osmtype = "node"
        elif prefix.startswith("way"):
            osmtype = "way"
        elif prefix.startswith("rel"):
            osmtype = "relation"
        else:
            # Unrecognised prefix: skip rather than guess.
            continue
        key = items[1]
        value = items[3] if len(items) > 3 else None
        matchers[osmtype].append((key, value))
    return matchers


_BoundingBox = Tuple[float, float, float, float]  # (lat_min, lon_min, lat_max, lon_max)


def _normalize_bounding_boxes(bounding_box) -> List[_BoundingBox]:
    """Accept one ``(lat_min, lon_min, lat_max, lon_max)`` box or a list
    of them; always return a list.

    The multi-box form exists because the osmium passes read the WHOLE
    extract file regardless of box size — one pass selecting against N
    boxes costs the same as one pass against one box, while N separate
    calls cost N full reads.  Callers with several disjoint areas (the
    per-airport inset footprint queries) pass the list; a single bounding
    RECTANGLE over disjoint areas would be wrong, sweeping up everything
    between them.
    """
    boxes = list(bounding_box)
    if not boxes:
        return []
    # Multi-box form: the first element is itself a box (a sequence),
    # not a coordinate scalar.  Sequence detection (rather than scalar
    # type checks) keeps numpy scalar coordinates classified correctly.
    if isinstance(boxes[0], (tuple, list)):
        return [tuple(float(value) for value in box) for box in boxes]
    if len(boxes) != 4:
        raise ExtractFilterError(
            "bounding_box must be a 4-tuple or a list of 4-tuples"
        )
    return [tuple(float(value) for value in boxes)]


def _tags_match(tags: "osmium.osm.TagList", matchers: List[_Matcher]) -> bool:
    """True when any matcher's key is present (and its value equals, when
    the matcher carries one).  The ``("*", None)`` matcher matches every
    element — the clip builder's tag-agnostic selection."""
    for key, value in matchers:
        if key == "*":
            return True
        actual = tags.get(key)
        if actual is None:
            continue
        if value is None or actual == value:
            return True
    return False


class _SelectionHandler(osmium.SimpleHandler):
    """Pass 1 — decide selected elements and seed the closure sets."""

    def __init__(self, matchers: _Matchers, bounding_boxes: List[_BoundingBox]):
        super().__init__()
        self._matchers = matchers
        self._boxes = list(bounding_boxes)
        # The node callback below runs once per node in the extract —
        # tens of millions of calls for a country pbf, the cut's wall-
        # time floor.  The common single-box case keeps its bounds in
        # locals-friendly scalars so the test is inline compares, not a
        # method call per node.
        self._single_box = self._boxes[0] if len(self._boxes) == 1 else None
        # Shared state consumed by later passes.
        self.nodes_in_bbox: set = set()
        self.ways_touching: set = set()
        self.needed_way_ids: set = set()
        self.needed_node_ids: set = set()
        self.selected_rels: Dict[int, _RelData] = {}

    def _in_bbox(self, lat: float, lon: float) -> bool:
        for (lat_min, lon_min, lat_max, lon_max) in self._boxes:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return True
        return False

    def node(self, n: "osmium.osm.Node") -> None:
        loc = n.location
        single = self._single_box
        if single is not None:
            if not (single[0] <= loc.lat <= single[2]
                    and single[1] <= loc.lon <= single[3]):
                return
        elif not self._in_bbox(loc.lat, loc.lon):
            return
        self.nodes_in_bbox.add(n.id)
        if _tags_match(n.tags, self._matchers["node"]):
            # A directly selected node is its own closure.
            self.needed_node_ids.add(n.id)

    def way(self, w: "osmium.osm.Way") -> None:
        refs = [nd.ref for nd in w.nodes]
        if not any(ref in self.nodes_in_bbox for ref in refs):
            return
        self.ways_touching.add(w.id)
        if _tags_match(w.tags, self._matchers["way"]):
            self.needed_way_ids.add(w.id)

    def relation(self, r: "osmium.osm.Relation") -> None:
        touches = False
        way_member_refs: List[int] = []
        node_member_refs: List[int] = []
        for m in r.members:
            if m.type == "n":
                node_member_refs.append(m.ref)
                if m.ref in self.nodes_in_bbox:
                    touches = True
            elif m.type == "w":
                way_member_refs.append(m.ref)
                if m.ref in self.ways_touching:
                    touches = True
        if not (touches and _tags_match(r.tags, self._matchers["relation"])):
            return
        members = [(m.type, m.ref, m.role) for m in r.members]
        tags = [(t.k, t.v) for t in r.tags]
        self.selected_rels[r.id] = (members, tags)
        # Downward closure of the relation: its member ways and member nodes.
        self.needed_way_ids.update(way_member_refs)
        self.needed_node_ids.update(node_member_refs)


class _WayGatherHandler(osmium.SimpleHandler):
    """Pass 2 — collect the geometry/tags of every needed way and grow the
    needed-node set with those ways' nodes."""

    def __init__(self, needed_way_ids: set, needed_node_ids: set):
        super().__init__()
        self._needed_way_ids = needed_way_ids
        self._needed_node_ids = needed_node_ids
        self.ways: Dict[int, _WayData] = {}

    def way(self, w: "osmium.osm.Way") -> None:
        if w.id not in self._needed_way_ids:
            return
        refs = [nd.ref for nd in w.nodes]
        tags = [(t.k, t.v) for t in w.tags]
        self.ways[w.id] = (refs, tags)
        self._needed_node_ids.update(refs)


class _NodeGatherHandler(osmium.SimpleHandler):
    """Pass 3 — collect the coordinates/tags of every needed node."""

    def __init__(self, needed_node_ids: set):
        super().__init__()
        self._needed_node_ids = needed_node_ids
        self.nodes: Dict[int, _NodeData] = {}

    def node(self, n: "osmium.osm.Node") -> None:
        if n.id not in self._needed_node_ids:
            return
        loc = n.location
        tags = [(t.k, t.v) for t in n.tags]
        self.nodes[n.id] = (loc.lat, loc.lon, tags)


def _gather_ways_prefiltered(path, needed_way_ids, needed_node_ids):
    """Pass 2 with the id membership test in C++ (osmium.filter.IdFilter):
    only the needed ways ever reach Python.  Against the plain handler —
    one Python callback per way in the file — this removes millions of
    calls whose only work was a set lookup."""
    ways: Dict[int, _WayData] = {}
    if not needed_way_ids:
        return ways
    processor = osmium.FileProcessor(path, osmium.osm.WAY).with_filter(
        osmium.filter.IdFilter(needed_way_ids)
    )
    for w in processor:
        refs = [nd.ref for nd in w.nodes]
        ways[w.id] = (refs, [(t.k, t.v) for t in w.tags])
        needed_node_ids.update(refs)
    return ways


def _gather_nodes_prefiltered(path, needed_node_ids):
    """Pass 3 with the id membership test in C++ (see pass 2 above) —
    the extract's full node table (tens of millions for a country
    extract) stays on the C++ side; Python sees only the closure."""
    nodes: Dict[int, _NodeData] = {}
    if not needed_node_ids:
        return nodes
    processor = osmium.FileProcessor(path, osmium.osm.NODE).with_filter(
        osmium.filter.IdFilter(needed_node_ids)
    )
    for n in processor:
        location = n.location
        nodes[n.id] = (location.lat, location.lon, [(t.k, t.v) for t in n.tags])
    return nodes


# The C++-side prefilters need pyosmium >= 4 (FileProcessor + IdFilter);
# the handler classes above remain the fallback so an older runtime is
# slower, never broken.
_HAS_PREFILTERS = hasattr(osmium, "FileProcessor") and hasattr(
    getattr(osmium, "filter", None), "IdFilter"
)


def _process_extract(
    path: str,
    matchers: _Matchers,
    bounding_boxes: List[_BoundingBox],
) -> Tuple[Dict[int, _NodeData], Dict[int, _WayData], Dict[int, _RelData]]:
    """Run the three passes over one extract file and return its selected +
    closure nodes, ways and relations.  Ways whose nodes are not all present
    in the file are dropped."""
    if not os.path.isfile(path):
        raise ExtractFilterError("extract file not found: " + str(path))
    try:
        selection = _SelectionHandler(matchers, bounding_boxes)
        selection.apply_file(path)

        if _HAS_PREFILTERS:
            gathered_ways = _gather_ways_prefiltered(
                path, selection.needed_way_ids, selection.needed_node_ids
            )
            nodes = _gather_nodes_prefiltered(
                path, selection.needed_node_ids
            )
        else:
            way_gather = _WayGatherHandler(
                selection.needed_way_ids, selection.needed_node_ids
            )
            way_gather.apply_file(path)
            gathered_ways = way_gather.ways

            node_gather = _NodeGatherHandler(selection.needed_node_ids)
            node_gather.apply_file(path)
            nodes = node_gather.nodes
    except ExtractFilterError:
        raise
    except Exception as e:  # osmium raises RuntimeError on unreadable/corrupt input
        raise ExtractFilterError(
            "could not read extract " + str(path) + ": " + str(e)
        ) from e

    ways = {
        wid: data
        for wid, data in gathered_ways.items()
        if all(ref in nodes for ref in data[0])
    }
    return nodes, ways, selection.selected_rels


def _xml_escape(text: str) -> str:
    """Escape a string for an XML attribute value.  Newlines/tabs are turned
    into numeric entities as well, so that the line-oriented consumer parser
    never sees a tag value split across lines."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
        .replace("\t", "&#9;")
    )


def _serialize(
    nodes: Dict[int, _NodeData],
    ways: Dict[int, _WayData],
    rels: Dict[int, _RelData],
) -> bytes:
    """Emit nodes, then ways, then relations as Overpass-style OSM XML.

    Every element carries ``version="1"`` (harmless, mirrors ``out meta``).
    Each element and each child sits on its own line so the consumer's
    line-by-line, quote-splitting parser reads them exactly as it reads an
    Overpass response.
    """
    out: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<osm version="0.6" generator="Ortho4XP-regional-extract-filter">\n',
    ]

    def emit_tags(tags: List[Tuple[str, str]]) -> None:
        for key, value in tags:
            out.append(
                '    <tag k="'
                + _xml_escape(key)
                + '" v="'
                + _xml_escape(value)
                + '"/>\n'
            )

    for node_id in sorted(nodes):
        lat, lon, tags = nodes[node_id]
        head = (
            '  <node id="'
            + str(node_id)
            + '" lat="'
            + "{:.7f}".format(lat)
            + '" lon="'
            + "{:.7f}".format(lon)
            + '" version="1"'
        )
        if tags:
            out.append(head + ">\n")
            emit_tags(tags)
            out.append("  </node>\n")
        else:
            out.append(head + "/>\n")

    for way_id in sorted(ways):
        refs, tags = ways[way_id]
        out.append('  <way id="' + str(way_id) + '" version="1">\n')
        for ref in refs:
            out.append('    <nd ref="' + str(ref) + '"/>\n')
        emit_tags(tags)
        out.append("  </way>\n")

    for rel_id in sorted(rels):
        members, tags = rels[rel_id]
        out.append('  <relation id="' + str(rel_id) + '" version="1">\n')
        for mtype, ref, role in members:
            # osmium member types are single chars; the consumer expects the
            # long form ("way"/"node"/"relation").
            long_type = {"n": "node", "w": "way", "r": "relation"}.get(mtype, mtype)
            out.append(
                '    <member type="'
                + long_type
                + '" ref="'
                + str(ref)
                + '" role="'
                + _xml_escape(role)
                + '"/>\n'
            )
        emit_tags(tags)
        out.append("  </relation>\n")

    out.append("</osm>")
    return "".join(out).encode("utf-8")


def filter_extracts_to_osm_xml(
    extract_paths: Iterable[str],
    statements: Iterable[str],
    bounding_box: Tuple[float, float, float, float],
) -> bytes:
    """OSM XML bytes reproducing Overpass union + deep-recursion semantics.

    extract_paths: iterable of local extract file paths (.osm.pbf, .osm,
        .osm.bz2).
    statements: iterable of Overpass statement strings exactly as used in
        O4_Vector_Map, e.g. ``way["natural"="water"]``,
        ``rel["waterway"="riverbank"]``, ``node["aeroway"]`` (value part
        optional -> key-existence match).
    bounding_box: ``(lat_min, lon_min, lat_max, lon_max)`` in degrees, or
        a LIST of such boxes — one filtering pass then selects elements
        inside ANY of the boxes (see :func:`_normalize_bounding_boxes` for
        why that beats one call per box).

    Returns utf-8 XML bytes: an ``<osm version="0.6" generator="...">``
    document containing nodes first, then ways, then relations, with the full
    downward closure of every selected element.  Elements are deduplicated by
    ``(type, id)`` across the extract files, first file wins.  Ways whose
    nodes are not all present in their extract are dropped (see module
    docstring).  Raises ExtractFilterError when an extract file is
    missing/unreadable.
    """
    matchers = _parse_statements(statements)
    bounding_boxes = _normalize_bounding_boxes(bounding_box)
    merged_nodes, merged_ways, merged_rels = _merge_extracts(
        extract_paths, matchers, bounding_boxes)
    return _serialize(merged_nodes, merged_ways, merged_rels)


def _merge_extracts(extract_paths, matchers, bounding_boxes):
    """Three-pass filter every extract and merge, first file wins."""
    merged_nodes: Dict[int, _NodeData] = {}
    merged_ways: Dict[int, _WayData] = {}
    merged_rels: Dict[int, _RelData] = {}
    for path in extract_paths:
        nodes, ways, rels = _process_extract(path, matchers, bounding_boxes)
        for node_id, data in nodes.items():
            merged_nodes.setdefault(node_id, data)
        for way_id, data in ways.items():
            merged_ways.setdefault(way_id, data)
        for rel_id, data in rels.items():
            merged_rels.setdefault(rel_id, data)
    return merged_nodes, merged_ways, merged_rels


# Tag-agnostic matchers: select EVERYTHING touching the bbox, with full
# closure — the superset any statement query over a sub-box can need.
_MATCH_ALL: _Matchers = {
    "node": [("*", None)],
    "way": [("*", None)],
    "relation": [("*", None)],
}


def clip_extracts_to_pbf(
    extract_paths: Iterable[str],
    bounding_box,
    output_path: str,
    temporary_directory: Optional[str] = None,
) -> None:
    """Write a merged, bbox-clipped extract covering every element any
    statement query over a sub-box of ``bounding_box`` could select.

    The clip applies the same selection semantics as a query — bbox touch
    plus full downward closure — but tag-agnostically, so filtering the
    clip with any statements and any bbox INSIDE the clip box is
    byte-identical to filtering the original extracts (selection there
    only ever needs elements the clip retained).  Serving the repeated
    per-tile query rounds (water, roads, airports, ...) from a clip a few
    MB in size replaces re-decoding hundreds of MB of country pbf per
    round.

    Memory note: the clip transiently holds the whole area's elements in
    Python dicts — a dense metropolitan 1° tile can reach a couple of GB;
    comparable to the mesh step's own peak and released immediately.

    Raises ExtractFilterError on any read/write failure; the scratch
    directory is removed and ``output_path`` is only ever replaced
    atomically.

    temporary_directory: root for the cut's scratch directory, which is
        where the temporary is written before the atomic move onto
        ``output_path`` (#159 — never beside the destination, which may be
        the shared corpus).  Default: the engine's lane-local ``tmp``
        product directory, or the platform temp dir when the engine has no
        data root yet.
    """
    # THE DESTINATION IS DECLARED BEFORE ANY WORK (#159 bar 2).  The cut is
    # the expensive part — a whole-country extract read — and there is no
    # point paying it for an output an armed shared-repo write guard will
    # refuse to let land.  Declaring here means the refusal arrives before
    # the read, before the scratch, and before any child process exists.
    EXTWRITE.declare_external_write(output_path,
                                    writer=_PYOSMIUM_WRITER_NAME)
    bounding_boxes = _normalize_bounding_boxes(bounding_box)
    nodes, ways, rels = _merge_extracts(
        extract_paths, _MATCH_ALL, bounding_boxes)
    # LANE-LOCAL SCRATCH, not a sibling of the destination (#159): the
    # writer below is ``osmium.SimpleWriter``, a C extension holding its
    # own file handle, so a temporary cut beside an output in the shared
    # corpus is a C-level corpus write no Python guard can see.  The
    # scratch dir is fresh per cut, so the old per-pid-and-thread unique
    # name is no longer load-bearing either.
    scratch = _make_cut_scratch(temporary_directory)
    temporary_path = os.path.join(scratch, _CUT_PART_TEMPLATE % 0)
    try:
        writer = osmium.SimpleWriter(temporary_path)
        try:
            # Stream order nodes -> ways -> relations: the selection
            # handler relies on it exactly as with Geofabrik files.
            for node_id in sorted(nodes):
                lat, lon, tags = nodes[node_id]
                writer.add_node(osmium.osm.mutable.Node(
                    id=node_id, location=(lon, lat), tags=tags))
            for way_id in sorted(ways):
                refs, tags = ways[way_id]
                writer.add_way(osmium.osm.mutable.Way(
                    id=way_id, nodes=refs, tags=tags))
            for rel_id in sorted(rels):
                members, tags = rels[rel_id]
                writer.add_relation(osmium.osm.mutable.Relation(
                    id=rel_id, members=members, tags=tags))
        finally:
            writer.close()
        _move_into_place(temporary_path, output_path)
    except ExtractFilterError:
        raise
    except Exception as e:
        raise ExtractFilterError(
            "could not write clip " + str(output_path) + ": " + str(e)
        ) from e
    finally:
        _discard_cut_scratch(scratch)


# ---------------------------------------------------------------------------
# Clip cutting via osmium-tool (optional C++ fast path)
# ---------------------------------------------------------------------------
# ``osmium extract --strategy smart --option types=any`` retains, for a
# region box: every node in the box; every way with a node in the box,
# made reference-complete; and every relation directly referencing any
# of those nodes or ways, with ALL member nodes and ways (and those
# ways' nodes).  That is a superset of what :func:`clip_extracts_to_pbf`
# keeps — the extras are parent relations pulled in recursively, which
# re-filtering can never select (a relation is only selected through
# its own member geometry).  Filtering an osmium-cut clip is therefore
# byte-identical to filtering the original extract; the tests assert
# exactly that.  The default ``complete_ways`` strategy would NOT be
# equivalent: it leaves a selected relation's outside member ways
# behind, breaking the downward-closure half of the clip contract.
# Measured on gcc-states.osm.pbf (250 MB, a 1.1x1.1 degree box,
# 2026-07-23): osmium extract 0.9 s wall against 90.1 s for the
# pyosmium cutter above — and filtering either clip gave bytes
# identical to filtering the full extract (sha-verified, an 11-
# statement production-shaped query).
#
# Multiple extracts are deliberately NOT combined with ``osmium
# merge``: two Geofabrik snapshots taken on different days can carry
# different versions of a shared border object, and merge keeps both
# versions, while this module's contract is first-file-wins.  Instead
# each extract is osmium-cut on its own — that is the expensive
# whole-file read — and the small per-region clips are merged by
# :func:`clip_extracts_to_pbf`, whose merge rule IS the contract.

_OSMIUM_POLL_SECONDS = 0.5

#: How the osmium child is NAMED when its output path is declared to an
#: armed shared-repo write guard (#159), and therefore in the refusal and
#: in the swallowed-refusal report: "a subprocess" is not an answer a lane
#: can act on.
_OSMIUM_WRITER_NAME = "osmium"


def _run_osmium_extract(
    osmium_binary: str,
    source_path: str,
    bbox_argument: str,
    output_path: str,
    stderr_path: str,
    should_stop: Optional[Callable[[], bool]],
    spawn_kwargs: Optional[dict],
) -> None:
    """One ``osmium extract`` run, waited on with ``should_stop`` polls.

    stderr goes to a file rather than a pipe so the wait loop can never
    deadlock on a full pipe buffer; its tail is read back for the error
    message on a non-zero exit."""
    if should_stop is not None and should_stop():
        raise ExtractFilterError("clip cutting stopped")
    # A SPAWN IS A WRITE DECLARATION (#159).  Both paths are lane-local by
    # construction now, so under an armed guard this refuses NOTHING; it is
    # here so that a future caller passing a corpus path never gets to
    # spawn a child the guard cannot see.  The refusal is the harness's own
    # and is RECORDED, so swallowing it fails the run.
    EXTWRITE.declare_external_writes(
        (output_path, stderr_path), writer=_OSMIUM_WRITER_NAME)
    command = [
        osmium_binary, "extract",
        "--strategy", "smart", "--option", "types=any",
        "--bbox", bbox_argument,
        "--no-progress", "--overwrite",
        "--output", output_path,
        source_path,
    ]
    try:
        with open(stderr_path, "wb") as stderr_file:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                **(spawn_kwargs or {}),
            )
    except Exception as e:
        raise ExtractFilterError(
            "could not run osmium-tool (" + str(osmium_binary) + "): "
            + str(e)
        ) from e
    while True:
        try:
            returncode = process.wait(timeout=_OSMIUM_POLL_SECONDS)
            break
        except subprocess.TimeoutExpired:
            if should_stop is None or not should_stop():
                continue
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise ExtractFilterError("clip cutting stopped")
    if returncode != 0:
        tail = ""
        try:
            with open(stderr_path, "rb") as stderr_file:
                tail = stderr_file.read()[-500:] \
                    .decode("utf-8", "replace").strip()
        except OSError:
            pass
        raise ExtractFilterError(
            "osmium extract failed (exit %d)%s"
            % (returncode, ": " + tail if tail else "")
        )


def cut_clip_with_osmium(
    extract_paths: Iterable[str],
    bounding_box,
    output_path: str,
    osmium_binary: str,
    should_stop: Optional[Callable[[], bool]] = None,
    spawn_kwargs: Optional[dict] = None,
    temporary_directory: Optional[str] = None,
) -> None:
    """:func:`clip_extracts_to_pbf` semantics, cut by osmium-tool.

    Same contract as the pyosmium cutter — filtering the result with any
    statements and any bbox inside ``bounding_box`` is byte-identical to
    filtering the original extracts — at C++ single-pass speed (see the
    section comment above for why ``smart``/``types=any`` guarantees
    this and why multiple extracts are cut separately then merged by the
    pyosmium cutter).

    extract_paths: local extract files, first-file-wins order.
    bounding_box: ONE ``(lat_min, lon_min, lat_max, lon_max)`` box (the
        clip cache is always cut for a single padded area box).
    osmium_binary: path of the osmium-tool executable to run.
    should_stop: optional zero-argument callable polled while osmium
        runs; returning True terminates the child and raises.
    spawn_kwargs: optional extra ``subprocess.Popen`` keyword arguments
        (the engine passes its posix-spawn-preserving set, see
        ``O4_UI_Utils.external_tool_keyword_arguments``).

    Raises ExtractFilterError on any failure, stop request included;
    ``output_path`` is only ever replaced atomically and temporaries are
    removed on every path.

    temporary_directory: root for the cut's scratch directory, which is
        where the temporary is written before the atomic move onto
        ``output_path`` (#159 — never beside the destination, which may be
        the shared corpus).  Default: the engine's lane-local ``tmp``
        product directory, or the platform temp dir when the engine has no
        data root yet.
    """
    boxes = _normalize_bounding_boxes(bounding_box)
    if len(boxes) != 1:
        raise ExtractFilterError(
            "osmium clip cutting expects a single clip box"
        )
    (lat_min, lon_min, lat_max, lon_max) = boxes[0]
    bbox_argument = "%.7f,%.7f,%.7f,%.7f" % (
        lon_min, lat_min, lon_max, lat_max)
    paths = [str(path) for path in extract_paths]
    for path in paths:
        if not os.path.isfile(path):
            raise ExtractFilterError("extract file not found: " + path)
    # THE DESTINATION IS DECLARED BEFORE ANY WORK (#159 bar 2).  The cut is
    # the expensive part — a whole-country extract read — and there is no
    # point paying it for an output an armed shared-repo write guard will
    # refuse to let land.  Declaring here means the refusal arrives before
    # the read, before the scratch, and before any child process exists.
    EXTWRITE.declare_external_write(output_path,
                                    writer=_OSMIUM_WRITER_NAME)
    # LANE-LOCAL SCRATCH (#159): osmium is a CHILD PROCESS, so a part cut
    # beside an output in the shared corpus is a write no Python guard can
    # refuse.  A fresh directory per cut also removes the need for the old
    # per-pid-and-thread unique names.
    scratch = _make_cut_scratch(temporary_directory)
    part_paths = [os.path.join(scratch, _CUT_PART_TEMPLATE % index)
                  for index in range(len(paths))]
    stderr_path = os.path.join(scratch, _CUT_STDERR_NAME)
    try:
        for source_path, part_path in zip(paths, part_paths):
            _run_osmium_extract(
                osmium_binary, source_path, bbox_argument, part_path,
                stderr_path, should_stop, spawn_kwargs,
            )
        if len(part_paths) == 1:
            _move_into_place(part_paths[0], output_path)
        else:
            # Small inputs now: the pyosmium cutter's read cost is a few
            # seconds here, and its first-file-wins merge is the oracle.
            # It cuts its OWN scratch temporary and moves it into place.
            clip_extracts_to_pbf(part_paths, boxes[0], output_path,
                                 temporary_directory=temporary_directory)
    finally:
        _discard_cut_scratch(scratch)


def cut_clip_parts_with_osmium(
    extract_paths: Iterable[str],
    bounding_box,
    part_output_paths: Iterable[str],
    osmium_binary: str,
    should_stop: Optional[Callable[[], bool]] = None,
    spawn_kwargs: Optional[dict] = None,
    temporary_directory: Optional[str] = None,
) -> None:
    """Cut one clip PART per extract, no merge — C++ end to end.

    The merged single-file clip (:func:`cut_clip_with_osmium`) pays a
    pyosmium first-file-wins merge whenever an area spans several
    extracts — 161 MB of Alpine clips took minutes of Python callbacks
    (observed 2026-07-23, tile +46+006 across three extracts).  The
    merge buys nothing: the query-time filter already consumes an
    ORDERED FILE LIST with first-file-wins semantics, so the parts can
    be cached and served as-is, in ``extract_paths`` order.

    Each part is written atomically; the CALLER owns completeness (it
    writes its parts manifest only after this returns).  Same failure
    contract as :func:`cut_clip_with_osmium`, and the same lane-local
    scratch.

    temporary_directory: root for the cut's scratch directory, which is
        where the temporary is written before the atomic move onto
        ``output_path`` (#159 — never beside the destination, which may be
        the shared corpus).  Default: the engine's lane-local ``tmp``
        product directory, or the platform temp dir when the engine has no
        data root yet.
    """
    boxes = _normalize_bounding_boxes(bounding_box)
    if len(boxes) != 1:
        raise ExtractFilterError(
            "osmium clip cutting expects a single clip box"
        )
    (lat_min, lon_min, lat_max, lon_max) = boxes[0]
    bbox_argument = "%.7f,%.7f,%.7f,%.7f" % (
        lon_min, lat_min, lon_max, lat_max)
    paths = [str(path) for path in extract_paths]
    outputs = [str(path) for path in part_output_paths]
    if len(paths) != len(outputs):
        raise ExtractFilterError(
            "one part output per extract required (%d extracts, %d outputs)"
            % (len(paths), len(outputs)))
    for path in paths:
        if not os.path.isfile(path):
            raise ExtractFilterError("extract file not found: " + path)
    # THE DESTINATION IS DECLARED BEFORE ANY WORK (#159 bar 2).  The cut is
    # the expensive part — a whole-country extract read — and there is no
    # point paying it for an output an armed shared-repo write guard will
    # refuse to let land.  Declaring here means the refusal arrives before
    # the read, before the scratch, and before any child process exists.
    EXTWRITE.declare_external_writes(outputs,
                                     writer=_OSMIUM_WRITER_NAME)
    # LANE-LOCAL SCRATCH (#159) — see :func:`cut_clip_with_osmium`.
    scratch = _make_cut_scratch(temporary_directory)
    temporary_paths = [os.path.join(scratch, _CUT_PART_TEMPLATE % index)
                       for index in range(len(outputs))]
    stderr_path = os.path.join(scratch, _CUT_STDERR_NAME)
    try:
        for source_path, temporary_path in zip(paths, temporary_paths):
            _run_osmium_extract(
                osmium_binary, source_path, bbox_argument, temporary_path,
                stderr_path, should_stop, spawn_kwargs,
            )
        for temporary_path, output in zip(temporary_paths, outputs):
            _move_into_place(temporary_path, output)
    finally:
        _discard_cut_scratch(scratch)
