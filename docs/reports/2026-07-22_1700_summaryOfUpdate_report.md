# Summary Report — 2026-07-22 17:00

## What changed

**1. Mở rộng news_sitemap_crawler thêm 3 nguồn sitemap**
Thêm `vneconomy`, `baodautu`, `tinnhanhchungkhoan` vào `news_sitemap_crawler.py`. Các nguồn này không nhúng title trong sitemap → implement `slug_to_title()` fallback (từ URL slug) + `parse_shard()` fallback. Đã backfill đầy đủ:
- vneconomy: 224.905 rows
- baodautu: 158.429 rows
- tinnhanhchungkhoan: 329.797 rows
- Tổng: ~713K articles mới

**2. Telegram crawler mới**
`telegram_crawler.py` — crawl public channel history qua t.me/s/ (plain HTTP + regex, không Playwright, không API key).
- 4 channels VN stock: kakatachannel (516), chungkhoanvietnammoon (1.651), chungkhoanvietnam2026 (227), chungkhoanF0 (13)
- Tổng: ~2.407 messages
- Schema đồng nhất với news_articles.csv, dedup theo url

**3. Clean code enforcement**
Thêm section "Clean Code (strict)" vào CLAUDE.md + fix telegram_crawler.py:
- Magic number → named constants (BATCH_SIZE, PROGRESS_INTERVAL, DEFAULT_SLEEP)
- Loại bỏ unused imports (ThreadPoolExecutor, lxml.html, sys, Path)
- Loại bỏ unused extracted fields (views, message_id) — YAGNI
- Tách `crawl_channel` → helper methods (_process_messages, _flush_batch, _log_progress)
- Xoá dead code (else branch trùng lặp trong main)
- Refactor main() giảm trùng lặp

**4. Merge mở rộng**
`merge_news.py` thêm: forum, telegram 4 channels.
`news_articles.csv` sau merge: **2.182.452 rows** (từ 16 sources).

**5. Social media expansion epic**
`docs/social-media-expansion-epic.md` — research + kế hoạch cho Facebook (Pages API), Zalo OA, TikTok.

## Files changed

| File | Purpose |
|---|---|
| `news_sitemap_crawler.py` | +3 sitemap sources, slug_to_title(), parse_shard fallback |
| `telegram_crawler.py` | NEW — Telegram channel crawler (4 channels) |
| `merge_news.py` | +forum + 4 telegram sources |
| `CLAUDE.md` | +Clean Code section |
| `docs/social-media-expansion-epic.md` | NEW — Social media epic plan |

## Tests & lint

- `ruff check telegram_crawler.py news_sitemap_crawler.py merge_news.py`: **Clean**
- `pytest` (190 tests): **190 passed**
- `pytest -m smoke` (9 smoke tests): **9 passed**

## Code review

- **Adversarial review (self):** telegram_crawler.py reviewed for clean code compliance. Issues found: unused imports (removed), unused extractions (removed), magic numbers (→ named constants), long method (→ helpers), dead code (removed). All resolved.
- **Similar check:** `merge_news.py` SOURCES dict pattern checked — consistent with existing entries.
- **Impact analysis:** `merge_news.py` callers: `run_daily_all.ps1` (runs merge_news.py after all crawlers). No other callers. Low blast radius.

## Final dataset (sau backfill)

| Source | Rows |
|---|---|
| cafef | 4.067 |
| ssi | 1.867 |
| hsc | 6 |
| vndirect | 2.043 |
| tuoitre | 283.568 |
| thanhnien | 387.169 |
| vietnamplus | 773.152 |
| vnexpress | 13.938 |
| vneconomy | 224.905 |
| baodautu | 158.429 |
| tinnhanhchungkhoan | 329.797 |
| forum | 1.104 |
| telegram (4 channels) | 2.407 |
| **news_articles.csv** | **2.182.452** |

## Commits
- `1ac0790` — feat: expand sitemap sources + telegram + social media epic
- `14a36b7` — docs: update project-context + sprint-status

All pushed to `origin/feat/data-classification-and-telegram`.

## Risks / follow-ups

- ❗**Telegram anti-bot unknown at scale**: t.me/s/ hiện không chặn, nhưng crawl sâu (100K+ pages) có thể trigger. Cần monitoring.
- 📌 **Facebook Pages Graph API** cần App Review (2-4 tuần) — epic đã lập, chưa implement.
- 📌 **Zalo OA** cần credentials từ OA owner — epic lập, chờ access.
- 📌 `news_sitemap_crawler.py` nên thêm `--test` mode cho 3 nguồn mới để verify title parsing.

## Definition-of-Done checklist

- [x] Code trực tiếp thực hiện yêu cầu
- [x] Tests pass (190/190, 9/9 smoke)
- [x] Ruff clean trên file thay đổi
- [x] Code review done + findings fixed
- [x] Summary report generated
- [x] Impact analysis: low (merge_news.py callers only)
- [x] Similar check: merge_news.py SOURCES consistent
