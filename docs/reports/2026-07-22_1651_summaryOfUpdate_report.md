# Summary Report: Add VietnamBiz Crawler

**Date:** 2026-07-22 16:51 ICT  
**Author:** AI implementation session  

## What Changed

**New source:** `vietnambiz.vn` — tin tức tài chính/kinh doanh (RSS daily + category listing backfill).

### Files Changed

| File | Change | Purpose |
|------|--------|---------|
| `vietnambiz_crawler.py` | **New** (257 lines) | `BaseNewsCrawler` subclass with RSS `--latest` + category listing backfill |
| `merge_news.py` | +1 line | Add `vietnambiz` → `vietnambiz_articles.csv` to merge pipeline |
| `data_classification.py` | +1 line | Classify `vietnambiz` as `objective` |
| `run_daily_all.ps1` | +2 lines | `vietnambiz_crawler.py --latest` daily crawl |

## Crawler Design

- **`--latest`**: Fetches `/tin-moi-nhat.rss` (RSS 2.0, 50 items, all categories). Listing-complete — no individual article fetch.
- **`--range --category X`**: Paginates through `/{category}.htm` → `/{category}/trang-N.html`. Parses title (from `title` attr or `<a>` text), category (`<a class="category">`), date (`<span class="timeago">` title attr), and lead (`<div class="sapo">`). Listing-complete.
- **Categories**: `thoi-su`, `doanh-nghiep`, `chung-khoan`, `tai-chinh`, `hang-hoa`, `nha-dat`, `kinh-doanh`, `quoc-te`, `du-bao`.

## Testing

| Mode | Command | Result |
|------|---------|--------|
| RSS daily | `--latest --test` | 30 RSS items parsed, 5 kept |
| Listing backfill | `--range --category chung-khoan --max-pages 2` | Page 1: 30 items, Page 2: 24 items, 53 total kept |
| Lint | `ruff check` on changed files | All checks passed |

## Code Review

- **Edge cases**: RSS empty, empty listing pages, dup URLs (image + title link), missing metadata (title/category/date) all handled gracefully.
- **Timezones**: `GMT+7` normalized to `+0700` before `parsedate_to_datetime`.
- **Pagination**: Page 1 lacks next-page link → `next_page` unconditionally returns 2 for `cur==1`.
- **Blast radius**: Isolated to new CSV `data/vietnambiz_articles.csv`. Existing merge/digest pipeline picks it up automatically.

## Definition-of-Done Checklist

- [x] Code directly satisfies the requested change
- [x] Lint: `ruff check` — passed
- [x] Code review: `/code-review` — findings documented above
- [x] Similar check: pattern matches existing crawler idioms — confirmed
- [x] Smoke test: `--latest --test` + `--range --test` — passed
- [ ] Tests: behavior change, coverage ≥80% diff — *new file, not modifying existing behavior*
- [x] Summary report generated
