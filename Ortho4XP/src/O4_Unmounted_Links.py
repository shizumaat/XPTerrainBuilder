"""Custom Scenery links whose target is not there (issue #668).

X-Plane users keep scenery packs on an external drive and link them into
``Custom Scenery``.  While that drive is not mounted every such link
DANGLES: the app can neither read the pack nor write a tile folder through
it.  This module is the ONE place that recognises such a link, names the
drive it waits for, and removes ONE link at the user's request.

* :func:`dangling_link` — the first link on a path (the path itself or a
  parent folder) whose target does not exist: ``{"link", "target",
  "volume"}``, else ``None``.  A healthy link to a mounted volume is
  never reported.
* :class:`UnmountedLink` — the tile-ending exception for a tile OUTPUT
  folder behind such a link (catalogue code ``output_link_unmounted``,
  :mod:`O4_Tile_Failures`).
* :func:`unmounted_packs` — the airports of a tile whose previous patch
  was graded from a pack that now dangles (the patch's own ``o4_apt_dat``
  stamp is the witness).  The tile still builds; the airport is graded
  from X-Plane's own data and the tile carries a warning
  (``airport_pack_unmounted``, the #564 "built, but…" path).
* :func:`remove_link` — the engine command ``remove_scenery_link``: removes
  a dangling link that sits directly in a ``Custom Scenery`` folder.  It
  never follows the link and never deletes a folder.

Imports only the standard library and :mod:`O4_Scenery_Links` (whose
link test and removal it shares).
"""

from __future__ import annotations

import glob
import os
import re
import urllib.parse
from typing import Optional

# the ONE link test and removal (symlink or Windows junction)
from O4_Scenery_Links import _is_link, _remove_link

__all__ = ["UnmountedLink", "dangling_link", "volume_of", "check_output",
           "unmounted_packs", "remove_link", "FAILURE_CODE",
           "READ_FAILURE_CODE"]

FAILURE_CODE = "output_link_unmounted"
READ_FAILURE_CODE = "airport_pack_unmounted"
_CUSTOM_SCENERY = "Custom Scenery"
_APT_DAT_RE = re.compile(r"""o4_apt_dat=['"]([^'"]*)['"]""")
_ICAO_RE = re.compile(r"""o4_icao=['"]([^'"]*)['"]""")


def _read_target(path: str) -> str:
    try:
        return os.readlink(path)
    except OSError:
        return ""


def volume_of(target: str) -> str:
    """The drive a link target lives on, as the user knows it: the
    ``<name>`` of a macOS ``/Volumes/<name>/…`` path, the ``X:`` of a
    Windows drive path; ``""`` when the target names no drive."""
    if not target:
        return ""
    norm = target.replace("\\", "/")
    if norm.startswith("//?/"):
        norm = norm[4:]
    parts = [p for p in norm.split("/") if p]
    if norm.startswith("/Volumes/") and len(parts) >= 2:
        return parts[1]
    if re.match(r"^[A-Za-z]:", norm):
        return norm[:2].upper()
    return ""


def dangling_link(path: str) -> Optional[dict]:
    """The first link on ``path`` (its parents first, then ``path``) whose
    target does not exist; ``None`` when every link on it resolves (or
    there is none).  Never creates or follows anything beyond ``stat``."""
    if not path:
        return None
    full = os.path.abspath(path)
    chain = []
    head = full
    while True:
        chain.append(head)
        parent = os.path.dirname(head)
        if parent == head:
            break
        head = parent
    for candidate in reversed(chain):
        if not os.path.lexists(candidate):
            return None          # nothing further down exists either
        if _is_link(candidate) and not os.path.exists(candidate):
            target = _read_target(candidate)
            return {"link": candidate, "target": target,
                    "volume": volume_of(target)}
    return None


class UnmountedLink(Exception):
    """A tile's output folder is (or lies behind) a link whose target is
    missing — on macOS, a drive that is not mounted.  The tile cannot be
    built until the drive is back or the link is removed."""

    failure_code = FAILURE_CODE

    def __init__(self, found: dict):
        self.failure_params = {"link": found.get("link", ""),
                               "target": found.get("target", ""),
                               "volume": found.get("volume", "")}
        super().__init__("%s -> %s (target missing%s)" % (
            found.get("link", ""), found.get("target", "") or "?",
            ", drive %s not mounted" % found["volume"]
            if found.get("volume") else ""))


def check_output(build_dir: str) -> None:
    """Raise :class:`UnmountedLink` when ``build_dir`` cannot be reached
    because a link on it dangles (the pre-flight and the failing write)."""
    found = dangling_link(build_dir)
    if found:
        raise UnmountedLink(found)


def _pack_root(apt_dat: str) -> Optional[str]:
    """``…/Custom Scenery/<pack>`` of a path inside a pack, else None."""
    parts = os.path.normpath(apt_dat).split(os.sep)
    if _CUSTOM_SCENERY not in parts:
        return None
    index = len(parts) - 1 - parts[::-1].index(_CUSTOM_SCENERY)
    if index + 1 >= len(parts):
        return None
    return os.sep.join(parts[:index + 2]) or None


def _patch_stamp(path: str) -> tuple:
    """``(icao, apt_dat)`` from a patch file's ``<osm>`` root ("" each
    when unstamped).  Reads the first two lines only."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            head = handle.readline() + handle.readline()
    except OSError:
        return ("", "")
    apt = _APT_DAT_RE.search(head)
    icao = _ICAO_RE.search(head)
    return (urllib.parse.unquote(icao.group(1)) if icao else "",
            urllib.parse.unquote(apt.group(1)) if apt else "")


def unmounted_packs(patch_dir: str, earlier=()) -> list:
    """One row per airport of a tile whose LAST patch was graded from a
    Custom Scenery pack that is now a dangling link: ``{"icao", "pack",
    "link", "target", "volume"}``.  Read BEFORE the tile's vector step
    rewrites the patches.  An airport never built from such a pack has no
    witness and is not named.  ``earlier`` (the rows the previous build
    published) carries an airport forward while its link still dangles:
    that build regraded it from X-Plane's data, so its patch no longer
    names the pack."""
    rows = []
    for path in sorted(glob.glob(os.path.join(patch_dir or "",
                                              "*.patch.osm"))):
        icao, apt_dat = _patch_stamp(path)
        root = _pack_root(apt_dat) if apt_dat else None
        if not root:
            continue
        found = dangling_link(root)
        if found:
            rows.append(dict(found, icao=icao or "?",
                             pack=os.path.basename(root)))
    seen = {row["icao"] for row in rows}
    for row in earlier or ():
        if (isinstance(row, dict) and row.get("icao") not in seen
                and row.get("link") and dangling_link(row["link"])):
            rows.append(dict(row))
            seen.add(row.get("icao"))
    return rows


def remove_link(path: str) -> dict:
    """ENGINE COMMAND ``remove_scenery_link``: remove ONE dangling link.

    Refuses (``ValueError``, its sentence for the user) a path that is not
    directly inside a ``Custom Scenery`` folder, that is not a link, or
    whose target is reachable.  Only the link goes — never its target,
    never a folder.  Returns ``{"removed": path}``.
    """
    if not path:
        raise ValueError("No link was named.")
    full = os.path.abspath(path)
    parent = os.path.basename(os.path.dirname(full))
    if os.path.normcase(parent) != os.path.normcase(_CUSTOM_SCENERY):
        raise ValueError("“%s” is not in a Custom Scenery folder; the app "
                         "removes only links there." % full)
    if not os.path.lexists(full):
        raise ValueError("“%s” does not exist." % full)
    if not _is_link(full):
        raise ValueError("“%s” is not a link; the app will not delete it."
                         % full)
    if os.path.exists(full):
        raise ValueError("The link “%s” points to a folder that is "
                         "reachable; the app removes only a link whose "
                         "target is missing." % full)
    _remove_link(full)
    return {"removed": full}
