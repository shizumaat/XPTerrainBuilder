# DEM-follow joint reconciliation: close the flex dead zone

Fable spec, 2026-08-05. From the demfollow probe (scratchpad
demfollow_probe/ — read out/ arms first; the verdict is canon-grade:
ONE defect, interventionally sufficient). Lines against 446e53b.
BINDING: RULINGS.md (runway flex law: CIFP immovable, profiles flex
within grade law; feasibility-is-guaranteed; convergence guards;
timing suspended).

## Mechanism (probe-attributed)
O4_RUNWAY_DEM_FOLLOW aborts HEAZ (rc=3): the follow deviation is
computed PER RUNWAY; 18/36 sinks −0.12 at its join anchor, 05/23
sinks −0.14 at its threshold-join — a +0.02 m differential across a
292 m taxiway priced at exactly 1.5000%, converting 2.6 mm of slack
into a 17.4 mm inversion on all 47 route nodes (the geodesic between
seeds 1579/1437). Band value falsified (0.5 m arm byte-identical);
ordering falsified (band re-derives already); (3151,3152) exonerated
(threshold-anchored, moved 0.0000). Restoring ONE anchor builds rc=0.
THE DEAD ZONE: the deficit 0.0174 sits below the B2 flex's
_DEMAND_TOL_M (0.05) and above the band materiality (0.01) — the
machinery that exists to drain cross-runway taxi tension never sees
demands in [0.01, 0.05).

## The fix (minimal, single-pass: let the flex do its job)
Align the flex demand tolerance with the band materiality:
_DEMAND_TOL_M 0.05 → 0.01 (one constant; cite this spec at the site).
The B2 envelope already prices the taxi route at full budgets; with
the tolerance aligned, the 0.0174 demand enters round 0 and the ÷2
origin split drains ~9 mm from each runway — inside every clamp
(slack ~1.75/0.115 m, budget 4.0). No new machinery. RISK to
pre-register: more sub-5cm demands enter the flex everywhere — bins
and rounds may rise; the honest B2 line quotes demand-count deltas
per airport; any NEW over-cap segment or census rise is a STOP.

## Verification (streamlined; this is a DEM-follow-world fix — the
## gate stays "0"; the evidence feeds the composed-world flip)
Stress: HEAZ (the abort: DEM-follow arm builds rc=0, final-band
inversions ≤ 2 sub-materiality = the control's), then the composed
arm (DEM-follow + SELF_UNLOCK): rc=0. Ride-along: HECA DEM-follow arm
(the flexconv (ii) result must HOLD: builds, 0 inversions; its
end-zone table ≤ its recorded 13-segment state). Sentinel: CYXY
gate-off identity 2x + one DEM-follow arm (no regression vs its
recorded state). KCLT DEM-follow arm: builds, census quoted (first
KCLT read of this world — report only). Default arms byte-identical
everywhere (the constant only matters when flex runs — it runs by
default! _DEMAND_TOL_M is LIVE at defaults: gate-off identity 2x at
HEAZ + CYXY + HECA vs release anchors is REQUIRED and a change is a
STOP-and-report — pre-register whether the default surface moves; if
it does, this round becomes flip-gated and lands via the next tip).
Suite: same reds vs matched control; twins: the dead-zone synthetic
(a 0.02 cross-runway demand drains), the HEAZ regression twin.
STOP: default-surface change (report, do not land ungated); any new
over-cap; composed HEAZ still aborts (the joint-follow design (b)
returns to the designer); second miss.
