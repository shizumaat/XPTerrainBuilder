"""Unit tests for the CONTINUOUS break-blend weight in
``feasibility_project`` (docs/specs/break-blend-continuity-spec.md, gate
``O4_BREAK_BLEND_CONTINUOUS``, default "0").

Hermetic — no build, no fixtures.  Covers the spec's acceptance item 1:

  (a) a synthetic pocket whose envelope is FLAT across a witness frontier
      still gets a 12 m step from the shipped weight (two adjacent nodes
      inherit ``dist`` from two different value-winning paths) and grades
      smoothly under the gate;
  (b) the gate moves NO break membership and NO envelope value — only the
      weight (spec: "this changes no envelope, no witness, no break
      membership");
  (c) the degenerate ``else 0.5`` branch is counted by production, fires
      on the constructed same-node-witness case, and fires NOWHERE in the
      pocket under either arm;
  (d) gate off (unset or "0") is identical.

THE POCKET (one frame, stated once).  A 101-node chain, budget 1.0 m per
step, with a hard LOW anchor at each end (node 0 at 0.0 m, node 100 at
21.0 m) and one hard HIGH anchor (node 101 at 200.0 m) welded to the
middle node with a 20 m budget.  Every free node is broken: its floor
(from the high anchor) is ~130-180 m above its ceiling (from the nearer
low anchor).  The ceiling WITNESS changes at node 60/61 — and because a
ceiling value is exactly ``z_anchor + path budget``, the recorded distance
jumps by the two anchors' value gap (60 -> 39) while the ceiling VALUE
does not move at all (60.0 both sides).  That is the discontinuity the
spec attributes; here it is isolated with nothing else in the graph.
"""
import pytest

import auto_patch.config as cfg
from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)


@pytest.fixture(autouse=True)
def _zero_emit_margin(monkeypatch):
    monkeypatch.setattr(cfg, "EMIT_QUANTIZATION_MARGIN_M", 0.0)


# ── the pocket ───────────────────────────────────────────────────────────

CHAIN = 100            # nodes 0..100, budget 1.0 m between neighbours
HIGH = CHAIN + 1       # the contradicting high anchor
FRONTIER = 60          # the ceiling witness frontier (0 wins <=60, 100 >60)


def _pocket():
    edges = [(i, i + 1, 1.0) for i in range(CHAIN)]
    edges.append((CHAIN // 2, HIGH, 20.0))
    elev = [100.0] * (HIGH + 1)
    elev[0] = 0.0
    elev[CHAIN] = 21.0
    elev[HIGH] = 200.0
    return edges, elev, {0, CHAIN, HIGH}


def _run(edges, elev, hard, *, gate, monkeypatch, capsys, tmp_path,
         label="pocket"):
    """One projection; returns ``(elev, broken, t_fallback_count)``.

    The fallback count is read from the PRODUCTION forensics row — the
    spec's channel for it — not from a test-only hook."""
    if gate is None:
        monkeypatch.delenv("O4_BREAK_BLEND_CONTINUOUS", raising=False)
    else:
        monkeypatch.setenv("O4_BREAK_BLEND_CONTINUOUS", gate)
    monkeypatch.setenv("O4_BREAK_FORENSICS", str(tmp_path / f"{label}.csv"))
    out = list(elev)
    broken: set = set()
    feasibility_project(out, [{"edges": edges}], set(hard),
                        force_scalar=True, broken_out=broken,
                        forensics={"label": "", "classes": {},
                                   "nodes_ll": None})
    text = capsys.readouterr().out
    marker = "t_fallback="
    assert marker in text, text
    count = int(text.split(marker)[1].split()[0].strip())
    return out, broken, count


# ── (a) the discontinuity, and its repair ────────────────────────────────

def test_shipped_weight_steps_at_the_witness_frontier(monkeypatch, capsys,
                                                      tmp_path):
    edges, elev, hard = _pocket()
    off, broken, _ = _run(edges, elev, hard, gate=None, monkeypatch=monkeypatch,
                          capsys=capsys, tmp_path=tmp_path)
    assert broken == set(range(1, CHAIN))
    step = abs(off[FRONTIER + 1] - off[FRONTIER])
    # the envelope is FLAT across the frontier, so this step is the weight
    # and nothing else
    assert step > 10.0, step
    neighbours = max(abs(off[i + 1] - off[i])
                     for i in range(1, CHAIN - 1) if i != FRONTIER)
    assert step > 4.0 * neighbours, (step, neighbours)


def test_continuous_weight_grades_the_pocket_smoothly(monkeypatch, capsys,
                                                      tmp_path):
    edges, elev, hard = _pocket()
    off, _, _ = _run(edges, elev, hard, gate="0", monkeypatch=monkeypatch,
                     capsys=capsys, tmp_path=tmp_path, label="off")
    on, _, _ = _run(edges, elev, hard, gate="1", monkeypatch=monkeypatch,
                    capsys=capsys, tmp_path=tmp_path, label="on")
    off_max = max(abs(off[i + 1] - off[i]) for i in range(1, CHAIN - 1))
    on_max = max(abs(on[i + 1] - on[i]) for i in range(1, CHAIN - 1))
    assert off_max > 10.0, off_max
    assert on_max < 3.5, on_max
    assert on_max < off_max / 3.0
    # and the frontier itself is now an ordinary interior step
    assert abs(on[FRONTIER + 1] - on[FRONTIER]) <= on_max


def test_continuous_weight_leaves_no_local_pit(monkeypatch, capsys, tmp_path):
    """The owner-visible defect is a PIT: a node metres below both of its
    neighbours.  Under the gate no interior node may sit outside the
    interval its two neighbours span by more than one budget."""
    edges, elev, hard = _pocket()
    on, _, _ = _run(edges, elev, hard, gate="1", monkeypatch=monkeypatch,
                    capsys=capsys, tmp_path=tmp_path)
    worst = max(min(on[i - 1], on[i + 1]) - on[i] for i in range(2, CHAIN - 1))
    assert worst < 1.0, worst


# ── (b) the gate moves the weight and nothing else ───────────────────────

def test_gate_moves_no_break_membership(monkeypatch, capsys, tmp_path):
    edges, elev, hard = _pocket()
    _, broken_off, _ = _run(edges, elev, hard, gate="0",
                            monkeypatch=monkeypatch, capsys=capsys,
                            tmp_path=tmp_path, label="off")
    _, broken_on, _ = _run(edges, elev, hard, gate="1",
                           monkeypatch=monkeypatch, capsys=capsys,
                           tmp_path=tmp_path, label="on")
    assert broken_on == broken_off


def test_gate_moves_nothing_outside_the_break(monkeypatch, capsys, tmp_path):
    """A FEASIBLE component in the same call (hard anchor + a chain the
    envelope merely clamps) must come out bit-for-bit identical on both
    arms: the gate may touch the blend weight and nothing else."""
    edges, elev, hard = _pocket()
    feas = [HIGH + 1 + k for k in range(5)]          # 102..106
    edges = edges + [(feas[k], feas[k + 1], 2.0) for k in range(4)]
    elev = elev + [50.0, 80.0, 80.0, 80.0, 80.0]
    hard = set(hard) | {feas[0]}
    off, _, _ = _run(edges, elev, hard, gate="0", monkeypatch=monkeypatch,
                     capsys=capsys, tmp_path=tmp_path, label="off")
    on, _, _ = _run(edges, elev, hard, gate="1", monkeypatch=monkeypatch,
                    capsys=capsys, tmp_path=tmp_path, label="on")
    assert off[feas[0]:] == on[feas[0]:]
    assert off[feas[1]] != 80.0                      # it really was clamped


def test_gate_moves_no_hard_value(monkeypatch, capsys, tmp_path):
    edges, elev, hard = _pocket()
    on, _, _ = _run(edges, elev, hard, gate="1", monkeypatch=monkeypatch,
                    capsys=capsys, tmp_path=tmp_path)
    for h in hard:
        assert on[h] == elev[h]


# ── (c) the degenerate branch ────────────────────────────────────────────

def test_degenerate_branch_never_fires_in_the_pocket(monkeypatch, capsys,
                                                     tmp_path):
    edges, elev, hard = _pocket()
    for gate in ("0", "1"):
        _, _, count = _run(edges, elev, hard, gate=gate,
                           monkeypatch=monkeypatch, capsys=capsys,
                           tmp_path=tmp_path, label=f"g{gate}")
        assert count == 0, (gate, count)


@pytest.mark.parametrize("gate", ["0", "1"])
def test_degenerate_branch_fires_on_the_same_node_witness(gate, monkeypatch,
                                                          capsys, tmp_path):
    """Both witnesses AT the node (zero-budget welds to a low and a high
    anchor at once): both distance fields are genuinely zero, so the
    ``0.5`` branch is the only answer — the one case the spec keeps."""
    edges = [(0, 1, 0.0), (0, 2, 0.0)]
    elev = [50.0, 0.0, 100.0]
    out, broken, count = _run(edges, elev, {1, 2}, gate=gate,
                              monkeypatch=monkeypatch, capsys=capsys,
                              tmp_path=tmp_path, label=f"same{gate}")
    assert broken == {0}
    assert count == 1
    assert out[0] == pytest.approx(50.0)


# ── (d) gate off is gate absent ──────────────────────────────────────────

def test_gate_off_is_gate_absent(monkeypatch, capsys, tmp_path):
    edges, elev, hard = _pocket()
    absent, broken_a, fb_a = _run(edges, elev, hard, gate=None,
                                  monkeypatch=monkeypatch, capsys=capsys,
                                  tmp_path=tmp_path, label="absent")
    zero, broken_z, fb_z = _run(edges, elev, hard, gate="0",
                                monkeypatch=monkeypatch, capsys=capsys,
                                tmp_path=tmp_path, label="zero")
    assert absent == zero
    assert broken_a == broken_z
    assert fb_a == fb_z
