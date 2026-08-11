# Round 11 — a flat site never flattens another airport; an empty inset is no inset

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r11kmci**. Pre-ship mode
(docs/RULINGS.md); deviations STOP-and-report. Runs in parallel with
lane/r10tunnel (bridges.py) — this lane must NOT touch bridges.py.

## Measured attribution (2026-08-11 KMCI recon, ledgered harness build
## KMCI_20260811T1201, tree befb3ba)

The owner's 70 m airside/groundside cliff at KMCI is a DEM defect, not a
classification defect:

* **KFLV** (flat_candidate, Z0 234.24 m, ~19 km away) claimed 3,529
  object placements around KMCI (the KMCI Taimodels pack's DSF) and
  emitted 12 synthetic CONSTANT 234.24 m cluster insets, the largest
  12.73 km², over KMCI's real ~300 m terrain. The engine's own feather
  check WARNED — "differs from the base DEM by a median −64.5 m
  (>10 m; check vertical datum)" — and substituted anyway. In-build,
  KMCI's flat-site detector then read relief 0.00 m / DEM−Z0 72.19 m
  where the same detector reads relief 15.56 m off disk: the plateau is
  manufactured during DEM prep. Every DEM-sampling authority (aprons,
  groundside, object-bridge trenches, basin rims — all measured at
  exactly 234.24) inherited it; CIFP-pinned runways/junctions kept
  ~299–313 m. Max adjacent-node step measured: 59.36 m over 1.00 m.
* Claim machinery: `flat_site_mode.claimed_placements_by_icao` builds
  entries for every tile icao but its per-airport loop swallows failures
  (`except Exception: continue`, ~line 344) — a silently dropped owner
  removes it from `post_mesh.worklist_claim_assigner`'s candidate set,
  and the assigner's nearest-airport FALLBACK ("nothing is ever dropped
  for want of an owner", post_mesh.py ~206) then awards the points to a
  distant airport. That fallback is correct for object ANCHORING; it is
  not a licence to rewrite terrain.
* **Independent second defect:** `KMCI_usgs3dep.tif` (the corpus 1 m
  lidar inset) is 100.00 % NODATA (cut from Kansas project
  KS_Statewide_2018_A18 for a Missouri airport) yet the build reports
  "inset coverage 100%" — the coverage metric is bbox-based and never
  counts valid pixels. Controls: KFLV/KMKC insets 0 % nodata.

## The laws

### R11-1 A CLUSTER INSET REQUIRES A CONTAINMENT CLAIM
### (AMENDED 2026-08-11, lead ruling on the implementer's STOP-3: the
### HZMB fallback case)

* A claimed-placement CLUSTER extends an airport's flat substitution
  when its placements were claimed by CONTAINMENT in that airport's
  claim geometry.
* Placements that reached the airport through the nearest-airport
  FALLBACK are recorded (count, per-DSF) and are NOT excluded outright:
  they join clustering IFF their cluster passes BOTH guards — the
  R11-1 distance bound (centroid within `FLAT_SITE_CLUSTER_MAX_KM` of
  the claiming airport's apt.dat extent) AND the R11-2 feather-datum
  check. This is what keeps R8-1's motivating case alive: VHHH's HZMB
  island (fallback-claimed, ~1 km, datum-consistent at Z0) clusters;
  KFLV→KMCI (fallback, ~19 km, −64.5 m) dies on both guards. The
  fallback's object-ANCHORING role stays untouched either way.
* Twin (added to the test items): a fallback-claimed cluster at 1 km
  with a clean datum SURVIVES; the same cluster at 6 km, or at 1 km
  with a 60 m datum error, refuses with the finding.
* The per-airport entry loop in `claimed_placements_by_icao`
  (flat_site_mode.py ~335-345) names every airport it drops and why
  (one vprint per dropped icao: `[flat-site] claim-entry for XXXX
  dropped (ExcType: msg) — its placements can only fall to OTHER
  airports`); the bare `except Exception: continue` keeps the continue
  but loses the silence.
* Belt-and-suspenders distance bound: a cluster whose centroid lies
  more than `FLAT_SITE_CLUSTER_MAX_KM` (config, default 5.0 km,
  `O4_FLAT_SITE_CLUSTER_MAX_KM`) from the claiming airport's apt.dat
  extent refuses with a counted finding naming both distances (HZMB,
  the motivating case, is ~1 km; KFLV→KMCI is ~19 km).

### R11-2 THE DATUM CHECK REFUSES, NEVER JUST WARNS

The existing feather-ring comparison (median |synthetic − base DEM|
over the ring, threshold 10 m, currently a WARNING in
O4_Airport_Elevation_Insets) becomes a per-cluster REFUSAL for
claimed-object cluster insets: the cluster inset is DROPPED, the line
says so with the measured median, and a counted finding records it.
The airport's own apt.dat-extent substitution is NOT subject to this
(its Z0 comes from ITS CIFP consensus — the R11 scope is the cluster
extensions only; do not change OTHH/VHHH behaviour).

### R11-3 INSET COVERAGE COUNTS VALID PIXELS

* The inset coverage metric counts non-NODATA pixels against the
  extent; an inset below `INSET_MIN_VALID_FRAC` (config, default 0.05)
  valid is NO INSET: one loud line naming the file, its valid fraction
  and its source project; `dem_inset_provenance` records
  `nodata_fraction` and the fallback; the build proceeds on the base
  DEM exactly as if the file were absent.
* This is detection + honest fallback ONLY. Re-fetching KMCI's real
  lidar is an owner `--refresh-data dem` event, out of scope here.

### R11-4 TOOL INDEX

`tools/classify_report.py` exists, renders `pavement_score_decisions`,
and is absent from `tools/INDEX.md` — the recon lawfully treated it as
absent. Add its index row (one line, consult-before-create voice).
No behaviour change to the tool itself.

## Tests (tests/test_round11_flat_claim.py, new)

1. Fallback-exclusion twin: two airports on one DSF, one entry dropped
   (raise inside its loop body via monkeypatch) ⇒ the dropped airport's
   contained placements do NOT join the other's clusters; the drop line
   and the fallback count are emitted.
2. Distance-bound twin: cluster centroid 6 km from the extent ⇒ refused
   finding; 1 km ⇒ kept (HZMB regression pin).
3. Datum-refusal twin: synthetic cluster inset with ring median 60 m off
   base ⇒ cluster dropped + finding; 2 m off ⇒ kept; the airport's own
   extent substitution unaffected in both.
4. Valid-fraction twin: an all-NODATA raster reports coverage 0 %,
   provenance nodata_fraction=1.0, base-DEM fallback, loud line; a 50 %
   raster reports 0.5 and stays an inset.
5. Existing test_flat_site_mode.py / test_airport_elevation_insets.py
   direct-covering files once (6 known pre-existing no_data-fixture
   failures on main — verify identical at base befb3ba, leave them).

## Acceptance (ledgered harness build)

* KMCI rc=0 on the CURRENT corpus (the NODATA inset still present —
  R11-3's fallback is what the build now exercises): in the emitted
  patch, ZERO apron/groundside_pavement nodes below 285 m (recon
  baseline: apron min 234.20, 253 of 1435 ways below 270 m); max
  adjacent-node step at 39.30128,-94.70727 < 2 m (baseline 59.36 m);
  the build log shows the KFLV cluster refusals (distance or datum)
  and the KMCI inset NODATA fallback line.
* KFLV's own-extent substitution still present in the log (Z0 234.24
  over its apt.dat extent) — the flat airport stays flat.
* Watch the harness shared-repo audit: the recon build wrote one mask
  raster (Masks/+30-100/+39-095/6192_3856.png, CONTAMINATED on record).
  If your build reports the same masks side effect, quote it verbatim
  in the report and do NOT authorise a refresh — owner's call.

## Bookkeeping

Lead writes the DEFERRED_VERIFICATION line at merge (no battery, no
census, no VHHH/OTHH cluster-inset arm beyond the twins). Version
stamps are the lead's at app build. OWNER items this spec does NOT do:
re-fetch KMCI lidar (`--refresh-data dem`), regularise/revert the mask
contamination (`--refresh-data masks` or corpus revert), adjudicate the
parking-lot APRON verdict (needs the R11-4 instrument on a real build).
