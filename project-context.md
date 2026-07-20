# Project Context — crawl_data

## What
Vietnam stock-market data crawler. Two layers:
1. **Opinion crawlers** (existing): Vietstock analysis PDFs, Cafef/SSI/HSC/VNDIRECT/tuoitre/thanhnien/vietnamplus/vnexpress news → `data/*_articles.csv`. Browser+HTTP, resumable.
2. **Objective VN30 layer** (2026-07-12): primary-source disclosures + news for VN30 volatility model → `data/objective/objective_v<date>.csv`.

## Stack
Python 3.13 (`uv`), Playwright (stealth), requests, lxml, PyMuPDF, pandas. Windows. pytest + ruff + diff-cover (DoD in CLAUDE.md).

## Key modules
- `base_news_crawler.py` — Template Method news crawler framework (opinion layer). Reused not just for paginated-listing crawlers (ssi/hsc/vndirect) but also as a base for non-paginated topologies (subclass for `fetch`/CSV helpers only, override the flow method) — see `news_sitemap_crawler.py` and `vnexpress_wayback_backfill.py`.
- `news_sitemap_crawler.py` — sitemap-shard metadata crawler for tuoitre/thanhnien/vietnamplus (title embedded in sitemap → no per-article fetch). `--source <name> [--latest | --from-date/--end-date]`.
- `vnexpress_wayback_backfill.py` — vnexpress.net blocks bots at the sitemap-shard level (302 redirect, even Googlebot UA + Playwright headless); harvests historical article links via the Wayback Machine (archive.org CDX API + archived snapshot HTML) instead. `pub_date` is the snapshot capture date (approximate), not the real publish date. archive.org self-throttles at high concurrency — use `--workers 3-6`.
- `vndirect_crawler.py` — research notes, now bilingual: `--lang en|vi` (Vietnamese pages are separate articles at different slugs, not a UI translation; `category` gets a `-vi` suffix).
- `objective/` — VN30 objective layer: schema (ObjectiveRecord 16 fields), vn30 (30 tickers), base_objective_crawler (UTC, checksum dedup, raw layer), classify (event_type), adapters (vsdc, vietstock disclosure, tier2_rss × 5 outlets), build_objective (merge+dedup+version), dashboard (Chart.js HTML).
- `run_daily_all.ps1` — daily schedule (opinion + objective crawlers + build + dashboard); includes tuoitre/thanhnien/vietnamplus `--latest`.

## Current dataset (2026-07-18)
- Opinion news (`data/news_articles.csv`, via `merge_news.py`): **1,465,810 rows** — cafef 4.1k, ssi 1.9k, hsc 6, vndirect 2k (incl. Vietnamese), tuoitre 283.6k, thanhnien 387.2k, vietnamplus 773.2k, vnexpress 13.9k (Wayback-harvested, approximate dates).
- Vietstock (analysis reports, separate schema): 14.8k.
- Objective: **434 VN30 records** (Vietstock 420 + VSDC 4), 29/30 tickers, 2005→2026. + Tier-2 news companion.
- Known gaps: nld.com.vn is not an independent source (redirects entirely to tuoitre.vn/nld/*); cafef deep-backfill infeasible (IP throttle + unsectioned sitemap); vnexpress pre-~2010 not recoverable (old URL scheme).

## How to run
```bash
uv run pytest tests/                                    # 190+ tests
python news_sitemap_crawler.py --source tuoitre --latest        # daily (7-day window)
python vnexpress_wayback_backfill.py --target kinh-doanh --workers 3  # Wayback backfill
python vndirect_crawler.py --latest --category company-note --lang vi
python -m objective.adapters.vietstock_disclosure --latest --max-pages 999  # VN30 deep backfill
python -m objective.adapters.vsdc_crawler --latest      # VSDC corporate actions
python -m objective.build_objective                     # unified dataset
python -m objective.dashboard                           # HTML dashboard
```

## BMAD
Planning artifacts: `_bmad-output/planning-artifacts/` (PRD, ARCHITECTURE-SPINE, epics, sprint-status). bmad-loop validate passes but RUN blocked (MSYS2 tmux socket on Windows).
