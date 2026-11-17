"""#2136: the macOS available-memory probe reads the kernel's own figure
(``kern.memorystatus_level`` x ``hw.memsize``), with the old ``vm_stat``
sum as its fallback; Linux and Windows are unchanged.  Mocked sysctl and
vm_stat — no reading of this machine is asserted."""
import ctypes

import pytest

import O4_Parallel_Utils as PU

_GIB = 1024.0 ** 3

_VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                    22184.
Pages active:                                2082399.
Pages inactive:                              2079699.
Pages speculative:                               975.
Pages purgeable:                               29795.
File-backed pages:                            667051.
Pages occupied by compressor:                3366519.
"""


def _sysctl(values):
    def fake(name, ctype):
        return values.get(name)
    return fake


@pytest.fixture
def darwin(monkeypatch):
    monkeypatch.setattr(PU.sys, "platform", "darwin")
    monkeypatch.setattr(PU, "_darwin_vm_stat_gigabytes",
                        lambda: PU._vm_stat_available_gigabytes(_VM_STAT, 16384))


def test_memorystatus_level_times_memsize(monkeypatch, darwin):
    monkeypatch.setattr(PU, "_darwin_sysctl_int", _sysctl(
        {"kern.memorystatus_level": 54, "hw.memsize": 128 * int(_GIB)}))
    assert PU._darwin_available_gigabytes() == pytest.approx(69.12)


def test_reading_is_larger_than_the_vm_stat_sum_it_replaces(monkeypatch, darwin):
    """The owner's machine on 11-17: level 50 on 128 GB = 64 GB, where the
    vm_stat sum of the same moment reads ~32 GB."""
    monkeypatch.setattr(PU, "_darwin_sysctl_int", _sysctl(
        {"kern.memorystatus_level": 50, "hw.memsize": 128 * int(_GIB)}))
    old = PU._vm_stat_available_gigabytes(_VM_STAT, 16384)
    assert old == pytest.approx(32.54, abs=0.01)
    assert PU._darwin_available_gigabytes() == pytest.approx(64.0)


@pytest.mark.parametrize("values", [
    {},                                                    # sysctl absent
    {"hw.memsize": 128 * int(_GIB)},                       # no level
    {"kern.memorystatus_level": 0, "hw.memsize": 1 << 37},  # nonsense level
    {"kern.memorystatus_level": 140, "hw.memsize": 1 << 37},
])
def test_falls_back_to_vm_stat(monkeypatch, darwin, values):
    monkeypatch.setattr(PU, "_darwin_sysctl_int", _sysctl(values))
    assert PU._darwin_available_gigabytes() == pytest.approx(32.54, abs=0.01)


def test_vm_stat_sum_ignores_unlisted_and_empty():
    assert PU._vm_stat_available_gigabytes("nothing here\n", 4096) is None


def test_not_darwin_answers_none(monkeypatch):
    monkeypatch.setattr(PU.sys, "platform", "linux")
    assert PU._darwin_available_gigabytes() is None


def test_probe_order_linux_first_then_darwin_then_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(PU, "_linux_available_gigabytes",
                        lambda: calls.append("linux"))
    monkeypatch.setattr(PU, "_darwin_available_gigabytes",
                        lambda: calls.append("darwin") or 61.0)
    monkeypatch.setattr(PU, "_windows_available_gigabytes",
                        lambda: calls.append("windows") or 1.0)
    assert PU._probe_available_memory_gigabytes() == 61.0
    assert calls == ["linux", "darwin"]


def test_a_raising_probe_falls_through(monkeypatch):
    def boom():
        raise OSError("no")
    monkeypatch.setattr(PU, "_linux_available_gigabytes", boom)
    monkeypatch.setattr(PU, "_darwin_available_gigabytes", boom)
    monkeypatch.setattr(PU, "_windows_available_gigabytes", lambda: 7.0)
    assert PU._probe_available_memory_gigabytes() == 7.0


@pytest.mark.skipif(PU.sys.platform != "darwin", reason="macOS sysctl")
def test_real_sysctl_reads_an_integer():
    assert PU._darwin_sysctl_int("hw.memsize", ctypes.c_uint64) > 0
    level = PU._darwin_sysctl_int("kern.memorystatus_level", ctypes.c_int)
    assert 0 <= level <= 100
