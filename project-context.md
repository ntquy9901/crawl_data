# Project Context — crawl_data

## What
Vietnam stock-market data crawler. Two layers:
1. **Opinion crawlers**: Vietstock analysis PDFs, Cafef/SSI/HSC/VNDIRECT + 20+ news sources (sitemap/RSS/Wayback/browser) -> `data/*_articles.csv`.
2. **Objective VN30 layer** (2026-07-12): primary-source disclosures + news for VN30 volatility model -> `data/objective/objective_v<date>.csv`.

## Stack
Python 3.13 (`uv`), Playwright (stealth), requests, lxml, PyMuPDF, pandas. Windows. pytest + ruff + diff-cover (DoD in CLAUDE.md).

## Key modules
- `base_news_crawler.py` — Template Method news crawler framework. Reused by ssi/hsc/vndirect/vietnambiz + helpers-only for sitemap/wayback crawlers.
- `news_sitemap_crawler.py` — sitemap-shard metadata crawler (20+ sources). `--source <name> [--latest | --from-date/--end-date]`. Sources without embedded title use `slug_to_title()` fallback.
- `vietnambiz_crawler.py` — VietnamBiz RSS + listing backfill, 9 categories.
- `vnexpress_wayback_backfill.py` — Wayback Machine backfill for vnexpress.net.
- `vndirect_crawler.py` — research notes, bilingual `--lang en|vi`.
- `telegram_crawler.py` — Telegram public channel crawler (t.me/s/), 8 VN stock/crypto channels.
- `objective/` — VN30 objective layer: schema, vn30, base crawler, adapters, build_objective, dashboard.
- `run_daily_all.ps1` — daily schedule (opinion + objective crawlers + merge + dashboard).
- Clean code enforced: named constants, single responsibility, guard clauses, no dead code, YAGNI.

## Current dataset (2026-07-23)
- **News merged** (`data/news_articles.csv`, via `merge_news.py`): **~2.48M rows** from 25+ sources:
  - cafef 39.2k, ssi 210.5k, hsc 30, vndirect 53.7k
  - tuoitre 283.6k, thanhnien 387.2k, vietnamplus 773.2k, vnexpress 13.9k
  - vneconomy 224.9k, baodautu 158.5k, tinnhanhchungkhoan 329.9k
  - **vietnamnet 1,191.6k** (2003-2026, MM-YYYY shards)
  - **thuonghieucongluan 243.9k** (2013-2026, daily shards)
  - **coin68 23.9k** (crypto news, fetch_all_shards)
  - **fica 19.3k** (finance, fetch_all_shards)
  - **nhipsongkinhdoanh 17.5k** (2020-2026, monthly shards, 21 shards 429)
  - **vietbao 12.9k** (2024-2026, monthly shards)
  - **cafebiz 7.0k** (2019-2026, monthly shards)
  - **vietnambiz 1.7k** (9 categories, listing-based)
  - **vietnamfinance 1.0k**, **nhadautu 500**, **thoibaotaichinhvietnam 400**, **theinvestor 149**
  - forum 1.1k, telegram 8 channels ~4.3k
- Vietstock (analysis reports, separate schema): 14.8k.
- Objective: 434 VN30 records (29/30 tickers, 2005->2026).
- Epics created: social media expansion (Facebook Pages API, Zalo OA, TikTok) — `docs/social-media-expansion-epic.md`.

## How to run
```bash
uv run pytest tests/
uv run python news_sitemap_crawler.py --source <name> --latest
uv run python news_sitemap_crawler.py --source <name> --from-date YYYY-MM-DD
uv run python vietnambiz_crawler.py --latest
uv run python vietnambiz_crawler.py --range --category <cat> --max-pages 0
uv run python telegram_crawler.py --all --backfill
uv run python vnexpress_wayback_backfill.py --target kinh-doanh --workers 3
```

## BMAD
Planning artifacts: `_bmad-output/planning-artifacts/` (PRD, ARCHITECTURE-SPINE, epics, sprint-status).
