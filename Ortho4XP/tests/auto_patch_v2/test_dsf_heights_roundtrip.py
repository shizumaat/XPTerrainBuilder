"""#131 / #166 / #181 twins: the ``HEIGHTS`` row (the elevation scale of
the object pools) and the placement round trip.

KASE ``+39-107.dsf`` (Aerosoft) carries 14 ``OBJECT_MSL`` rows at
2337-2444 m, above the 2047.97 m a 0.03125 quantum can encode, so WED
wrote ``HEIGHTS 0.06250``.  The object stage converts every elevated row
on-ground (RULINGS 2026-09-11d); the re-dump then printed ``HEIGHTS
0.03125`` and the verifier refused the write ("structural row 4"), so no
object placement ever ran at KASE (#131).

Two things are measured about that row, and together they are the law
:func:`dsf_write._heights_reconciled` carries:

* With no elevated row left, DSFTool stores no height scale at all — any
  ``HEIGHTS`` text encodes to ONE byte-identical DSF (#131).
* The quantum DSFTool PRINTS on ``--dsf2text`` is not a function of the
  DSF at all (#181, measured in this file's own terms below and in
  ``_heights_reconciled``'s docstring): one binary, byte-identical input,
  ``0.06250`` written to one output path and ``1.00000`` to another.  The
  ENCODED scale — the elevation span of the ``# pool`` block — is the
  stable observable, and it survives.

So every twin here asserts the ENCODED scale and the verifier's verdict,
and only RECORDS the dumped text.  That is what makes the file green in
any run order: nothing in it reads a field that moves with the pytest
``tmp_path`` neighbourhood.  The quantum is compared by ENCODABLE RANGE:
a re-pool that still carries every elevated row is recorded, one that
cannot encode a remaining row is still refused.
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
#: ``HIGH_MSL_M`` as :data:`PACK_QUANTUM` stores it (``round(z / q) * q``
#: — the drift the round trip is allowed is ``TOL_ELEV_M``).
HIGH_MSL_ENCODED_M = (2444.5, 2337.75)

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


def _requantised(text: str, quantum: str) -> str:
    """``text`` as a re-dump at ``quantum`` would print it: the row's
    quantum replaced, its ``# max encodeable`` recomputed, and every
    elevated row at the value the pools decode to.

    Both :data:`HIGH_MSL_ENCODED_M` values are exact multiples of
    :data:`PACK_QUANTUM` and of :data:`WIN_REDUMP_QUANTUM`, so one
    spelling serves either pool."""
    top = float(quantum) * W.POOL_QUANTA
    out = text.replace(
        f"{W.HEIGHTS_KEYWORD} {PACK_QUANTUM} 0.0  # max encodeable 4095.93750",
        f"{W.HEIGHTS_KEYWORD} {quantum} 0.0  # max encodeable {top:.5f}")
    for authored, encoded in zip(HIGH_MSL_M, HIGH_MSL_ENCODED_M):
        out = out.replace(f"{authored:.9f}", f"{encoded:.9f}")
    return out


#: What the bundled ``Utils/win/DSFTool.exe`` printed for an UNEDITED
#: ``HEIGHTS 0.06250`` text with elevated rows on CI windows-latest, run
#: 36877241692 (2026-10-01) — the measurement #166 was opened on.
WIN_REDUMP_QUANTUM = "0.12500"

#: A quantum that CANNOT carry :data:`HIGH_MSL_M`: ``0.03125 x 65535`` tops
#: out at 2047.96875 m.  This is #131's own refusal row and it stays one.
UNENCODABLE_QUANTUM = DEFAULT_QUANTUM

#: The attribution record the DSFTool twin below prints into the CI log.
#: #166 asks whether the Windows refusal is an OLDER XPTools build or a
#: parse difference, and that cannot be answered from a red/green bit --
#: it needs the binary's own version string NEXT TO the quantum it
#: produced, on the runner that produced it.  Linux and macOS record the
#: same pair, so one CI run of the matrix is the whole comparison.  It is
#: a RECORD and not an assertion: the quantum it carries is the unstable
#: field (#181), so asserting a platform map made unrelated PRs red or
#: green at random (#234, #242 — both directions on one commit).
ATTRIBUTION_RECORD = "DSFTOOL-HEIGHTS-ATTRIBUTION"

#: The object-pool scale line DSFTool writes as a dump comment.  Its
#: elevation column is quantum x 65535 and survives the round trip.
POOL_COMMENT_PREFIX = "# pool"
#: What :data:`PACK_QUANTUM` encodes to in that column.
PACK_POOL_SCALE = "4095.93750"
#: The record the stability twin prints, one line per platform (#181).
NONDETERMINISM_RECORD = "DSFTOOL-HEIGHTS-TEXT-STABILITY"


def _pool_elevation_scales(text: str) -> list[str]:
    """The elevation column of every 4-plane object-pool comment."""
    out = []
    for line in text.splitlines():
        if line.startswith(POOL_COMMENT_PREFIX) and "p=4" in line:
            out.append(line.split()[-2])
    return out


def _record(capsys, line: str) -> None:
    """Print one measurement line into the CI log of the run that made it."""
    with capsys.disabled():
        print("\n" + line)


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


# ── pure: what the quantum is compared BY ──────────────────────────────

def test_a_heights_quantum_that_cannot_encode_a_remaining_row_is_refused():
    """#131's own refusal row, kept: 0.03125 tops out below 2444 m."""
    actual = _requantised(DUMP, UNENCODABLE_QUANTUM)
    rep = W.compare_dumps(DUMP, actual)
    assert not rep.ok
    assert any(W.HEIGHTS_KEYWORD in f for f in rep.findings), rep.findings
    assert rep.heights_repool == ""


def test_a_heights_quantum_that_still_encodes_every_row_is_a_recorded_repool():
    """The #166 decision: a PURE RE-POOL passes and is RECORDED.

    ``1.00000`` is the quantum DSFTool 2.4.0-b1 prints for this very DSF
    when the output path happens to perturb it (#181).  It encodes to
    65535 m, so every 2444 m row still fits and nothing was lost — the
    write must not be refused over a text field, and the change must not
    pass silently either.
    """
    for quantum in ("1.00000", WIN_REDUMP_QUANTUM):
        actual = _requantised(DUMP, quantum)
        rep = W.compare_dumps(DUMP, actual)
        assert rep.ok, (quantum, rep.findings)
        assert rep.heights_repool == f"{PACK_QUANTUM} -> {quantum}"
        assert rep.max_elev_m <= W.TOL_ELEV_M
        # the record reaches the write report (``o4_placement_provenance``)
        assert rep.to_dict()["heights_repool"] == rep.heights_repool


def test_the_recorded_windows_redump_is_accepted_as_a_pure_repool():
    """#166 twinned with the recorded Windows measurement, no runner.

    CI windows-latest run 36877241692 recorded ``heights_in=0.06250
    heights_out=0.12500`` for this fixture, which is what #166 is about.
    The CI log publishes that record line, not the dump text, so the
    fixture here is :data:`DUMP` re-spelled at that quantum with the
    elevated rows at the values the pools decode to — the DECISION's
    twin, not a byte copy of the Windows file.  (The Windows header line
    is ``I`` rather than ``A``; that difference is separate and is what
    :func:`_platform` exists for.)

    0.12500 x 65535 = 8191.875 m, so both 2444 m rows still encode and
    neither moved beyond ``TOL_ELEV_M``: on this law Windows is no longer
    a refusal, and the #131 protection is untouched (the twin above).
    """
    win = _requantised(DUMP, WIN_REDUMP_QUANTUM)
    assert _heights(win) == WIN_REDUMP_QUANTUM
    rep = W.compare_dumps(DUMP, win)
    assert rep.ok, rep.findings
    assert rep.heights_repool == f"{PACK_QUANTUM} -> {WIN_REDUMP_QUANTUM}"


def test_heights_quantum_not_compared_once_no_elevated_row_remains():
    edited = W.edit_dump(DUMP, _plan(DUMP))
    assert "OBJECT_MSL" not in edited
    assert _heights(edited) == PACK_QUANTUM          # the edit copies the row
    actual = edited.replace(f"HEIGHTS {PACK_QUANTUM}", f"HEIGHTS {DEFAULT_QUANTUM}")
    rep = W.compare_dumps(edited, actual)
    assert rep.ok, rep.findings
    assert rep.heights_repool == ""        # not stored at all, so not a re-pool
    # a MISSING row is still a structural loss
    gone = "\n".join(ln for ln in actual.splitlines()
                     if not ln.startswith(W.HEIGHTS_KEYWORD)) + "\n"
    assert not W.compare_dumps(edited, gone).ok


def test_a_missing_heights_row_is_a_loss_while_an_elevated_row_remains():
    gone = "\n".join(ln for ln in DUMP.splitlines()
                     if not ln.startswith(W.HEIGHTS_KEYWORD)) + "\n"
    rep = W.compare_dumps(DUMP, gone)
    assert not rep.ok
    assert rep.heights_repool == ""


# ── DSFTool: the measurement the law stands on ───────────────────────

@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_pack_heights_survive_an_unedited_round_trip(tmp_path, capsys):
    """The pack's ENCODED scale survives; the dumped text need not say so."""
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    out, back = _encode(tmp_path, "pristine", dump, tool)
    scales = _pool_elevation_scales(back)
    _record(capsys, f"{NONDETERMINISM_RECORD} platform={sys.platform} "
                    f"case=unedited pool_scales={scales} "
                    f"heights_in={PACK_QUANTUM} heights_text={_heights(back)!r}")
    assert scales and all(s == PACK_POOL_SCALE for s in scales), scales
    rep = W.verify_roundtrip(str(out), dump, tool)
    assert rep.ok, rep.findings
    assert rep.max_elev_m <= W.TOL_ELEV_M


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_one_remaining_elevated_row_keeps_the_encoded_pack_scale(tmp_path,
                                                                capsys):
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    edited = W.edit_dump(dump, _plan(dump, keep_last=True))
    assert edited.count("OBJECT_MSL ") == 1
    out, back = _encode(tmp_path, "one", edited, tool)
    scales = _pool_elevation_scales(back)
    _record(capsys, f"{NONDETERMINISM_RECORD} platform={sys.platform} "
                    f"case=one-elevated-row pool_scales={scales} "
                    f"heights_in={PACK_QUANTUM} heights_text={_heights(back)!r}")
    assert scales and all(s == PACK_POOL_SCALE for s in scales), scales
    assert W.verify_roundtrip(str(out), edited, tool).ok


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_full_conversion_passes_and_the_heights_text_decides_nothing(tmp_path):
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    edited = W.edit_dump(dump, _plan(dump))
    out, _back = _encode(tmp_path, "conv", edited, tool)
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
    """Record (platform, DSFTool version, quantum); assert the stable half.

    This is the record #166 asks for and the one a strict xfail cannot
    be: an xfail says only THAT a platform differs.  This says WHICH
    BINARY produced which quantum, in the CI log of the run that measured
    it, so the attribution is read off the matrix instead of guessed --
    and the day the bundled ``Utils/win/DSFTool.exe`` is replaced, the
    recorded version changes beside the quantum it produced.

    What it does NOT do any more is assert a platform map.  The quantum
    is the field #181 measured as path-dependent, so that assertion made
    PRs red or green for reasons nothing in their diff could reach
    (#234 flipped both ways on one commit, #242 likewise).  The
    assertion here is the ENCODED scale, which does not move.
    """
    tool = _dsftool_path()
    version = _dsftool_version(tool, tmp_path)
    dump = _platform(DUMP, tool, tmp_path)
    _out, back = _encode(tmp_path, "attribution", dump, tool)
    quantum = _heights(back)
    scales = _pool_elevation_scales(back)
    _record(capsys, f"{ATTRIBUTION_RECORD} platform={sys.platform} "
                    f"version={version!r} heights_in={PACK_QUANTUM} "
                    f"heights_out={quantum} pool_scales={scales}")
    assert scales and all(s == PACK_POOL_SCALE for s in scales), (
        f"the pack's {PACK_QUANTUM} quantum did not survive the round trip "
        f"in the POOLS, which is the observable the law reads -- "
        f"re-attribute #166/#131 from this record: platform={sys.platform} "
        f"version={version!r} heights_out={quantum} pool_scales={scales}")


# ── #181: WHAT THE DUMPED ``HEIGHTS`` LINE IS WORTH ──────────────────────
#
# #181 reported the DSFTool twins above as ORDER-DEPENDENT: green alone,
# red after the elevation-inset files, with a wrong quantum coming back,
# and hypothesised shared Python state (the dump cache, a module global
# keyed on something that collides).  That hypothesis is REFUTED.
# Measured on linux, DSFTool 2.4.0-b1, 2026-10-02 (and again by this lane
# from a bare shell with no pytest in sight):
#
# * The re-dump's ``HEIGHTS`` line is not a function of the DSF.  One
#   binary, one 537-byte input (``cmp``-identical bytes), rc 0:
#   ``/tmp/m1/x.dsf -> /tmp/m1/aa.text`` dumps ``0.06250  # max
#   encodeable 4095.93750`` and ``/tmp/bt181/mA/x.dsf ->
#   /tmp/bt181/mA/aa.text`` dumps ``1.00000  # max encodeable
#   65535.00000``, 3/3 each.  In ONE directory a FRESH output path gives
#   ``1.00000`` and overwriting an EXISTING one gives ``0.06250``.
# * ``strace -e trace=openat,write`` over both runs: the only difference
#   is one extra ``openat(..., O_DIRECTORY)`` of the output path's extra
#   component — DSFTool walks the output path — and the ``write`` length
#   (845 vs 838 bytes, exactly the 7 by which the two lines differ).  The
#   input is read identically; nothing else is opened.  An output-path
#   depth sweep flips the answer at 9 components.  It does not move with
#   the input path, the cwd, the environment, rlimits, the signal mask,
#   the locale or memory pressure (all compared and equal, #181).
# * So the "run order" was a correlation: a different order gives
#   different tmp paths, and the pytest basetemp happens to be a
#   neighbourhood where this build prints its default scale.
# * The ENCODED quantum is NOT affected.  In both dumps the object pools
#   carry ``4095.93750`` (= 0.06250 x 65535), i.e. the round trip really
#   does preserve the pack's scale; only the text line DSFTool writes
#   about it is unreliable.
#
# NO CONFTEST ISOLATION CAN FIX THAT, because no Python-level state is
# involved: the remedy is that nothing we assert or refuse on reads the
# field.  That is why every twin above asserts the pool scale and the
# verifier's verdict, and the verifier compares the quantum by ENCODABLE
# RANGE (``dsf_write._heights_reconciled``).  The twin below keeps the
# unstable field measured, in the log, on every platform.

@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_the_encoded_quantum_survives_whatever_the_heights_text_says(
        tmp_path, capsys):
    """The round trip preserves the pack's scale; the text may not say so.

    Dumps ONE encoded DSF to two different output paths — nothing about
    the file differs, so a dump that is a function of the file must agree
    — and asserts the ENCODED scale is identical both times.  Whether the
    ``HEIGHTS`` text agreed is printed, not asserted: that is the #181
    measurement, and the day this build becomes deterministic the record
    says so without a test flipping colour for the wrong reason.
    """
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    (encoded, _back) = _encode(tmp_path, "stability", dump, tool)

    texts = []
    # Two output paths as unlike each other as a test may make them --
    # this build's answer moved with nothing else (#181).
    deep = tmp_path / ("nested" + "/deeper" * 4)
    deep.mkdir(parents=True)
    for out in (tmp_path / "s.text", deep / ("a" * 40 + ".text")):
        texts.append(Path(W.dump(str(encoded), str(out), tool)).read_text(
            encoding="utf-8"))

    scales = [_pool_elevation_scales(text) for text in texts]
    quanta = [_heights(text) for text in texts]
    _record(capsys, f"{NONDETERMINISM_RECORD} platform={sys.platform} "
                    f"case=two-output-paths pool_scales={scales} "
                    f"heights_in={PACK_QUANTUM} heights_text={quanta} "
                    f"stable={len(set(quanta)) == 1}")

    assert scales[0] == scales[1], (
        f"the ENCODED quantum moved between two dumps of one DSF, which "
        f"would make the round trip itself unsound (not merely its text "
        f"record): pool_scales={scales} heights_text={quanta}")
    assert scales[0] and all(scale == PACK_POOL_SCALE for scale in scales[0]), (
        f"the pack's {PACK_QUANTUM} quantum did not survive the round trip "
        f"in the pools either: pool_scales={scales} heights_text={quanta}")


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_the_verifier_passes_wherever_the_dumped_heights_text_lands(tmp_path):
    """The order-independence twin: the verdict must not follow the path.

    #181's symptom was three twins going red because the dump landed in a
    neighbourhood where this build prints its default scale.  Here the
    SAME encoded DSF is verified against the SAME expected text through
    two deliberately unlike output paths, one of them 9 components deep —
    the depth that flips the printed quantum on linux.  Both verdicts
    must be ``ok``, and the recorded re-pool is whatever the text said.
    """
    tool = _dsftool_path()
    dump = _platform(DUMP, tool, tmp_path)
    encoded, _back = _encode(tmp_path, "verdict", dump, tool)

    deep = tmp_path / "/".join(f"l{i}" for i in range(9))
    deep.mkdir(parents=True)
    for out in (tmp_path / "near.verify.text", deep / "far.verify.text"):
        rep = W.verify_roundtrip(str(encoded), dump, tool, str(out))
        assert rep.ok, (str(out), rep.findings)
        assert rep.max_elev_m <= W.TOL_ELEV_M
        assert rep.heights_repool in ("", f"{PACK_QUANTUM} -> "
                                          f"{_heights(Path(out).read_text(encoding='utf-8'))}")
