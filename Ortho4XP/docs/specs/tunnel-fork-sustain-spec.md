# Tunnel fork sustained-divergence — spec (2026-08-07, FROZEN, amended F-2)

Author: lead session (Fable). Status: FROZEN as amended. Closes the
FAIL-1 residual of `tunnel-ramp-cut-boundaries-spec.md` (20 over-cap
`within_shape` rows on `tunnel_ramp`, worst 42.46 %).

**AMENDMENT (same day).** §1-§2's premise ("separation runs
9.52 → 0.00 m") was a distance-to-line reading; under the probe's own
equal-arc-length metric the arm spread is 7.3-9.1 m and sustained, so
the §2 predicate is provably inert at OTHH (landed anyway as a correct
guard for genuine converging twins — keep it). The operative defect is
FRAME MISMATCH in the threshold: `spread` is a 2-D euclidean
same-station distance but the reference `cluster_span` is a 1-D
perpendicular projection of the portal nodes onto the head walk's
first-segment perpendicular — near-zero for implied-bore portals
staggered longitudinally along an oblique pavement edge, so twin
carriageways read as permanently forked. §2b below replaces the
threshold; it must be CONFIRMED before implementation (§2b step 0).

## 1. The defect

`_emit_portal_cluster`'s fork probe declares a fork when member-portal
spread exceeds `cluster_span + _div_margin` at ANY station (fires at
s ≈ 157.5 m on a 1.2 m relative splay), and never asks whether the
members re-converge. The A-site cluster is twin one-way service
carriageways (`F|-98`/`F|-99`, implied bore) whose separation runs
9.52 → 0.00 m — they merge into one road (shared end node), yet the
probe emits two independent fork arms that overlap (93.89 m² polygon
overlap), intern into each other, and mint cross-arm adoption rows
(16 rows) plus weld-splice spikes in the sibling cluster
(`-11764…-11777`, 4 rows). The `s_div is None` branch already emits
the correct single combined surface (combined width ≈ 15.5 m vs the
22 m default envelope).

## 2. F-1 — Fork requires SUSTAINED divergence

In `bridges.py`'s fork probe: a cluster forks ONLY when the member
spread, having crossed the threshold, REMAINS above it through the end
of the probe window (a genuine Y-split: arms that keep separating). A
spread that falls back to (or below) `cluster_span` before the window
ends is twin-carriageway noise — `s_div = None`, the existing
combined-ramp path runs. Implement with a named module constant beside
`_div_margin` (comment citing this spec + the measured 9.52→0.00
profile); no config-file knob. The existing genuine-fork behavior must
be preserved and unit-tested (synthetic Y-split with monotone
divergence still forks; synthetic converging twins do not).

Expected consequence (verify, do not force): both A-site clusters
collapse to single combined surfaces; the 16 cross-arm rows and — if
the splice donors were the sibling arm — the 4 weld-splice rows
disappear. If weld-splice rows SURVIVE with the arms merged, they are
the out-of-scope `layout.py:1982` class: STOP and report, do not touch
`layout.py`.

## 2b. F-2 — Frame-consistent fork threshold (the operative fix)

**Step 0 — CONFIRM (one `O4_TUNNEL_DEBUG=1` build, authorized):** the
new debug line prints the fork decision and `cluster_span`; the
mechanism is confirmed iff `cluster_span` measures ≪ the portals'
euclidean separation (~9.5 m) for the A-site clusters. If it does NOT
(cluster_span ≈ 9.5 m and the threshold fired anyway): STOP and
report — the inference failed and no further change lands.

**The change:** fork on divergence GROWTH in ONE frame. Let
`spread(s)` be the existing equal-arc-length euclidean member
separation and `spread₀` the first station's value (the members'
separation where the walks begin). The fork condition becomes
`spread(s) − spread₀ > _div_margin`, sustained per §2's F-1 window
rule (which stays). `cluster_span` drops out of the fork predicate
entirely (leave its other uses untouched). Twin carriageways
(spread₀ ≈ 9, growth ≈ 0) never fork; a genuine Y from one throat
(spread₀ ≈ 0, growth monotone) forks exactly as before. Update the
F-1 synthetic tests' geometry only if their pass/fail intent requires
it — the Y-split must still fork, the converging twins must still not,
and add a third synthetic: STAGGERED parallel twins (portals offset
along the walk direction, constant lateral separation) must NOT fork —
that is the OTHH shape. Named constant semantics and the debug line
update accordingly.

## 3. T-1 — Promote the acceptance checker (owed under RULINGS 7e90032)

The scratchpad `accept_othh.py` reached its second use. Promote it
into `tools/` with: a generic name and CLI (patch path, control path,
site list / thresholds as arguments — no hardcoded `/tmp` or OTHH
literals baked in; OTHH's site set may ship as a named default
profile), an `tools/INDEX.md` entry in the same commit-unit, and a
twin test (the CLI and any library entry must share one code path;
follow the check_grade/census twin pattern at whatever small scale
fits). Census numbers inside it must come from `check_grade` /
`tools/harness/census.py` code paths — never a private re-count.

## 4. Acceptance — ONE OTHH build (`--tag fork-sustain`) + matched census

1. Unit tests: sustained-Y still forks; converging twins do not; the
   promoted tool's twin.
2. Suite through the ledger (blast-named + tunnel files +
   test_harness).
3. Build asserts:
   * over-cap `within_shape` rows on `tunnel_ramp`: **≤ 2** (the
     `-11318` `object_bridge_ramp` pair only);
   * ALL parent + boundary-round wins hold (mouth ≤ 15 m of D;
     A/B1/B2/B3 ramps ≤ 60 m; covered spans clean; 0
     `tunnel_low_connector`; no ≥ 8 m-spread ways in the C2 footprint;
     `building1` flat; sub-grade role counts at control; retreat walls
     near ramps ≤ 5);
   * matched ADJUDICATED delta vs `/tmp/harness/OTHH_matched_ctl.osm`
     ≤ **−24** (must not regress the accepted round);
   * actionable sites ≤ **82** (control's number; the accepted round
     read 83).
4. Build-time statement (tripwire only).

## 5. Guards

Materiality 0.01 m / 0.01 pp; attempt cap 2 then STOP-and-report;
`.progress` heartbeat; budget: 1 build + census + suite.

## OUTCOME (2026-08-07, recorded)

F-1 landed, unit-proven, INERT at OTHH (kept as a guard: synthetic
converging twins 1 throat → 0; genuine Y preserved). F-2 was
FALSIFIED at §2b step 0 before implementation: the step-0 frame audit
(9 clusters) measured `cluster_span` 9.51 vs portal euclidean 9.52 at
the A-site — no frame collapse; the arm spread genuinely grows
9.45 → 13.25 m and HOLDS, because the probe window (277.1 m) runs past
`F|-98`'s length (229.6 m) onto continuations that truly separate.
F-2 would have been decision-identical on all 9 clusters (max
predicate divergence 0.22 m against a 2.0 m margin). The one real
frame-mismatch specimen — cluster (295, −2490), span 0.53 vs 30.01 m —
forks under every predicate (+212.8 m growth): the class exists but is
not load-bearing at OTHH; parked. T-1 (tool promotion) complete.

RESIDUAL RELOCATED: the 20 over-cap rows are a PATH CROSSING between
two lawfully-separated cluster walks (spread₀ 9.45 m ≥ the 9.2 m
`s_arm` requirement) whose carriageways merge at a shared source node
— the arms overlap 93.89 m² and share 6 nodes. A fork-predicate change
cannot address walks that meet. Next-round design options are with the
owner (reverse-Y join / overlap clip / accept-and-park).

RULED (owner, same day): ACCEPT AND PARK — the walk-crossing residual
(20 rows, +1 actionable site) stays; reverse-Y join is the recorded
design direction if re-armed. See RULINGS "A-site walk-crossing
residual".
