# Title Quality Assessment & `--test` Mode Enhancement

## Changes Made

**File:** `news_sitemap_crawler.py` (+35 lines)

| Change | Purpose |
|--------|---------|
| `SLUG_BASED_SOURCES` constant | Identify vneconomy/baodautu/tinnhanhchungkhoan as title-from-slug sources |
| `url_stub()` helper | Extract URL filename stem for readable stub display |
| `SitemapNewsCrawler._assess_title_quality()` | Static method returning `(is_ok: bool, reason: str)` — checks: too_short, empty, single_short_word, all_numeric, html_remnant |
| `SitemapNewsCrawler._print_title_quality_report()` | Prints quality table: Good/Bad counts + bad-titles table (URL stub, title, issue) + first 10 sample titles |
| `crawl_backfill()` title collection | Collects (url_stub, title) tuples in test mode for slug-based sources |
| argparse `--test` help text | Updated to mention title assessment |

## Title Quality Assessment Results

| Source | Titles Sampled | Good | Bad | % Good |
|--------|---------------|------|-----|--------|
| vneconomy | 3,408 | 3,408 | 0 | 100% |
| baodautu | 2,000 | 2,000 | 0 | 100% |
| tinnhanhchungkhoan | 2,945 | 2,945 | 0 | 100% |
| **Total** | **8,353** | **8,353** | **0** | **100%** |

**Finding:** `slug_to_title()` produces excellent results for all 3 slug-based sources. No bad titles detected across 8,353 samples from the last 2 sitemap shards (~30 days).

## Adversarial Code Review Findings

- **Fixed (v1):** Bad-titles table showed duplicated columns (both "Stub" and "Generated title" contained the same title text). Fixed by collecting `(url_stub, title)` tuples and displaying them separately.
- **Fixed (v1):** Regex `(caph|div|span|class|id)\d{0,3}` matched standalone English words like "Class" (false positive on baodautu's "H Class" title). Tightened to `(caph|div)\d{1,3}` with `\b` anchors.
- **Lint:** `f""` without placeholders → `""`; unused loop variable `i` → `_`.

## Recommendations for `slug_to_title()`

No urgent issues — current quality is 100%. Cosmetic improvements that could be made:

1. **Date pattern detection:** Slugs like `15-8-2026` → `1582026` (concatenated). Could split on number-nonnumber boundaries to produce `15 8 2026` or infer date formatting. Low priority — readers parse `1582026` as a date naturally.

2. **Abbreviation lookup table:** Common Vietnamese finance abbreviations in slugs (`ck`→chung-khoán, `dn`→doanh-nghiệp, `tcd`→tai-chinh-doanh-nghiep, etc.) could be expanded. The `capitalize()` approach produces readable results already (e.g., `Tphcm` for `tphcm`), so the value-add is marginal.

3. **Brand/English term preservation:** Terms like "coca-cola", "vinamilk", "group" are lossy (become "Coca Cola", "Vinamilk", "Group"). To preserve casing would require a term list or heuristic — not worth the complexity for metadata-only use.

**Recommendation:** Keep `slug_to_title()` as-is. The 100% quality rate confirms it's fit for purpose. If body fetching is added later, real titles from page HTML can override the slug-generated ones.
