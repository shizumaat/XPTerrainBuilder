"""AN AIRPORT ENTRY, PACKAGED FROM A BUILT TILE (#1699 phase 2).

What an entry carries is the census of spec §2: the airport's PATCH
FAMILY (``O4_Unpatched_Airports.airport_patch_family`` — the patch, its
``.axes.json`` sidecar, the graded surface, the object plan and screen,
the companion plans), each read by a later step of the user's build, and
the user's EDITS (the patch editor's ``<ICAO>_edited.patch.osm``, and the
pavements classified by hand — #1697 ``auto_patch_v2.airport.user_roles``
rows — as ``edits.json``'s ``role_overrides``).  Not carried: the
object stage's local refusal marker, the build log, the tile-wide
object-anchor worklist (the user's build writes its own), imagery, and
anything of a scenery pack.

The patch must be what this app would build NOW for the installed pack
(the reuse gate's own stale-input list, ``auto_patch.driver.
auto_patch_stale_inputs``): a stale patch is refused, so an entry's law
and signature are the ones that really solved it.  Every local path is
tokenised (``tile_bundle.paths``, the tile bundles' one implementation)
and every file is xz-compressed; the result is checked with the
library's own checks (:mod:`.checks`) before anything leaves the app.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import os
import time

from . import FORMAT, LICENCE, LibraryRefused
from . import key as _key
from . import layout as L
from . import terms as _terms

__all__ = ["NOT_MATCHED_STAMPS", "REQUIRED", "package", "write_folder"]

#: Stamps a stale value of which does not refuse a publish: the
#: publisher's data snapshot, which an entry exists to spare the receiver
#: (:mod:`.key`).
NOT_MATCHED_STAMPS = ("o4_dem", "o4_osm", "o4_cifp", "o4_imagery", "o4_tools")

#: The family members an entry cannot do without.
REQUIRED = ("{icao}_auto.patch.osm", "{icao}_auto.patch.osm.axes.json",
            "{icao}.graded.json")

_XZ_PRESET = 6
_REFUSED_SUFFIX = ".screen.refused"


def _role_rows(patch_dir: str, icao: str) -> list:
    """The airport's hand-set pavement roles as ``edits.json`` carries them
    (no local path in a row: source id, ring digest, role, the evidence)."""
    from auto_patch_v2.airport import user_roles as _ur
    try:
        rows = _ur.read(patch_dir, icao)
    except (OSError, ValueError) as exc:
        raise LibraryRefused("%s's hand-set classifications are unreadable (%s)"
                             % (icao, exc)) from exc
    return [rows[s].to_dict() for s in sorted(rows)]


def _family(patch_dir: str, icao: str) -> list:
    """``[(name, path)]`` of the airport's solved files on disk."""
    import O4_Unpatched_Airports as UNPATCHED
    out = []
    for path in UNPATCHED.airport_patch_family(patch_dir, icao):
        name = os.path.basename(path)
        if name.endswith(_REFUSED_SUFFIX) or not os.path.isfile(path):
            continue
        if L.SOLVED_NAME_RE.match(name):
            out.append((name, path))
    names = {n for n, _p in out}
    missing = [r.format(icao=icao) for r in REQUIRED
               if r.format(icao=icao) not in names]
    if missing:
        raise LibraryRefused("%s has no %s in this tile: build the tile with "
                             "airport grading on, then publish" % (icao, missing[0]))
    return sorted(out)


def _require_current(tile, icao: str, patch: str, xp_root: str) -> dict:
    from auto_patch import driver as _driver
    from auto_patch.build_support import read_patch_source
    meta = read_patch_source(patch)
    if not meta or not meta.get("freshness"):
        raise LibraryRefused("%s's patch carries no build stamps; build the "
                             "tile again, then publish" % icao)
    stale = [k for k, _was, _now in _driver.auto_patch_stale_inputs(
        meta, patch, xp_root, icao, tile=tile) if k not in NOT_MATCHED_STAMPS]
    if stale:
        raise LibraryRefused(
            "%s's patch is not what this app would build now (%s changed "
            "since). Build the tile again, then publish." % (icao, stale[0]))
    return meta


def _xz(data: bytes) -> bytes:
    return lzma.compress(data, preset=_XZ_PRESET)


def _attribution(manifest: dict) -> bytes:
    lines = ["%s — XPTerrainBuilder airport patch, version %d" % (
        manifest["icao"], manifest["version"]), "",
        "For the scenery pack: %s" % manifest["pack"]["name"], "",
        "Derived from:"]
    lines += [_terms.source_line(s) for s in manifest["sources"]]
    lines += ["", _terms.statement(manifest["licence"]), ""]
    return "\n".join(lines).encode("utf-8")


def package(tile, icao: str, *, kind: str, publisher: str, version: int,
            notes: str = "", licences: dict | None = None) -> dict:
    """The entry for ``icao`` of the built ``tile``, in memory.

    :param kind: ``"freeware"`` or ``"payware"`` for a custom pack (the
        publisher says which); the global default airports are always
        ``"default"``.
    :param licences: the library's ``licences.json`` (:mod:`.terms`): each
        source's terms, and the entry's licence and non-commercial mark.
    :returns: ``{"rel", "files": {name: bytes}, "manifest", "pack"}`` —
        ``rel`` the entry folder (``layout.entry_dir``).
    :raises LibraryRefused: no current patch, an unknown pack, a local path.
    """
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES
    import O4_Version
    from tile_bundle import paths as _paths
    from tile_bundle.export import sources
    from tile_bundle.key import xplane_root

    from .checks import local_paths
    icao = icao.upper()
    xp_root = xplane_root(tile)
    if not xp_root:
        raise LibraryRefused("No X-Plane folder is set; the pack cannot be read")
    patch_dir = FNAMES.patch_dir(tile.lat, tile.lon)
    solved = _family(patch_dir, icao)
    meta = _require_current(tile, icao, os.path.join(
        patch_dir, FNAMES.auto_patch_name(icao)), xp_root)
    pack = _key.pack_now(xp_root, icao, tile.lat, tile.lon)
    if not pack.get("pack"):
        raise LibraryRefused("%s is in no installed scenery pack" % icao)
    if not pack.get("custom"):
        kind = "default"
    elif kind not in ("freeware", "payware"):
        raise LibraryRefused("Say whether %s is a free or a paid pack" % pack["pack"])
    pairs = _paths.roots(tile, CFG.custom_scenery_dir, xp_root)
    home = os.path.expanduser("~")

    def change(text: str) -> str:
        return _paths.tokenise_text(text, pairs)

    members = [(L.SOLVED + "/" + name, path) for name, path in solved]
    edited = os.path.join(patch_dir, FNAMES.edited_patch_name(icao))
    if os.path.isfile(edited):
        members.append((L.EDITED + "/" + os.path.basename(edited), edited))
    files, listed = {}, {}
    for name, path in members:
        with open(path, "rb") as handle:
            raw = _paths.transform_file_bytes(path, handle.read(), change)
        left = _paths.leftovers(raw, pairs, (home,)) or local_paths(
            raw.decode("utf-8", "replace"))
        if left:
            raise LibraryRefused("%s would carry a local path (%s); not "
                                 "published" % (os.path.basename(path), left[0]))
        data = _xz(raw)
        files[name + ".xz"] = data
        listed[name + ".xz"] = {"bytes": len(data),
                                "sha256": hashlib.sha256(data).hexdigest(),
                                "raw_bytes": len(raw),
                                "raw_sha256": hashlib.sha256(raw).hexdigest()}
    tile_key = FNAMES.short_latlon(tile.lat, tile.lon)
    found = _terms.annotate(sources(tile, icao), licences or _terms.DEFAULT_LICENCES)
    licence = _terms.entry_licence(found)
    manifest = {"format": FORMAT, "icao": icao, "tile": tile_key,
                "version": int(version),
                "pack": {"name": pack["pack"], "custom": bool(pack["custom"]),
                         "kind": kind},
                "signature": pack["signature"], "law": _key.law_now(tile),
                "solve": meta["freshness"].get("o4_solve_cfg", ""),
                "engine_version": getattr(O4_Version, "version", ""),
                "min_engine": getattr(O4_Version, "version", ""),
                "publisher": publisher, "licence": licence,
                "noncommercial": licence != LICENCE,
                "published": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "sources": found, "files": listed,
                "notes": notes}
    edits = {"format": FORMAT, "edited_patch": next(
        (n for n in listed if n.startswith(L.EDITED + "/")), None),
        "role_overrides": _role_rows(patch_dir, icao)}
    files[L.MANIFEST] = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8")
    files[L.EDITS] = (json.dumps(edits, indent=1, sort_keys=True) + "\n").encode("utf-8")
    files[L.ATTRIBUTION] = _attribution(manifest)
    return {"rel": L.entry_dir(icao, pack["pack"], pack["signature"], version),
            "files": files, "manifest": manifest, "pack": pack}


def write_folder(root: str, entry: dict) -> str:
    """Lay ``entry``'s files out under ``root`` at its folder (the
    pre-publish check reads them where the library would)."""
    folder = os.path.join(root, *entry["rel"].split("/"))
    for name, data in entry["files"].items():
        path = os.path.join(folder, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
    return folder
