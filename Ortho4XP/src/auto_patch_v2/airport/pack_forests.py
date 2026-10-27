"""OLD FLAT FORESTS in an airport pack's DSF, and their X-Plane 12 3D
upgrade (issue #1360).

Owner (2026-10-26): "identify if the airport uses x-plane 11 style .for
resources that are the old flat planes, and ask the user if they would
like to update their resources to point to the equivalent 3D x-plane 12
resources."  This module owns the pure halves, any pack, any tile:

* THE CHECK — :func:`old_forests`: every ``POLYGON_DEF`` of a DSFTool
  dump that names a ``.for`` file, resolved the way X-Plane resolves it
  (``obj8.resolve_resource``: the pack folder first, then the installed
  libraries), whose file is FLAT — :func:`for_kind`: a ``.for`` with any
  ``SHADER_3D`` or ``MESH`` line draws 3D trees (X-Plane 12's forest
  format; a 3D file may still carry a few ``TREE`` lines for its last
  billboard step), one with ``TREE`` lines and neither is the old flat
  kind.  A definition that does not resolve is not judged here (the
  missing-art check owns it, ``pack_art``).
* THE MAP — each flat file X-Plane itself ships gets its 3D target from
  ``pack_forests_map.FOREST_MAP``, and only when THIS install provides
  that target as 3D: a merged export that resolves to a 3D file, or a
  name only a seasonal / excluding export provides (X-Plane 12 is the
  only version with those, and every ``.for`` it exports through them is
  3D — the listing the map cites; the merged library index does not
  carry them, ``agp_reader.other_export_names``).  An X-Plane 11 install
  has neither, and is offered nothing.  A pack's own ``.for`` and a flat file the map does
  not name are UNMAPPED: reported, never guessed.
* THE RENAME — :func:`rename_definitions`: the dump text with the mapped
  ``POLYGON_DEF`` rows pointing at their targets.  Only those rows change;
  every polygon keeps its index, its points and every other byte.

The rewrite itself is ``dsf_write.write_pack``'s (``forests=``): the
pristine DSF stays as ``<name>.dsf.anchor_bak``, the record beside it
gains ``forest_upgrade`` (:func:`record`), and every later write of the
DSF re-applies it while the pristine file is the one it was accepted
for (:func:`recorded`).
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import os
import typing as _t

from .obj8 import resolve_resource
from .pack_art import FIRST_PATHS, count_uses, declared_definitions
from .pack_forests_map import FOREST_MAP

__all__ = ["OldForest", "for_kind", "forest_key", "old_forests",
           "renames_of", "rename_definitions", "decision_key", "record",
           "recorded", "summary", "log_line", "RECORD_KEY"]

#: the key of the record row (``o4_placement_provenance.json``)
RECORD_KEY = "forest_upgrade"
#: a ``.for`` line keyword that only X-Plane 12's 3D trees use
KEYWORDS_3D = frozenset({"SHADER_3D", "MESH"})


@_dc.dataclass(frozen=True)
class OldForest:
    """One flat forest the DSF declares.  ``index`` is its position among
    the polygon definitions, ``uses`` the polygons that draw it,
    ``target`` its 3D replacement (``""`` = unmapped), ``local`` whether
    the file is the pack's own."""

    index: int
    path: str
    uses: int = 0
    target: str = ""
    local: bool = False

    def to_dict(self) -> dict[str, _t.Any]:
        return _dc.asdict(self)


def for_kind(path: str) -> str | None:
    """``"3d"`` | ``"flat"`` for a ``.for`` file, ``None`` when it is
    neither (unreadable, or no tree in it)."""
    trees = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                kw = raw.split(None, 1)[0] if raw.strip() else ""
                if kw in KEYWORDS_3D:
                    return "3d"
                trees = trees or kw == "TREE"
    except OSError:
        return None
    return "flat" if trees else None


def forest_key(resolved: str, default_scenery: str) -> str:
    """The :data:`FOREST_MAP` key of a resolved file: ``<library>/<file>``
    under X-Plane's ``Resources/default scenery``; ``""`` elsewhere."""
    try:
        rel = os.path.relpath(os.path.abspath(resolved),
                              os.path.abspath(default_scenery))
    except ValueError:                       # another drive (Windows)
        return ""
    if rel.startswith(os.pardir):
        return ""
    return rel.replace(os.sep, "/")


def _target(key: str, index: _t.Mapping[str, str],
            kinds: dict[str, str | None],
            also_exported: _t.Callable[[], _t.Container[str]] | None) -> str:
    target = FOREST_MAP.get(key, "")
    if not target:
        return ""
    phys = resolve_resource(target, None, index)
    if phys is None:
        return target if (also_exported is not None
                          and target.lower() in also_exported()) else ""
    if phys not in kinds:
        kinds[phys] = for_kind(phys)
    return target if kinds[phys] == "3d" else ""


def old_forests(pack_root: str, source: str | _t.Sequence[str],
                index: _t.Mapping[str, str] | None,
                default_scenery: str,
                also_exported: _t.Callable[[], _t.Container[str]] | None = None
                ) -> tuple[OldForest, ...] | None:
    """THE CHECK.  Every flat forest ``source`` (a dump path, or its rows)
    declares, with its use count and its target; ``()`` when there is
    none.  ``None`` without a library index: a virtual path could not be
    resolved, so nothing is said.  ``also_exported`` answers the
    LOWER-CASED names the index does not carry but a seasonal or
    excluding export provides; asked only for a target the index lacks."""
    if index is None:
        return None
    kinds: dict[str, str | None] = {}
    found: list[tuple[int, str, str, bool]] = []
    pack = os.path.abspath(pack_root) + os.sep
    for i, path in enumerate(declared_definitions(source)["polygon"]):
        p = path.replace("\\", "/").replace(":", "/")
        if not p.lower().endswith(".for"):
            continue
        phys = resolve_resource(p, pack_root, index)
        if phys is None:
            continue
        if phys not in kinds:
            kinds[phys] = for_kind(phys)
        if kinds[phys] != "flat":
            continue
        local = os.path.abspath(phys).startswith(pack)
        target = "" if local else _target(forest_key(phys, default_scenery),
                                          index, kinds, also_exported)
        found.append((i, path, target, local))
    if not found:
        return ()
    uses = count_uses(source, {("polygon", i) for i, *_ in found})
    return tuple(OldForest(i, p, uses[("polygon", i)], t, loc)
                 for i, p, t, loc in found)


def renames_of(old: _t.Iterable[OldForest]) -> dict[str, str]:
    """``{declared path: 3D target}`` of the mapped ones."""
    return {f.path: f.target for f in old if f.target}


def rename_definitions(text: str, renames: _t.Mapping[str, str]
                       ) -> tuple[str, int]:
    """THE RENAME (pure): ``text`` with each ``POLYGON_DEF`` whose path is
    a key of ``renames`` pointing at its value.  Returns the text and the
    rows renamed; nothing else changes."""
    if not renames:
        return text, 0
    out: list[str] = []
    n = 0
    for raw in text.splitlines(keepends=True):
        kw, _, rest = raw.partition(" ")
        if kw == "POLYGON_DEF":
            path = rest.strip()
            if path in renames:
                end = raw[len(raw.rstrip("\r\n")):]
                out.append(f"POLYGON_DEF {renames[path]}{end}")
                n += 1
                continue
        out.append(raw)
    return "".join(out), n


def decision_key(pristine_sha256: str, renames: _t.Mapping[str, str]) -> str:
    """What an accepted upgrade is keyed to: the PRISTINE DSF content and
    the set of renames.  A pack update is a different key."""
    h = hashlib.sha256(pristine_sha256.encode("ascii", "replace"))
    for old, new in sorted(renames.items()):
        h.update(f"\n{old}\t{new}".encode("utf-8", "surrogateescape"))
    return h.hexdigest()


def record(pristine_sha256: str, renames: _t.Mapping[str, str], renamed: int,
           time: str) -> dict[str, _t.Any]:
    """The :data:`RECORD_KEY` entry of ``o4_placement_provenance.json``:
    every definition changed, from what, to what."""
    return {"accepted": True, "time": time,
            "key": decision_key(pristine_sha256, renames),
            "pristine_sha256": pristine_sha256,
            "renamed": int(renamed),
            "renames": [{"path": k, "target": v}
                        for k, v in sorted(renames.items())]}


def recorded(entry: _t.Mapping[str, _t.Any] | None,
             pristine_sha256: str) -> dict[str, str]:
    """The upgrade the user accepted for THIS pristine DSF, read back from
    :func:`record`'s row; ``{}`` when none is recorded, when it belongs to
    another pristine file, or when the row no longer reads as written."""
    row = (entry or {}).get(RECORD_KEY)
    if not (isinstance(row, dict) and row.get("accepted") is True
            and row.get("pristine_sha256") == pristine_sha256):
        return {}
    try:
        renames = {str(r["path"]): str(r["target"])
                   for r in row.get("renames") or ()}
    except (KeyError, TypeError):
        return {}
    return renames if row.get("key") == decision_key(pristine_sha256,
                                                     renames) else {}


def summary(old: _t.Sequence[OldForest]) -> dict[str, _t.Any]:
    """The counts and names the ``PackOldForests`` event carries."""
    mapped = [f for f in old if f.target]
    unmapped = [f for f in old if not f.target]
    return {"total": len(old), "mapped": len(mapped),
            "uses": sum(f.uses for f in mapped),
            "first_paths": [f.path for f in mapped[:FIRST_PATHS]],
            "unmapped": len(unmapped),
            "first_unmapped": [f.path for f in unmapped[:FIRST_PATHS]]}


def log_line(pack: str, old: _t.Sequence[OldForest]) -> str:
    """The engine log line for a pack that declares flat forests."""
    s = summary(old)
    line = (f"[pack] {pack}: {s['total']} old flat (X-Plane 11) forest "
            f"definition(s); {s['mapped']} have an X-Plane 12 3D equivalent "
            f"({s['uses']} polygon(s))")
    if s["unmapped"]:
        line += (f", {s['unmapped']} have none and stay as they are "
                 f"— first: {s['first_unmapped'][0]}")
    return line
