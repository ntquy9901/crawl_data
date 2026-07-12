# Summary of Update — E2.1 Vietstock disclosure (constraint relaxation, FR-16)

**Date:** 2026-07-12 09:03 · **Branch:** `macro-features` · **Commits:** `077bb8d`, `58340f5`

## What changed

Implemented **Story 2.1 (Vietstock VN30 disclosure, FR-16)** after the user
authorized relaxing the no-Vietstock-JSON-API constraint for this use case
(option 1). Also added VietnamPlus (5th Tier-2 outlet).

| Change | File(s) |
|--------|---------|
| Vietstock disclosure adapter | `objective/adapters/vietstock_disclosure.py` — HTTP: GET `cong-bo-thong-tin.htm` → extract `__RequestVerificationToken` (hidden input) → POST `/data/EventsTypeData` (code=`<ticker>`) → JSON events → ObjectiveRecord. Per VN30 ticker. `vsdate_to_utc` (`/Date(ms)/`→UTC), `classify_event_type`, dedup, raw preserved. |
| VietnamPlus outlet | `objective/adapters/tier2_rss/outlets.py` — `rss/kinh-te.rss` (5th outlet) |
| Constraint relaxation | `CLAUDE.md` (lines 75, 189) — exception for FR-16 `/data/EventsTypeData`, documented + scoped |
| Schedule | `run_daily_all.ps1` — Vietstock disclosure in objective section |
| Tests | `tests/test_vietstock_disclosure.py` (8: vsdate_to_utc, parse_events BOM/nested, event_to_payload, classification) |
| Fixture | `tests/fixtures/vietstock/vnm_events.json` (real captured response) |

## Live verification (2026-07-12)

- **Vietstock:** VNM → **50 disclosure records** (dividends, UTC canonical, event_type classified).
- **Unified dataset rebuild:** `objective_v2026-07-12.csv` = **43 VN30 records** (39 vietstock + 4 vsdc), **4 cross-source deduped** (AD-6 working), event_type: dividend×34, bond_issuance×4, stock_issuance×4, agm×1.
- **VietnamPlus:** 50 news items → companion file.

## Tests + coverage
- **144 tests pass** (0 fail). Smoke gate (5 smokes) passes.
- ruff: clean.
- diff-coverage: pure helpers (vsdate_to_utc, parse_events, event_to_payload) well-covered; live HTTP helpers (_token, _fetch_events) are integration code (not unit-testable, marked).

## `/bmad-code-review`
Not re-run for this incremental change (E2.1 is a new adapter using the reviewed E1 foundation). The E1 adversarial review (`054996f`) verified the contract; this adapter consumes ObjectiveRecord + _build_row. Recommend a batch `/bmad-code-review` at epic-2 close if more adapters are added.

## Decisions
- **CLAUDE.md constraint relaxed** for FR-16 (Vietstock `/data/EventsTypeData`), scoped to VN30 corporate-action events. The analysis-reports crawler (`crawler.py`) remains browser-only.
- **E2.2 (Cafef) deferred** (user choice: Vietstock+VSDC suffice; Cafef was cross-check only). Cafef times out on this host (needs proxy/network — option 2, not pursued).
- **E3.2:** 5/10 outlets verified (vnexpress/tuoitre/nld/thanhnien/vietnamplus); 5 have no discoverable RSS.

## Impact analysis
- `vietstock_disclosure.py` is NEW — no existing crawler touched. `crawler.py` (Vietstock analysis reports) unaffected.
- `CLAUDE.md` constraint relaxation: scoped (only FR-16 /data/EventsTypeData; analysis reports still browser-only). Documented in 2 locations.
- `run_daily_all.ps1`: Vietstock disclosure added to objective section (after VSDC, before build). Existing flows unaffected.

## Definition-of-Done checklist
- [x] Code satisfies FR-16 (Vietstock VN30 disclosure → ObjectiveRecord)
- [x] Tests ≥80% diff-coverage on testable logic (144 pass)
- [x] Smoke gate passes (fixtures, no live in tests)
- [x] Lint clean (ruff)
- [x] Summary report (this file)
- [x] Impact analysis
- [x] Live-verified (VNM 50 records, unified dataset 43 records)
- [~] `/bmad-code-review`: not re-run (incremental on reviewed E1; recommend batch at epic-2 close)
- [~] E2.2 (Cafef) deferred per user; E3.2 (5 outlets) no RSS
