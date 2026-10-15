"""Reading and writing one ``*.patch.osm`` for the patch editor (spec
patch-editor-20261015 §1.2, §2).

The reader turns a patch into the §2 wire lists — nodes ``[id, lat, lon,
alt|null]`` (``alt`` is the node's ``alt_abs`` tag) and ways ``{id, refs,
tags}`` — plus what a rewrite must carry through untouched: the root
element's attributes AS WRITTEN (raw text, so a stamp re-reads
byte-for-byte), any other node tags, and top-level elements the editor does
not model (a hand-made file's relations).

The writer follows the v2 emitter's conventions
(``emit/osm_adapter.render_patch``): single-quoted attributes, the root on
ONE line, nodes before ways, ``action='modify' visible='true'``, lat/lon at
the law's identity precision, ``alt_abs`` at the law's elevation
quantisation whenever that is exact.  It writes atomically (a temporary file
in the same folder, then ``os.replace``).

The saved header (§1.2): every ``o4_*`` attribute of the patch the edit
started from re-keyed ``o4_edited_from_<name>`` (the ``o4_`` prefix moves to
the front, so no stamp reader's pattern — ``o4_apt_dat='…'`` and the
freshness keys are matched unanchored — can mistake a recorded stamp for a
live one), stamps an already-edited base recorded carried as they are, and
``o4_user_edited='1'``.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import re
import tempfile
import typing as _t
import xml.etree.ElementTree as ET

from auto_patch.build_support import USER_EDITED_ATTR, patch_root_line
from auto_patch_v2.emit.osm_adapter import _q

__all__ = ["EDITED_FROM_PREFIX", "PatchFile", "read_patch", "root_attributes",
           "edited_header", "recorded_stamps_line", "render", "write_atomic"]

#: The re-key of a base stamp in an edited patch's header.
EDITED_FROM_PREFIX = "o4_edited_from_"

_ATTR_RE = re.compile(r"""([\w:.-]+)=(['"])(.*?)\2""", re.S)


@_dc.dataclass
class PatchFile:
    """One patch as the editor sees it."""

    path: str
    root_raw: list[tuple[str, str, str]]     # (name, quote, raw value)
    header: dict[str, str]                   # name -> XML-unescaped value
    nodes: list[list]                        # [id, lat, lon, alt|None]
    ways: list[dict]                         # {id, refs, tags}
    node_tags: dict[int, list[tuple[str, str]]]  # tags other than alt_abs
    extras: list[str]                        # other top-level elements, raw

    def bbox(self) -> list[float] | None:
        """``[min_lat, min_lon, max_lat, max_lon]`` of the nodes."""
        if not self.nodes:
            return None
        lats = [n[1] for n in self.nodes]
        lons = [n[2] for n in self.nodes]
        return [min(lats), min(lons), max(lats), max(lons)]


def root_attributes(line: str) -> list[tuple[str, str, str]]:
    """``(name, quote, raw value)`` of every attribute on an ``<osm …>``
    root line, in order."""
    body = line[line.index("<osm") + 4:]
    return [(m.group(1), m.group(2), m.group(3)) for m in _ATTR_RE.finditer(body)]


def read_patch(path: str) -> PatchFile:
    """Parse *path* (raises ``ValueError`` with the cause on a bad file)."""
    line = patch_root_line(path)
    if line is None:
        raise ValueError(f"{os.path.basename(path)} is not a patch: no <osm> "
                         f"element in its first two lines")
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValueError(f"{os.path.basename(path)} cannot be read ({exc}); "
                         f"fix or remove the file") from None
    nodes: list[list] = []
    node_tags: dict[int, list[tuple[str, str]]] = {}
    ways: list[dict] = []
    extras: list[str] = []
    for el in root:
        if el.tag == "node":
            nid = int(el.get("id"))
            alt = None
            other = []
            for t in el.findall("tag"):
                k, v = t.get("k"), t.get("v")
                if k == "alt_abs" and alt is None:
                    try:
                        alt = float(v)
                        continue
                    except (TypeError, ValueError):
                        pass
                other.append((k, v))
            if other:
                node_tags[nid] = other
            nodes.append([nid, float(el.get("lat")), float(el.get("lon")), alt])
        elif el.tag == "way":
            ways.append({"id": int(el.get("id")),
                         "refs": [int(nd.get("ref")) for nd in el.findall("nd")],
                         "tags": {t.get("k"): t.get("v") for t in el.findall("tag")}})
        else:
            el.tail = None
            extras.append(ET.tostring(el, encoding="unicode"))
    return PatchFile(path, root_attributes(line), dict(root.attrib), nodes, ways,
                     node_tags, extras)


def edited_header(base_raw: _t.Iterable[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """The saved root attributes (§1.2) from the base's raw ones."""
    plain, carried, rekeyed = [], [], []
    for name, quote, raw in base_raw:
        if name == USER_EDITED_ATTR:
            continue
        if name.startswith(EDITED_FROM_PREFIX):
            carried.append((name, quote, raw))
        elif name.startswith("o4_"):
            rekeyed.append((EDITED_FROM_PREFIX + name[3:], quote, raw))
        else:
            plain.append((name, quote, raw))
    # An already-edited base keeps the stamps of the patch the FIRST edit
    # started from; its own o4_* (none, normally) are not stamps of that.
    stamps = carried if carried else rekeyed
    return plain + stamps + [(USER_EDITED_ATTR, "'", "1")]


def recorded_stamps_line(raw: _t.Iterable[tuple[str, str, str]]) -> str | None:
    """An ``<osm …>`` line carrying the stamps an edited patch RECORDED,
    under their original names — what ``build_support.parse_patch_source``
    reads — or ``None`` when it recorded none."""
    parts = [f"o4_{name[len(EDITED_FROM_PREFIX):]}={q}{v}{q}"
             for name, q, v in raw if name.startswith(EDITED_FROM_PREFIX)]
    return ("<osm " + " ".join(parts) + ">") if parts else None


def _alt_text(alt: float, zdp: int) -> str:
    text = f"{alt:.{zdp}f}"
    return text if abs(float(text) - alt) < 1e-9 else repr(float(alt))


def render(header: _t.Iterable[tuple[str, str, str]], nodes: _t.Sequence[_t.Sequence],
           ways: _t.Sequence[_t.Mapping], node_tags: _t.Mapping[int, _t.Sequence] | None = None,
           extras: _t.Sequence[str] = (), *, identity_dp: int, z_dp: int) -> str:
    """The ``.osm`` text: nodes and ways in the order given, tags unchanged.
    Raises ``ValueError`` when a way names a node that is not given."""
    known = {int(n[0]) for n in nodes}
    for w in ways:
        missing = [r for r in w["refs"] if int(r) not in known]
        if missing:
            raise ValueError(f"way {w['id']} references node {missing[0]}, which "
                             f"is not in the nodes sent; send every node a way uses")
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<osm " + " ".join(f"{k}={q}{v}{q}" for k, q, v in header) + ">"]
    for n in nodes:
        nid, lat, lon = int(n[0]), float(n[1]), float(n[2])
        alt = n[3] if len(n) > 3 else None
        out.append(f"  <node id='{nid}' action='modify' visible='true' "
                   f"lat='{lat:.{identity_dp}f}' lon='{lon:.{identity_dp}f}'>")
        if alt is not None:
            out.append(f"    <tag k='alt_abs' v='{_alt_text(float(alt), z_dp)}' />")
        for k, v in (node_tags or {}).get(nid, ()):
            out.append(f"    <tag k={_q(k)} v={_q(v)} />")
        out.append("  </node>")
    for w in ways:
        out.append(f"  <way id='{int(w['id'])}' action='modify' visible='true'>")
        out.extend(f"    <nd ref='{int(r)}' />" for r in w["refs"])
        out.extend(f"    <tag k={_q(k)} v={_q(v)} />" for k, v in (w.get("tags") or {}).items())
        out.append("  </way>")
    out.extend("  " + e for e in extras)
    out.append("</osm>")
    return "\n".join(out) + "\n"


def write_atomic(path: str, text: str) -> None:
    """Write *text* to *path* through a temporary file and ``os.replace``."""
    folder = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".patch_edit_", suffix=".tmp", dir=folder)
    # mkstemp creates the file 0600; a patch is an ordinary file like the
    # auto patch beside it: keep the replaced file's mode, else the umask's.
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
