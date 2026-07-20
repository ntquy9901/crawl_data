"""Debug traderviet.io HTML structure."""
import re

import requests

url = 'https://traderviet.io/forums/phan-tich-chung-khoan-viet-nam.71/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
r = requests.get(url, headers=headers, timeout=30)
print(f'Status: {r.status_code}')
print(f'Length: {len(r.text)}')

# Check for blocking
if 'cloudflare' in r.text.lower() or 'just a moment' in r.text.lower():
    print('BLOCKED by Cloudflare')
if 'captcha' in r.text.lower():
    print('CAPTCHA detected')
if 'attention' in r.text.lower():
    print('Attention check detected')

# Find all div classes related to threads
classes = set(re.findall(r'class="([^"]*)"', r.text))
for c in sorted(classes):
    cl = c.lower()
    if any(x in cl for x in ['struct', 'thread', 'item', 'message', 'content', 'main', 'title', 'list', 'block']):
        print(f'  class: {c}')

# Look for thread URLs
urls = re.findall(r'href="(/threads/[^"]*)"', r.text)
print(f'Thread URLs found: {len(urls)}')
for u in urls[:10]:
    print(f'  {u}')

# Check for JSON-LD
jsonld = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.DOTALL)
print(f'JSON-LD blocks: {len(jsonld)}')

# Look for XenForo-specific markers
for marker in ['xenforo', 'xf', 'structItem', 'discussionList', 'threadList', 'data-xf']:
    if marker in r.text.lower():
        print(f'XenForo marker found: {marker}')

# Save a sample for inspection
with open(r'C:\Users\QUY\AppData\Local\Temp\traderviet_sample.html', 'w', encoding='utf-8') as f:
    f.write(r.text[:50000])
print('Saved sample to temp')
