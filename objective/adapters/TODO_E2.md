# TODO — Epic 2 (Vietstock browser + Cafef disclosure), FR-16/FR-17

Deferred: both need a real browser to obtain the disclosure list (verified
2026-07-12). Not implemented blind — a browser adapter must be written against
the *rendered* DOM, which requires a live Playwright run to discover selectors.

## E2.1 — Vietstock per-company disclosure (FR-16)

**Finding (live probe):** `finance.vietstock.vn/<TICKER>/cong-bo-thong-tin.htm`
returns a ~300 KB **shell** via plain HTTP (stable UA works — no captcha on the
GET), but the disclosure LIST is **JSON-loaded by AJAX** — the static HTML has
no disclosure `<a>` items (only nav/social links). The page `<title>` confirms
the company resolved (e.g. "VNM: CTCP Sữa Việt Nam"). Dates `12/07/2026` appear
(near the disclosure table) but the rows themselves are populated post-render.

**Constraint (CLAUDE.md):** KHÔNG dùng Vietstock JSON API — chỉ browser crawl.
So the adapter MUST render the page (Playwright) and scrape the populated DOM,
not call the AJAX JSON endpoint.

**Plan:**
1. Subclass `BaseObjectiveCrawler` BUT override `fetch()` to use Playwright
   (reuse `utils/anti_bot` — stealth browser, `safe_goto`, stable UA — same as
   the existing `crawler.py` `VietstockCrawler`).
2. `listing_url(page)` = `finance.vietstock.vn/{ticker}/cong-bo-thong-tin.htm`
   for each VN30 ticker (iterate `load_vn30()`).
3. **Live step (do first):** render one ticker's page in a real browser, dump
   the disclosure-table DOM → identify the row selector (title / date / detail-
   link / attachment). Only then write `parse_listing`/`parse_article`.
4. `company_code` = the ticker being iterated (known) → VN30 by construction;
   `event_type` via `classify_event_type(title)`; `raw_text` from the detail page.
5. `--latest` per ticker; the daily schedule (run_daily_all.ps1) loops VN30.

## E2.2 — Cafef per-company disclosure (FR-17)

**Finding:** `cafef.com.vn` company/disclosure pages **timed out** on plain HTTP
(2026-07-12) — Cafef throttles/blocks non-browser clients (its own crawler uses
the RSS/sitemap path, not these pages). Needs browser or the Cafef sitemap
backfill route (see `docs/anti-throttle.md`).

**Plan:** either (a) Playwright render of the Cafef company-disclosure page
(same browser-override pattern as E2.1), or (b) use the Cafef sitemap to find
disclosure articles + filter by VN30 company-name keyword. Decide after a live
probe of the rendered Cafef disclosure DOM.

## Why deferred, not done

Both are browser stories whose selectors can only be confirmed by rendering the
live page. Writing them blind (guessing the JSON-populated DOM) would be
speculative code that likely misses — violating the no-speculation rule. Do E2
in a session that can run Playwright live to capture the rendered structure.
