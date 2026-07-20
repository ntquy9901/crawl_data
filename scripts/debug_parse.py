"""Debug forum_crawler parsing."""
import requests

url = 'https://traderviet.io/forums/phan-tich-chung-khoan-viet-nam.71/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
r = requests.get(url, headers=headers, timeout=30)
html = r.text

# Check exact text around structItem
idx = html.find('structItem structItem--thread')
if idx >= 0:
    # Show 200 chars before and 4000 chars after
    start = max(0, idx - 200)
    end = min(len(html), idx + 4000)
    snippet = html[start:end]
    print(f"Context around first structItem--thread (at byte {idx}):")
    print(snippet)
    print("\n\n---")
    print(f"structItem--thread occurrences: {html.count('structItem structItem--thread')}")
else:
    print("structItem structItem--thread NOT FOUND in raw HTML")
    # Look for alternate class format
    alt = html.find('structItem--thread')
    if alt >= 0:
        print(f"Found 'structItem--thread' at {alt}")
        print(html[max(0,alt-200):alt+2000])
