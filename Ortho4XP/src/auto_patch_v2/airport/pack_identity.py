"""ONE AIRPORT'S PACK IDENTITY, PORTABLE (#1699): the digest a tile bundle
key and a library airport entry both match on.

``pack.signature`` is the airport's apt.dat block hash, the hash of its
pack's tile DSF(s), a borrowed Global Airports block and the ``1302
flatten`` declaration.  Two installations compare it only through a
DIGEST of those parts, with every DSF hashed as installed: the pristine
``.anchor_bak`` when a build rewrote the live file
(``dsf_write.pristine_dsf_path``), so a pack this app already modified
still matches the one another user has fresh from its developer.  No
path is in the digest; the pack folder's name is returned for display.
"""
from __future__ import annotations

import hashlib
import json

from . import apt_dat as _apt
from . import dsf_write as _dw
from . import pack as _pack
from .file_hash import sha256_file

__all__ = ["NO_APT_DAT", "digest", "pack_signature"]

#: The signature of an airport no installed apt.dat defines.
NO_APT_DAT = "no apt.dat"


def digest(value) -> str:
    """A sha256 of ``value``'s canonical JSON."""
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pack_signature(root: str, icao: str, lat: int, lon: int,
                   files: list | None = None) -> dict:
    """``{"pack", "custom", "signature"}`` of ``icao``'s pack in the X-Plane
    install ``root`` for tile (``lat``, ``lon``).  ``files``, when given,
    gets every file the signature read (the apt.dat, a borrowed Global
    Airports apt.dat or ``""``, the pristine DSFs) — what a cache of it is
    keyed on."""
    from ..law import Law
    sel = _pack.select_pack(root, icao, Law.for_airport(icao))
    if sel is None:
        return {"pack": "", "custom": False, "signature": NO_APT_DAT}
    block = _apt.read_airport_block(sel.apt_dat_path, icao) or []
    sig = _pack.signature(sel, block, lat, lon)
    pristine = [_dw.pristine_dsf_path(p) for p in sig.dsf_paths]
    if files is not None:
        files.extend([sel.apt_dat_path, sel.borrowed_apt_dat_path or ""] + pristine)
    return {"pack": sel.name, "custom": bool(sel.custom),
            "signature": digest([sig.apt_dat_sha256,
                                  [sha256_file(p) for p in pristine],
                                  sig.borrowed_block_sha256,
                                  bool(sig.flatten_declared)])[:32]}
