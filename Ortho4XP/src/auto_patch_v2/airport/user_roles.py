"""HAND-SET PAVEMENT ROLES (issue #1697): the classification a user gave a
pack pavement in the patch editor, and the one rule the classifier applies
it by.

A hand-set role is a USER EDIT (owner RULINGS 2026-10-15d: what the user
edits is what gets built): the classifier never overrides it.  It is an
INPUT to the solve, not an edit of the emitted patch, so the next build
regrades the whole airport from the classify stage with it (grading is
airport-wide: one shape's law moves its neighbours), and it survives every
rebuild and every pack update that leaves its pavement alone.

The file, beside the patch: ``o4_user_roles_<ICAO>.json``::

    {"version": 1, "icao": "KXYZ",
     "roles": [{"source": "pav131", "ring": "<sha256>", "role": "apron",
                "was": "junction", "description": "Apron 3",
                "set_at": "2026-11-03T04:00:00Z", "pack": ""},
               {"source": "dsf:pol267", "ring": "", "role": "primary_parallel",
                "pack": "<pack signature>", ...}, ...]}

THE IDENTITY (never proximity).  ``source`` is the id the build names the
pavement by: ``pav<N>`` for an apt.dat row 110, ``dsf:pol<N>`` /
``dsf:objpav<N>`` for one the pack draws in its DSF.  An apt.dat row also
carries ``ring``, :func:`ring_key` of its exterior ring — its vertices as
canonical ``model.frame.identity_key`` lat/lon keys, sorted, hashed — and
is honoured only where the pavement under that id still has that ring, so
it survives a pack update that leaves it alone.  A DSF pavement is read
only by the full load, so its row carries the PACK SIGNATURE instead
(``pack``: ``pack_identity.pack_signature``) and is honoured only while
the pack is that one.  A row that no longer names its pavement is named
and skipped, never moved to a neighbour.  ``was`` is the role the
classifier gave the shape the user changed — every row is also EVIDENCE
that the classifier was wrong there (#1697), which a general fix can read.

The rows are the shape the patch library's ``edits.json`` carries for role
overrides (``docs/specs/patch-library-phase2-20261102.md`` §10): one row per
source, keyed by ring or pack, no airport-specific field.

:func:`apply` is pure: every cell of a hand-set source whose role is a
pavement role (:data:`CHOOSABLE`) takes the hand-set role and its side;
a source's runway, shoulder, building or strip cells keep theirs.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import json
import os
import re
import tempfile
import typing as _t

__all__ = ["ROLES_FILENAME", "EVIDENCE_FILENAME", "CHOOSABLE", "RoleOverride", "roles_path",
           "ring_key", "source_of", "read", "set_role", "lay_rows", "digest", "record_evidence",
           "for_pack", "resolve", "apply"]

#: ``<patch dir>/o4_user_roles_<ICAO>.json``.
ROLES_FILENAME = "o4_user_roles_{icao}.json"
_VERSION = 1
#: ``<Patches>/o4_classifier_evidence.jsonl``: one line per hand-set role
#: set or cleared, on every airport — the user's own record of where the
#: classifier was wrong, for a general fix to read (never read by a build).
EVIDENCE_FILENAME = "o4_classifier_evidence.jsonl"
#: The pavement roles a user may give a shape, with the words both apps
#: show (the register's own names; ``precedence.toml`` holds each).
CHOOSABLE: tuple[tuple[str, str], ...] = (
    ("apron", "Apron"),
    ("primary_parallel", "Taxiway: primary parallel"),
    ("secondary_parallel", "Taxiway: secondary parallel"),
    ("cross_connector", "Taxiway: cross connector"),
    ("stub", "Taxiway: stub"),
    ("junction", "Taxiway: junction"),
    ("service_road", "Service road"),
    ("service_junction", "Service road junction"),
    ("parking_lot", "Parking lot"),
    ("groundside_pavement", "Groundside pavement"),
)
_ROLES = frozenset(r for r, _label in CHOOSABLE)
#: The source id a cell's ``ref`` starts with (``pav131``, ``pav54#2``,
#: ``dsf:pol267``, ``dsf:objpav3#1``).
_SOURCE = re.compile(r"^(pav\d+|dsf:pol\d+|dsf:objpav\d+)(?:[#:].*)?$")


@_dc.dataclass(frozen=True)
class RoleOverride:
    """One hand-set role."""

    source: str
    ring: str
    role: str
    was: str = ""
    description: str = ""
    set_at: str = ""
    pack: str = ""

    def to_dict(self) -> dict:
        return _dc.asdict(self)

    @classmethod
    def from_dict(cls, d: _t.Mapping) -> "RoleOverride":
        return cls(str(d["source"]), str(d["ring"]), str(d["role"]), str(d.get("was", "")),
                   str(d.get("description", "")), str(d.get("set_at", "")),
                   str(d.get("pack", "")))


def roles_path(patch_dir: str, icao: str) -> str:
    return os.path.join(patch_dir, ROLES_FILENAME.format(icao=str(icao).upper()))


def ring_key(ring_lonlat: _t.Iterable[tuple[float, float]], dp: int) -> str:
    """The identity of a pavement's exterior ring: each vertex's canonical
    ``model.frame.identity_key`` at ``dp`` places, sorted (start and winding
    free), hashed."""
    from ..model.frame import identity_key
    keys = sorted({identity_key(lat, lon, dp) for lon, lat in ring_lonlat})
    return hashlib.sha256(";".join(f"{la!r},{lo!r}" for la, lo in keys).encode("ascii")).hexdigest()


def source_of(ref: str) -> str | None:
    """The apt.dat pavement id a cell or patch way's ``ref`` belongs to, or
    ``None`` (a minted strip, a road ribbon, a building pad...)."""
    m = _SOURCE.match(str(ref or ""))
    return m.group(1) if m else None


def read(patch_dir: str, icao: str) -> dict[str, RoleOverride]:
    """``{source: override}``; empty when there is no file.  Raises
    ``ValueError`` on a file this version cannot read."""
    path = roles_path(patch_dir, icao)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("version") != _VERSION:
        raise ValueError(f"{os.path.basename(path)}: version {doc.get('version')!r} "
                         f"is not {_VERSION}")
    return {o.source: o for o in (RoleOverride.from_dict(d) for d in doc.get("roles") or ())}


def _write(patch_dir: str, icao: str, rows: _t.Mapping[str, RoleOverride]) -> str:
    """Write ``rows`` atomically (none left: the file is removed)."""
    path = roles_path(patch_dir, icao)
    if not rows:
        if os.path.isfile(path):
            os.remove(path)
        return path
    os.makedirs(patch_dir, exist_ok=True)
    doc = {"version": _VERSION, "icao": str(icao).upper(),
           "roles": [rows[k].to_dict() for k in sorted(rows)]}
    fd, tmp = tempfile.mkstemp(prefix=".roles-", suffix=".tmp", dir=patch_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def set_role(patch_dir: str, icao: str, row: RoleOverride | None, *,
             source: str) -> RoleOverride | None:
    """Set (``row``) or clear (``None``) ``source``'s hand-set role; returns
    the row it replaced."""
    if row is not None and row.role not in _ROLES:
        raise ValueError(f"{row.role!r} is not a pavement role a shape can be given")
    rows = read(patch_dir, icao)
    previous = rows.pop(source, None)
    if row is not None:
        rows[source] = row
    _write(patch_dir, icao, rows)
    return previous


def lay_rows(patch_dir: str, icao: str, rows: _t.Iterable[_t.Mapping]) -> int:
    """Write ``rows`` (``RoleOverride.to_dict`` shapes, a library entry's
    ``role_overrides``) as the airport's hand-set roles where it has none
    of its own; returns how many were laid (0: none given, or the user's
    own file stays)."""
    got = {o.source: o for o in (RoleOverride.from_dict(d) for d in rows or ())
           if o.role in _ROLES}
    if not got or os.path.isfile(roles_path(patch_dir, icao)):
        return 0
    _write(patch_dir, icao, got)
    return len(got)


def digest(patch_dir: str, icao: str) -> str:
    """``o4_user_roles``, the patch's freshness stamp of its hand-set roles:
    one digest of each row's ``(source, ring, pack, role)`` — what the solve
    reads, not when or why it was set — ``"none"`` for none, ``"unreadable"``
    for a file this version cannot read (the loader applies none)."""
    try:
        rows = read(patch_dir, icao)
    except (OSError, ValueError, KeyError):
        return "unreadable"
    if not rows:
        return "none"
    text = ";".join(f"{o.source},{o.ring},{o.pack},{o.role}" for _s, o in sorted(rows.items()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def record_evidence(log_dir: str, line: _t.Mapping) -> str:
    """Append ``line`` (one set or cleared role) to the evidence log in
    ``log_dir``; returns its path."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, EVIDENCE_FILENAME)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(dict(line), sort_keys=True) + "\n")
    return path


def for_pack(rows: _t.Iterable[RoleOverride], signature: _t.Callable[[], str]
             ) -> tuple[tuple[RoleOverride, ...], tuple[str, ...]]:
    """``(rows, refusals)``: the rows keyed by ring, and those keyed by pack
    (a DSF pavement) whose pack is still ``signature()`` — asked only when
    such a row exists (the build's caller; the loader knows no pack
    signature)."""
    rows = tuple(rows)
    now = signature() if any(not o.ring for o in rows) else ""
    keep = tuple(o for o in rows if o.ring or o.pack == now)
    return keep, tuple(f"{o.source} ({o.description or 'pavement'}): the pack has changed "
                       f"since its classification was set" for o in rows if o not in keep)


def resolve(rows: _t.Iterable[RoleOverride], pavements: _t.Iterable, dp: int,
            sources: _t.Collection[str] = ()
            ) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """``(((source, role), ...), refusals)``: each row keyed by ring whose
    ``source`` is still an apt.dat pavement (``AptPavement``: ``index``,
    ``rings``) with that ring, and each keyed by pack (:func:`for_pack`
    checked it) whose ``source`` is among the model's pavement ids
    ``sources``.  The loader calls it, where the pack's own coordinates
    are."""
    rings = {f"pav{p.index}": ring_key(p.rings[0], dp) for p in pavements if p.rings}
    take: list[tuple[str, str]] = []
    refused: list[str] = []
    for o in sorted(rows, key=lambda o: o.source):
        if o.role not in _ROLES:
            refused.append(f"{o.source}: {o.role!r} is not a pavement role")
        elif not (rings.get(o.source) == o.ring if o.ring else o.source in sources):
            refused.append(f"{o.source} ({o.description or 'pavement'}) is not the pavement "
                           f"it was when its classification was set; the pack has changed")
        else:
            take.append((o.source, o.role))
    return tuple(take), tuple(refused)


def apply(cells: _t.Sequence, overrides: _t.Iterable[tuple[str, str]],
          side_of: _t.Callable[[str], str]) -> tuple[list, int]:
    """``(cells, changed)``: every pavement-role cell of a hand-set source
    in its hand-set role (``side_of(role)`` its side), ``evidence`` naming
    the classifier's own verdict."""
    want = dict(overrides)
    if not want:
        return list(cells), 0
    out, changed = [], 0
    for c in cells:
        role = want.get(source_of(c.ref) or "")
        if role is None or c.role not in _ROLES or c.role == role:
            out.append(c)
            continue
        out.append(_dc.replace(c, role=role, side=side_of(role),
                               evidence={**c.evidence, "user_role": role,
                                         "classified_as": c.role}))
        changed += 1
    return out, changed
