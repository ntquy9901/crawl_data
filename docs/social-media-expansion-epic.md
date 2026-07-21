# Social Media Expansion — EPIC

## Objective

Collect stock/finance news & analysis from social media platforms popular in Vietnam.

## Background

Current project has 16+ news sources (newspapers, RSS, securities research). Missing:
- **Zalo OA** (dominant VN messaging, finance OAs)
- **Facebook Pages/Groups** (largest VN finance communities)
- **TikTok** (emerging finance content)

All 3 require different technical approaches vs. existing crawlers (anti-bot, auth, API).

---

## Epic A: Facebook Pages (Graph API)

**Priority: P0** — highest VN finance community density.

| Item | Detail |
|---|---|
| Approach | Meta Graph API v21+ with Page Public Content Access |
| Scope | Public Pages of VN securities firms (SSI, VNDIRECT, HSC, VPS, CafeF, Vietstock) |
| Data | Post text, pub_date, URL, engagement stats |
| Key blocker | App Review + Business Verification (2-4 weeks) |
| Crawler pattern | `BaseNewsCrawler` subclass, Graph API pagination (no Playwright) |
| Output | `data/facebook_articles.csv` |
| Dedup | By `url` per existing convention |

### Challenges
- App Review approval (requires business verification, privacy policy URL, video demo).
- Rate limit: `4800 × Engaged Users / 24h` for Pages API.
- Each page needs `?fields=posts{message,created_time,permalink_url}`.

### Acceptance
- [ ] 5+ VN finance pages scraped (latest posts)
- [ ] Backfill 1 year of posts per page
- [ ] All posts have `pub_date`, `url`, `body`
- [ ] output in `facebook_articles.csv`

---

## Epic B: Zalo OA

**Priority: P1** — high VN penetration, but limited to OAs you own.

| Item | Detail |
|---|---|
| Approach | Zalo OA OpenAPI v3.0 (`article/getslice`, `article/getdetail`) |
| Scope | Only OAs you own/manage (no third-party OA reading) |
| Data | Title, body, pub_date, URL |
| Crawler pattern | Plain HTTP API calls (not Playwright) |
| Key blocker | Must own/manage target OA to get API credentials |
| Output | `data/zalo_articles.csv` |

### Alternatives (High Risk)
- `zca-js` (unofficial reverse-engineered Zalo personal-account lib) — fragile, bans common.
- Playwright on `chat.zalo.me` with saved session — very high maintenance.

### Acceptance
- [ ] Zalo OA API wrapper functional
- [ ] At least 1 finance OA (e.g., VNDIRECT, TCBS) if credentials available
- [ ] Output in `zalo_articles.csv`

---

## Epic C: TikTok (Playwright rehydration)

**Priority: P2** — growing VN finance content, but highest technical risk.

| Item | Detail |
|---|---|
| Approach | Playwright + parse `SIGI_STATE` / `__UNIVERSAL_DATA_FOR_REHYDRATION__` blob from HTML |
| Scope | 20-30 finance hashtags (`#chungkhoan`, `#dautu`, `#tai chinh`) + ~10 creators |
| Data | Video description, pub_date, creator, URL, view count |
| Key challenge | TTWID binding, msToken rotation, device fingerprint |
| Crawler pattern | `BaseNewsCrawler` subclass, Playwright-based |
| Output | `data/tiktok_articles.csv` |

### Constraints
- Expect 14-22% block rate even with residential proxies.
- Signature-based API is NOT feasible for non-academic project (TikTok rotates signing alg every 2-8 weeks).
- Keep volume low (<50 accounts/hashtags) to reduce fingerprinting.

### Acceptance
- [ ] Playwright rehydration approach working on 3+ test accounts
- [ ] 10+ hours stable run without blocked IP
- [ ] Output in `tiktok_articles.csv`

---

## Effort Summary

| Epic | Initial | Ongoing | Recommend |
|---|---|---|---|
| A: Facebook | 2-4 weeks | 0h (API stable) | ✅ Start now |
| B: Zalo | 2-3 days | Low | ⏸ Wait until OA owned |
| C: TikTok | 2-4 weeks | 10-20h/mo | 🔶 Low priority |

## Roadmap

Phase 1 — Facebook Pages (Graph API approval → crawl)
Phase 2 — Zalo OA (if credentials available)
Phase 3 — TikTok (only if bandwidth allows)
