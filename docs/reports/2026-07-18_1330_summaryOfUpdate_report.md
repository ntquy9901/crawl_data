# Summary — News sitemap backfill crawler (tuoitre/thanhnien/vietnamplus)

## Context
User request: crawl nld/thanhnien/tuoitre/vietnamplus/vnexpress "từ năm 2000, hiện tại ít quá" —
the existing Tier-2 RSS adapters (`objective/adapters/tier2_rss/outlets.py`) only pull the latest
~20-50 items per feed (no history), which is why volume was low.

## Research findings (changed the plan)
Live sitemap probing (2026-07-18) showed the "từ 2000" premise doesn't hold and one of the 5
requested sources isn't independently crawlable:
- **tuoitre**: sitemap floor ~2011-01, no bot-block.
- **thanhnien**: sitemap floor ~2011-06, no bot-block.
- **vietnamplus**: sitemap floor ~2010-01 (monthly shards, gzip), no bot-block.
- **nld.com.vn**: entire domain (including RSS) redirects to `tuoitre.vn/nld/*` and serves Tuổi Trẻ
  content — not an independent source. Excluded (would just duplicate tuoitre under a fake label).
- **vnexpress**: sitemap index readable, but per-day shard URLs are bot-blocked (302 redirect) for
  both plain `requests` (any UA, incl. Googlebot) and headless Playwright without stealth. Deferred.

User confirmed (via AskUserQuestion): proceed with the 4 non-vnexpress sources → then narrowed to 3
once the nld redirect was discovered; full backfill from each site's real floor to today;
metadata-only (title/url/pub_date, no per-article fetch).

## What changed
- **`news_sitemap_crawler.py`** (new): sitemap-index → shard-XML backfill crawler for
  tuoitre/thanhnien/vietnamplus. Since each site's sitemap already embeds the article title
  (`image:title` or `news:title`), no per-article HTTP fetch is needed — lighter than
  `cafef_crawler.py`'s approach (which must fetch every article to read a breadcrumb). Subclasses
  `BaseNewsCrawler` to reuse its `fetch`/`_load_seen`/`_append`/`CSV_HEADERS` (see code-review below)
  and only implements the sitemap-specific `crawl_backfill`.
- **`merge_news.py`**: added `tuoitre`/`thanhnien`/`vietnamplus` to `SOURCES` (no column renames
  needed — schema matches `CSV_HEADERS` directly).
- **`data_classification.py`**: added the 3 sources to `_BY_SOURCE` → `objective` (factual news,
  consistent with `cafef`/`ssi`).
- **Tests**: `tests/test_news_sitemap_crawler.py` (16 unit tests: title-cleaning for both CDATA
  styles, shard-range filtering, shard parsing incl. suffix rejection, dedup-against-CSV, CLI,
  max-articles cap, index-fetch-failure path) + `tests/smoke/test_smoke_news_sitemap.py` (marked
  `smoke`, fixture-only, no network) + 3 XML fixtures under `tests/fixtures/news_sitemap/`.

## Code review (`/code-review`, medium effort)
3 parallel finder agents (correctness / reuse+simplification+efficiency / altitude+conventions) +
verification. 6 findings surfaced, all resolved:
- **Fixed**: heavy duplication of `_load_seen`/`_init_csv`/`_append`/`fetch`/`UA_HEADERS` vs
  `base_news_crawler.py` → refactored `SitemapNewsCrawler` to subclass `BaseNewsCrawler` instead of
  reinventing a third crawler pattern (this also addressed the separate "third parallel pattern"
  altitude finding). Dead `base_url` config key removed. `--test` mode narrowed its date window
  up front instead of scanning the full ~15-year sitemap index before slicing to 2 shards.
- **Refuted** (verified directly, no change): claimed `parse_date` can't handle tuoitre's
  no-seconds lastmod format (`2026-07-15T23:23+07:00`) — confirmed by direct test it parses fine via
  the function's regex-prefix fallback. Claimed `max_articles` cap leaves same-shard items
  incorrectly un-deduped — re-reading the loop shows this is correct resumable-run behavior.

## Tests / coverage / lint
- `uv run pytest -q` → **166 passed** (full suite; was 169 before a mid-review refactor removed 3
  tests for a function that got absorbed into the reused base class).
- `uv run pytest --cov=news_sitemap_crawler --cov-report=xml` + `uvx diff-cover coverage.xml
  --fail-under=80` → **93.5% diff coverage** (gate: 80%).
- `uvx ruff check news_sitemap_crawler.py merge_news.py data_classification.py tests/...` → clean.
- Smoke gate (`uv run pytest -m smoke`): includes the new fixture-only tuoitre backfill smoke test.
- Live verification: ran `--test` (small window) against real tuoitre/thanhnien/vietnamplus
  sitemaps — all 3 parsed correctly (titles, URLs, dates) before and after the refactor.

## Impact analysis
New file + additive changes only to `merge_news.py`/`data_classification.py` (new dict entries,
no renames of existing keys). No existing crawler's behavior changes. `run_daily_all.ps1` and
Task Scheduler `CrawlDailyNews` are untouched — this crawler is not yet wired into the daily job
(backfill-only tool, run manually per source).

## Not done / follow-ups
- **Full backfill not yet run** — this report covers implementation + validation only. Next step
  (pending user go-ahead per session): run
  `PYTHONUTF8=1 python news_sitemap_crawler.py --source <tuoitre|thanhnien|vietnamplus>` for each
  source (floor → today), likely 10-30 min each given thousands of shards.
- vnexpress: deferred (bot-blocked at the per-day-shard level; would need `utils/anti_bot.py`
  stealth, unverified whether that's sufficient).
- nld: excluded (not an independent source — see research findings above).
- Not wired into `run_daily_all.ps1` — these are one-time-backfill tools; a daily incremental mode
  (e.g. only the latest shard) could be added later if ongoing daily volume from these sources is
  wanted, following the same `--latest`-vs-`--range` split cafef/ssi/hsc/vndirect already use.

## Definition of Done
- [x] Code satisfies the request (no unrelated refactor beyond what code review required)
- [x] Tests written, diff-coverage 93.5% (≥ 80% gate)
- [x] Checks run: pytest, ruff, diff-cover (all above)
- [x] Code review run (`/code-review`, medium) — 6 findings, all resolved (4 fixed, 2 refuted)
- [x] Smoke test added and passing (fixture-only, no live network)
- [x] Impact analysis (above)
- [ ] Similar-check: base_news_crawler.py's Template Method pattern was reused here; no further
  copies of this sitemap-shard pattern exist elsewhere to check
- [ ] Actual backfill run — pending (see Not done / follow-ups)
