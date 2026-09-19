"""IS THIS ``.anchor_bak`` STILL THE PACK'S ORIGINAL?  — the ONE decision
site (spec ``object-placement-spec.md`` §12a; owner RULINGS 2026-09-18k (2)
and 2026-09-18l).

Before this module the v2 write half created ``<dsf>.anchor_bak`` ONCE and
from then on re-encoded the live DSF from it, forever, without ever asking
whether the backup still belonged to the pack on disk.  A pack the user
updated IN PLACE therefore had its NEW DSF silently reverted from the OLD
backup — user data loss, invisible to the freshness gate because the gate
read the same stale backup.  v1 had the rule (invariant I-14); v2 recorded
the hashes and never read them.

THE RULE, in one place.  Every reader resolves its file through
:func:`classify_dsf` / :func:`classify_object` (``Verdict.read_path``);
every writer asks the same verdict whether it may write
(``Verdict.may_write``); and this module is the ONLY code that renames a
backup (:func:`adopt`).  Both classifiers are PURE — they never write — and
memoised on the ``(size, mtime_ns)`` of the live file, the backup and the
record, so an adoption or a write invalidates the memo by itself.

THE IDENTITY LADDER (cheapest first; a later rung runs only when the
earlier one does not decide):

1. ``size + mtime_ns`` equal to a recorded or sibling stat  ⇒ same file
   (the standard the freshness gate already uses);
2. size differs ⇒ NOT the same file, and no hash is computed;
3. ``sha256`` of the live file against the recorded hashes;
4. the IN-BAND witnesses — the ownership mark this writer now stamps into
   every DSF it writes (``PROPERTY o4/placement_rewrite <version>``,
   MEASURED to survive DSFTool ``text -> dsf -> text`` and to be findable
   by a raw byte scan of the encoded file, 2026-09-18), and, for DSFs
   written up to 1.0.351 which carry no mark, an ``OBJECT_DEF`` on a
   ``__b<digits>.obj`` name — a split body, which only this writer mints.

The witnesses make "is this file ours?" answerable FROM THE FILE, so a
lost, overwritten or half-written record can never again turn our own
output into "the user's".

THE OWNER'S ANSWERS (RULINGS 2026-09-18l) override two spec defaults:

* **Q1** — a leftover backup superseded by an in-place pack update is
  retired by RENAME (``.anchor_bak.superseded-<UTC>``), never deleted.
* **Q2** — when ownership CANNOT be proven (row D6: no record entry, no
  mark, no body-name witness), the app does NOT stand down.  It ASSUMES
  the live file is its own rewrite, first saves a stamped COPY of it
  beside it (``<name>.unrecognised-<UTC>``, never overwriting an existing
  copy), then rebuilds from the old backup, with one loud line naming the
  copy.  "It keeps working without asking, and if the guess is wrong your
  new DSF is replaced (but its copy is still in the folder)."

Only rows D2 (our own rewrite with the original GONE) and D8 (a backup we
cannot read) stand the write half down: neither has a pristine file to
rebuild from, and backing up our own output as "the original" is the one
act that destroys the original for good.
"""
from __future__ import annotations

import dataclasses as _dc
import enum
import hashlib
import json
import os
import re
import shutil
import typing as _t
from datetime import datetime, timezone

from ..model.placement import BACKUP_SUFFIX, PROVENANCE_FILENAME

__all__ = ["State", "Verdict", "BackupUnproven", "OWNERSHIP_PROPERTY",
           "SUPERSEDED_INFIX", "UNRECOGNISED_INFIX", "RECORD_VERSION",
           "classify_dsf", "classify_object", "adopt", "carries_our_mark",
           "backup_matches_record", "read_record", "dsf_entry",
           "update_dsf_entry", "record_path_for", "preserve_live_copy",
           "stamp", "invalidate_memo"]

#: The in-band ownership mark ``edit_dump`` writes into every DSF this
#: engine encodes.  MEASURED 2026-09-18 on a real pack DSF (TFFJ
#: ``+17-064.dsf``, DSFTool 2.4.0-b1): the row survives
#: ``--text2dsf`` -> ``--dsf2text`` unchanged and the property name is
#: present as a plain C string in the encoded file, so the raw byte scan
#: below finds it.
OWNERSHIP_PROPERTY = "o4/placement_rewrite"

#: A retired backup keeps its bytes under this infix FOREVER (Q1).  The
#: stamped name ends in neither ``.anchor_bak`` nor ``.dsf`` nor ``.obj``,
#: so no ``endswith`` walker, no dump-cache prefix filter and not X-Plane
#: ever reads it.
SUPERSEDED_INFIX = ".superseded-"

#: The stamped COPY of a live file whose ownership could not be proven
#: (Q2) — the bytes survive whatever the app decides to do next.
UNRECOGNISED_INFIX = ".unrecognised-"

#: ``o4_placement_provenance.json`` grew a per-DSF map (§12a (2)).
RECORD_VERSION = 2

#: only THIS writer mints a body on this name (§4.5)
_BODY_NAME = re.compile(rb"__b\d+\.obj")


class BackupUnproven(RuntimeError):
    """The write half stands down for this file (rows D2 / D8).

    ``apply_plan`` lets it through to the engine's ``_place_objects``,
    which prints the §12a (4) line and writes NOTHING — a half-written
    pack is torn geometry, so the refusal happens before the restore and
    before any cut file.
    """


class State(enum.Enum):
    NO_BACKUP = "no_backup"
    PRISTINE = "pristine"
    OURS = "ours"
    REPLACED = "replaced"
    UNPROVEN = "unproven"
    ORIGINAL_LOST = "original_lost"
    LIVE_MISSING = "live_missing"


@_dc.dataclass(frozen=True)
class Verdict:
    """What the one rule says about one (live, backup) pair."""

    state: State
    live: str
    backup: str
    #: what every READER opens
    read_path: str
    #: False => the write half stands down for THIS file
    may_write: bool
    #: "stat" | "sha256" | "mark" | "body-names" | "y-only" | ""
    witness: str = ""

    @property
    def row(self) -> str:
        """The §12a table row this verdict is, for a log line."""
        return _ROW.get((self.state, bool(self.backup)), "")


_ROW = {
    (State.NO_BACKUP, False): "D1",
    (State.ORIGINAL_LOST, False): "D2",
    (State.PRISTINE, True): "D3",
    (State.OURS, True): "D4",
    (State.REPLACED, True): "D5",
    (State.UNPROVEN, True): "D6",
    (State.LIVE_MISSING, True): "D7",
}


def stamp(now: datetime | None = None) -> str:
    """The UTC stamp every retired / preserved file carries."""
    return (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")


# ── stats, hashes and the in-band witnesses ─────────────────────────────

def _stat(path: str) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def _sha256(path: str) -> str | None:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def carries_our_mark(dsf_path: str) -> bool:
    """Whether the DSF at ``dsf_path`` carries this engine's ownership
    mark, by a RAW BYTE SCAN.

    DSFTool writes uncompressed DSFs and the PROP atom holds plain C
    strings, so the property NAME appears verbatim in the encoded file.
    A 7z-compressed DSF is never ours and the scan correctly finds
    nothing."""
    return _scan(dsf_path, OWNERSHIP_PROPERTY.encode("ascii"))


def _carries_body_names(dsf_path: str) -> bool:
    """The SECOND witness, for DSFs written up to 1.0.351 with no mark:
    an ``OBJECT_DEF`` on a ``__b<digits>.obj`` name — a split body, which
    only this writer mints (§4.5)."""
    return _scan(dsf_path, None, _BODY_NAME)


def _scan(path: str, needle: bytes | None,
          pattern: "re.Pattern[bytes] | None" = None) -> bool:
    """Stream ``path`` looking for ``needle`` / ``pattern``, with an
    overlap so a hit never falls across a chunk boundary."""
    tail = b""
    over = 64
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    return False
                buf = tail + chunk
                if needle is not None and needle in buf:
                    return True
                if pattern is not None and pattern.search(buf):
                    return True
                tail = buf[-over:]
    except OSError:
        return False


# ── the record (§12a (2)) ───────────────────────────────────────────────

def record_path_for(dsf_path: str) -> str:
    """``o4_placement_provenance.json`` beside ``dsf_path``."""
    return os.path.join(os.path.dirname(dsf_path), PROVENANCE_FILENAME)


def read_record(dsf_path: str) -> dict:
    """The record beside ``dsf_path``, or ``{}`` when there is none or it
    cannot be parsed.  NEVER raises: a garbled record is "no entry", which
    lands the caller in row D6, never in a crash."""
    try:
        with open(record_path_for(dsf_path), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def dsf_entry(record: _t.Mapping, basename: str) -> dict:
    """THIS DSF's entry, version 1 and version 2 alike.

    A version-1 record holds ONE DSF's hashes at the top level under a
    ``dsf`` field — it is this DSF's entry only when that field names it
    (the one-record-per-folder defect: a record naming a SIBLING DSF is
    "no entry", exactly as if the file had never been written)."""
    dsfs = record.get("dsfs")
    if isinstance(dsfs, dict):
        e = dsfs.get(basename)
        if isinstance(e, dict):
            return e
        return {}
    if record.get("dsf") == basename:
        return dict(record)
    return {}


def update_dsf_entry(dsf_path: str, fields: _t.Mapping,
                     *, top_level: _t.Mapping | None = None) -> str:
    """Read-modify-write THIS DSF's entry, atomically (§12a (2)).

    The top-level keys of the LAST write stay exactly as they are today
    (tools and ``v2_rebake_replay.py disk`` read them); the per-DSF map
    is what makes a sibling DSF's entry survive this one."""
    path = record_path_for(dsf_path)
    doc = read_record(dsf_path)
    if top_level:
        doc.update(dict(top_level))
    doc["version"] = RECORD_VERSION
    dsfs = doc.get("dsfs")
    if not isinstance(dsfs, dict):
        dsfs = {}
    base = os.path.basename(dsf_path)
    entry = dict(dsfs.get(base) or {})
    entry.update(dict(fields))
    dsfs[base] = entry
    doc["dsfs"] = dsfs
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)
    invalidate_memo()
    return path


# ── the DSF table ───────────────────────────────────────────────────────

_MEMO: dict[tuple, Verdict] = {}


def invalidate_memo() -> None:
    """Drop the in-process memo (a write or an adoption did happen)."""
    _MEMO.clear()


def _memo_key(live: str, backup: str, record: str | None) -> tuple:
    return (os.path.abspath(live), _stat(live), _stat(backup),
            None if record is None else _stat(record))


def _same_file(a: str, b: str, digest: dict) -> str:
    """``"stat"`` / ``"sha256"`` when ``a`` and ``b`` are the same bytes,
    else ``""``.  Rungs (i)-(iii) of the ladder."""
    sa, sb = _stat(a), _stat(b)
    if sa is None or sb is None:
        return ""
    if sa == sb:
        return "stat"
    if sa[0] != sb[0]:
        return ""                          # rung (ii): size differs, no hash
    ha, hb = _digest(a, digest), _digest(b, digest)
    return "sha256" if ha is not None and ha == hb else ""


def _digest(path: str, memo: dict) -> str | None:
    """sha256 of ``path``, computed at most once per classification."""
    if path not in memo:
        memo[path] = _sha256(path)
    return memo[path]


def _ours_by_stat(live: str, entry: _t.Mapping) -> str:
    """RUNG (i) ONLY — the recorded ``(size, mtime_ns)`` of what we last
    wrote.  THIS is the normal path: two stats, no read, no hash."""
    size = _stat(live)
    rec_size = entry.get("written_size")
    rec_mtime = entry.get("written_mtime_ns")
    if (size is not None and isinstance(rec_size, int)
            and isinstance(rec_mtime, int) and (rec_size, rec_mtime) == size):
        return "stat"
    return ""


def _ours_dsf(live: str, entry: _t.Mapping, digest: dict) -> str:
    """Rungs (ii)-(iv): the witness that ``live`` is OUR OWN output."""
    size = _stat(live)
    if size is None:
        return ""
    rec_size = entry.get("written_size")
    hashes = [h for h in (entry.get("written_sha256"),
                          entry.get("prior_written_sha256")) if h]
    if hashes:
        # rung (ii): a recorded SIZE that differs rules the ONE recorded
        # written hash out without reading a byte.
        skip = (isinstance(rec_size, int) and rec_size != size[0]
                and len(hashes) == 1)
        if not skip:
            h = _digest(live, digest)                       # rung (iii)
            if h is not None and h in hashes:
                return "sha256"
    if carries_our_mark(live):                              # rung (iv)
        return "mark"
    if _carries_body_names(live):
        return "body-names"
    return ""


def classify_dsf(dsf_path: str) -> Verdict:
    """THE DSF TABLE (§12a (1), rows D1-D8).  Pure: writes nothing.

    A path that already IS a backup is returned unchanged (never
    ``.anchor_bak.anchor_bak``), exactly as ``pristine_dsf_path`` has
    always done."""
    if not dsf_path or dsf_path.endswith(BACKUP_SUFFIX):
        return Verdict(State.PRISTINE, dsf_path, "", dsf_path, True, "")
    backup = dsf_path + BACKUP_SUFFIX
    key = _memo_key(dsf_path, backup, record_path_for(dsf_path))
    hit = _MEMO.get(key)
    if hit is not None:
        return hit
    v = _classify_dsf(dsf_path, backup)
    _MEMO[key] = v
    return v


def _classify_dsf(live: str, backup: str) -> Verdict:
    entry = dsf_entry(read_record(live), os.path.basename(live))
    digest: dict = {}
    live_there = os.path.isfile(live)
    bak_there = os.path.isfile(backup)

    if not bak_there:
        if not live_there:
            # nothing on disk at all: every caller's ``isfile`` skips, and
            # ``write_pack`` raises FileNotFoundError on its own
            return Verdict(State.NO_BACKUP, live, "", live, False, "")
        w = _ours_by_stat(live, entry) or _ours_dsf(live, entry, digest)
        if w:
            # D2: OUR rewrite, the original GONE.  Never back up our own
            # output as "the original" — that is the one act that
            # destroys the original for good.
            return Verdict(State.ORIGINAL_LOST, live, "", live, False, w)
        # D1: the pack as installed; today's first build
        return Verdict(State.NO_BACKUP, live, "", live, True, "")

    if _stat(backup) is None or not os.access(backup, os.R_OK):
        # D8: a backup we cannot read is a backup we cannot dump
        return Verdict(State.UNPROVEN, live, backup, live, False, "")
    if not live_there:
        # D7: the new version dropped this tile
        return Verdict(State.LIVE_MISSING, live, backup, live, False, "")

    # THE NORMAL PATH, FIRST AND ON STATS ALONE (D4): the pristine
    # compare below would otherwise sha256 BOTH files every build
    # whenever a rewrite happens to keep the pack's size (TFFJ: 26,678
    # bytes before and after — RULINGS 2026-09-18k (1)).
    w = _ours_by_stat(live, entry)
    if w:
        return Verdict(State.OURS, live, backup, backup, True, w)

    same = _same_file(live, backup, digest)
    if same:
        # D3: pristine — first build, or someone restored
        return Verdict(State.PRISTINE, live, backup, backup, True, same)

    w = _ours_dsf(live, entry, digest)
    if w:
        # D4: ours.  THE ONLY ROW THE NORMAL BUILD TAKES.
        return Verdict(State.OURS, live, backup, backup, True, w)

    if entry.get("written_sha256") or entry.get("prior_written_sha256") \
            or entry.get("backup_sha256"):
        # D5: an entry exists, the live file is neither the backup nor
        # anything we ever wrote — THE USER'S NEW FILE.
        return Verdict(State.REPLACED, live, backup, live, True, "")

    # D6: no entry, no mark, no body names.  OWNER Q2 (RULINGS
    # 2026-09-18l): do NOT stand down — assume the file is ours, keep a
    # stamped copy of it, and rebuild from the old backup.  The write
    # half calls ``preserve_live_copy`` first; the READ frame is the
    # backup, as it is today.
    return Verdict(State.UNPROVEN, live, backup, backup, True, "")


def backup_matches_record(dsf_path: str) -> bool:
    """Whether ``<dsf>.anchor_bak`` still matches its recorded hashes
    (D4's second check).

    A backup that no longer matches its record, under a live file that IS
    ours, is a USER ACT ON THE BACKUP: the build proceeds from it,
    re-records and says so once.  ``True`` when there is nothing recorded
    to disagree with — we never write the backup after creating it, so
    "no record" is not evidence of a change."""
    backup = dsf_path + BACKUP_SUFFIX
    entry = dsf_entry(read_record(dsf_path), os.path.basename(dsf_path))
    st = _stat(backup)
    if st is None:
        return True
    size, mtime = entry.get("backup_size"), entry.get("backup_mtime_ns")
    if isinstance(size, int) and isinstance(mtime, int):
        if (size, mtime) == st:
            return True                                     # rung (i)
        if size != st[0]:
            return False                                    # rung (ii)
    want = entry.get("backup_sha256")
    if not want:
        return True
    if isinstance(size, int) and size != st[0]:
        return False
    return _sha256(backup) == want                          # rung (iii)


# ── the OBJECT table ────────────────────────────────────────────────────

def _v1_sidecar(pack_root: str) -> dict:
    """v1's ``.o4_reanchor_provenance.json`` ``objects`` map."""
    try:
        with open(os.path.join(pack_root, ".o4_reanchor_provenance.json"),
                  encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    objs = doc.get("objects") if isinstance(doc, dict) else None
    return objs if isinstance(objs, dict) else {}


def _y_only(live: str, backup: str) -> bool:
    """v1's invariant I-16 as a WITNESS: a bake changes ``y`` tokens and
    nothing else — same line count, and every differing line has the same
    first token, the same token count, and differs only in tokens that
    parse as floats."""
    try:
        with open(live, "r", errors="replace") as fh:
            a = fh.read().splitlines()
        with open(backup, "r", errors="replace") as fh:
            b = fh.read().splitlines()
    except OSError:
        return False
    if len(a) != len(b) or not a:
        return False
    differing = 0
    for x, y in zip(a, b):
        if x == y:
            continue
        differing += 1
        tx, ty = x.split(), y.split()
        if not tx or not ty or len(tx) != len(ty) or tx[0] != ty[0]:
            return False
        for u, v in zip(tx, ty):
            if u == v:
                continue
            try:
                float(u), float(v)
            except ValueError:
                return False
    return differing > 0


def classify_object(obj_path: str, pack_root: str) -> Verdict:
    """THE OBJECT TABLE (§12a (1), rows O1-O7).  Pure: writes nothing.

    v2 never opens an authored ``.obj`` for writing, so an adopted object
    needs NO new backup — the stale one is retired and the file is simply
    the pack's.  ``may_write`` here means "the restore step may put the
    backup back over this live file"; the adopt/retire actions of rows
    O6 / O7 are keyed on ``state``."""
    if not obj_path or obj_path.endswith(BACKUP_SUFFIX):
        return Verdict(State.PRISTINE, obj_path, "", obj_path, False, "")
    backup = obj_path + BACKUP_SUFFIX
    key = _memo_key(obj_path, backup, None) + (os.path.abspath(pack_root),)
    hit = _MEMO.get(key)
    if hit is not None:
        return hit
    v = _classify_object(obj_path, backup, pack_root)
    _MEMO[key] = v
    return v


def _classify_object(live: str, backup: str, pack_root: str) -> Verdict:
    if not os.path.isfile(backup):
        # O1: nothing was ever baked here — the file IS the pack's
        return Verdict(State.NO_BACKUP, live, "", live, False, "")
    if not os.path.isfile(live):
        # O7: the new version dropped this object.  NEVER recreate it.
        return Verdict(State.LIVE_MISSING, live, backup, backup, False, "")

    sl, sb = _stat(live), _stat(backup)
    if sl is not None and sl == sb:
        # O2: nothing is read at all — two stats, and the restore step
        # does nothing (today both whole files are read on every build)
        return Verdict(State.PRISTINE, live, backup, backup, False, "stat")
    if sl is not None and sb is not None and sl[0] == sb[0]:
        # equal SIZE, different mtime: ONE byte compare decides O3 from a
        # same-size replacement.  After O3's ``utime`` this pair is row
        # O2 forever, so the compare is a first-build cost only.
        if _sha256(live) == _sha256(backup):
            # O3: same bytes, moved mtime — sync it and be O2 next time
            return Verdict(State.PRISTINE, live, backup, backup, True,
                           "sha256")

    rel = os.path.relpath(os.path.abspath(live),
                          os.path.abspath(pack_root)).replace(os.sep, "/")
    entry = _v1_sidecar(pack_root).get(rel) or {}
    want = entry.get("written_sha256")
    if want:
        if _sha256(live) == want:
            return Verdict(State.OURS, live, backup, backup, True, "sha256")
        # O6: a sidecar entry exists and the live file is not what it
        # says we wrote — the user's file.
        return Verdict(State.REPLACED, live, backup, live, False, "")
    if _y_only(live, backup):
        # O5: OURS by witness only — the restore keeps L's bytes FIRST
        return Verdict(State.OURS, live, backup, backup, True, "y-only")
    # O6: neither
    return Verdict(State.REPLACED, live, backup, live, False, "")


# ── the two WRITES this module owns ─────────────────────────────────────

def _free_name(base: str, infix: str, now: datetime | None) -> str:
    """``<base><infix><UTC stamp>``, never a name that already exists —
    v1's fixed ``.orphaned`` name silently destroyed the previous orphan
    every time a pack was updated twice."""
    first = base + infix + stamp(now)
    cand = first
    n = 1
    while os.path.exists(cand):
        cand = f"{first}-{n}"
        n += 1
    return cand


def preserve_live_copy(v: Verdict, *, now: datetime | None = None) -> str:
    """OWNER Q2: keep a stamped COPY of a live file whose ownership could
    not be proven, BEFORE anything is rebuilt over it.  Returns the copy's
    path (``""`` when there is no live file to copy)."""
    if not v.live or not os.path.isfile(v.live):
        return ""
    dest = _free_name(v.live, UNRECOGNISED_INFIX, now)
    shutil.copy2(v.live, dest)
    invalidate_memo()
    return dest


def adopt(v: Verdict, *, now: datetime | None = None) -> str:
    """Retire the superseded backup and (for a DSF) make the user's live
    file the new original.  Returns the SUPERSEDED path.

    In this order, exactly:

    1. ``os.replace(B, B + ".superseded-<UTC>")`` — RENAMED WITH A STAMP,
       NEVER DELETED, never overwritten by a later adoption (Q1);
    2. for a DSF whose live file is present, ``copy2(L, B + ".tmp")`` then
       ``os.replace`` onto B — ``copy2`` keeps L's size+mtime, which is
       what makes the freshness stamp converge on the NEXT build (§12a (3)
       row 9: exactly one rebuild).

    A crash between (1) and (2) leaves no B and the user's L — row D1,
    which is correct.  An OBJECT gets no step (2): v2 never opens an
    authored ``.obj`` for writing, so the file is simply the pack's."""
    if not v.backup or not os.path.isfile(v.backup):
        return ""
    superseded = _free_name(v.backup, SUPERSEDED_INFIX, now)
    os.replace(v.backup, superseded)
    if (v.state is State.REPLACED and v.live.lower().endswith(".dsf")
            and os.path.isfile(v.live)):
        tmp = v.backup + ".tmp"
        shutil.copy2(v.live, tmp)
        os.replace(tmp, v.backup)
    invalidate_memo()
    return superseded
