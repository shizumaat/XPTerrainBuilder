"""THE REBAKE PLAN'S EXTENSION, CACHED beside the partition (issue #362).

``pack_partition.extend_partition`` partitions the plate-exempt
multi-anchor placements back into the load reading — at OTHH 95 members,
27,690 parts, 282 s on EVERY build, warm or cold, because the partition
cache holds the load reading and nothing of this.  What it computes is a
pure function of:

* the load reading it extends — which the partition's own fingerprint
  pins (pack content, the dump, the law, the frame, the code:
  ``partition_cache``), and which is ALSO digested here from the object in
  hand (:func:`base_digest`), so a partition that is not the one this
  process fingerprinted can never be served another's extension;
* WHICH placements come back, and where each stands (:func:`added_digest`)
  — the plate set is a planar product, so it is the half the partition
  key cannot know.

The record is kept in the partition cache's COMPANION file
(``partition_cache.companion``): no partition cache, no extension cache.
A miss, an unreadable file or a refused write just computes — the build
never depends on it.
"""
from __future__ import annotations

import hashlib
import typing as _t

import numpy as np

from . import partition_cache as _pcache

__all__ = ["SUFFIX", "LABEL", "base_digest", "added_digest", "load", "store"]

#: Appended to the partition cache's own file name.  Bump the trailing
#: number when the SHAPE of the record changes.
SUFFIX = ".ext1"

#: The cache's name on its log line.
LABEL = "extension"


def _placement(o: _t.Any) -> tuple:
    """Everything the extension reads off one placement, as plain values."""
    return (o.id, o.path, o.resolved, tuple(float(v) for v in o.xy),
            float(o.heading_deg), float(o.agl_m), o.kind, float(o.anchor_z),
            o.deck_kind, o.hard_deck is None)


def base_digest(part: _t.Any) -> str | None:
    """sha256 of what the extension reads off the LOAD reading ``part``:
    the part boxes, their member / component / line / scatter columns and
    contact roots, every base member's placement and admitted components,
    the anchor numbering, the deck families, the counts and the skips.
    ``None`` for a reading with no load geometry (nothing to extend)."""
    geom = getattr(part, "geom", None)
    if geom is None:
        return None
    ix = geom.index
    h = hashlib.sha256()
    for name in ("box_lo", "box_hi", "member", "comp", "line", "root", "scatter"):
        a = getattr(ix, name, None)
        h.update(name.encode())
        if a is not None:
            a = np.ascontiguousarray(a)
            h.update(f"{a.dtype.str}{a.shape}".encode()); h.update(a.tobytes())
        h.update(b"\0")
    recipes = getattr(geom.members, "recipes", None)
    if recipes is None:
        return None
    for r in recipes:
        h.update(repr((_placement(r.obj), tuple(r.comps))).encode()); h.update(b"\n")
    for piece in (tuple(geom.member_ref), tuple(geom.anchor_of_member),
                  sorted(geom.anchor_ix.items()), sorted(geom.deck_family_ids),
                  part.icao, part.pack_name, part.pack_root,
                  sorted(part.counts.items()), tuple(part.skipped)):
        h.update(repr(piece).encode()); h.update(b"\0")
    return h.hexdigest()


def added_digest(add: _t.Sequence[tuple]) -> str:
    """sha256 of the placements coming back, IN ORDER: each one's anchor
    key and the placement fields the extension reads."""
    h = hashlib.sha256()
    for key, o in add:
        h.update(repr((tuple(key), _placement(o))).encode()); h.update(b"\n")
    return h.hexdigest()


def _slot(part: _t.Any, add: _t.Sequence[tuple]) -> "tuple[str, str] | None":
    base = base_digest(part)
    if base is None:
        return None
    return _pcache.companion(part.pack_root, part.icao, SUFFIX,
                             f"{base}|{added_digest(add)}")


def load(part: _t.Any, add: _t.Sequence[tuple]) -> _t.Any | None:
    """The record stored for extending ``part`` by ``add``, or ``None``.
    Leaves the ``[extension] cache HIT|MISS|OFF`` line (issue #395)."""
    slot = _slot(part, add)
    if slot is None:
        _pcache.companion_note(LABEL, "OFF", "(no partition cache on file to "
                               "keep it beside)")
        return None
    got = _pcache.read(*slot)
    _pcache.companion_note(LABEL, "MISS" if got is None else "HIT",
                           f"{slot[0]} ({len(add)} placement(s) coming back)")
    return got


def store(part: _t.Any, add: _t.Sequence[tuple], record: _t.Any) -> bool:
    """Keep ``record`` for the next build; ``False`` when there is no
    partition cache to keep it beside, or the write fails."""
    slot = _slot(part, add)
    if slot is None or not _pcache.write(*slot, record):
        return False
    _pcache.companion_note(LABEL, "WROTE", slot[0])
    return True
