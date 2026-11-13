"""THE OSM CONTENT AN AIRPORT'S SOLVE READ — the patch gate's OSM key by
CONTENT, not by file (issue #2050, owner RULINGS 2026-11-13o).

``osm.feed_witness`` (``o4_osm``, #880) is the size and mtime of every
feed file over the airport's 3x3 tile neighbourhood.  It moves whenever
any of those files is rewritten, appears or vanishes — a ledgered
``--refresh-data osm_layers``, a neighbour tile's first build writing its
own airports layer — and on 2026-11-13 KDEN re-solved for ~25 min on
"o4_osm changed" after a refresh of its tile's airports layer.

The content stamp (``o4_osm_content``) is what the load READ:
:func:`docs_content` digests, per feed, the multiset of ways
``osm.load_feed`` selected inside the airport's box — each way's tags of
interest and its vertices, sorted, with NO ids.  The ids are left out
because Ortho4XP renumbers a cache's elements on every write (negative
ids in fetch order), so an edit anywhere in the tile renumbers every way
in the box without changing one of them.  ``"v1|<lat>|<lon>|<radius>|
<feed>=<hex>;…"``: the box rides in the stamp (``repr`` floats, exact)
so the gate recomputes the very same selection.

THE GATE (:func:`osm_input_stale`) is two-tier: the file witness first
(stat only, as before); only when it moved is the content recomputed
(one parse of the neighbourhood's feeds, ~2.7 s at KDEN) and compared.
An equal answer is MEMOISED beside the patch
(``o4_osm_content_<ICAO>.memo``: the live witness it was proved for),
so the next build is back on the stat-only path; the patch itself is
never rewritten (its bytes are a step-reuse output, #837).  A patch
stamped before this key has no content to compare and rebuilds on a
moved witness, exactly as before — and carries the key from then on.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import typing as _t

from . import osm as _osm

__all__ = ["CONTENT_VERSION", "MEMO_NAME", "docs_content", "content_stamp",
           "parse_stamp", "changed_feeds", "memo_path", "osm_input_stale",
           "describe", "layer_content_digest"]

#: The digest's own version: bump it when :func:`_way_line` changes, so a
#: stamp of another derivation is never compared as equal or unequal.
CONTENT_VERSION = "v1"

#: ``<patch dir>/o4_osm_content_<ICAO>.memo`` — not ``*.json``: no glob of
#: the patch directory reads it (the ``object_plan`` precedent).
MEMO_NAME = "o4_osm_content_{icao}.memo"

_WITNESS_RE = re.compile(r"(-?\d+),(-?\d+)\|[0-9a-f]{16}")


def _way_line(way: _osm.RawWay) -> str:
    """One way, id-free and canonical: its tags sorted, its vertices in
    node order (``repr`` — the floats the load hands the solve)."""
    return json.dumps([sorted(way.tags.items()),
                       [[repr(la), repr(lo)] for la, lo in way.points]],
                      separators=(",", ":"))


def _feed_digest(ways: _t.Iterable[_osm.RawWay]) -> str:
    h = hashlib.sha256()
    for line in sorted(_way_line(w) for w in ways):
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def docs_content(docs: _t.Mapping[str, _osm.OsmDoc], lat: float, lon: float,
                 radius_deg: float) -> str:
    """The ``o4_osm_content`` stamp of the feeds a load read (``docs``:
    feed → the ``osm.load_feed`` answer for that box).  Every feed of
    ``osm.FEEDS`` is named; a feed the load did not read digests as
    empty, the same as a feed with no way in the box."""
    parts = [f"{feed}={_feed_digest(docs[feed].ways if feed in docs else ())}"
             for feed in _osm.FEEDS]
    return "|".join((CONTENT_VERSION, repr(float(lat)), repr(float(lon)),
                     repr(float(radius_deg)), ";".join(parts)))


def content_stamp(osm_root: str, lat: float, lon: float,
                  radius_deg: float) -> str:
    """:func:`docs_content` of the feeds on disk now — ``osm.load_feed``
    per feed over the same box, the load's own selection."""
    docs = {feed: _osm.load_feed(osm_root, feed, lat, lon, radius_deg)
            for feed in _osm.FEEDS}
    return docs_content(docs, lat, lon, radius_deg)


def parse_stamp(stamp: str) -> tuple[float, float, float, dict] | None:
    """``(lat, lon, radius, {feed: digest})`` of a content stamp, or
    ``None`` for a missing, malformed or other-version one."""
    fields = (stamp or "").split("|")
    if len(fields) != 5 or fields[0] != CONTENT_VERSION:
        return None
    try:
        lat, lon, radius = (float(v) for v in fields[1:4])
        feeds = dict(item.split("=", 1) for item in fields[4].split(";"))
    except ValueError:
        return None
    return lat, lon, radius, feeds


def changed_feeds(was: str, now: str) -> list[str]:
    """The feeds whose content differs between two stamps (all of
    ``osm.FEEDS`` when either cannot be read)."""
    a, b = parse_stamp(was), parse_stamp(now)
    if a is None or b is None:
        return list(_osm.FEEDS)
    return [f for f in _osm.FEEDS if a[3].get(f) != b[3].get(f)]


def memo_path(patch_dir: str, icao: str) -> str:
    """Where the gate memoises a content-equal answer for ``icao``."""
    return os.path.join(patch_dir, MEMO_NAME.format(icao=icao))


def _memo_proves(patch_dir: str, icao: str, content: str, witness: str) -> bool:
    try:
        with open(memo_path(patch_dir, icao), encoding="utf-8") as fh:
            memo = json.load(fh)
    except (OSError, ValueError):
        return False
    return (isinstance(memo, dict) and memo.get("content") == content
            and memo.get("witness") == witness)


def _write_memo(patch_dir: str, icao: str, content: str, witness: str) -> None:
    path = memo_path(patch_dir, icao)
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"content": content, "witness": witness}, fh)
        os.replace(tmp, path)
    except OSError:
        pass                # the next gate proves it again


def osm_input_stale(witness: str, content: str, osm_root: str,
                    patch_dir: str, icao: str
                    ) -> tuple[str | None, str | None] | None:
    """``None`` when the OSM the patch was solved on is what is on disk
    now; else ``(was, now)`` for the gate's ``o4_osm`` row — the two
    content stamps when the patch has one, else the two file witnesses
    (:func:`describe` words either).

    ``witness`` / ``content``: the patch's ``o4_osm`` / ``o4_osm_content``
    stamps.  The witness names the home tile (``"<lat>,<lon>|<hex>"``);
    a missing or malformed one is changed (fail-safe, #880)."""
    m = _WITNESS_RE.fullmatch(witness or "")
    if not m:
        return (witness or None, None)
    live = _osm.feed_witness(osm_root, int(m.group(1)), int(m.group(2)))
    if live == witness:
        return None
    box = parse_stamp(content)
    if box is None:
        return (witness, live)
    if _memo_proves(patch_dir, icao, content, live):
        return None
    try:
        now = content_stamp(osm_root, *box[:3])
    except Exception:       # an unreadable feed: not provably the same
        return (content, "unreadable")
    if now == content:
        _write_memo(patch_dir, icao, content, live)
        return None
    return (content, now)


def describe(was: str | None, now: str | None) -> str:
    """Why an ``o4_osm`` row is stale, in words for the build log."""
    if now is None:
        return "the patch carries no OSM stamp"
    if now == "unreadable":
        return "an OSM feed around the airport could not be read"
    if parse_stamp(was or "") is None:
        return ("the OSM feed files changed (the patch predates content "
                "stamps, so their content could not be compared)")
    return ("the OSM content in the airport's box changed ("
            + ", ".join(changed_feeds(was or "", now)) + ")")


#: ``(path, size, mtime_ns) -> digest`` of the layers
#: :func:`layer_content_digest` has parsed in this process.
_LAYER_MEMO: dict = {}


def layer_content_digest(path: str) -> str | None:
    """One id-free digest of a WHOLE cached OSM layer (``None`` when it
    cannot be read): every tagged node (position + tags), every way (tags
    + its vertices' positions in order), every relation (tags + its
    members as type, role and the member's own canonical form).  Two
    writes of the same data — a refresh, a fetch through another backend
    that numbers the elements differently — digest equal (#2050).

    The airport-inset completion stamp keys the tile's airport SET on it
    (``O4_Airport_Elevation_Insets._inset_completion_key``).  Memoised on
    the file's stat: one parse per layer version per process."""
    import bz2
    import xml.etree.ElementTree as ET
    try:
        st = os.stat(path)
        key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
        if key in _LAYER_MEMO:
            return _LAYER_MEMO[key]
        opener = bz2.open if path.endswith(".bz2") else open
        with opener(path, "rb") as fh:
            root = ET.fromstring(fh.read())
    except (OSError, ET.ParseError, EOFError, ValueError):
        return None

    def tags(el) -> list:
        return sorted((t.get("k", ""), t.get("v", "")) for t in el.findall("tag"))

    nodes: dict[str, list] = {}
    ways: dict[str, list] = {}
    lines: list[str] = []
    for el in root:
        if el.tag == "node":
            pos = [el.get("lat", ""), el.get("lon", "")]
            nodes[el.get("id", "")] = pos
            if el.find("tag") is not None:
                lines.append(json.dumps(["n", pos, tags(el)]))
    for el in root:
        if el.tag == "way":
            geom = [nodes.get(nd.get("ref", ""), None) for nd in el.findall("nd")]
            ways[el.get("id", "")] = geom
            lines.append(json.dumps(["w", tags(el), geom]))
    for el in root:
        if el.tag == "relation":
            members = []
            for m in el.findall("member"):
                kind, ref = m.get("type", ""), m.get("ref", "")
                form = (nodes.get(ref) if kind == "node" else
                        ways.get(ref) if kind == "way" else None)
                members.append([kind, m.get("role", ""), form])
            lines.append(json.dumps(["r", tags(el), members]))
    h = hashlib.sha256()
    for line in sorted(lines):
        h.update(line.encode("utf-8") + b"\n")
    digest = _LAYER_MEMO[key] = h.hexdigest()[:16]
    return digest
