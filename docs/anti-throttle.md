# Anti-throttle / chống block IP — research SOTA (2025–2026) + design cho Cafef

## Vấn đề Cafef (verify 2026-07-05)
Cafef **rate-limit theo IP** khi fetch article sustained: single request OK (classify đúng section), nhưng concurrent liên tục → trả soft-block page (HTML không có breadcrumb) → `kept=0`. Test: workers=4/10/20 đều 0 kept sau 1000–3000 processed. **Không phải Cloudflare/TLS** (vì single OK) → giải pháp phải xoay vòng **IP**, không phải giả TLS.

## SOTA options (2025–2026)

| Cách | Defeat IP rate-limit? | Cost | Engineering | Note |
|---|---|---|---|---|
| **Rotating residential proxy** (Bright Data, Oxylabs, Smartproxy/Decodo, IPRoyal) | ✅ ĐÚNG chỗ này | $1.75–15/GB | Trung bình | Mỗi request 1 IP residential → cafef thấy nhiều IP, không rate-limit 1 IP. **Recommend cho Cafef.** |
| **Scraping API** (ZenRows, ScraperAPI, ScrapingBee, Scrapingdog) | ✅ (họ xoay IP) | ~$1–8 / 1K req | Thấp (gọi API) | Turnkey: họ lo proxy+anti-bot+JS+CAPTCHA. Nhưng full backfill 746k bài = $750–6000. Daily (50 bài) thì rẻ. |
| **curl_cffi** (TLS/JA3/JA4 impersonate) | ❌ KHÔNG (cùng IP) | Free | Trung bình | Giả vỏ TLS browser → vượt anti-bot **dựa TLS** (Cloudflare basic, Akamai). Cafef là rate-limit IP → không giúp. (Hữu ích cho site Cloudflare thay Playwright — nhanh hơn.) |
| **Politeness** (workers=1 + random delay 2–5s) | ⚠️ Né dưới ngưỡng | Free | Thấp | Ở dưới rate limit thì không bị block. Free nhưng deep backfill 746k bài = vài tuần. **OK cho daily (ít bài).** |
| **FlareSolverr** (Cloudflare JS challenge) | ❌ | Free/self-host | — | Cafef không phải Cloudflare JS challenge → không áp dụng. |

**Provider proxy (xếp hạng 2025–2026):** Bright Data/Oxylabs = premium (pool lớn nhất, anti-bot mạnh, đắt); Smartproxy/Decodo = cân bằng; IPRoyal = budget (nhiều GB/$). Nguồn: [Bright Data vs Oxylabs](https://brightdata.com/blog/comparison/bright-data-vs-oxylabs), [Scrapfly top proxies](https://scrapfly.io/blog/posts/top-5-residential-proxy-providers), [AIMultiple 2026](https://aimultiple.com/residential-proxy-providers).

## Design cho Cafef (recommend)
**2 lớp tuỳ quy mô:**

1. **Daily (ít bài, ~50/ngày)** → **Politeness** (free): `cafef_crawler.py --daily` vốn dùng RSS (không fetch article), nên không throttle. Đã OK. Không cần proxy.
2. **Deep backfill (746k bài)** → **Rotating residential proxy** qua `utils/proxy_manager.py` (đã có sẵn, dormant, hỗ trợ `IP:PORT:USER:PASS`):
   - Wire `proxy_manager` vào `cafef_crawler._fetch_once`: mỗi article fetch lấy 1 proxy random từ pool → `requests.get(url, proxies=...)`. IP chết → `mark_dead` + retry proxy khác.
   - User nạp residential proxy vào `proxies.txt` (từ IPRoyal/Smartproxy, ~$5–15 thử nghiệm) + `USE_PROXY=true` trong `.env`.
   - Kết hợp `workers=8–10` (giờ an toàn vì mỗi request IP khác).
   - Code change nhỏ trong `_fetch_once` (~10 dòng) + bật `USE_PROXY`.

**Fallback (không muốn trả tiền):** politeness `workers=1` + delay 3s → ~20 bài/phút → daily OK, backfill deep không khả thi → chấp nhận daily RSS tích lũy.

## Không recommend cho Cafef
- **curl_cffi**: không giải quyết rate-limit IP (chỉ TLS). (Có thể dùng cho **VNDIRECT** thay Playwright cho nhanh hơn — Cloudflare của VNDIRECT có thể bị vượt bằng curl_cffi + proxy, nhưng đã có Playwright working → để sau.)
- **Scraping API**: đắt cho full backfill; chỉ hợp lý nếu thuê theo daily (rẻ).

## sources
- [Bright Data – Web Scraping with curl_cffi](https://brightdata.com/blog/web-data/web-scraping-with-curl-cffi)
- [Scrapfly – 11 Best Anti-Bot Bypass Tools](https://scrapfly.io/blog/posts/best-anti-bot-bypass-tools)
- [Scrapeway – ScraperAPI vs ZenRows benchmark](https://scrapeway.com/web-scraping-api/scraperapi/vs/zenrows)
- [curl_cffi repo](https://github.com/lexiforest/curl_cffi)
- [Datahut – bypass Cloudflare with curl_cffi](https://www.blog.datahut.co/post/web-scraping-without-getting-blocked-curl-cffi)
