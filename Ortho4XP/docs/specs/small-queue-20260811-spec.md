# Small queue — KSTJ inverted band · classification adjudication · transient-504

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **smallq**. Pre-ship mode
(docs/RULINGS.md); deviations STOP-and-report to the Fable lead.
Owner-ruled (closing interview 2026-08-11): all three items, one
implementer. The three items are independent — a STOP on one never
blocks the others.

## SQ1 KSTJ inverted band — ATTRIBUTION ONLY, no fix without a ruling

Evidence carried: KSTJ (tile +39-095) fails
`assert_no_final_band_inversion` with a 31-node inverted band on EVERY
+39-095 build; its patch is dropped. Context: KSTJ is one of the r11
"effectively-empty insets that now fall back loudly but were not
adjudicated"; r9 fixed the crown-frame clamp class (every airport
built again) — KSTJ still drops, so this is NOT (or not only) that
class.

Work: build KSTJ through the harness
(`venv/bin/python tools/harness/build_airport.py KSTJ --tile 39 -95`,
foreground; `--allow-degraded-dem` only if the entry refuses on DEM
state, and say so). Capture the inversion record (the
`_final_band_inversions` stash groundside.py ~:1204 publishes, and the
refusal's own output). Attribute the 31 nodes: (a) which band/nodes,
where (lat/lon, roles); (b) is the inversion manufactured by the
fallback-DEM frame (the r11 loud-fallback path), a band/clamp frame
defect (r8/r9 family), or a genuine law inconsistency at the site?
Interventional standard (mechanism-before-fix): at least one
counterfactual arm — e.g. `O4_BAND_SEED_EXACT=0` control, or a
degraded-vs-real DEM comparison if the tile's real insets cover KSTJ —
not an attribution read alone. Feasibility is guaranteed (standing
law): a lawful surface EXISTS for the real airport; the inversion is a
defect to attribute, never an answer. STOP after attribution: report
the mechanism with the evidence; the fix is a Fable spec next round.
No auto_patch code changes in this lane (a concurrent lane owns
auto_patch this session).

## SQ2 Classification adjudication — measured verdicts, routed to the owner

Two findings await the classify instrument (INDEX'd
`Ortho4XP/tools/classify_report.py` — it reads production's own
shadow-pass decisions; it classifies nothing itself):

* KCLT `apron -10602` in the triangle — the r14
  `tunnel_airside_conflict` finding said "likely scorer-misclassified".
* KMCI shapeID 995 — parking-lot-as-apron (r11 owner item).

Work: run the tool per its INDEX contract for KCLT and KMCI (build or
`--from-json` a prior dump if one exists in the lane; builds
foreground through the tool's own path). For each finding: the shadow-
pass decision, legacy-vs-scorer disagreement, the shape's OSM tags and
geometry facts, centroid lat/lon to fly to, and a RECOMMENDED verdict
with the evidence — but the VERDICT IS THE OWNER'S (intent questions
route to the owner; standing law). Output: one short adjudication
artifact per airport (markdown, in the lane scratch dir, paths quoted
in your report) the lead will hand the owner. No code changes.

## SQ3 Transient-504 fetch fix — implement

Mechanism (lead-verified, `src/O4_Airport_Elevation_Insets.py`): the
module owns `TransientFetchError` (~:232) and
`error_message_indicates_transient_network_failure` (~:276), and every
`fetch_inset` caller honours the convention — a RAISED failure is
never recorded as a durable no-coverage negative, while a returned
`None` is. But the `discover()` implementations (~:995 TNM shown:
`requests.get` exception → None; `status_code != 200` → None —
including 503/504/429; non-JSON body → None; also audit the other
`discover()` sites ~:1335, ~:1644 and `discover_inset` ~:670) swallow
OUTAGES into that durable None.

The law: a discovery failure that says nothing about coverage RAISES
`TransientFetchError`; only a genuine no-data answer (a successful
response with no usable items) stays None. Concretely, for HTTP-level
discovery: transport exceptions (timeouts, connection failures) raise;
status 5xx and 429 raise; a non-JSON body on an otherwise-2xx response
is ambiguous — treat as transient (an error page is an outage
artifact, not a catalog answer); 4xx other than 429 stays durable
None (say so in a WARN either way, keeping the existing message
idiom). GDAL-mediated discovery paths route through the existing
fragment matcher. Verify by reading each `discover()` caller that the
raise propagates to the layer that already honours the convention —
never add a second recording convention.

Tests: the module's existing test idiom, headless (fake
responses/exceptions; no network): each transient shape raises, empty
catalog stays None, 404 stays None, and the caller-level test that a
raise records NO durable negative. Run the directly-covering files
once, ledgered.

## Acceptance

SQ1: the attribution report (mechanism named, counterfactual arm
quoted). SQ2: the two adjudication artifacts. SQ3: tests green once,
ledgered; quote the per-site behaviour table (site → old → new).
Build-time impact: none expected anywhere (SQ3 is failure-path only);
flag any tripwire anomaly.

## Bookkeeping

Convergence guards: attempt cap 2, second miss = STOP-and-report;
`.progress` heartbeat in the lane scratch dir. Skipped verifications =
DEFERRED_VERIFICATION.md candidate lines (lead writes final). The
shared-repo guard is law — a refused build is a condition to fix, not
to work around; downloads/cache regenerations are NOT authorised in
this lane (a discovery retry at build time is a read, not a refresh —
but if any path wants to WRITE the shared corpus, stop).
