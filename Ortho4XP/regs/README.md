# regs/ — the primary sources our grade law derives from

Owner decision 2026-08-08: regulatory source documents live IN the
repo so the provenance of every ruleset value is auditable, and so
future edition updates are deliberate, versioned events. The derived
values themselves live in `../docs/specs/fabric-model-reg-set.md`
(per-ruleset, per-surface, with section citations and verification
dates); the ruleset code carries them per the region-rulesets ruling.

## Inventory

| File | Edition | Source | Status |
|---|---|---|---|
| `AC-150-5300-13B-Airport-Design-Chg1-w-errata.pdf` | 13B + Chg 1 w/ errata (signed 2024-08-16) | faa.gov (owner-downloaded 2026-08-08; automated fetch is 403-blocked) | US-government work, public domain |
| `errata-AC-150-5300-13B-Airport-Design-Chg1-2025-04-03.pdf` | errata sheet 2025-04-03 | faa.gov, same | public domain |
| `CS-ADR-DSN-Issue7-2025-extracted.txt` | Issue 7, 2025-05-16 (ED Decision 2025/004/R) | easa.europa.eu (text extraction, primary-verified 2026-08-08) | EU document, reused with source acknowledgment |

## ICAO Annex 14 — deliberately NOT committed

Annex 14 Vol I (8th ed., 2018) is ICAO-copyrighted and sold; this
repo is public, so redistributing its text is not ours to do. The
working extraction lives gitignored at `../tmp/regset/annex14.txt`
(regenerate from a licensed copy when needed). Our DERIVED values —
facts, with citations — are in the reg-set table, primary-verified
2026-08-08.

## Updating an edition

Replace the file, then re-run the verification pass against
`../docs/specs/fabric-model-reg-set.md` (every affected row gets a
fresh PRIMARY-VERIFIED date) and sweep the ruleset constants the
table maps. An edition bump without the verification pass is a
defect, not an update.
