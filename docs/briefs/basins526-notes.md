# basins526 — pit/basin objects: the gap (G), #526 (B1), #527 (B2), #528 (B3)

Lane branch `claude/basins526`, base main `f5f11c81f`. Reference: `/tmp/harness/othh513_OTHH.*`
(body eb7565539e36, plan sha 8e24e55b3f68), `docs/briefs/othh513-notes.md`.

## Step 0 — instruments

* `tools/obj8_split_report.py --units-with SUBSTR` (NEW parameter; `airport/placement_read.plan_units_with`):
  the plan trimmed to the units holding a matching resource BEFORE the plan stage — the two
  pit units of OTHH read in 2.3 s instead of the pack's ~600 s. Every plan-wide count is then
  partial and the tool says so.
* Base partial read (`Dewatering Drainage`, main code): `Drainage_06_000` b0 `skirted` on the
  trench floor (z −0.74, y0 −2.51), b1 basin:7; `Drainage_06_001` b0 basin:0, b1/b2 basin:7
  (3 bodies in the PARTIAL plan; the as-built 1.0.385 plan has a 4th, b3 basin:9 — the full-plan
  base is being read to settle whether the partial plan or the tree differs);
  `Dewatering_02_LOD0_002` b1..b10 `plate_only` / `footless_own_ground` at z −9.68.
