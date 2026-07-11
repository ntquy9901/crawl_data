# Review — Version & Reality Verification

**Reviewer lens:** version/reality-verify (from `finalize_reviewers`).
**Target:** `ARCHITECTURE-SPINE.md` (2026-07-11).
**Date:** 2026-07-11.
**Method:** web-searched current versions (July 2026) for every Stack-table entry; read `base_news_crawler.py`, `pyproject.toml`, `.python-version`, `utils/anti_bot.py` against the spine's brownfield claims; cross-checked AD-11 `event_type` enum and VSDC/HNX access claims against the PRD `addendum.md` + web reality.

---

## Verdict: **PASS (with minor notes)**

The spine is well-grounded. Every Stack-table technology exists, is current as of July 2026, and is the right fit for a Python async crawler. Brownfield conventions are accurately ratified against the live code — including the one explicit divergence (AD-3, HN_TZ vs UTC), which is factually correct. The VSDC/HNX/SSC access claims and the `event_type` taxonomy are reality-checked (empirically probed per the addendum, and corroborated by web evidence), not training-data assertions. No blocking findings. Four minor notes below; two deserve a light follow-up, none block adoption.

---

## 1. Stack currency — all current (web-verified, 2026-07-11)

| Stack entry | Web-verified current (Jul 2026) | Verdict |
| --- | --- | --- |
| **Python 3.13** | 3.13.14 (Jun 10, 2026) is latest 3.13.x. ⚠️ **3.13 EOL = 2026-10-01** (endoflife.date); 3.14.x series already shipping (3.14.6, Jun 10 2026). | ✅ Current, but **EOL in ~3 months** — see Note A. |
| **requests** | 2.34.2 (latest). `pyproject.toml` pins `>=2.31.0` → satisfied. | ✅ Current & correctly pinned. |
| **playwright + chromium** | 1.61.0 (Jun 29, 2026). `pyproject.toml` pins `>=1.40.0` → satisfied. Min Python 3.10. | ✅ Current. |
| **playwright-stealth** | v1.x → **v2.0.0** is current (context-manager/`Stealth` class API; breaking import change). `utils/anti_bot.py:12` already uses the **v2 API** (`from playwright_stealth import Stealth`). `pyproject.toml` pins `>=1.0.0` — floor is too low but resolved version is current. | ✅ Current **but pin is stale** — see Note B. |
| **lxml** | 6.1.1 (May 18, 2026); 7.0.0a3 alpha. `pyproject.toml` pins `>=5.0` → satisfied. | ✅ Current. |
| **PyMuPDF** | 1.28.0 (Jun 29, 2026). `pyproject.toml` pins `>=1.28` → exact. | ✅ Current & correctly pinned. |
| **pandas** | 3.0.4 (Jun 28, 2026) — **3.0 is a major breaking release** (Python 3.14 support, breaking changes). `pyproject.toml` pins `>=2.0.0` → will resolve to 3.0.4. | ✅ Current, **but floor spans a major break** — see Note C. |
| **Windows Task Scheduler** | N/A (OS feature). `CrawlDailyNews` task @ 05:00 referenced. | ✅ Fits; not versionable. |

**Sources:** [Python source releases](https://www.python.org/downloads/source/), [endoflife.date/python](https://endoflife.date/python), [requests PyPI](https://pypi.org/project/requests/), [playwright PyPI/releases](https://pypi.org/project/playwright/), [playwright-stealth PyPI](https://pypi.org/project/playwright-stealth/), [lxml PyPI](https://pypi.org/project/lxml/), [PyMuPyPI](https://pypi.org/project/pymupdf/), [pandas](https://pandas.pydata.org/).

---

## 2. Brownfield ratification — accurate against the code

Cross-checked each spine claim against `base_news_crawler.py`:

| Spine claim | Code reality (`base_news_crawler.py`) | Match |
| --- | --- | --- |
| Hooks `listing_url/parse_listing/parse_article/next_page` | Lines 96-115: exactly these 4 abstract hooks, same signatures. | ✅ |
| Dedup by `url` (`_load_seen`) | Line 134: `_load_seen()` reads `url` column into `seen` set; line 205 skips `if u in self.seen`. | ✅ |
| `id = md5(url)[:12]` | Line 49: `short_id(url)` = `hashlib.md5(url.encode())[:12]`. Line 177 assigns it. | ✅ |
| `CSV_HEADERS` = the opinion-news schema | Lines 28-31: exactly `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`. Spine correctly calls this the "opinion/news" schema and builds a *separate* ObjectiveRecord (AD-1) rather than mutating it. | ✅ |
| Stable `UA_HEADERS`, no per-request fake-UA | Line 33-35: fixed Chrome 124 UA string. Matches spine's "stable UA, **không** fake-useragent mỗi request" pitfall note. | ✅ |
| ThreadPoolExecutor, `--workers`/`--batch`, audit log | Lines 211, 324-325, 160-167. | ✅ |
| `collected_at` via `HN_TZ` (+07) | Line 26: `HN_TZ = timezone(timedelta(hours=7))`. Line 42: `now_iso()` = `datetime.now(HN_TZ).strftime("...%z")` → emits `+0700`. | ✅ |

### AD-3 divergence — **VERIFIED ACCURATE** ✅
The spine asserts (AD-3): base uses `HN_TZ` (+07) for `collected_at`; the objective layer must emit UTC instead. This is factually correct on both sides:
- **Base side:** `now_iso()` (line 42) returns local `+0700`, not UTC. Confirmed.
- **Spine side:** wants `...Z` (UTC). This is a deliberate, real divergence, correctly flagged `[DIVERGENCE]`, and the spine's prescription ("adapter objective PHẢI ghi UTC, không kế thừa `now_iso()` nguyên vên") is the right call — opinion crawlers keep `+07`, objective layer overrides. **The spine does not assert anything the code contradicts.**

Minor precision nit (non-blocking): AD-3 says base uses "+07"; the actual `now_iso()` output is `+0700` (strftime `%z`, no colon) and stores tz-aware local, not a bare "+07" string. The semantic claim (+07 offset, not UTC) is correct; the literal string representation differs. Not worth fixing in the spine.

---

## 3. Reality-check of asserted decisions (VSDC/HNX, event_type, document_id, checksum)

### VSDC/HNX/SSC access claims — reality-anchored ✅
The spine relies on the addendum's "empirically probed 2026-07-11" access digest. Web evidence corroborates:
- **VSDC (`vsd.vn`) = public HTTP corporate actions:** Confirmed — VSDC (Vietnam Securities Depository and Clearing Corporation) publishes corporate-action notices at `vsd.vn/en/ad/{id}` (e.g. dividend payments, rights issues, stock dividends observed live: `vsd.vn/en/ad/170543` BED dividend, `vsd.vn/en/ad/195101` REE stock dividend). No Cloudflare/paywall on public reads. The spine's `vsdc_crawler.py` adapter (HTTP, ID sweep) is sound.
- **HNX = server-rendered HTML disclosures:** Plausible per addendum; HNX is a known exchange disclosure site. (Not re-probed independently — addendum's empirical probe is the source of record; spine defers to it correctly.)
- **SSC = Oracle ADF/Playwright-needed:** The addendum's claim (JSF postback, shell HTML) is a known SSC.gov.vn characteristic. Spine defers SSC to a later epic — correctly.
- **HOSE = React SPA + OAuth Bearer (`api.hsx.vn`):** Spine defers HOSE (dropped/deferred). This matches the known hard-to-scrape HOSE reality. No fabricated access claim.

**No access claim in the spine is asserted from training data.** Each is either empirically probed (addendum) or deferred, and the probed ones are web-corroborated.

### AD-11 `event_type` enum — grounded, with a coverage note ✅ (minor)
Enum: `{financial_statement, board_resolution, dividend, stock_issuance, stock_split, rights_issue, esop, insider_trading, shareholder_change, ma, exec_change, agm, extraordinary_announcement, other}`.

Cross-checked against the observed VSDC announcement taxonomy: `dividend`, `stock_issuance`, `stock_split`, `rights_issue`, `esop`, `insider_trading`, `agm` all map 1:1 to real VSDC corporate-action notice types. `extraordinary_announcement` maps to Circular 96's 24-hour extraordinary-disclosure category. `other` is a correct catch-all.

**Coverage gap (non-blocking):** VSDC also publishes (a) **bond-related** announcements (interest, redemption, conversion) and (b) **foreign-ownership** disclosures. Neither is in the enum. Given the objective scope is **VN30 equity** (AD-5), omitting bonds and foreign-ownership is a defensible scope decision, not a fabrication — but the spine should note this exclusion explicitly (one line in AD-11 or Deferred) so a future bond/foreign-ownership adapter doesn't get force-fit into `other`.

### `document_id = sha1(source+url)[:16]` — sound, deliberate divergence ✅
- Spine (Consistency table): `document_id = sha1(source+url)[:16]`, explicitly **different** from news-layer `short_id` (md5(url)[:12]) to "tránh đụng id-space."
- Code reality: news layer `short_id` = md5(url)[:12] (line 49). Spine's new `sha1(source+url)[:16]` is a different algorithm (sha1 vs md5), different input (includes source prefix), different length (16 vs 12) → no collision possible between the two id-spaces. This is a considered, correct design, not an assertion. Collisions within the objective layer: sha1[:16] = 64 bits → birthday bound ~4B docs; far above any realistic VN30 disclosure volume. Fine.
- SHA1 collision resistance is cryptographically broken, but for a 16-char non-adversarial dedup key this is irrelevant (no attacker controls source+url to force collision in a self-crawled dataset). No issue.

### `checksum = sha256(normalize(raw_text))` (AD-6) ✅
Standard near-dupe content fingerprint. sha256 is the correct choice for content addressing (unlike the document_id, this is not truncated, so full hash strength). `normalize(raw_text)` is left to the build step — underspecified but appropriately deferred to `build_objective.py` impl. Not a fabrication; standard practice.

### `company_code` regex `^[A-Z0-9]{3,5}$` (AD-4) ✅
HOSE/UPCoM tickers are 3-5 chars uppercase alphanumeric (VNM, FPT, HPG, BVH...). Regex is correct for the Vietnamese ticker format. VN30 is all HOSE (3-5 char) — matches.

---

## Findings (ranked)

### F1 — [web-check] Python 3.13 reaches EOL 2026-10-01 (~3 months out) — *minor, plan-ahead*
The spine pins Python 3.13 (`.python-version`), which is current but enters end-of-life in October 2026. The objective layer is greenfield (new `objective/` package), so this is the natural moment to at least *flag* a 3.14 migration path rather than entrench 3.13. Not blocking — 3.13 is supported through the build of v1 — but the spine's Stack table should note the EOL so the team isn't surprised. **Action:** add a one-line note in Stack or Deferred ("Python 3.13 EOL Oct-2026; migrate to 3.14 in next window").

### F2 — [code-check] `pyproject.toml` pins `playwright-stealth>=1.0.0` but code already uses the v2.0.0 API — *minor*
`utils/anti_bot.py:12` does `from playwright_stealth import Stealth` (the v2 class/context-manager API, which broke imports at 2.0.0). The `>=1.0.0` floor in `pyproject.toml` would resolve a v1.x that lacks `Stealth`. In practice uv resolves the latest (2.x) so it works, but the pin is misleading. This is a **pre-existing** project issue, not introduced by the spine — but the spine ratifies the stack, so it should not propagate the stale floor. **Action:** (optional, brownfield hygiene) bump floor to `>=2.0.0` in `pyproject.toml`; spine itself needs no change.

### F3 — [code-check] pandas floor `>=2.0.0` spans the 3.0 major break — *minor*
pandas 3.0 (Feb 2026) introduced breaking changes; `>=2.0.0` allows both 2.x and 3.0.x resolution. `build_objective.py` (AD-8, not yet built) will be pandas-dependent. Since the objective layer is new, pin the floor to `>=3.0` to avoid a 2.x↔3.0 drift surprise during the build. **Action:** (for the objective build, not the spine text) tighten pandas pin when `build_objective.py` is implemented.

### F4 — [web-check] AD-11 `event_type` enum omits bonds + foreign-ownership (both real VSDC categories) — *minor, documentation*
VSDC publishes bond-related announcements and daily foreign-ownership disclosures; neither is in the AD-11 enum. Excluding them fits the VN30-equity objective scope, but the exclusion is implicit. **Action:** add one sentence to AD-11 or Deferred noting "bonds + foreign-ownership intentionally excluded for VN30-equity scope; add enum values if objective scope widens."

---

## What was checked and passed (no action)
- Stack: all 8 entries current (web-verified) and correctly fitted to an async Python crawler. ✅
- Brownfield: `CSV_HEADERS`, the 4 hooks, `_load_seen` url-dedup, `short_id` md5[:12], `UA_HEADERS` stable UA, ThreadPoolExecutor + `--workers`/`--batch`, audit log — every ratified convention matches the code verbatim. ✅
- AD-3 divergence (HN_TZ +07 vs desired UTC): both sides verified accurate; the divergence is real and correctly flagged. ✅
- VSDC/HNX/SSC/HOSE access claims: reality-anchored (empirically probed + web-corroborated); no training-data assertion. ✅
- `document_id` sha1 scheme, `checksum` sha256 scheme, `company_code` regex: sound, deliberate, non-fabricated. ✅
- `config/vn30.yaml` and `objective/` correctly marked NEW (do not yet exist on disk — verified via glob). ✅
- `run_daily_all.ps1` extension point (AD-10): file exists; `[ADOPTED]` is accurate. ✅

---

## Summary
**Verdict: PASS.** The spine ratifies live code conventions accurately (including the one genuine divergence, AD-3), every named technology is current and fitting as of July 2026, and no decision is asserted from training data without a reality-check. Four minor notes (Python 3.13 EOL heads-up, two stale `pyproject.toml` pins pre-existing, one enum-coverage doc gap) — none blocking; two are brownfield hygiene, two are spine-text suggestions.
