"""O4_Windows_Assoc (#2143): per-user .xptb association, fake winreg."""
import contextlib
import sys

import O4_Windows_Assoc as WA


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self, store=None):
        self.store = dict(store or {})
        self.writes = []

    @contextlib.contextmanager
    def OpenKey(self, root, sub):
        if sub not in self.store:
            raise OSError("missing")
        yield sub

    def QueryValueEx(self, key, name):
        return (self.store[key], self.REG_SZ)

    @contextlib.contextmanager
    def CreateKey(self, root, sub):
        yield sub

    def SetValueEx(self, key, name, reserved, kind, value):
        self.store[key] = value
        self.writes.append(key)


EXE = r"C:\Apps\XPTB\XPTerrainBuilder.exe"


def test_missing_association_is_written_once():
    reg = FakeWinreg()
    line = WA.ensure(EXE, reg)
    assert line and EXE in line
    assert reg.store[r"Software\Classes\.xptb"] == WA.PROG_ID
    assert reg.store[r"Software\Classes\.xptbundle"] == WA.PROG_ID
    assert reg.store[r"Software\Classes\XPTerrainBuilder.Package\shell\open\command"] \
        == '"%s" "%%1"' % EXE
    reg.writes.clear()
    assert WA.ensure(EXE, reg) is None and reg.writes == []


def test_other_copy_is_repointed():
    reg = FakeWinreg()
    WA.ensure(r"D:\Old\XPTerrainBuilder.exe", reg)
    reg.writes.clear()
    assert WA.ensure(EXE, reg)
    assert sorted(reg.writes) == sorted([
        r"Software\Classes\XPTerrainBuilder.Package\DefaultIcon",
        r"Software\Classes\XPTerrainBuilder.Package\shell\open\command"])


def test_launch_check_skips_unfrozen_and_non_windows(monkeypatch):
    said = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delattr(sys, "frozen", raising=False)
    WA.check_at_launch(said.append)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    WA.check_at_launch(said.append)
    assert said == []
