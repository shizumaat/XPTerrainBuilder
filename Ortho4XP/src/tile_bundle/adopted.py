"""ADOPTED PACKAGE (owner 2026-11-12T14:19Z): a tile another tool built,
kept by Convert existing tiles as one of ours (``o4_engine.world_adopt``),
saved so it can come back without the drive it came from.

    "I do want to adopt them all, but would like the app to be able to
    do it."

An adopted tile has no downloaded inputs of ours to package
(:mod:`.inputs`), so its package carries the tile's PRODUCTS instead --
everything X-Plane reads but the imagery:

* ``dsf/<tile>.dsf`` -- the DSF as its source folder holds it (a 7z DSF
  stays packed: ``O4_DSF_Compress`` unpacks it when it is laid out);
* ``terrain/*.ter``;
* ``textures/<name>`` -- every texture that is not a DDS (the mask PNGs
  and water borders the ``.ter`` files name);
* the top-level ``*.cfg``, the imagery manifest (``*_imagery.json``,
  without its World-pack layout) and ``color_field.json``;
* ``textures.txt`` -- the DDS names the ``.ter`` files load: the imagery
  a restore lays as placeholders (or fetches), never packaged.

The package is a ``tar.xz`` with ``manifest.json`` (format ``xptb-2``,
kind :data:`.kinds.ADOPTED`, every member's sha256) and
``ATTRIBUTION.txt``.  Who made the data and under what terms is not
known, so it is always marked PERSONAL, as our packages from a source
whose terms do not allow sharing are (``patch_library.terms``).

* :func:`save` -- write the package of one adopted tile folder.
* :func:`plan` -- the install sheet's details (``install.plan``).
* :func:`lay_out` -- the members back into a tile folder, the DSF
  unpacked; each DDS of ``textures.txt`` not there whole is given by
  ``placeholder(name)`` (a kept placeholder, a cut of the source) or
  listed missing.
* :func:`install` -- ``install.install``'s adopted kind: the tile laid
  out and published into the World pack (``o4_engine.world_adopt``).

No tile or airport is named here.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import time

from . import PACKAGE_FORMAT, BundleRefused
from . import kinds as _kinds

__all__ = ["DSF_DIR", "TEXTURE_LIST", "XZ_PRESET", "save", "plan",
           "lay_out", "install", "texture_names"]

#: The member folder of the DSF, and the list of the imagery left out.
DSF_DIR = "dsf"
TEXTURE_LIST = "textures.txt"
#: The DSF is mostly 7z-packed already: a light preset is as small.
XZ_PRESET = 3
_TOP_SUFFIXES = (".cfg", "_imagery.json", "color_field.json")
_LAYOUT_KEY = "world_layout"


def _tile_name(lat: int, lon: int) -> str:
    return "%+03d%+04d" % (int(lat), int(lon))


def texture_names(folder: str) -> list:
    """The DDS names the folder's ``terrain/*.ter`` files load."""
    names = set()
    terrain = os.path.join(folder, "terrain")
    for name in sorted(os.listdir(terrain)) if os.path.isdir(terrain) else ():
        if not name.endswith(".ter"):
            continue
        with open(os.path.join(terrain, name), encoding="utf-8",
                  errors="replace") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) == 2 and parts[0].startswith("BASE_TEX") \
                        and parts[1].lower().endswith(".dds"):
                    names.add(os.path.basename(parts[1]))
    return sorted(names)


def _members(folder: str, dsf: str, lat: int, lon: int) -> list:
    """``[(member name, absolute path or bytes)]`` of the package."""
    out = [(f"{DSF_DIR}/{_tile_name(lat, lon)}.dsf", dsf)]
    for sub, keep in (("terrain", lambda n: n.endswith(".ter")),
                      ("textures", lambda n: not n.lower().endswith(".dds"))):
        where = os.path.join(folder, sub)
        for name in sorted(os.listdir(where)) if os.path.isdir(where) else ():
            path = os.path.join(where, name)
            if keep(name) and os.path.isfile(path) and not name.startswith("."):
                out.append((f"{sub}/{name}", path))
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if name.endswith(_TOP_SUFFIXES) and os.path.isfile(path):
            out.append((name, _top_bytes(name, path)))
    listed = "\n".join(texture_names(folder)) + "\n"
    out.append((TEXTURE_LIST, listed.encode("utf-8")))
    return out


def _top_bytes(name: str, path: str) -> bytes:
    """A top-level file's bytes; the imagery manifest without the World
    pack's layout (the folders of this installation)."""
    with open(path, "rb") as handle:
        data = handle.read()
    if not name.endswith("_imagery.json"):
        return data
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError:
        return data
    if isinstance(doc, dict):
        doc.pop(_LAYOUT_KEY, None)
        data = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    return data


def _sources(tool: str) -> list:
    return [{"provider": tool or "another tool", "personal": True,
             "why": "an adopted tile: who made its data, and under what "
                    "terms, is not known"}]


def save(folder: str, dsf: str, lat: int, lon: int, out: str,
         tool: str = "") -> dict:
    """Write the adopted package of the tile folder ``folder`` (its
    ``terrain/`` and ``textures/``, top-level cfg and manifest) with the
    DSF ``dsf`` to ``out``.  ``tool``: who built the tile, as far as is
    known.  ``{"path", "bytes", "files", "seconds"}``.

    :raises BundleRefused: no DSF, or no terrain."""
    from patch_library import terms as _terms

    from .export import _info
    t0 = time.time()
    if not os.path.isfile(dsf):
        raise BundleRefused("the adopted tile %s has no DSF (%s)"
                            % (_tile_name(lat, lon), dsf))
    if not texture_names(folder):
        raise BundleRefused("the adopted tile %s has no terrain in %s"
                            % (_tile_name(lat, lon), folder))
    blobs = {}
    for name, what in _members(folder, dsf, lat, lon):
        if isinstance(what, bytes):
            blobs[name] = what
        else:
            with open(what, "rb") as handle:
                blobs[name] = handle.read()
    sources = _sources(tool)
    manifest = {
        "format": PACKAGE_FORMAT, "kind": _kinds.ADOPTED,
        "tiles": [{"tile": _tile_name(lat, lon), "airports": {}}],
        "tile": _tile_name(lat, lon), "built_by": tool,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": sources, "licence": "", "noncommercial": True,
        "personal": True, "warning": _terms.personal_warning(sources),
        "imagery": "not included",
        "files": {name: {"bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in blobs.items()}}
    head = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
    note = ("Adopted tile %s (built by %s): its mesh, terrain and masks; "
            "no imagery.\n%s\n" % (manifest["tile"], tool or "another tool",
                                   manifest["warning"])).encode("utf-8")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    temporary = out + ".tmp"
    with tarfile.open(temporary, "w:xz", preset=XZ_PRESET) as tar:
        for name, data in [("manifest.json", head), ("ATTRIBUTION.txt", note),
                           *sorted(blobs.items())]:
            tar.addfile(_info(name, len(data)), io.BytesIO(data))
    os.replace(temporary, out)
    return {"path": out, "bytes": os.path.getsize(out), "files": len(blobs),
            "seconds": round(time.time() - t0, 1)}


def plan(path: str, manifest: dict) -> dict:
    """``install.plan``'s details for an adopted package."""
    tile = manifest.get("tile", "")
    return {"path": path, "format": manifest.get("format", ""),
            "legacy": False, "kind": _kinds.ADOPTED, "key": "",
            "title": "", "creator": manifest.get("built_by", ""), "notes": "",
            "url": "", "tiles": [{"tile": tile, "airports": []}],
            "sources": manifest.get("sources") or [], "licence": "",
            "noncommercial": True, "personal": True,
            "warning": manifest.get("warning", ""),
            "bytes": os.path.getsize(path),
            "files": len(manifest.get("files") or {}), "conflicts": [],
            "summary": ["Adopted tile %s: its mesh, terrain and masks, "
                        "kept in the World pack" % tile,
                        "Imagery is not included: it is laid low-res and "
                        "sharpened as you fly.",
                        manifest.get("warning", "")]}


def _safe(name: str) -> bool:
    parts = name.split("/")
    return (bool(name) and ".." not in parts and not name.startswith("/")
            and "\\" not in name and ":" not in name)


def _read(path: str) -> tuple:
    """``(manifest, {name: bytes})``, every member checked against the
    manifest's sha256.

    :raises BundleRefused: a damaged package or an unsafe name."""
    blobs = {}
    try:
        with tarfile.open(path, "r:*") as tar:
            for member in tar.getmembers():
                if member.isfile():
                    blobs[member.name] = tar.extractfile(member).read()
    except (OSError, tarfile.TarError) as error:
        raise BundleRefused("%s does not read (%s)"
                            % (os.path.basename(path), error)) from error
    try:
        manifest = json.loads(blobs.pop("manifest.json", b"{}").decode("utf-8"))
    except ValueError as error:
        raise BundleRefused("%s has no manifest" % os.path.basename(path)) \
            from error
    if manifest.get("kind") != _kinds.ADOPTED:
        raise BundleRefused("%s is not an adopted tile's package"
                            % os.path.basename(path))
    for name, row in (manifest.get("files") or {}).items():
        data = blobs.get(name)
        if not _safe(name) or data is None \
                or hashlib.sha256(data).hexdigest() != row.get("sha256"):
            raise BundleRefused("%s is damaged (%s)"
                                % (os.path.basename(path), name))
    return manifest, {n: blobs[n] for n in manifest.get("files") or {}}


def _place(target: str, data: bytes) -> None:
    """``data`` at ``target`` (a 7z DSF unpacked), whole or not at all."""
    import O4_DSF_Compress as DSFC
    os.makedirs(os.path.dirname(target), exist_ok=True)
    partial = target + ".part"
    with open(partial, "wb") as handle:
        handle.write(data)
    if target.endswith(".dsf") and DSFC.is_compressed(partial):
        try:
            DSFC.unpack(partial, target)
        finally:
            os.remove(partial)
    else:
        os.replace(partial, target)


def _link(given: str, final: str) -> None:
    os.makedirs(os.path.dirname(final), exist_ok=True)
    partial = final + ".part"
    try:
        os.link(given, partial)
    except OSError:
        shutil.copyfile(given, partial)
    os.replace(partial, final)


def lay_out(path: str, folder: str, placeholder=None) -> dict:
    """Lay the package ``path`` into the tile folder ``folder``: terrain,
    the non-DDS textures and the top-level files written; the DSF under
    ``Earth nav data`` (unpacked when it is a 7z).  Each DDS of
    ``textures.txt`` not already whole there is linked or copied from
    ``placeholder(name)`` (a path, or ``None``).  ``{"tile", "lat",
    "lon", "files", "dsf", "missing": [DDS names nothing gave]}``.

    :raises BundleRefused: as :func:`_read`."""
    import O4_DDS_File as DDS
    import O4_World_Pack as WP
    manifest, blobs = _read(path)
    lat, lon = WP.parse_tile(manifest["tile"])
    dsf = os.path.join(folder, WP.dsf_relpath(lat, lon))
    textures = blobs.pop(TEXTURE_LIST, b"").decode("utf-8").split()
    for name, data in sorted(blobs.items()):
        _place(dsf if name.startswith(DSF_DIR + "/")
               else os.path.join(folder, *name.split("/")), data)
    missing = []
    for name in textures:
        final = os.path.join(folder, "textures", name)
        if DDS.is_whole(final):
            continue
        given = placeholder(name) if placeholder else None
        if given and DDS.is_whole(given):
            _link(given, final)
        else:
            missing.append(name)
    return {"tile": manifest["tile"], "lat": lat, "lon": lon,
            "files": len(blobs), "dsf": dsf, "missing": missing}


def install(path: str, manifest: dict) -> dict:
    """``install.install`` of an adopted package: laid out and published
    into the World pack (``o4_engine.world_adopt.install_package``)."""
    from o4_engine import world_adopt
    details = plan(path, manifest)
    details.update(world_adopt.install_package(path))
    return details
