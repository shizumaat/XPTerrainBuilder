# HECA round 6c — cleanup: gap-fill veto deferral + item-3 join verification
# (owner ruling 2026-08-30e; residuals from round 6b)

Two residuals, one lane, ONE closing HECA build.

## A — item 6 survivors: the subdivider veto deferral

Round 6b made groundside_pavement a gap-fill blocker (RULING 4,
merged); strips over groundside fell 27→18, but TWO faces survive:
3190 (70 % of 19,408 m²) and 3192 (63 % of 16,942 m² — the same
10,630 m² lot the control's 3227 covered 100 %). Named mechanism
(measure before fixing): `gap_fill._veto_is_only_subdividers`
(gap_fill.py:441) DEFERS the veto when every blocker is a subdivider
role, and groundside_pavement is in `_POCKET_SUBDIVIDER_ROLES`, so
the new blocker feeds the deferral. Fix within RULING 4's intent: a
groundside blocker vetoes like a service road — being a subdivider
must not neutralise it. Attribute first (demonstrate the deferral
fires on these two faces), then fix; the enclave truth-table twin
from round 6b extends, not forks.

Acceptance: zero spine graded_strip area over 2837/2838 (and quote
the whole-airport spine-over-groundside m², round-6b arm: 18 strips /
26,778 m²); lawful spine elsewhere untouched.

## B — item 3: verify the metre-frame join and the road classification

Round 6b attempt 2 (`86aa26e1`) moved the lot-carried-road sever's
identity join into the metre frame after measuring the 11-dp lat/lon
join miss by 3 mm across the frame round-trip. UNVERIFIED in budget.
Verify: demonstrate the join FIRES for feed way -13192 (node -113465
at the ruling's coordinate) against groundside ring -12831 — a
diagnostic or fixture read, then the closing build. Then the site:
30.1118886,31.4064793 must classify as ROAD (service_road under the
free-road ramp law, welding toward 30.1123727,31.4059687), not
graded_strip — round 6b left it at the right height (107.18) but the
wrong class. If the sever fires and the ramp law then moves the site
value, quote the before/after; the item-2 band at the site yields to
the severed road corridor per the free-road ruling (roads grade as
roads).

RULING 3's scope is unchanged: identity-vertex trigger only, §H3
stays refuted and OFF.

## Acceptance

Site-first at both sites; ONE closing HECA build (control = round-6b
closing arm, ledger body d1a5a580652d, or the merged-main base arm if
the ledger requires a new frame — never rebuild an existing control);
census via harness, not worsened beyond attributed re-roling; twins
extended in place. Below-bar = STOP with residual quoted. NOTE: the
building79 structure-walls lane runs concurrently on a different
mechanism (dsf_reader footprints) — coordinate nothing, touch nothing
in dsf_reader/object_footprints.
