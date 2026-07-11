---
review: adversarial
reviewer_lens: "Construct two units one level down that each obey every AD to the letter yet still build incompatibly."
target: ARCHITECTURE-SPINE.md (AD-1..AD-11)
units_one_level_down: [vsdc_crawler, vietstock_disclosure, cafef_disclosure, tier2_rss/*, build_objective.py]
date: 2026-07-11
verdict: REVISE (7 exploitable incompatibility pairs found; 2 are data-corrupting)
---

# Adversarial Review — Architecture Spine

## Method

For each AD I ask: *can two adapters each produce ObjectiveRecords that pass every literal word of the AD, yet are mutually incompatible at the merge/join/dedup step?* Every pair below names (a) the two compliant-but-incompatible outputs, (b) the exact AD text that permits it, and (c) the new/tightened AD that closes it. I ground every construction in the actual code (`base_news_crawler.py`, `merge_news.py`, `utils/body_extractor.py`, `utils/dedup.py`) so the attacks are buildable, not hypothetical.

The spine's core bet is: *one ObjectiveRecord contract (AD-1) holds every adapter consistent.* This review finds that the contract is a **field-set contract** (which columns exist) but **not a value contract** (what a column's value means). Field-set agreement is necessary but not sufficient — two CSVs with identical headers can still fail to join. Seven concrete failure modes follow.

---

## HOLE 1 — `company_code` placement diverges between ticker-as-code and ticker-as-name (data-corrupting)

**AD text at fault:** AD-4 — "`company_code` = uppercase, regex `^[A-Z0-9]{3,5}$`, nguồn từ VN30 list. Tier-1 bắt buộc có; Tier-2 news `company_code` **nullable**." AD-1 lists `company_code, company_name` as two fields but defines neither's *content semantics* beyond the regex on code.

**The incompatible pair — both AD-compliant:**

- **Adapter A (`vsdc_crawler`):** A VSDC corporate-action row names the entity by legal name ("Công ty Cổ phần Sữa Việt Nam") with no ticker in the feed. The adapter obeys AD-4: it needs a `company_code` matching `^[A-Z0-9]{3,5}$`. It cannot emit the legal name as code (fails regex), so it looks up the VN30 ticker → `company_code="VNM"`, `company_name="Công ty Cổ phần Sữa Việt Nam"`.
- **Adapter B (`cafef_disclosure`):** A Cafef disclosure headline reads "VNM công bố báo cáo tài chính". The adapter parses the ticker out of the title → `company_code="VNM"`. But for `company_name` it has nothing parsed, so it emits `company_name=""` (empty, allowed — AD-1 sets no non-null constraint on `company_name`).

Both obey AD-1 (fields present) and AD-4 (code is uppercase, regex-clean, from VN30 list). **Yet they disagree on whether `company_name` is populated.** Downstream, any consumer that joins on `company_name` (e.g., a name-canonicalization pass before NLP) treats A as a VNM row and B as an *unknown-entity* row — silently dropping B, or doubling VNM under two name spellings when Cafef later emits "Vinamilk".

**Worse variant — ticker-in-the-wrong-field:** AD-4 constrains `company_code` but says nothing about what goes in `company_name`. An adapter may legally put `"VNM"` (the ticker) into `company_name` while leaving `company_code` null (Tier-2, nullable). Now the *same ticker lives in two different columns across adapters*. A `WHERE company_code = 'VNM'` filter (the VN30 universe filter implied by AD-5) drops every Tier-2 row that parked the ticker in `company_name`. The model loses all Tier-2 news for that ticker.

**AD gap:** AD-4 governs only `company_code`'s format; no AD governs (a) `company_name`'s required content/normalization, (b) the rule "ticker goes in code, never in name", or (c) cross-field consistency ("if code is non-null, name MUST be the VN30-canonical name for that code").

**Fix — new AD-4b (company_name binding):**
> `company_name`, when `company_code` is non-null, MUST equal the `company_name` from `config/vn30.yaml` for that code (single canonical display name; no aliases, no legal-name variants). A ticker string MUST NEVER appear in `company_name`. When `company_code` is null (Tier-2 pre-NLP), `company_name` MUST also be empty — the ticker, if mentioned, is captured in `raw_text` only, awaiting NLP enrichment. This closes both the name-drift and the ticker-in-wrong-field cracks.

---

## HOLE 2 — `publish_time` "UTC" strings that aren't comparable (data-corrupting, silent)

**AD text at fault:** AD-3 — "lưu `publish_time`/`crawl_time` ISO-8601 **UTC** (`...Z`)." The rule mandates the *suffix* `Z` but is silent on (a) precision (date-only vs second vs microsecond), (b) timezone of the *source* value before conversion, and (c) what to do when the source carries no time at all.

**The incompatible pair — all three rows literally end in `Z`, all AD-3-compliant:**

- **VSDC:** feed timestamp `2026-03-15 09:00:00` with no timezone marker. VSDC is a Vietnam system; a defensible reading is "this is +07 local" → adapter converts → `publish_time="2026-03-15T02:00:00Z"`.
- **Vietstock disclosure:** page shows `15/03/2026` (date only, no time). Adapter, obeying "emit UTC Z", does one of: `"2026-03-15T00:00:00Z"` (date-at-midnight UTC), or `"2026-03-14T17:00:00Z"` (midnight +07 → UTC). **Both are reasonable; AD-3 does not say which.** The two adapters pick differently.
- **Tier-2 RSS:** `<pubDate>Mon, 15 Mar 2026 09:00:00 +0700</pubDate>`. Adapter strips the offset honestly → `2026-03-15T02:00:00Z`.

All three pass AD-3's literal test (string ends in `Z`, ISO-8601). **But row 2 is ambiguous by up to 7 hours, and the two readings of "date-only" place the same disclosure on different UTC days.** A volatility model that buckets events by UTC trading day (`publish_time.dt.date`) will, for a date-only Vietstock disclosure, classify the event into *yesterday* or *today* depending on which adapter author wrote the conversion. This is a silent, undetectable label error in a training set — the worst class of bug for this system.

A second crack in the same AD: AD-3 says nothing about **naive vs aware at the pandas layer**. If one adapter writes `2026-03-15T02:00:00Z` and another writes `2026-03-15T02:00:00+00:00` (both valid ISO-8601 UTC, both end in a UTC marker), `pd.to_datetime` parses them identically — but if a third writes `2026-03-15T02:00:00` (trailing-Z forgotten in one branch), pandas treats it as naive and a `tz_compare` against aware values raises or silently miscompares. AD-3's "`...Z`" shorthand doesn't forbid the `+00:00` form nor enforce a single canonical form.

**AD gap:** AD-3 fixes the timezone but not (a) date-only semantics, (b) source-tz assumption when absent, (c) a single canonical UTC string form.

**Fix — tighten AD-3 (canonical timestamp form):**
> (a) `publish_time` and `crawl_time` MUST be ISO-8601 UTC in exactly the form `YYYY-MM-DDTHH:MM:SSZ` (seconds precision, literal trailing `Z`; neither `+00:00` nor microsecond fractional). (b) When the source timestamp has an explicit offset, convert to UTC. (c) When the source timestamp has **no offset** (VSDC, Vietstock pages), it MUST be treated as `+07` (Asia/Ho_Chi_Minh) and converted — this is a single project-wide rule, not per-adapter judgment. (d) When the source has **date only** (no time), emit `YYYY-MM-DDT00:00:00Z` after converting the date as midnight +07 → `YYYY-DD-YYT17:00:00Z` of the previous day; record the date-only origin in an audit field (not a new ObjectiveRecord column — log only). (e) `build_objective.py` MUST reject (not silently coerce) any `publish_time` not matching `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`.

---

## HOLE 3 — null `company_code` in Tier-2 rows breaks the VN30 universe filter at merge (AD-5 × AD-8 seam)

**AD text at fault:** AD-4 permits Tier-2 `company_code` to be null ("raw capture chỉ"). AD-5 says every adapter reads `config/vn30.yaml` for the universe filter. AD-8 says `build_objective.py` merges per-source CSVs into the versioned dataset. **No AD states whether the unified dataset is VN30-filtered or universe-all, nor how null-code rows survive the filter.**

**The incompatible pair:**

- **Tier-2 RSS adapter** obeys AD-4: emits `company_code=""` (null/empty) for a market-news article that mentions VNM in passing but has no parsed ticker. AD-4 explicitly blesses this.
- **`build_objective.py`** (AD-8) is told by AD-5 to "filter to VN30 universe". The only field it can filter on is `company_code`. A row with `company_code=""` fails `company_code ∈ VN30`. The build step now faces an underspecified choice: (a) drop the row (losing Tier-2 coverage that AD-4 explicitly allowed to be captured), or (b) keep it (violating "filter to VN30"). **Both choices are consistent with the spine as written.** Two implementers reading the same spine ship different datasets.

The deeper corruption: if the build keeps null-code rows (choice b) and a later NLP pass enriches them, the *post-hoc* join of enriched news onto Tier-1 disclosures can produce **two owners of the VNM entity-time** — a VSDC dividend row (code=VNM, real timestamp) and a Tier-2 news row (code enriched to VNM later, fuzzy timestamp from HOLE 2) — that the model cannot reconcile as same-event vs separate-event. AD-6's checksum dedup does not save you here: news-body text and a VSDC structured action are *different text* → different checksums → never deduped, even when they describe the identical corporate action.

**AD gap:** No AD defines (a) whether the unified dataset is VN30-filtered or retains unfiltered Tier-2, (b) the contract for late-enrichment re-joining, (c) the rule that a Tier-2 row with null code is *deferred* (not dropped, not joined) until NLP stamps a code.

**Fix — new AD-8b (universe gate + enrichment re-join contract):**
> (a) The unified `objective_v<date>.csv` retains VN30-filtered Tier-1 rows AND Tier-2 rows with null `company_code` (flagged) — Tier-2 is captured-now-enrich-later by design (Deferred list). (b) A Tier-2 row with null `company_code` MUST NOT be joined to a Tier-1 entity-time record in any downstream objective dataset until NLP assigns a code; `build_objective.py` emits them into a separate `objective_v<date>_unenriched.csv` companion file, never into the primary join set. (c) The enrichment re-join is a *new build step* (not a mutation of existing rows): enriched Tier-2 rows get a fresh `document_id` namespace suffix and a provenance field recording they were NLP-derived, not source-derived. This makes "two owners of one entity" impossible — the primary dataset has only source-derived codes; NLP-derived codes live in a clearly-separated companion.

---

## HOLE 4 — `normalize(raw_text)` is undefined → cross-source checksum dedup both over- and under-fires

**AD text at fault:** AD-6 — "checksum = `sha256(normalize(raw_text))` dedup cross-source". The function `normalize` is **never defined**. The codebase already has `utils/body_extractor.py::normalize_body` — but that function is a *display* normalizer (collapses whitespace, drops boilerplate lines, keeps paragraphs). It is not specified as the checksum normalizer, and even if it were, it has properties that break cross-source dedup:

**The incompatible pair — both faithfully compute "sha256 of normalized raw_text":**

- **Vietstock disclosure adapter** extracts `raw_text` from its own HTML via its selector, runs `normalize_body` (drops `<script>`, collapses whitespace, strips "TIN MỚI"/"XEM THÊM" boilerplate per the regex in body_extractor.py). Checksum = `H_A`.
- **Cafef disclosure adapter** republishes the *same* announcement (VSDC disclosures are cross-posted to Cafef verbatim). But Cafef wraps the text in different HTML (different nav, ads, related-news sidebar). Cafef's selector pulls `div.detail-content`, which excludes some wrappers Vietstock includes. After `normalize_body`, the two texts **differ by the boilerplate/related-news lines that one selector captured and the other didn't** → `H_B ≠ H_A`. **The same document escapes cross-source dedup** — the exact failure AD-6 exists to prevent. AD-6 is satisfied on paper (a checksum was computed) but defeated in effect.

**The inverse failure (different docs collide):** `normalize_body` truncates with `max_chars` and drops short lines. Two different disclosures that share a long identical opening paragraph but diverge later, *if both adapters apply head-truncation before checksumming*, hash to the same value → **two distinct events collapse into one**. The spine never says whether truncation is part of checksum-normalization.

**A third normalization axis the AD ignores: Unicode normalization.** Vietnamese text routinely arrives in either NFC or NFD (composed vs decomposed diacritics). `raw_text` from `requests` (encoding forced to utf-8) and from Playwright (`innerHTML`) can be in *different* Unicode forms for the *same* bytes-after-normalization. `sha256("đ")` in NFC ≠ `sha256("đ")` in NFD. Two adapters, one HTTP (NFC) one browser (NFD), emit the same Vietnamese sentence with different checksums. AD-6 never mentions `unicodedata.normalize`.

**AD gap:** AD-6 names the dedup key (`normalize(raw_text)`) but leaves the function undefined, permitting per-adapter divergence in (a) selector scope, (b) truncation, (c) Unicode form, (d) case, (e) whitespace rules.

**Fix — tighten AD-6 (define `normalize` as a single canonical function):**
> `normalize(raw_text)` for checksum purposes is **one function**, `objective/schema.py::checksum_normalize(text)`, distinct from `body_extractor.normalize_body` (which remains for display). It MUST: (a) `unicodedata.normalize("NFC", text)` first; (b) lowercase; (c) strip all HTML tags and entities; (d) collapse all whitespace (spaces, tabs, newlines) to a single space and trim; (e) remove a fixed boilerplate list defined in `schema.py` (the same list for every adapter); (f) **NOT truncate** (checksum is over full normalized text — truncation is display-only). Every adapter imports and calls this exact function; no adapter may define its own. A conformance test asserts `checksum_normalize(text_from_vietstock_html) == checksum_normalize(text_from_cafef_html)` on a fixture pair of the same cross-posted announcement.

---

## HOLE 5 — `document_id = sha1(source+url)[:16]` collides and diverges on canonicalization gaps

**Convention text at fault:** Consistency table — "`document_id` = `sha1(source+url)`[:16]". This has two cracks the spine doesn't address.

**(a) Diverges when the same doc has different URLs across sources.** VSDC hosts a disclosure at `vsdc.com.vn/.../doc/12345`; Vietstock mirrors it at `vietstock.vn/.../tdtc-12345-abc`. Same document, different `source+url` → two different `document_id`s. This is *fine* for raw-path isolation (AD-2 wants per-source raw files), but it means `document_id` is **not** a cross-source document key. AD-6's checksum is the only cross-source key. But nothing in the spine says so explicitly — a downstream consumer that joins on `document_id` (the natural reading of a field literally named "document id") will double-count every cross-posted disclosure. The field name promises a property the value doesn't have.

**(b) Collides when url canonicalization differs within one source.** Two adapters (or the same adapter across runs) may canonicalize query-string order differently: `?a=1&b=2` vs `?b=2&a=1`. `sha1(source+url)` then differs → resume dedup (AD-6 url-dedup) misses the already-seen doc → re-crawl. Inversely, if one adapter strips trailing slashes and another doesn't, `url/` and `url` hash differently within the *same* source — a silent resume miss. The spine defines no url canonicalization rule; `base_news_crawler._load_seen` compares raw `url` strings with no normalization (confirmed in code: `seen.add(u)` on the raw value). AD-6 inherits this.

**The incompatible pair:** Adapter A (VSDC) canonicalizes by sorting query params; Adapter B (Cafef), written by another implementer, doesn't. Both "dedup by url" per AD-6. Adapter B re-crawls ~10% of its corpus every run (query-param reordering on Cafef pagination URLs is common). Neither violates the AD.

**AD gap:** No AD defines (a) url canonicalization before id-hashing and dedup, (b) that `document_id` is a per-source raw-path key, NOT a cross-source document identity (checksum is).

**Fix — new AD-6b (url canonicalization + document_id semantics):**
> (a) `canonicalize_url(url)` = lowercase scheme+host, strip default port, remove trailing slash (except root), **sort query parameters by key**, drop fragment. This one function is applied before *both* resume url-dedup and `document_id` hashing, in every adapter. (b) `document_id` is a **per-source raw-storage key** (`data/raw/<source>/<document_id>`) and a **per-source resume key** — it is NOT guaranteed unique across sources and MUST NOT be used as a cross-source join key by downstream. Cross-source document identity is the `checksum` field (AD-6) only. `objective/schema.py` exposes both with docstrings stating this, and `build_objective.py`'s merge joins on checksum for cross-source dedup, never on document_id.

---

## HOLE 6 — `category` and `event_type` are both listed but their relationship is unspecified → two adapters can populate them inconsistently

**AD text at fault:** AD-1 lists both `category` and `event_type` as ObjectiveRecord fields. AD-11 defines the `event_type` enum strictly. **No AD defines `category` at all** — not its type, not its value domain, not its relationship to `event_type`. Is `category` a free-text section label ("Doanh nghiệp", "Thị trường")? A duplicate of `event_type`? A finer sub-taxonomy?

**The incompatible pair — both AD-1 + AD-11 compliant:**

- **Adapter A (Vietstock disclosure):** reads the page's breadcrumb as `category="Báo cáo tài chính"` (Vietnamese label) and maps the same fact to `event_type="financial_statement"` (per AD-11 enum).
- **Adapter B (Cafef disclosure):** reads its breadcrumb as `category="Finance"` (English) or leaves `category=""` (no breadcrumb on disclosure pages) and sets `event_type="financial_statement"`.

Both have a valid `event_type` (AD-11 ✓) and both have *some* value in `category` (AD-1 ✓, field present). **But `category` is now a free-for-all column** — Vietnamese in A, English in B, empty in a third adapter. Any downstream group-by on `category` is meaningless; and because `event_type` is the *only* governed taxonomy field, `category` becomes dead weight that either (a) misleads a consumer into grouping on it, or (b) forces every consumer to learn to ignore it. The spine spent a whole AD (AD-11) tightening `event_type` and zero words on `category`, leaving exactly the kind of ungoverned field AD-1 was meant to eliminate.

**AD gap:** `category` is in the ObjectiveRecord (AD-1) but ungoverned — no domain, no type, no nullable rule, no source.

**Fix — tighten AD-1 + new AD-11b (category semantics):** Either (preferred) **remove `category` from ObjectiveRecord** entirely — `event_type` (AD-11) is the governed taxonomy and `category` adds no governed information; or (if retained) define it as: `category` is a free-text **source-native section label** in the source's original language, nullable, documented as non-canonical and "for traceability only, not for grouping." The fix must pick one explicitly; leaving it as-is is the defect.

---

## HOLE 7 — `raw_text` extraction source differs (HTML body vs PDF text vs listing-snippet) → checksum compares apples to oranges across tiers

**AD text at fault:** AD-1 lists `raw_text` with no definition of *what it is*. AD-6 hashes it. The structural seed shows adapters handle HTML (Cafef, Tier-2), PDF (Vietstock disclosure attachments), and structured feeds (VSDC). **No AD says which representation of the document feeds `raw_text`.**

**The incompatible pair:**

- **Vietstock disclosure (browser):** the "document" is a PDF attachment. `raw_text` = PyMuPDF-extracted PDF text (per `body_extractor` PDF path). Includes page headers/footers, pagination artifacts.
- **Cafef disclosure (HTTP):** same corporate action, but Cafef's version is an HTML article (the PDF was transcribed to HTML). `raw_text` = `div.detail-content` text.

Both emit `raw_text`. Both run AD-6's `normalize(raw_text)`. **But the PDF extraction injects page-break artifacts and omits hyperlinked context that the HTML version includes.** Even after HOLE 4's canonical `checksum_normalize`, the two texts differ by artifacts → different checksums → same event not deduped cross-source. The root cause is that `raw_text` is defined per-*adapter-medium* rather than per-*document-canonical-form*.

**AD gap:** `raw_text` is the checksum input (AD-6) yet its extraction source/medium is ungoverned, so checksums compare different representations of the same document.

**Fix — tighten AD-1 (raw_text definition):**
> `raw_text` is the **canonical text representation** of the document used for both checksum and downstream NLP. For HTML-sourced documents it is the article-body text per `body_extractor` with the source's selector; for PDF-sourced documents it is the PyMuPDF text *after* stripping page headers/footers and pagination artifacts via a shared `objective/schema.py::pdf_clean(text)` (defined once). For structured feeds (VSDC) with no free text, `raw_text` is a stable serialized form of the structured fields (key-sorted, single canonical serializer), and `event_type` carries the semantic. A conformance test holds a fixture of the same VSDC action posted as HTML, PDF, and feed, and asserts all three `checksum_normalize` to the same hash — if they cannot (medium-intrinsic differences), the checksum-dedup is documented as *same-medium-only* and cross-medium dedup is deferred to NLP.

---

## Lower-confidence observations (not blocking, but worth a tightening pass)

- **AD-9 (objective/opinion separation)** is a strong, clean invariant — no adversarial crack found. One minor risk: it forbids merging opinion CSVs but doesn't forbid an adapter from *reading* an opinion source for disambiguation (e.g., resolving a ticker from an SSI research note). Probably fine (read ≠ merge), but a one-line clarification ("separation is at the *dataset* boundary, not the *read* boundary") would prevent a future implementer from over-restricting.
- **AD-7 (two adapter families)** correctly routes both to AD-1. The only latent risk: the browser adapter reusing `VietstockCrawler` inherits its `HN_TZ`/`now_iso()` (+07) — AD-3 flags this as a divergence but the *fix* ("adapter objective PHẢI ghi UTC, không kế thừa `now_iso()`") is stated for timestamps. Good. But the same `VietstockCrawler` also inherits its `pdf_url`-based dedup (`utils/dedup.py` keys on `pdf_url`, not `url`) — the objective layer keys on `url` (AD-6). An adapter that mixes the two dedup keys (inherits parent's `pdf_url` seen-set but emits ObjectiveRecords keyed by `url`) will silently re-emit or silently drop. AD-6 should state the objective layer uses `url` exclusively and must not inherit the `pdf_url` seen-set.
- **AD-2 (raw derivable from cleaned)** is sound. Minor: "cleaned must be derivable from raw" is a one-way property; no AD says raw is *append-only / immutable*. If an adapter overwrites a raw file on re-crawl (same `document_id`, updated content), the old cleaned record in a versioned `objective_v<date>.csv` is no longer derivable from the mutated raw. An immutability clause (raw files are write-once; updates get a new `document_id`) would close this.

---

## Summary table — holes, severity, fix

| # | Hole (incompatible pair) | Severity | AD gap | Fix |
|---|---|---|---|---|
| 1 | `company_code`/`company_name` ticker-placement diverges | **Data-corrupting** | AD-4 governs code format only | New AD-4b: company_name bound to VN30 canonical; ticker never in name; null code ⇒ null name |
| 2 | `publish_time` "UTC" strings not comparable (date-only, source-tz, form) | **Data-corrupting** | AD-3 fixes tz not form/semantics | Tighten AD-3: single form `...SZ`; no-offset⇒+07; date-only rule; build-time regex reject |
| 3 | Null Tier-2 `company_code` vs VN30 filter at merge | **High** | AD-4×AD-8 seam; no universe-gate contract | New AD-8b: unenriched Tier-2 to companion file; enrichment is new-build not mutation |
| 4 | `normalize(raw_text)` undefined → checksum over/under-fires | **High** | AD-6 names key, not function | Tighten AD-6: single `checksum_normalize` (NFC, lower, strip, no-trunc) in schema.py |
| 5 | `document_id` collides/diverges on url-canonicalization gaps | Medium | Convention line, no canonicalization AD | New AD-6b: `canonicalize_url`; document_id is per-source key only |
| 6 | `category` ungoverned beside governed `event_type` | Medium | AD-1 lists it, no AD defines it | Remove `category` from ObjectiveRecord, or define as traceability-only free-text |
| 7 | `raw_text` medium differs (HTML/PDF/feed) → checksums incomparable | Medium | AD-1 lists it, no AD defines source | Tighten AD-1: raw_text canonical form per medium + shared pdf_clean; conformance test |

**Blocking for spine finalization:** Holes 1, 2, 3 (data-corrupting / silent / at the merge seam the whole architecture pivots on). Holes 4–7 are high/medium and should be closed in the same pass since they share a root cause: **the spine governs field presence (AD-1) but not field value-semantics**, and governs function *names* (AD-6 `normalize`) without the function *bodies*. The recurring fix shape is: lift every shared computation (timestamp form, url canonicalization, checksum normalize, company_name binding, raw_text medium) into `objective/schema.py` as a single owned function with a conformance test, and reword the ADs to *name that function* rather than describe an operation in prose.
