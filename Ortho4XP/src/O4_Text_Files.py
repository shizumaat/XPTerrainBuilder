"""TEXT FILES NAME THEIR ENCODING, AT ONE PLACE (issues #539, #510, #92).

``open(path, "r")`` with no ``encoding=`` reads in the machine's ANSI code
page on Windows (cp1252 in the West, cp932 / cp936 / cp949 / cp950 in East
Asia), and the app does not set UTF-8 mode.  A non-ASCII byte is then
either mojibake or a ``UnicodeDecodeError`` -- and a reader that wraps the
read in a broad ``except`` drops the file with no error.  The console's
twin of this module is ``O4_Console_Encoding``; this one is the corpus.

Three classes of file, three readings:

* **Ours** -- files only the app ships (the elevation ``.elv``) and
  files the engine writes itself: UTF-8.  Read with
  :data:`SHIPPED_ENCODING`, which also drops a byte-order mark an editor
  added; written with :data:`WRITE_ENCODING`.
* **Supplied** -- a file a user or a third party may have written and
  the engine only READS (an imagery ``.lay`` / ``.comb`` / extent /
  filter, which people add their own of; a server list; a scenery pack's
  text): UTF-8 by specification, anything in the wild.  :func:`open_supplied` reads UTF-8
  and, when the bytes are not UTF-8, latin-1 -- which maps every byte, so
  the read can never raise and the file is never dropped; the ASCII a
  parser keys on is the same under both.
* **Ours, from before** -- a config file the user's own machine wrote
  when the writer named no encoding (``Ortho4XP.cfg`` up to beta 1): that
  is the ANSI code page.  ``open_supplied(path, legacy_ansi=True)`` tries
  it between UTF-8 and latin-1, so a path such as ``C:\\Users\\José`` an
  older build saved still reads back; the writer now names UTF-8.

A reader that STREAMS a very large supplied file (``apt.dat``, a DSF text
dump) names ``encoding="utf-8"`` with its own ``errors=`` policy at the
``open`` instead of loading the bytes twice here.
"""

from __future__ import annotations

import io
import locale
import sys

__all__ = ["SHIPPED_ENCODING", "WRITE_ENCODING", "decode_supplied",
           "open_supplied"]

#: Read encoding of every file the app ships or writes: UTF-8, and a
#: byte-order mark an editor added is dropped.
SHIPPED_ENCODING = "utf-8-sig"

#: Write encoding of every text file the engine writes (never a BOM).
WRITE_ENCODING = "utf-8"

#: Maps every byte to a character: the reading that cannot fail.
_EVERY_BYTE = "latin-1"


def _ansi_code_page() -> str:
    """This machine's ANSI code page (Windows); UTF-8 elsewhere.
    ``locale.getencoding`` answers it even under Python's UTF-8 mode."""
    if sys.platform != "win32":
        return "utf-8"
    getencoding = getattr(locale, "getencoding", None)      # Python >= 3.11
    return getencoding() if getencoding else locale.getpreferredencoding(False)


def decode_supplied(raw: bytes, legacy_ansi: bool = False) -> str:
    """The text of a SUPPLIED file's bytes; never raises.

    UTF-8 (byte-order mark dropped) when the bytes are UTF-8 -- so an
    ASCII or UTF-8 file reads exactly as a UTF-8 ``open`` reads it; else
    this machine's ANSI code page when ``legacy_ansi`` (a file an older
    build of this app wrote here); else latin-1, which decodes anything.
    """
    encodings = [SHIPPED_ENCODING]
    if legacy_ansi:
        encodings.append(_ansi_code_page())
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode(_EVERY_BYTE)


def open_supplied(path: str, legacy_ansi: bool = False):
    """Open a SUPPLIED text file for reading; a decode can never raise.

    A text stream over :func:`decode_supplied`, with the newline handling
    of a text-mode ``open`` (``\\r\\n`` reads as ``\\n``).  Raises what
    ``open`` raises for a missing or unreadable file, nothing else.
    """
    with open(path, "rb") as handle:
        text = decode_supplied(handle.read(), legacy_ansi)
    stream = io.StringIO(newline=None)
    stream.write(text)
    stream.seek(0)
    return stream
