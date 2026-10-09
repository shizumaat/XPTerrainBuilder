"""ISSUE #321 TWIN: an arm flag of ``tools/v2_solve_replay.py`` either
takes effect in the run and is named on stdout, or the run REFUSES.

``--replay PKL --from classify --rule apron.arm_reread_factor=0.0 --emit
OUT`` printed no arm line and no refusal and emitted the UNARMED result
(``--rule`` is read by ``--capture`` and ``--reclassify`` alone).  The
table in ``tools/replay_arms.py`` now decides every flag x run pairing;
this file spells the table a second time, cell by cell, and asserts the
gate agrees with it — and that the command line refuses BEFORE it opens
the capture.

Offline: no capture, no corpus, no engine import.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "v2_solve_replay.py"
sys.path.insert(0, str(ROOT / "tools"))
import replay_arms as A  # noqa: E402

S = ("classify", "planar", "shapes", "constraints")
REPLAY = {f"replay/{s}" for s in S}
DUMP = {f"stage1-dump/{s}" for s in S}
ARRANGE = {f"{m}/{s}" for m in ("replay", "pad-read", "stage1-dump")
           for s in ("classify", "planar")}

#: THE TABLE, spelled independently: flag -> the runs it takes effect in.
#: Every other (flag, run) cell is a REFUSAL.
EXPECT = {
    "--rule": {"capture", "reclassify"},
    "--placement": {"capture"} | ARRANGE,
    "--cifp-dir": {"capture"},
    "--data-overlay": {"capture"},
    "--mod-cache-root": {"capture"},
    "--design-weight": REPLAY | DUMP | {"stage1-dump/why-from"},
    "--drop-generator": REPLAY | DUMP | {"stage1-dump/why-from"},
    "--chord-fill": REPLAY,
    "--method": REPLAY,
    "--probe-arm": {"probe-site"},
    "--late-from": REPLAY,
    "--gap-free": {"replay/classify", "replay/planar"},
}

#: every other option of the tool, DECIDED not to be an arm: a mode
#: selector, an output, a read's own parameter, or the pool pin
NOT_ARMS = {
    "--capture", "--out", "--reclassify", "--replay", "--from", "--json",
    "--z-out", "--design-verbose", "--shape-dump", "--pad-read", "--workers",
    "--rim-diagnostics", "--site", "--site-radius", "--emit", "--verify",
    "--solved-out", "--why-from", "--why-vertex", "--why-at", "--why-hard",
    "--why-hard-stage", "--why-relax", "--why-hump", "--bank-from",
    "--probe-site", "--probe-drop", "--stage1-dump", "--stage1-diff",
    "--movers",
}

CELLS = [(f, c) for f in A.ARM_FLAGS for c in A.CONTEXTS]


def test_the_table_covers_every_flag_and_every_run():
    assert set(A.ARM_FLAGS) == set(EXPECT)
    assert len(A.CONTEXTS) == len(set(A.CONTEXTS)) == 19
    for flag, where in EXPECT.items():
        assert where <= set(A.CONTEXTS), flag


@pytest.mark.parametrize("flag,context", CELLS)
def test_each_cell_arms_by_name_or_refuses_by_name(flag, context):
    if context in EXPECT[flag]:
        lines = A.arm_gate(context, {flag: "V"})
        assert len(lines) == 1 and f"ARM {flag} V" in lines[0]
        assert context in lines[0]
    else:
        with pytest.raises(SystemExit) as exc:
            A.arm_gate(context, {flag: "V"})
        msg = str(exc.value)
        assert msg.startswith("REFUSED: ") and flag in msg and context in msg
        # the refusal says where the flag DOES take effect
        assert all(c in msg for c in EXPECT[flag])


def test_one_inert_flag_refuses_the_whole_run():
    with pytest.raises(SystemExit) as exc:
        A.arm_gate("replay/classify", {"--placement": "k=v", "--rule": "a.b=1",
                                       "--cifp-dir": "/x"})
    msg = str(exc.value)
    assert "--rule" in msg and "--cifp-dir" in msg and "--placement" not in msg


def test_every_option_of_the_tool_is_decided():
    """A new option lands in the arm table or in ``NOT_ARMS`` — never
    undecided (the data-overlay flag is spelled through a constant)."""
    src = TOOL.read_text(encoding="utf-8")
    opts = set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', src))
    assert "DATA_OVERLAY_FLAG, dest=" in src
    opts.add("--data-overlay")
    assert opts == set(A.ARM_FLAGS) | NOT_ARMS, (
        opts ^ (set(A.ARM_FLAGS) | NOT_ARMS))


def _run(*argv):
    return subprocess.run([sys.executable, str(TOOL), *argv],
                          capture_output=True, text=True, timeout=120)


def test_the_issue_command_refuses_before_reading_the_capture(tmp_path):
    """The #321 command line.  The pickle does not exist: a refusal that
    names ``--rule`` proves the gate ran before the capture was opened."""
    r = _run("--replay", str(tmp_path / "absent.pkl"), "--from", "classify",
             "--rule", "apron.arm_reread_factor=0.0", "--emit", str(tmp_path))
    assert r.returncode != 0
    assert "REFUSED: --rule apron.arm_reread_factor=0.0" in r.stderr
    assert "replay/classify" in r.stderr and "reclassify" in r.stderr
    assert not list(tmp_path.iterdir())


def test_an_effective_arm_is_named_before_the_run(tmp_path):
    """``--design-weight`` takes effect at ``--from constraints``: its arm
    line is printed, then the (absent) capture is what fails."""
    r = _run("--replay", str(tmp_path / "absent.pkl"),
             "--design-weight", "solver=qp", "--drop-generator", "apron")
    assert "REPLAY ARM --design-weight solver=qp (takes effect at "\
           "replay/constraints)" in r.stdout
    assert "REPLAY ARM --drop-generator apron" in r.stdout
    assert "REFUSED" not in r.stderr and r.returncode != 0


# ── ISSUE #420: an unknown --drop-generator name REFUSES ─────────────
# ``--drop-generator <unknown>`` filtered rows by a name no row carries,
# so it dropped NOTHING and said nothing — the run was reported under an
# arm never applied.  ``replay_arms.drop_gate`` refuses it (pure, below);
# ``v2_solve_replay.drop_rows`` is the ONE filter every assembly site
# calls, and it asks the gate first (the engine's row model, no corpus).

def test_drop_gate_passes_a_generator_a_head_and_the_pseudo_generator():
    A.drop_gate(["taxi_box", "rulesets.eat ceiling", "eat_ramp_reach"],
                {"taxi_box"}, {"rulesets.eat ceiling"})
    A.drop_gate([], set(), set())


def test_drop_gate_refuses_an_unknown_name_listing_the_known_ones():
    with pytest.raises(SystemExit) as exc:
        A.drop_gate(["taxi_box", "no_such_gen"], {"taxi_box", "apron"},
                    {"plane_gradient"})
    msg = str(exc.value)
    assert msg.startswith("REFUSED: --drop-generator no_such_gen ")
    assert "taxi_box " not in msg.split("Known")[0]     # only the unknown is named
    assert "Known generators: apron, eat_ramp_reach, taxi_box." in msg
    assert "Known ruling heads: plane_gradient" in msg


def test_every_drop_site_goes_through_the_one_filter():
    src = TOOL.read_text(encoding="utf-8")
    assert src.count("ruling_head(r) not in drop") == 1     # drop_rows alone
    assert src.count("drop_rows(") == 4                     # def + 3 sites


def test_drop_rows_refuses_before_filtering_and_drops_by_generator_or_head():
    import importlib.util
    sys.path.insert(0, str(ROOT / "src"))
    from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
    spec = importlib.util.spec_from_file_location("_v2_solve_replay_drop", TOOL)
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    cs = ConstraintSet.from_rows([
        Pin(0, 1.0, Source("taxi_box", "law_a (why)")),
        Pin(1, 2.0, Source("apron_within_shape", "law_b")),
        Pin(2, 3.0, Source("wall_terrace", "law_c (owner)"))])
    kept = R.drop_rows(cs, ["taxi_box", "law_b"])
    assert [r.v for r in kept.rows()] == [2]
    # a REGISTERED generator with no rows in this set is known, not refused
    assert len(R.drop_rows(cs, ["runway_profile"]).rows()) == 3
    with pytest.raises(SystemExit) as exc:
        R.drop_rows(cs, ["taxi_boxx"])
    assert "REFUSED: --drop-generator taxi_boxx" in str(exc.value)
    assert "law_a" in str(exc.value) and "wall_terrace" in str(exc.value)
    # the ribbon-free stage-1 set is checked on the full set, not again
    assert len(R.drop_rows(cs, ["taxi_boxx"], check=False).rows()) == 3


def test_gap_free_and_late_from_are_two_runs():
    """``--gap-free`` solves the base a ``--late-from`` run reads (the build's
    own ``gap_free``, never a second spelling of it)."""
    src = TOOL.read_text()
    assert "from auto_patch_v2.pipeline.stage_one_map import gap_free as _gap_free" in src
    assert "not both in one run" in src


def test_the_base_map_keeps_a_gap_apron_cell():
    """spec §59: a piece classed apron is a stage-1 cell — the base keeps it."""
    import types
    sys.path.insert(0, str(ROOT / "src"))
    from auto_patch_v2.pipeline.stage_one_map import gap_free
    import dataclasses as dc

    @dc.dataclass(frozen=True)
    class Cl:
        cells: tuple
    mk = lambda ref: types.SimpleNamespace(ref=ref)  # noqa: E731
    cl = Cl((mk("pav1"), mk("gap:0"), mk("gapapron:0"), mk("gap:3")))
    assert [c.ref for c in gap_free(cl).cells] == ["pav1", "gapapron:0"]
    assert gap_free(Cl((mk("pav1"), mk("gapapron:0")))) is None
