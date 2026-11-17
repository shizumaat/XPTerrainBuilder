"""Windows file association for ``.xptb`` / ``.xptbundle`` packages (#2143).

The portable zip has no installer, so the Qt window registers the
association itself at launch, per user (``HKCU\\Software\\Classes``, no
administrator rights) — the same keys ``scripts/windows/register_xptb.cmd``
writes.  It writes only when the association is missing or points at a
different copy of the app, and then says so in one console line.
Only a frozen ``XPTerrainBuilder.exe`` on Windows registers: a source
checkout's ``python.exe`` is never the program to open a package with.

Undo: ``reg delete HKCU\\Software\\Classes\\.xptb /f`` (and ``.xptbundle``,
``XPTerrainBuilder.Package``).
"""
from __future__ import annotations

import os
import sys

__all__ = ["PROG_ID", "SUFFIXES", "wanted_keys", "ensure", "check_at_launch"]

PROG_ID = "XPTerrainBuilder.Package"
SUFFIXES = (".xptb", ".xptbundle")
_ROOT = "Software\\Classes"


def wanted_keys(exe: str) -> dict[str, str]:
    """Sub-key of ``HKCU\\Software\\Classes`` -> its default value."""
    keys = {s: PROG_ID for s in SUFFIXES}
    keys[PROG_ID] = "XPTerrainBuilder package"
    keys[PROG_ID + "\\DefaultIcon"] = '"%s",0' % exe
    keys[PROG_ID + "\\shell\\open\\command"] = '"%s" "%%1"' % exe
    return keys


def _read(winreg, sub: str):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _ROOT + "\\" + sub) as key:
            return winreg.QueryValueEx(key, "")[0]
    except OSError:
        return None


def ensure(exe: str, winreg) -> str | None:
    """Write the keys that differ from :func:`wanted_keys`; the console
    line when anything was written, else None."""
    stale = {sub: value for sub, value in wanted_keys(exe).items()
             if _read(winreg, sub) != value}
    if not stale:
        return None
    for sub, value in stale.items():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _ROOT + "\\" + sub) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, value)
    _notify_shell()
    return ".xptb and .xptbundle packages now open with %s." % exe


def _notify_shell():
    """Explorer re-reads associations (SHChangeNotify ASSOCCHANGED)."""
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


def check_at_launch(say=print) -> None:
    """At window show: register when this is the frozen Windows app."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import winreg
        line = ensure(os.path.abspath(sys.executable), winreg)
    except Exception as exc:              # a locked-down profile: say why
        line = "Could not register .xptb packages with this app: %s" % exc
    if line:
        say(line)
