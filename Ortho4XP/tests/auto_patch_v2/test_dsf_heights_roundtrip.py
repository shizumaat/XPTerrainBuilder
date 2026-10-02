"""#131 twins: the ``HEIGHTS`` row (the elevation scale of the object
pools) and the placement round trip.

KASE ``+39-107.dsf`` (Aerosoft) carries 14 ``OBJECT_MSL`` rows at
2337-2444 m, above the 2047.97 m a 0.03125 quantum can encode, so WED
wrote ``HEIGHTS 0.06250``.  The object stage converts every elevated row
on-ground (RULINGS 2026-09-11d); the re-dump then printed ``HEIGHTS
0.03125`` and the verifier refused the write ("structural row 4"), so no
object placement ever ran at KASE.  Measured: with no elevated row left
DSFTool stores no height scale at all — any ``HEIGHTS`` text encodes to
ONE byte-identical DSF — while with one left the text's quantum is
honoured.  These pin both halves: the row is compared in full while an
elevated row remains, and by keyword only when none does.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf as D
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.model.placement import PlacementPlan, Provenance

#: WED's quantum for KASE-class elevations (> 2047.96875 m)
PACK_QUANTUM = "0.06250"
#: DSFTool's re-dump of a DSF whose object pools carry no elevation
DEFAULT_QUANTUM = "0.03125"
HIGH_MSL_M = (2444.497367819, 2337.749828336)

DUMP = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\n"
        "# file: /fixture/+39-107.dsf\n\n"
        "DIVISIONS 32\n"
        f"HEIGHTS {PACK_QUANTUM} 0.0  # max encodeable 4095.93750\n"
        "PROPERTY sim/west -107\nPROPERTY sim/east -106\n"
        "PROPERTY sim/north 40\nPROPERTY sim/south 39\n"
        "PROPERTY sim/planet earth\nPROPERTY sim/overlay 1\n"
        "OBJECT_DEF objects/shelter.obj\n"
        "OBJECT_DEF objects/tower.obj\n"
        "OBJECT 0 -106.866000000 39.223000000 69.540000\n"
        f"OBJECT_MSL 1 -106.839264324 39.190091173 {HIGH_MSL_M[0]:.9f} 90.259556\n"
        f"OBJECT_MSL 1 -106.874122129 39.234236954 {HIGH_MSL_M[1]:.9f} 159.996338\n")


def _plan(text: str, keep_last: bool = False) -> PlacementPlan:
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".text", delete=False) as fh:
        fh.write(text)
    conv = W.conversions_for_dump(D.read_dump(fh.name))[0]
    Path(fh.name).unlink()
    if keep_last:
        conv = conv[:-1]
    return PlacementPlan(
        icao="KASE", pack_name="", pack_root="", dsf_path="", dsf_backup_path="",
        provenance=Provenance(dump_sha="", engine_version="", law_digest=""),
        conversions=tuple(conv), kept=())


def _heights(text: str) -> str:
    return next(ln.split()[1] for ln in text.splitlines()
                if ln.startswith(W.HEIGHTS_KEYWORD + " "))


#: Measured on CI windows-latest (run 36877241692, 2026-10-01): the
#: bundled ``Utils/win/DSFTool.exe`` re-dumps an UNEDITED ``HEIGHTS
#: 0.06250`` text with elevated rows as ``0.12500`` — it does not honour
#: the text's quantum where the macOS / Linux builds do.  Strict: the day
#: it does, this flips red and the note goes.
WIN_REQUANTISES = pytest.mark.xfail(
    sys.platform == "win32", strict=True,
    reason="Windows DSFTool re-pools HEIGHTS 0.06250 -> 0.12500 (#131 note)")


#: What the Windows binary re-pools the pack quantum to (#166).
WIN_REQUANTISED = "0.12500"

#: The attribution record the Windows twin below prints into the CI log.
#: #166 asks whether the Windows refusal is an OLDER XPTools build or a
#: parse difference, and that cannot be answered from a red/green bit --
#: it needs the binary's own version string NEXT TO the quantum it
#: produced, on the runner that produced it.  Linux and macOS record the
#: same pair, so one CI run of the matrix is the whole comparison.
ATTRIBUTION_RECORD = "DSFTOOL-HEIGHTS-ATTRIBUTION"


def _dsftool_version(tool: str, tmp_path: Path) -> str:
    """The version line DSFTool writes into its own dumps.

    Line 2 of a dump is ``800 written by DSFTool <version>``; the fixture
    header above only carries line 1 (``A`` / ``I``), which says nothing
    about the build.
    """
    seed = tmp_path / "version.text"
    seed.write_text(DUMP, encoding="utf-8", newline="\n")
    W._run([tool, "--text2dsf", str(seed), str(tmp_path / "version.dsf")])
    dumped = Path(W.dump(str(tmp_path / "version.dsf"),
                         str(tmp_path / "version.back.text"), tool))
    for line in dumped.read_text(encoding="utf-8").splitlines()[:4]:
        if "written by" in line:
            return line.strip()
    return "unknown (no 'written by' line in the dump)"


def _platform(text: str, tool: str, tmp_path: Path) -> str:
    """``text`` with the platform DSFTool's own header line (``A`` on
    macOS / Linux, ``I`` on Windows) — a pack's pristine dump always comes
    from the same binary that re-dumps it, so the fixture must too."""
    seed = tmp_path / "seed.text"
    seed.write_text(text, encoding="utf-8", newline="\n")
    W._run([tool, "--text2dsf", str(seed), str(tmp_path / "seed.dsf")])
    head = Path(W.dump(str(tmp_path / "seed.dsf"), str(tmp_path / "seed2.text"),
                       tool)).read_text(encoding="utf-8").splitlines()[0]
    return head + "\n" + text.split("\n", 1)[1]


def _encode(tmp_path: Path, name: str, text: str, tool: str) -> tuple[Path, str]:
    src = tmp_path / f"{name}.text"
    src.write_text(text, encoding="utf-8", newline="\n")
    out = tmp_path / f"{name}.dsf"
    W.encode(str(src), str(out), tool)
    back = W.dump(str(out), str(tmp_path / f"{name}.back.text"), tool)
    return out, Path(back).read_text(encoding="utf-8")


# ── pure: the verifier keeps guarding the quantum where it is stored ──

def test_heights_quantum_still_compared_while_an_elevated_row_remains():
    actual = DUMP.replace(f"HEIGHTS {PACK_QUANTUM}", f"HEIGHTS {DEFAULT_QUANTUM}")
    rep = W.compare_dumps(DUMP, actual)
    assert not rep.ok
    assert any(W.HEIGHTS_KEYWORD in f for f in rep.findings)


def test_heights_quantum_not_compared_once_no_elevated_row_remains():
    edited = W.edit_dump(DUMP, _plan(DUMP))
    assert "OBJECT_MSL" not in edited
    assert _heights(edited) == PACK_QUANTUM          # the edit copies the row
    actual = edited.replace(f"HEIGHTS {PACK_QUANTUM}", f"HEIGHTS {DEFAULT_QUANTUM}")
    rep = W.compare_dumps(edited, actual)
    assert rep.ok, rep.findings
    # a MISSING row is still a structural loss
    gone = "\n".join(ln for ln in actual.splitlines()
                     if not ln.startswith(W.HEIGHTS_KEYWORD)) + "\n"
    assert not W.compare_dumps(edited, gone).ok


# ── DSFTool: the measurement the exemption stands on ─────────────────

@WIN_REQUANTISES
@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_pack_heights_survive_an_unedited_round_trip(tmp_path):
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    out, back = _encode(tmp_path, "pristine", dump, tool)
    assert _heights(back) == PACK_QUANTUM
    rep = W.verify_roundtrip(str(out), dump, tool)
    assert rep.ok, rep.findings
    assert rep.max_elev_m <= W.TOL_ELEV_M


@WIN_REQUANTISES
@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_one_remaining_elevated_row_keeps_the_pack_quantum(tmp_path):
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    edited = W.edit_dump(dump, _plan(dump, keep_last=True))
    assert edited.count("OBJECT_MSL ") == 1
    out, back = _encode(tmp_path, "one", edited, tool)
    assert _heights(back) == PACK_QUANTUM
    assert W.verify_roundtrip(str(out), edited, tool).ok


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_full_conversion_passes_and_the_heights_text_is_not_stored(tmp_path):
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    edited = W.edit_dump(dump, _plan(dump))
    out, back = _encode(tmp_path, "conv", edited, tool)
    assert _heights(back) == DEFAULT_QUANTUM            # the KASE symptom
    rep = W.verify_roundtrip(str(out), edited, tool)
    assert rep.ok, rep.findings                          # #131: no refusal
    # benign BYTE FOR BYTE: whatever HEIGHTS the text says (or none), the
    # encoded DSF is the same file — there is nothing to preserve
    digests = {hashlib.sha256(out.read_bytes()).hexdigest()}
    for q in ("0.12500", DEFAULT_QUANTUM, None):
        variant = (edited.replace(f"HEIGHTS {PACK_QUANTUM}", f"HEIGHTS {q}")
                   if q else "\n".join(ln for ln in edited.splitlines()
                                       if not ln.startswith(W.HEIGHTS_KEYWORD)) + "\n")
        o, _ = _encode(tmp_path, f"v{q}", variant, tool)
        digests.add(hashlib.sha256(o.read_bytes()).hexdigest())
    assert len(digests) == 1


# ── #166: the attribution record, one line per platform in the CI log ──

@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_the_heights_quantum_is_recorded_with_the_dsftool_version(tmp_path,
                                                                  capsys):
    """Record (platform, DSFTool version, quantum) and pin the known map.

    This is the twin #166 asks for and the one the strict xfails above
    cannot be: an xfail says only THAT Windows differs.  This says WHICH
    BINARY differed, in the CI log of the run that measured it, so the
    attribution ("older XPTools build" vs "parse difference") is read off
    the matrix instead of guessed -- and the day the bundled
    ``Utils/win/DSFTool.exe`` is replaced, the recorded version changes
    and this test says whether the quantum followed it.

    No fix is expected from Linux or macOS: neither can run the Windows
    binary, so this records and pins, it does not repair.
    """
    tool = _dsftool_path()
    version = _dsftool_version(tool, tmp_path)
    dump = _platform(DUMP, tool, tmp_path)
    _out, back = _encode(tmp_path, "attribution", dump, tool)
    quantum = _heights(back)
    record = (f"{ATTRIBUTION_RECORD} platform={sys.platform} "
              f"version={version!r} heights_in={PACK_QUANTUM} "
              f"heights_out={quantum}")
    with capsys.disabled():
        print("\n" + record)
    expected = WIN_REQUANTISED if sys.platform == "win32" else PACK_QUANTUM
    assert quantum == expected, (
        f"a THIRD behaviour, neither the honoured {PACK_QUANTUM} of the "
        f"macOS/Linux builds nor the {WIN_REQUANTISED} measured on "
        f"windows-latest run 36877241692 -- re-attribute #166 from this "
        f"record: {record}")
