# 0005 Content-keyed derived caches with witness-on-read and pristine inputs

## Date

2026-10-18 (records RULINGS 2026-09-11n, 2026-09-14v, 2026-09-14ab, 2026-10-17a Q1/Q2; issues #362, #382)

## Status

accepted

## Context

Derived caches make warm builds much faster. With the pack partition cache, the
warm partition + classify time at OTHH fell from 321 s to 18 s (RULINGS
2026-09-14ab). But a key that leaves out an input serves a stale result. #382
found that the partition key held nothing identifying the DEM, and named library
`.obj` files by path instead of by content. The object stage gave the same result
when rerun over a written pack only after every read went through
`pristine_dsf_path` and the dump cache was keyed by content hash (RULINGS
2026-09-11n). The partition cache is a derived cache that invalidates itself; it
is not a `--refresh-data` event. It stores recipes rather than placed geometry
(≤ 60 MB; RULINGS 2026-09-14v, 2026-09-14ab). #362 asked whether a second build
of an unchanged pack reuses its caches.

## Decision

A derived cache is keyed by the content of everything it reads (input bytes, the
identity of the code that produces it, the law digest), never by paths or
timestamps. It reads only pristine inputs, never its own earlier output. A cached
result (a hit) is served only when its witnesses, such as DEM samples and law
rows, give the same answers at read time. A hit must be byte-identical to a fresh
computation (a miss). New caches (the v2 stage cache and the DDS cache) live under
the user's data folder, with a size cap and oldest-first eviction. The build-time
law judges a cache on its miss arm (RULINGS 2026-10-17a Q1/Q2). The mechanisms are
specified in `docs/specs/v2-stage-cache-spec.md` and
`docs/specs/step-reuse-content-keys-spec.md` (plan W1/W4). This ADR adds no law.

## Consequences

- Each input in a key gets a MISS twin, the form #382 asked for.
- A derived cache is not a corpus download and needs no `--refresh-data`
  (contrast ADR 0002).
- Ambiguity, not resolved here: the spec cites "partition cache 2026-08-13", but
  `docs/RULINGS.md` has no entry headed 2026-08-13. The partition cache entries
  read for this ADR are 2026-09-14v and 2026-09-14ab. "Witness-on-read" is the
  spec's term, and no ruling read here defines it beyond the stage-cache spec.
