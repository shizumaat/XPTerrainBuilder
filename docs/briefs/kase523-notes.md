# kase523 — KASE #523 attribution notes (lane `claude/kase523`, base main d5f80475)

Owner site (app 1.0.385): dip at 39.2183645, -106.8653281 (A) and/or too high at
39.2185627, -106.8658607 (B). No code changed. STOPPED at an intent question.

## Numbers at the site (replay of a main capture == sw11_KASE)

Cross-section at the site, runway side to apron side (offset from the taxiway line through A):

| vertex | what | offset m | built m | DEM m | built − DEM |
|---|---|---|---|---|---|
| v642 (B) | runway-role lobe / strip edge | −36.0 | 2372.61 | 2371.77 | +0.84 |
| v643 | runway-role lobe / strip edge | −29.1 | 2372.68 | 2371.94 | +0.74 |
| v644 | lobe corner (runway + primary_parallel + strip) | −23.4 | 2372.20 | 2372.12 | +0.08 |
| v987 (A) | junction + primary_parallel | 0 | 2370.75 | 2372.28 | −1.53 |
| v1223 | apron#58 edge + junction | +25.3 | 2369.80 | 2371.78 | −1.97 |

A → v644: 1.45 m over 29.4 m = 4.9 %. Apron edge → v644: 2.40 m over 51.4 m = 4.7 %.
The ground itself is level across this section (2371.8–2372.3 m).

Along the taxiway line through A, going north (downhill): follows the ground at ~2.2 % to
180 m south of A, then drops at 3.4–5.6 % between 140 m and 86 m south of A (ending
1.8–2.2 m below the ground), then runs nearly flat (0.3–1.0 %) through A to 40 m north.

## Census (harness, sw11_KASE)

The pair IS reported: `taxi_box primary_parallel|runway` 1.45 m, 4.93 % against a 2.50 % box cap,
and `airside_no_step` on the same pair against 2.63 %; `airside_no_step junction|runway`
2.40 m, 4.67 % against 2.26 %. 170 rows within 60 m of A (within_shape 52, taxi_box 50,
airside_no_step 46, transverse 13, strip_transverse 8, strip_arc 1). No instrument hole.

## Mechanism (by intervention)

Hard rows relaxed at the site: none (stage 1: 0 relaxed; the only `hard_conflict` is a
groundside road cross-section 150 m away). The taxi caps are PRICED here (hard only on the
fronting set); the apron's 1.5 % cap is hard and its 1 % preference is priced at the same
weight as the taxi caps.

The apron/junction sheet beside the runway is ~1.5 km long. The runway is built at 2.023 %
(§50 yield, thresholds are truth) and the taxi family yields with it (30ah); the apron does
not. Mean built − DEM by station north of A (base → arm I3):

| station m | runway | taxi | apron/junction |
|---|---|---|---|
| −150..0 | +0.40 → +0.44 | −0.96 → +0.45 | −2.04 → +0.28 |
| 0..150 | +0.73 → +0.82 | −0.23 → +0.67 | −0.68 → +1.29 |
| 450..600 | +0.54 → +0.52 | +0.50 → +0.44 | +0.22 → +0.31 |
| 900..1050 | +1.22 → +1.22 | +1.07 → +0.33 | +2.69 → +0.98 |
| 1200..1350 | +2.02 → +1.57 | +3.84 → +0.65 | +5.20 → +1.22 |

Arms (scratch edit of `common.roles.apron` in rulesets.toml, reverted; replay of one capture):

| arm | apron preferred / max | A | A → v644 | verify rows | taxi_box | within_shape |
|---|---|---|---|---|---|---|
| base | 1.0 % / 1.5 % | 2370.75 | 1.45 m (4.9 %) | 4529 | 660 | 2376 |
| I1 | 1.0 % / 2.023 % | 2370.96 | 1.26 m (4.3 %) | 4482 | 645 | 2237 |
| I2 | 1.5 % / 1.5 % | 2370.95 | 1.27 m (4.3 %) | 3869 | 514 | 2128 |
| I4 | 1.5 % / 2.023 % | 2372.04 | 0.64 m (2.2 %) | 2751 | 302 | 1417 |
| I3 | 2.023 % / 2.023 % | 2372.59 | 0.23 m (0.8 %) | 1650 | 103 | 893 |

I3 also settles the hard set (base: 5 rows over, two runway transverse rows "in a law
conflict, kept hard" — at 39.22898, -106.87115 and 39.21848, -106.86629, the two ends of
the sheet). I3 moves runway-face vertices at the north end by up to 2.85 m DOWN
(v331 39.22901, -106.87078: 2350.34 → 2347.50, DEM 2346.42).

History: present in the first KASE frame (kase130b, 2026-09-30: A 2369.08, corner 2370.55);
today's values since sw1003 (2026-10-01).

## Question for the owner

Does an apron tied to a runway whose cap yielded to its thresholds (§50) yield with it, as
the taxi family does (30ah)? Recommendation: yes.

Frames: capture `kase523/KASE.pkl`; I3 arm patch `kase523/kase523_i3_apron_yields_KASE.osm`.
