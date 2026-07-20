"""Debug the exact same path the crawler uses."""
import re
import sys

sys.path.insert(0, r'C:\luanvan\crawl_data')

from urllib.parse import urljoin

import requests

from base_news_crawler import strip_html

url = 'https://traderviet.io/forums/phan-tich-chung-khoan-viet-nam.71/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
r = requests.get(url, headers=headers, timeout=30)
html = r.text

# Try the exact split approach from the crawler
parts = html.split('structItem structItem--thread')
print(f'Parts from split: {len(parts)} (first is before first match)')
print(f'Total "structItem structItem--thread" count: {html.count("structItem structItem--thread")}')

items = []
for part in parts[1:]:
    # Extract thread URL
    m = re.search(r'href="(/t/[^"]+)"[^>]*>(.*?)</a>', part, re.DOTALL)
    if m:
        thread_url = m.group(1)
        title = strip_html(m.group(2))
        full_url = urljoin('https://traderviet.io', thread_url)

        # Author
        author = ''
        m2 = re.search(r'data-author="([^"]+)"', part)
        if m2:
            author = m2.group(1)

        # Date
        pub_date = ''
        m3 = re.search(r'<time[^>]*datetime="([^"]+)"', part)
        if m3:
            pub_date = m3.group(1)[:19]

        # Reply count
        reply = 0
        m4 = re.search(r'<dt>\s*Trả lời\s*</dt>\s*<dd[^>]*>\s*([\d,]+)\s*</dd>', part)
        if m4:
            reply = int(m4.group(1).replace(',', ''))

        # View count
        views = 0
        m5 = re.search(r'<dt>\s*Xem\s*</dt>\s*<dd[^>]*>\s*([\d,]+)\s*</dd>', part)
        if m5:
            views = int(m5.group(1).replace(',', ''))

        items.append({
            'url': full_url,
            'title': title,
            'author': author,
            'pub_date': pub_date,
            'reply_count': reply,
            'view_count': views,
        })

print(f'\nThreads found: {len(items)}')
for item in items[:5]:
    print(f'  Title: {item["title"][:60]}')
    print(f'  URL: {item["url"]}')
    print(f'  Author: {item["author"]}')
    print(f'  Date: {item["pub_date"]}')
    print(f'  Replies: {item["reply_count"]}, Views: {item["view_count"]}')
    print()
