# Project Context — crawl_data

## What
Vietnam stock-market data crawler. Two layers:
1. **Opinion crawlers** (existing): Vietstock analysis PDFs, Cafef/SSI/HSC/VNDIRECT news → `data/*_articles.csv`. Browser+HTTP, resumable.
2. **Objective VN30 layer** (new 2026-07-12): primary-source disclosures + news for VN30 volatility model → `data/objective/objective_v<date>.csv`.

## Stack
Python 3.13 (`uv`), Playwright (stealth), requests, lxml, PyMuPDF, pandas. Windows. pytest + ruff + diff-cover (DoD in CLAUDE.md).

## Key modules
- `base_news_crawler.py` — Template Method news crawler framework (opinion layer).
- `objective/` — VN30 objective layer: schema (ObjectiveRecord 16 fields), vn30 (30 tickers), base_objective_crawler (UTC, checksum dedup, raw layer), classify (event_type), adapters (vsdc, vietstock disclosure, tier2_rss × 5 outlets), build_objective (merge+dedup+version), dashboard (Chart.js HTML).
- `run_daily_all.ps1` — daily schedule (opinion + objective crawlers + build + dashboard).

## Current dataset (2026-07-12)
- Opinion: vnstock 14.8k + cafef/ssi/hsc/vndirect ~6k (existing).
- Objective: **434 VN30 records** (Vietstock 420 + VSDC 4), 29/30 tickers, 2005→2026. + 264 Tier-2 news companion.

## How to run
```bash
uv run pytest tests/                                    # 151 tests
python -m objective.adapters.vietstock_disclosure --latest --max-pages 999  # VN30 deep backfill
python -m objective.adapters.vsdc_crawler --latest      # VSDC corporate actions
python -m objective.adapters.tier2_rss.vnexpress --latest  # Tier-2 news
python -m objective.build_objective                     # unified dataset
python -m objective.dashboard                           # HTML dashboard
```

## BMAD
Planning artifacts: `_bmad-output/planning-artifacts/` (PRD, ARCHITECTURE-SPINE, epics, sprint-status). bmad-loop validate passes but RUN blocked (MSYS2 tmux socket on Windows).
