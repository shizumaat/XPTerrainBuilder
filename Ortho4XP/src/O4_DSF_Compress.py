"""Write a DSF as a 7z archive, and prove it decodes to the source byte for
byte (#1992 P1c: converting built tiles to on-demand form).

X-Plane reads a 7z-compressed DSF natively (Laminar's own global scenery
ships that way); an Ortho4XP DSF is written uncompressed (``XPLNEDSF``
cookie) and shrinks to ~60 % as LZMA.

* :func:`compress` -- 7-Zip (``O4_Overlay_Utils.resolve_unzip_cmd``: the
  vendored ``7zz`` / ``7z.exe``, else PATH) archives the DSF with LZMA1
  (``-m0=lzma``, the coder Laminar's DSFs use) and an UNCOMPRESSED archive
  header (``-mhc=off``), so the one packed stream starts at byte 32 and
  :mod:`O4_DSF_Header`'s pure-Python reader decodes it.
* :func:`decodes_to` -- the archive, decoded by that reader (not by the
  tool that wrote it), equals the source DSF's bytes (SHA-256 of each).
* :func:`is_compressed` -- the file already is a 7z.

Standard library only (plus the engine's own DSF reader).
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import subprocess

import O4_DSF_Header as DSFH
import O4_UI_Utils as UI  # posix_spawn launches, never fork

__all__ = ["CompressError", "compress", "decodes_to", "is_compressed"]

_SEVEN_ZIP = b"7z\xbc\xaf\x27\x1c"


class CompressError(RuntimeError):
    """No 7-Zip, or it failed, or its archive does not decode to the DSF."""


def is_compressed(path: str) -> bool:
    """Does the file at ``path`` start with the 7z signature?"""
    try:
        with open(path, "rb") as handle:
            return handle.read(len(_SEVEN_ZIP)) == _SEVEN_ZIP
    except OSError:
        return False


def _digest(path: str) -> str:
    """SHA-256 of the DSF at ``path`` as X-Plane reads it (decompressed
    when it is a 7z); ``""`` when it does not read as a DSF."""
    data = DSFH.dsf_bytes(path)
    return hashlib.sha256(data).hexdigest() if data else ""


def decodes_to(archive: str, source: str) -> bool:
    """Does ``archive`` decode, by the engine's own reader, to exactly the
    bytes of the DSF ``source`` (either one may be a 7z)?"""
    want = _digest(source)
    return bool(want) and _digest(archive) == want


def _seven_zip() -> str:
    import O4_Overlay_Utils as OVL
    found = OVL.resolve_unzip_cmd()
    if not found:
        raise CompressError("no 7-Zip found (Utils/<os>/7zz or 7z on PATH)")
    return found


def compress(source: str, dest: str, *, threads: int = 2) -> None:
    """Write ``source`` (an uncompressed DSF) to ``dest`` as a one-file 7z
    whose member has the DSF's own name, and check that it decodes back to
    ``source``.  The archive is written under a temporary name in
    ``dest``'s folder and renamed onto ``dest`` only when it verifies;
    ``CompressError`` (and ``dest`` untouched) otherwise."""
    temp = f"{dest}.{os.getpid()}.part.7z"
    with contextlib.suppress(OSError):
        os.remove(temp)
    command = [_seven_zip(), "a", "-t7z", "-m0=lzma", "-mx=5", "-mhc=off",
               f"-mmt={max(1, int(threads))}", "-bd", "-y",
               os.path.abspath(temp), "--",   # a tile "-28-057" is no switch
               os.path.abspath(source)]       # 7z stores the bare name
    try:
        done = subprocess.run(command, capture_output=True, check=False,
                              **UI.external_tool_keyword_arguments())
        if done.returncode != 0:
            raise CompressError(
                f"7-Zip exited {done.returncode} on {source}: "
                + done.stderr.decode("utf-8", "replace")[-300:])
        if not decodes_to(temp, source):
            raise CompressError(f"the 7z of {source} does not decode to it")
        os.replace(temp, dest)
    finally:
        with contextlib.suppress(OSError):
            os.remove(temp)
