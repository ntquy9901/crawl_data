# Project Context — crawl_data

## What
Vietnam stock-market data crawler. Two layers:
1. **Opinion crawlers** (existing): Vietstock analysis PDFs, Cafef/SSI/HSC/VNDIRECT/tuoitre/thanhnien/vietnamplus/vnexpress/vneconomy/baodautu/tinnhanhchungkhoan/forum/telegram news → `data/*_articles.csv`. Browser+HTTP, resumable.
2. **Objective VN30 layer** (2026-07-12): primary-source disclosures + news for VN30 volatility model → `data/objective/objective_v<date>.csv`.

## Stack
Python 3.13 (`uv`), Playwright (stealth), requests, lxml, PyMuPDF, pandas. Windows. pytest + ruff + diff-cover (DoD in CLAUDE.md).

## Key modules
- `base_news_crawler.py` — Template Method news crawler framework. Reused by ssi/hsc/vndirect + helpers-only for sitemap/wayback crawlers.
- `news_sitemap_crawler.py` — sitemap-shard metadata crawler: tuoitre/thanhnien/vietnamplus/vneconomy/baodautu/tinnhanhchungkhoan. `--source <name> [--latest | --from-date/--end-date]`. Sources without embedded title (vneconomy/baodautu/tinnhanhchungkhoan) use `slug_to_title()` fallback.
- `vnexpress_wayback_backfill.py` — Wayback Machine backfill for vnexpress.net (blocks bot at sitemap level). 
- `vndirect_crawler.py` — research notes, bilingual `--lang en|vi`.
- `telegram_crawler.py` — Telegram public channel crawler (t.me/s/), 4 VN stock channels. Plain HTTP + regex.
- `objective/` — VN30 objective layer: schema, vn30 (30 tickers), base crawler, adapters (vsdc, vietstock disclosure, tier2_rss × 5 outlets), build_objective (merge+dedup+version), dashboard.
- `run_daily_all.ps1` — daily schedule (opinion + objective crawlers + merge + dashboard).
- Clean code enforced: named constants, single responsibility, guard clauses, no dead code, YAGNI.

## Current dataset (2026-07-22)
- **News merged** (`data/news_articles.csv`, via `merge_news.py`): **2,182,452 rows** unique (by url) from 16 sources:
  - cafef 4.1k, ssi 1.9k, hsc 6, vndirect 2k, tuoitre 283.6k, thanhnien 387.2k, vietnamplus 773.2k, vnexpress 13.9k
  - vneconomy 224.9k, baodautu 158.4k, tinnhanhchungkhoan 329.8k **<-- new 2026-07-22**
  - forum 1.1k, telegram 4 channels 2.4k **<-- new 2026-07-22**
- Vietstock (analysis reports, separate schema): 14.8k.
- Objective: 434 VN30 records (29/30 tickers, 2005→2026).
- Epics created: social media expansion (Facebook Pages API, Zalo OA, TikTok) — `docs/social-media-expansion-epic.md`.

## How to run
```bash
uv run pytest tests/                                    # 190+ tests
python telegram_crawler.py --all --backfill             # Telegram channels
python news_sitemap_crawler.py --source vneconomy --latest
python vnexpress_wayback_backfill.py --target kinh-doanh --workers 3
# ... (same as before)
```

## BMAD
Planning artifacts: `_bmad-output/planning-artifacts/` (PRD, ARCHITECTURE-SPINE, epics, sprint-status).
