"""MISSING ART: the definitions a pack DSF declares that are not installed
(owner RULINGS 2026-10-06c, issue #433).

X-Plane drops a WHOLE scenery pack when its DSF declares one definition
whose file it cannot find (``E/SCN: Failed to find resource … DSF canceled
due to missing art assets … err=15``).  This module owns the two halves of
the ruling, both pure and both general — any pack, any tile:

* THE CHECK — :func:`missing_definitions`: every ``OBJECT_DEF`` /
  ``POLYGON_DEF`` / ``NETWORK_DEF`` / ``TERRAIN_DEF`` of a DSFTool text
  dump, resolved the way X-Plane resolves it: a file under the pack
  folder, else a virtual path some installed ``library.txt`` exports
  (``obj8.resolve_resource`` — the ONE resolver, over the engine's merged
  library index).  ``RASTER_DEF`` rows name data layers, not files, and
  ``terrain_Water`` is built into the simulator: neither is ever missing.
  A STOCK ``lib/…`` path is X-Plane's own catalogue and is never called
  missing either: the merged index does not model every way the
  simulator exports its catalogue (measured 2026-10-06 over 216 cached
  pack dumps: 437 distinct stock paths the index lacks —
  ``lib/g10/autogen/*.ags``, the deciduous ``.for`` forests — in packs
  that load).  A wrong "X-Plane will not load this pack" is worse than
  none, so the same holds for any name another ``EXPORT*`` directive
  mentions (``also_exported``).
* THE OMISSION — :func:`omit_definitions`: the dump text without the
  missing definitions and without every placement, polygon and network
  segment that uses one, the surviving rows renumbered.  A row that
  survives changes in its definition INDEX token only; every other byte
  of it is copied.

WHAT COUNTS AS MISSING.  The file system the pack is installed on
answers, exactly as it answers X-Plane's own ``open``: a reference that
differs from the file on disk only in letter case is present on a
case-insensitive volume and missing on a case-sensitive one.  ``\\`` and
``:`` are read as ``/`` (packs authored on Windows / classic Mac OS).
WITHOUT a library index nothing can be called missing — a virtual path
would read as absent — so the check then answers nothing (``None``),
never a guess.

A missing ``TERRAIN_DEF`` is REPORTED but cannot be omitted: its patches
are the mesh itself, and a DSF without them has a hole in the ground
(:func:`can_omit`).
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import os
import re
import typing as _t

from .obj8 import is_stock_library_resource, resolve_resource

__all__ = ["MissingDef", "DEF_KINDS", "FIRST_PATHS", "declared_definitions",
           "missing_definitions", "omit_definitions", "can_omit",
           "decision_key", "kind_counts", "first_paths", "summary",
           "log_line", "accepted", "record"]

#: definition keyword -> the kind name the event and the record carry
DEF_KINDS = {"OBJECT_DEF": "object", "POLYGON_DEF": "polygon",
             "NETWORK_DEF": "network", "TERRAIN_DEF": "terrain"}
#: the rows that USE a definition (token 1 is its index) -> kind
USE_ROWS = {"OBJECT": "object", "OBJECT_MSL": "object", "OBJECT_AGL": "object",
            "BEGIN_POLYGON": "polygon", "BEGIN_SEGMENT": "network",
            "BEGIN_SEGMENT_CURVED": "network", "BEGIN_PATCH": "terrain"}
#: a use row that opens a BLOCK, and the keyword that closes it
BLOCK_END = {"BEGIN_POLYGON": "END_POLYGON", "BEGIN_SEGMENT": "END_SEGMENT",
             "BEGIN_SEGMENT_CURVED": "END_SEGMENT_CURVED",
             "BEGIN_PATCH": "END_PATCH"}
#: names X-Plane resolves with no file
BUILT_IN = frozenset({"terrain_water"})
#: the kinds :func:`omit_definitions` may remove
OMITTABLE = frozenset({"object", "polygon", "network"})
#: how many paths the warning names
FIRST_PATHS = 5

_INDEX = re.compile(r"^(\s*\S+\s+)(\d+)")


@_dc.dataclass(frozen=True)
class MissingDef:
    """One declared definition X-Plane will not find.  ``index`` is its
    position among the definitions of its ``kind``; ``uses`` the rows of
    the DSF that place it."""

    kind: str
    index: int
    path: str
    uses: int = 0

    def to_dict(self) -> dict[str, _t.Any]:
        return _dc.asdict(self)


def _lines(source: str | _t.Iterable[str]) -> _t.Iterator[str]:
    """The rows of a dump — a PATH is opened (utf-8, undecodable bytes
    kept as themselves: resource paths are bytes to X-Plane), any other
    iterable is read as the rows."""
    if isinstance(source, str):
        with open(source, "r", encoding="utf-8", errors="surrogateescape") as fh:
            yield from fh
    else:
        yield from source


def declared_definitions(source: str | _t.Iterable[str]) -> dict[str, list[str]]:
    """``{kind: [path, ...]}`` in declaration order.  Reads the dump's
    HEAD only: DSFTool writes every definition before the first data row,
    so the read stops there (the OTHH dump: 1,859 of 236,778 lines)."""
    out: dict[str, list[str]] = {k: [] for k in DEF_KINDS.values()}
    for raw in _lines(source):
        kw, _, rest = raw.partition(" ")
        kind = DEF_KINDS.get(kw)
        if kind is not None:
            out[kind].append(rest.strip())
        elif kw.strip() in USE_ROWS:
            break
    return out


def _present(path: str, pack_root: str,
             index: _t.Mapping[str, str]) -> bool:
    p = path.replace("\\", "/").replace(":", "/")
    if p.lower() in BUILT_IN or is_stock_library_resource(p):
        return True
    return (resolve_resource(p, pack_root, index) is not None
            or (p != path and resolve_resource(path, pack_root, index) is not None))


def _count_uses(source: str | _t.Iterable[str],
                wanted: _t.AbstractSet[tuple[str, int]]) -> dict[tuple[str, int], int]:
    uses: dict[tuple[str, int], int] = dict.fromkeys(wanted, 0)
    for raw in _lines(source):
        kw, _, rest = raw.partition(" ")
        kind = USE_ROWS.get(kw)
        if kind is None:
            continue
        try:
            key = (kind, int(rest.split(None, 1)[0]))
        except (ValueError, IndexError):
            continue
        if key in uses:
            uses[key] += 1
    return uses


def missing_definitions(pack_root: str, source: str | _t.Sequence[str],
                        index: _t.Mapping[str, str] | None,
                        also_exported: _t.Callable[[], _t.Container[str]] | None = None
                        ) -> tuple[MissingDef, ...] | None:
    """THE CHECK.  Every definition ``source`` (a dump path, or its rows)
    declares that neither the pack folder nor the library index provides,
    with the number of rows that use it; ``()`` when all are installed.

    ``None`` when ``index`` is ``None``: without the installed libraries a
    virtual path cannot be told from a missing file, so nothing is said.
    ``also_exported`` answers the LOWER-CASED names the index does not
    carry but an installed library still exports; it is asked — and the
    dump's body read, once — only when something looks missing."""
    if index is None:
        return None
    absent = [(kind, i, path)
              for kind, paths in declared_definitions(source).items()
              for i, path in enumerate(paths)
              if path and not _present(path, pack_root, index)]
    if absent and also_exported is not None:
        names = also_exported()
        absent = [a for a in absent
                  if a[2].replace("\\", "/").lower() not in names]
    if not absent:
        return ()
    uses = _count_uses(source, {(k, i) for k, i, _p in absent})
    return tuple(MissingDef(k, i, p, uses[(k, i)]) for k, i, p in absent)


def can_omit(missing: _t.Iterable[MissingDef]) -> bool:
    """Whether a DSF without ``missing`` is still a whole DSF: every kind
    but a terrain definition (module doc)."""
    return all(m.kind in OMITTABLE for m in missing)


def omit_definitions(text: str, missing: _t.Iterable[MissingDef]
                     ) -> tuple[str, dict[str, int]]:
    """THE OMISSION (pure).  ``text`` without each definition in
    ``missing`` — matched by kind, index AND path, so a list that does
    not describe this text raises ``ValueError`` — and without every row
    or block that uses one; the indices of what stays are renumbered.

    Returns the text and ``{"<kind>_defs": n, "<kind>_uses": n}``."""
    gone: dict[tuple[str, int], str] = {}
    for m in missing:
        if m.kind not in OMITTABLE:
            raise ValueError(f"a {m.kind} definition cannot be omitted: {m.path!r}")
        gone[(m.kind, m.index)] = m.path
    counts: dict[str, int] = {}
    if not gone:
        return text, counts
    removed_idx: dict[str, list[int]] = {}
    for kind, i in gone:
        removed_idx.setdefault(kind, []).append(i)
    for v in removed_idx.values():
        v.sort()
    seen: dict[str, int] = {}
    matched = 0
    out: list[str] = []
    skip_until: str | None = None
    for raw in text.splitlines(keepends=True):
        kw, _, rest = raw.partition(" ")
        kw = kw.strip()
        if skip_until is not None:
            if kw == skip_until:
                skip_until = None
            continue
        kind = DEF_KINDS.get(kw)
        if kind is not None:
            i = seen.get(kind, 0)
            seen[kind] = i + 1
            if (kind, i) in gone:
                if rest.strip() != gone[(kind, i)]:
                    raise ValueError(
                        f"{kw} {i} is {rest.strip()!r}, not {gone[(kind, i)]!r}")
                matched += 1
                counts[kind + "_defs"] = counts.get(kind + "_defs", 0) + 1
                continue
            out.append(raw)
            continue
        kind = USE_ROWS.get(kw)
        if kind is None or kind not in removed_idx:
            out.append(raw)
            continue
        m = _INDEX.match(raw)
        if m is None:
            out.append(raw)
            continue
        i = int(m.group(2))
        if (kind, i) in gone:
            counts[kind + "_uses"] = counts.get(kind + "_uses", 0) + 1
            skip_until = BLOCK_END.get(kw)
            continue
        below = sum(1 for r in removed_idx[kind] if r < i)
        out.append(raw if not below
                   else f"{m.group(1)}{i - below}{raw[m.end():]}")
    if matched != len(gone):
        raise ValueError(f"{len(gone) - matched} definition(s) to omit are not "
                         f"declared by this DSF")
    return "".join(out), counts


# ── what the warning, the record and the decision read ──────────────────

def kind_counts(missing: _t.Iterable[MissingDef]) -> dict[str, int]:
    """``{kind: definitions missing}``, kinds in ``DEF_KINDS`` order."""
    out: dict[str, int] = {}
    for kind in DEF_KINDS.values():
        n = sum(1 for m in missing if m.kind == kind)
        if n:
            out[kind] = n
    return out


def first_paths(missing: _t.Sequence[MissingDef]) -> list[str]:
    return [m.path for m in missing[:FIRST_PATHS]]


def summary(missing: _t.Sequence[MissingDef]) -> dict[str, _t.Any]:
    """The fields the ``PackMissingArt`` event carries."""
    return {"total": len(missing), "kinds": kind_counts(missing),
            "uses": sum(m.uses for m in missing),
            "first_paths": first_paths(missing),
            "can_omit": can_omit(missing)}


def log_line(pack: str, missing: _t.Sequence[MissingDef]) -> str:
    """The engine log line (owner-fixed wording, RULINGS 2026-10-06c)."""
    kinds = ", ".join(f"{n} {k}" for k, n in kind_counts(missing).items())
    return (f"[pack] {pack}: {len(missing)} definition(s) the DSF declares "
            f"are not installed ({kinds}); X-Plane will not load this pack "
            f"— first: {missing[0].path}")


def decision_key(pristine_sha256: str, missing: _t.Iterable[MissingDef]) -> str:
    """What an accepted omission is keyed to: the pack's PRISTINE DSF
    content and the SET of missing paths.  A pack update, or art that was
    restored (or lost) since, is a different key — and a new question."""
    h = hashlib.sha256(pristine_sha256.encode("ascii", "replace"))
    for row in sorted(f"{m.kind}\t{m.path}" for m in missing):
        h.update(b"\n" + row.encode("utf-8", "surrogateescape"))
    return h.hexdigest()


def record(pristine_sha256: str, missing: _t.Sequence[MissingDef],
           counts: _t.Mapping[str, int], time: str) -> dict[str, _t.Any]:
    """The ``omitted_art`` entry of ``o4_placement_provenance.json``."""
    return {"accepted": True, "time": time,
            "key": decision_key(pristine_sha256, missing),
            "pristine_sha256": pristine_sha256,
            "counts": dict(counts),
            "definitions": [m.to_dict() for m in missing]}


def accepted(entry: _t.Mapping[str, _t.Any] | None, pristine_sha256: str,
             missing: _t.Iterable[MissingDef]) -> bool:
    """Whether the user ALREADY accepted this exact omission: the record's
    key is the key of this pristine DSF and this missing set."""
    row = (entry or {}).get("omitted_art")
    return (isinstance(row, dict) and row.get("accepted") is True
            and row.get("key") == decision_key(pristine_sha256, missing))
