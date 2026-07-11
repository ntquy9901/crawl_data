# Rubric Review — ARCHITECTURE-SPINE.md

Reviewer: rubric-walker (claude)
Date: 2026-07-11
Altitude: initiative (architecture spine)
Spine reviewed: `architecture-crawl_data-2026-07-11/ARCHITECTURE-SPINE.md`
Cross-checked against: `base_news_crawler.py` (brownfield), `prd-crawl_data-2026-07-11/prd.md` (driving spec)

---

## Verdict: NEEDS-FIX (minor)

The spine is strong: the right divergence points are targeted, the ratification of the brownfield Template-Method pattern is explicit, and the objective/opinion boundary (AD-9) is a genuinely hard problem solved well. But two findings block a clean pass — one real divergence point left under-specified (the `_load_seen`/`_init_csv` inheritance collision against `ObjectiveRecord`), and one missing hardening on the most load-bearing AD (AD-1 enforceability). Both are surgical; neither invalidates the design.

---

## Checklist Findings

### 1. Fixes the REAL divergence points — misses none?  **MOSTLY YES, one gap**

**Passes.** The ADs target places where two independently-built adapters would genuinely diverge:
- AD-1 (field set), AD-3 (tz), AD-4 (ticker casing), AD-5 (universe list), AD-6 (dedup), AD-11 (event_type enum) — all are real fork-in-the-road decisions. If two devs each built a VSDC adapter and a Cafef adapter without these, they would produce non-mergeable CSVs. Correct targeting.

**F-1 (gap, item 1): AD-7a under-specifies the inheritance boundary — a real divergence point left half-decided.**
AD-7a says HTTP objective adapters "subclass `BaseNewsCrawler` (hooks `listing_url/parse_listing/parse_article/next_page` already ratified), override `_fetch_and_parse` to emit ObjectiveRecord." But in the brownfield code (`base_news_crawler.py`), the subclass ALSO inherits:
- `_init_csv()` — hard-writes `CSV_HEADERS` (12 cols: `id, source, title, category, pub_date, url, author, lead, pdf_url, pdf_filename, collected_at, body`) as the header row;
- `_append()` — writes via `DictWriter(fieldnames=CSV_HEADERS)`, silently dropping any `ObjectiveRecord` field not in `CSV_HEADERS`;
- `_load_seen()` — reads the `url` column from `self.csv_file`.

`ObjectiveRecord` (AD-1) has a DIFFERENT 16-field set (`document_id, source, source_tier, url, publish_time, crawl_time, company_code, company_name, title, raw_text, language, category, event_type, attachment_urls, checksum, raw_path`). An adapter that naively inherits `_init_csv`/`_append` would either (a) write the wrong header row and drop ~8 objective fields on append, or (b) force the adapter author to override `_init_csv`/`_append`/`_load_seen` — and TWO authors would override them slightly differently (different field order, different null handling, different seen-key). That is exactly the kind of divergence the spine exists to kill.

AD-7a must either: (i) name the override set explicitly ("override `_fetch_and_parse` AND `_init_csv`/`_append`/`_load_seen`, sourced from `objective/schema.py`"), or (ii) point to a shared `BaseObjectiveCrawler` that fixes these once. Right now AD-1 governs the record but AD-7 governs the framework wiring, and the wiring contract is incomplete. Severity: medium-high — this is the one AD whose Rule does not fully prevent its own stated divergence.

### 2. Every AD's Rule enforceable and actually prevents its divergence?  **YES, except AD-1/AD-7 (see F-1)**

- AD-2 (raw vs cleaned paths): enforceable — path conventions are machine-checkable. Good.
- AD-3 (UTC): enforceable, and the `[DIVERGENCE]` callout against `HN_TZ`/`now_iso()` is exactly right — it flags the real brownfield wart instead of papering over it. Strong.
- AD-4 (ticker regex + VN30 source): enforceable via the `vn30.yaml` reference. Good.
- AD-5 (single universe file): enforceable — "one file, one owner" + AD-4 cross-ref. Good.
- AD-6 (url-dedup + checksum): two-layer, both enforceable. The split (url at adapter, checksum at build) is the right altitude.
- AD-8, AD-9 (per-source isolation, objective/opinion wall): enforceable via filesystem tree. AD-9's "build_objective.py chỉ đọc objective source CSV" is a clean guard.
- AD-10, AD-11 (scheduler, enum): enforceable. Enum defined in one file (`objective/schema.py`).

**F-2 (item 2): AD-1's Rule says "Không thêm/bớt cột" but names no mechanism.** Unlike AD-3/AD-4/AD-11, AD-1 has no "defined in `objective/schema.py`" anchor stated in its own Rule body — that anchor appears only later in the Structural Seed (`schema.py # ObjectiveRecord + event_type enum`). Since AD-1 is the single most load-bearing invariant (everything else assumes it), its Rule should explicitly name the single source-of-truth module for the field set, so two adapters can't each hand-roll a `dataclass`/`TypedDict` that drifts. Minor, but AD-1 earns the strongest wording because everything hangs off it.

### 3. Nothing under Deferred could let two units diverge?  **YES — clean**

Checked each Deferred item:
- NLP/macro/SSC/HOSE-direct/HNX-UPCoM/Tier-2-enrichment — all genuinely downstream or out-of-scope; none creates a present-day adapter choice. A future SSC adapter would need its own ADs (correctly deferred).
- **Operational envelope (deployment/env/infra)** — marked `[ADOPTED]` inheriting the current single-Windows-box setup. See F-3 below — this is the one dimension worth scrutinizing, but as "adopted" it does not let two units diverge.

No deferred item should have been an AD. Clean.

### 4. Named tech verified-current?  **YES, with notes**

Stack table (line 110-119) lists: Python 3.13, requests, playwright+chromium+playwright-stealth, lxml, PyMuPDF, pandas, Windows Task Scheduler. All are present in the brownfield project (`CLAUDE.md`, `pyproject`, existing crawlers). The table is correctly labeled "seed — verified existing, ratified."

- **To verify (not asserting failure):** version pins for `playwright`, `requests`, `PyMuPDF` are not given (just names). For a spine at this altitude that is acceptable (version pinning belongs to the story/implementation level), but the reviewer flags that `playwright-stealth` in particular has had breaking releases; if a story pins a version, it should be checked against the `utils/anti_bot.py` import surface. No action required at spine level.

### 5. Ratifies rather than contradicts brownfield?  **YES, strongly — with the F-1 caveat**

The spine explicitly ratifies, not contradicts:
- `BaseNewsCrawler` Template Method + hooks (AD-7a) — matches `base_news_crawler.py` exactly.
- `VietstockCrawler` + `utils/anti_bot` reuse (AD-7b) — matches.
- `CSV_HEADERS`/opinion schema kept for existing crawlers, ObjectiveRecord separate (AD-1 note) — correct separation, does not break existing `data/*.csv`.
- `HN_TZ`/`now_iso()` flagged as a `[DIVERGENCE]` to fix in objective layer only (AD-3) — correct: ratifies the existing opinion layer as-is while fixing the new one. This is the textbook way to handle a brownfield wart.
- `short_id` (md5) vs `document_id` (sha1) — Consistency Conventions explicitly notes the id-space split to "avoid đụng id-space." Good catch, ratifies without collision.
- `utf-8-sig` CSV encoding, `PYTHONUTF8=1`, audit log, `UA_HEADERS` stable UA, `.env`+sibling config, `DOWNLOAD_PDF`/`--no-playwright` flags — all ratified verbatim from the codebase.
- Dedup split (url in adapter via `_load_seen`, checksum at build) — matches the brownfield `_load_seen` pattern.

The ONLY ratification gap is F-1: the spine ratifies the framework hooks but under-specifies which base-class methods an objective adapter must NOT inherit as-is (`_init_csv`/`_append`/`_load_seen`), because those are bound to `CSV_HEADERS`/`now_iso()`, which the objective layer deliberately diverges from. The ratification is correct in spirit; it's just incomplete on the method-level boundary.

### 6. PRD capabilities covered (FR → architecture)?  **YES — full map**

The `binds:` frontmatter lists `[FR-4, FR-5, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-14, FR-15, FR-16, FR-17]` — exactly the in-scope FRs from PRD §6.1. Cross-checked the Capability→Architecture Map (lines 147-159):
- FR-4,5 (VSDC) → `vsdc_crawler.py` governed by AD-1,2,3,4,6,7. Covered.
- FR-16 (Vietstock browser disclosure) → `vietstock_disclosure.py` governed by AD-7, AD-5. Covered.
- FR-17 (Cafef HTTP disclosure) → `cafef_disclosure.py` governed by AD-7. Covered.
- FR-15 (Tier-2 RSS x10) → `tier2_rss/` governed by AD-7 (company_code nullable). Covered.
- FR-8 (canonical schema) → `schema.py` governed by AD-1, AD-11. Covered.
- FR-9 (raw preservation) → `data/raw/` governed by AD-2. Covered.
- FR-10 (dedup) → base url-dedup + `build_objective.py` checksum. Covered.
- FR-11 (resumable) → `BaseNewsCrawler._load_seen`. Covered (subject to F-1).
- FR-12 (versioning) → `build_objective.py` → `objective_v<date>.csv`. Covered.
- FR-13 (objective/opinion separation) → AD-9. Covered.
- FR-14 (daily schedule) → AD-10. Covered.

Out-of-scope FRs (FR-1,2,3 HNX/UPCoM; FR-6 HOSE; FR-7 SSC) are correctly Deferred. Every in-scope FR maps to a governed location. No orphan capabilities.

### 7. Every owned dimension decided/deferred/open-question — no whole dimension silent?  **YES, with one flag**

Walked the dimensions this altitude owns:
- **Data model / schema:** decided (AD-1, AD-11). Good.
- **Storage topology:** decided (AD-2 layered, AD-8 versioned, AD-9 wall). Good.
- **Identity / keys:** decided (Consistency Conventions — sha1[:16] document_id). Good.
- **Time semantics:** decided (AD-3 UTC). Good.
- **Universe / filtering:** decided (AD-4, AD-5). Good.
- **Dedup / idempotency:** decided (AD-6). Good.
- **Concurrency / parallelism:** NOT an explicit AD, but ratified from brownfield (`ThreadPoolExecutor` via `--workers`, `ProcessPoolExecutor` for PDF) in Consistency Conventions/CLAUDE.md. Acceptable — the project's crawl-design rules already govern this and the spine inherits them. Not silent, just inherited.
- **Scheduling / freshness:** decided (AD-10). Good.
- **Error / observability:** decided (Consistency Conventions — audit log, fail-continue). Good.
- **Operational envelope (deployment/environments/infra/operations):** Deferred as `[ADOPTED]` (single Windows box, `.env`, file+CSV, Task Scheduler). This is a decision (adopt existing), not silence.

**F-3 (item 3, low severity): The "operational envelope" is adopted but its constraints are not surfaced as invariants the new objective layer must respect.** The spine says "single Windows box, file+CSV store, no DB/cloud" but does not state the load-bearing consequences for the objective layer — e.g., `build_objective.py` doing checksum-dedup over a growing `data/objective/` is an unbounded in-process scan on a single box with no DB index; the objective layer adds `data/raw/<source>/` bytes that can grow unbounded with no retention policy. At spine altitude this is acceptable to defer, but a one-line note ("raw layer growth is unbounded; retention/compaction is a story-level Open Question") would prevent a future story from silently assuming a retention AD exists. Not blocking.

---

## Summary Table

| # | Item | Finding | Severity |
|---|------|---------|----------|
| F-1 | 1, 2, 5 | AD-7a under-specifies the base-class inheritance boundary: objective adapters inheriting `_init_csv`/`_append` (bound to `CSV_HEADERS`) + `_load_seen` would collide with `ObjectiveRecord`. Name the override set or point to a `BaseObjectiveCrawler`. | **medium-high (blocks clean pass)** |
| F-2 | 2 | AD-1 Rule lacks an explicit single-source-of-truth module anchor in its own body (the `schema.py` anchor lives only in the Structural Seed). AD-1 is the most load-bearing AD — make its Rule self-contained. | low |
| F-3 | 7 | Operational envelope `[ADOPTED]` but raw-layer growth/retention is not flagged as an Open Question for stories. | low |

No findings against items 3, 4, 6 (Deferred is clean; tech is verified-existing; PRD coverage is complete and mapped).

---

## Recommended Fixes (surgical)

1. **F-1 (required for pass):** In AD-7a, expand the Rule to either:
   - "Objective HTTP adapters subclass `BaseNewsCrawler` and MUST override `_fetch_and_parse`, `_init_csv`, `_append`, `_load_seen` — all sourced from `objective/schema.py` (ObjectiveRecord fieldnames + UTC timestamps). Do NOT inherit `CSV_HEADERS`/`now_iso()`," OR
   - introduce a `BaseObjectiveCrawler(BaseNewsCrawler)` that fixes these once, and AD-7a says "subclass `BaseObjectiveCrawler`."
2. **F-2 (recommended):** In AD-1's Rule body, add "Field set defined in exactly one place: `objective/schema.py` (`ObjectiveRecord`). All adapters import from there." (mirror AD-11's `schema.py` anchor).
3. **F-3 (optional):** Add a one-line Open Question under the operational-envelope Deferred bullet: "raw layer (`data/raw/<source>/`) grows unbounded on a single-box file store; retention/compaction policy deferred to story level."
