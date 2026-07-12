# TODO — Epic 2 + E3.2 remainder: BLOCKED on source access (verified live 2026-07-12)

All remaining stories were **live-probed** and are blocked on source access, not
on code. Per the strict DoD (no speculative code), they are deferred with the
evidence + the decision/path each needs. None can be implemented cleanly without
a product/environment change.

## E2.1 — Vietstock per-company disclosure (FR-16) — DONE (option 1, 2026-07-12)

Implemented in objective/adapters/vietstock_disclosure.py via the /data/EventsTypeData POST endpoint (no-JSON-API constraint relaxed for FR-16, see CLAUDE.md). Live-verified: VNM → 50 disclosure records. Original BLOCKED notes retained below for context.

### Original BLOCKED analysis (superseded)

**Evidence (3 Playwright probes + network capture):**
- `finance.vietstock.vn/<TICKER>/cong-bo-thong-tin.htm` renders the company
  overview (price/financial tables) but NOT the disclosure list — after
  goto + 5s wait + clicking the disclosure tab, the DOM has **0 scrapeable
  disclosure rows** (`a` matching disclosure title + VNM/cbtt href = 0).
- Network capture shows the disclosure data is loaded via internal POST
  endpoints: `finance.vietstock.vn/Data/GetDocument`, `/data/EventsTypeData`,
  `/Data/GetBondRelated`, … rendered into a JS grid component.

**Why blocked:** the data comes from `/Data/` POST endpoints that the
**no-Vietstock-JSON-API constraint (CLAUDE.md) forbids calling directly**, and
the browser-rendered DOM does not expose the items in a stable scrapeable
structure (JS grid). Compliant browser-scrape (render + read DOM) yields nothing.

**Decision needed (not a code task):**
- (a) Relax the no-JSON-API constraint for Vietstock disclosures and call the
  `/Data/GetDocument` endpoint directly (simplest, but breaks the standing rule),
  OR
- (b) Reverse-engineer the JS grid's rendered DOM with much deeper Playwright
  work (wait for the specific grid selector, possibly per-ticker), OR
- (c) Replace Vietstock with another Tier-3 route for VN30 disclosures.

## E2.2 — Cafef disclosure (FR-17) — BLOCKED (unreachable from this environment)

**Evidence:** `cafef.com.vn` returns `ERR_CONNECTION_TIMED_OUT` via BOTH plain
HTTP (urllib) AND headless Playwright (stealth browser) — on
`thi-truong-chung-khoan.chn` and `doanh-nghiep.chn`. The existing cafef crawler
uses RSS + sitemap (not these pages) for the same reason.

**Decision needed:** Cafef is IP/geo-throttled from this host. Options: route
through a proxy (the project has `proxies.txt`/`CAFEF_USE_PROXY` infra —
unverified), run from a different network, or drop Cafef and rely on the RSS
Tier-2 outlets + VSDC for VN30 coverage.

## E3.2 — remaining 6 Tier-2 outlets — NO RSS discoverable

**Verified (RSS autodiscovery + URL sweep, 2026-07-12):** of the guide's 9
non-VnExpress outlets, only **3 expose working RSS** (tuoitre, nld, thanhnien —
implemented). The other 6 have **no `<link rel=alternate type=…rss>` autodiscovery**
and the guessed feed paths fail (SSL-cert/timeout/DNS):
- vneconomy.vn — SSL CERTIFICATE_VERIFY_FAILED (likely has RSS; urllib CA issue).
- vietnamplus.vn — no autodiscovery (RSS exists at numeric section IDs; needs the
  section-id map).
- baodautu.vn — timeout.
- baochinhphu.vn — no autodiscovery.
- vietnam.vn (TTXVN) — no autodiscovery.
- Kinh tế Sài Gòn — domain unclear (thesaigotimes.vn DNS fail; may be sggp.org.vn).

**Path:** per-site work — for each: fix TLS (use `requests` w/ proper CA), find
the real feed via sitemap or the section-id map, or fall back to sitemap-scraping
the article list. Low yield (several VN outlets have discontinued RSS).

## Net

Implemented + live-verified Tier-2 outlets: **vnexpress, tuoitre, nld, thanhnien**
(4). VN30 corporate-action coverage stands on **VSDC** (Tier-1, working). E2
(Vietstock/Cafef disclosure) needs a constraint/proxy/network decision before it
is code-able.
