"""``patch_roles`` / ``patch_role_set`` — the patch editor's hand-set
pavement classification (protocol 1.33, issue #1697): read, set or clear
the role a user gave one pack pavement, as a user edit the classifier
honours on every rebuild (``auto_patch_v2/airport/user_roles``).

The role is written at once beside the patch (it is not part of the patch
file, so saving or reverting the patch neither writes nor drops it); the
editor's Undo sends the previous role back.  The next build of the tile
regrades the whole airport from the classify stage with it — the stages
before classify come from the stage cache.

A patch way names its pavement by ``ref`` (``pav131``, ``pav54#2``,
``dsf:pol267``); an apt.dat pavement's identity is its ring
(``user_roles.ring_key``), read here through the loader's own apt.dat
reader (``load.read_apt``: the pack the build selects, the §44 borrow
composed), so the row names exactly the pavement the build will read; a
DSF pavement's is the pack's signature.  Every change is also one line of the
classifier-evidence log (``user_roles.EVIDENCE_FILENAME`` in the Patches
folder): where a user said the classifier was wrong.  Synchronous: one
apt.dat block read.
"""
from __future__ import annotations

import datetime as _dt
import os

import O4_File_Names as FNAMES

__all__ = ["patch_roles", "patch_role_set"]


def _patch_dir(tile: str) -> tuple[str, int, int]:
    parsed = FNAMES.parse_tile_key(tile)
    if parsed is None:
        raise ValueError(f"patch_role_set: {tile!r} is not a tile key like +45-123.")
    return FNAMES.patch_dir(*parsed), parsed[0], parsed[1]


def _choices() -> list[dict]:
    from auto_patch_v2.airport.user_roles import CHOOSABLE
    return [{"role": r, "label": label} for r, label in CHOOSABLE]


def patch_roles(tile: str, icao: str) -> dict:
    """ENGINE COMMAND ``patch_roles``: ``{choices: [{role, label}],
    overrides: [{source, role, was, description, set_at}], path}`` — the
    roles a shape can be given and the hand-set ones beside the patch (an
    unreadable file reads as none)."""
    from auto_patch_v2.airport import user_roles as _ur
    patch_dir, _lat, _lon = _patch_dir(tile)
    try:
        rows = _ur.read(patch_dir, icao)
    except (OSError, ValueError):
        rows = {}
    return {"choices": _choices(),
            "overrides": [{k: v for k, v in rows[s].to_dict().items() if k not in ("ring", "pack")}
                          for s in sorted(rows)],
            "path": os.path.basename(_ur.roles_path(patch_dir, icao))}


def _identity(icao: str, lat: int, lon: int, source: str) -> tuple[str, str, str]:
    """``(ring, pack, description)`` of ``source`` in the pack the build
    reads: an apt.dat pavement by its ring (the loader's own reader), a
    DSF one by the pack's signature (``patch_library.key.pack_now``, the
    library's cached one) — ``user_roles``' two identities."""
    from auto_patch_v2.airport import user_roles as _ur
    from auto_patch_v2.airport.load import read_apt
    from auto_patch_v2.law import Law

    from .pack_objects import xplane_root_for
    xroot = xplane_root_for(lat, lon)
    if not xroot:
        raise ValueError("No X-Plane folder is set for this tile, so its airport pack "
                         "cannot be read.")
    if source.startswith("dsf:"):
        from patch_library import key as _key
        return "", str(_key.pack_now(xroot, icao, lat, lon).get("signature", "")), ""
    _sel, _block, apt, _bres, frame = read_apt(str(icao).upper(), xroot,
                                               Law.for_airport(icao), "")
    for p in apt.pavements:
        if f"pav{p.index}" == source and p.rings:
            return _ur.ring_key(p.rings[0], frame.identity_dp), "", p.description or ""
    raise ValueError(f"The airport's pack has no pavement {source}; rebuild the tile and "
                     f"select the shape again.")


def _evidence(tile: str, icao: str, source: str, row, previous, was: str) -> None:
    """One line of the classifier-evidence log (``<Patches>/``
    ``o4_classifier_evidence.jsonl``, user data): the role set or cleared
    and the classifier's own verdict.  A log that cannot be written never
    refuses the edit."""
    import O4_Version
    from auto_patch_v2.airport import user_roles as _ur
    done = row or previous
    line = {"at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tile": tile, "icao": str(icao).upper(), "source": source,
            "action": "set" if row is not None else "cleared",
            "role": row.role if row is not None else None,
            "previous_role": previous.role if previous is not None else None,
            "classified_as": (done.was if done is not None else "") or was,
            "ring": done.ring if done is not None else "",
            "description": done.description if done is not None else "",
            "engine": getattr(O4_Version, "version", "")}
    try:
        _ur.record_evidence(FNAMES.Patch_dir, line)
    except OSError:
        pass


def patch_role_set(tile: str, icao: str, ref: str, role: str | None = None,
                   was: str = "") -> dict:
    """ENGINE COMMAND ``patch_role_set``: the pack pavement the way ``ref``
    belongs to is classified ``role`` by hand on every rebuild; no ``role``
    clears it (the classifier decides again).  ``was`` is the role the
    shape showed (the evidence that the classifier was wrong).  Replies
    ``{source, role, previous_role, description, path}`` —
    ``previous_role`` is what an Undo sends."""
    from auto_patch_v2.airport import user_roles as _ur
    source = _ur.source_of(ref)
    if source is None:
        raise ValueError(f"This shape ({ref or 'no ref'}) is not one of the pack's pavements; "
                         f"only a pack pavement's classification can be changed.")
    choices = {c["role"] for c in _choices()}
    role = str(role) if role else None
    if role is not None and role not in choices:
        raise ValueError(f"patch_role_set: {role!r} is not a pavement role a shape can be "
                         f"given ({', '.join(sorted(choices))}).")
    patch_dir, lat, lon = _patch_dir(tile)
    row = None
    description = ""
    if role is not None:
        ring, pack, description = _identity(icao, lat, lon, source)
        previous = _ur.read(patch_dir, icao).get(source)
        row = _ur.RoleOverride(
            source, ring, role,
            was=(previous.was if previous is not None else str(was or "")),
            description=description,
            set_at=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            pack=pack)
    previous = _ur.set_role(patch_dir, icao, row, source=source)
    _evidence(tile, icao, source, row, previous, str(was or ""))
    return {"source": source, "role": role,
            "previous_role": None if previous is None else previous.role,
            "description": description or (previous.description if previous else ""),
            "path": os.path.basename(_ur.roles_path(patch_dir, icao))}
