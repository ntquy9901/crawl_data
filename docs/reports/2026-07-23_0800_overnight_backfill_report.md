# Overnight Backfill Report — 2026-07-22/23

## Overview
Overnight operation: 3 parallel background processes ran continuously to backfill new Vietnamese financial/crypto/news sources and maintain daily crawl loops.

## Changes & New Sources

### News Sitemap Crawler — 4 new sources added
- **coin68**: Vietnamese crypto news, 10+ post-sitemaps (non-date shards), slug-based, trailing-slash URLs → requires `slug_to_title` fix (rstrip `/`)
- **thuonghieucongluan**: Thương Hiệu Công Luận, daily shards `sitemap-article-YYYY-MM-DD.xml`, 2013–2026, HAS `news:title` embedded (no individual fetch needed)
- **nhadautu**: Nhà Đầu Tư, single flat sitemap (500 URLs), slug-based, `.html` suffix
- **vietbao**: VietBao, monthly shards `sitemap-blog-YYYY-MM.xml`, 2024–2026, slug-based, `.html` suffix

### Technical fix
- `slug_to_title()` in `news_sitemap_crawler.py`: added `.rstrip("/")` to handle trailing-slash URLs (coin68)

### VietnamBiz crawler (created in previous session)
- Backfilled all 9 categories (`thoi-su`, `doanh-nghiep`, `chung-khoan`, `tai-chinh`, `hang-hoa`, `nha-dat`, `kinh-doanh`, `quoc-te`, `du-bao`)
- Categories with many dups (cross-category overlap) — expected

## Current Dataset

| Source | Rows | Type | Notes |
|--------|------|------|-------|
| vietnamnet | 1,191,566 | News | Full backfill 2003–2026 |
| thuonghieucongluan | 243,899 | News | Full backfill 2013–2026, `news:title` embedded |
| baodautu | 158,515 | News | Full backfill |
| vneconomy | 224,965 | News | Full backfill |
| tinnhanhchungkhoan | 329,876 | News | Full backfill |
| vnexpress | 13,938 | News | Wayback Machine backfill |
| tuoitre | 283,570 | News | Full backfill |
| thanhnien | 387,169 | News | Full backfill |
| vietnamplus | 773,152 | News | Full backfill |
| cafef | 39,249 | News | Daily RSS only |
| ssi | 210,523 | Research | Full backfill |
| vndirect | 53,705 | Research | Full backfill |
| hsc | 30 | Research | Daily-only |
| vnstock | 14,836 | Reports | Full backfill |
| coin68 | 23,946 | Crypto News | Full backfill (new) |
| nhipsongkinhdoanh | 17,538 | News | Backfill (21 shards HTTP 429) |
| fica | 19,260 | News | Full backfill (new) |
| cafebiz | 6,956 | News | Full backfill (new) |
| vietbao | 12,910 | News | Full backfill 2024–2026 (new) |
| vietnambiz | 1,671 | News | 9 categories backfill (new) |
| vietnamfinance | 1,000 | News | Single sitemap (new) |
| thoibaotaichinhvietnam | 400 | News | Single sitemap (new) |
| theinvestor | 149 | News | Single sitemap (new) |
| nhadautu | 500 | News | Single sitemap (new) |
| Telegram (8 channels) | ~4,300 | Social | Various |
| forum_articles | 1,104 | Social | |
| **news_articles** (merged) | **~2.48M** | | Dedup by url |

## Running Processes (background, continuous)

| PID | Script | Sources | Cycle |
|-----|--------|---------|-------|
| 6396 | overnight_process1 | coin68 + thuonghieucongluan | 30 min |
| 39028 | overnight_process2 | vietnambiz + nhadautu + vietbao | 30 min |
| 19848 | overnight_process3 | merge_news + morning_digest | 60 min |

Each process: backfill → continuous loop (daily crawl → merge → sleep → repeat).

## New Files Created

| File | Purpose |
|------|---------|
| `vietnambiz_crawler.py` | VietnamBiz RSS + listing backfill (previous session) |
| `overnight_process1_coin68_thuonghieucongluan.ps1` | Continuous crawl P1 |
| `overnight_process2_vietnambiz_nhadautu_vietbao.ps1` | Continuous crawl P2 |
| `overnight_process3_merge_digest.ps1` | Merge + digest P3 |
| `zalo_oa_crawler.py` | Zalo OA crawler (previous session) |

## Modified Files

| File | Changes |
|------|---------|
| `news_sitemap_crawler.py` | Added 4 sources, `slug_to_title` fix for trailing slashes, `coin68`/`nhadautu`/`vietbao` added to `SLUG_BASED_SOURCES` |
| `merge_news.py` | Added `vietnambiz` source entry |
| `data_classification.py` | Added `vietnambiz` → objective mapping |
| `run_daily_all.ps1` | Added `vietnambiz` daily RSS crawl |
| `scripts/backfill_vnstock_pdf.py` | Minor changes |
| `telegram_crawler.py` | Minor changes |
| `tests/test_news_sitemap_crawler.py` | Added fixture + tests for new sources |

## Remaining Issues
- **nhipsongkinhdoanh**: 21 shards failed (HTTP 429) — needs retry with longer delay/proxy
- **vietnambiz**: Low row count (1,671) due to cross-category duplication
- **nhadautu**: Only 500 articles available (sitemap limit)
- **Stockbiz**: Cloudflare-protected, no sitemap — may need Playwright
- **dantri.com.vn**: No sitemap found — would need RSS/listing-based crawler
