"""A PLACED PART'S READINGS, KEPT ACROSS BUILDS (#2176 census recommendation
2, lane ``lfilecache``).

``contact.part_attrs`` — a part's ground feet, its footprint outline (one
shapely union per part, ``contact.plan_hull``) and its solid height — is
114 + 16 + 3 s of KMCI's serial pack stage and 99 + 16 + 2 s of KATL's,
paid again on every build whose partition cache missed (any pack-code
edit).  It is a function of the component's own geometry and of where the
placement puts it, nothing else.

WHY NOT ONCE PER FILE, PLACED RIGIDLY.  Measured on KMCI (this lane), the
census's own proposal does not hold the reading: read in the file's frame
and turned per placement, 35,200 of 81,226 parts' rings changed (1,063 by
more than 0.5 m), 191 parts crossed the 2.5 m walled gate and the cluster
count went 17,662 -> 17,783; read at the placement's HEADING and only
translated, 3,905 rings still changed (35 by more than 0.5 m) and the
clusters went 17,662 -> 17,699.  The outline is not equivariant to the
float: its outward fit doubles a tolerance until an exact ``covers``
predicate holds, splits across an axis-aligned box and decimates a hull
from its lexicographically first vertex, and the solid height reads 1 m
plan cells on the frame's own grid.  So the readings are kept per FILE but
keyed by everything ``part_attrs`` reads of the placement — exactly — and a
hit is the reading the placing would derive, bit for bit.

KEY (per file content, in the per-file store, kind ``part``): the
component index, the placement's heading, anchor ``xy``, ``anchor_z``,
``agl_m`` and ``zero_y``, the line / scatter class, and the four foot
numbers.  A pack whose DSF, DEM at the anchors and files did not change is
served whole; any of them moved is a miss for that placement only.
"""
from __future__ import annotations

import typing as _t

__all__ = ["PartBook"]


def _part_key(ci: int, o: _t.Any, is_line: bool, is_scat: bool, params: tuple) -> tuple:
    """Everything ``contact.part_attrs`` reads of component ``ci`` placed
    by ``o`` (module doc), as exact values."""
    return (int(ci), float(o.heading_deg), float(o.xy[0]), float(o.xy[1]),
            float(o.anchor_z), float(o.agl_m), float(o.zero_y), bool(is_line),
            bool(is_scat), tuple(float(p) for p in params))


class PartBook:
    """One build's view of the kept part readings (module doc).
    ``files``: the per-file store, or ``None`` (nothing is held)."""

    def __init__(self, files: _t.Any = None) -> None:
        self.files = files
        self._by_path: dict[str, dict] = {}
        self._dirty: set[str] = set()
        #: the keys this build asked, per file: a file written back keeps
        #: only these (a moved placement's old reading is not kept forever)
        self._asked: dict[str, set] = {}

    def _of(self, path: str) -> dict:
        got = self._by_path.get(path)
        if got is None:
            kept = None
            if self.files is not None:
                from .file_readings import MISSING
                kept = self.files.get("part", path)
                kept = None if kept is MISSING else kept
            got = self._by_path[path] = dict(kept or {})
        return got

    @staticmethod
    def _classes(mi: int, lines: _t.AbstractSet[int], scat: _t.AbstractSet[int]
                 ) -> tuple[bool, bool]:
        is_line = mi in lines
        return is_line, (mi in scat and not is_line)

    def held(self, members: _t.Sequence, lines: _t.Collection[int],
             scat: _t.Collection[int], params: tuple) -> list:
        """Per member, its parts' ``(feet, rings, solid_h)`` when every one
        is kept, else ``None`` — the ``attrs`` of ``contact.partition``."""
        lines, scat = set(lines), set(scat)
        out: list = []
        for mi, (o, geom, comps) in enumerate(members):
            is_line, is_scat = self._classes(mi, lines, scat)
            book = self._of(str(geom.path)) if comps else {}
            keys = [_part_key(ci, o, is_line, is_scat, params) for ci, _c in comps]
            self._asked.setdefault(str(geom.path), set()).update(keys)
            row = [book.get(k) for k in keys]
            out.append(row if comps and all(r is not None for r in row) else None)
        return out

    def take(self, members: _t.Sequence, lines: _t.Collection[int],
             scat: _t.Collection[int], params: tuple, parts: _t.Sequence,
             held: _t.Sequence) -> int:
        """Keep the readings of the placed ``parts`` of every member
        ``held`` did not serve; returns how many members were kept."""
        lines, scat = set(lines), set(scat)
        by_member: dict[int, list] = {}
        for p in parts:
            by_member.setdefault(p.member, []).append(p)
        n = 0
        for mi, (o, geom, comps) in enumerate(members):
            if held[mi] is not None or not comps:
                continue
            is_line, is_scat = self._classes(mi, lines, scat)
            book = self._of(str(geom.path))
            got = {p.comp: p for p in by_member.get(mi, ())}
            for ci, _c in comps:
                p = got.get(ci)
                if p is not None:
                    book[_part_key(ci, o, is_line, is_scat, params)] = (
                        p.feet, p.rings, p.solid_h)
            self._dirty.add(str(geom.path))
            n += 1
        return n

    def commit(self) -> int:
        """Hand every file read here to the store; returns how many."""
        n = 0
        if self.files is not None:
            for path in sorted(self._dirty):
                asked = self._asked.get(path, set())
                self.files.put("part", path, {k: v for k, v in self._by_path[path].items()
                                              if k in asked})
                n += 1
        self._dirty.clear()
        return n
