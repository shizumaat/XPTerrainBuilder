#!/usr/bin/env python3
"""Resolve every resource a rewritten scenery DSF references, exactly as
X-Plane does, and diff it against our pristine ``.dsf.anchor_bak`` backup.

THE REGRESSION GUARD for the object stage's DSF rewrite (RULINGS
2026-09-13bl / 13bq).  The question it answers is not "does this pack
have broken references" — many shipped packs do — but the narrower,
adjudicating one: **did WE break it?**  A def that resolves in the
pristine dump and not in the live one is our defect; a def broken in
both is the pack's, and never fails the verdict.

Read-only, always.  It reads the data repo's content-keyed text dumps
(``Airport_mod_cache/<pack>/<tile>.dsf.<sha8>.text``) through
``dsf_reader.dsf_content_tag`` + ``_default_pack_text_cache_path`` +
``airport_mod_cache_dir`` and NEVER ``ensure_dsf_text_path`` (which
WRITES that cache).  On a cache miss it runs ``DSFTool --dsf2text`` into
its own scratch directory.  It writes nothing but that scratch dir,
stdout, and an optional ``--json`` target.

TWO TRAPS, both measured (RULINGS 13bq) and both twinned:

1. ``os.path.exists`` is CASE-INSENSITIVE on APFS and lies about what
   X-Plane will find.  Exact case is proven segment-by-segment against
   ``os.listdir``; a case-only match is reported as CASE-MISS with the
   on-disk spelling.
2. ``EXPORT_SEASON`` / ``EXPORT_EXCLUDE_SEASON`` / ``EXPORT_RATIO``
   carry ONE extra token before the virtual path.  Parsing them as the
   plain two-token form stranded 678 defs on the scout's first pass.

CLASSES per def
    PRISTINE-BROKEN  unresolved in BOTH dumps      (the pack's, not ours)
    OURS             resolves pristine, not live   (a path we garbled)
                     — also a pristine def missing from the live list
                       (``dropped-def``), and placements lost beyond
                       what the split bodies account for
                       (``dropped-placements``)
    OURS-NEW         live-only def that does NOT resolve
    OK-NEW           live-only def that resolves (our ``__b<n>`` bodies)
plus per-pack CASE-MISS, ORPHAN (``*.obj.anchor_bak`` with no original
beside it) and BODY-MISSING (a ``__b<n>.obj`` def not on disk at its
exact-case pack-relative path — a body must be pack-local, never a
library hit).

The object stage LAWFULLY moves an original's placements onto its
``__b<n>`` bodies, so those bodies' placements are credited back to the
original before a shortfall counts as ``dropped-placements``.

Usage (from ``Ortho4XP/``)::

    venv/bin/python tools/dsf_resource_audit.py --custom-scenery \\
        "/Users/noah/X-Plane 12/Custom Scenery"
    venv/bin/python tools/dsf_resource_audit.py "PACK DIR" [...] --json out.json

Exit 0 on ``VERDICT: CLEAN``, 1 on any OURS-class finding.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Sequence

# ── constants ────────────────────────────────────────────────────────

DEF_KINDS = ("OBJECT_DEF", "POLYGON_DEF", "NETWORK_DEF")

#: The placement keywords that index into each def table.
PLACEMENT_KEYWORDS = {
    "OBJECT": "OBJECT_DEF",
    "OBJECT_MSL": "OBJECT_DEF",
    "OBJECT_AGL": "OBJECT_DEF",
    "BEGIN_POLYGON": "POLYGON_DEF",
    "BEGIN_SEGMENT": "NETWORK_DEF",
    "BEGIN_SEGMENT_CURVED": "NETWORK_DEF",
}

#: All SEVEN library export forms.  The three in ``_EXPORT_SKIP_ONE``
#: carry one extra token (a ratio, or a season list) BEFORE the virtual
#: path — trap 2.
EXPORT_KEYWORDS = frozenset({
    "EXPORT",
    "EXPORT_BACKUP",
    "EXPORT_EXCLUDE",
    "EXPORT_EXTEND",
    "EXPORT_RATIO",
    "EXPORT_SEASON",
    "EXPORT_EXCLUDE_SEASON",
})
_EXPORT_SKIP_ONE = frozenset({
    "EXPORT_RATIO", "EXPORT_SEASON", "EXPORT_EXCLUDE_SEASON"})

#: A split body written by the object stage: ``<stem>__b<n>.obj``.
BODY_RE = re.compile(r"^(?P<stem>.+)__b\d+\.obj$", re.IGNORECASE)

# Resolution statuses.
PACK = "PACK"                    # exact-case pack-relative hit
PACK_CASE = "PACK_CASE"          # case-only hit — X-Plane would MISS it
LIB = "LIB"                      # a library export whose real file exists
LIB_DANGLING = "LIB_DANGLING"    # exported, but every real file missing
UNRESOLVED = "UNRESOLVED"

RESOLVED_STATUSES = frozenset({PACK, LIB})


# ── library index ────────────────────────────────────────────────────

def parse_library_file(path: str) -> Iterator[tuple[str, str, str]]:
    """Yield ``(keyword, virtual_path, real_path_relative)`` for every
    export line of one ``library.txt``.

    All seven ``EXPORT*`` forms; the ratio/season token is skipped."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split(None, 1)
        keyword = head[0]
        if keyword not in EXPORT_KEYWORDS or len(head) < 2:
            continue
        rest = head[1].strip()
        if keyword in _EXPORT_SKIP_ONE:
            parts = rest.split(None, 1)
            if len(parts) < 2:
                continue
            rest = parts[1].strip()
        parts = rest.split(None, 1)
        if len(parts) < 2:
            continue
        vpath, rpath = parts[0], parts[1].strip()
        if not vpath or not rpath:
            continue
        yield keyword, vpath, rpath


def find_library_files(roots: Sequence[str]) -> list[str]:
    """Every ``<root>/*/library.txt`` under each root directory."""
    out: list[str] = []
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            candidate = os.path.join(root, name, "library.txt")
            if os.path.isfile(candidate):
                out.append(candidate)
    return out


class LibraryIndex:
    """Virtual path -> the real files that export it.

    X-Plane matches virtual paths case-insensitively, so the index is
    keyed on the lowercased vpath.  Existence of the real file is probed
    LAZILY, on the first query for that vpath — 93k exports over 323
    libraries is half a million stats otherwise, almost all of them for
    paths nothing in the audited packs ever names."""

    def __init__(self) -> None:
        self._exports: dict[str, list[tuple[str, str]]] = {}
        self.library_files: list[str] = []
        self._probe_cache: dict[str, tuple[str, str | None]] = {}

    @classmethod
    def from_roots(cls, roots: Sequence[str]) -> "LibraryIndex":
        index = cls()
        for lib in find_library_files(roots):
            index.add_library_file(lib)
        return index

    def add_library_file(self, path: str) -> None:
        base = os.path.dirname(path)
        self.library_files.append(path)
        for _kw, vpath, rpath in parse_library_file(path):
            real = os.path.join(base, rpath.replace("\\", "/"))
            self._exports.setdefault(vpath.lower(), []).append((real, path))

    @property
    def vpath_count(self) -> int:
        return len(self._exports)

    def resolve(self, vpath: str) -> tuple[str, str | None]:
        """``(LIB, library.txt)``, ``(LIB_DANGLING, first real path)`` or
        ``(UNRESOLVED, None)``."""
        key = vpath.lower()
        hit = self._probe_cache.get(key)
        if hit is not None:
            return hit
        exports = self._exports.get(key)
        if not exports:
            result: tuple[str, str | None] = (UNRESOLVED, None)
        else:
            result = (LIB_DANGLING, exports[0][0])
            for real, lib in exports:
                if os.path.isfile(real):
                    result = (LIB, lib)
                    break
        self._probe_cache[key] = result
        return result


# ── exact-case pack-relative resolution (trap 1) ─────────────────────

class PackResolver:
    """Resolve a resource path the way X-Plane does: pack-relative with
    TRUE exact-case checking first, then the library index.

    ``os.path.exists`` is not used for the pack-relative probe — on a
    case-insensitive volume it reports a hit for a spelling X-Plane's
    own case-sensitive lookup would miss.  Every segment is matched
    against the parent directory's ``os.listdir``."""

    def __init__(self, pack_root: str, library: "LibraryIndex | None" = None):
        self.pack_root = pack_root
        self.library = library
        self._listing: dict[str, dict[str, str]] = {}

    def _entries(self, directory: str) -> dict[str, str]:
        cached = self._listing.get(directory)
        if cached is None:
            try:
                cached = {n.lower(): n for n in os.listdir(directory)}
            except OSError:
                cached = {}
            self._listing[directory] = cached
        return cached

    def pack_relative(self, rel: str) -> tuple[bool, str | None]:
        """``(exact_case_hit, on_disk_relative_spelling_or_None)``.

        The second element is the real on-disk spelling whenever the
        path resolves case-INsensitively — equal to ``rel`` when the
        first element is True, different when it is a CASE-MISS."""
        segments = [s for s in rel.replace("\\", "/").split("/")
                    if s and s != "."]
        if not segments:
            return False, None
        current = self.pack_root
        on_disk: list[str] = []
        exact = True
        for seg in segments:
            match = self._entries(current).get(seg.lower())
            if match is None:
                return False, None
            if match != seg:
                exact = False
            on_disk.append(match)
            current = os.path.join(current, match)
        if not os.path.isfile(current):
            return False, None
        return exact, "/".join(on_disk)

    def resolve(self, path: str) -> tuple[str, str | None]:
        """``(status, detail)`` — status is one of PACK / PACK_CASE /
        LIB / LIB_DANGLING / UNRESOLVED."""
        exact, on_disk = self.pack_relative(path)
        if exact:
            return PACK, None
        if on_disk is not None:
            return PACK_CASE, on_disk
        if self.library is not None:
            return self.library.resolve(path)
        return UNRESOLVED, None


# ── DSF text dumps ───────────────────────────────────────────────────

@dataclass
class Dump:
    """The def tables and placement counts of one DSF text dump."""

    defs: dict[str, list[str]] = field(
        default_factory=lambda: {k: [] for k in DEF_KINDS})
    counts: collections.Counter = field(default_factory=collections.Counter)

    def placements(self, kind: str, index: int) -> int:
        return self.counts.get((kind, index), 0)

    def by_path(self, kind: str) -> collections.Counter:
        """Placement count summed per def PATH (a path may in principle
        appear at two indices)."""
        out: collections.Counter = collections.Counter()
        for index, path in enumerate(self.defs[kind]):
            out[path] += self.placements(kind, index)
        return out

    def paths(self, kind: str) -> list[str]:
        return self.defs[kind]


def parse_dump(lines: Iterable[str]) -> Dump:
    """Parse a DSFTool ``--dsf2text`` dump into its def tables and
    per-def placement counts."""
    dump = Dump()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        head = line.split(None, 1)
        keyword = head[0]
        if keyword in DEF_KINDS:
            dump.defs[keyword].append(head[1].strip() if len(head) > 1 else "")
            continue
        kind = PLACEMENT_KEYWORDS.get(keyword)
        if kind is None:
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            index = int(fields[1])
        except ValueError:
            continue
        dump.counts[(kind, index)] += 1
    return dump


def parse_dump_file(path: str) -> Dump:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse_dump(fh)


def pack_root_for_dsf(dsf_path: str) -> str | None:
    """The pack root of a DSF in either shipped layout: grouped
    (``<pack>/Earth nav data/+40-010/+40-004.dsf``) or flat
    (``<pack>/Earth nav data/+40-004.dsf``)."""
    parent = os.path.dirname(os.path.abspath(dsf_path))
    grandparent = os.path.dirname(parent)
    if os.path.basename(parent) == "Earth nav data":
        return grandparent
    if os.path.basename(grandparent) == "Earth nav data":
        return os.path.dirname(grandparent)
    return None


def _dsf_reader():
    """The engine's ``auto_patch.dsf_reader``, imported lazily.

    The single seam every cache lookup goes through, so a test can
    substitute it without touching ``sys.modules`` (importing the real
    engine is neither needed nor wanted in the twin)."""
    from auto_patch import dsf_reader
    return dsf_reader


def mod_cache_root() -> str | None:
    """The ``Airport_mod_cache`` root this run will READ.

    Printed with every run because it follows the cwd in a source
    checkout: a lane worktree without the shared repo's cache resolves
    to its own empty directory and every dump becomes a DSFTool miss —
    the same numbers, but a slower and differently-framed measurement.
    Point ``O4_AIRPORT_MOD_CACHE_DIR`` at the shared repo's cache to
    read the dumps a build already warmed."""
    try:
        import O4_File_Names as _FNAMES
        return _FNAMES.airport_mod_cache_root()
    except Exception:
        return None


def cached_dump_path(dsf_path: str) -> str | None:
    """The data repo's content-keyed dump for this DSF, if it exists.

    Reuses the engine's own naming so the cache a build warmed is the
    cache we read.  NEVER calls ``ensure_dsf_text_path``: that WRITES."""
    pack_root = pack_root_for_dsf(dsf_path)
    if pack_root is None:
        return None
    try:
        dsf_reader = _dsf_reader()
    except Exception:
        return None
    try:
        cache_dir = dsf_reader.airport_mod_cache_dir(pack_root)
        if not cache_dir:
            return None
        candidate = dsf_reader._default_pack_text_cache_path(
            cache_dir, dsf_path)
        tag = dsf_reader.dsf_content_tag(dsf_path)
    except Exception:
        return None
    if os.path.isfile(candidate):
        return candidate
    # The cache key is basename + content tag, so a pristine
    # ``X.dsf.anchor_bak`` whose dump was taken BEFORE the rewrite (when
    # those same bytes still sat at ``X.dsf``) is filed under the live
    # basename.  Same content tag, same bytes, same dump — measured at
    # VHHH 2026-09-13.  Accept it; still a read.
    if os.path.basename(dsf_path).endswith(".dsf.anchor_bak"):
        alias = os.path.join(
            cache_dir, f"{os.path.basename(dsf_path)[:-len('.anchor_bak')]}"
                       f".{tag}.text")
        if os.path.isfile(alias):
            return alias
    return None


def dsftool_dump(dsf_path: str, scratch_dir: str) -> str | None:
    """Run ``DSFTool --dsf2text`` into ``scratch_dir`` (the cache-MISS
    path).  Never writes the data repo or the pack."""
    try:
        tool = _dsf_reader()._dsftool_path()
    except Exception:
        tool = None
    if not tool:
        return None
    os.makedirs(scratch_dir, exist_ok=True)
    import hashlib
    key = hashlib.sha1(os.path.abspath(dsf_path).encode("utf-8")).hexdigest()[:8]
    out = os.path.join(scratch_dir,
                       f"{os.path.basename(dsf_path)}.{key}.text")
    try:
        subprocess.run([tool, "--dsf2text", dsf_path, out],
                       check=True, capture_output=True)
    except Exception:
        return None
    return out if os.path.isfile(out) else None


def load_dump(dsf_path: str, scratch_dir: str,
              cache_only: bool = False) -> tuple["Dump | None", str]:
    """``(Dump, provenance)`` — cache first, DSFTool into scratch on a
    miss.  Provenance is ``cache`` / ``dsftool`` / ``missing``."""
    cached = cached_dump_path(dsf_path)
    if cached:
        return parse_dump_file(cached), "cache"
    if cache_only:
        return None, "missing"
    produced = dsftool_dump(dsf_path, scratch_dir)
    if produced:
        return parse_dump_file(produced), "dsftool"
    return None, "missing"


# ── pack discovery ───────────────────────────────────────────────────

def find_tile_pairs(pack_root: str) -> list[tuple[str, str]]:
    """``(live_dsf, pristine_anchor_bak)`` for every tile of this pack
    the object stage has rewritten.  Both shipped layouts."""
    end = os.path.join(pack_root, "Earth nav data")
    pairs: list[tuple[str, str]] = []
    if not os.path.isdir(end):
        return pairs
    for dirpath, _dirnames, filenames in os.walk(end):
        for name in sorted(filenames):
            if not name.endswith(".dsf.anchor_bak"):
                continue
            pristine = os.path.join(dirpath, name)
            live = pristine[:-len(".anchor_bak")]
            if os.path.isfile(live):
                pairs.append((live, pristine))
    return sorted(pairs)


def discover_packs(custom_scenery: str) -> list[str]:
    """Every pack under a Custom Scenery root carrying our backup."""
    out: list[str] = []
    if not os.path.isdir(custom_scenery):
        return out
    for name in sorted(os.listdir(custom_scenery)):
        pack = os.path.join(custom_scenery, name)
        if os.path.isdir(pack) and find_tile_pairs(pack):
            out.append(pack)
    return out


def find_orphan_backups(pack_root: str) -> list[str]:
    """``*.obj.anchor_bak`` files under the pack whose ``X.obj`` is
    gone — a backup we made of a file that no longer exists."""
    orphans: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(pack_root):
        for name in filenames:
            if not name.endswith(".obj.anchor_bak"):
                continue
            backup = os.path.join(dirpath, name)
            original = backup[:-len(".anchor_bak")]
            if not os.path.isfile(original):
                orphans.append(os.path.relpath(backup, pack_root))
    return sorted(orphans)


# ── the audit ────────────────────────────────────────────────────────

PRISTINE_BROKEN = "PRISTINE-BROKEN"
OURS = "OURS"
OURS_NEW = "OURS-NEW"
OK_NEW = "OK-NEW"
OK = "OK"
CASE_MISS = "CASE-MISS"
ORPHAN = "ORPHAN"
BODY_MISSING = "BODY-MISSING"

#: Sub-kinds recorded on an OURS row (all three count as OURS).
OURS_GARBLED = "garbled-path"
OURS_DROPPED_DEF = "dropped-def"
OURS_DROPPED_PLACEMENTS = "dropped-placements"

#: The classes that make the verdict DEFECT.  PRISTINE-BROKEN never does.
FAILING = (OURS, OURS_NEW, CASE_MISS, ORPHAN, BODY_MISSING)


@dataclass
class PackReport:
    pack: str
    tiles: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)
    live_defs: int = 0
    pristine_defs: int = 0
    provenance: list[str] = field(default_factory=list)

    def count(self, cls: str) -> int:
        if cls == ORPHAN:
            return len(self.orphans)
        if cls == CASE_MISS:
            return sum(1 for r in self.rows if r["case_miss"])
        if cls == BODY_MISSING:
            return sum(1 for r in self.rows if r["body_missing"])
        return sum(1 for r in self.rows if r["cls"] == cls)

    def placements(self, cls: str) -> int:
        return sum(max(r["pristine_n"], r["live_n"])
                   for r in self.rows if r["cls"] == cls)

    def paths(self, cls: str) -> set[str]:
        if cls == CASE_MISS:
            return {r["path"] for r in self.rows if r["case_miss"]}
        if cls == BODY_MISSING:
            return {r["path"] for r in self.rows if r["body_missing"]}
        if cls == ORPHAN:
            return set(self.orphans)
        return {r["path"] for r in self.rows if r["cls"] == cls}

    @property
    def failures(self) -> int:
        return sum(self.count(c) for c in FAILING)


def _body_stem(path: str) -> str | None:
    m = BODY_RE.match(path)
    return m.group("stem") if m else None


def audit_pack(pack_root: str,
               live: Dump,
               pristine: Dump,
               library: "LibraryIndex | None" = None,
               tile: str = "",
               orphans: "Sequence[str] | None" = None) -> PackReport:
    """Classify every def of one (live, pristine) dump pair.

    Pure apart from the filesystem reads resolution needs: it touches
    only the pack directory and the library index."""
    resolver = PackResolver(pack_root, library)
    report = PackReport(pack=os.path.basename(os.path.abspath(pack_root)))
    if tile:
        report.tiles.append(tile)
    report.orphans = list(orphans if orphans is not None
                          else find_orphan_backups(pack_root))

    for kind in DEF_KINDS:
        live_paths = live.paths(kind)
        pristine_paths = pristine.paths(kind)
        report.live_defs += len(live_paths)
        report.pristine_defs += len(pristine_paths)
        live_counts = live.by_path(kind)
        pristine_counts = pristine.by_path(kind)
        live_set = set(live_paths)
        pristine_set = set(pristine_paths)
        live_index_of = {p: i for i, p in enumerate(live_paths)}

        # Placements the split bodies of a pristine path account for.
        body_credit: collections.Counter = collections.Counter()
        for path, n in live_counts.items():
            stem = _body_stem(path)
            if stem is not None:
                body_credit[stem + ".obj"] += n

        seen: set[str] = set()
        ordered = live_paths + [p for p in pristine_paths if p not in live_set]
        for path in ordered:
            if path in seen:
                continue
            seen.add(path)
            in_live = path in live_set
            in_pristine = path in pristine_set
            live_n = live_counts.get(path, 0)
            pristine_n = pristine_counts.get(path, 0)

            live_status, live_detail = (
                resolver.resolve(path) if in_live else (None, None))
            pristine_status, pristine_detail = (
                resolver.resolve(path) if in_pristine else (None, None))

            live_ok = live_status in RESOLVED_STATUSES
            pristine_ok = pristine_status in RESOLVED_STATUSES

            sub = ""
            if not in_live:
                cls, sub = OURS, OURS_DROPPED_DEF
            elif not in_pristine:
                cls = OK_NEW if live_ok else OURS_NEW
            elif not live_ok and not pristine_ok:
                cls = PRISTINE_BROKEN
            elif not live_ok and pristine_ok:
                cls, sub = OURS, OURS_GARBLED
            else:
                cls = OK

            shortfall = 0
            if in_pristine and cls in (OK, PRISTINE_BROKEN):
                credited = live_n + body_credit.get(path, 0)
                if credited < pristine_n:
                    shortfall = pristine_n - credited
                    cls, sub = OURS, OURS_DROPPED_PLACEMENTS

            case_miss = (live_status == PACK_CASE
                         or pristine_status == PACK_CASE)
            body_missing = False
            if in_live and _body_stem(path) is not None:
                exact, _on_disk = resolver.pack_relative(path)
                body_missing = not exact

            report.rows.append({
                "pack": report.pack,
                "tile": tile,
                "kind": kind,
                "path": path,
                "cls": cls,
                "sub": sub,
                "live_index": live_index_of.get(path),
                "live_n": live_n,
                "pristine_n": pristine_n,
                "shortfall": shortfall,
                "live_status": live_status,
                "pristine_status": pristine_status,
                "resolved_by": (live_detail if live_status == LIB
                                else (pristine_detail
                                      if pristine_status == LIB else None)),
                "on_disk": (live_detail if live_status == PACK_CASE
                            else (pristine_detail
                                  if pristine_status == PACK_CASE else None)),
                "case_miss": case_miss,
                "body_missing": body_missing,
            })
    return report


def merge_reports(reports: Sequence[PackReport]) -> PackReport:
    """Fold several tiles of one pack into a single report."""
    first = reports[0]
    merged = PackReport(pack=first.pack)
    for r in reports:
        merged.tiles.extend(r.tiles)
        merged.rows.extend(r.rows)
        merged.live_defs += r.live_defs
        merged.pristine_defs += r.pristine_defs
        merged.provenance.extend(r.provenance)
    merged.orphans = first.orphans
    return merged


# ── rendering ────────────────────────────────────────────────────────

_HDR = "  {:<8} {:>5}  {:<58} {:<28} {:>9}  {}"


def _table(report: PackReport, verbose: bool) -> list[str]:
    shown = [r for r in report.rows
             if verbose or r["cls"] not in (OK, OK_NEW)
             or r["case_miss"] or r["body_missing"]]
    if not shown:
        return []
    lines = [_HDR.format("KIND", "IDX", "PATH", "CLASS", "LIVE/PRIS",
                         "RESOLVED-BY")]
    for r in sorted(shown, key=lambda r: (r["cls"], r["kind"], r["path"])):
        cls = f"{r['cls']}:{r['sub']}" if r["sub"] else r["cls"]
        extra = r["resolved_by"] or ""
        if r["on_disk"]:
            extra = f"CASE-MISS on-disk={r['on_disk']}"
        elif LIB_DANGLING in (r["live_status"], r["pristine_status"]):
            extra = "LIB-DANGLING"
        if r["body_missing"]:
            extra = (extra + " BODY-MISSING").strip()
        lines.append(_HDR.format(
            r["kind"].replace("_DEF", ""),
            "-" if r["live_index"] is None else r["live_index"],
            r["path"][-58:], cls[:28],
            f"{r['live_n']}/{r['pristine_n']}", extra))
    return lines


def summary_line(report: PackReport) -> str:
    return ("  SUMMARY {pack}: defs live={live} pristine={pris} | "
            "PRISTINE-BROKEN {pb} defs/{pbp} placements | OURS {ours} | "
            "OURS-NEW {onew} | OK-NEW {oknew} | CASE-MISS {cm} | "
            "ORPHAN {orph} | BODY-MISSING {bm}").format(
        pack=report.pack, live=report.live_defs, pris=report.pristine_defs,
        pb=report.count(PRISTINE_BROKEN),
        pbp=report.placements(PRISTINE_BROKEN),
        ours=report.count(OURS), onew=report.count(OURS_NEW),
        oknew=report.count(OK_NEW), cm=report.count(CASE_MISS),
        orph=report.count(ORPHAN), bm=report.count(BODY_MISSING))


def verdict_line(reports: Sequence[PackReport]) -> tuple[str, int]:
    totals = {c: sum(r.count(c) for r in reports) for c in FAILING}
    if not sum(totals.values()):
        return "VERDICT: CLEAN", 0
    parts = ", ".join(f"{c} {n}" for c, n in totals.items() if n)
    return f"VERDICT: DEFECT ({parts})", 1


def render(reports: Sequence[PackReport], verbose: bool = False) -> list[str]:
    out: list[str] = []
    for report in reports:
        out.append("=" * 78)
        out.append(f"PACK {report.pack}  tiles={','.join(report.tiles)}"
                   f"  dumps={','.join(report.provenance)}")
        out.extend(_table(report, verbose))
        for o in report.orphans:
            out.append(f"  ORPHAN  {o}")
        out.append(summary_line(report))
    return out


# ── CLI ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Audit DSF resource references, live vs pristine "
                    ".anchor_bak (RULINGS 2026-09-13bl/13bq).")
    p.add_argument("packs", nargs="*", metavar="PACK_DIR",
                   help="scenery pack directories to audit")
    p.add_argument("--custom-scenery", metavar="ROOT",
                   help="audit every pack under ROOT holding a "
                        "*.dsf.anchor_bak")
    p.add_argument("--xplane", metavar="XP_ROOT",
                   help="X-Plane root supplying Resources/default scenery "
                        "libraries (default: the Custom Scenery parent)")
    p.add_argument("--scratch", metavar="DIR",
                   help="scratch dir for DSFTool dumps on a cache miss "
                        "(default: a tempfile.mkdtemp)")
    p.add_argument("--cache-only", action="store_true",
                   help="never run DSFTool; a cache miss is reported")
    p.add_argument("--json", metavar="OUT", dest="json_out",
                   help="write every row as JSON")
    p.add_argument("--verbose", action="store_true",
                   help="list OK and OK-NEW rows too")
    return p


def main(argv: "Sequence[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)

    packs = [os.path.abspath(p) for p in args.packs]
    custom_scenery = (os.path.abspath(args.custom_scenery)
                      if args.custom_scenery else None)
    if custom_scenery:
        packs.extend(discover_packs(custom_scenery))
    if not packs:
        print("no packs: pass PACK_DIR or --custom-scenery ROOT",
              file=sys.stderr)
        return 2
    if custom_scenery is None:
        parent = os.path.dirname(packs[0])
        custom_scenery = parent if os.path.isdir(parent) else None

    xplane = args.xplane
    if not xplane and custom_scenery:
        xplane = os.path.dirname(custom_scenery)
    roots = [r for r in (
        custom_scenery,
        os.path.join(xplane, "Resources", "default scenery") if xplane else None,
    ) if r]
    library = LibraryIndex.from_roots(roots)
    print(f"libraries: {len(library.library_files)} library.txt, "
          f"{library.vpath_count} virtual paths")
    print(f"dump cache (READ-ONLY): {mod_cache_root() or 'unresolved'}")

    scratch = args.scratch or tempfile.mkdtemp(prefix="dsf_resource_audit.")
    reports: list[PackReport] = []
    for pack in packs:
        pairs = find_tile_pairs(pack)
        if not pairs:
            print(f"  SKIP {os.path.basename(pack)}: no *.dsf.anchor_bak")
            continue
        orphans = find_orphan_backups(pack)
        per_tile: list[PackReport] = []
        for live_dsf, pristine_dsf in pairs:
            tile = os.path.basename(live_dsf)[:-len(".dsf")]
            live, live_prov = load_dump(live_dsf, scratch, args.cache_only)
            pristine, pris_prov = load_dump(
                pristine_dsf, scratch, args.cache_only)
            if live is None or pristine is None:
                print(f"  SKIP {os.path.basename(pack)} {tile}: no dump "
                      f"(live={live_prov} pristine={pris_prov})")
                continue
            r = audit_pack(pack, live, pristine, library, tile=tile,
                           orphans=orphans)
            r.provenance.append(f"{live_prov}/{pris_prov}")
            per_tile.append(r)
        if per_tile:
            reports.append(merge_reports(per_tile))

    for line in render(reports, args.verbose):
        print(line)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"packs": [{
                "pack": r.pack, "tiles": r.tiles,
                "live_defs": r.live_defs, "pristine_defs": r.pristine_defs,
                "orphans": r.orphans, "rows": r.rows} for r in reports]},
                fh, indent=1)

    verdict, code = verdict_line(reports)
    print(verdict)
    return code


if __name__ == "__main__":  # pragma: no cover
    _here = os.path.dirname(os.path.abspath(__file__))
    _src = os.path.join(os.path.dirname(_here), "src")
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
    sys.exit(main())
