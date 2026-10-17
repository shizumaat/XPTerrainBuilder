# Imagery fetch — spec (2026-10-17, Beta 3 W0 + W5)

Status: PROPOSAL. Plan: `beta3-build-speed-plan-20261017.md` W0 (§3 here) and
W5 (§4–5). Issues: manifest B3-02, B3-03, B3-13, B3-14. Related: #622 (progress
share, measured rate, prefetch — unchanged by this spec). Prior art: E
`docs/specs/net-download.md` R1–R7, `docs/benchmarks/network.md`, ADR 0005.

Download time is EXCLUDED from both build-time budgets; this spec's measure is
request rate and failure count on a cold imagery cache, reported as a range.

## 1. Problem (verified 2026-10-17)

`src/O4_Imagery_Utils.py`:

- `http_request_to_image` (`:1172-1272`): `requests` session `.get` with
  `http_timeout = 10` (`:60`); a `429` is not matched — it falls to
  "Unmanaged Server answer", `break`s and the piece returns `(0, status)`
  (`:1247-1250, :1272`); `5xx` likewise breaks unless `check_tms_response`
  (default False, `:61`); connection failures sleep a fixed 2 s and retry up to
  `max_connect_retries = 10` (`:62`). No `Retry-After`, no backoff, no
  per-host state. No `HTTPAdapter`/`Retry` is mounted.
- Concurrency: `max_threads` per provider, default 16 (`:1571-1574`,
  `:1710-1713`), one `requests.Session()` per orthophoto (`:1553`, `:1674`);
  `effective_download_slots` Auto = 2 orthophotos (`O4_Parallel_Utils.py:
  255-271`), so ~32 requests in flight per tile. The imagery class cap in
  `o4_engine/parallel.py` bounds tiles.
- Bing: `Providers/Global/BI.lay:2` is `http://r{switch:0,1,2,3}.ortho.tiles.
  virtualearth.net/tiles/a{quadkey}.jpeg?g=136` — cleartext HTTP/1.1. 22
  provider files use `http://`, 54 `https://`.
- Placeholder ("no imagery") detection is by `Content-Length` 1033 on
  `virtualearth` and 2521 on `arcgisonline` (`:1200-1206`).
- Warm path: an orthophoto already in the cache is reused (`build_jpeg_ortho`,
  `:1860`); the fetcher matters only on a cold cache.

E measured (its network, 2026-09-12, `network.md` §1–2): our host pattern
222 req/s at 32 in flight; the https `ecn.t{0-3}` host 287 req/s at the same
concurrency with byte-identical bodies; HTTP/2 at 128 in flight 1,436 req/s
with zero 429 over 270,000 requests; the placeholder carries
`X-VE-Tile-Info: no-tile`. Those are E's figures on E's line; ours are to be
measured.

## 2. Design principles

- Preserve: per-provider `max_threads` as a CAP (never exceeded), the
  `request_headers` path (authenticated providers), the placeholder tests,
  `UI.red_flag` cancellation, `download_meter.record` (#622), `incomplete_imgs`
  bookkeeping and the white-square fallback.
- Land in three steps of rising size, each behind its own measurement; the
  threaded `requests` fetcher stays the default until the async one is
  measured on three platforms.

## 3. W0 — the two one-file changes

### 3.1 429 / Retry-After and bounded backoff (B3-02)

In `http_request_to_image`:

- `429` and `503` with `Retry-After` (seconds or HTTP-date, `email.utils.
  parsedate_to_datetime`) → sleep `min(max(retry_after, 1), 60)` and retry,
  counted against a per-call PUSHBACK budget (default 6 pauses / 120 s total),
  not against `max_connect_retries`;
- `429`/`503` without the header, and `5xx` → exponential backoff
  `0.5 · 2^k` s with ±25 % jitter, capped at 8 s, `k ≤ 5`, then fail as today;
- `4xx` other than 429 stay answers (404 → no tile, 403 → stop as today);
- the fixed `time.sleep(2)` on connection failure becomes the same backoff.

A module-level per-host pause (`_HOST_PAUSED_UNTIL[netloc]`) so the other
15 threads of the orthophoto do not each hit the paused host; checked before
`.get`. No new dependency. Output bytes unchanged.

### 3.2 The https Bing host (B3-03)

`Providers/Global/BI.lay:2` → `https://ecn.t{switch:0,1,2,3}.tiles.virtualearth.
net/tiles/a{quadkey}.jpeg?g=15312` (E's measured choice; `t.ssl.ak.tiles.
virtualearth.net` is the single-host fallback). The `g=` value is mandatory
and free; E found identical bytes for `g=1/136/15312` and that a new value is
edge-cold. Our acceptance re-measures: ≥ 300 quadkeys fetched from both hosts,
sha256 identical body by body, placeholder count identical. The placeholder
test gains the header check (`X-VE-Tile-Info: no-tile`) BESIDE the 1033-byte
test, never instead of it. Owner Q9.

### 3.3 Measurement for W0

One cold-cache tile (imagery cache emptied for that tile only, lane-local),
three runs at three times of day, before and after: `download_meter` rate,
failed pieces, white-squared textures. Reported as ranges.

## 4. Adaptive concurrency and hedging inside the threaded fetcher (B3-13)

Keep `parallel_execute` and the thread pool; make the number of ACTIVE
requests per host group adaptive (E R2, AIMD):

- a `HostWindow` per provider code: `in_flight` starts at
  `min(max_threads, 8)`, +1 per round of successes up to `max_threads`
  (the cap), halved on 429/503/refused connection or a latency spike (p50 ×
  4), ×0.75 on a timeout, paused on `Retry-After`; a semaphore the worker
  acquires before `.get`;
- hedging (E R3): a request with no answer after `hedge_after_s = max(3, 5 ×
  p50)` is doubled on the same session; the first good answer wins, the loser
  is dropped (`requests` cannot cancel; the loser's thread finishes and its
  body is discarded — bounded by at most one hedge per request);
- stats delivered to `download_meter` as today; the window size joins the
  `ImageryDownloadsDone`-class reporting only if #622 asks for it.

Byte output unchanged. Twins with a stub session (`tests/test_imagery_step_
failures.py` already stubs the step): window grows on success, halves on 429,
obeys `Retry-After`, never exceeds `max_threads`; a hedged pair returns one
image.

## 5. Async HTTP/2 fetcher behind a flag (B3-14; owner Q4)

`src/O4_Imagery_Fetch.py` (new): one `AsyncSession` (`curl_cffi`, HTTP/2) per
orthophoto build, the §4 window and hedging in asyncio, `req_per_s` ceiling
per host group optional. `build_texture_from_tilbox` chooses the fetcher by
`O4_IMAGERY_FETCHER=async|threads` (default `threads` until measured). The
per-piece contract is unchanged: `(success, PIL.Image)` per part, pasted into
`big_image`; `request_headers` and the provider's session cookies are
forwarded; the placeholder tests run on the body and headers identically.

Admission conditions: `curl_cffi` wheels for mac arm64/x86_64, win, linux in
the freeze (`requirements.txt`, both `.spec` hiddenimports if lazily imported —
`src/auto_patch/CLAUDE.md` Gotchas); licence (MIT) recorded in `LICENSING.md`
§3; measured rate on three platforms over the threaded §4 fetcher.
Fallback: `httpx[http2]` if `curl_cffi` fails to freeze.

## 6. Interfaces and files (`tools/blast.py` 2026-10-17)

| File | Hazards |
|---|---|
| `src/O4_Imagery_Utils.py` | imported by 25 files (9 src incl. `O4_Qt_GUI`, `O4_Qt_Map`, `session.py`, `jsonl.py`); tests: `test_imagery_step_failures`, `test_imagery_incomplete_warning`, `test_imagery_share`, `test_provider_registry`, `test_dds_file` |
| `Providers/Global/BI.lay` | provider file parsed by `O4_Imagery_Utils` (`test_provider_registry`) |
| `src/O4_Parallel_Utils.py` | `parallel_execute` shared by masks and bathymetry — do not change its contract |
| `src/o4_engine/download_meter.py` | #622's meter; additive only |
| `src/o4_engine/events.py` | NOT touched; blast reports `ImageryDownloadsDone` as python-only drift already (fix before ship, separate) |

Env flags added: `O4_IMAGERY_FETCHER` (B3-14). Each new flag gets a test (the
blast index flags default-ON env reads with no test).

## 7. Acceptance and rollback

- B3-02: twins; one cold tile shows no higher failed-piece count.
- B3-03: body identity over the sample; rate range reported.
- B3-13/14: rate range on three cold runs; failed pieces not higher; textures
  sha256-identical to the threaded arm (same JPEGs → same DDS); the window
  never exceeds `max_threads`.
- Rollback: the `.lay` line is one revert; `O4_IMAGERY_FETCHER=threads`; `git
  revert`.

## 8. Out of scope

The prefetch step (#622 item 3); Overpass/OSM fetching (`O4_OSM_Utils`, its
own mirrors law); DEM/inset downloads (#158); provider registry changes beyond
the Bing host; any change to texture bytes.

## Licence

Design follows E's `net-download.md` rules R1–R7 as prior art; re-implemented.
`Ortho4XP/` (GPL-3).
